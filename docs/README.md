# Documentation map

## Start here

- **[Try the counter](try-the-counter.md)**: run it locally, then create your own
  counter on CKB testnet.
## Advanced

- [Deploy your own copy of the contract](owned-counter-testnet.md): for
  operators who want a separate deployment instead of joining the existing one
  (about 114,000 testnet CKB).

## How the counter works

- [Counter specification](week-15-acceptance-spec.md): the exact rules the
  circuit and Type Script enforce, and why.
- [Counter test matrix](owned-counter-test-matrix.md): every adversarial case,
  what it attacks and the expected rejection.
- [Architecture](architecture.md) and [threat boundary](threat-boundary.md):
  what each component is responsible for, and what is out of scope.

## What's next

- [Private tally v2 design](private-tally-v2-spec.md): hidden value, proof as the
  authority, and the planned multi-party setup ceremony.

## Toolchain internals

- [Generated-proof workflow](current-generated-proof-workflow.md),
  [compatibility matrix](compatibility-matrix.md),
  [Week 14 wire layout fix](week-14-wire-layout.md),
  [Noir artifact inspection](artifact-inspection.md),
  [CKB verifier endpoint](ckb-endpoint.md).

## Decisions

- [SP1 evaluation](week-13-sp1-evaluation.md): why this stage continues with
  Noir to Groth16.

## Project history

- [Project history](project-history.md): Weeks 7–14 and the earlier Capsule example.
- Weekly design notes: [Week 8 backend](week-08-backend.md),
  [Week 9 adapter](week-09-adapter.md),
  [Week 10 proof-bound Capsule](week-10-proof-bound-capsule.md),
  [Week 10 reproduction](reproducing-week-10.md),
  [Week 11 developer preview](week-11-developer-preview.md),
  [Week 11–12 reviewer quickstart](reviewer-quickstart.md) (Capsule example).
- Results for every milestone are in [`evidence/`](../evidence/).
