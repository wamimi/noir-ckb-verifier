# Week 15 — public counter lifecycle

Status of the original local-validation run: **implemented and locally validated;
testnet not executed in that run**. The subsequent operator-run testnet lifecycle
was confirmed on 7 October 2026; see the separate
[testnet evidence](week-15-testnet.md). Statements below about pending testnet
work describe the earlier local-run snapshot, not the latest project status.
The implementation uses a separate application profile with inexpensive owner
admission before pairing.
Base toolkit revision is `b155300c8145916a485696bf461e36f055bb5135`; implementation
is uncommitted workspace changes, not a claimed release revision. No staging,
commit, push, publication, PR or public-network transaction was performed.

The [application specification](../docs/week-15-acceptance-spec.md),
[quickstart](../docs/owned-counter-quickstart.md), and
[requirement matrix](../docs/owned-counter-test-matrix.md) describe the fixed
`noir-ckb/owned-counter/v1` profile. It is a **public proof-enforcement example**,
not a privacy application or general generator. Application capacity has **no
withdrawal/destruction path**. All setup material is explicitly development-only,
single-party with public contribution entropy, not a production ceremony.

## Reproduced results

- Fresh new circuit: four ordered public Fields; 2,339 constraints, 2,325 variables.
  Fresh ptau power 13, fresh circuit-specific zkey/VK, witness checks, setup/key
  verification, proof generation, snarkjs verification and adapter round-trip pass.
  Altering each public coordinate rejects the original proof.
- Maximum-range fresh proof passes; five out-of-range/non-increment inputs reject
  during ACVM constraint solving. These are not fresh invalid-proof tests.
- 48 VM cases pass inside one Rust integration-test function. They include real
  secp owner signatures, initialization, public/context binding, wrong VK/proof,
  capacity/ownership, ambiguous groups, witness errors and resource limits.
- Three actual isolated RISC-V mutations detected by targeted **incorrect
  acceptance**; each retains a passing valid control. No primitive mutation.
- Actual local-node deployment, signed zero-state creation and signed proof-bound
  update are committed, with inputs consumed and exact successor Cells checked.
- Same-machine fresh-directory reproduction repeats fresh setup/build/proofs,
  all 48 cases, all three mutations and the committed local lifecycle. It copies
  source including uncommitted changes, excludes previous ignored artifacts,
  reuses installed pinned tool executables, Cargo/npm caches and the clean pinned
  backend source checkout. It is not an independent clean-clone review.
- Host workspace: 17 tests pass; VM tests remain explicitly ignored in that host
  command and are executed separately by the matrix runner. Formatting, Clippy
  with warnings denied, and Python syntax checks pass.

Public provenance is retained in [week-15-manifest.json](week-15-manifest.json)
and its curated `week-15/` files. Full generated setup/proof/binary directories
remain ignored under `target/week-15/`. Disposable key/wallet files are excluded
from public evidence. Exact commands, cwd, build environment overrides, outputs
and statuses are retained. Source hashes identify the uncommitted implementation.

## Exact fresh-directory run

Runner: `scripts/local-owned-counter.py`, copied into
`target/week-15/reproduction-source-01/`, output `target/local-run` beneath that
copy. Invoked with the pinned native CKB/ckb-cli paths, backend
`/Users/xiaomao/Noir-Groth16`, ports 18124/18125 and `--mutations`.
[Full commands](week-15/local-commands.json), [source copy](week-15/source-copy.json),
[build flags](week-15/build.json), [setup logs](week-15/setup-commands.json).

Pins: backend `828025f3a0090e2934940956c0f5dc8093eb5532`; verifier libraries
`d64c769ffe2d2edb5eb308dc59058efda77c2f83`; Nargo beta.18 / compiler
`99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`; snarkjs 0.7.5; host Rust 1.95.0;
contract Rust 1.94.1. Existing contract package versions were retained while
adding the directly linked verifier dependency graph. Upstream attribution and
licenses are unchanged.

Node CKB 0.210.0 (`2592ddf0502cd4adfe886db893cccc866db3c60f`), CLI 2.0.0
(`80efc21c30e9fc7847407a217034681b6e46c763`), official Darwin ARM64 artifacts.
Their archive/executable pins are in `scripts/fetch-counter-tools.py`; both
executables were hash-checked and used. Node binds loopback, no outbound peers.
Generated accounts are development-only and never used publicly. Both local
nodes were stopped after validation; their ignored data directories remain.

Fresh-directory artifact identities:

