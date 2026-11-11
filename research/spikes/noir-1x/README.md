# Spike: does the pinned backend accept Noir 1.0 ACIR?

Research question for [R1](../../noir-1x.md): "the backend only needs small changes for
Noir 1.x". True or false, and what exactly changes?

## What it is

- `probe.py`: compiles a **copy** of `circuits/private-tally-v2` with a given Nargo, then
  runs backend `interop`, snarkjs witness check, R1CS identity against the frozen ceremony
  R1CS, and a proof with the ceremony key. One JSON object per run.
- `survey.py`: compiles five circuits with two Nargo versions and compares the decoded
  ACIR program and the R1CS.
- `backend-noir-1x.patch`: the spike change to `wamimi/Noir-Groth16@828025f`
  (`crates/noir-acir`, 107 added lines, 1 changed). It is a probe, not a proposed commit:
  it contains debugging switches (`NOIR_CKB_DUMP_*`, `NOIR_CKB_SPIKE_PERMISSIVE`).
- `wide/`: a survey circuit with integer division, bit operations and array access.
- `results/`: the JSON written by the runs below.

## Command

```bash
NARGO_OLD=... NARGO_NEW=... BACKEND=/path/to/Noir-Groth16 SNARKJS=/path/to/snarkjs \
  research/spikes/noir-1x/run.sh
```

## Result (10 November 2026, Linux x86_64)

Tools: Nargo 1.0.0-beta.18, 1.0.0-beta.26 and 1.0.0-rc.0 from the official release
archives; Nargo 1.0.0-rc.7 built from tag `v1.0.0-rc.7` (`045e2ea`) because that tag had no
release archive; backend at `828025f`; snarkjs 0.7.5. The backend and Nargo rc.7 were built
with Rust 1.97.0, not the pinned 1.95.0 and 1.89.0 (the pinned toolchains could not be
downloaded on the machine used). No final `v1.0.0` tag existed on this date.

Calibration: Nargo beta.18 with the pinned backend reproduced the frozen ceremony R1CS
(`5bd9cf5e…`) byte for byte, and proofs made with `tally_final.zkey` verified.

| Nargo | Poseidon library | Backend | Compile | Backend | R1CS equals frozen ceremony R1CS | Proof with ceremony key |
| --- | --- | --- | --- | --- | --- | --- |
| beta.18 | v0.2.6 (committed) | pinned | ok, 21 tests | ok | yes | verified |
| beta.18 | v0.3.0 | pinned | **fails** (`@` syntax) | | | |
| beta.26, rc.0, rc.7 | v0.2.6 (committed) | pinned | **fails** (16 errors, slice literal) | | | |
| beta.26 | v0.3.0 | pinned | ok, 21 tests | **fails to parse the artifact** | | |
| rc.0 | v0.3.0, v0.4.0 | pinned | ok, 21 tests | **fails to parse** | | |
| rc.7 | v0.3.0, v0.4.0 | pinned | ok, 21 tests | **fails to parse** | | |
| beta.26 | v0.3.0 | patched | ok | ok | **yes** | **verified** |
| rc.0 | v0.4.0 | patched | ok | ok | **yes** | **verified** |
| rc.7 | v0.4.0 | patched | ok | ok | **yes** | **verified** |
| beta.18 | v0.2.6 | patched | ok | ok | yes | verified |

Commitments printed by the helper package were identical for all compilers and library
versions (same three test vectors). The decoded ACIR program of the tally, including the
Brillig bytecode, was identical between beta.18 and rc.0/rc.7: 24 opcodes (12 `AssertZero`,
6 `RANGE`, 4 `Poseidon2Permutation`, 2 `BrilligCall`), 33 witnesses.

Survey, beta.18 against rc.7 through the patched backend (rc.0 gave the same):

| Circuit | Same ACIR program | Same R1CS | Note |
| --- | --- | --- | --- |
| `owned-counter-v1` | yes | yes (`843ee202…`) | |
| `proof-bound-capsule` | yes | yes | |
| `square-root-public-first`, `square-root` | yes | yes | |
| `wide` (division, XOR/AND, array read and write) | **no** | **no**: 876 constraints under beta.18, 746 under rc.7 | Both witnesses satisfied their R1CS. Needed the memory-operation conversion, which only the permissive switch enables |

## What did not work

- Raising the backend's own `acir`/`acvm` dependency from beta.19 to rc.7 stopped at the
  first crate (`noir-acir`: `current_witness_index` no longer exists). The other three
  crates were not reached, so the size of that route is unknown.
- rc.1 to rc.7 had no downloadable Nargo archive at the usual release URL (HTTP 404).
- The witness solver is still ACVM beta.19 executing Brillig emitted by rc.7. It produced
  satisfying witnesses for the six circuits tried; that is not evidence for others.
- Proving was not repeated in CKB-VM; the R1CS and proofs are identical to ones already
  verified there, so nothing new would be exercised.
