# Week 9 arkworks and CKB wire adapter

## Objective

Week 9 tests one cross-library claim:

```text
the retained Week 8 public-first snarkjs proof
  -> strict BN254 JSON parsing
  -> validated arkworks 0.5 objects
  -> arkworks host verification with public input 49
  -> canonical compressed serialization
  -> groth16-ckb version-1 Molecule encoding
  -> pinned wire decoding and host verification
```

The same proof must reject public input `7` in arkworks. A successful positive
check without the negative check is insufficient.

## Pinned endpoint dependency

The adapter pins the following crates from `groth16-ckb` commit
`d64c769ffe2d2edb5eb308dc59058efda77c2f83`:

- `groth16-schema`
- `wire-decode`
- `verifier-core`

This avoids creating a second undocumented wire format. The adapter constructs
the endpoint's own generated Molecule entities, decodes them through the
endpoint decoder, compares the reconstructed canonical byte buffers, and calls
the endpoint host verifier.

## Input fixture

`tests/fixtures/week-09-public-first/` contains only public development material:

- snarkjs verification key
- snarkjs proof
- intended public vector `[49]`
- incorrect public vector `[7]`
- provenance manifest

The source files are the retained Week 8 public-first artifacts normalized with
one trailing line-feed byte for committed text-file hygiene. The manifest records
both the original Week 8 hashes and the committed fixture hashes. No witness,
proving key, R1CS, WTNS, or Powers of Tau material is included.

## Fail-closed parsing rules

The adapter accepts only:

- `protocol = groth16`;
- snarkjs curve identifier `bn128`;
- canonical unsigned decimal integers without signs or leading zeroes;
- base-field and scalar-field integers strictly below their respective moduli;
- affine G1 marker `z = 1`;
- affine G2 marker `z = [1,0]`;
- non-infinity points on the expected curve and in the correct subgroup;
- `nPublic == public.len()` and `IC.len() == public.len() + 1`.

arkworks `FromStr` reduces integers modulo the field modulus. The adapter
therefore performs an explicit integer bound check before calling it. Omitting
this check would allow a non-canonical source number to be silently changed.

snarkjs/ffjavascript represents Fq2 values as `[c0,c1]`, which maps directly to
`ark_bn254::Fq2::new(c0,c1)`. Solidity calldata examples reverse these
coefficients for the EVM precompile; that EVM-specific order is not used here.
The final proof verification is the required cross-implementation confirmation
of the mapping.

## Output boundary

After host verification, the adapter writes ignored generated output:

```text
target/week-09/adapter-output/
  vk.bin
  proof.bin
  public_inputs.bin
  vk.mol.bin
  witness.mol.bin
  vk_data_hash.bin
  manifest.json
```

`vk_data_hash.bin` is the CKB Blake2b data hash of `vk.mol.bin`. It is the value
the reference endpoint expects a consuming Type Script to commit to in its
script arguments.

The retained execution used:

```bash
target/release/noir-ckb-adapter \
  --vk tests/fixtures/week-09-public-first/verification_key.json \
  --proof tests/fixtures/week-09-public-first/proof.json \
  --public tests/fixtures/week-09-public-first/public.json \
  --negative-public tests/fixtures/week-09-public-first/wrong-public.json \
  --out target/week-09/adapter-output
```

## Retained result

The Week 9 execution and independent source recheck passed on 27 July 2026:

```text
snarkjs 0.7.5: [49] accepted; [7] rejected
arkworks 0.5:  [49] accepted; [7] rejected
pinned groth16-ckb host round trip: accepted
```

The locked Rust suite executed 11 tests: 4 parser-validation unit tests and 7
interoperability integration tests. All 11 passed with no failures or ignored
tests. The integration coverage included positive and negative proof semantics,
exact canonical-byte round trips, pinned endpoint verification, wrong public
input rejection, wrong wire-version rejection, and truncated-witness rejection.

The generated wire artifacts were:

| File | Bytes | SHA-256 |
|---|---:|---|
| `vk.bin` | 296 | `d1fff371445229aebd8ab9bbe99136d6cb7edc2ffc9cfbdb3d2167eb0b5b3ef2` |
| `proof.bin` | 128 | `e7f78ab7982a1f5bae7d0ca41a127441e1a2b313fd115c5f6689cc3c73128f83` |
| `public_inputs.bin` | 36 | `3ba8a49e2f3e686fd0d1400e8ca9a180f24d049dbc03f4932552eff4d31bba6d` |
| `vk.mol.bin` | 334 | `41e4aa9079d7801a218b2b660d7e9852e52cc8f884645506432e5f38ac7cd01e` |
| `witness.mol.bin` | 194 | `2f29111ce4a456dd147e352aab6c2d6ba1f270792f93e1a7e253c29037c7095b` |
| `vk_data_hash.bin` | 32 | `abc2ab2344b56daf6e2e8bc3b5c8425923a85bc49baab887231f5e8bfe159b36` |

The 32-byte CKB data-hash value stored in `vk_data_hash.bin` is:

```text
1fa6f0c18ff7b0d32abcd01ddf2ddcc3e4190be99add55bbf2418f045eb32715
```

This value is a CKB Blake2b hash of the Molecule VK payload. It is distinct
from the SHA-256 digest used to identify the `vk_data_hash.bin` file in the
artifact table.

## Week 9 stopping point

Week 9 stops after the pinned endpoint crates decode and host-verify the emitted
Molecule payload. It does not claim:

- CKB-VM execution of the Noir-derived proof;
- a transaction containing the emitted witness;
- Capsule transition binding;
- a production trusted setup;
- arbitrary Noir public-wire compatibility;
- audit or production readiness.

Those boundaries remain Week 10 and later work.
