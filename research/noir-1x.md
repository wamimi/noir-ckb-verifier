# R1. Noir 1.x: a decoder bridge for named release candidates

Status: **spiked; one external review recorded in section 12.** What was built is a decoder
bridge that lets the pinned backend read artifacts from three named compilers for five
simple circuits. It is not Noir 1.x support; that is a separate milestone (section 10). Spike code and exact commands:
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
| D1 | The tally, compiled with that release, yields the frozen ceremony R1CS and a proof under the ceremony key that verifies | Passed in the spike for beta.26, rc.0 and rc.7 with a patched backend. No final 1.0.0 existed |
| D2 | The exact backend change is listed and is reviewable | Listed in section 5; spike patch is 107 lines in one crate |
| D3 | Everything outside the tested envelope is refused before proving | Not met. The external review showed four things that pass: any Brillig instruction, a relabelled beta.19 artifact, serialization format 4, and programs with several functions or a return value (section 12) |
| D4 | The same on the pinned Rust toolchains, in CI, on macOS and Linux | Not done |
| D5 | The CKB-VM matrices for counter and tally pass with artifacts from the new compiler | Not run; expected to be identical because the R1CS and keys are identical |

## 2. What was believed, and what the spike found

Belief: "the backend only needs small changes for Noir 1.x."

| Finding | Evidence |
| --- | --- |
| No final Noir 1.0.0 existed on 10 November 2026. The newest tag was `v1.0.0-rc.7` (28 October 2026); rc.1 to rc.7 had no release archive, rc.0 had one | `git ls-remote --tags noir-lang/noir`; release URLs returned 404 |
| The committed tally does **not compile** on beta.26 or any rc: `noir-lang/poseidon` v0.2.6 uses a slice literal the newer compiler rejects | observed during the spike; this row and its error count were not archived in the result files |
| Poseidon v0.3.0 and v0.4.0 compile on beta.26 and the rcs and do **not** compile on beta.18. There is no library version that works on both sides | spike |
| With v0.3.0 or v0.4.0 the commitments are unchanged | spike: identical helper outputs for three vectors on every compiler |
| The pinned backend **cannot parse** the newer artifact | spike: "failed parsing" for beta.26, rc.0, rc.7 |
| The cause is the ACIR byte encoding, not the program. beta.18 writes bincode; beta.26 and the rcs write a format byte (`0x03`, compact MessagePack) followed by MessagePack | source: `acvm-repo/acir/src/serialization.rs` at rc.7; first bytes of both artifacts |
| Decoded and upgraded, the tally's program was **equal** under beta.18 and rc.7, Brillig bytecode included, except that the rc form no longer carries `current_witness_index` | observed during the spike by JSON equality after recomputing that field; not archived (the survey files cover the other five circuits, not the tally). The comparison reads both programs as beta.19 types: it shows equal bytes, not equal execution, and it does not compare the ABI |
| With a decoder for the new encoding the backend emits the **frozen ceremony R1CS** and ceremony-key proofs verify | spike, D1 |
| The same holds for the counter, the Capsule fixture and both square-root fixtures | spike survey |
| It does **not** hold in general. A circuit with array access and integer operations got a different program and a different R1CS, and its memory operations have a new shape | spike survey, `wide`: the two inequalities are recorded. The constraint counts seen (876 and 746) were not archived |

Verdict: the belief **held for the deployed applications and broke as a general
statement**. The change to read the tally's artifact is small. The change to accept
arbitrary Noir 1.0 programs is not established, and a compiler bump can change the R1CS of
any circuit that is not as simple as the tally, which voids its setup. The external review
added a second reason: the backend's beta.19 Brillig VM does not execute rc Brillig
identically (section 12, finding 1), so reading an artifact is not the same as running it
correctly.

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
| B. Add a decoder for the rc encoding and keep the beta.19 runtime (the spike): a decoder bridge | Tally, counter, Capsule: same R1CS | About 110 lines in `noir-acir` for the decoder. The 110 lines are not the cost of the option: it also needs a validated Brillig instruction set and differential tests against the matching runtime, which were not sized | ACVM beta.19 executes Brillig from a newer compiler, with known differences; acceptable only inside a validated instruction set |
| C. Move the backend's runtime (`acir`, `acvm`) to the 1.0 release: one compiler/runtime pair | The clean end state | Unknown: the attempt stopped at the first compiler error (one removed field); `noir-witness` (1,900 lines) and `noir-r1cs` (9,900 lines) were not reached, so B and C have not been compared on cost | A large change to the least-tested component |
| D. Replace the backend with Sunspot's lowering | Audited lowering | New proof and key formats (gnark), new adapter, Go toolchain, and Sunspot is on beta.22, not 1.0 | Resets the Week 8 to 14 evidence |

