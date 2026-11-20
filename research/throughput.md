# R3. Throughput: how many proof checks fit in a block

Status: **spiked on the pinned toolchain; one external review recorded in section 12.** The script and harness were changed after that review and the changed versions were run on Rust 1.97.0 only; the pinned numbers below are from the version before the review. Spike code and exact
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
| D1 | N proofs under one key verified in one script run, N ≥ 100, inside 3.5B cycles, in CKB-VM | Passed in a script-only fixture: 172 repeated proof checks (two recorded proofs alternating). Not a transaction a node would relay |
| D2 | One invalid proof anywhere in the batch is rejected | Shown at N = 4 for every position, with exit code 51 after an accepted control, in both modes (1.97.0, after the review). In the size sweep the last public input was altered: 18 rejections with exit code 51 after an accepted control, 2 not shown because the valid batch exceeds the cycle limit, 8 separate-mode runs not made (1.97.0). The pinned run of 11 November used the earlier harness, which did not record why a run failed: there the altered batch failed at the 10 sizes whose valid batch was accepted, and at 5 sizes in separate mode. The earlier "12 of 12" and "24 of 24" counted cycle-limited and unexecuted runs as rejections |
| D3 | The same on the pinned toolchain | Done |
| D4 | A node accepts, relays and mines a transaction of that size | Not tested |
| D5 | 100 complete ballots (proof, public-vector rebuild, nullifier insertion) in one block | Depends on R2; budget in section 6 |

## 2. What was believed, and what the spike found

| Belief | Result |
| --- | --- |
| "One verification is about 117M cycles" | 96M to 186M depending on the public inputs (R0, 1.97.0). For the tally proofs on the pinned build: 113.5M to 114.9M in this spike, 112.8M to 115.6M in the recorded transactions |
| Separate verification limits a block to about 30 checks | **Held**: 30 tally proofs fit (computed from 113.5M each); 32 small-input proofs fit on 1.97.0 |
| Batching N proofs under one key is much cheaper than N verifications | **Held**: about 79M fixed plus 19.9M per proof, against about 113.5M per proof; 4.6 times cheaper at N = 16 and 5.7 times in the limit |
| 100 or more checks per block are reachable | **Held for verification alone, in a script-only fixture**: 172 repeated proof checks in 3,497,943,690 cycles; 175 exceeded the limit; 173 and 174 were not run on the pinned build. On 1.97.0, 175 fit and 176 did not |
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
| B. Randomized batch in one script run | 172 verification-only (fixture) | none: same keys, same proofs | Check each proof off-chain first, because one bad proof rejects the whole batch | **Chosen** for shared mode |
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
  before any challenge exists, so changing any of them changes every challenge. It does
  not stop trial and error: a prover can compute the challenges of as many candidate
  batches as it likes, and reordering the same proofs is already a new candidate.
- Soundness of the batching step: for one fixed batch in which at least one equation
  fails, the product holds with probability at most 2⁻¹²⁸ over the challenges (the
  small-exponents argument). A prover who tries Q candidate batches succeeds with
  probability about Q/2¹²⁸, plus terms for BLAKE2b collisions and for breaking the key
  hash. This is an argument in the random-oracle model for BLAKE2b and is separate from
  the security of Groth16, its setup and BN254, which batching does not change.
- Preconditions the script enforces: every proof and key point is on the curve and in the
  right subgroup (arkworks checked deserialization, as `verifier-core` does); no proof
  point and no key point is the identity; the key has at least its constant IC entry;
  every public value is below the modulus; 1 ≤ N ≤ 256. Key validation and the bound on N
  were added after the external review (findings 1 and 3). Sums computed during the check
  may be the identity and are not rejected.
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
| Largest batch tested under 3.5B cycles | 172 repeated proof checks, 50,875 transaction bytes, 2,056,310 cycles of headroom; 173 and 174 not run, 175 exceeded | spike, pinned, script-only fixture |
| The same after the review changes | 175 fit (3,491,480,605), 176 did not; 173 and 174 fit | spike, 1.97.0 |
| Separate verification | 113.5M to 114.9M per proof | spike, pinned |
| Single proof, four-pair product | 93.3M | spike, pinned |
| Script size | 120,400 bytes (before the review changes) | spike, pinned |
| Cycles left per ballot at 100 ballots per block | 3,500M ÷ 100 = 35M per ballot; minus 19.9M and a 0.8M share of the fixed cost leaves about 14.3M for the public-vector rebuild and the nullifier insertion | computed |

