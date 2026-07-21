# Week 8 backend selection and experiment

## Objective

Week 8 tests one narrow compatibility claim:

```text
the pinned Noir beta.18 square-root artifact
  -> strict ACIR-to-R1CS lowering
  -> iden3 R1CS and WTNS
  -> development-only BN254 Groth16 setup
  -> proof generation
  -> source-backend verification
```

Passing this experiment will not establish CKB compatibility. Typed arkworks conversion, canonical serialization, Molecule encoding, CKB-VM verification, and Capsule transition binding remain later milestones.

## Selected experiment backend

The first backend experiment uses [Noir-Groth16](https://github.com/jamesbachini/Noir-Groth16) at:

```text
4b7caace1f2128e454c8d0fe50cac1ec46b1e272
```

This revision was selected for evaluation because it exposes the intermediate boundary needed by this project:

- Noir artifact JSON and ABI parsing
- pedantic ACVM witness solving by default
- strict ACIR-to-R1CS lowering
- iden3 `.r1cs` and `.wtns` output
- snarkjs-compatible Groth16 artifacts
- explicit failure for unsupported or underconstrained behavior

The revision's workspace uses Noir beta.19 ACIR/ACVM dependencies and also carries a beta.18 legacy ACIR parser pinned to `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`. The latter matches the source revision embedded in the Week 7 artifact. Nelly reproduced those pins, and the backend parsed, solved, and lowered the existing artifact. The later public-input gate showed why those successes alone were insufficient.

The backend is consumed from a separate checkout. Its source is not vendored into this repository and will not be modified during the baseline.

## Why Sunspot is not the first experiment

[Sunspot](https://github.com/reilabs/sunspot) remains a research comparison, but its current main branch requires Noir beta.22 and is primarily organized around a Solana/gnark proving workflow. Moving the existing beta.18 fixture to beta.22 would combine compiler migration with backend evaluation and make a failure harder to diagnose.

Sunspot is therefore not rejected. It is deferred until this project has a known Groth16 control path and a reason to compare gnark-produced objects or upgrade the Noir compiler.

## Evidence gates

The experiment advances only after each gate's complete terminal output is retained and reviewed:

1. Confirm the exact backend revision, clean status, dependency locks, and host tools.
2. Build the backend CLI from the lockfile.
3. Parse the existing beta.18 `square_root.json` without recompiling it.
4. Strictly solve and lower the artifact using `inputs.json`.
5. Inspect the R1CS/WTNS metadata and verify witness consistency with a pinned snarkjs version.
6. Generate a development-only Powers of Tau transcript and Groth16 proving key.
7. Generate a proof and verify it with the source backend.
8. Inspect and hash the proof, verification key, public inputs, R1CS, and WTNS.
9. Confirm the public input is semantically `y = 49`, not merely that verification returns success.
10. Run at least one negative check showing altered public input or proof data is rejected.

If the original fixture fails the public-input semantic gate, preserve it as regression evidence. A public-first source-order control may be tested separately to isolate whether the failure is caused by identity witness-to-wire mapping. Such a control is not evidence of general compatibility and must not replace a fail-closed layout check or correct backend remapping.

## Public-input semantic gate

Groth16 verification can succeed while exposing or binding the wrong values as public inputs. The Week 7 ACIR printout establishes:

```text
private parameters: [w0]
public parameters: [w1]
ASSERT w1 = w0*w0
```

The expected Groth16 public input is therefore exactly `49`. Week 8 must inspect the generated `public.json`; a file containing `7` would be a semantic incompatibility even if `snarkjs groth16 verify` reports success.

This check is deliberately separate from proof verification because:

```text
proof verifies for some exported public vector
!=
the exported vector preserves Noir's public ABI semantics
```

## Development setup warning

The Week 8 setup is local test material only. It is not a production ceremony and provides no claim of secure setup provenance. Powers of Tau files, proving keys, witnesses, and proof artifacts remain ignored by Git. The evidence record retains commands, versions, sizes, hashes, and non-secret decoded metadata instead of committing secret-bearing or bulky generated material.

## Week 8 stopping point

Week 8 ends after source-backend Groth16 verification, public-input semantic validation, negative verification, and artifact inspection.

The following are explicitly deferred:

- parsing snarkjs JSON into arkworks BN254 types
- coordinate/field conversion implementation
- canonical arkworks serialization
- Molecule encoding
- `groth16-ckb` verification of the Noir-derived proof
- Capsule Cell-transition tests
- production setup or deployment

## Compatibility result and remediation experiment

The original private-first fixture produced a structurally valid and source-verifiable Groth16 proof, but the generated public vector was `[7]`. The same proof was rejected against the Noir-intended vector `[49]`. The selected backend is therefore not generally compatible with Noir's visibility metadata at this revision.

Week 8 preserves that failure and adds `circuits/square-root-public-first` as an explicitly limited control. It states the same relation but declares public `y` before private `x`. Retained evidence confirmed all of the following:

- Nargo assigns public `y` to the leading ACIR witness position.
- The backend parses, solves, and strictly lowers the new artifact.
- snarkjs reports the R1CS/WTNS pair consistent.
- generated `public.json` is exactly `["49"]`.
- the proof verifies with `["49"]` and rejects `["7"]`.

The passing control does not generalize to arbitrary Noir circuits. They still require a correct remapper or a pre-proving layout rejection rule.
