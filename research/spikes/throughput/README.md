# Spike: randomized batch verification of Groth16 proofs in CKB-VM

Research question for [R3](../../throughput.md): how many proof checks fit in one block
(3.5B cycles), verified one by one and verified as one randomized batch under one key?

## What it is

- `contracts/verify-batch`: one script with two modes. Mode 0 calls `verifier-core` once
  per proof. Mode 1 checks all proofs with one pairing product (N + 3 Miller loops, one
  final exponentiation), with 128-bit challenges derived by BLAKE2b from the key hash and
  every proof and public input in the batch.
- `harness/`: two tests. `batch` builds a transaction carrying N proofs taken from recorded
  case files, runs both modes, then alters one public input of the last proof. `adversarial`
  runs 39 malformed or invalid batches and keys at small N. Every run is classified as
  accepted, rejected by the script with an exit code, cycle limit exceeded, or other. A
  valid batch must be accepted or cycle-limited; an altered batch counts as rejected only
  when its control was accepted and the script exited with the expected code.
- The fixture is one script run on a Cell of 1,000 shannons. It measures the verifier. It
  is not a transaction a node would relay: ckb-testtool does not check capacity rules, the
  proofs are two recorded proofs repeated, and there is no public-vector rebuild, no effect
  and no fee payer.

## Command

```bash
research/spikes/throughput/run.sh
```

## Result after the external review (11 November 2026, Rust 1.97.0 only)

The review ([R3](../../throughput.md), section 12) led to three changes: the script
validates the key in batch mode (at least one IC entry, no identity point) and bounds N
before allocating (1 to 256, and no more than the witness can hold); the harness asserts
controls and classifies failures. Full output: `results/2026-11-11-rust-1.97.0-after-review.txt`.
Not run on the pinned toolchain yet. Script size: 90,016 bytes.

- Sweep, batch mode: accepted at N = 1 to 175 (90,952,254 cycles at 1; 3,431,225,603 at
  172; 3,448,827,730 at 173; 3,472,907,699 at 174; 3,491,480,605 at 175); cycle limit at 176.
- Sweep, last public input altered: 18 rejections with exit code 51 after an accepted
  control (13 batch, 5 separate); 2 not shown because the valid batch itself exceeds the
  cycle limit (batch at 176, separate at 32); 8 separate-mode runs above N = 32 not made.
- Adversarial: 39 of 39 cases returned the expected result in both modes. Valid batches in
  reversed order and with one proof four times were accepted. Exit code 51: a public input
  or proof point altered at each index of a batch of four, two altered items, identity A, B
  or C, a public value not below the modulus, a missing public input, valid proofs under
  another circuit's key. Exit code 50: identity α, β, γ, δ, first or last IC entry, and an
  empty IC. Exit code 48: ten malformed framings. Chunk boundaries N = 5, 6, 13, 14 in
  batch mode: valid accepted, index 0 and last index altered rejected with 51.
- Cycle cost of the added checks: none measurable (the changed script used 0.004% fewer
  cycles at N = 1 and 0.005% fewer at N = 172 than the earlier build on the same compiler).

Not covered: off-curve and non-subgroup points, a key without public inputs, chosen
coefficients (zero, boundary, identity aggregates), and any application rule.

## Result on the pinned toolchain (11 November 2026, before the review changes)

Rust 1.94.1 (contracts), Rust 1.95.0 (harness), clang 18, macOS ARM64. Full output:
`results/2026-11-11-pinned-macos-arm64.txt`. Script size: 120,400 bytes. Proofs: the
recorded tally update and create proofs, alternating.

| N | Separate (cycles) | Batch (cycles) |
| --- | --- | --- |
| 1 | 114,906,306 | 93,265,649 |
| 2 | 226,968,383 | 122,834,394 |
| 4 | 453,862,661 | 160,346,092 |
| 8 | 907,694,597 | 238,731,118 |
| 16 | 1,815,287,412 | 398,680,509 |
| 32 | over 3.5B | 715,730,048 |
| 64 | | 1,353,053,766 |
| 128 | | 2,626,770,336 |
| 160 | | 3,260,552,258 |
| 172 | | 3,497,943,690 |
| 175 | | over 3.5B |

- Batch cost: about 79M fixed plus 19.9M per proof. Separate: about 113.5M per proof.
- Largest batch tested under 3.5B cycles: 172 repeated proof checks, with 2,056,310 cycles
  to spare. 173 and 174 were not run; at 19.9M per proof 173 would exceed the limit
  (estimate).
- A batch of one is 18.8% cheaper than `verifier-core` in the same binary.
- With the last public input altered, the run failed at each of the 10 sizes whose valid
  batch was accepted (batch mode) and at each of the 5 such sizes in separate mode. The
  harness of this run did not record the cause of a failure. The summary line "12 of 12" in
  the result file also counted 3 cycle-limited runs and 6 separate-mode runs that were
  never executed; it is kept in the file as recorded and is wrong.
- The pinned build was 2% to 3% slower than the Rust 1.97.0 build below, not the 10%
  allowed for beforehand.

## Result on Rust 1.97.0 (11 November 2026, first run)

Not the pinned toolchain (same situation and same build as
[`../toolkit-architecture/placement`](../toolkit-architecture/placement/README.md): Rust
1.97.0, LLVM 22.1.6, `-Zbuild-std`, ckb-testtool 1.1.1, Linux x86_64). Full output:
`results/2026-11-11-rust-1.97.0-build-std.txt`. Script size: 90,800 bytes.

Proofs: the recorded tally update and create proofs, alternating (ceremony key, four public
inputs, two or three of them full-width).

| N | Separate (cycles) | Batch (cycles) | Transaction bytes |
| --- | --- | --- | --- |
| 1 | 111,505,877 | 90,956,202 | 601 |
| 2 | 220,249,766 | 119,829,396 | 895 |
| 4 | 440,432,011 | 156,699,354 | 1,483 |
| 8 | 880,841,864 | 233,617,910 | 2,659 |
| 16 | 1,761,587,243 | 390,541,433 | 5,011 |
| 32 | over 3.5B | 701,624,478 | 9,715 |
| 64 | | 1,326,919,964 | 19,123 |
| 128 | | 2,576,609,358 | 37,939 |
| 160 | | 3,198,465,216 | 47,347 |
| 175 | | 3,491,658,697 | 51,757 |
| 176 | | over 3.5B | |

- Batch cost: about 77M fixed plus 19.5M per proof. Separate: about 110M per proof in this
  binary (104.9M for the same proofs in the placement spike's binary; the 5% difference
  between two builds of the same library was not investigated).
- With small public values (a development-key circuit, n = 4): separate 103.5M each, 32
  fit in a block (3,311,344,404); batch 175 fit (3,487,040,752).
- With the last public input altered: the run failed at the 22 batch-mode and 11
  separate-mode sizes whose valid control was accepted (cause not recorded by that
  harness). An earlier version of this file said "all 24 runs", which also counted 3
  cycle-limited and 12 unexecuted runs.
- A batch of one is 18% cheaper than `verifier-core` in the same binary. `ark-groth16`
  computes e(α, β) as a separate pairing with its own final exponentiation on every
  verification; the batch equation folds it into the one product.

## What did not work

- The first version prepared all G2 points at once and ran out of memory at N = 64 (script
  exit -1). Miller loops now run in chunks of 8.
- Only verification was measured. A real batch must also rebuild N public vectors and
  apply N state updates; those costs are R2's.
- One script run in ckb-testtool. Whether a node relays and mines a 3.4B-cycle
  transaction was not tested.
