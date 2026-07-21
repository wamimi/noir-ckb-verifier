# Architecture

## Goal

The project aims to turn a Noir-authored statement into circuit-specific artifacts consumable by a generic CKB Groth16 verifier, then bind the proof's public inputs to a typed Cell transition.

The first architecture does not generate a new Rust verifier binary for each circuit. It separates reusable code from circuit-specific data:

```text
generic verifier code Cell
  + circuit-specific VK Cell
  + proof/public-input transaction witness
  + application Type Script rules
```

## Proposed pipeline

```text
Noir source (.nr)
  |
  | nargo compile / nargo execute
  v
versioned ACIR program artifact + execution witness
  |
  | Week 8 experimental ACIR-to-Groth16 backend
  v
BN254 Groth16 proof + verification key + ordered public inputs
  |
  | typed Rust adapter
  v
validated arkworks BN254 objects + canonical compressed serialization
  |
  | Molecule host encoder
  v
VK Cell data + WitnessArgs.input_type payload
  |
  | generic groth16-ckb script
  v
verify(vk, public_inputs, proof)
  |
  | Capsule application protocol
  v
proof-bound old Cell -> new Cell transition
```

## Layer responsibilities

### Noir and ACIR

Noir describes the statement and which inputs are private or public. Nargo compiles the program into a version-sensitive ACIR artifact and executes the circuit to produce a witness assignment. Neither artifact is itself a Groth16 proof.

### Groth16 backend

The selected experiment backend lowers supported ACIR programs into Groth16-compatible constraint systems, solves or imports witnesses, and produces BN254 proof material. Week 8 confirmed that these mechanical stages can succeed while public-wire semantics still fail, so the backend cannot be accepted without the boundary checks below.

### ACIR witness to R1CS wire boundary

An R1CS header records counts for public outputs, public inputs, and private inputs. Those counts are meaningful only if the corresponding values occupy the target format's required wire positions. Copying ACIR witnesses to R1CS wires by index while separately copying only the visibility counts is not a semantic conversion.

Week 8 demonstrated the failure concretely:

```text
Noir private-first ACIR: [w0=x=7 private, w1=y=49 public]
identity R1CS wires:     [wire1=7 public, wire2=49 private]
result:                  proof verifies with [7], rejects [49]
```

The public-first control happened to align with identity mapping:

```text
Noir public-first ACIR:  [w0=y=49 public, w1=x=7 private]
identity R1CS wires:     [wire1=49 public, wire2=7 private]
result:                  proof verifies with [49], rejects [7]
```

The adapter/backend boundary must therefore implement one of two policies before setup or proving:

1. Soundly remap public outputs, public inputs, private inputs, remaining witnesses, constraint terms, and materialized witness values into the target R1CS order.
2. Fail closed unless the ACIR witness layout already exactly matches the required R1CS order.

Source parameter reordering is acceptable as a labeled compatibility fixture, not as a general conversion algorithm.

### Artifact adapter

The adapter must parse source proof objects into typed field elements and affine points, reject invalid encodings, and serialize validated objects using arkworks canonical serialization. It must not rely on ad hoc hex reversal.

Required validation includes:

- exact field bounds
- coordinate and extension-field ordering
- curve membership
- subgroup membership
- infinity handling
- public-input ordering and count
- source/destination verification agreement

### CKB wire layer

The generic verifier expects circuit-specific VK data in a CellDep and proof plus public inputs in `WitnessArgs.input_type`, encoded through its Molecule schema. The consuming script commits to the intended VK Cell data hash.

Molecule provides deterministic framing. It does not establish cryptographic validity or application meaning.

### Capsule application layer

The application layer derives the expected public inputs from the actual transaction. A valid proof is accepted only if its public inputs match the consumed and created Capsule Cells and the chosen replay domain.

## Why the Barretenberg path is only a control

The installed Barretenberg toolchain can demonstrate that the Noir artifact and witness are usable by Noir's common proving path. That result is useful as a control, but it does not produce the BN254 Groth16/arkworks interface consumed by `groth16-ckb`.

Any optional Week 7 Barretenberg proof must be labeled:

```text
Noir artifact control: verified by Barretenberg
CKB Groth16 compatibility: not established
```

## Milestones

### Week 7: endpoint baseline

- minimal circuit
- ACIR artifact and execution witness
- artifact inspection
- existing CKB-VM verifier reproduction
- compatibility and threat documentation

### Week 8: ACIR to Groth16

- deliberately select and pin a backend
- produce a development-only BN254 Groth16 setup
- preserve the private-first semantic failure as a regression fixture
- prove and verify a public-first compatibility control in the source backend
- require a fail-closed layout policy before general use

### Week 9: cross-library interoperability

- typed conversion into arkworks objects
- canonical serialization and Molecule encoding
- source-backend and arkworks host verification of the same proof

### Week 10: proof-bound Capsule

- CKB-VM verification through the production wire decoder
- transaction-derived public inputs
- accept the correct transition and reject a valid proof attached to the wrong transition

## Primary references

- [Noir manual workflow](https://noir-lang.org/docs/getting_started_manually)
- [Nargo command reference](https://www.noir-lang.org/docs/reference/nargo_commands/)
- [Molecule in CKB](https://docs.nervos.org/docs/serialization/serialization-molecule-in-ckb)
- [groth16-ckb](https://github.com/CECILIA-MULANDI/groth16-ckb)