**Chosen after the review: two separate pieces of work.**

- *The bridge (B)*, for one named release candidate and for a bounded, validated set of
  artifacts: the four ACIR opcodes and an explicit list of Brillig instructions and
  operand forms. It was shown to keep the deployed key valid for the tally. It did not
  fail closed as claimed (D3), and it is not described as Noir 1.x support anywhere.
- *Noir 1.x support*, its own milestone (N6): one pinned compiler and the matching runtime
  (option C, or B plus differential tests of every admitted instruction against the rc VM),
  chosen after C has been sized. A final 1.0.0, when it exists, is a new pin and a new
  acceptance run, not something the bridge covers.

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
   `BrilligCall`, `RANGE`, `Poseidon2Permutation`) with a named error. The spike stops
   there, which admits any instruction inside the Brillig functions. Required before
   merging: an allow-list of Brillig instructions and operand forms that refuses at least
   `Shl`/`Shr`, relative addressing, `MultiScalarMul` and the other black-box operations
   whose checks changed, until each has a differential test (review finding 1).

The recomputed `current_witness_index` is an inclusive allocation bound over operational
witnesses. The walk does not visit assertion payloads or `Call.inputs`; that is harmless
for the four allowed opcodes and must become a typed visitor before the set grows (review
finding 8).

Not in the patch and required before merging:

5. Remove the spike's debugging switches and the permissive mode.
6. Record which decoder accepted the artifact in the interop output. Apply the support
   policy after whichever decoder succeeded, and refuse an artifact whose `noir_version`
   family does not match the decoder that read it. Refuse programs with more than one
   function or with return values at admission. `noir_version` is an editable string:
   `noir-ckb build` must take the artifact from a compilation it ran itself with the
   pinned compiler, not from a file it is handed (review finding 3).
7. Tests in the backend: the six probe rows as fixtures (artifact in, R1CS hash out), and
   one artifact per refused opcode.
8. Memory operations (`MemoryInit`, `MemoryOp`): the rc form stores two witness indices
   and an operation flag serialized under the name `read`, where `false` is a read. The
   spike converts them in every mode and accepts them only in permissive mode. Supporting arrays means adding them to
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
| ACIR format byte other than the chosen one | **not refused today**: the rc.0 and rc.7 crates decode formats 2, 3 and 4, and the review showed a format-4 program passing the bridge. An earlier version of this row said the decoder rejects it "by construction", which was untested and wrong. Required: an explicit check of the format byte | no |
| Opcode outside the tested set | `upgrade_rc_program_json`, only when the rc decoder is the one that read the artifact (review finding 3) | observed during the spike (`wide` refused with "unsupported opcode BlackBoxFuncCall.XOR"); not archived, since every survey run used permissive mode |
| Brillig instruction outside a tested set | **not refused today** | no |
| More than one function, or return values | toolkit rejects ABI returns; the bridge accepts both | no |
| Public parameters not where the R1CS exposes them (the Week 8 failure) | existing layout gate | weakly: both square-root orders gave the expected R1CS, but each has one public input, and the survey bypasses the toolkit gate |
| R1CS differs from the one the key was made for | setup check (`snarkjs zkey verify`) and hash pin | yes: `r1cs_is_frozen_ceremony_r1cs` |
| Witness does not satisfy the R1CS | `snarkjs wtns check` before proving, and the backend's own check during materialization | yes, on every run. This does not catch a Brillig difference that yields another satisfying witness (review finding 2), and `probe.py` itself does not stop on a failed check (finding 6) |
| Poseidon library with the stale-cache bug used with more than 3 inputs | existing static test | not re-run |

## 7. Measured numbers

| Item | Value |
| --- | --- |
| Tally R1CS under beta.18, beta.26, rc.0, rc.7 | 3,338 constraints, 5 private and 4 public inputs, SHA-256 `5bd9cf5e…` in all four |
| Tally ACIR | 3,234 bytes as bincode, 2,892 bytes as MessagePack (recorded). 24 opcodes and 33 witnesses were observed and not archived |
| Counter R1CS under beta.18 and rc.7 | identical (`843ee202…`) |
| `wide` survey circuit | different program and different R1CS (recorded); 876 and 746 constraints observed, not archived |
| Noir unit tests of the tally | 21 passed on every compiler that compiled it |
| Spike patch | 2 files, 107 lines added, 1 changed |
| Build of Nargo rc.7 from source | 10 min 36 s on 2 cores (observed, not archived) |

