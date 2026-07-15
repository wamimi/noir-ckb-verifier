# Week 7 evidence record

**Nominal week ending:** 12 July 2026  
**Catch-up execution/finalization date:** 15 July 2026  
**Policy:** A result remains pending until Nelly runs the command, retains its complete output, and the output is reviewed.

## 1. Standalone repository

| Item | Expected | Status |
|---|---|---|
| Repository | `wamimi/noir-ckb-verifier` | Scaffolded locally; no success claim beyond file inspection |
| License | Apache-2.0 | Scaffolded |
| Circuit | private `x`, public `y`, assert `x*x == y` | Check and compilation passed 2026-07-15 |
| Fixture | `x=7`, `y=49` | Witness solved successfully 2026-07-15 |

## 2. Noir toolchain and artifacts

### Tool versions

Command:

```bash
cd /Users/xiaomao/noir-ckb-verifier
nargo --version
bb --version
```

Retained output:

```text
nargo version = 1.0.0-beta.18
noirc version = 1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
(git version hash: 99bb8b5cf33d7669adbdef096b12d80f30b4c0c9, is dirty: false)
3.0.0-nightly.20260102
```

Status: **Verified 15 July 2026**

### Type check and input validation

Command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
nargo check
```

Retained output:

```text
Note: Prover.toml already exists. Use --overwrite to force overwrite.
```

Status: **Passed 15 July 2026.** Nargo returned normally. The note is expected because the repository already contains the intentional `x=7`, `y=49` development fixture; no overwrite was requested.

### ACIR compilation

Command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
nargo compile --print-acir
```

Retained output:

```text
Compiled ACIR for main:
func 0
private parameters: [w0]
public parameters: [w1]
return values: []
ASSERT w1 = w0*w0

exit_code=0
```

Status: **Passed 15 July 2026**

Confirmed artifact path: `target/square_root.json`

Inspection:

```text
file type: JSON data
size: 894 bytes
SHA-256: 6fc139050100c3083e48f31d4a3fb051d8d96e31bfa98865d103ce12d37d57cb
artifact noir_version: 1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
artifact hash: 7259915808694063673
ABI: x = private Field; y = public Field; return type = null
```

The generated `target/` directory is ignored and the artifact itself is not committed.

### Witness execution

Command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
nargo execute witness
```

Retained output:

```text
[square_root] Circuit witness successfully solved
[square_root] Witness saved to target/witness.gz
exit_code=0
```

Status: **Passed 15 July 2026**

Confirmed witness path: `target/witness.gz`

Inspection:

```text
compressed size: 47 bytes
gzip-reported uncompressed size: 108 bytes
SHA-256: 77a911f41c3e6844ba2e66a68a693eca08aa3711dad4a274038f0c0d11dde554
gzip integrity test: exit code 0
Git ignore rule: target/
```

The macOS `file` utility described the small stream as `gzip compressed data, max compression, truncated`; this observation is retained. The dedicated `gzip -t` integrity check returned 0, and Nargo reported successful witness generation.

### Optional Barretenberg control

Proof-generation command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
mkdir -p target/bb-control
bb prove \
  -b target/square_root.json \
  -w target/witness.gz \
  --write_vk \
  --verify \
  -o target/bb-control
```

Retained generation output:

```text
Scheme is: ultra_honk, num threads: 12 (mem: 13.78 MiB)
CircuitProve: Proving key computed in 5 ms (mem: 15.83 MiB)
WARNING: computing verification key while proving. Pass in a precomputed vk for better performance. (mem: 15.83MiB)
Public inputs saved to "target/bb-control/public_inputs" (mem: 17.95 MiB)
Proof saved to "target/bb-control/proof" (mem: 17.95 MiB)
VK saved to "target/bb-control/vk" (mem: 17.95 MiB)
VK Hash saved to "target/bb-control/vk_hash" (mem: 17.95 MiB)
exit_code=0
```

Generated artifacts:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `proof` | 16,256 bytes | `f3007837a3d59f95c44edf82f670b0e3380d1079a6e7567792134aa6e46df2bd` |
| `public_inputs` | 32 bytes | `218cd422fe6a50299655006c5c9a13a4a06d5d815f4c929b876885dda1fd4652` |
| `vk` | 3,680 bytes | `c8d90d34eea356934ba880b5e5ab907540cc71602059dcbf9dd9b1ea75a5e89f` |
| `vk_hash` | 32 bytes | `4f896232c4a944d89a7c63b65e5de1797c514bcc02d8b93ac4a89c19414d45d1` |

Explicit verification command:

```bash
bb verify \
  -p target/bb-control/proof \
  -k target/bb-control/vk \
  -i target/bb-control/public_inputs
```

Retained verification output:

