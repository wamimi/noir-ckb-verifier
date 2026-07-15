# Threat boundary

## Security status

This project is experimental, pre-audit research. Development trusted setups, experimental ACIR lowerings, and cross-library conversions must not be presented as production-ready cryptography.

## Mathematical verification is not authorization

The generic verifier establishes only:

```text
verify(vk, public_inputs, proof)
```

It does not establish that the proof belongs to the particular CKB transition being validated.

The application acceptance rule must be:

```text
proof verifies under the committed VK
AND decoded public inputs are canonical and ordered
AND public inputs equal values derived from this transaction
AND Capsule transition rules hold
AND replay-domain rules hold
-> accept
```

## Required transition binding

The final Capsule circuit and Type Script design must agree on commitments covering at least:

- old Capsule state or commitment
- new Capsule state or commitment
- stable Capsule identifier
- intended action identifier
- nullifier or equivalent one-time authorization value
- replay domain, potentially including network/script identity and the consumed OutPoint

The precise hash function, field encoding, domain separators, and OutPoint policy remain design work. They must be specified before Week 10 implementation.

## Required acceptance tests

```text
valid proof + correct transition -> accept
valid proof + wrong transition   -> reject
invalid proof                    -> reject
malformed serialization          -> reject
wrong VK Cell                    -> reject
replayed proof in wrong domain   -> reject
```

The “valid proof + wrong transition” test is a first-class security invariant, not an optional negative case.

## Private-data boundary

A Noir private witness is private only during proof generation. It must remain off-chain and must not be committed to Git.

A CKB transaction witness is public transaction data. It may carry a zero-knowledge proof and public inputs, but it must never carry the private Noir witness merely because both objects are called “witnesses.”

The Week 7 `x = 7` fixture is intentionally public, non-sensitive test data.

## Serialization boundary

“Groth16 over BN254” does not imply byte compatibility between implementations. The adapter must reject:

- out-of-range base- or scalar-field elements
- invalid coordinate or extension-field ordering
- points not on the curve
- points outside the correct subgroup
- unexpected infinity points
- non-canonical encodings
- truncated, oversized, or ambiguously framed input
- public-input count or ordering mismatches

Conversion must construct validated typed objects and then use arkworks canonical serialization. Manual byte reversal is not a sufficient interoperability strategy.

## Verification-key binding

The application must commit to the intended VK Cell data, not merely load any CellDep containing a syntactically valid key. A wrong or substituted VK Cell must fail before or during proof verification.

## Resource and liveness boundary

The CKB-VM verifier has finite cycle and memory limits. Exact Week 7 binary size and cycle evidence will be recorded from a fresh user-run build. Indefinite fuzzing and deployment are explicitly outside the baseline.

## Out of scope for Week 7

- production trusted setup ceremony
- audited soundness claims
- ACIR-to-Groth16 execution
- cross-library proof conversion
- CKB devnet deployment
- indefinite fuzzing
- final Capsule commitment design

## Reference

- [groth16-ckb threat model](https://github.com/CECILIA-MULANDI/groth16-ckb/blob/main/docs/threat-model.md)
