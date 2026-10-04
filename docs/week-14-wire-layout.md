# Week 14 visibility-aware wire layout validation

Status: local scalar-fixture validation passed through fresh Groth16 proofs,
host adapter verification and the fresh Capsule CKB-VM matrix. The backend fix
is now published in the maintained fork; the normal CLI build/prove/test workflow
also passed locally against that revision. Broader compatibility and independent
clean-clone reproduction remain separate gates. No upstream PR is planned.
The pipeline remains Noir → ACIR → Groth16 → CKB. SP1 research is unchanged.

## Repositories and patch identity

- Backend base: `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`.
- Backend published branch: `fix/week14-public-wire-layout` in `wamimi/Noir-Groth16`.
- Published revision: `828025f3a0090e2934940956c0f5dc8093eb5532`.
- Toolkit inspected HEAD: `521e978449b31701d29e7e35c3a34d4f15bae43a`.
- CKB verifier: `d64c769ffe2d2edb5eb308dc59058efda77c2f83`, unchanged.
- Nargo beta.18 / noirc `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`.
- Backend ACIR/ACVM dependencies remain beta.19; no dependency pin changes.
- Host Rust 1.95.0, contract Rust 1.94.1, snarkjs 0.7.5.

## Data flow and migration

ACVM produces constant one followed by ACIR witnesses in index order. Those
values remain the input to instance-dependent lowering. R1CS allocation now
places constant one, public returns, public parameters, private parameters, and
remaining original witnesses in order, followed by lowering-created wires.
Each visibility group uses ascending ACIR witness indices. The carried
`acir_wire_map` controls both constraint references and witness conversion.
`known_wire_value` resolves its R1CS wire argument through that map;
`instance_witness_value` intentionally retains ACIR indexing.

Materialization converts once and solves intermediate wires. The full-assignment
checker does not remap or repair values. The CLI keeps its ACIR vector separate
from its materialized R1CS vector. Strict `interop` emits the paired R1CS/WTNS.
The standalone `witness` command emits `acir.wtns` for diagnostics instead of the
ambiguous `witness.wtns`; its map and binary remain ACIR-indexed. This filename
change is intentional. Old debug R1CS JSON must be regenerated because the
mapping field is required. Binary encodings are unchanged. Binary wire labels
remain wire identifiers, not a separate ACIR witness assignment.

Changed wire layouts require fresh circuit setup keys and proofs. Historical
proofs and fixtures must stay with their historical keys. No randomized proof
hash equality is expected.

## Tested subset and boundaries

| Case | Current evidence / boundary |
| --- | --- |
| Private-first and public-first scalar square | Fresh proofs accept public 49 and reject 7; host adapter checks pass |
| Interleaved scalar parameters | Real beta.18 artifact; public vector 49, 121; swapped vector rejected |
| Capsule scalar fields | Fresh seven-input proof and adapter checks pass; 14 CKB-VM tests pass |
| Zero public inputs | Real beta.18 artifact lowered and checked; Groth16/adapter/VM path not yet claimed |
| Public arrays and structs | Toolkit rejects explicitly; no application support claim |
| Noir return values | Toolkit rejects explicitly; compiler-to-return ordering not established |
| Disjoint ACIR returns | Synthetic mapping/serialization test only; no Noir frontend support claim |
| Input/return alias or overlapping visibility groups | Backend rejects explicitly |
| Out-of-range parameter witness | Backend rejects explicitly |
| Invalid square witness / altered public wire | Constraint checking rejects |
| Unsupported opcodes | Existing strict CLI rejection tests pass |

The scalar fixtures independently compare source-order ABI input values with
fixed expected public vectors and mapped wires. This supports the pinned tested
profile, not an assumption that ABI flattening, source order and witness order
are equivalent for every compiler or data type. There is no native Groth16
prover in the inspected backend Rust workspace; proof generation remains the
snarkjs interop path. Arkworks checks occur in the toolkit adapter.

## Historical pre-commit local validation command

The command below documents the original uncommitted-patch experiment. Its
base/branch guard is deliberately unchanged; it is not the current fork workflow.
For the published revision use [current generated-proof setup](current-generated-proof-workflow.md).

From the toolkit repository, use a fresh output directory:

```bash
python3 scripts/week14-layout-check.py --out target/week-14/local-check-01
```

This explicit local-development runner checks the backend base and branch,
snapshots the tracked diff and new files, runs focused regressions, rebuilds the
backend CLI offline, and checks paired R1CS/WTNS for five fixtures with cached
snarkjs 0.7.5. It records the patch, new-file and binary hashes. It does not change
the normal CLI's clean-revision guard, project configuration, or current-build
pointers. It performs no trusted setup, proving or VM execution.

Expected final markers: `week14_layout_checks=passed` and
`fresh_proof_and_vm_status=pending`. Any error is a stop condition. Do not reuse
an output directory or continue to setup after a mismatch. A missing offline
dependency is a prerequisite failure, not a successful test. The runner completed
successfully in `local-check-01` and, after lint cleanup, `local-check-02`.
Its pending-proof marker describes the runner's scope; later proof and VM results
are recorded separately in the evidence document.

## Subsequent gates (passed for the recorded fixtures)

1. Backend workspace tests, formatting and clippy required by its contributor guide.
2. Full toolkit/adapter regression tests.
3. Fresh development setup and proofs for both squares and the patched Capsule;
   verify each proof with its own key and intended public values; reject 7 for
   both square proofs. Include an interleaved proof and permutation rejection.
4. Adapter positive/negative checks against fresh artifacts.
5. Direct CKB verifier tests and Capsule transition matrix using the fresh
   Capsule via `NOIR_CKB_FIXTURE_DIR`, retaining the pinned verifier binary.

These gates passed in developer-run validation: backend 95 tests passed (3
ignored), toolkit 16 passed (14 VM tests initially ignored), four fresh proofs
and adapter checks passed, then all 14 Capsule VM tests passed separately.
Verifier-only cycles were 101577918; bound-transition cycles were 101627127.
See [Week 14 evidence](../evidence/week-14.md) for exact coverage and exclusions.

The original layout provenance is preserved, with subsequent artifact hashes in
`target/week-14/fresh-validation-manifest.json`. All generated material remains
under ignored `target/week-14/`. The normal CLI clean-revision guard remains
enabled; `noir-ckb.toml` now pins the published fork revision. Old manifests remain
historical and must not be edited to impersonate the new revision.

This is a semantic layout correction, not a backend security audit. The Capsule
is still a wiring fixture with arithmetic placeholder commitments. Development
setup, production security, testnet deployment, Battleship and a documentation
website are outside this change.
