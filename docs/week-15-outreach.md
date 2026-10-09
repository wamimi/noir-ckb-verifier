# Week 15 distribution text

Prepared, not sent. Use the same actual forum URL and reviewer link in each message.
Recipient/channel details and report-submission destination remain to be supplied.
Send the combined announcement after the demo URL is available. No invitation
implies that its recipient has reviewed or endorsed the design.

## Review group

I've published a noir-ckb counter preview: a Noir-defined update proved off-chain
and enforced by a CKB Type Script on testnet, alongside owner authorization.
The forum update explains the result and why this stage continues with Groth16.

Forum: add the actual published post URL.
Review: https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/owned-counter-review.md

You can inspect the existing result without a wallet or reproduce it locally.
Could you follow the steps without help, and were proof verification, owner
signatures and Cell binding clear? If this fits an application you have in mind,
what would you prove, which public values must match your Cells, and would you
test an early supported-circuit workflow with us?

## Neon

Week 15 now has a tested public counter lifecycle, including confirmed testnet
creation and update. The preview includes evidence inspection and local reproduction;
the backend decision keeps the current Noir-to-Groth16 path while acknowledging
per-circuit trusted setup. Independent reproduction and developer demand are pending.

Forum: add the actual published post URL.
Review: https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/owned-counter-review.md
Report: docs/week-15-report.md (submit through the agreed reporting channel).

The proposed funding scope is supported external circuits and a bounded configurable
application template, to be refined from concrete use cases in Week 16.

## Individual reviewer invitation

I'd appreciate your review of the noir-ckb public counter preview if you have time.
It includes recorded testnet evidence and a disposable local reproduction path.
I'm particularly interested in installation friction and whether the separation
between proof verification, owner authorization and Cell binding is clear.

Forum: add the actual published post URL.
Review: https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/owned-counter-review.md

If you have a concrete application or Noir circuit, I'd also like to understand
its public-to-Cell mapping and whether you would test a supported integration.
