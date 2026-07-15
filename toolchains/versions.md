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
| Rust | `rustc 1.95.0` | reproduce CKB verifier and future adapter | Pending |
| Cargo | `cargo 1.95.0` | reproduce CKB verifier and future adapter | Pending |
| Node.js | `v24.3.0` | TypeScript SDK/example tests | Pending |
| npm | `11.4.2` | host tooling if needed | Pending |
| pnpm | Not recorded in preflight | verifier SDK/example tests | Pending |
| RISC-V Rust target | Not recorded in preflight | CKB-VM build | Pending |

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
