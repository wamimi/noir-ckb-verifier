# Owned counter v1 — application specification, revision 2

Status: **implemented, locally validated, and demonstrated on testnet**. See
[Week 15 evidence](../evidence/week-15.md) and the
[executed requirement matrix](owned-counter-test-matrix.md). The confirmed public
lifecycle is recorded in [testnet evidence](../evidence/week-15-testnet.md).
Implementation started from toolkit `b155300c8145916a485696bf461e36f055bb5135`.
The existing Capsule and its artifacts remain
historical regressions. [Feasibility evidence](../evidence/week-15-phase1.md)
is for the existing verifier, not this application.

## Architecture

Implement one **owner-controlled public counter**, profile
`noir-ckb/owned-counter/v1`, with a conventional secp256k1 ownership Lock and a
new application Type that directly links the pinned `verifier-core` and
`wire-decode`. Create at zero, update by exactly one, preserve owner and capacity,
and reject destruction and multi-instance transactions. Pin the circuit-specific
VK commitment in the executable, not user-selectable args. Use selected-operation
binding, not the whole raw transaction. No Spawn/IPC, private-state scheme,
transfer, recovery, upgrade, batching, arbitrary circuit generator or game.

This is an honest lifecycle/proof-enforcement example: its counter and relation
are public and it needs no private circuit parameter. A proof of increment is
more expensive than a direct arithmetic check; the purpose is to exercise the
Noir-to-CKB application boundary. It is not a privacy or efficiency claim.

## Circuit and policy ownership

Four scalar public Field parameters, in this exact order:

| Slot | ABI name | Meaning and source |
| --- | --- | --- |
| 0 | old_count | u64 from the consumed application Cell data |
| 1 | new_count | u64 from the successor data |
| 2 | context_lo | First 16 digest bytes interpreted little-endian as u128 |
| 3 | context_hi | Last 16 digest bytes interpreted little-endian as u128 |

No returns, arrays, structs or private parameters. Circuit constraints require
old_count and new_count to fit u64, `new_count = old_count + 1` in Fr, and both
context limbs to fit u128. With u64 ranges, the equality rejects overflow rather
than wrapping. Range lowering and the exact four-input binding must pass fresh
compiler/R1CS/proof tests; prior two-input probe results are not substituted for
those gates. The circuit does not recompute the context hash: the Type derives
it from CKB and compares all four public values before invoking verification.

Fresh development setup is generated for this circuit, checked against its R1CS,
and its canonical Molecule VK data hash is compiled into the application Type.
Setup completes before Type compilation; the circuit has no constant depending
on its future executable hash, avoiding a build/setup cycle. The release
manifest pins circuit/compiler/backend, R1CS, setup provenance, VK and Type ELF.
Replacing the VK requires a different Type executable/code hash; a transaction
creator cannot admit an arbitrary VK or weaker relation through args/witness.
No production ceremony or setup security is claimed. Public demonstration entropy
must be labeled; operator secrets/keys must never be logged or committed.

## Cell layout and uniqueness

Application Type args: exactly `0x01 || instance_id[32]` (33 bytes).
Application data: exactly `0x01 || count:u64_le` (9 bytes).
These version bytes belong to this new Type/profile namespace; they do not
reinterpret Capsule v1 or reuse its replay_domain. Unknown versions/lengths reject.

Use the full 32-byte CKB Type ID derivation at initialization:
`instance_id = blake2b_ckb(first_transaction_input.as_slice() || output_index:u64_le)`.
The input is the Molecule CellInput (including since), not just its OutPoint;
output_index is the actual absolute application output position. Check all 32
bytes. CKB input consumption plus collision resistance gives instance uniqueness
within this code/profile. Script identity includes the executable identity and
args; equal human-readable IDs under different code are not the same application.

In addition to one member per exact Type group, count all transaction Cells whose
Type has this application's code_hash and hash_type, regardless of args. Creation
allows zero such inputs and exactly one output; update requires one input and one
output with the exact same Type Script. This rejects two different instance IDs
batched under the same application code, not merely duplicate group members.
Unrelated application types and ordinary funding/change Cells are outside this
count. No automatic sorting or output-0 assumption is allowed.

## Lifecycle, ownership and capacity

| Operation | Acceptance rule |
| --- | --- |
| Create | Unique Type ID; one application output; count exactly zero; supported owner Lock; first funding input has that same Lock; enough occupied capacity under CKB consensus. No initialization proof: every initial-state fact is public and checked directly |
| Update | One consumed Cell and exact-Type successor; canonical state; same complete Lock; same capacity; four public values match the actual operation; proof verifies under the executable-pinned VK; owner Lock authorization succeeds |
| Destroy | Reject explicitly, including an empty successor group. The Type ID helper permits burning, so the application must add its own rejection |

