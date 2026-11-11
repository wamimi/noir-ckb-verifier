# R1. Noir 1.x support

Status: **spiked.** Spike code and exact commands:
[`spikes/noir-1x`](spikes/noir-1x/README.md). Nothing in `circuits/private-tally-v2` or
`ceremony/` was modified; every compile ran on a copy.

## 1. Problem and definition of done

`noir-ckb` is pinned to Nargo 1.0.0-beta.18. A developer who installs Noir today gets a
newer compiler and newer libraries, and the pinned path refuses their circuit. Before the
build period the project needs to know what moving costs, and in particular whether the
deployed tally survives it (same R1CS, same ceremony key) or needs a new ceremony.

Done when, for one named Noir release:

| # | Test | State |
| --- | --- | --- |
| D1 | The tally, compiled with that release, yields the frozen ceremony R1CS and a proof under the ceremony key that verifies | Passed in the spike for beta.26, rc.0 and rc.7 with a patched backend |
| D2 | The exact backend change is listed and is reviewable | Listed in section 5; spike patch is 107 lines in one crate |
| D3 | Everything outside the tested envelope is refused before proving | Shown for one unsupported opcode; the full list is section 6 |
| D4 | The same on the pinned Rust toolchains, in CI, on macOS and Linux | Not done |
| D5 | The CKB-VM matrices for counter and tally pass with artifacts from the new compiler | Not run; expected to be identical because the R1CS and keys are identical |

## 2. What was believed, and what the spike found

Belief: "the backend only needs small changes for Noir 1.x."

| Finding | Evidence |
| --- | --- |
| No final Noir 1.0.0 existed on 10 November 2026. The newest tag was `v1.0.0-rc.7` (28 October 2026); rc.1 to rc.7 had no release archive, rc.0 had one | `git ls-remote --tags noir-lang/noir`; release URLs returned 404 |
| The committed tally does **not compile** on beta.26 or any rc: `noir-lang/poseidon` v0.2.6 uses a slice literal the newer compiler rejects | spike: 16 compile errors |
| Poseidon v0.3.0 and v0.4.0 compile on beta.26 and the rcs and do **not** compile on beta.18. There is no library version that works on both sides | spike |
| With v0.3.0 or v0.4.0 the commitments are unchanged | spike: identical helper outputs for three vectors on every compiler |
| The pinned backend **cannot parse** the newer artifact | spike: "failed parsing" for beta.26, rc.0, rc.7 |
| The cause is the ACIR byte encoding, not the program. beta.18 writes bincode; beta.26 and the rcs write a format byte (`0x03`, compact MessagePack) followed by MessagePack | source: `acvm-repo/acir/src/serialization.rs` at rc.7; first bytes of both artifacts |
| Decoded, the tally's program is **identical** under beta.18 and rc.7, Brillig included, except that the rc form no longer carries `current_witness_index` | spike: JSON equality after recomputing that one field |
| With a decoder for the new encoding the backend emits the **frozen ceremony R1CS** and ceremony-key proofs verify | spike, D1 |
| The same holds for the counter, the Capsule fixture and both square-root fixtures | spike survey |
| It does **not** hold in general. A circuit with array access and integer operations got a different program and a different R1CS (876 to 746 constraints), and its memory operations have a new shape | spike survey, `wide` |

Verdict: the belief **held for the deployed applications and broke as a general
statement**. The change to accept the tally is small. The change to accept arbitrary
Noir 1.0 programs is not established, and a compiler bump can change the R1CS of any
circuit that is not as simple as the tally, which voids its setup.

## 3. Prior art

