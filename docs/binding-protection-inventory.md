# Capsule protection inventory — v1

Inspected before test implementation on 2026-10-06 at toolkit
`090461a901ac569e3331ded05fc4c3896f0457c5`; backend
`828025f3a0090e2934940956c0f5dc8093eb5532`; verifier
`d64c769ffe2d2edb5eb308dc59058efda77c2f83`. External checkouts were clean.
The four existing untracked planning/evidence documents are outside this work.

This inventory describes the configured proof-in-Lock plus binding-Type fixture.
“Existing test” means inspected source and historical Week 14 evidence, not a new
execution. New measurements belong in the separate binding-review evidence.

Sources: `contracts/crates/capsule-binding/src/main.rs`,
`crates/ckb-integration-tests/tests/{capsule_transition,verifier_vm}.rs`,
`crates/noir-ckb-cli/src/workflow.rs`, the pinned verifier's
`script/crates/{ckb-script,wire-decode,verifier-core}/src/`, and
`circuits/proof-bound-capsule/src/main.nr`.

| Property / intended guarantee | Component and exact coverage | Existing test / expected rejection | Gap or exclusion |
| --- | --- | --- | --- |
| Invalid proof cannot authorize | Verifier pairing check for committed VK and entire ordered public vector | `invalid_proof_with_matching_changed_transition_rejects_in_verifier`, code 5 | Conditional on the input actually using the intended verifier Lock |
| Wrong VK cannot substitute | Lock args are 32-byte CKB hash of complete Molecule VK Cell data; first matching CellDep | `missing_vk_cell_rejects_in_verifier`, 12 | Existing test is missing-key, not well-formed wrong-key substitution; duplicate identical hash is accepted by first-match lookup, unlike Cecilia's separate zk-lock |
| Wrong public values | Type compares all seven 32-byte slots to args/data/action; verifier checks proof against supplied vector | wrong-new-state Type 30; altered-new-state verifier 5 | These are different boundaries |
| Public ordering | CLI scalar ABI names/order and exported witness/vector guards; Type positional comparison | Week 14 interleaved swapped `[121,49]` rejected by snarkjs/adapter; CLI semantic gate | No existing Capsule VM permutation case; arrays/structs/returns excluded |
| Capsule identity | Slot 0 equals Type args bytes 1..33 | `valid_proof_and_wrong_capsule_id_reject`, 30 | Numeric identity is not a unique Type ID or OutPoint |
| Old/new state | Slots 1/2 from input state/nullifier; 3/5 from successor state/nullifier | wrong-new-state, 30 | Old-state and both nullifier mismatch cases not explicit in old matrix |
| Action/domain | Slot 4 is scalar 1; slot 6 is Type args bytes 33..65 | wrong-replay-domain, 30 | Fixed domain is not network/script/input/transaction binding; no action-negative VM case yet |
| Successor Lock | Complete input/output Lock hashes must match | `changed_verifier_lock_reject`, 32 | Preserves whatever Lock was supplied; does not authenticate verifier code identity |
| Duplicate groups | Exactly one Type group input/output; exactly one transaction input/output with input Lock hash | duplicate Capsule input 23; duplicate verifier-Lock input 33 | Output duplicates not explicit in old tests; multiple unrelated groups allowed only if these cardinalities hold |
| Witness ownership | Both scripts read group-input 0 `WitnessArgs.input_type`; cardinalities align groups in configured composition | duplicate input cases above | Missing/misplaced witness and nonzero absolute input position need explicit tests |
| Malformed/truncated | Type args/data: version 1 and exactly 65 bytes; seven-public-input count/length; verifier Molecule and canonical point/scalar decoding | malformed args 21, input data 25, truncated witness 17 | Not exhaustive decoder fuzzing; Type's byte comparison alone is not field-range validation |
| Creation | Type requires group input 0 | No existing Capsule creation test; code predicts 24 | Unsupported lifecycle, not a deployable initialization path; testtool inserts starting Cells directly |
| Destruction | Type requires group output 0 | No existing destruction test; code predicts 24 | Intentionally update-only |
| Reuse at another input | Statement has no consumed OutPoint | No old explicit test; same seven fields are predicted reusable | Actual limitation for input-specific authorization; UTXO double-spend rules do not prevent reuse at another Cell |
| Reuse in changed transaction | Only seven values and structural Lock/group rules examined | Changed state with old values 30; changed vector with old proof 5 | Changes outside selected fields may accept; no full transaction commitment |
| Capacity / unrelated outputs | Neither capacity nor unrelated output bytes enter the statement or Type checks | No existing explicit test | Intentional exclusion for wiring fixture; unsafe to infer value preservation or payment authorization |
| Verifier identity | Harness assigns generic verifier; Type checks continuity only | No existing bypass test | Composition gap if Type is treated as independently proof-enforcing; same always-success Lock can satisfy continuity |

