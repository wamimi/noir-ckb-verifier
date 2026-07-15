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
| Fixture | `x=7`, `y=49` | Scaffolded; execution pending |

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

Retained output: **Pending**

Expected witness path: `target/witness.gz` (must be confirmed)

Inspection and SHA-256: **Pending**

### Optional Barretenberg control

Status: **Not run**

If run, it demonstrates only that Barretenberg can consume the Noir artifact and witness. It does not establish Groth16 or CKB compatibility.

## 3. groth16-ckb endpoint reproduction

Repository: `/Users/xiaomao/groth16-ckb`

### Source revision and environment

- commit: **Pending**
- worktree status: **Pending**
- Rust/Cargo: **Pending**
- installed RISC-V target: **Pending**
- Node/pnpm: **Pending**

### Production CKB-VM binary

- build result: **Pending**
- exact byte size / human-readable size: **Pending**
- file type: **Pending**
- SHA-256: **Pending**

### Rust and CKB integration tests

- `cargo test --workspace`: **Pending**
- `cargo test --workspace -- --ignored --nocapture`: **Pending**
- `cargo test -p integration-tests`: **Pending**
- explicit cycle benchmark: **Pending**

### TypeScript SDK and example tests

- SDK install/tests/typecheck: **Pending**
- square-root example install/tests/typecheck: **Pending**

### Excluded baseline work

- indefinite fuzzing: not run
- devnet deployment: not run

## 4. Report claims gate

The Week 7 report must not say “I rebuilt,” “I ran,” “all tests passed,” quote a binary size/hash, or quote a cycle count until the corresponding result above is populated from retained user-run output.

The report must disclose that implementation and evidence collection were completed as catch-up after the nominal 12 July week ending.