The supported owner is standard `secp256k1_blake160_sighash_all` with a 20-byte
owner identifier. The build/deployment profile pins its Script code_hash,
hash_type and executable data hash for the selected chain. The Type admits only
that Lock template, preserves its complete Script, and authenticates the actual
resolved code bytes. For Type-hash resolution, match the code Cell's Type hash
and require its data hash to equal the pinned executable hash; reject ambiguous
matches. Neither template nor verification policy is creator-selectable in args.
The owner identifier is selectable at creation and immutable afterwards.

Creation requires the first consumed funding Cell to use the output owner Lock,
so a legitimate initialization includes that owner's signature. Updates require
the input Lock's signature independently of the proof. The Type does not verify
signatures twice. Local node tests must demonstrate unsigned/wrong-key rejection
and a real signed success, not substitute always-success for ownership.

Run inexpensive shape, state, supported-owner admission, ownership continuity,
capacity, and context checks before expensive proof verification. A mandatory-
verification negative uses an invalid proof under an otherwise permitted standard
owner configuration and must reach the proof-verification failure. This isolates
the proof requirement without weakening or delaying admission.

Unsupported always-success Locks are tested separately and rejected by admission,
including when supplied with a valid proof. Always-success provides no owner
authorization; an injected synthetic Cell is not a legitimate owned lifecycle.
No diagnostic requires pairing to run before an inexpensive admission failure.

Initial capacity may be chosen above the consensus occupied-capacity minimum;
every update preserves it exactly. Fees come from separate ordinary Cells.
There is no withdrawal, close, recovery or transfer path in this version, including
at the terminal u64 maximum. Capacity therefore remains in the application Cell.
Code/VK Cells need a retention policy for liveness, not a mutable upgrade policy.

## Canonical selected-operation context

Define H as 32-byte Blake2b with personalization `ckb-default-hash`.
`profile_id = H(ASCII("noir-ckb/owned-counter/v1"))`.
`network_domain[32]` is the genesis-hash value fixed by the build profile.
The client checks actual RPC genesis against it. This is explicit domain
separation, not a claim that a CKB script can intrinsically detect its host chain
or prevent an identical-history clone from reusing identical artifacts.

Digest preimage is the following concatenation, in order, without separators,
sorting, padding, or implicit numeric conversions:

| Order | Bytes | Source |
| --- | --- | --- |
| 1 | ASCII `noir-ckb/owned-counter/context/v1` followed by byte 0 | Fixed domain tag |
| 2 | 32 | Compiled network_domain |
| 3 | 32 | Fixed profile_id |
| 4 | 32 | Current Type Script hash loaded from CKB |
| 5 | 32 | instance_id from validated args |
| 6 | 1, value 1 | Fixed UPDATE action |
| 7 | 36 | GroupInput 0 previous_output Molecule OutPoint: tx hash bytes then u32_le index |
| 8 | 9 | Complete canonical old application data |
| 9 | 9 | Complete canonical successor data |
| 10 | 32 | Successor complete Lock Script hash |
| 11 | 8 | Successor capacity, u64_le shannons |

Hash the exact preimage with H. Encode digest[0..16] and digest[16..32] as separate
u128 little-endian integers, each zero-extended to a canonical 32-byte Fr encoding.
This loses no digest bits and performs no modular reduction. Scalars old/new are
zero-extended u64_le. The public vector decoder must accept exactly four elements.
The input capacity/owner are covered by explicit equality rules with the successor;
those rules remain mandatory even though the digest includes successor values.

The Type compares supplied public bytes with this derived vector (script-side
binding), then passes the derived vector to `verifier_core::verify` with the proof
and authenticated VK (cryptographic binding). A mutation that skips the supplied-
vector comparison may still be rejected by the pairing check; such a result
must not be reported as an incorrect-acceptance mutation detection. Test the two
boundaries separately and choose load-bearing mutations accordingly.

Excluded from the proof context: unrelated fee inputs/change outputs, their data
and capacities, absolute application position on updates, input since, headers,
transaction version, dependency ordering and witness signatures. Other CKB rules
and signatures still apply. Changes to these excluded fields can preserve the
proof only if shape and all application policies remain valid; a raw transaction
change always requires owner signatures to be regenerated. Changing covered fields
requires re-derivation and a fresh proof. Init input/output positions are fixed
before computing Type ID. Dependencies must still resolve to the pinned bytes.

## Witness, verifier and upgrade policy

Keep the existing version-1 Groth16 Molecule proof/VK codec at verifier pin
`d64c769ffe2d2edb5eb308dc59058efda77c2f83`; the **application statement profile**
is new. VK data comes from exactly one resolved CellDep matching the compiled
hash; missing, substituted or duplicate matches reject. The Type calls the
`no_std` verifier library directly, not the generic entrypoint that permits
unrestricted creation and accepts a VK commitment from script args.

