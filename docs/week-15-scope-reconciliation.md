# Week 15 reconciliation against the original six phases

Historical assessment from 7 October 2026. Publication-pending statements below
describe that handoff, not current GitHub status. The five commits were subsequently
published through `836f2a1`; see the [current checklist](week-15-delivery-checklist.md)
and [report](week-15-report.md) for the 9 October follow-up.

Assessed 7 October 2026 from the approved prompt, source and retained evidence,
not from the draft checklist alone. The approved application is one **public
owner-controlled counter**, not privacy, a general application compiler or Battleship.
Current source is an uncommitted working tree on `b155300c8145916a485696bf461e36f055bb5135`.
No commit, push, publication, signing or broadcast occurred in this handoff pass.

## Where the earlier handoff stopped

The core implementation, fresh setup/proofs, adversarial tests, mutations, signed
local-node lifecycle and same-machine fresh-directory reproduction were completed
before handing off public testnet execution. The **entire six-phase delivery was
not finished**. The earlier handoff stopped after the RPC User-Agent/error-handling
fix, focused tests, read-only preflight and the next testnet build instructions.
Public testnet signing/broadcast/confirmation was pending operator execution;
reviewer bootstrap, portable provenance and reusable operator documentation were
not yet finished. This was a deferred handoff, not evidence of a failed or missing
contract lifecycle. The operator subsequently completed the three public transactions.

## Phase-by-phase reconciliation

“Complete” below means within the approved bounded scope, not audited or exhaustively
tested. Recorded local results and freshly executed handoff checks are distinguished.

| Original requirement | Actual implementation/document | Evidence/test | Status | Exact remaining action |
| --- | --- | --- | --- | --- |
| 1: acceptance rules and architecture approval before implementation | [Approved specification](week-15-acceptance-spec.md); [phase1 feasibility](../evidence/week-15-phase1.md) | User approved public counter, Type ID, direct verifier, compiled VK; cheap owner admission before pairing | Complete | None; material protocol changes need new approval |
| 1: feasibility, size, cycles, integration complexity | Direct `verifier_core` link in `contracts/crates/owned-counter`; spec comparison | Phase1 feasibility; exact new ELF 113,320 bytes, local signed VM case 111,247,154 cycles in [execution evidence](../evidence/week-15.md) | Complete | No equivalent Spawn counter benchmark exists; do not claim direct/Spawn performance superiority |
| 2: separate narrow lifecycle; initialization, owner update, preservation, no destruction/ambiguity | `circuits/owned-counter-v1/src/main.nr`; `contracts/crates/owned-counter/src/main.rs`; `scripts/owned_counter.py`; CLI `counter` | [48-case matrix](owned-counter-test-matrix.md), creation and update node receipts | Complete | None; Capsule remains historical and unchanged |
| 3: new profile and exact operation binding; fresh setup; script versus cryptographic rejection | Four ordered Fields and full digest as two LE128 limbs; specification; `setup-owned-counter.py` | Fresh 2,339-constraint setup; changed coordinates reject; different-OutPoint old-vector rejects49, recomputed-vector old-proof rejects51, fresh proof accepts | Complete | None; fees/change and selected other fields intentionally excluded |
| 4: adversarial requirement matrix and isolated actual-binary mutations | `crates/ckb-integration-tests/tests/owned_counter.rs`; `check-owned-counter.py`; `mutate-owned-counter.py`; matrix | 48 cases within one Rust test; 3 mutant incorrect acceptances with valid controls; six range cases; actual owner signatures | Complete | No exhaustive fuzzing/audit claimed; invalid cases remain local |
| 5: actual local-node lifecycle before demonstrated claim | `local-owned-counter.py`; pinned `fetch-counter-tools.py` | [Local run](../evidence/week-15/local-run.json), checked state and local receipts | Complete | No rerun needed for prose/read-only reviewer additions |
| 5: operator-assisted public deployment, legitimate creation/update, confirmation | Client prepare/prove/check/confirm; [operator batches](owned-counter-testnet.md) | [Testnet evidence](../evidence/week-15-testnet.md), 3 operator receipts; new independent read-only RPC check | Complete | No pending transaction/funding step. Additional transactions require approval |
| 6: quickstart, versions, build/setup/prove/test/init/deployment, failures, integrity, limits, review template | [Reviewer entry](owned-counter-review.md), [bootstrap](owned-counter-bootstrap.md), [quickstart](owned-counter-quickstart.md), operator guide, issue template | Recorded complete local reproduction; help/argument and snippet checks; locked cache fetches; 12 focused Python tests; retained testnet proof verified | Complete for source handoff | Publication must identify a real source revision; no full fresh-machine installation claimed |
| 6: fresh-directory attempt avoiding old ignored artifacts | Source-copy/local runner in retained reproduction | [Source copy](../evidence/week-15/source-copy.json), repeated fresh setup/proofs/mutations/local node | Complete | Installed tools, clean backend and warm caches reused; independent reproduction pending reviewers, not an original completion gate |

