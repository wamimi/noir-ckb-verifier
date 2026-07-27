# Week 9 evidence record

**Policy:** Results remain pending until complete terminal output is retained and
reviewed. This file records expected gates before execution so failures are not
silently rewritten as successes.

## Scope

- pin Rust, Cargo, repository, and endpoint dependency revisions;
- verify the committed fixture provenance and JSON equivalence;
- generate `Cargo.lock` from the pinned manifests;
- build and test the typed Rust adapter;
- verify the retained proof with arkworks using `[49]`;
- reject the same proof using `[7]`;
- encode canonical arkworks and version-1 Molecule artifacts;
- decode the Molecule artifacts through the pinned endpoint crates;
- host-verify the decoded artifacts through `verifier-core`;
- retain output sizes and SHA-256 hashes.

Week 9 stops before CKB-VM execution and Capsule transition tests.

## Gate 1: environment and source state

Status: **Passed and reviewed 27 July 2026**

Retain:

- standalone repository commit and worktree status;
- `groth16-ckb` commit and worktree status;
- Rust and Cargo versions;
- fixture files, sizes, and SHA-256 hashes;
- semantic JSON comparison with the retained Week 8 source files.

Retained results:

- standalone base revision: `ed06afc975ede158d37ef987f042acdc55c0062c`;
- standalone branch: `main`, aligned with `origin/main` before the uncommitted
  Week 9 scaffold;
- standalone status contained only the expected Week 9 source, fixture, and
  documentation changes;
- Rust: `rustc 1.95.0 (59807616e 2026-04-14)`;
- Cargo: `cargo 1.95.0 (f2d3ce0bd 2026-03-21)`;
- pinned endpoint revision:
  `d64c769ffe2d2edb5eb308dc59058efda77c2f83`;
- endpoint `git status --short` produced no output, confirming a clean worktree.

Committed fixture inspection:

| File | Bytes | SHA-256 |
|---|---:|---|
| `manifest.json` | 1,676 | `611aa6ee6bd113cc71bde0db986f7f4bd2558cb4b04d8c4503b6ed76544d6bc0` |
| `proof.json` | 807 | `40a963fae6ae05b22547adab882e5bb3f318e850729ded606e342980ee7e62d4` |
| `public.json` | 10 | `ff43072fcc95627d49160362f3b7023c10aa1456bb1758fd524d1b5185d5cd23` |
| `verification_key.json` | 2,932 | `c886ff510808ee21f354f9e16ede7405418276abe44c4992041be5f767612d81` |
| `wrong-public.json` | 10 | `6b76b7114eb9596b5a55eafb0a3d664e777806d53e5016c1f74b939d1a58b9f0` |

Python JSON comparisons against the retained ignored Week 8 source files
reported:

```text
vk_semantic_match= True
proof_semantic_match= True
public_semantic_match= True
```

The committed proof, verification key, and intended public vector therefore
preserve the Week 8 JSON values. Their byte hashes differ only because the
committed text files add the single trailing line-feed byte documented in the
fixture manifest.

## Gate 2: dependency lock and compilation

Status: **Passed and reviewed 27 July 2026**

Retain:

- successful `cargo generate-lockfile`;
- resolved `groth16-ckb` Git revision in `Cargo.lock`;
- `cargo check --workspace --all-targets`;
- `cargo fmt --all -- --check`;
- `cargo clippy --workspace --all-targets -- -D warnings`.

Dependency download success alone is not adapter compatibility evidence.

Lockfile results:

- `cargo generate-lockfile` returned exit code `0`;
- Cargo locked 110 packages;
- `Cargo.lock` exact size: 26,320 bytes (`ls -lh`: 26K);
- `Cargo.lock` SHA-256:
  `165c4f85eb3f36949a0ef24a02a79f16e734f5dd934376201347c88c40d19d61`;
- arkworks core pins resolved to `ark-bn254 0.5.0`, `ark-ec 0.5.0`,
  `ark-ff 0.5.0`, `ark-groth16 0.5.0`, and `ark-serialize 0.5.0`;
- `ark-snark` resolved to `0.5.1`;
- `num-bigint` resolved to `0.4.8`;
- `sha2` resolved to `0.10.9`.

All three endpoint packages resolved from the exact requested Git revision:

```text
git+https://github.com/CECILIA-MULANDI/groth16-ckb
?rev=d64c769ffe2d2edb5eb308dc59058efda77c2f83
#d64c769ffe2d2edb5eb308dc59058efda77c2f83
```