The last row is the budget R2 has to meet for the ballot box. If a set insertion in
CKB-VM costs more than about 14M cycles, 100 ballots per block is out of reach with a
single shared set and the design has to shard.

What the fixture is. One script run on a Cell of 1,000 shannons with a 900-shannon output,
which is below the occupied-capacity rule a node enforces and which ckb-testtool does not
check; two recorded proofs repeated; no public-vector rebuild, no effects, no fee payer's
Lock. It measures the batch verifier and nothing else. The fixed cost of 79M is a fit over
large N; a batch of one cost 93.3M.

Conditional budget for ballots. If a ballot costs 19.9M for verification and 1.2M for its
nullifier insertion (R2), then 160 ballots use 79M + 160 × 21.1M = 3,455M cycles and leave
45M for everything not in that sum: rebuilding 160 public vectors and context digests, the
application checks, the fee payer's Lock and transaction overhead. That is 281,250 cycles
per ballot, and the binding checks alone were estimated at under 1M per proof in R0. So
160 is an upper bound under an optimistic model, 162 is where the model reaches zero
headroom, and the number of complete ballots per block is unknown until a capacity-valid
transaction with distinct ballots is measured (test plan item 6). The target of 100
ballots leaves 14.3M per ballot and is the figure to plan with.

A block's 3.5B cycles are shared with every other transaction on the chain. A batch of this
size is a relay transaction that fills an entire block.

## 7. Pinned tools

As R0, section 10. arkworks 0.5 (`ark-bn254`, `ark-ec`, `ark-ff`, `ark-groth16`,
`ark-serialize`), `groth16-ckb@d64c769`, ckb-std 1.1.0, ckb-hash 1.1.0, ckb-testtool 1.1.1.

## 8. Test plan

1. The spike on the pinned toolchain (D3): `spikes/throughput/run.sh`. To be repeated for
   the version changed after the review.
2. Adversarial batches. Run in CKB-VM on 1.97.0 after the review (39 cases, each with the
   exit code both modes must return): at N = 4 a public input and a proof point altered at
   every index, two items altered, reversed order and a fourfold duplicate accepted,
   identity A, B and C, a public value not below the modulus, a public input missing,
   valid proofs under another circuit's key, identity α, β, γ, δ, IC first and last, an
   empty IC, ten malformed framings (counts 0, too large, too small, 257, 0xffffffff;
   outer and inner trailing bytes; truncation; an item length of 0xffffffff), and the chunk
   boundaries N = 5, 6, 13, 14 with index 0 and the last index altered.
   Not yet covered from the reviewer's list: off-curve and non-subgroup points in each
   position (the script relies on arkworks' checked deserialization; a fixture needs a
   curve library in the harness); a key with zero public inputs (no recorded proof exists);
   zero and boundary coefficients, an identity aggregate and a zero coefficient sum (they
   need a test-only seam for the coefficients and belong to the library crate, T3); a
   duplicated ballot rejected by the nullifier rule (no nullifier rule in the spike).
3. Differential: for random batches of valid and invalid proofs, batch result equals the
   conjunction of separate results, on the host with the same code (10,000 batches) and in
   CKB-VM (a smaller sample).
4. Challenge derivation: change any byte of any item and require every r_i (i ≥ 1) to
   change.
5. A local node: submit one transaction of about 3.4B cycles and one of about 1B; record
   whether each is accepted to the pool, relayed and committed (D4).
6. A capacity-valid batch transaction with distinct ballots, per-item public-vector
   rebuild, nullifier insertions and a secp256k1 fee input: cycles per ballot, and the
   largest N that fits.

## 9. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| T1 | Spike repeated on the pinned toolchain | Done 11 November 2026: largest N under 3.5B was 172 |
| T2 | Single-product verification proposed to `groth16-ckb` (patch and tests written, section 11) | Upstream integration tests and both recorded matrices pass with the patched verifier on the pinned toolchain; cycles at least 10% lower |
| T3 | Batch verifier as a library crate with the adversarial and differential tests, a bound on N and key validation shared with `verifier-core`, and a test-only seam for the coefficients | Test plan items 2 to 4 pass, including the cases listed as not yet covered |
| T4 | Node behaviour for large transactions | Test plan item 5 recorded |
| T5 | Batch mode in the generator, with shared mode (R0 milestone M7) | Two voters' proofs in one transaction on a local chain; test plan item 6 recorded |

