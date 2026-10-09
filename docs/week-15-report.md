# Week 15 — counter developer preview

Report prepared 9 October 2026. Submission and distribution are pending.

A Noir-defined counter update has been proved off-chain and enforced by a CKB
Type Script on testnet, alongside owner authorization. The counter changed from
zero to one while preserving ownership and 200 CKB application capacity.

## Completed

- Fixed public Noir counter circuit, application Type and conventional owner Lock composition.
- Recorded fresh proof generation, public-input rejection checks, 48 VM cases and
  three isolated detected mutations. These are local adversarial results.
- Recorded local-node lifecycle and fresh-directory reproduction on the maintainer's
  existing macOS ARM64 environment with installed tools and caches. The new guided
  entry point also completed a fresh full local lifecycle on 9 October, including
  48 VM cases and three mutations; 19 Python and six CLI tests passed.
- Confirmed testnet dependency deployment, zero-state creation and proof-authorized
  update, with transaction contents and Cells checked. No new deployment is needed.

Evidence: [local validation](../evidence/week-15.md),
[testnet lifecycle](../evidence/week-15-testnet.md),
[handoff checks](../evidence/week-15-handoff.md),
[guided-run validation](../evidence/week-15-guided.md).

## Published

The five source/test/documentation/SP1 commits are on GitHub through
`836f2a1fb8426a2f45ce788d4075331b8870854f`.
The [original reviewer instructions](https://github.com/wamimi/noir-ckb-verifier/blob/836f2a1/docs/owned-counter-review.md)
and public proof, statement and transaction evidence are available.

The guided onboarding follow-up is published at
`4ae8a710f9ba71be21f8a19cef12dbdf87571f41`, including the
[reviewer starting page](https://github.com/wamimi/noir-ckb-verifier/blob/4ae8a71/docs/owned-counter-review.md),
launcher and new validation evidence. Remote source, reviewer page and evidence
were fetched and matched to the local files after the push.
The video and forum announcement are pending publication; no placeholder is
counted as a delivered demo.

## Backend decision

The available SP1 verifier passed the reproduced positive and rejection cases on
CKB-VM. That verifier result does not itself establish a Noir-to-SP1 pipeline.
This stage continues with the existing Noir-to-Groth16 workflow and its maintained
backend visibility-ordering correction. Circuit-specific trusted setup remains a
limitation. This is not a claim that SP1 is unsuitable or Groth16 is universally better.

## Pending

- Record/upload the demo, publish/share the forum
  update with the review group and Neon, and submit this report.
- Independent reproduction, including installation and execution feedback.
- Concrete developer use cases, required public-to-Cell mappings, adoption blockers
  and willingness to test a supported integration. Demand is not yet validated.

Usability evidence and product-demand evidence will be tracked separately. Replies
are not required before submission, and invitations do not imply reviewer endorsement.

## Proposed for funding

External-circuit support within an explicit supported subset and a bounded
configurable application template. Week 16 should scope these using concrete
use cases and testing commitments, rather than treat them as implemented capabilities.

## Limitations

Fixed public counter; development-only public-entropy setup; macOS ARM64 is the
reproduced host; source checkout required; no arbitrary-circuit generation, audit,
production readiness or application Cell withdrawal/destruction. Hosted CI currently
covers the historical Capsule path rather than the full counter lifecycle.