The packages were:

- `groth16-schema 0.0.0`;
- `wire-decode 0.0.0`;
- `verifier-core 0.0.0`.

The repository status after locking contained the expected Week 9 scaffold plus
the newly generated untracked `Cargo.lock`.

Compilation-quality gates:

| Command | Result | Observed build output |
|---|---|---|
| `cargo fmt --all -- --check` | Exit `0` | No formatting diff |
| `cargo check --locked --workspace --all-targets` | Exit `0` | Finished dev profile in 0.16s |
| `cargo clippy --locked --workspace --all-targets -- -D warnings` | Exit `0` | Checked `artifact-adapter 0.1.0`; finished in 0.92s |

The short `cargo check` duration indicates reuse of resolved dependencies and
build state. This is a locked compilation validation, not a clean-from-scratch
build. Clippy accepted the adapter with warnings promoted to errors.

## Gate 3: Rust test suite

Status: **Passed and reviewed 27 July 2026**

Required tests include:

- canonical scalar parser rejects a modulus-sized value instead of reducing it;
- non-canonical decimal text is rejected;
- retained proof verifies with public `[49]`;
- same proof rejects public `[7]`;
- Molecule round-trip reproduces the exact canonical byte buffers;
- pinned `verifier-core` accepts the decoded positive fixture.

Record exact test totals and exit code rather than predicting them here.

Command:

```text
cargo test --locked --workspace -- --nocapture
```

Retained result:

- locked dependencies and test targets compiled in 5.60 seconds;
- command exit code: `0`;
- library unit tests: 4 passed, 0 failed, 0 ignored;
- interoperability integration tests: 7 passed, 0 failed, 0 ignored;
- binary unit tests: 0 tests;
- documentation tests: 0 tests;
- aggregate executed tests: **11 passed, 0 failed, 0 ignored**.

The four parser-validation tests confirmed rejection of:

- a scalar equal to the BN254 scalar modulus rather than silently reducing it;
- non-canonical decimal text with a leading zero;
- a non-affine projective marker;
- off-curve G1 coordinates.

The seven interoperability tests confirmed:

- protocol mismatch rejection;
- public-input count mismatch rejection;
- the retained proof verifies in arkworks with intended public `[49]`;
- the same unchanged proof rejects public `[7]`;
- canonical bytes survive Molecule encoding and pinned endpoint decoding
  unchanged;
- the pinned `verifier-core` host path accepts the decoded positive payload;
- the pinned endpoint rejects the wrong public input after wire round trip;
- the endpoint decoder rejects wire version `2`;
- the endpoint decoder rejects a truncated Molecule witness.

This test suite establishes the cross-library host result for the single
retained public-first fixture. Release inspection, generated CLI artifacts, and
independent snarkjs re-verification are recorded separately in Gates 4 and 5.

## Gate 4: adapter CLI and generated artifacts

Status: **Passed and reviewed 27 July 2026**

Release build command:

```text
cargo build --locked --release -p artifact-adapter --bin noir-ckb-adapter
```

Retained release-build result:

- command exit code: `0`;
- optimized build completed in 18.12 seconds;
- binary: `target/release/noir-ckb-adapter`;
- exact size: 2,025,776 bytes (`ls -lh`: 1.9M);
- format: Mach-O 64-bit executable, arm64;
- SHA-256:
  `ed0f37ff16ad5c80323a3bf72bb7b81e0a22d7365bc65b421d85ac14b81d6576`.

The repository status contained only the expected uncommitted Week 9 source,
fixture, documentation, and lockfile changes.

The CLI gate required explicit positive, negative, and endpoint round-trip
results, together with the generated manifest, file sizes, file
classifications, and SHA-256 hashes.

Required filenames:

```text
vk.bin
proof.bin
public_inputs.bin
vk.mol.bin
witness.mol.bin
vk_data_hash.bin
manifest.json
```

Sizes were recorded only after execution rather than predicted from the
implementation.

CLI execution result:

```text
arkworks_positive_verify=accepted
arkworks_negative_verify=rejected
groth16_ckb_wire_roundtrip=accepted
public_input_count=1
vk_bytes=296
proof_bytes=128
public_inputs_bytes=36
vk_molecule_bytes=334
witness_molecule_bytes=194
vk_data_hash=1fa6f0c18ff7b0d32abcd01ddf2ddcc3e4190be99add55bbf2418f045eb32715
output_directory=target/week-09/adapter-output
adapter_run_exit_code=0
```

