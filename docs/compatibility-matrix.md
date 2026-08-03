# Compatibility matrix

**Baseline reporting period:** Week ending Sunday, 12 July 2026

**Evidence reproduced and finalized:** 15 July 2026 as Week 7 catch-up

**Week 8 backend experiment:** executed and reviewed 20–21 July 2026

**Week 9 adapter experiment:** executed and reviewed 27 July 2026

**Week 10 proof-bound Capsule experiment:** executed and reviewed 3 August 2026

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
| Private-first diagnostic proof set | snarkjs `proof.json`, `verification_key.json`, `public.json` | Pinned Noir-Groth16 + snarkjs | Source verifier | Development-only BN254 Groth16; Noir-intended public vector is `[49]` | Generated `[7]` verifies; intended `[49]` is rejected; proof is mathematically valid but Noir-incompatible |
| Public-first compatibility proof set | retained snarkjs JSON fixture | Pinned Noir-Groth16 + snarkjs | snarkjs 0.7.5 and Rust adapter | Development-only BN254 Groth16; constrained identity wire layout | Both implementations accept `[49]` and reject `[7]`; fixture hashes unchanged by recheck |
| Validated crypto objects | arkworks BN254 proof, VK, `Fr` inputs | Rust artifact adapter | arkworks host verifier and wire encoder | Strict decimal bounds; curve/subgroup validation; public-input count and order preserved | Week 9 retained fixture converted; arkworks accepts `[49]` and rejects `[7]` |
| Canonical bytes | arkworks compressed serialization | Rust artifact adapter | `groth16-ckb` Molecule encoder/decoder | arkworks 0.5 canonical compressed encoding | Week 9 emitted 296-byte VK, 128-byte proof, and 36-byte one-input buffer; exact endpoint round trip passed |
| CKB VK payload | version-1 Molecule VK data | Rust artifact adapter | VK Cell / `groth16-ckb` | Cell data hash committed in script args | 334-byte host payload emitted and decoded; CKB data hash `1fa6f0c18ff7b0d32abcd01ddf2ddcc3e4190be99add55bbf2418f045eb32715`; not yet exercised in CKB-VM |
| CKB proof payload | version-1 Molecule proof + public inputs | Rust artifact adapter | `WitnessArgs.input_type` / `groth16-ckb` | Public transaction witness, not a private Noir witness | 194-byte host payload emitted; pinned decoder round trip and host verifier passed; malformed version/witness and wrong public input rejected |
| Mathematical verification | Boolean verifier result | `groth16-ckb` | Capsule protocol | `verify(vk, public_inputs, proof)` | Normal suite: 39 passed; ignored suite: 2 passed including 1,000-sample differential test and cycle benchmark |
| Capsule statement | `proof-bound-capsule` ACIR/R1CS and seven public inputs | Nargo beta.18 + pinned Noir-Groth16 | snarkjs 0.7.5 | Public-first constrained layout; one private authorization witness | Week 10 public vector `[11,65,5,66,1,96,13]` preserved; snarkjs accepts intended vector and rejects three single-field changes |
| Week 10 CKB wire payload | 526-byte VK Molecule data and 386-byte witness payload | Rust artifact adapter | Pinned `groth16-ckb` decoder and CKB-VM verifier | Seven canonical arkworks `Fr` inputs in fixed semantic order | Host round trip and verification passed; production CKB-VM accepted the Noir-derived proof in `101,576,496` cycles |
| Capsule binding script | 28,032-byte stripped RISC-V ELF | Rust `1.94.1`, `ckb-std 1.1.0` | CKB-VM | Fixed 65-byte args/data; exact group shapes; preserved verifier lock; transaction-derived public tuple | Built and executed; SHA-256 `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |
| Application semantics | Transition-bound public inputs | Capsule Type Script | CKB validation | Actual old/new state, Capsule ID, action, nullifiers, and replay domain | Fixed Week 10 fixture completed: correct transition accepted; 11 malformed, invalid, ambiguous, or wrong-transition cases rejected; combined transaction `101,625,705` cycles |

## Week 8 backend selection

### Noir-Groth16

The first experiment selected Noir-Groth16 commit `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`. Manifest and lockfile inspection confirmed a beta.19 ACIR/ACVM runtime plus an explicit legacy beta.18 parser matching the Week 7 compiler source revision. Retained execution gates confirmed parsing, solving, strict lowering, setup, proving, and source verification, while also exposing the public-wire incompatibility described above.

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

Arkworks conversion and pinned host wire interoperability were completed for the
separate public-first compatibility fixture in Week 9. The private-first
diagnostic remains an intentional rejection case.

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