```text
Scheme is: ultra_honk, num threads: 12 (mem: 13.83 MiB)
Proof verified successfully (mem: 15.72 MiB)
exit_code=0
```

Status: **Generated and verified 15 July 2026**

This demonstrates only that Barretenberg can consume the Noir artifact and witness through its UltraHonk path. It does not establish Groth16 or CKB compatibility. All generated control artifacts remain under the ignored circuit `target/` directory.

## 3. groth16-ckb endpoint reproduction

Repository: `/Users/xiaomao/groth16-ckb`

### Source revision and environment

- commit: `d64c769ffe2d2edb5eb308dc59058efda77c2f83`
- worktree status: clean (`git status --short` produced no output)
- Rust: `rustc 1.95.0 (59807616e 2026-04-14)`
- Cargo: `cargo 1.95.0 (f2d3ce0bd 2026-03-21)`
- installed RISC-V target: `riscv64imac-unknown-none-elf`
- Node.js: `v24.3.0`
- pnpm: `10.12.4`

Status: **Verified 15 July 2026**

### Production CKB-VM binary

- build command result: exit code 0; Cargo finished the optimized release profile in 0.14 seconds
- exact size: 98,464 bytes (`ls -lh`: 96K)
- file type: `ELF 64-bit LSB executable, UCB RISC-V, RVC, soft-float ABI, version 1 (SYSV), statically linked, stripped`
- SHA-256: `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8`

Status: **Build validation passed and binary inspected 15 July 2026.** Cargo reused existing build outputs, as shown by the 0.14-second completion and pre-existing binary timestamp. This is not recorded as a clean-from-scratch rebuild.

### Rust and CKB integration tests

- `cargo test --workspace`: **Passed 15 July 2026, exit code 0**
  - host unit tests: 3 passed
  - differential/adversarial tests: 26 passed, 1 ignored
  - property tests: 2 passed
  - CKB integration verification tests: 8 passed
  - cycle benchmark: 1 ignored
  - aggregate executed total: 39 passed, 0 failed, 2 ignored
- `cargo test --workspace -- --ignored --nocapture`: **Passed 15 July 2026, exit code 0**
  - 1,000-sample differential test: passed in 176.22s
  - cycle benchmark: passed in 1.27s
  - measured cycles:

    | Public inputs | CKB-VM cycles |
    |---:|---:|
    | 1 | 99,843,490 |
    | 4 | 100,656,230 |
    | 8 | 101,702,797 |
    | 16 | 103,998,027 |
    | 32 | 108,736,103 |
    | 64 | 118,483,349 |
- `cargo test -p integration-tests`: **Passed 15 July 2026, exit code 0**
  - 8 verification tests passed
  - 0 failed
  - 1 cycle benchmark ignored for the explicit benchmark command
- explicit cycle benchmark: **Passed 15 July 2026, exit code 0**
  - 1 public input: 99,843,490 cycles
  - 4 public inputs: 100,656,230 cycles
  - 8 public inputs: 101,702,797 cycles
  - 16 public inputs: 103,998,027 cycles
  - 32 public inputs: 108,736,103 cycles
  - 64 public inputs: 118,483,349 cycles
  - the values exactly matched the earlier ignored-suite benchmark

### TypeScript SDK and example tests

- SDK frozen install: **Passed 15 July 2026, exit code 0**
  - lockfile already up to date
  - dependencies already up to date
  - completed in 213 ms with pnpm 10.12.4
  - pnpm warned that the `esbuild` build script was ignored
  - repository status remained clean
- SDK tests: **Passed 15 July 2026, exit code 0**
  - 3 test files passed
  - 18 tests passed
  - Vitest duration: 493 ms
- SDK typecheck: **Passed 15 July 2026, exit code 0; no diagnostics**
- square-root example frozen install: **Passed 15 July 2026, exit code 0**
  - lockfile and dependencies already up to date
  - completed in 202 ms with pnpm 10.12.4
  - pnpm warned that the `esbuild` build script was ignored
  - repository status remained clean
- square-root example tests: **Passed 15 July 2026, exit code 0**
  - 1 test file passed
  - 6 tests passed
  - transaction-shape assertions covered verifier/VK CellDeps, VK data-hash args, trigger-Cell spending, and `WitnessArgs.input_type`
  - Vitest duration: 532 ms
- square-root example typecheck: **Passed 15 July 2026, exit code 0; no diagnostics**

### Excluded baseline work

- indefinite fuzzing: not run
- devnet deployment: not run

## 4. Report claims gate

The Week 7 report must not say “I rebuilt,” “I ran,” “all tests passed,” quote a binary size/hash, or quote a cycle count until the corresponding result above is populated from retained user-run output.

The report must disclose that implementation and evidence collection were completed as catch-up after the nominal 12 July week ending.
