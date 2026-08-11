# `noir-ckb` developer preview

`noir-ckb` coordinates the repository's pinned, development-only path from the
supported Noir Capsule circuit to a proof-bound transaction test in CKB-VM.

The preview requires Rust 1.95.0 for the host tools, Rust 1.94.1 with the CKB
RISC-V target for the scripts, Nargo/noirc 1.0.0-beta.18, Node.js with `npx`,
and clean checkouts of the two pinned external repositories. The first snarkjs
invocation may require network access so `npx` can obtain version 0.7.5.

```bash
cargo +1.95.0 build --locked --release \
  -p noir-ckb-cli \
  --bin noir-ckb

./target/release/noir-ckb build
./target/release/noir-ckb prove
./target/release/noir-ckb test
```

The commands use [`../../noir-ckb.toml`](../../noir-ckb.toml). The two external
repositories are expected beside this repository by default:

```text
parent/
  noir-ckb-verifier/
  Noir-Groth16/
  groth16-ckb/
```

Different locations can be selected without editing the configuration:

```bash
export NOIR_GROTH16_REPO=/absolute/path/to/Noir-Groth16
export GROTH16_CKB_REPO=/absolute/path/to/groth16-ckb
```

## Command boundaries

### `noir-ckb build`

The build command checks exact compiler and repository revisions, compiles the
Noir package, builds both CKB scripts, lowers ACIR to R1CS/WTNS, and rejects any
witness layout that does not preserve the configured public/private order. It
writes a versioned build manifest below:

```text
target/noir-ckb/proof-bound-capsule/builds/<run-id>/
```

### `noir-ckb prove`

The prove command creates fresh BN254 Groth16 setup and proof artifacts with
public development entropy. It checks the exact seven-value public vector,
requires all configured negative vectors to fail, performs the arkworks and
pinned endpoint round trip, and writes CKB Molecule payloads below:

```text
target/noir-ckb/proof-bound-capsule/proofs/<run-id>/
```

The setup is deliberately unsuitable for production. Generated witnesses,
Powers of Tau files, proving keys, and proofs remain ignored by Git.

### `noir-ckb test`

The test command runs the normal host suite and supplies the latest generated
fixture to the existing 12-case CKB-VM transaction matrix. It requires one
correct proof-bound transition to pass and all invalid, mismatched, malformed,
or ambiguous cases to fail. Its JSON report is written below:

```text
target/noir-ckb/proof-bound-capsule/tests/<run-id>/test-report.json
```

## Compatibility policy

This alpha preview supports only the checked-in `proof-bound-capsule` fixture
and its pinned toolchain. A mathematically valid proof is not enough to pass
the compatibility gate. The Noir ABI, R1CS public-input count, leading witness
positions, generated public vector, serialization boundary, and CKB Cell
transition must all agree.

The command surface is not yet a stable API and does not provide a production
trusted setup, arbitrary Noir circuit support, deployment, an audit, or final
commitment and replay constructions.
