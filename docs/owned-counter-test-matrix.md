# Owned counter v1 acceptance-to-test matrix

Executed results: [48 VM cases](../evidence/week-15/matrix-results.json),
[three isolated RISC-V mutations](../evidence/week-15/mutations.json),
[range checks](../evidence/week-15/range-results.json), and
[local node lifecycle](../evidence/week-15/local-run.json).
The VM cases are rows within one Rust integration-test function, not 48 separately
registered Rust tests. Every row uses the same baseline code identities; changes
named below are explicit. Correct owner signatures are regenerated for candidate
transactions except signature-negative cases.

| Requirement | Cases / evidence | Enforcing boundary and result |
| --- | --- | --- |
| Real initialization | create-valid; local creation receipt | Actual transaction, zero state, owner signature, full Type ID; output checked live at confirmation |
| Invalid initial state | create-nonzero | Type code 53, no proof required |
| Invalid identity | create-wrong-id; substituted-id; initial-unknown-version | Full creation hash / exact Type continuity / args version reject (44/42/41) |
| Unique instance shape | duplicate-output; ambiguous-different-id; duplicate-input-group; ambiguous-input-identities; initial-duplicate-output | Type scans same code/hash_type across args, rejects with 42 |
| Valid update | update-valid; local update receipt | Fresh four-input proof, actual signature, bound input consumed and successor checked |
| Signature requirement | missing-signature; wrong-signature | Standard Lock rejects -2/-31 in these cases; Type is not signature verifier |
| Proof mandatory under admitted owner | invalid-proof-permitted-owner | Structurally valid unrelated proof with correct supplied vector reaches pairing, rejects 51 |
| Unsupported owner | always-success-owner; always-success-valid-proof | Synthetic otherwise canonical input; Type rejects admission 45 before pairing; never claim always-success supplies authorization |
| Owner executable admission | resolved-owner-code-substitution | Synthetic code dep with same Type hash but always-success data rejects 45 |
| Pinned VK | wrong-vk; missing-vk; duplicate-vk | Type rejects 50; witness/creator cannot select another VK policy |
| Public order | wrong-public-order | Type compares exact derived vector, rejects 49 |
| Successor state | wrong-successor-state | Old supplied vector mismatches actual state, rejects 49 |
| Input-specific script binding | other-outpoint-old-vector | Context comparison rejects 49 |
| Input-specific cryptographic binding | other-outpoint-recomputed-old-proof; other-outpoint-fresh-proof | Correct different vector with old proof rejects 51; fresh proof accepts |
| Different valid operation | other-operation-old-proof; other-operation-fresh-proof | 1→2 operation with correctly derived vector rejects old 0→1 proof; fresh proof accepts |
| Ownership unchanged | owner-changed; initial-owner-substitution | Type rejects 46; fresh proof over changed successor owner cannot override policy |
| Capacity preserved | capacity-reduced; capacity-increased | Fresh correct proofs over changed capacity still reject 47 |
| Witness owner/location | missing-proof; proof-in-output-type; proof-wrong-index; application-at-index-one | Wrong placement rejects 48; correct GroupInput mapping at absolute index one accepts |
| Malformed inputs | truncated-proof; trailing-proof; wrong-wire-version; oversized-witness; malformed-state | Canonical decoder / 512-byte witness limit / state format rejects 48 or 43 |
| Resource limits | input-limit; output-limit; resolved-dependency-limit | 65 entries reject 52 (resolved deps includes dep-group expansion) |
| Destruction | destruction | Explicit unsupported shape rejects 42 |
| Intentionally excluded fields | unrelated-change-capacity; unrelated-change-data; dependency-order; input-since-excluded | Same proof, regenerated owner signature accepts in VM; since consensus maturity is outside testtool's limited consensus checks |
| No position sorting | application-at-index-one | Reordered application/funding positions preserve selected context on updates; correct witness placement accepts |
| Exact circuit public binding | setup-commands.json four changed-scalar verifications | Fresh circuit/setup; each changed public coordinate rejects original proof in snarkjs; Type separately derives context |
| Exact circuit bounds | maximum-valid plus five range-negative cases | Fresh maximum-range proof accepts; count overflow, each context overflow, and non-increment fail ACVM with Cannot satisfy constraint |
| Client assembly | client-check.json; client-stale-rejection.json | Live 1→2 proof check accepts while preserving output_type; changed successor rejects before signing |
| Artifact integrity | release/build manifests; CLI inspect | SHA-256 files and CKB data hashes checked; wrong network/genesis refuses client execution |

The constraint-negative results are witness-solving failures, not produced invalid
proofs. No zero-public fresh-proof claim is made. R1CS/wtns checks and development
zkey/ptau verification also run for the actual new circuit. The exact four-public
circuit has 2,339 constraints and 2,325 R1CS variables in this pipeline.

## Mutation criteria and results

Each mutation copies the contract workspace, removes one marked check, builds its
actual RISC-V ELF, and retains a successful valid control. Changing executable
bytes changes the Type Script hash included in context: the runner derives fresh
statements/proofs for the mutant identity instead of accidentally testing an old
code hash. Within each control/target pair the code identity is fixed.

| Removed check | Target | Observed mutant behavior |
| --- | --- | --- |
| Proof verification call | invalid-proof-permitted-owner | Invalid proof incorrectly accepted; correct owner still signs |
| Creation count zero | create-nonzero | Nonzero initialization incorrectly accepted |
| Capacity equality | capacity-reduced | Correct fresh proof over reduced-capacity context incorrectly accepted |

All three mutations were detected by incorrect acceptance. The harness's nonzero
exit is required but insufficient: the runner checks the targeted result is `Ok`,
and the valid control also succeeds. Build errors/timeouts/unrelated rejections
are failures of the experiment. Baseline binaries and Capsule are never modified.

## Explicit scope and remaining gaps

Update, 7 October 2026: the legitimate creation and update were subsequently
confirmed on public testnet; see [testnet evidence](../evidence/week-15-testnet.md).
The negative matrix remains local VM evidence, not public testnet rejection tests.

This is a bounded deterministic matrix, not exhaustive fuzzing, an audit, or a
production security claim. It does not prove every possible transaction shape or
malformed-byte pattern. CKB consensus checks beyond the testtool harness are
established here for the legitimate locally committed transactions, with the
separate testnet receipts covering the public happy path. Independent review,
non-macOS tooling, multisig/OmniLock, transfer,
withdrawal/recovery/upgrades, batching and arbitrary Noir compatibility are not
validated/supported. Whole-transaction binding is intentionally not implemented.