## Every required deliverable

| Original deliverable | Actual path | Evidence/test | Status | Exact remaining action |
| --- | --- | --- | --- | --- |
| Approved application specification | [week-15-acceptance-spec.md](week-15-acceptance-spec.md) | Implemented admission order matches user adjustment | Complete | None |
| New versioned contract/circuit/client | Paths above; `crates/noir-ckb-cli/src/main.rs` | Fresh setup, signatures, VM and real-node results | Complete | Publish source only with approval |
| Requirement-to-test matrix | [owned-counter-test-matrix.md](owned-counter-test-matrix.md) | Named cases, codes, mutation targets and exclusions | Complete | None |
| Actual validation evidence/provenance | [Original local evidence](../evidence/week-15.md), [public deployment](../evidence/week-15-public/deployment.json), [handoff checks](../evidence/week-15-handoff.md), [source snapshot](../evidence/week-15-public/source-state.json) | Original release hash, deployed source hashes, artifacts, receipt hashes and current file hashes | Complete as working-tree provenance | After approved commit, record real revision and verify snapshot; do not pretend base commit contains Week15 |
| Local-node initialization/update or exact blocker | [local-run.json](../evidence/week-15/local-run.json) | Committed deployment, zero creation, 0→1 update, exact Cells | Complete | No local execution blocker |
| Testnet workflow and approved receipts | [Operator guide](owned-counter-testnet.md), [testnet evidence](../evidence/week-15-testnet.md) | Operator confirmation plus independent read-only content/state/artifact check | Complete | Account/consolidation guide help-checked; not a second newly executed wallet lifecycle |
| Public-review quickstart | [Reviewer entry](owned-counter-review.md) → bootstrap → local quickstart | Implemented commands and recorded local run; targeted bootstrap validation | Complete locally; publication pending | Approve/publish actual source revision, replace announcement revision placeholder and check remote links |
| Completion summary distinguishing status | This document and [delivery checklist](week-15-delivery-checklist.md) | Links to executed versus proposed work | Complete | Do not convert publication pending into a deployment-success claim |

## Answers and publication gates

1. **Original implementation finished before handoff?** Core implementation and local
   acceptance testing: yes. Entire six-phase reviewer delivery: no; packaging/docs and
   operator testnet execution remained.
2. **Interrupted/deferred?** Public execution waited for the operator; it is now confirmed.
   Bootstrap, usable operator batches and portable provenance were deferred and are now
   supplied. A fresh-machine install and external review were never completed.
3. **What remains in Phase6?** User-approved source publication, an actual revision in
   announcement/checkout instructions, and remote link verification after publication.
   Local documentation/tooling handoff is complete. Full fresh-machine and independent
   reproduction remain explicitly unverified, not retroactive acceptance requirements.
4. **Essential before publishing this source preview?** Review the combined diff, approve
   a commit/publication, ensure intended counter files/public evidence are included and
   wallet/private/unrelated files are excluded, check the snapshot and publish a real
   source revision. Link the reviewer guide and limitations. No new chain transaction
   is necessary. This assistant has not staged, committed or published anything.
5. **Useful but not original requirements?** Standalone packaging, cross-platform
   installers, hosted counter CI, resource/timing benchmarks beyond recorded evidence,
   automated multi-Cell coin selection, and external-circuit configuration. Current
   CI is Capsule, Rust CLI requires source/Python, supported tested host is macOS ARM64,
   one funding Cell is required. These limitations are now explicit.

## Completion categories

- **Implemented and tested:** fixed circuit/Type/client, fresh development setup,
  public binding, real owner signatures, lifecycle and mutation matrix, local node,
  same-machine reproduction, operator testnet lifecycle, RPC compatibility/error
  tests, read-only reviewer checker and portable public proof verification.
- **Implemented but not fully executed in this pass:** expanded installation/operator
  instructions are syntax/help checked; no new wallet/account/consolidation or
  fresh-machine install was performed. Recording guide/forum text are drafts only.
- **Proposed:** bring-your-own-supported-circuit workflow and configurable binding
  infrastructure. One working application is the preview; broader developer
  integration belongs in the subsequent proposal. Demand has not yet been validated.
- **Explicitly unsupported:** arbitrary Noir, production privacy/security/ceremony,
  audit claims, withdrawal/destruction, transfer/recovery/upgrades, batching, other
  owner Locks, full-transaction binding, Battleship and its UI.

## Rerun policy

Documentation-only changes need links/snippet/claim checks. Read-only reviewer or
RPC changes need focused unit tests and read-only integration checks. Builder,
proof attachment, wallet integration or client binding changes require their
corresponding local transaction/proof checks. Contract, circuit, setup or profile
changes need new approval and fresh setup as applicable, full VM/range/mutation and
local-node lifecycle validation; they create a different release identity. Do not
repeat expensive unchanged setup/node runs merely to make documentation look fresh.
