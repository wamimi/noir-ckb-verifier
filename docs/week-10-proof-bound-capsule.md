# Week 10 proof-bound Capsule

## Objective

Week 10 moved the retained Noir-derived Groth16 path from host interoperability
into CKB-VM execution and added an application script that binds the proof's
ordered public inputs to a typed Capsule Cell transition.

The required transaction-level acceptance rule is:

```text
the pinned Groth16 verifier lock accepts the proof and public inputs
AND the Capsule Type Script derives the same ordered public inputs from the transaction
AND the Capsule structural rules hold
-> accept
```

The central negative case is equally important:

```text
the Groth16 proof remains valid for its encoded public inputs
AND one application-relevant field in the Capsule transition is changed
-> the transaction must be rejected by the Capsule Type Script
```

## Script composition

The prototype places the generic `groth16-ckb` verifier in the Capsule Cell's
lock field and the application-specific binding script in its type field. For a
one-input Capsule transition, both script groups resolve group input zero to the
same transaction input and therefore inspect the same `WitnessArgs.input_type`
payload.

The verifier lock establishes mathematical validity under the verification key
whose Cell data hash is committed in its script arguments. The Capsule Type
Script does not duplicate pairing verification. It decodes the public-input
vector and compares it with values derived from the input Cell, output Cell, and
type-script arguments.

## Version 1 application encoding

The initial encoding is deliberately fixed-width and fail-closed.

```text
Capsule Type Script args (65 bytes)
  version                 1 byte, value 1
  capsule_id             32 bytes, canonical arkworks Fr encoding
  replay_domain          32 bytes, canonical arkworks Fr encoding

Capsule Cell data (65 bytes)
  version                 1 byte, value 1
  state_commitment       32 bytes, canonical arkworks Fr encoding
  nullifier              32 bytes, canonical arkworks Fr encoding
```

The transition action is the canonical scalar value `1`, representing an
update. The Type Script requires exactly one group input and one group output,
preserves the input lock script on the output, and derives this ordered vector:

```text
[
  capsule_id,
  input.state_commitment,
  input.nullifier,
  output.state_commitment,
  UPDATE_ACTION_ID,
  output.nullifier,
  replay_domain,
]
```

Every scalar must already be in the 32-byte canonical representation expected
by the pinned arkworks 0.5 endpoint. No modular reduction, alternate byte order,
or variable-width integer is accepted at the application boundary.

## Circuit fixture

The first transition fixture uses public, non-secret values:

| Field | Value |
|---|---:|
| Capsule ID | 11 |
| Old state commitment | 65 |
| Old nullifier | 5 |
| New state commitment | 66 |
| Action ID | 1 |
| New nullifier | 96 |
| Replay domain | 13 |
| Private development witness | 7 |

The constraints are:

```text
old_state_commitment = secret^2 + capsule_id + old_nullifier
new_state_commitment = old_state_commitment + action_id
new_nullifier = secret * replay_domain + old_nullifier
```

These equations ensure that every public value participates in the proved
statement. They are a compact interoperability and authorization fixture, not a
final Capsule cryptographic design.

## Executed gates

### Gate 1: Noir semantics — completed

- `nargo check`
- `nargo compile --print-acir`
- inspect the ABI and confirm seven public parameters followed by one private
  parameter
- `nargo execute witness`
- inspect and hash the generated ACIR and witness

### Gate 2: pinned Groth16 backend — completed

- parse, solve, and lower the circuit with the pinned backend
- inspect the R1CS header and full witness ordering
- require exported public values to equal `[11, 65, 5, 66, 1, 96, 13]`
- generate a development-only Groth16 key and proof
- verify the intended vector and reject at least one changed public vector

### Gate 3: adapter and production wire format — completed

- convert the retained snarkjs artifacts through validated arkworks objects
- verify in arkworks
- encode the pinned version-1 Molecule VK and witness payloads
- decode through the production endpoint crates and require exact byte equality

### Gate 4: CKB-VM mathematical verification — completed

- execute the Noir-derived proof through the production `groth16-ckb` RISC-V
  binary under `ckb-testtool`
- record the exact script revisions, binaries, hashes, exit results, and cycles

### Gate 5: proof-bound Capsule authorization — completed for the retained fixture

- valid proof plus the intended Capsule transition accepts
- the same valid proof plus a changed new state rejects
- the same valid proof plus a changed Capsule ID rejects
- the same valid proof plus a changed replay domain rejects
- an invalid proof rejects
- an omitted verification-key Cell dependency rejects
- malformed Cell data, malformed script args, malformed witness data, and
  multiple-cell group shapes reject

The corrected explicit matrix ran 12 CKB-VM transaction cases. The intended
transition was accepted in `101,625,705` cycles. The eleven negative cases were
rejected at their intended verifier or binding-script boundary, including the
central valid-proof/wrong-transition cases and the two group-ambiguity cases.
Exact exit codes and command evidence are retained in
[`../evidence/week-10.md`](../evidence/week-10.md).

## Deliverables

- transition-aware Noir circuit and deterministic development fixture
- byte-level Capsule version-1 specification
- application-specific Capsule binding Type Script
- CKB-VM integration harness using the production Groth16 verifier binary
- positive, negative, replay-domain, malformed-data, and missing-VK-dependency tests
- exact artifact hashes, binary sizes, test totals, exit codes, and cycle counts
- updated architecture, compatibility matrix, and threat-boundary documents
- evidence-gated Week 10 CKBuilder report

## Non-goals

Week 10 does not claim a production trusted setup, a general ACIR-to-R1CS
compiler, a private mainnet deployment, a final hash/commitment construction,
an audit, or production readiness. The fixed-width explicit public tuple is a
prototype contract between the Noir statement and CKB transaction semantics.
