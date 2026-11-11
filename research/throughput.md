# R3. Throughput: how many proof checks fit in a block

Status: **spiked on the pinned toolchain; external review not done.** Spike code and exact
command: [`spikes/throughput`](spikes/throughput/README.md). Cycle counts below are from
the pinned toolchain (Rust 1.94.1, macOS ARM64, 11 November 2026) unless marked "1.97.0",
which is an earlier run on a different compiler. The two runs differ by 2% to 3%.

## 1. Problem and definition of done

A voting relay or a note pool has to check many proofs per block. CKB's consensus limit is
3.5B cycles per block (`MAX_BLOCK_CYCLES`, `ckb@v0.210.0` `spec/src/consensus.rs`) and
597,000 bytes. One Groth16 verification costs about 100M cycles today. The target was 100
or more proof checks per block.

| # | Test | State |
| --- | --- | --- |
| D1 | N proofs under one key verified in one script run, N ≥ 100, inside 3.5B cycles, in CKB-VM | Passed: N = 172 |
| D2 | One invalid proof anywhere in the batch is rejected | Passed: 12 of 12 runs pinned, 24 of 24 on 1.97.0. Only the last position was altered |
| D3 | The same on the pinned toolchain | Done |
| D4 | A node accepts, relays and mines a transaction of that size | Not tested |
| D5 | 100 complete ballots (proof, public-vector rebuild, nullifier insertion) in one block | Depends on R2; budget in section 6 |

## 2. What was believed, and what the spike found

| Belief | Result |
| --- | --- |
| "One verification is about 117M cycles" | 96M to 186M depending on the public inputs (R0, 1.97.0). For the tally proofs on the pinned build: 113.5M to 114.9M in this spike, 112.8M to 115.6M in the recorded transactions |
| Separate verification limits a block to about 30 checks | **Held**: 30 tally proofs fit (computed from 113.5M each); 32 small-input proofs fit on 1.97.0 |
| Batching N proofs under one key is much cheaper than N verifications | **Held**: about 79M fixed plus 19.9M per proof, against about 113.5M per proof; 4.6 times cheaper at N = 16 and 5.7 times in the limit |
| 100 or more checks per block are reachable | **Held for verification alone**: 172 proofs in 3,497,943,690 cycles; 175 exceeded the limit |
| A single verification cannot be made cheaper without batching | **Broke**: a batch of one cost 93.3M against 114.9M for `verifier-core` in the same binary (18.8% less). `ark-groth16` computes e(α, β) as its own pairing, with its own final exponentiation, on every call (source: `ark-groth16` 0.5.0 `verifier.rs`); one four-pair product avoids it |

## 3. Prior art