Update proof + supplied four public scalars occupy `WitnessArgs.input_type` at
application GroupInput 0's absolute witness index. Conventional Lock signatures
occupy `WitnessArgs.lock` at their own Lock group leader. Multiple fee inputs can
share the owner Lock; do not copy Capsule's one-Lock-input restriction. Transaction
builders preserve all other witness fields. No proof is required on creation;
there is no input application group there. `output_type` is not a proof carrier.
Missing, truncated, trailing, noncanonical, wrong-version or wrong-count payloads
reject. Bound exact profile payload sizes before heap allocation. Supported shape
limits: at most 64 transaction inputs, 64 outputs and 64 resolved dependencies.

Resolve the new Type executable by **data hash with hash_type Data1** (CKB-VM v1),
not an upgradeable Type hash. Pin and verify actual ELF bytes. There is no separate
verifier child identity: its code is linked into and authenticated by this ELF.
Application code, VK or ownership-template changes create a new profile/artifact;
old Cells cannot migrate to it. Deploying identical bytes at another dependency
OutPoint is compatible with data-hash resolution and is not an upgrade.

## Requirement-to-test matrix (execution linked above)

| Requirement | Required tests and distinction |
| --- | --- |
| Real initialization | Signed local-node create at zero; committed transaction and exact live Cell checks; invalid state/version/Type ID reject without proof |
| Identity uniqueness | Duplicate output; changed ID on update; reuse initialization ID with another first input/output index; two distinct instances in one tx reject |
| Owned proof-enforced update | Real secp signature + fresh proof accepts; absent/wrong signature rejects independently; invalid proof rejects with canonical supplied vector |
| Verifier admission | Wrong/missing/duplicate VK; supplied weaker VK and arbitrary args cannot change executable-pinned policy; wrong resolved owner code rejects |
| Mandatory proof and unsupported owners | Invalid proof under a permitted signed owner rejects at verification; always-success independently rejects owner admission; it cannot initialize this application |
| Input-specific replay | Old supplied vector at another OutPoint fails context comparison; correctly recomputed vector for that OutPoint with old proof fails pairing; fresh proof for the second context accepts |
| Intended operation | Wrong successor state with old supplied values fails comparison; correctly recomputed different valid increment with old proof fails pairing; new proof succeeds |
| Ownership/capacity | Changed owner; reduced/increased application capacity; valid fresh proofs for otherwise well-formed candidate statements must not override Type policies |
| Witness ownership | Missing, malformed, wrong field, wrong absolute index; nonzero application input index; ordinary same-owner fee input and preserved Lock witness |
| Shapes/lifecycle | Duplicate group and distinct-ID groups; create+update mixture; destruction; resource-bound overflow reject |
| Permitted exclusions | Deterministic code identities; adjust only unrelated funding/change/since/dependency order; reuse proof with valid regenerated signatures; accept only permitted changes |
| Freshness/ranges | Counter maximum overflow; out-of-range and reordered public values; exact new circuit/context limb proof-binding tests |

Planned isolated RISC-V mutations: skip proof verification; skip creation's
zero-state check; skip capacity equality. Each gets a passing unmodified baseline,
a passing valid control for the mutant, and a targeted transaction that the mutant
incorrectly accepts. For capacity, generate a correct proof over the changed
capacity first so pairing does not mask the missing policy. Compilation failures,
timeouts and unrelated error codes do not count. Additional mutations need a
specific acceptance witness; do not infer detection merely from a failed test.

## Implementation and operator gates

The circuit/Type/client use a separate profile; Capsule remains unchanged.
CLI pin/adapter/manifest facilities are reused, with setup separated from
per-operation proving and public values derived from live Cells.
The implementation adds the fixed `counter` command family; exact implemented
commands and prerequisites are in the [quickstart](owned-counter-quickstart.md).
The documented wallet interface uses pinned ckb-cli tooling and separately
reviewed preparation, signing, submission and confirmation steps.

Exact-profile host/VM/mutation checks, signed local-node initialization/update,
and a same-machine fresh-directory reproduction are recorded in the evidence.
The separate testnet evidence records confirmed public transactions. No
independent reproduction or production-readiness claim follows from these results.

Testnet proceeds only with operator approval, in separate checked batches:
preflight (revision/artifacts/genesis/address/tools/funding), dependency deployment,
initialization, prove/update, then receipts and Cell checks. Distinguish locked
capacity from fees. Operator signs; never request keys or inspect personal wallets.
Before a retry, resolve any previous broadcast's status. Invalid cases stay local
or use dry-run. A hash or successful process exit is not confirmation. Record
implemented, locally validated, ready for operator execution, submitted/unconfirmed
and confirmed statuses independently. Each deployment requires explicit operator review before signing or broadcasting.
