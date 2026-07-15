# Compatibility matrix

Status is evidence-based. “Pending” means the interface is planned or researched but has not yet been reproduced in the retained Week 7 command record.

| Layer | Artifact | Producer | Consumer | Format / assumptions | Week 7 status |
|---|---|---|---|---|---|
| Circuit source | `src/main.nr` | Developer | Nargo beta.18 | Noir source; `x` private, `y` public | Check and compilation passed 2026-07-15 |
| Development input | `Prover.toml` | Developer | Nargo/ACVM | TOML fixture; `x=7`, `y=49`; intentionally public test data | Accepted by `nargo check`; execution pending |
| Compiled program | `target/square_root.json` | Nargo/noirc beta.18 | ACIR-aware backend | Version-sensitive JSON containing bytecode and ABI metadata | Generated and inspected 2026-07-15; ignored by Git |
| Execution witness | `target/square_root.gz` or named witness | Nargo/ACVM beta.18 | Proving backend | Compressed witness; may contain private values | Not generated |
| Control proof | Barretenberg proof/VK | `bb` | Barretenberg | Honk/Barretenberg path; not a CKB Groth16 artifact | Optional; not generated |
| Groth16 constraint system | R1CS or backend-native constraint system | Week 8 backend | Groth16 setup/prover | Must represent supported ACIR semantics exactly | Deferred to Week 8 |
| Proposed proof set | BN254 Groth16 proof, VK, public inputs | Week 8 backend | Source verifier and Rust adapter | Source representation may be snarkjs JSON, gnark objects, or another typed format | Deferred to Week 8 |
| Validated crypto objects | arkworks BN254 proof, VK, `Fr` inputs | Rust artifact adapter | arkworks host verifier and wire encoder | Curve/subgroup validated; public-input order preserved | Deferred to Week 9 |
| Canonical bytes | arkworks compressed serialization | Rust artifact adapter | `groth16-ckb` Molecule encoder/decoder | arkworks 0.5-compatible encoding | Deferred to Week 9 |
| CKB VK payload | Molecule VK data | Host encoder | VK Cell / `groth16-ckb` | Cell data hash committed in script args | Existing endpoint; reproduction pending |
| CKB proof payload | Molecule proof + public inputs | Host encoder | `WitnessArgs.input_type` / `groth16-ckb` | Public transaction witness, not a private Noir witness | Existing endpoint; reproduction pending |
| Mathematical verification | Boolean verifier result | `groth16-ckb` | Capsule protocol | `verify(vk, public_inputs, proof)` | Existing endpoint; reproduction pending |
| Application semantics | Transition-bound public inputs | Capsule Type Script | CKB validation | Commitments to actual old/new state, identity, action, and replay domain | Design only; Week 10 |

## Week 8 backend candidates (research only)

### Noir-Groth16

The current project describes a Rust pipeline that parses Noir artifact JSON and ABI metadata, solves witnesses with ACVM, lowers supported ACIR opcodes to deterministic R1CS, emits iden3 `.r1cs`/`.wtns`, and uses snarkjs for Groth16 setup, proof generation, and verification.

Strengths for this project:

- explicit R1CS and witness intermediates
- explicit proof, public input, and verification-key JSON artifacts
- documented supported, guarded, and rejected ACIR behavior
- a compatibility corpus and strict failure mode

Open Week 8 questions:

- exact Noir/noirc and ACIR dependency revisions at the selected source commit
- exact mapping between its public input order and Noir ABI order
- development setup provenance and reproducibility
- safe conversion from snarkjs-style points into arkworks BN254 objects

No Week 7 backend command is run.

### Sunspot

Sunspot currently states that it requires Noir `1.0.0-beta.18`, consumes Noir circuits, and provides Groth16 proving/verification tooling oriented toward Solana through gnark-related components. It is unaudited.

Strengths for this project:

- explicit beta.18 compatibility matches the Week 7 compiler pin
- existing Noir-to-Groth16 evidence

Open Week 8 questions:

- how directly its proof and VK types can be exported without Solana-specific framing
- whether its setup and output formats support stable cross-library fixtures
- exact gnark-to-arkworks field and point conversion requirements

No Week 7 backend command is run.

## Selection rule

The Week 8 backend is selected by a reproducible minimal-circuit experiment, not by project popularity or newest compiler version. The compiler, ACIR parser, witness solver, lowering implementation, proof system, curve, and artifact formats must be pinned as one compatibility set.

## Sources

- [Noir-Groth16 repository](https://github.com/jamesbachini/Noir-Groth16)
- [Sunspot repository](https://github.com/reilabs/sunspot)
- [Noir manual workflow](https://noir-lang.org/docs/getting_started_manually)
- [groth16-ckb repository](https://github.com/CECILIA-MULANDI/groth16-ckb)
