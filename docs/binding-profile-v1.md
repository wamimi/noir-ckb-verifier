# Proposed specification: noir-ckb Capsule binding profile v1

Document revision 1, 2026-10-06. `noir-ckb/capsule-selected-fields/1` is a
proposed documentation/profile identifier for the existing implementation; it
is not a new on-chain field or an implemented generic application ABI. Normative
statements below describe acceptance of the current configured composition.
Future requirements are explicitly marked proposed. See the
[protection inventory](binding-protection-inventory.md) and
[reproduced evidence](../evidence/binding-review.md).

## Supported compiler and circuit profile

Noir/Nargo `1.0.0-beta.18`, noirc
`99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`; maintained Noir-Groth16 fork
`828025f3a0090e2934940956c0f5dc8093eb5532`; strict supported ACIR lowering;
BN254 Groth16 via snarkjs `0.7.5`; typed arkworks `0.5` adapter.
Scalar Field parameters only, no return value. Arrays, structs, unsupported
opcodes and other compiler versions are outside this toolkit profile.
The backend maps ACIR witnesses consistently to visibility-ordered R1CS wires;
the CLI independently checks scalar ABI names/order and exported values.
The normal toolkit build/prove/test application harness remains Capsule-specific.

The Capsule relation is exactly:

```
old_state = secret * secret + capsule_id + old_nullifier
new_state = old_state + action
new_nullifier = secret * replay_domain + old_nullifier
```

These are arithmetic fixture equations, not production commitments. The relation
does not establish a complete reusable private-state lifecycle.

## Ordered statement and canonical encoding

| Slot | Field | Source checked by the Type |
| --- | --- | --- |
| 0 | capsule_id | Type args bytes `[1,33)` |
| 1 | old_state_commitment | GroupInput 0 data `[1,33)` |
| 2 | old_nullifier | GroupInput 0 data `[33,65)` |
| 3 | new_state_commitment | GroupOutput 0 data `[1,33)` |
| 4 | action_id | Constant scalar 1 (update) |
| 5 | new_nullifier | GroupOutput 0 data `[33,65)` |
| 6 | replay_domain | Type args `[33,65)` |

Args and Cell data are exactly 65 bytes, beginning with byte version 1.
Each scalar is exactly 32-byte little-endian canonical BN254 Fr, value less than
`21888242871839275222246405745257275088548364400416034343698204186575808495617`.
No modular reduction, decimal-to-byte guessing, implicit sorting or permutation
is part of this ABI. The Type compares bytes; canonical scalar validity relies
on the composed verifier's decoder. A Type under another Lock does not inherit
that guarantee.

On-chain VK and witness are the pinned verifier's **Molecule**
`Groth16VerifyingKey` and `Groth16Witness`, each with uint16 little-endian
version 1 and the BN254 union variant (tag 0). Source of truth:
`groth16-ckb/schemas/groth16.mol` at the verifier pin. Proof points are canonical
compressed arkworks `a:G1(32) || b:G2(64) || c:G1(32)` inside the witness table.
The public `FrVec` is count-framed; the decoder reconstructs
`u32_le(7) || seven scalars` (228 bytes) for verifier-core.
VK decoding reconstructs `alpha:G1 || beta:G2 || gamma:G2 || delta:G2 ||
u64_le(8) || eight G1 IC points`. Molecule offsets/framing are not optional.
Malformed versions, unions, lengths and noncanonical fields/points reject;
verifier-core also rejects infinity points and mismatched public/IC counts.

This is not Cecilia's separate zk-lock raw `WitnessArgs.lock` profile or
CellScript's fixed 464-byte Spawn envelope. Those formats are not interchangeable.

## Identities and witness ownership

Verifier source pin: `CECILIA-MULANDI/groth16-ckb`
`d64c769ffe2d2edb5eb308dc59058efda77c2f83` (upstream licensing retained).
Lock args must be exactly the 32-byte CKB personalized Blake2b data hash of the
complete intended **Molecule VK Cell data**. The verifier resolves the first
matching CellDep by data hash; duplicate identical data is not rejected by this
pin. A witness cannot select a replacement VK. A new setup requires its own VK
identity even for the same circuit.

The Lock Script's `code_hash`, `hash_type`, and args identify the execution
policy. The evidence records executable SHA-256 for provenance, which must not
be confused with either a CKB data hash or a Script hash. The testtool harness
uses `Context::build_script`, hence `hash_type=Type` and a synthetic code Cell
Type hash. It is not a deployment or an immutable data-hash upgrade policy.
Same Script hash does not freeze executable bytes under an upgradeable Type-hash
resolution policy. Future deployment must specify and authenticate that policy.