## 10. Risks and open questions

| Risk | Handling |
| --- | --- |
| A node's pool treats very large transactions differently. In `ckb@v0.210.0`, `max_tx_verify_cycles` (default 70M) is the threshold above which a transaction goes through the pausable large-cycle verification queue; the cycle ceiling passed to verification on submission is the consensus block limit (source: `tx-pool/src/process.rs`, `verify_queue.rs`). The tally's 115M-cycle transactions were committed on testnet. Behaviour near 3.5B was not tested | T4. A practical batch is likely well below a full block |
| A full-block transaction waits for a miner with an empty block template | Target batches of 32 to 64 (0.7B to 1.3B cycles) in normal operation |
| The same library verified the same proof in 104.9M to 114.9M cycles across four binaries and two compilers; the cause of the spread is unexplained | Quote per-binary numbers; do not quote one number for "a verification" |
| Batch failure hides the offender; anyone can submit invalid or conflicting items for free; a batch can also fail with every proof valid | Relayer rule in section 12 |
| The system secp256k1 Lock rejects any witness over 32,768 bytes among those it hashes (its own group's, and those beyond the input count); a 172-proof payload is about 50 KB | The batch payload sits in the application input's witness, which a fee payer's Lock does not read (R4, section 5); test in R4's plan |
| Challenges of 128 bits | At most 2⁻¹²⁸ for one fixed batch; about Q/2¹²⁸ for a prover who tries Q candidate batches, and a candidate costs one hash (reordering is enough). 2⁶⁴ candidates give about 2⁻⁶⁴ |
| The pinned cycle numbers are from the script before key validation and the bound on N were added | Rerun `spikes/throughput/run.sh` on the pinned toolchain; on 1.97.0 the changed script cost 0.004% less at N = 1 and 0.005% less at N = 172 than the earlier one |

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
integration tests and the 4 new tests passed (11 November 2026). After the external review
two tests were added to the patch (X equal to the identity, and a key with no public
inputs); the 6 tests passed on Rust 1.97.0 and have not yet been run on the pinned
toolchain. The change to `verifier-core` itself is the one already tested there.

## 12. External review

One review by an outside model, at commit `206df77`, covering this document, the spike, the
upstream patch and `verifier-core` and `wire-decode` at `d64c769`. Finding 2 and the
arithmetic of finding 5 were reproduced from the code and the result files; the rest were
argued from source. No forgery was attempted or found. All seven findings were accepted.

| # | Severity | Finding | Response |
| --- | --- | --- | --- |
| 1 | Medium | Batch mode did not validate the key. A key with an identity α, β, γ, δ or IC entry reached the batch arithmetic (mode 0 rejects it inside `verifier-core`), and an empty IC reached `len() - 1`, which panics. The document's claim that no point is the identity was false for key points | Accepted. Confirmed at `main.rs` (the `deserialize_compressed` of the key was followed directly by `gamma_abc_g1.len() - 1`). Batch mode now applies `verifier-core`'s key rules before any arithmetic and returns 50; mode 0 maps `InvalidVk` to 50 as well. Seven key cases (six identity positions and an empty IC) return 50 in both modes (1.97.0). As the reviewer notes, this was not a forgery path against a correctly generated key pinned by hash |
| 2 | Medium | The rejection test counted skipped runs, cycle exhaustion and loader errors as rejections, and never asserted that a valid batch was accepted. "12 of 12" and "24 of 24" overstated what was shown | Accepted. The harness now classifies every run (accepted, script exit code, cycle limit, other), asserts that a valid batch is accepted or cycle-limited, and counts a rejection only when the control was accepted and the altered batch exited with 51. Corrected counts are in D2 and section 6. The adversarial list was added as a second test: 39 cases, section 8 says which of the reviewer's list are still missing |
| 3 | Medium | The count N sized an allocation before it was checked against the bytes present | Accepted. N is now refused with 48 before any allocation unless 1 ≤ N ≤ 256 and N × 166 bytes (the smallest item) fit in the witness; the item length is added with checked arithmetic. Counts of 0, 5 with four items, 257 and 0xffffffff, and an item length of 0xffffffff, return 48 in both modes |
| 4 | Medium | The relayer rule covered invalid proofs and nullifier conflicts but not transactions that fail with every proof valid: a consumed application Cell after a competing batch, stale set witnesses, capacity or cycle overruns, conflicting fee inputs; and it bounded work per connection, not in total | Accepted. The rule is rewritten below. The reviewer confirmed the fee statement: a transaction whose script fails is not committed and pays no fee |
| 5 | Medium | "172 per block" described a fixture that is not a relayable transaction: capacities of 1,000 and 900 shannons, two proofs repeated, no public-vector rebuild, no effects, no fee payer. 173 and 174 were not run. "About 160 ballots" leaves 45M cycles in total, 281,250 per ballot, for everything not modelled | Accepted. The result is now stated as 172 repeated proof checks in a script-only VM fixture; 172 is the largest tested success on the pinned build, where 173 and 174 are still not run. 160 ballots is kept only as a conditional budget (section 6). The capacity-valid measurement with distinct ballots, binding, effects and a fee Lock is test plan item 6 and R0 milestone M7 |
| 6 | Low | "2⁻¹²⁸ per attempt, and each attempt needs new valid-looking proofs" was wrong: reordering the same proofs gives a new transcript and a new trial at the cost of a hash | Accepted. Sections 4 and 10 now state at most 2⁻¹²⁸ for one fixed transcript and about Q/2¹²⁸ for a prover who tries Q transcripts, plus hash-collision terms, in the random-oracle model, and separate this from Groth16 and BN254 security |
| 7 | Low | The new single-product tests did not contain a case with X equal to the identity, although the README named it, and none with zero public inputs | Accepted. Two tests added to the patch: X = identity built from known scalars with every key and proof point a non-identity point, and a key with only the constant IC entry. 6 of 6 passed on Rust 1.97.0; the pinned rerun is listed in section 11 |

Examined by the reviewer without a finding: the batch equation and its signs; the soundness
argument (including correlated proofs, duplicates and several invalid items); the transcript
(count, lengths, proofs and public inputs are all hashed; indices are fixed-width; the
128-bit coefficients have no reduction bias; the key is bound by its data hash); the
deterministic outer framing; curve and subgroup checks by arkworks' checked
deserialization; the chunked Miller loops; and the single-product patch. The reviewer also
pointed out that an identity aggregate (Σ r_i·X_i, Σ r_i·C_i, a zero Σ r_i) is legitimate
and must not be rejected, which the script does not do.

**Relayer rule after the review.** None of this is built or tested.

1. *Admission.* Verify each proof on its own before queueing it. Keep one pending item per
   nullifier. Bound the verification work in progress and queued across all connections
   together, not per connection, and refuse beyond it.
2. *Assembly.* Immediately before sending, read the live application Cell and rebuild from
   it: the consumed OutPoint, every set witness against the current root, the capacity
   arithmetic, and the cycle and size totals. Drop items whose nullifier is now in the set
   or whose root has left the ring. Use fee inputs that no other pending transaction of the
   relayer spends.
3. *Classification of a failed or dropped transaction.* (a) The application Cell was
   consumed by someone else, or a set witness is stale: every proof is still valid; go back
   to step 2 with the same items. Do not re-verify and do not discard. (b) A fee input was
   spent, or the pool rejected the size or fee: rebuild the envelope only. (c) The script
   exited with 51: only then re-verify items singly and drop the failures. (d) Any other
   exit code: a relayer bug; stop and report.
4. *Retries* are bounded per batch and per item. An item that has gone through step 3(a)
   more than a set number of times is returned to its sender with the reason.
5. *The voter's side* (added after the R4 review, finding 5). A relayer is not needed for
   authorization: the proof is the authority and a relayer cannot change a bound ballot.
   It is a privacy observer: it sees the submitting connection's IP address, the time of
   submission, the nullifier and, with public choices, the choice. It is also an
   availability dependency: it can drop or delay a ballot, and nothing in this rule stops
   that or makes it visible. The client keeps the submitted ballot, watches the ballot box
   for its nullifier, and resubmits through another relayer or a wallet-funded transaction
   if it has not appeared by a deadline it chooses before `close_after`. That preserves the
   right to submit, not the voting window: a ballot held back until after `close` cannot be
   cast. Timely inclusion is an assumption of the ballot box, not a property (R2 section 4).

The inclusion race in 3(a) cannot be removed by checking state late: with several relayers
on one Cell, all but one lose each round. That is the single-Cell contention R2 section 4
accepted, and the reason one relayer per ballot box is the operating assumption.