- [Sunspot](https://github.com/reilabs/sunspot/tree/0a9f7d01070cfb8b34cbfa77e4782e18adacc096)
  (Noir to Groth16 through gnark, audited) pins one compiler too: its README requires
  Noir 1.0.0-beta.22. Pinning one version is the norm for ACIR consumers, not a weakness
  specific to this project.
- Noir's own serialization keeps a format byte so that consumers can refuse what they do
  not understand
  ([`serialization.rs`](https://github.com/noir-lang/noir/blob/045e2ea3bfb96b9dd97f1bddfe5c4c9e704dec15/acvm-repo/acir/src/serialization.rs)).
  rc.7 defines formats 2, 3 and 4; Nargo rc.7 wrote format 3 for the tally.
- The backend already supports beta.18 through the same mechanism the spike used: decode
  with that version's `acir` crate, convert through JSON to the runtime (beta.19) types.

## 4. Options and the chosen design

| Option | Result | Cost | Risk |
| --- | --- | --- | --- |
| A. Stay on beta.18 | Works today | None | New users cannot use current Noir or libraries; grows worse monthly |
| B. Add a decoder for the 1.0 encoding and keep the beta.19 runtime (the spike) | Tally, counter, Capsule proven identical | About 110 lines in `noir-acir`, plus tests | ACVM beta.19 executes Brillig from a newer compiler; safe only inside a tested opcode set |
| C. Move the backend's runtime (`acir`, `acvm`) to the 1.0 release | The clean end state | Unknown: the first crate failed on one removed field; `noir-witness` (1,900 lines) and `noir-r1cs` (9,900 lines) were not reached | A large change to the least-tested component |
| D. Replace the backend with Sunspot's lowering | Audited lowering | New proof and key formats (gnark), new adapter, Go toolchain, and Sunspot is on beta.22, not 1.0 | Resets the Week 8 to 14 evidence |

**Chosen: B for the grant period, pinned to one named release, with C as a later, separate
piece of work.** B is small, was shown to keep the deployed key valid, and fails closed.
The release to pin is the final 1.0.0 if it exists when the work starts, otherwise the
newest rc with an official archive (rc.0 on the spike date).

## 5. The exact backend changes

In `crates/noir-acir` of `wamimi/Noir-Groth16`, on top of `828025f`
([spike patch](spikes/noir-1x/backend-noir-1x.patch)):

1. `Cargo.toml`: add the `acir` crate of the pinned 1.0 tag as a third decoder
   (`acir_rc`), next to `acir_legacy` (beta.18).
2. `deserialize_program_base64_compatible`: after the runtime decoder fails, try
   `acir_rc`; on success convert through JSON.
3. `upgrade_rc_program_json`: recompute `current_witness_index` as the highest witness
   index in each function (parameters, return values, expression terms, black-box inputs
   and outputs, Brillig outputs).
4. In the same function: refuse every opcode outside the tested set (`AssertZero`,
   `BrilligCall`, `RANGE`, `Poseidon2Permutation`) with a named error.

Not in the patch and required before merging:

5. Remove the spike's debugging switches and the permissive mode.
6. Record which decoder accepted the artifact in the interop output, and have `noir-ckb`
   compare the artifact's `noir_version` with the pinned release before calling the
   backend at all.
7. Tests in the backend: the six probe rows as fixtures (artifact in, R1CS hash out), and
   one artifact per refused opcode.
8. Memory operations (`MemoryInit`, `MemoryOp`): the rc form stores two witness indices
   and an operation flag serialized under the name `read`, where `false` is a read. The
   spike converts them only in permissive mode. Supporting arrays means adding them to
   the tested set with differential tests against Noir execution; it is not needed for
   the tally, the counter or Battleship as designed (bitmaps instead of arrays).

Outside the backend:

9. `circuits/`: a new circuit directory for any application that moves, with
   `noir-lang/poseidon` v0.4.0. `circuits/private-tally-v2` stays as it is; the deployed
   profile keeps building with beta.18 for as long as it is supported.
10. `toolchains/platforms.json`: a second Nargo entry with archive and binary hashes.
11. `scripts/private_tally.py`: no change was needed in the spike; the helper's output
    line has the same form.

## 6. What must fail closed

| Condition | Where refused | Tested in the spike |
| --- | --- | --- |
| Artifact `noir_version` not in the supported list | `noir-ckb` before the backend | no (exists today for beta.18) |
| ACIR format byte other than the one decoder supports (rc.7 defines a format 4) | decoder error | by construction: the rc.0 crate rejects it; not exercised |
| Opcode outside the tested set | `upgrade_rc_program_json` | yes: `wide` refused with "unsupported opcode BlackBoxFuncCall.XOR" |
| Public parameters not where the R1CS exposes them (the Week 8 failure) | existing layout gate | yes, indirectly: both square-root orders gave the expected R1CS |
| R1CS differs from the one the key was made for | setup check (`snarkjs zkey verify`) and hash pin | yes: `r1cs_is_frozen_ceremony_r1cs` |
| Witness does not satisfy the R1CS (for example a Brillig difference) | `snarkjs wtns check` before proving | yes, on every run |
| Poseidon library with the stale-cache bug used with more than 3 inputs | existing static test | not re-run |

## 7. Measured numbers

| Item | Value |
| --- | --- |
| Tally R1CS under beta.18, beta.26, rc.0, rc.7 | 3,338 constraints, 5 private and 4 public inputs, SHA-256 `5bd9cf5e…` in all four |
| Tally ACIR | 24 opcodes, 33 witnesses, identical; 3,234 bytes as bincode, 2,892 bytes as MessagePack |
| Counter R1CS under beta.18 and rc.7 | identical (`843ee202…`) |
| `wide` survey circuit | 876 constraints (beta.18), 746 (rc.7) |
| Noir unit tests of the tally | 21 passed on every compiler that compiled it |
| Spike patch | 2 files, 107 lines added, 1 changed |
| Build of Nargo rc.7 from source | 10 min 36 s on 2 cores |

## 8. Pinned tools for the work

Nargo: the chosen 1.0 release, by archive hash. Recorded on the spike date: beta.18 archive
`b7c39a6b…`, beta.26 `64048040…`, rc.0 `cb2e46e2…` (Linux x86_64). `noir-lang/poseidon`
v0.4.0. Backend: a new revision of the fork on top of `828025f`. Everything else as in
`toolchains/platforms.json`.

## 9. Test plan

1. Probe rows as CI jobs on both platforms with the pinned Rust (D4).
2. Differential test per supported circuit: Noir execution, backend witness, R1CS
   satisfaction, snarkjs verification, CKB-VM verification (the existing
   `check-private-tally-circuit.py` pattern, run under the new compiler).
3. Adversarial: an artifact with each refused opcode; an artifact with the format byte
   changed; an artifact whose `noir_version` is edited; a truncated bytecode; the Week 8
   private-first circuit. Each must stop before proving.
4. Counter and tally CKB-VM matrices with artifacts from the new compiler (D5).

## 10. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| N1 | Spike repeated on the pinned toolchains | `spikes/noir-1x/run.sh` prints "frozen R1CS: True" and "verified" for the patched rows on macOS and Linux |
| N2 | Patch cleaned (items 5 to 7) and merged into the fork | Backend tests pass; probe rows are fixtures |
| N3 | `noir-ckb` accepts two compiler pins | `noir-ckb build` on a 1.0 circuit succeeds; on any other version it stops with the supported list |
| N4 | A 1.0 copy of the tally circuit with poseidon v0.4.0 | Its R1CS hash equals the ceremony's; the 49-case matrix passes |
| N5 | Arrays (item 8), only if an application needs them | Differential tests for `MemoryInit` and `MemoryOp` |

## 11. Risks and open questions

| Risk | Handling |
| --- | --- |
| The final 1.0.0 changes the encoding or the default format again | The decoder is tied to one tag; a new tag is a new pin and a repeat of N1 |
| A later compiler changes the tally's ACIR, so the ceremony key no longer matches | Refused by the R1CS hash check. The deployed profile keeps its own compiler pin |
| ACVM beta.19 mis-executes newer Brillig | Witness check before proving turns this into a refusal, not an unsound proof; option C removes the cause |
| Developers expect arbitrary Noir | The supported set is printed by `noir-ckb check`; the first unsupported opcode is named in the error |
| Spike toolchain differed from the pins | N1 |

Open: whether to support beta.18 and 1.0 side by side for longer than the deployed
profiles need; whether option C should be proposed upstream to the backend's author
rather than carried in the fork.
