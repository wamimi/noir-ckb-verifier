# noir-ckb: a testnet counter demo and a request for developer feedback

Status: prepared for publication. Add the actual video URL after recording; do not
claim this draft has been posted. Source baseline `836f2a1` and the tested guided
onboarding follow-up `4ae8a71` are published.

## What now works

A Noir-defined counter update has been proved off-chain and enforced by a CKB
Type Script on testnet, alongside owner authorization. Here is how to inspect
and reproduce it.

The public counter was created at zero and updated to one, preserving the owner
and 200 CKB application capacity. The Noir circuit defines the bounded increment;
the Type derives the statement from the actual Cell operation and verifies the
proof; the conventional owner Lock requires a signature. A proof alone does not
authorize an arbitrary Cell transition.

Recorded local validation includes fresh proofs, 48 VM cases, three detected
mutations and a committed local-node lifecycle. The testnet deployment, creation
and update are confirmed in the linked evidence.

## Inspect or reproduce

Start with the [reviewer page](https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/owned-counter-review.md)
and [testnet evidence](https://github.com/wamimi/noir-ckb-verifier/blob/main/evidence/week-15-testnet.md).
Tested guided preview revision: `4ae8a710f9ba71be21f8a19cef12dbdf87571f41`.
From that source checkout, run `python3 -B scripts/start-counter.py`.
You can inspect recorded artifacts, perform live read-only checks, or reproduce the
complete application locally. Neither initial review nor local reproduction needs
your own wallet or faucet funds. Testnet deployment is optional.

Video: pending recording and upload. Replace this sentence with its real link
before publishing the combined demo announcement.

## Why continue with Groth16 for this stage?

I evaluated the available SP1 verifier on CKB-VM and reproduced successful
verification and rejection cases. However, verifying an SP1 proof on CKB does not
itself provide a Noir-to-SP1 pipeline. For this stage, I am continuing with the
existing Noir-to-Groth16 path, including the visibility-ordering correction in my
maintained backend fork. This keeps the work focused on the Noir developer workflow.
The per-circuit trusted setup remains a real limitation; this decision does not
remove it or establish that Groth16 is universally the better choice.

The evaluated SP1 PLONK wrapper uses a universal trusted setup. This work did not
establish a Noir-to-SP1 bridge; it does not claim that no bridge exists elsewhere.
See the [SP1 evaluation](https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/week-13-sp1-evaluation.md).

## Current limitations

- One fixed public counter, not private state or arbitrary-circuit generation.
- Development-only setup with public entropy; no production ceremony or audit.
- macOS ARM64 is the reproduced local environment. Source checkout required;
  no standalone distribution or validated cross-platform installer.
- No withdrawal/destruction from the application Cell; its capacity remains locked.
- Same-machine reproduction is recorded. Fresh-machine and independent developer
  reproduction are pending. Existing hosted CI covers Capsule, not the full counter.

## Proposed next step and developer questions

The proposed next stage is external-circuit support within a documented supported
subset and a bounded configurable application template. Those are proposal items,
not current capabilities. Feedback should determine their realistic scope.

For reviewers: could you follow the instructions without help? Where did installation
or execution fail? Were proof, owner-authorization and Cell-binding responsibilities clear?

For potential users: what would you want to prove in a CKB application? Do you already
have a Noir circuit or concrete application? Which public values must match your Cells?
Would you try an early supported-circuit workflow with us, and what would prevent adoption?

Please reply here or use the [Owned counter v1 preview review issue template](https://github.com/wamimi/noir-ckb-verifier/issues/new?template=owned-counter-review.md).
Include your source revision, platform and sanitized errors. Never share wallet material.
A successful reproduction validates usability; a concrete use case and willingness
to test provides stronger demand evidence than general interest. Demand is not yet validated.
