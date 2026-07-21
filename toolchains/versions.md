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

Assistant source inspection observed the following dependency boundary at that revision:

```text
runtime ACIR/ACVM: Noir v1.0.0-beta.19
legacy ACIR parser: Noir v1.0.0-beta.18
locked beta.18 source: 99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
locked beta.19 source: 74d6be658e1ad252f87943292ba09bdd4da80bd4
```

Nelly reproduced these pins from the checked-out manifests and lockfile on 20 July 2026. The checkout was detached at the expected revision and `git status --short` was empty. `snarkjs` was subsequently pinned to `0.7.5` for R1CS/WTNS inspection and the development-only Groth16 experiment.

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

The Noir and Barretenberg values below were reproduced by Nelly on 15 July 2026. The remaining values were observed during assistant preflight but are not yet retained user-run evidence for the Week 7 report.

| Tool | Preflight observation | Week 7 role | Retained user evidence |
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
