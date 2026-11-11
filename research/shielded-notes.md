# R2. Shielded notes: commitments, membership, nullifiers, and shared state

Status: **spiked; design chosen; external review not done.** Spike code and exact command:
[`spikes/shielded-notes`](spikes/shielded-notes/README.md). Constraint counts are from the
pinned Nargo and backend. Cycle counts are from Rust 1.97.0, not the pinned toolchain;
earlier spikes put the pinned build 2% to 3.5% above it.

## 1. Problem and definition of done

The tally hides a value but every update of one Cell is linkable (private tally spec,
section 7). Unlinkable transfers need notes: a commitment per note in a tree, a proof of
membership that does not say which leaf, and a nullifier that makes each note spendable
once. On CKB this state has to live in Cells, and a Cell has one writer at a time.

| # | Test | State |
| --- | --- | --- |
| D1 | Constraint counts for membership at depths 16, 20, 32 from the real backend | Done (spike) |
| D2 | CKB-VM cycles for sparse-tree absence and insertion, and for a Poseidon2 tree append | Done (spike), not on the pinned toolchain |
| D3 | Shared-state designs compared on throughput, contention and cost, with one chosen | Done (section 4) |
| D4 | A pool on a local chain: deposit, transfer, withdraw; a double spend, a forged root and a replayed proof are rejected | Not built |
| D5 | Two users' proofs made against the same pool state both land without either proving again | Not built |
| D6 | Reviewed note scheme with test vectors from two implementations | Not done |

## 2. What was measured

| Item | Value | Basis |
| --- | --- | --- |
| One tree level in a circuit | 716 constraints | spike |
| Membership at depth 16 / 20 / 32 | 11,459 / 14,323 / 22,915 constraints | spike |
| Spend one note at depth 16 / 20 / 32 | 14,619 / 17,483 / 26,075 | spike |
| Join-split 2-in 2-out at depth 16 / 20 / 32 | 32,134 / 37,862 / 55,046 | spike |
| Poseidon2 permutation in CKB-VM | 394,000 cycles | spike; port checked against Noir's test vector in the VM |
| Tree append, one leaf, depth 20 / 32 | 7.92M / 12.67M cycles | spike |
| Tree append, 64 leaves, root once, depth 20 / 32 | 0.51M / 0.59M cycles per leaf | spike |
| Nullifier set (BLAKE2b sparse Merkle tree): absent-then-insert, one key | 0.93M to 1.27M cycles for trees of 0 to 10,000 keys | spike |
| The same, 32 keys in one proof | 1.12M per key | spike |
| Set proof size | 564 bytes for one key, 306 per key for 32 (10,000-key tree) | spike |

Consequences:

- **Script-side effects are affordable.** R3 left about 14.3M cycles per ballot at 100
  ballots per block. A nullifier insertion costs about 1.2M. The ballot box fits with a
  wide margin; shared mode (R0, section 3.8) does not need the fallback of putting the
  update in the circuit.
- **Hashing the commitment tree in the script is the expensive part**, and it is cheap
  only in batches: 7.9M for one leaf at depth 20, 0.5M per leaf for 64.
- **A join-split needs a power-of-tau file of 2^16** (37,862 or 55,046 constraints); the
  tally needed 2^12.

## 3. Prior art