## 8. Pinned tools for the work

Nargo: the chosen 1.0 release, by archive hash. Recorded on the spike date: beta.18 archive
`b7c39a6b…`, beta.26 `64048040…`, rc.0 `cb2e46e2…` (Linux x86_64). `noir-lang/poseidon`
v0.4.0. Backend: a new revision of the fork on top of `828025f`. Everything else as in
`toolchains/platforms.json`.

## 9. Test plan

1. Probe rows as CI jobs on both platforms with the pinned Rust (D4), driven by an
   expected-outcome matrix: the run exits non-zero when any row differs from its expected
   result, including the rows that are expected to fail. Proving is guarded by the witness
   check. Every row, count and raw program that a document cites is written to the result
   files.
2. Differential test per supported circuit: Noir execution, backend witness, R1CS
   satisfaction, snarkjs verification, CKB-VM verification (the existing
   `check-private-tally-circuit.py` pattern, run under the new compiler).
3. Inputs that must be refused before proving: an artifact with each refused opcode; one
   with each refused Brillig instruction; format bytes 2 and 4; a beta.19-encoded program
   carrying an rc `noir_version`; two functions; a return value; a truncated bytecode.
   Positive: the private-first scalar layout that Week 14 supports. Negative: swapped or
   leaked public values.
5. ABI and public inputs: compare the ABI and the raw and upgraded programs, and check an
   interleaved fixture with at least two unequal public values against Noir's own
   execution and the exported public vector.
6. Brillig differential tests: every admitted instruction and operand form executed by the
   beta.19 VM and by the rc VM on edge values, with equal results required.
7. Hints: for each unconstrained output of a supported circuit, a test that an alternative
   value fails the constraints.
4. Counter and tally CKB-VM matrices with artifacts from the new compiler (D5).

## 10. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| N1 | Spike repeated on the pinned toolchains, as an acceptance run | `spikes/noir-1x/run.sh` checks an expected-outcome matrix and exits non-zero on any deviation, on macOS and Linux; all cited evidence archived |
| N2 | Bridge cleaned (items 4 to 7) and merged into the fork, named as a decoder bridge for one release candidate | Backend tests pass; probe rows are fixtures; test plan items 3 and 5 pass |
| N3 | `noir-ckb` accepts two compiler pins and compiles with them itself | `noir-ckb build` on a circuit for the pinned rc succeeds; on any other version, and on a supplied artifact, it stops with the supported list |
| N4 | A copy of the tally circuit for the pinned rc with poseidon v0.4.0 | Its R1CS hash equals the ceremony's; the 49-case matrix passes |
| N5 | Arrays (item 8), only if an application needs them | Differential tests for `MemoryInit` and `MemoryOp` |
| N6 | **Noir 1.x support**, a milestone of its own and not implied by N1 to N4. Size option C; pin one compiler and its matching runtime (the final 1.0.0 if it exists, otherwise one named rc); admit only what is differentially tested | Test plan items 6 and 7 pass for the pinned pair; a circuit outside the tally's shape (integers, shifts, a hint) gives the same witness as Noir's own execution; the documentation names the pair and does not say "Noir 1.x" without it |

## 11. Risks and open questions

| Risk | Handling |
| --- | --- |
| The final 1.0.0 changes the encoding or the default format again | The decoder is tied to one tag; a new tag is a new pin and a repeat of N1 |
| A later compiler changes the tally's ACIR, so the ceremony key no longer matches | Refused by the R1CS hash check. The deployed profile keeps its own compiler pin |
| ACVM beta.19 mis-executes newer Brillig. Known differences exist (review finding 1) | The witness check guarantees only that the witness satisfies the R1CS. A different satisfying witness is not refused; it is not an unsound proof of the emitted R1CS either, and whether it matters depends on the circuit constraining its hints. Handling: Brillig allow-list in the bridge, differential tests, and N6 |
| The probe and `run.sh` are not acceptance tests | N1 |
| Developers expect arbitrary Noir, or read "1.x" as supported | The supported compiler and instruction set are printed by `noir-ckb check`; the first unsupported opcode is named in the error; the bridge is not called Noir 1.x support |
| Spike toolchain differed from the pins | N1 |