| Artifact | Bytes | SHA-256 | CKB data hash |
| --- | ---: | --- | --- |
| Type ELF | 113320 | `07494c88be73b006d929509702a6c52db2f8a2f96f8135953efdbaa2876c1677` | `d834acc9f0eded5d5c4391ce50586b7fddddb600c6d85f358669f7dde5bbe737` |
| VK Molecule | 430 | `6ca575a28d52d017e81bf1d60c27d11036d6fb0baefe1fca4041519c1df643e1` | `685bc8cd974970ba3a030025f683c7fd6fce0715c2e9f286660634a8b35058fe` |

The valid signed-update VM case uses **111,247,154 cycles** for this exact
fresh-directory binary/proof/transaction. Budget 300,000,000 is a harness setting,
not a consensus limit. This is not a local-node RPC cycle measurement or a fair
performance delta against the earlier seven-input verifier/Spawn arrangements.
No comparable spawned counter was built; direct verification suffices here.

Local receipts (not public explorer transactions):

| Item | Value |
| --- | --- |
| Genesis | `72cfc87b8d9a9b4bb2907023ce4d6ace82350f97035187f176b659f802cec01c` |
| Dependency deployment | `6259615afe552c1e58c137c3ddf5e3a3e744974d263dec708f28e4b45b705216` |
| Initialization | `c604e20c64d731ef9945d0e6d023d7287d031eb2f2c770eb347f53bb6945d67d` |
| Update | `89e52d3df87ce898fc542000bc81c14142be990abff517019e747f7883e90494` |

Dependency outputs 0/1 are Type code/VK. Initialization output 0 is count 0;
update consumes that OutPoint and creates output 0 count 1, the same full owner
Lock and 20,000,000,000 shannons (200 CKB). Receipts check exact raw transaction,
committed status, input consumption and live output data/Type/Lock/capacity.
[Checked state records](week-15/checked-state.json) preserve the actual expected
outputs used by the successful confirmation checks. [First local observations](week-15/first-local-observations.json)
also retain direct RPC-observed committed output data and post-update live/spent
status from the first independently initialized development chain.

## Failures and subsequent checks

The first setup attempt used power 10, too small for 2,339 constraints. snarkjs
`groth16 setup` returned exit zero with ERROR text; the subsequent zkey command
failed. This is retained as a failed attempt, not setup success. The runner now
sizes power from R1CS constraints and treats snarkjs ERROR output as failure.
Setup-02 and the fresh-directory setup pass. A test-generator syntax error and
relative fixture-path invocation were corrected before running cases. The
missing-signature expected code was corrected from -1 to the observed standard
Lock -2; the actual rejection was never counted as acceptance.

After the fresh-directory run, client-only finishing changes preserve optional
witness fields when attaching proof, add release `inspect`, tighten constraint-
failure matching and check dependency hashes during deployment confirmation.
The new witness behavior and stale-operation check were exercised against an
actual live input on the first dev node without another broadcast; logs are
retained. All recorded range failures explicitly contain `Cannot satisfy constraint`.
The circuit/contract sources match the fresh-directory release source hashes.
The earlier whole-workflow run and these later targeted checks are distinct.

[Preservation hashes](week-15/preservation.json) verify 36 historical and pre-existing files
unchanged, including Capsule source/fixtures, earlier evidence and pre-existing
untracked planning documents. No old public slot, key or artifact was repurposed.
The previous Phase 1 file intentionally retains its historical pre-implementation
status; the later application specification and this implementation evidence supersede
that status without rewriting historical measurements.

## Delivery status at the local-validation snapshot

**Implemented and tested:** circuit, Type, selected-operation context, owner/VK
admission, fresh development setup, unsigned transaction/proof/check/confirmation
client, existing CLI `counter` entry point, local signing/node workflow, VM/range/
mutation tests, integrity manifests, quickstart and issue template.

**Implemented but not publicly executed:** operator-assisted testnet preparation,
signing-tool integration and confirmation path. Testnet policy/artifact build,
wallet/address/funding preflight, approved broadcasts and receipts are pending.
No transaction is submitted or confirmed on testnet. Begin with the small read-only
[operator preflight batch](../docs/owned-counter-testnet.md); wait for actual output.

**Proposed only:** configurable external-circuit bindings and future application
profiles, including Battleship. No game or general compiler is implemented.

**Explicitly unsupported:** arbitrary Noir programs, production privacy/security,
audited readiness, whole-transaction replay protection, other owner Lock families,
transfer, withdrawal/destruction, recovery, upgrades/migration and batching.
