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

Producer command:

```bash
cd /Users/xiaomao/noir-ckb-verifier/circuits/square-root
nargo execute witness
```

Retained Nargo output:

```text
[square_root] Circuit witness successfully solved
[square_root] Witness saved to target/witness.gz
exit_code=0
```

Generated artifact:

| Property | Observed value |
|---|---|
| Path | `circuits/square-root/target/witness.gz` |
| Size | 47 bytes compressed; gzip footer reports 108 bytes uncompressed |
| SHA-256 | `77a911f41c3e6844ba2e66a68a693eca08aa3711dad4a274038f0c0d11dde554` |
| Integrity check | `gzip -t` returned exit code 0 |
| Git status | Ignored by the repository's `target/` rule |

The macOS `file` command described this very small stream as `gzip compressed data, max compression, truncated`. That description is retained as an observation, but the dedicated gzip integrity check returned success and Nargo reported successful witness solving and output.

### Interpretation

The execution witness contains the concrete assignment used to solve the circuit. It is an input to a proving backend; it is not itself a cryptographic proof.

This development fixture uses an intentionally non-secret `x = 7`, but future execution witnesses may contain genuinely private values. Witness artifacts therefore remain excluded from Git by default.

This Noir execution witness must not be confused with a CKB transaction witness. A future CKB `WitnessArgs.input_type` may carry a zero-knowledge proof and public inputs, but it must not expose the private Noir witness.

## Barretenberg control proof

This optional control checks that the compiled Noir artifact and execution witness are accepted by the installed Barretenberg backend. It does not produce Groth16 artifacts and does not establish compatibility with `groth16-ckb`.

Producer command:

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

Barretenberg reported the `ultra_honk` scheme and returned exit code 0 after writing the artifacts below:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `target/bb-control/proof` | 16,256 bytes | `f3007837a3d59f95c44edf82f670b0e3380d1079a6e7567792134aa6e46df2bd` |
| `target/bb-control/public_inputs` | 32 bytes | `218cd422fe6a50299655006c5c9a13a4a06d5d815f4c929b876885dda1fd4652` |
| `target/bb-control/vk` | 3,680 bytes | `c8d90d34eea356934ba880b5e5ab907540cc71602059dcbf9dd9b1ea75a5e89f` |
| `target/bb-control/vk_hash` | 32 bytes | `4f896232c4a944d89a7c63b65e5de1797c514bcc02d8b93ac4a89c19414d45d1` |

Because the combined prove command did not print an explicit verification result, verification was rerun as a separate evidence gate:

```bash
bb verify \
  -p target/bb-control/proof \
  -k target/bb-control/vk \
  -i target/bb-control/public_inputs
```

Retained result:

```text
Scheme is: ultra_honk, num threads: 12 (mem: 13.83 MiB)
Proof verified successfully (mem: 15.72 MiB)
exit_code=0
```

All control artifacts are under the ignored circuit `target/` directory.

### Compatibility conclusion

```text
Noir artifact + witness -> Barretenberg UltraHonk proof -> Barretenberg verification: established
Noir artifact + witness -> BN254 Groth16 -> groth16-ckb: not established in Week 7
```