The positive result used the retained public vector `[49]`; the negative result
used `[7]` with the same proof and verification key. The round-trip result
includes decoding with the pinned endpoint crate, exact canonical-byte
comparisons, and host verification with the pinned `verifier-core` crate.

Generated artifact inspection:

| File | Bytes | SHA-256 |
|---|---:|---|
| `vk.bin` | 296 | `d1fff371445229aebd8ab9bbe99136d6cb7edc2ffc9cfbdb3d2167eb0b5b3ef2` |
| `proof.bin` | 128 | `e7f78ab7982a1f5bae7d0ca41a127441e1a2b313fd115c5f6689cc3c73128f83` |
| `public_inputs.bin` | 36 | `3ba8a49e2f3e686fd0d1400e8ca9a180f24d049dbc03f4932552eff4d31bba6d` |
| `vk.mol.bin` | 334 | `41e4aa9079d7801a218b2b660d7e9852e52cc8f884645506432e5f38ac7cd01e` |
| `witness.mol.bin` | 194 | `2f29111ce4a456dd147e352aab6c2d6ba1f270792f93e1a7e253c29037c7095b` |
| `vk_data_hash.bin` | 32 | `abc2ab2344b56daf6e2e8bc3b5c8425923a85bc49baab887231f5e8bfe159b36` |
| `manifest.json` | 1,045 | `b2b71080be8e9d3cd0e42e2db53b9d3947fa4d96c6801a9554749a66266e02a8` |

All six binary files were classified as data, and the manifest was classified
as JSON. The manifest's six sizes and hashes exactly matched the independent
`wc -c` and `shasum -a 256` results. The seven files totalled 2,065 bytes.

The raw `vk_data_hash.bin` contents were:

```text
1fa6f0c18ff7b0d32abcd01ddf2ddcc3e4190be99add55bbf2418f045eb32715
```

The `xxd` display wrapped the final four hexadecimal characters onto the next
terminal line; concatenating the two lines gives the same 32-byte value printed
by the CLI. This is the CKB data-hash value of the versioned verification-key
Molecule payload, not the SHA-256 digest of `vk_data_hash.bin` shown in the
table.

## Gate 5: independent source recheck

Status: **Passed and reviewed 27 July 2026**

The independent check reran pinned snarkjs verification against the committed
fixture:

```text
public [49] -> accept
public [7]  -> reject
```

The fixture was re-hashed after both commands to confirm that verification did
not mutate it.

Retained results:

- `npx --yes snarkjs@0.7.5 --version` printed a banner identifying
  `snarkjs@0.7.5`, followed by the command help, and returned exit code `99`;
  this invocation is recorded as version-identification output rather than a
  successful version command;
- verification with committed public vector `[49]` printed `OK!` and returned
  exit code `0`;
- verification of the same proof and key with `[7]` printed `Invalid proof`
  and returned exit code `1`, the required negative-test result;
- the verification key, proof, intended public vector, and wrong public vector
  had identical SHA-256 hashes before and after both checks.

The unchanged before-and-after fixture hashes were:

| File | SHA-256 |
|---|---|
| `verification_key.json` | `c886ff510808ee21f354f9e16ede7405418276abe44c4992041be5f767612d81` |
| `proof.json` | `40a963fae6ae05b22547adab882e5bb3f318e850729ded606e342980ee7e62d4` |
| `public.json` | `ff43072fcc95627d49160362f3b7023c10aa1456bb1758fd524d1b5185d5cd23` |
| `wrong-public.json` | `6b76b7114eb9596b5a55eafb0a3d664e777806d53e5016c1f74b939d1a58b9f0` |

This independent recheck confirms that snarkjs 0.7.5 and the Rust adapter
agree on the retained fixture's intended public-input semantics: `[49]`
accepts and `[7]` rejects.

## Claim boundary

The accepted Week 9 claim is limited to:

> One provenance-recorded, public-first Noir-derived Groth16 proof was converted
> into validated arkworks 0.5 objects, verified with the same intended public
> input in snarkjs and arkworks, encoded into the pinned groth16-ckb v1 Molecule
> format, decoded, and verified through the pinned host endpoint.

The result will not establish arbitrary Noir compatibility, production setup
security, CKB-VM execution, or proof-bound Capsule authorization.
