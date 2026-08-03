# Toolchain versions

Artifact compatibility is treated as part of the protocol surface. Every retained artifact must identify the exact tool and version that produced it.

## Week 7 pin

The Week 7 Noir compatibility fixture is pinned to:

```text
nargo/noirc 1.0.0-beta.18
```

This version matches the installed compiler selected for the baseline. It is not an assertion that beta.18 is the best long-term version. Sunspot's current main branch has since moved to beta.22; Week 8 therefore evaluates a backend with an explicit beta.18 compatibility parser before considering a compiler migration.

## Week 8 candidate pin

The selected Noir-Groth16 experiment targets source revision:

```text
4b7caace1f2128e454c8d0fe50cac1ec46b1e272
```

Source inspection identified the following dependency boundary at that revision:

```text
runtime ACIR/ACVM: Noir v1.0.0-beta.19
legacy ACIR parser: Noir v1.0.0-beta.18
locked beta.18 source: 99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
locked beta.19 source: 74d6be658e1ad252f87943292ba09bdd4da80bd4
```

The pins were reproduced from the checked-out manifests and lockfile on 20 July 2026. The checkout was detached at the expected revision and `git status --short` was empty. `snarkjs` was subsequently pinned to `0.7.5` for R1CS/WTNS inspection and the development-only Groth16 experiment.

Week 8 host-tool evidence currently includes:

| Tool | Retained version |
|---|---|
| Rust | `rustc 1.95.0 (59807616e 2026-04-14)` |
| Cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` |
| Nargo | `1.0.0-beta.18` |
| noirc | `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` |
| Node.js | `v24.3.0` |
| npm | `11.4.2` |
| snarkjs | `0.7.5` through `npx --yes snarkjs@0.7.5` |

`rg` was not available in the host shell, so the dependency search used the equivalent built-in `grep -nE` command.

## Evidence status

The Noir and Barretenberg values below were reproduced on 15 July 2026. Items marked pending were observed during initial environment inspection but were not part of the retained Week 7 execution record.

| Tool | Environment observation | Week 7 role | Retained evidence |
|---|---|---|---|
| Nargo | `1.0.0-beta.18` | compile and execute Noir | Verified 2026-07-15 |
| noirc | embedded `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` reported by `nargo --version` | compile Noir to ACIR | Verified 2026-07-15; source reported clean |
| Barretenberg | `3.0.0-nightly.20260102` | optional non-Groth16 control path | Verified 2026-07-15 |
| Rust | `rustc 1.95.0 (59807616e 2026-04-14)` | reproduce CKB verifier and future adapter | Verified 2026-07-15 |
| Cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` | reproduce CKB verifier and future adapter | Verified 2026-07-15 |
| Node.js | `v24.3.0` | TypeScript SDK/example tests | Verified 2026-07-15 |
| npm | `11.4.2` | host tooling if needed | Pending |
| pnpm | `10.12.4` | verifier SDK/example tests | Verified 2026-07-15 |
| RISC-V Rust target | `riscv64imac-unknown-none-elf` | CKB-VM build | Verified installed 2026-07-15 |

The `groth16-ckb` endpoint baseline is pinned to commit:

```text
d64c769ffe2d2edb5eb308dc59058efda77c2f83
```

Its worktree was clean when the Week 7 reproduction began.

There is no standalone `noirc` executable in the current `PATH`. The embedded compiler version is reported by `nargo --version`, so `noirc --version` is not part of the command record.

## Artifact provenance requirements

For every generated fixture, retain:

- producer command
- producer version and, where applicable, source revision
- artifact path and SHA-256 digest
- whether the artifact contains private witness material
- expected consumer and format assumptions
- verification results from each implementation that consumed it

NB: Do not commit proving keys, toxic-waste inputs, private application witnesses, or large generated build directories.

## Week 9 adapter pins

The Week 9 Rust workspace requests arkworks `0.5` and pins its CKB wire boundary
to `groth16-ckb` revision:

```text
d64c769ffe2d2edb5eb308dc59058efda77c2f83
```

The pinned packages are `groth16-schema`, `wire-decode`, and `verifier-core`.
`Cargo.lock` was generated and reviewed on 27 July 2026. It resolved:

| Package | Locked version/source |
|---|---|
| `ark-bn254` | `0.5.0` |
| `ark-ec` | `0.5.0` |
| `ark-ff` | `0.5.0` |
| `ark-groth16` | `0.5.0` |
| `ark-serialize` | `0.5.0` |
| `ark-snark` | `0.5.1` |
| `groth16-schema` | Git revision `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |
| `wire-decode` | Git revision `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |
| `verifier-core` | Git revision `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |

The lockfile is 26,320 bytes with SHA-256
`165c4f85eb3f36949a0ef24a02a79f16e734f5dd934376201347c88c40d19d61`.

The locked release build completed on 27 July 2026. The resulting
`noir-ckb-adapter` binary was a 2,025,776-byte arm64 Mach-O executable with
SHA-256:

```text
ed0f37ff16ad5c80323a3bf72bb7b81e0a22d7365bc65b421d85ac14b81d6576
```

The pinned snarkjs invocation identified itself as `snarkjs@0.7.5`. Its
`--version` form also printed the full command help and returned exit code 99,
so the evidence records that output as version identification rather than a
successful version command.

## Week 10 CKB-VM pins

The Week 10 Capsule fixture retains the Week 8 and Week 9 compiler, backend,
snarkjs, arkworks, and `groth16-ckb` revisions above. The host integration
workspace is pinned by the root `rust-toolchain.toml` and was checked with:

```text
rustc 1.95.0 (59807616e 2026-04-14)
cargo 1.95.0 (f2d3ce0bd 2026-03-21)
```

The separate no-std contract workspace pins:

| Component | Pinned version/source |
|---|---|
| Contract Rust | `1.94.1` |
| RISC-V target | `riscv64imac-unknown-none-elf` |
| `ckb-std` | `1.1.0` |
| `ckb-gen-types` | `1.1.0` |
| `ckb-hash` | `1.1.0` |
| `wire-decode` | Git revision `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |

The contract lockfile is 5,835 bytes with SHA-256
`22749bccbd156bd7a408e0c6dd8608a7c92b99b76cca181e8867b82ff2ab5aff`.
The resulting 28,032-byte Capsule binding RISC-V binary has SHA-256
`6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962`.

The expanded host workspace lockfile, including `ckb-testtool`, is 67,131
bytes with SHA-256
`0615a881dde5a10fd62c13beef8335c532af1f152aa7051cd0467e4a9b0d1d82`.