| System | Commitment tree | Nullifier | Binding of the spend | Taken from it |
| --- | --- | --- | --- | --- |
| [Tornado Cash](https://github.com/tornadocash/tornado-core/tree/1ef6a263ac6a0e476d063fcb269a9df65a1bd56a) | On-chain incremental tree, MiMC, fewer than 32 levels, last 30 roots accepted (`MerkleTreeWithHistory.sol`) | Hash of a random secret in the note; the contract also refuses a repeated commitment (`Tornado.sol`) | Recipient, relayer and fee as public inputs | The root ring; binding payout facts through the proof |
| [Tornado Nova](https://github.com/tornadocash/tornado-nova) | Same idea, 2-in 2-out with a public amount | Position-dependent | | The join-split shape with one signed public amount (repository confirmed to exist; not re-read) |
| Zcash Sapling and Orchard | Depth-32 tree, any past root (anchor) | Depends on the note's position, so equal notes get different nullifiers | A signature over the transaction hash under a key proven in the circuit | Position-dependent nullifier (from memory of the protocol specification; not re-read) |
| [Semaphore](https://github.com/semaphore-protocol/semaphore/blob/dbab5553c486a09d5e1042e5271e3316224cc176/packages/circuits/src/semaphore.circom) | Off-chain group tree, root on chain | `Poseidon(scope, secret)` | `message` bound in the circuit | The ballot box: scope = election |
| Aztec | Notes and nullifiers in protocol trees, a kernel circuit per transaction | | | Not applicable: the trees are part of the chain's own state (from memory; not re-read) |
| [nervosnetwork/sparse-merkle-tree](https://github.com/nervosnetwork/sparse-merkle-tree) v0.6.1 | | A 256-level BLAKE2b tree with compressed proofs, usable in `no_std` | | Used as the nullifier set |
| [VoteSecure v2.3](https://github.com/psawyerberlin/votesecure/blob/f10e944fc6e4b61156f0823e5e5d24c0a159415e/docs/architecture.md) (CKB, design) | | | | Sharded ballot boxes and relay batches as the answer to contention |

## 4. Shared-state designs compared

CKB facts that decide this: a block holds 3.5B cycles; a Cell is consumed by one
transaction; the pool accepts at most 25 unconfirmed ancestors by default
(`ckb@v0.210.0`, `resource/ckb.toml`), which caps a chain of transactions each spending
the previous output of the same Cell.

Per-operation costs used below (measured parts, summed; the sums are estimates):
join-split verified alone about 120M cycles (10 public inputs, R0 formula plus 3.5%);
in a batch 19.9M (R3); two nullifier insertions 2.4M; two leaves appended 8.3M alone or
about 1.0M in a batch of 32 operations.

| | A. One serialized Cell | B. K shards, each a full pool | C. A Cell per note plus an accumulator Cell |
| --- | --- | --- | --- |
| State | One Cell: tree frontier, ring of roots, nullifier root, capacity = pool value | K such Cells | A Cell per unabsorbed note; one accumulator Cell; one nullifier Cell |
| Transfers per block, one per transaction | about 26 by cycles (131M each), and at most about 26 in a pending chain | The same 26 in total: the block's cycles are shared | The same; spends still meet at the nullifier set and the accumulator |
| Transfers per block, batched by a relayer | about 145 (79M + 23.3M each) | The same in total | The same |
| Contention without a relayer | Every user races for one OutPoint; losers rebuild the transaction but, in shared mode, do not prove again | Divided by K | Deposits do not contend; spends do |
| Anonymity set | All notes | Divided by K; moving between shards is a public withdrawal and deposit | All notes, but a note is spendable only after someone absorbs it into the accumulator |
| Capacity | about 2,200 CKB once (depth 32, ring of 32); nothing per note | K times that | at least 140 CKB locked per note until absorbed (computed: 8 + 33 + 66 + 33 bytes) |
| Extra moving parts | A relayer for batching (anyone can be one) | Shard selection, cross-shard transfers | An absorber role, a second proof or script-side hashing for absorption, a waiting period |

**Chosen: A, with relayer batching.** The block's cycle limit, not the number of Cells,
is what bounds throughput, and one Cell with batching already reaches it. B divides the
anonymity set to solve a contention problem that shared-mode binding plus a relayer
solves without that cost. C adds a role, a delay and locked capacity, and parallelizes
only deposits.

Sharding stays the right tool for one case: ballot boxes with several independent
relayers. There the shards are not an anonymity loss if the nullifier set is what is
sharded (by the first bits of the nullifier, which are uniformly random) and the voter
tree stays one. That is VoteSecure's shape. It is specified for the ballot box as a later
option, not built in the grant period.

Failure modes of A, found by analysis and not yet by experiment:

- **A full pending chain.** Without batching, the 26th transaction in a chain is refused by
  default pool policy until earlier ones confirm.
- **Stale roots.** A proof names a root; with a ring of R roots it survives R − 1 later
  updates. With one batch per block and R = 32 a user has about 32 blocks to be included,
  otherwise the proof must be made again. R is a spec constant; 128 costs 3 KB of Cell data.
- **A relayer that stops.** Anyone can send a batch of one; the script does not know
  relayers. Liveness needs one honest sender, not a trusted one.
- **Withdrawals below a Cell's minimum** (61 CKB for a plain secp256k1 Cell) are impossible.
- **Tree exhaustion.** Depth 20 holds 1,048,576 leaves, 524,288 join-splits. A full tree
  freezes deposits and transfers. Depth 32 costs 17,184 more constraints per join-split
  and about 4.8M more cycles per root computation.

## 5. The chosen design

### 5.1 Notes

```
owner      = H2(TAG_OWNER, secret)
commitment = H2(H3(TAG_NOTE, value, owner), blinding)        leaf of the tree; never 0
nullifier  = H3(TAG_NULLIFIER, secret, position)             position = leaf index
```

H2 and H3 are Poseidon2 as in `noir-lang/poseidon` (state width 4, one permutation, at
most 3 inputs per call, as the tally requires). Tags are the integers of distinct ASCII
strings under a `noir-ckb/shielded-pool/v1/` prefix, as in the tally spec.

- **Why the position.** With a nullifier derived only from the note's content, a sender
  can create two identical notes for a recipient; they share a nullifier, so the second
  is unspendable. Tornado prevents this in the contract by refusing a repeated
  commitment. A CKB script cannot search the tree for a repeat, so the nullifier takes
  the leaf position, which the circuit already has as the path bits (the Zcash approach).
- **What a sender learns.** The sender knows `owner`, `value`, `blinding` and the
  commitment, not `secret`, so cannot compute the nullifier or see the spend.
- **Values** are 64-bit shannons; every value is range-checked, so the balance equation
  cannot wrap in the field.
- **Not designed here:** how the recipient learns `value` and `blinding`. Zcash encrypts
  them to the recipient inside the transaction. For the grant period the options are an
  off-chain hand-over or an unproven encrypted blob in the witness; both are open
  (section 10).

### 5.2 Circuit (join-split)

Private: for each of two inputs `secret`, `value`, `blinding`, path siblings and bits; for
each of two outputs `value`, `owner`, `blinding`.
Public, in this order: `root`, `nullifier_0`, `nullifier_1`, `commitment_0`, `commitment_1`,
`public_in`, `public_out`, `fee`, `ctx_lo`, `ctx_hi`.

Constraints: each input note opens under `root` at its position and yields its nullifier;
each output commitment is well formed and non-zero; all values fit 64 bits;
`in_0 + in_1 + public_in = out_0 + out_1 + public_out + fee`; the two nullifiers differ;
a zero-value input skips the membership check (dummy input); context halves fit 128 bits.

Measured without the last three rules and with the content-derived nullifier: 37,862
constraints at depth 20, 55,046 at depth 32. The position-derived nullifier adds about one
constraint per level; the dummy rule adds a few per input (estimate).

### 5.3 Cell

| Field | Bytes | Meaning |
| --- | --- | --- |
| version | 1 | constant 1 |
| leaves | 4 | number of commitments appended |
| frontier | 32 × depth | one node per level of the append-only tree |
| roots | 32 × R | ring of the last R roots; the proof's `root` must be one of them |
| nullifiers | 32 | root of the nullifier set; all-zero when empty |

Lock: the pinned always-success guard, as in the tally. Capacity: the pool's value plus the
Cell's own occupied capacity. Type args: version and Type ID.

### 5.4 Effects, now with fixed encodings

| Effect | Rule the script enforces | Helper data |
| --- | --- | --- |
| `set-insert` | The key is absent under `in.nullifiers`; `out.nullifiers` is the root with the key present (value `0x01` followed by 31 zero bytes). Tree: `sparse-merkle-tree` 0.6.1 rules, BLAKE2b with CKB's personalization | One compiled proof for all keys of the transaction |
| `tree-append` | `out.frontier`, `out.leaves` and the newest entry of `out.roots` are the result of appending the leaves, in order, to the input tree; Poseidon2 as in section 5.1; older ring entries shift | none |
| `capacity-add`, `capacity-sub` | `out.capacity = in.capacity ± value`, checked without overflow; the result must cover the Cell's occupied capacity | none |
| `add` | `out.f = in.f + value`, no overflow | none |

The R0 specs can now replace "free, to be fixed by R2" with constants: the empty
nullifier root is 32 zero bytes, and the empty frontier and first root are the hashes of
empty subtrees.

### 5.5 Binding

Shared mode (R0, section 3.8): the context holds the tag, network, profile, script hash,
pool id, action, both nullifiers, both commitments, `public_in` or `public_out`, `fee`,
and for a withdrawal the payout output's Lock hash, Type hash and data hash. It holds no
OutPoint. Replay is stopped by the nullifiers; a third party cannot redirect a withdrawal
because the payout is in the digest.

The miner fee can come out of the pool (`capacity-sub` by the proven `fee`), so a relayer
needs no CKB of its own and the user needs no visible fee Cell. This removes the fee-payer
leak listed in the tally's privacy section. Untested.

## 6. Budgets

| Item | Budget | Basis |
| --- | --- | --- |
| Join-split circuit, depth 32 | 56,000 constraints; setup with a 2^16 powers-of-tau file | spike, rounded up |
| Vote circuit (membership at depth 20, nullifier, choice) | 18,000 constraints | spike (spend-one-note) |
| One join-split in its own transaction | about 131M cycles | estimate from measured parts |
| One join-split inside a batch | about 23.3M cycles | estimate from measured parts |
| One ballot inside a batch | about 21.1M cycles (19.9M + 1.2M) | estimate from measured parts |
| Ballots per block | about 160 | computed from the row above and R3's fixed cost |
| Witness bytes per join-split | 482 payload + about 1,100 set proof, less in a batch | computed and spike |
| Pool Cell | about 2,200 CKB at depth 32 with a ring of 32 | computed |

## 7. Pinned tools

Nargo 1.0.0-beta.18, `noir-lang/poseidon` v0.2.6 (or the 1.0 pair from R1: v0.4.0),
backend `828025f`, snarkjs 0.7.5, `sparse-merkle-tree` 0.6.1, arkworks 0.5, ckb-std 1.1.0,
ckb-hash 1.1.0, ckb-testtool 1.1.1. The Poseidon2 constants in the script are generated
from Noir's solver at v1.0.0-beta.19.

## 8. Test plan

1. Cross-implementation vectors: commitment, nullifier and tree root for fixed inputs from
   Noir execution, from the script's Poseidon2 in CKB-VM, and from a third implementation.
2. Circuit tests: wrong secret, wrong path, wrong position, value above 64 bits, balance
   off by one, equal nullifiers, zero commitment, dummy input with non-zero value.
3. Script matrix, generated (R0 section 8) plus: nullifier already in the set; nullifier
   set proof for another root; root not in the ring; root in the ring after R − 1 updates
   (accept) and after R (reject); appended leaves in the wrong order; `leaves` not
   advanced; ring not rotated; capacity not moved by exactly the public amounts; payout
   output altered; pool left below its occupied capacity; tree full.
4. Concurrency (D5): two proofs against the same state, sent in either order and in one
   batch.
5. Privacy checks: two deposits and withdrawals by different users, then confirm from
   chain data alone that neither nullifier can be matched to a commitment.
6. Leak scans of client files, as for the tally.

## 9. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| S1 | Spike part 1 on the pinned toolchain | `spikes/shielded-notes/run.sh` output recorded |
| S2 | Poseidon2 and tree-append as a script library with vectors | Test plan item 1 |
| S3 | Effects in the generator (`set-insert`, `tree-append`, capacity) | Generated ballot box passes its matrix; two votes against one state both land |
| S4 | Note scheme reviewed and frozen | Written review; vectors published |
| S5 | Join-split circuit and development setup | Test plan item 2; constraint count within the budget |
| S6 | Pool on a local chain | D4 and D5 |
| S7 | Ceremony and testnet pool, only after S4 and an external look at S6 | Public transcript; a deposit, a transfer and a withdrawal by two outside accounts |

The ballot box needs S1 to S3 only. It is the smaller deliverable and exercises every
shared-mode mechanism; the pool adds the note scheme and a larger ceremony.

## 10. Risks and open questions

| Risk | Handling |
| --- | --- |
| The note scheme above was designed in this document and reviewed by nobody | S4 before any deployment; until then it is a draft |
| Note delivery to the recipient is not designed | Decide before S5: off-chain hand-over, or encrypted note data in the witness with a published scheme |
| A small anonymity set gives little privacy whatever the cryptography | State the set size in the client; fixed denominations are an option if amounts leak identity |
| Public amounts on deposit and withdrawal link the two when they are unusual | Same |
| Poseidon2 in the script must match Noir's exactly, forever | Constants generated from Noir's source; vectors in CI; a library change in Noir is a new profile |
| The Poseidon2 library pinned for beta.18 has a known fault for more than 3 inputs | Every call takes at most 3; the tally's static test is reused |
| Cycles measured off the pinned toolchain | S1 |
| A pool is a target with real value; this is pre-audit software | Testnet only, as the rest of the project |

Open: ring size; depth 20 or 32 for the first pool; whether the first shielded
deliverable should be the ballot box alone, with the pool specified and left for a
second grant.

## 11. External review

Not done.
