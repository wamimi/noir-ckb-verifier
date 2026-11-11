# Proposal for groth16-ckb: verify with one pairing product

A change to `verifier-core` of
[`CECILIA-MULANDI/groth16-ckb`](https://github.com/CECILIA-MULANDI/groth16-ckb), written
against revision `d64c769ffe2d2edb5eb308dc59058efda77c2f83`. It came out of the throughput
research in this repository ([R3](../../throughput.md)).

- [`single-product-verify.patch`](single-product-verify.patch): the change, a new host
  test file, and the two lock file updates. Applies with `git apply`.

## Summary

`verifier_core::verify` ends by calling `ark_groth16::Groth16::verify`. That function
checks

```
e(A, B) · e(X, −γ) · e(C, −δ) = e(α, β),      X = IC₀ + Σ xᵢ·ICᵢ
```

and computes the right-hand side with `E::pairing(α, β)` inside `prepare_verifying_key`
on every call (`ark-groth16` 0.5.0, `verifier.rs`). In total: four Miller loops and two
final exponentiations.

The patch checks the same equation as one product,

```
e(A, B) · e(−α, β) · e(−X, γ) · e(−C, δ) = 1
```

with one `multi_pairing` call: four Miller loops and one final exponentiation. The
negations are in G1. Nothing else in `verify` changes: the length checks, the checked
deserialization of key, proof and inputs, and the identity-point rejections stay as they
are and run before the product. Proofs, keys and wire formats are unchanged.

`ark-snark` is no longer needed by `verifier-core`; `ark-ff` is added for `PrimeField` and
`One`.

## Measured effect

On the repository's pinned toolchain (Rust 1.94.1, macOS ARM64, 11 November 2026), with the
repository's own benchmark (`cargo test -p integration-tests --test cycles -- --ignored
--nocapture`) at `d64c769` before and after the patch:

| Public inputs | Before | After | Saved |
| ---: | ---: | ---: | ---: |
| 1 | 99,843,490 | 79,186,128 | 20,657,362 (20.7%) |
| 4 | 100,656,230 | 79,967,436 | 20,688,794 (20.6%) |
| 8 | 101,702,797 | 81,071,306 | 20,631,491 (20.3%) |
| 16 | 103,998,027 | 83,333,647 | 20,664,380 (19.9%) |
| 32 | 108,736,103 | 88,051,450 | 20,684,653 (19.0%) |
| 64 | 118,483,349 | 97,832,285 | 20,651,064 (17.4%) |

The saving is a constant of about 20.66M cycles per verification.

A second measurement, on a different compiler: CKB-VM cycles for the same recorded proofs through a script that links `verifier-core`
(`research/spikes/toolkit-architecture/placement`, `verify-linked`), before and after,
built with Rust 1.97.0 and `-Zbuild-std` (not the repository's pinned 1.94.1):

| Proof | Before | After | Change |
| --- | --- | --- | --- |
| Private tally update (4 public inputs, 2 full-width) | 104,860,094 | 85,326,519 | −18.6% |
| Private tally create | 102,287,071 | 82,706,150 | −19.1% |
| Owned counter update | 99,755,219 | 80,217,270 | −19.6% |
| 1 small public input | 96,487,596 | 76,958,052 | −20.2% |
| 32 small public inputs | 105,146,625 | 85,571,072 | −18.6% |
| 32 full-width public inputs | 186,363,736 | 166,834,832 | −10.5% |

There the saving was about 19.5M cycles per verification, and the script went from 76,520
to 74,912 bytes.

## Tests

On the patched tree, on the pinned toolchain (11 November 2026):

| Suite | Result |
| --- | --- |
| `host` unit tests | 3 passed |
| `host/tests/differential.rs` (agreement with `ark_groth16`, bit flips in proof, key and inputs) | 26 passed; the ignored 1,000-sample variant also passed with `--ignored` |
| `host/tests/properties.rs` | 2 passed |
| `host/tests/single_product.rs` (new) | 4 passed |
| `integration-tests/tests/verify.rs` (CKB-VM, script built with `scripts/build-ckb-script.sh`) | 8 passed |
| `integration-tests/tests/cycles.rs` | passed; table above |

The new test file compares `verifier_core::verify` with `ark_groth16::Groth16::verify` and
requires the same verdict in each case:

- 25 proofs with a uniformly random (full-width) public input, each also with the input
  incremented and negated;
- public input 0, 1, and a witness of −1;
- 2, 4 and 16 public inputs, each input altered on its own, and two inputs exchanged;
- proofs for neighbouring equations that a sign error would accept: A negated, C negated,
  both negated, A and C exchanged; a valid proof under another key; a key with α negated.

## To reproduce on the pinned toolchain

```bash
git clone https://github.com/CECILIA-MULANDI/groth16-ckb && cd groth16-ckb
git checkout d64c769ffe2d2edb5eb308dc59058efda77c2f83
./scripts/build-ckb-script.sh
cargo test -p integration-tests --test cycles -- --ignored --nocapture    # before

git apply /path/to/single-product-verify.patch
./scripts/build-ckb-script.sh
cargo test --workspace
cargo test --workspace -- --ignored
cargo test -p integration-tests --test cycles -- --ignored --nocapture    # after
```

## Things the maintainer should weigh

- **New code hash.** Any change to `verifier-core` changes the script binary and therefore
  its data hash. Existing deployments and everything bound to the current hash are
  unaffected and do not benefit until they move to a new deployment.
- **The check no longer goes through `ark_groth16::Groth16::verify`.** The equation is now
  written out in this crate (12 lines), so its correctness rests on this repository's
  tests instead of on arkworks' verifier. The differential tests keep arkworks as the
  reference.
- **X can be the identity** for some public inputs. `multi_pairing` skips identity points,
  as arkworks' own verifier does; the product is then over three pairs.
- **An alternative with a further saving:** store e(α, β) in the key Cell (384 bytes more)
  and compare against it, removing one Miller loop. Not proposed here because it changes
  the key format.

## A separate observation about the README's cost model

The README says each additional public input adds about 270k to 300k cycles. That matched
our measurements only for small values. With full-width values (commitments, hashes) each
input cost about 2.8M cycles, because the scalar multiplication's cost follows the bit
length: 32 full-width inputs verified in 186M cycles against 105M for 32 small ones
(`research/spikes/toolkit-architecture/placement`, Rust 1.97.0). The benchmark's
`SumCircuit` inputs may be small values; if so, the table understates the cost for
applications whose public inputs are field-sized.
