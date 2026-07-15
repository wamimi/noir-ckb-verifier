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

The selected backend will lower the supported ACIR program into a Groth16-compatible constraint system, solve or import the witness, and produce BN254 proof material. Backend selection and execution are Week 8 work.

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
- prove and verify the minimal circuit in the source backend

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
