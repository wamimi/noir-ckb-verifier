# Artifact inspection

This document records structural observations about generated artifacts without committing the generated files themselves.

## ACIR program artifact

Producer command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
nargo compile --print-acir
```

Verified producer:

```text
nargo 1.0.0-beta.18
noirc 1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
```

Compiler output:

```text
Compiled ACIR for main:
func 0
private parameters: [w0]
public parameters: [w1]
return values: []
ASSERT w1 = w0*w0
```

Generated artifact:

| Property | Observed value |
|---|---|
| Path | `circuits/square-root/target/square_root.json` |
| File type | JSON data |
| Size | 894 bytes |
| SHA-256 | `6fc139050100c3083e48f31d4a3fb051d8d96e31bfa98865d103ce12d37d57cb` |
| Artifact `noir_version` | `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` |
| Artifact `hash` | `7259915808694063673` |
| Base64 bytecode text length | 152 characters |

Top-level JSON keys:

```text
abi
bytecode
debug_symbols
expression_width
file_map
hash
noir_version
```

The ABI records:

| Parameter | Noir type | Visibility |
|---|---|---|
| `x` | `Field` | private |
| `y` | `Field` | public |

The ABI return type is `null`, matching the circuit's lack of a return value. The ACIR text expresses the intended constraint directly as `w1 = w0*w0`.

### Interpretation

This artifact is a compiled, versioned circuit description with ABI metadata. It contains no concrete `x = 7` or `y = 49` assignment and is not a cryptographic proof.

The artifact is excluded from Git by `circuits/**/target/`. Its digest is retained so a later backend experiment can identify the exact compiler output it consumed.

## Execution witness

Status: **Pending `nargo execute witness`**

The witness artifact will be inspected only after the execution command succeeds. It may contain private witness values and will remain excluded from Git.