Open: whether to support beta.18 and 1.0 side by side for longer than the deployed
profiles need; whether option C should be proposed upstream to the backend's author
rather than carried in the fork.

## 12. External review

One review by an outside model, at commit `206df77`, against the backend at `828025f` and
the `acir`, `brillig` and `brillig_vm` sources of beta.19, rc.0 and rc.7. Seven findings
were shown by a test in a local harness that used the extracted upgrade function and the
real backend crates; the rc arithmetic and memory comparisons compiled rc.0 source modules
against beta.19 type interfaces and are not full rc-VM runs. All eight findings were
accepted.

| # | Severity | Finding | Response |
| --- | --- | --- | --- |
| 1 | High | Allowing the outer `BrilligCall` admits every Brillig instruction, and the beta.19 VM does not execute rc Brillig the same way: `Shl`/`Shr` by the full bit width return zero in rc and are an error in beta.19; relative addressing reads differ in a synthetic case; `MultiScalarMul` keeps its descriptor shape while the point and output layouts changed; several validation and error behaviours differ | Accepted. The patch is renamed for what it is, a decoder bridge for named release candidates, and "Noir 1.x support" becomes its own milestone with one pinned compiler/runtime pair and differential tests (sections 4 and 10). The bridge must validate the Brillig instruction and operand set, not only the outer opcode (section 5, item 4) |
| 2 | High | The witness check does not turn a Brillig mismatch into a refusal: a wrong hint value that still satisfies the R1CS passes. Shown with a hint constrained only by h·h − h = 0 | Accepted. The claim in sections 6 and 11 is replaced by what the check guarantees: the witness satisfies the emitted R1CS. Groth16 soundness for that R1CS is unaffected; whether the result is the intended one depends on the circuit constraining its unconstrained outputs. No such gap was shown in the tally or the counter |
| 3 | Medium | A beta.19-encoded program labelled with a supported rc `noir_version` is decoded by the native decoder before the rc allow-list runs, so the allow-list is bypassed; `noir_version` is an editable string, not provenance; programs with two functions or a return value pass the bridge | Accepted. Section 5, item 6 now requires the support policy after every decoder, a decoder and version-family consistency check, function and return limits at admission, and provenance from a compilation the tool itself runs with a pinned compiler |
| 4 | Medium | The rc.0 decoder accepts serialization format 4; the fail-closed table said it rejects it | Accepted; the table was wrong and had not been exercised. Corrected in section 6: formats outside the chosen one must be refused explicitly and tested |
| 5 | Medium | Equality of the upgraded programs does not show that named public inputs map to the same witnesses: the ABI is not compared, both sides are read under beta.19 semantics, and each square-root fixture has one public input. The test plan also required the private-first circuit to stop, which Week 14 supports | Accepted. Section 2 states what the comparison covers; the test plan compares ABI and raw programs and adds an interleaved fixture with two unequal public values; the private-first layout is now a positive test |
| 6 | Medium | `probe.py` proves after a failed witness check when the R1CS hash matches, and exits 0 when compilation fails; `run.sh` asserts nothing | Accepted. Not fixed in this session: the probe is evidence-gathering code and its recorded rows are unaffected, but it is not an acceptance test. Milestone N1 now requires an expected-outcome matrix that exits non-zero on any deviation, and a proving guard on the witness check |
| 7 | Medium | Several statements had no stored evidence: the patched beta.18 row; the "16 errors" row for the committed library on newer compilers; the constraint counts 876 and 746; the tally's opcode census, 33 witnesses and decoded-program equality; the strict refusal of `wide`; "proofs are identical"; the build time | Accepted. Each is now marked "observed during the spike, not archived" in this document and the spike README, or reworded. Proof identity was wrong as written (Groth16 proofs are randomized) and now reads "proofs verified". The supported rows are listed in the README |
| 8 | Note | The witness walk skips assertion payloads and `Call.inputs`, so it is not a scan of every witness | Accepted as a note. For the four allowed opcodes no operational witness is missed. Section 5 describes the value as an allocation bound over operational witnesses and requires a typed visitor before the opcode set grows |

Examined by the reviewer without a finding: expression, `FunctionInput`, public-input and
assertion-payload meaning across the versions; `RANGE` at the boundary bit sizes;
Poseidon2 constants and width; Brillig and `Call` predicates; the memory-operation
conversion (`read = false` is operation 0); and the Week 14 remapping for scalar layouts.
