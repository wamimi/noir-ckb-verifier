# Compatibility matrix

**Baseline reporting period:** Week ending Sunday, 12 July 2026

**Evidence reproduced and finalized:** 15 July 2026 as Week 7 catch-up

**Week 8 backend experiment:** executed and reviewed 20–21 July 2026

Status is evidence-based. “Pending” means the interface is planned or researched but has not yet been reproduced in a retained command record.

| Layer | Artifact | Producer | Consumer | Format / assumptions | Evidence status |
|---|---|---|---|---|---|
| Circuit source | `src/main.nr` | Developer | Nargo beta.18 | Noir source; `x` private, `y` public | Week 7 check and compilation passed |
| Public-first control source | `square-root-public-first/src/main.nr` | Developer | Nargo beta.18 | Same relation; declares public `y` before private `x` | Week 8 check/compile passed; ACIR assigns public `y` to `w0` and private `x` to `w1` |
| Public-first control R1CS/WTNS | iden3 `.r1cs` / `.wtns` | Pinned Noir-Groth16 experiment | snarkjs 0.7.5 | Identity layout is compatible only because public `y` is leading ACIR witness | Wire vector `[1,49,7,49]`; proof with `[49]` verifies; same proof with `[7]` is rejected |
| Development input | `Prover.toml` | Developer | Nargo/ACVM | TOML fixture; `x=7`, `y=49`; intentionally public test data | Week 7 fixture accepted and executed |
| Compiled program | `target/square_root.json` | Nargo/noirc beta.18 | ACIR-aware backend | Version-sensitive JSON containing bytecode and ABI metadata | Week 7 artifact generated and inspected; ignored by Git |
| Execution witness | `target/witness.gz` | Nargo/ACVM beta.18 | Proving backend | Gzip-compressed witness; may contain private values | Week 7 witness generated and integrity-checked; ignored by Git |
| Control proof | UltraHonk proof/VK/public inputs | Barretenberg `3.0.0-nightly.20260102` | Barretenberg | Barretenberg path; not a CKB Groth16 artifact | Week 7 control generated and explicitly verified; ignored by Git |
| Groth16 constraint system | iden3 `.r1cs` | Pinned Noir-Groth16 experiment | snarkjs Groth16 setup/prover | BN254; strict lowering; public/private wire placement must preserve Noir semantics | Structurally valid and satisfiable, but semantic gate failed: wire 1 contains private `x=7` while the R1CS marks one leading public input |
| Groth16 witness | iden3 `.wtns` | Pinned Noir-Groth16 experiment | snarkjs witness checker/prover | Pedantic ACVM solving; development fixture only | snarkjs 0.7.5 reports witness correct; exported vector is `[1,7,49,49]` |
| Proposed proof set | snarkjs `proof.json`, `verification_key.json`, `public.json` | Pinned Noir-Groth16 + snarkjs | Source verifier and future Rust adapter | Development-only BN254 Groth16; intended public vector is exactly `[49]` | Generated `[7]` verifies; intended `[49]` is rejected; artifact is mathematically valid but Noir-incompatible |
| Validated crypto objects | arkworks BN254 proof, VK, `Fr` inputs | Rust artifact adapter | arkworks host verifier and wire encoder | Curve/subgroup validated; public-input order preserved | Deferred to Week 9 |
| Canonical bytes | arkworks compressed serialization | Rust artifact adapter | `groth16-ckb` Molecule encoder/decoder | arkworks 0.5-compatible encoding | Deferred to Week 9 |
| CKB VK payload | Molecule VK data | Host encoder | VK Cell / `groth16-ckb` | Cell data hash committed in script args | Existing endpoint build and tests passed, including missing/wrong VK rejection |
| CKB proof payload | Molecule proof + public inputs | Host encoder | `WitnessArgs.input_type` / `groth16-ckb` | Public transaction witness, not a private Noir witness | Existing endpoint build and tests passed, including malformed/version/count rejection |
| Mathematical verification | Boolean verifier result | `groth16-ckb` | Capsule protocol | `verify(vk, public_inputs, proof)` | Normal suite: 39 passed; ignored suite: 2 passed including 1,000-sample differential test and cycle benchmark |
| Application semantics | Transition-bound public inputs | Capsule Type Script | CKB validation | Commitments to actual old/new state, identity, action, and replay domain | Design only; Week 10 |

## Week 8 backend selection

### Noir-Groth16

The first experiment selected Noir-Groth16 commit `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`. Manifest and lockfile inspection confirmed a beta.19 ACIR/ACVM runtime plus an explicit legacy beta.18 parser matching the Week 7 compiler source revision. User-run gates confirmed parsing, solving, strict lowering, setup, proving, and source verification, while also exposing the public-wire incompatibility described above.

Strengths for this project:

- explicit R1CS and witness intermediates
- explicit proof, public input, and verification-key JSON artifacts
- documented supported, guarded, and rejected ACIR behavior
- a compatibility corpus and strict failure mode

Required Week 8 checks:

- direct parsing of the existing beta.18 artifact
- exact mapping between its public input order and Noir ABI order; the exported value must be `49`, not private `x = 7`
- development setup provenance and reproducibility
- positive and negative source-verification behavior

Arkworks conversion is deferred to Week 9.

### Sunspot

Sunspot's current main branch states that it requires Noir `1.0.0-beta.22`, consumes Noir circuits, and provides Groth16 proving/verification tooling oriented toward Solana through gnark-related components. It is unaudited.

Strengths for this project:

- existing Noir-to-Groth16 evidence
- an independent gnark-oriented implementation for a later comparison

Open Week 8 questions:

- beta.18-to-beta.22 compiler migration requirements
- how directly its proof and VK types can be exported without Solana-specific framing
- whether its setup and output formats support stable cross-library fixtures
- exact gnark-to-arkworks field and point conversion requirements

It is deferred so the first experiment changes one compatibility boundary at a time.

## Selection rule

The Week 8 backend is accepted only by a reproducible minimal-circuit experiment, not by project popularity or a successful verifier message alone. The compiler, ACIR parser, witness solver, lowering implementation, proof system, curve, artifact formats, and semantic public-input order must form one pinned compatibility set.

## Sources

- [Noir-Groth16 repository](https://github.com/jamesbachini/Noir-Groth16)
- [Sunspot repository](https://github.com/reilabs/sunspot)
- [Noir manual workflow](https://noir-lang.org/docs/getting_started_manually)
- [groth16-ckb repository](https://github.com/CECILIA-MULANDI/groth16-ckb)