Both verifier Lock and Capsule Type read `WitnessArgs.input_type` at their
respective GroupInput index 0. Exactly-one group/cardinality rules make this the
same absolute input in the intended composition. It need not be transaction
input 0. `lock` and `output_type` are not alternate proof locations. Unrelated
Locks must retain their own witness ownership. Private Noir witnesses must never
be placed in public transaction witnesses.

The Capsule Type preserves the input Lock's complete hash, but **does not pin it
to the intended verifier**. The toolkit harness supplies this identity. A copied
Type attached to an always-success Lock is not a proof-enforcing application.
The regression suite explicitly demonstrates this composition gap. Proposed
future admission must authenticate verifier code/resolution policy and VK; this
requires a separately approved design, not a silent reinterpretation of args.

## Transaction shape, replay and errors

Exactly one input and one output in the Capsule Type group are required. Exactly
one transaction input and output may use that input Lock hash. Successor Lock
hash must equal input Lock hash. Other inputs/outputs are allowed subject to
those cardinalities and their own scripts. No sorting is performed: group
selection follows CKB Script identity, and positions can have application meaning.
Creation and destruction are unsupported (Type code 24); this fixture has no
on-chain bootstrap. Testtool installs the starting Cell directly.

Public mismatches reject with Type 30; duplicate Type members with 23; changed
successor Lock with 32; duplicate matching Lock members with 33. Verifier code 5
means a structurally valid proof/public/key combination failed verification;
missing bound VK is 12, absent input_type 16, malformed witness Molecule 17.
These codes describe the first observed failing script/check, not all possible
causes. Complete errors and script locations are retained in test logs.

Replay scope is exactly the seven selected values and structural checks.
There is no derived input OutPoint, network identity, Script hash, capacity,
`since`, fee, unrelated output, dependency list or raw transaction hash in the
statement. An already spent OutPoint is unavailable under CKB consensus, but a
proof can be reused at another Cell with the same selected statement. A numeric
replay_domain does not create one-time authorization. These tests exercise
CKB-VM via testtool, not capacity/liveness/mempool consensus admission.

## Compatibility and upgrade behavior

The schema, field order, circuit relation, VK, codec and executable-resolution
policy form one compatibility profile. Updating compiler/backend wire layout or
circuit constraints requires revalidation and normally fresh setup/proof material;
old keys cannot be relabeled. Different Lock args/code identity cannot pass the
current successor-Lock continuity rule. Type args changes split Script groups
and hit the unsupported create/destroy shapes. There is no migration entrypoint.
A future profile must use a separate explicit version and documented migration;
interface compatibility alone is not authority to replace executable code or VK.

## Proposed context profile — not implemented or approved

There is no unused Capsule context slot. Replacing replay_domain with a digest
would also change its circuit equation. A future version should distinguish
application constraints from a script-derived context envelope, include game or
application identity, action and input-specific scope, and prove binding with
both script-mismatch and old-proof/new-statement tests. The unused-public probe
shows binding for one exact lowering/prover path, not a guarantee for all backends.

| Candidate | Covered fields | Transaction assembly consequence |
| --- | --- | --- |
| Selected-field envelope | Explicit domain/profile, relevant ordered input OutPoints, application state/action, intended successor identity and any value/recipient fields the application needs | Changes outside the envelope can preserve a proof, but scripts still need explicit capacity/payment policies; sponsors can finalize excluded fee/change fields later |
| Whole raw transaction envelope | CKB raw transaction hash plus application/Script/domain context and input-specific selection where required | Finalize input order, since, outputs/data/capacity, dependencies, headers, version, fees/change before proving; changing any raw field requires a new proof |

“Whole transaction” here means **raw** transaction, excluding witnesses; including
proof bytes in their own commitment would be circular. Signatures can be added
after proving only while preserving raw fields and proof ownership. A client
should reserve proof space before fee calculation and reject post-proof raw
mutations. Live-input races still require re-resolution and usually reproving.
A transaction hash alone does not mean every witness or resolved dependency
upgrade policy is protected. Each profile needs explicit network/domain policy.

For a future context digest, prefer an explicitly specified lossless digest-to-
field encoding (for example two canonical u128 limbs) or document the security
scope of any deliberate truncation. Do not silently import Cecilia's 31-byte
truncation or CellScript's 15-input schema. No encoding choice is adopted here.
