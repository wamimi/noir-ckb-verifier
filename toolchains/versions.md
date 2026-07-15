# Toolchain versions

Artifact compatibility is treated as part of the protocol surface. Every retained artifact must identify the exact tool and version that produced it.

## Week 7 pin

The Week 7 Noir compatibility fixture is pinned to:

```text
nargo/noirc 1.0.0-beta.18
```

This version matches the installed compiler selected for the baseline and the version currently required by Sunspot. It is not an assertion that beta.18 is the best long-term version. The Week 8 backend selection must pin the compiler and backend together.

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

Do not commit proving keys, toxic-waste inputs, private application witnesses, or large generated build directories.
