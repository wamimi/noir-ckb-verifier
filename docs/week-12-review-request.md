# Week 12 external review request draft

This file contains copy-ready drafts for the CKBuilder project tracker and the
CKBuilders Telegram review channel. The requests may be published after the
local Week 12 gates pass; add independent clean-clone results when reviewers
return them.

## CKBuilder project-review issue

### Suggested title

`noir-ckb: proof-bound Noir/Groth16 verification for typed CKB Cell transitions`

### Project Summary

`noir-ckb` is an experimental developer toolchain for taking a supported Noir
circuit through BN254 Groth16 artifact generation, strict cross-library
conversion, CKB-VM verification, and application-specific binding to a typed
Cell transition. The current preview demonstrates why proof verification alone
is insufficient: a proof is accepted only when its ordered public statement
matches the exact Capsule Cell transition represented by the transaction.

### Tools used

- Noir/Nargo and ACIR
- Noir-Groth16 and snarkjs
- Rust and arkworks
- `groth16-ckb`
- Molecule
- `ckb-std`, `ckb-testtool`, and CKB-VM

### Current features

- pinned `noir-ckb build`, `prove`, and `test` developer-preview commands;
- fail-closed public/private witness-layout validation;
- strict snarkjs-to-arkworks and Molecule conversion;
- a generic Groth16 verifier executed in CKB-VM;
- a Capsule binding Type Script deriving seven ordered public inputs from Cell
  data and Type Script arguments;
- one accepted correct transition and eleven expected rejection cases;
- hosted retained-fixture CI and a public reviewer smoke test; and
- an upstream Noir-Groth16 public-wire compatibility report.

### Planned features

- validate the first post-program reference use case with CKB maintainers and a
  potential integration partner;
- replace placeholder commitment, nullifier, and replay rules with a reviewed
  protocol statement;
- turn the fixed Capsule mapping into a versioned declarative binding manifest;
- broaden Noir support through explicit, tested compatibility profiles;
- add CCC transaction construction and a labeled testnet preview; and
- prepare reproducible releases and independent review before any production
  claim.

### Deployed on

Not deployed. The current result is a local and hosted-CI CKB-VM developer
preview using public fixtures and development-only Groth16 setup material.

### Links

- Repository: https://github.com/wamimi/noir-ckb-verifier
- Reviewer quickstart: https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/reviewer-quickstart.md
- Upstream compatibility issue: https://github.com/jamesbachini/Noir-Groth16/issues/1
- Background article: https://talk.nervos.org/t/the-proof-is-valid-the-transition-might-not-be/10550

There is no hosted application UI yet. The test surface is the documented CLI
and CKB-VM transaction matrix.

### Request for feedback

I would especially value feedback on these decisions:

1. Is a toolkit-first, use-case-led direction useful to CKB developers, or
   should the project lead with one application immediately?
2. Is private credential/eligibility proof a credible first reference
   application, or is there a more urgent CKB-native problem for proof-bound
   Cell transitions?
3. Is the proposed boundary correct: `groth16-ckb` verifies the mathematical
   proof, while `noir-ckb` derives its public statement from the transaction and
   enforces application meaning?
4. What is the smallest useful integration that could validate the binding
   manifest with a real CKB project?
5. Which components should be contributed upstream instead of maintained here?
6. What evidence and milestones would make a bounded Community Fund proposal
   credible without overstating production readiness?

For reproduction feedback, please run the reviewer quickstart and share the
generated public terminal log or the complete failure output. Do not share
private witnesses or setup material.

## Telegram message

Gm! I have reached the Week 12 developer-preview stage of `noir-ckb`, an
experimental path from a supported Noir circuit to a Groth16 proof verified in
CKB-VM and bound to the exact typed Cell transition it authorizes.

The current public demo has one expected acceptance case and eleven rejection
cases, including a valid proof paired with the wrong state, Capsule identity, or
replay domain. I have also preserved and reported an upstream public-wire
ordering problem rather than hiding it behind the working fixture.

I would appreciate two kinds of help:

1. Please try the reviewer smoke test and tell me whether the commands and
   failures are clear: https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/reviewer-quickstart.md
2. Please advise on the strongest post-program direction: a reusable toolkit
   first, a private credential/eligibility reference application, or another
   CKB-native use case that needs proofs bound to Cell transitions.

Repository: https://github.com/wamimi/noir-ckb-verifier

This is pre-audit development infrastructure, not a mainnet or production
release.

## Follow-up on the upstream issue

The public-wire finding is an issue, not yet a pull request:
https://github.com/jamesbachini/Noir-Groth16/issues/1

If there is still no maintainer response, add one concise follow-up rather than
opening a duplicate:

> I can prepare the regression fixtures and a focused PR if the proposed
> witness-to-wire remapping direction matches the backend's intended public
> output/input convention. The fix would update both R1CS allocation and WTNS
> vector generation and document artifact invalidation. Would that contribution
> be welcome?

## People and channels to approach

1. Share the CKBuilder project-review issue with **Neon**, the CKBuilders
   coordinator, and in the **CKBuilders Telegram channel**, as requested by the
   tracker instructions.
2. Ask **Cecilia**, maintainer of `groth16-ckb`, to review the verifier-versus-
   application binding boundary and packaging needs.
3. Follow up with **James Bachini** on Noir-Groth16 issue #1 about whether a
   remapping PR is welcome.
4. After CKB architectural feedback, approach a concrete identity/attestation
   team such as `did:ckb`, Vellum, or Attest CKB. Ask whether they have an actual
   private-eligibility requirement before choosing that use case.