The circuit proves the three arithmetic equalities in its source. “Commitment”
and “nullifier” are field names, not evidence of hiding, unlinkability, or a
production one-time authorization mechanism. All seven current public fields
participate in those equalities. There is no spare context slot. Reinterpreting
`replay_domain` as an OutPoint digest would change both semantics and constraints
(`new_nullifier = secret * replay_domain + old_nullifier`), so it is not a
protocol-preserving enhancement.

Planned bounded validation: paired script-mismatch and cryptographic-reuse cases;
capacity/unrelated-output/cross-input acceptance controls; missing/moved witness,
output ambiguity, lifecycle and wrong-key cases; two isolated RISC-V check
mutations. No production check or statement field is changed by this work.

## Reproduced additions after the initial inventory

All names below are in `binding_boundaries.rs`; the original matrix remained
unchanged. The baseline ran using the Week 14 published-fork proof fixture.
See [evidence](../evidence/binding-review.md) for binary hashes and mutation results.

| Property | New test | Observed boundary |
| --- | --- | --- |
| All Cell-derived statement fields | `each_cell_statement_field_mismatch_rejects` | Type 30 for slots 0,1,2,3,5,6 |
| Each public value; wrong action | `old_proof_with_each_changed_public_value_rejects_in_verifier`; `type_action_comparison_rejects_without_verifier` | Verifier 5 for all slots; isolated Type action 30 |
| Correctly recomputed different operation | `old_proof_with_recomputed_valid_operation_rejects` | Verifier 5 |
| Public ordering | `swapped_public_values_with_matching_cells_reject_in_verifier` | Verifier 5 |
| Invalid proof | `well_formed_invalid_proof_rejects` | Verifier 5 |
| Wrong key | `well_formed_substituted_vk_fails_identity`; `rebound_different_vk_rejects_old_proof` | 12 with original identity; 5 with changed key identity |
| Cross-input reuse | `same_proof_accepts_at_two_distinct_input_outpoints` | Accepts: excluded from current statement |
| Capacity | `same_proof_accepts_changed_capacity` | Accepts: excluded |
| Changed transaction / unrelated output | `same_proof_accepts_unrelated_output` | Accepts: excluded |
| Witness indexing | `group_witness_at_nonzero_absolute_input_accepts` | Accepts correct group-relative slot |
| Wrong/missing witness | `proof_at_wrong_absolute_witness_rejects`; `missing_input_type_rejects` | Verifier 16 |
| Lock group ambiguity | `duplicate_verifier_lock_input_rejects`; `duplicate_verifier_lock_output_rejects` | Type 33 |
| Type output ambiguity | `duplicate_capsule_output_rejects` | Type 23 |
| Lifecycle | `capsule_creation_is_unsupported`; `capsule_destruction_is_unsupported` | Type 24 |
| Verifier identity gap | `type_alone_does_not_authenticate_verifier_lock` | Invalid proof accepts with same always-success Lock |

Malformed/truncated and successor-Lock rejection remain covered by the original
matrix, which also passed. New wrong-key tests close the missing substitution
case for a well-formed transformed key; they are not a second trusted setup.
Context-specific schema, authenticating verifier admission, production commitment
construction, on-chain bootstrap and value policy remain unresolved design work.