- Small-exponent batch verification: Bellare, Garay, Rabin,
  [Fast Batch Verification for Modular Exponentiation and Digital Signatures](https://eprint.iacr.org/1998/007).
  The check in section 4 is this test applied to the Groth16 pairing equation. (The Zcash
  protocol specification describes the same construction for its Groth16 proofs; that
  text was not re-read for this document.)
- [SnarkPack](https://eprint.iacr.org/2021/529) (Gailly, Maller, Nitulescu): aggregates
  Groth16 proofs into one logarithmic-size proof with a logarithmic-time verifier, reusing
  Groth16 powers-of-tau parameters; the abstract reports 8,192 proofs aggregated in 8.7 s
  and verified in 163 ms. Only the abstract was read for this document.
- [VoteSecure architecture v2.3](https://github.com/psawyerberlin/votesecure/blob/f10e944fc6e4b61156f0823e5e5d24c0a159415e/docs/architecture.md)
  (CKB, design proposal): relayers submit ballots in batches to sharded ballot boxes. It
  uses signatures, not proofs, so its batch sizes do not transfer.
- This repository, `evidence/week-13.md`: an SP1 PLONK proof verified in CKB-VM in
  66,229,968 cycles.

## 4. Options compared and the chosen design

| Option | Checks per block | New trust or setup | Extra work for the relayer | Verdict |
| --- | --- | --- | --- | --- |
| A. One proof per transaction | About 30. Also bounded by the pool: 25 unconfirmed ancestors by default (`ckb.toml`, `max_ancestors_count`), which matters when every transaction spends the previous output of one shared Cell | none | none | Baseline; enough for Battleship and single-writer Cells |
| B. Randomized batch in one script run | 172 | none: same keys, same proofs | Check each proof off-chain first, because one bad proof rejects the whole batch | **Chosen** for shared mode |
| C. SnarkPack aggregation | Not measured. Verifier does a logarithmic number of pairing-product checks | Needs a structured reference string | Runs an aggregator | Not for the grant period; revisit only if more than about 150 per block is needed |
| D. Relayer proves "these N proofs verify" in a zkVM, one proof on chain | 66M cycles whatever N (week 13 measurement) | zkVM circuit and its setup become part of the trust base | Proving time and hardware not measured here | Not for the grant period; the only option whose cost does not grow with N |
| E. Groth16 verification inside a Groth16 circuit | one check | new circuit and ceremony | BN254 is not pairing-friendly to itself; the circuit would be very large (estimate, not measured) | Rejected |

Also adopted, independent of batching: verify a single proof with the four-pair product
(section 2, last row). It is a change to the verifier, not to proofs or keys, and saved
18.8% in the pinned run.

### The batch check

For proofs (A_i, B_i, C_i) with public inputs x_i under one key:

```
Π e(r_i·A_i, B_i) · e(−(Σ r_i)·α, β) · e(−Σ r_i·X_i, γ) · e(−Σ r_i·C_i, δ) = 1
X_i = IC_0 + Σ_j x_ij·IC_j,   so   Σ r_i·X_i = (Σ r_i)·IC_0 + Σ_j (Σ_i r_i·x_ij)·IC_j
```

- N + 3 Miller loops and one final exponentiation.
- r_0 = 1; r_i for i ≥ 1 is the low 128 bits of
  `blake2b(blake2b(key_hash ‖ whole batch) ‖ i)`. Every proof and public input is hashed
  before any challenge exists, so a prover cannot choose a proof after seeing its r_i.
- Soundness: if any single equation fails, the product holds with probability about
  2⁻¹²⁸ over the challenges (the small-exponents argument), in the random-oracle model for
  BLAKE2b.
- Preconditions the script enforces: every point is on the curve and in the right
  subgroup (arkworks checked deserialization, as `verifier-core` does), no point is the
  identity, every public value is below the modulus.
- The public-input side costs n + 1 scalar multiplications for the whole batch instead of
  n per proof.

What batching does **not** give: it says "all N are valid" or nothing. It cannot say which
one is bad, so a relayer that does not pre-check can be made to waste a transaction by one
bad submission.

## 5. Exact interfaces

Spike witness layout (`WitnessArgs.input_type`): `u32 N`, then N × (`u32 length` ‖
`Groth16Witness`). Script args: key data hash (32) ‖ mode (1).

For the generator, batching belongs to shared mode (R0, section 3.8) and to a later
envelope version:

```
table BatchPayload {
    action: byte,
    items:  BytesVec,     // one BindingPayload-style item per proof: its witness publics and its proof
    aux:    BytesVec,     // helper data for effects, one entry per item
}
```

The script rebuilds each item's public vector exactly as for a single proof (same sources,
same context digest per item), feeds all vectors to one batch check, and applies the
effects item by item. A spec does not change to enable batching: `shared = true` actions
are batchable, others are not.

## 6. Measured budgets

| Item | Value | Basis |
| --- | --- | --- |
| Batch verification | 79M + 19.9M per proof (four public inputs, mostly full-width) | spike, pinned |
| Largest batch in a block | 172 proofs, 50,875 transaction bytes | spike, pinned |
| Separate verification | 113.5M to 114.9M per proof | spike, pinned |
| Single proof, four-pair product | 93.3M | spike, pinned |
| Script size | 120,400 bytes | spike, pinned |
| Cycles left per ballot at 100 ballots per block | 3,500M ÷ 100 = 35M per ballot; minus 19.9M and a 0.8M share of the fixed cost leaves about 14.3M for the public-vector rebuild and the nullifier insertion | computed |

The last row is the budget R2 has to meet for the ballot box. If a set insertion in
CKB-VM costs more than about 14M cycles, 100 ballots per block is out of reach with a
single shared set and the design has to shard.

A block's 3.5B cycles are shared with every other transaction on the chain. "172 per
block" means a relay transaction that fills an entire block.

## 7. Pinned tools

As R0, section 10. arkworks 0.5 (`ark-bn254`, `ark-ec`, `ark-ff`, `ark-groth16`,
`ark-serialize`), `groth16-ckb@d64c769`, ckb-std 1.1.0, ckb-hash 1.1.0, ckb-testtool 1.1.1.

## 8. Test plan

1. The spike on the pinned toolchain (D3): `spikes/throughput/run.sh`.
2. Adversarial batches: one bad proof in each position; a proof under another key; a
   duplicated proof (must be accepted by the pairing check and rejected by the nullifier
   rule, not by verification); public value at or above the modulus; identity points;
   N = 0; trailing bytes; N larger than the items present.
3. Differential: for random batches of valid and invalid proofs, batch result equals the
   conjunction of separate results, on the host with the same code (10,000 batches) and in
   CKB-VM (a smaller sample).
4. Challenge derivation: change any byte of any item and require every r_i (i ≥ 1) to
   change.
5. A local node: submit one transaction of about 3.4B cycles and one of about 1B; record
   whether each is accepted to the pool, relayed and committed (D4).

## 9. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| T1 | Spike repeated on the pinned toolchain | Done 11 November 2026: largest N under 3.5B was 172 |
| T2 | Single-product verification proposed to `groth16-ckb` (patch and tests written, section 11) | Upstream integration tests and both recorded matrices pass with the patched verifier on the pinned toolchain; cycles at least 10% lower |
| T3 | Batch verifier as a library crate with the adversarial and differential tests | Test plan items 2 to 4 pass |
| T4 | Node behaviour for large transactions | Test plan item 5 recorded |
| T5 | Batch mode in the generator, with shared mode (R0 milestone M7) | Two voters' proofs in one transaction on a local chain |

## 10. Risks and open questions

| Risk | Handling |
| --- | --- |
| A node's pool treats very large transactions differently. In `ckb@v0.210.0`, `max_tx_verify_cycles` (default 70M) is the threshold above which a transaction goes through the pausable large-cycle verification queue; the cycle ceiling passed to verification on submission is the consensus block limit (source: `tx-pool/src/process.rs`, `verify_queue.rs`). The tally's 115M-cycle transactions were committed on testnet. Behaviour near 3.5B was not tested | T4. A practical batch is likely well below a full block |
| A full-block transaction waits for a miner with an empty block template | Target batches of 32 to 64 (0.7B to 1.3B cycles) in normal operation |
| The same library verified the same proof in 104.9M to 114.9M cycles across four binaries and two compilers; the cause of the spread is unexplained | Quote per-binary numbers; do not quote one number for "a verification" |
| Batch failure hides the offender; anyone can submit invalid or conflicting items for free | Relayer rule in review item 2 (section 12) |
| The system secp256k1 Lock rejects any witness over 32,768 bytes among those it hashes (its own group's, and those beyond the input count); a 172-proof payload is about 50 KB | The batch payload sits in the application input's witness, which a fee payer's Lock does not read (R4, section 5); test in R4's plan |
| Challenges of 128 bits | Standard for this test; 2⁻¹²⁸ per attempt, and each attempt needs new valid-looking proofs |

Open: whether to upstream the four-pair verification to `groth16-ckb` or to carry it in a
`noir-ckb` crate; whether keys should store e(α, β) (384 more bytes per key Cell) to drop
one more Miller loop.

## 11. Proposed upstream: the single-product check in `verifier-core`

The saving for one proof does not need batching. It was written as a standalone change to
`groth16-ckb`'s `verifier-core`, with a new host test, for proposal to its maintainer:
[`upstream/groth16-ckb-single-product`](upstream/groth16-ckb-single-product/README.md).

| Same recorded proof through a script linking `verifier-core` | Before | After |
| --- | --- | --- |
| Tally update | 104,860,094 | 85,326,519 |
| Tally create | 102,287,071 | 82,706,150 |
| Counter update | 99,755,219 | 80,217,270 |

These three rows are from Rust 1.97.0. On the pinned toolchain, `groth16-ckb`'s own
benchmark went from 99,843,490 to 79,186,128 cycles at one public input and from
118,483,349 to 97,832,285 at 64: a constant saving of about 20.66M cycles (17.4% to
20.7%). On the patched tree, on the pinned toolchain, the repository's 26 differential
tests against arkworks (and the 1,000-sample variant), 2 property tests, 8 CKB-VM
integration tests and the 4 new tests passed (11 November 2026).

## 12. External review

Not done. Items a reviewer must examine, recorded so they are not lost:

1. **How the batch coefficients are derived.** In
   `spikes/throughput/contracts/crates/verify-batch/src/main.rs`:
   - line 37: `blob` is the whole `WitnessArgs.input_type` field: the count N, then for
     each item its length and its `Groth16Witness` payload (proof and public inputs);
   - lines 82 to 86: `seed = blake2b_256(key_data_hash ‖ blob)` with CKB's BLAKE2b
     personalization, computed once, after every item has been decoded and before any
     coefficient exists;
   - lines 98 to 107: `r_0 = 1`; for i ≥ 1, `r_i` is the low 128 bits (little-endian) of
     `blake2b_256(seed ‖ i as u32 LE)`;
   - lines 127 to 135: the Miller loops and the single final exponentiation.

   This is a Fiat-Shamir transcript over the key hash and all proofs and public inputs,
   fixed before the coefficients are drawn. What the transcript does **not** contain, and a
   reviewer should judge: the key's bytes (only their hash, which the script also uses to
   find the key Cell), the script hash, the network, and any transaction field outside the
   witness. Also to judge: `r_0 = 1`; 128-bit coefficients; whether hashing the raw blob
   (with its length prefixes) admits two different parses of one byte string; and that the
   coefficients are reduced from 128 bits, so no modular bias arises.
2. **All-or-nothing batches and relayer denial of service.** The check says "all valid" or
   nothing and cannot name the offender. Cases:
   - *Invalid proof submitted to a relayer.* It costs the sender nothing. A relayer that
     batches it loses the whole batch's work.
   - *Two valid ballots with the same nullifier*, sent to one relayer or to two. The
     second insertion fails and the batch with it.
   - *A nullifier inserted by another transaction* between batch assembly and inclusion.
   - *A ballot proved against a voter root or ring entry that is no longer accepted.*

   On CKB a transaction whose script fails is not committed and pays no fee, so the loss is
   the relayer's computation and delay, not CKB. Mitigation rule for the relayer
   specification: (a) verify every proof on its own off-chain before admitting it;
   (b) admit at most one pending item per nullifier and check it against the current set;
   (c) re-check every item against the latest state immediately before sending, and
   rebuild the batch without the items that fail; (d) on an on-chain rejection, re-verify
   the items singly and drop the failures; never resend a batch unchanged; (e) bound the
   work spent per submitter connection. None of this was built or tested.
3. **Only the last proof was altered** in the rejection runs. A bad proof in every
   position, a proof under another key, a duplicated proof and malformed batches are in
   the test plan (section 8) and were not run.
