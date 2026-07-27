# artifact-adapter

Week 9 typed Rust adapter for the constrained public-first compatibility path:

1. parse snarkjs Groth16 proof, verification-key, and public-input JSON;
2. validate BN254 field elements and G1/G2 points without modular reduction;
3. construct arkworks 0.5 objects;
4. verify the same proof through arkworks;
5. serialize with `CanonicalSerialize`;
6. encode the pinned `groth16-ckb` version-1 Molecule wire objects;
7. decode and verify the emitted wire objects through the pinned endpoint crates.

The adapter is fail-closed. It accepts only `protocol = groth16`, `curve = bn128`,
affine projective markers, canonical field elements, non-infinity curve points in
the correct subgroup, and a public-input count consistent with the verification
key.

This is experimental, development-only interoperability code. It does not make
the Week 8 trusted setup production-safe and does not establish support for
arbitrary Noir witness layouts.

## Command-line use

```bash
noir-ckb-adapter \
  --vk verification_key.json \
  --proof proof.json \
  --public public.json \
  --negative-public wrong-public.json \
  --out target/adapter-output
```

The optional negative public vector makes the semantic rejection check part of
the command. On success, the output directory contains canonical arkworks
buffers, version-1 Molecule VK and witness objects, the CKB VK data hash, and a
manifest containing exact byte sizes and SHA-256 digests.

The Week 9 retained fixture accepted `[49]`, rejected `[7]`, survived the pinned
wire decoder unchanged, and verified through the pinned host endpoint. See
[`../../evidence/week-09.md`](../../evidence/week-09.md) for the complete
evidence and claim boundary.
