# CKB Groth16 endpoint reproduction

This document records the Week 7 reproduction of the existing generic Groth16 verifier endpoint. It does not claim that the Noir fixture has crossed the Groth16 compatibility boundary.

## Pinned source and environment

Repository: [`CECILIA-MULANDI/groth16-ckb`](https://github.com/CECILIA-MULANDI/groth16-ckb)

| Property | Verified value |
|---|---|
| Commit | `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |
| Worktree before reproduction | Clean |
| Rust | `rustc 1.95.0 (59807616e 2026-04-14)` |
| Cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` |
| Rust target | `riscv64imac-unknown-none-elf` |
| Node.js | `v24.3.0` |
| pnpm | `10.12.4` |

## Production CKB-VM script build

Command:

```bash
cd /Users/xiaomao/groth16-ckb
./scripts/build-ckb-script.sh
```

Retained result:

```text
Finished `release` profile [optimized] target(s) in 0.14s
built: /Users/xiaomao/groth16-ckb/script/target/riscv64imac-unknown-none-elf/release/ckb-script
build_exit_code=0
```

Binary inspection:

| Property | Verified value |
|---|---|
| Path | `script/target/riscv64imac-unknown-none-elf/release/ckb-script` |
| Size | 98,464 bytes (`ls -lh`: 96K) |
| Type | ELF 64-bit LSB executable, UCB RISC-V, RVC, soft-float ABI, version 1 (SYSV), statically linked, stripped |
| SHA-256 | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |

### Evidence boundary

Cargo completed in 0.14 seconds and reused existing build outputs; the inspected binary timestamp predated this command. This result validates that the pinned source and current locked build state complete successfully and identifies the binary used by the following tests. It is not described as a clean-from-scratch or independent reproducible build.

A clean rebuild or the repository's reproducibility workflow can be performed as a later, separately labeled check if required. It is not necessary to fabricate that stronger claim for the Week 7 endpoint baseline.

## Test evidence

### Normal Rust workspace suite

Command:

```bash
cd /Users/xiaomao/groth16-ckb
cargo test --workspace
```

Result: **Passed 15 July 2026, exit code 0.**

Executed results aggregated across the test binaries:

| Suite | Passed | Failed | Ignored |
|---|---:|---:|---:|
| Host unit tests | 3 | 0 | 0 |
| Differential/adversarial tests | 26 | 0 | 1 |
| Property tests | 2 | 0 | 0 |
| CKB integration verification tests | 8 | 0 | 0 |
| Cycle benchmark | 0 | 0 | 1 |
| **Aggregate** | **39** | **0** | **2** |

The remaining crate unit-test and doc-test binaries contained zero tests and completed successfully.

The eight CKB integration cases covered:

- trigger-Cell creation
- missing VK CellDep rejection
- truncated witness rejection
- bad witness-version rejection
- public-input count mismatch rejection
- forged-proof rejection
- valid-proof acceptance
- wrong-VK rejection

The standard suite reused compiled test artifacts (`Finished ... in 0.30s`), then executed the differential/property tests for approximately 43 seconds in total.

### Ignored Rust tests

Command:

```bash
cd /Users/xiaomao/groth16-ckb
cargo test --workspace -- --ignored --nocapture
```

Result: **Passed, exit code 0.**

| Test | Result | Duration |
|---|---|---:|
| `differential_x_squared_1000_samples` | Passed | 176.22s |
| `cycle_benchmark` | Passed | 1.27s |

The benchmark reported:

| Public inputs | CKB-VM cycles |
|---:|---:|
| 1 | 99,843,490 |
| 4 | 100,656,230 |
| 8 | 101,702,797 |
| 16 | 103,998,027 |
| 32 | 108,736,103 |
| 64 | 118,483,349 |

The ignored-suite command reused compiled test artifacts (`Finished ... in 0.23s`). The cycle values are retained from the executed benchmark, not copied from the repository README.

### Explicit CKB integration rerun

Command:

```bash
cd /Users/xiaomao/groth16-ckb
cargo test -p integration-tests
```

Result: **Passed 15 July 2026, exit code 0.** The package compiled in 1.68 seconds, all 8 verification tests passed in 0.29 seconds, none failed, and the cycle benchmark remained intentionally ignored for the explicit benchmark gate.

### Explicit cycle benchmark

Command:

```bash
cd /Users/xiaomao/groth16-ckb
cargo test -p integration-tests \
  --test cycles \
  -- --ignored --nocapture
```

Result: **Passed 15 July 2026, exit code 0.** The test passed in 1.17 seconds and reproduced the same six cycle values observed in the full ignored-suite run:

| Public inputs | CKB-VM cycles |
|---:|---:|
| 1 | 99,843,490 |
| 4 | 100,656,230 |
| 8 | 101,702,797 |
| 16 | 103,998,027 |
| 32 | 108,736,103 |
| 64 | 118,483,349 |

### TypeScript SDK

Frozen dependency installation:

```bash
cd /Users/xiaomao/groth16-ckb/sdk/ts
pnpm install --frozen-lockfile
```

Result: **Passed 15 July 2026, exit code 0.** pnpm 10.12.4 reported that the lockfile and installed dependencies were already up to date and completed in 213 ms. The repository remained clean.

pnpm also reported that the `esbuild` dependency build script was ignored and suggested `pnpm approve-builds`. No approval is assumed or recorded; the following tests determine whether the frozen installed state is sufficient.

- SDK tests: **Passed 15 July 2026, exit code 0**
  - 3 test files passed
  - 18 tests passed
  - Vitest duration: 493 ms
- SDK typecheck: **Passed 15 July 2026, exit code 0; no diagnostics**
### Square-root integration example

Frozen dependency installation:

```bash
cd /Users/xiaomao/groth16-ckb/examples/square-root
pnpm install --frozen-lockfile
```

Result: **Passed 15 July 2026, exit code 0.** pnpm 10.12.4 reported that the lockfile and dependencies were already up to date, completed in 202 ms, and left the verifier repository clean.

As with the SDK install, pnpm reported that the `esbuild` build script was ignored. No dependency build-script approval is claimed.

- example tests: **Passed 15 July 2026, exit code 0**
  - 1 test file passed
  - 6 tests passed
  - verified creation transaction shape, verifier/VK CellDeps, VK data-hash script args, trigger-Cell spend, and `WitnessArgs.input_type` placement
  - Vitest duration: 532 ms
- example typecheck: **Passed 15 July 2026, exit code 0; no diagnostics**

## Compatibility conclusion

The existing CKB verifier endpoint and its production binary are independent of the Noir control proof:

```text
Barretenberg UltraHonk control proof -> verified by Barretenberg
generic BN254 Groth16 CKB endpoint   -> build validation and Rust suites passed
Noir-to-Groth16 interoperability     -> deliberately deferred to Week 8
```
