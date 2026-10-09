# Week 15 delivery checklist

Status updated 9 October 2026. The counter is the approved reference application,
not a replacement for a promised Battleship implementation. The earlier binding
inventory, mutations, specification and architecture comparison remain separate
completed review deliverables.

## Implementation and execution

- [x] Versioned counter specification and approval.
- [x] Separate circuit/Type/client; original Capsule preserved.
- [x] Owner admission, VK pin, initialization, selected-operation binding and capacity rules.
- [x] Recorded fresh proofs/ranges, 48 VM cases and three detected mutations.
- [x] Recorded signed local-node initialization and update.
- [x] Same-machine fresh-directory reproduction (not independent review).
- [x] Operator-run public testnet deployment, creation and update confirmed.
- [x] Public confirmation receipts curated outside ignored target directories.

## Public reviewer handoff — completed locally

- [x] Reconcile against the original six phases and required deliverables; see
      [the full table](week-15-scope-reconciliation.md).
- [x] Check deployed source hashes and preserve historical evidence; run relevant
      RPC/reviewer tests rather than repeat unchanged setup/node execution.
- [x] Curate portable public deployment/build provenance, proof/VK and source
      file hashes; exclude wallet files. Original published baseline: `836f2a1fb8426a2f45ce788d4075331b8870854f`.
- [x] Add explicit dependency-cache bootstrap, including locked Cargo fetches and
      an isolated-empty-npm-cache check. Full fresh-machine installation is untested.
- [x] Supply reusable operator batches without personal paths or funding OutPoints,
      covering account setup, consolidation, fees/capacity, signing and confirmation.
- [x] Prepare a user-recorded demo guide and unpublished feedback invitation.

## Publication status and remaining delivery

- [x] Five implementation/test/docs/SP1 commits confirmed on GitHub main at `836f2a1`.
- [x] Original source, reviewer instructions and public evidence are published.
- [x] Guided onboarding follow-up published at `4ae8a71`; remote source, reviewer
      page and evidence checked against local files.
- [ ] Record and upload the approximately five-minute demonstration; add its real URL.
- [ ] Publish the combined counter result/backend decision forum update.
- [ ] Share the same post and reviewer link with the review group and Neon; invite
      suggested reviewers without implying endorsement.
- [ ] Submit the Week 15 report, distinguishing completed/published/pending/proposed.

The recording and forum files are preparation material until those actions occur.
Independent reproduction and demand feedback do not block submission of an honest report.

Existing CI runs Capsule, not the full counter lifecycle. This limitation is stated
in the guides; adding hosted counter CI is useful future work, not a retroactive
Week15 gate. Standalone packaging and other platforms are likewise not required.
The retained run occupies about 1.5 GiB, not a measured peak/minimum requirement.
No reliable setup-duration benchmark was retained; measuring one is useful, not
an acceptance requirement. Do not invent duration/resource claims.

## After inviting reviewers

- [ ] Record external reproduction attempts separately from maintainer runs.
- [ ] Collect concrete dApp use cases and the missing features preventing integration.
- [ ] Use that evidence to bound the proposal, not to claim adoption prematurely.

## Deliberately outside Week 15

Configurable external-circuit bindings, broader tested Noir compatibility, a
standalone distribution, and expanded client support are candidate proposal work.
Battleship, its UI and game protocol belong to a separate later scope. Production
security, a production setup ceremony and arbitrary Noir compatibility are not
established by this preview.
