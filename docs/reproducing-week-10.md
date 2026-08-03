# Reproducing the Week 10 proof-bound Capsule

This guide reproduces the first retained Noir-to-CKB transaction-level vertical
slice. It provides two paths:

1. **Developer preview:** use the committed public Groth16 fixture and run the
   real verifier and Capsule binding scripts in CKB-VM.
2. **Full development reproduction:** compile the Noir circuit, lower it to
   R1CS, generate a fresh development-only Groth16 proof, convert it to the CKB
   wire format, and run that fresh proof through the CKB-VM matrix.

Neither path deploys to a network. The setup and proof fixtures are for public
development testing only. The repository is experimental, pre-audit, and not
suitable for production or mainnet use.

## What the matrix demonstrates

The Capsule Cell uses two cooperating scripts:

```text
Groth16 verifier lock
  -> checks proof validity under the VK committed by data hash

Capsule binding type
  -> derives seven public inputs from the transaction
  -> checks that they equal the proof's ordered public vector
```

The ordered vector is:

```text
[
  capsule_id,
  old_state_commitment,
  old_nullifier,
  new_state_commitment,
  action_id,
  new_nullifier,
  replay_domain,
]
```

The retained development values are `[11, 65, 5, 66, 1, 96, 13]`, with the
intentionally public private fixture value `authorization_secret = 7`.

## Verified environment

The Week 10 evidence was produced with:

| Component | Pin |
|---|---|
| `noir-ckb-verifier` implementation baseline | `93627dde932304b3c6087a8501cfbf14219d0563` |
| Nargo/noirc | `1.0.0-beta.18` / source `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` |
| Noir-Groth16 | `4b7caace1f2128e454c8d0fe50cac1ec46b1e272` |
| snarkjs | `0.7.5` |
| Host Rust | `1.95.0` |
| Contract Rust | `1.94.1` |
| `groth16-ckb` | `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |
| RISC-V target | `riscv64imac-unknown-none-elf` |

Newer `noir-ckb-verifier` revisions may contain documentation or test-harness
improvements. The external backend and verifier revisions remain protocol
pins for this reproduction.

## 1. Prepare the workspace

Install Git, Node.js 18 or newer, npm, and
[`rustup`](https://rust-lang.github.io/rustup/installation/). The fast preview
does not require Node.js, npm, or Nargo; they are needed only for full artifact
regeneration.

The commands in this guide use Bash/zsh syntax. On Windows, use WSL or Git
Bash; native PowerShell uses different environment-variable syntax.

Cloning a repository does not include the GitHub username in its local folder
name. By default, the two commands below create local folders named
`noir-ckb-verifier` and `groth16-ckb`. The optional `noir-ckb-preview` parent
folder can be created anywhere and renamed freely. When testing a fork, replace
only the first clone URL with the fork URL; Git still uses
`noir-ckb-verifier` as the default local folder name.

```bash
mkdir -p noir-ckb-preview
cd noir-ckb-preview

git clone https://github.com/wamimi/noir-ckb-verifier.git
git clone https://github.com/CECILIA-MULANDI/groth16-ckb.git

cd noir-ckb-verifier

export NOIR_CKB_REPO="$PWD"
export PREVIEW_ROOT="$(dirname "$NOIR_CKB_REPO")"
export GROTH16_CKB_REPO="$PREVIEW_ROOT/groth16-ckb"

git -C "$GROTH16_CKB_REPO" checkout --detach \
  d64c769ffe2d2edb5eb308dc59058efda77c2f83

git -C "$NOIR_CKB_REPO" rev-parse HEAD
git -C "$NOIR_CKB_REPO" status --short
git -C "$GROTH16_CKB_REPO" rev-parse HEAD
git -C "$GROTH16_CKB_REPO" status --short
```

The three exported values are calculated by the shell from the current local
folder. They are only shortcuts used by later commands; they are not GitHub
usernames and do not need to be edited when the repositories were cloned side
by side with their default names. If the repositories were deliberately cloned
under different local names, update only these three assignments.

Both status commands should be empty in fresh clones. Install the two Rust
toolchains. The repository-level `rust-toolchain.toml` selects `1.95.0` for
host code; the nested `contracts/rust-toolchain.toml` selects `1.94.1` for the
CKB script.

```bash
rustup toolchain install 1.95.0 --profile default
rustup toolchain install 1.94.1 \
  --profile default \
  --target riscv64imac-unknown-none-elf

rustc +1.95.0 --version
cargo +1.95.0 --version
rustup target list --toolchain 1.94.1 --installed | \
  grep riscv64imac-unknown-none-elf
```

## 2. Fast developer preview

### Build the generic Groth16 verifier

```bash
cd "$GROTH16_CKB_REPO"

./scripts/build-ckb-script.sh

ls -lh script/target/riscv64imac-unknown-none-elf/release/ckb-script
file script/target/riscv64imac-unknown-none-elf/release/ckb-script
```

At the pinned revision, the retained binary was a 98,464-byte stripped RISC-V
ELF with SHA-256:

```text
9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8
```

### Build the Capsule binding Type Script

```bash
cd "$NOIR_CKB_REPO"

./scripts/build-capsule-binding.sh

ls -lh contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding
file contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding
```

The retained binary was a 28,032-byte stripped RISC-V ELF with SHA-256:

```text
6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962
```

On macOS, hashes can be checked with `shasum -a 256`; on Linux, use
`sha256sum`.

### Run host validation

```bash
cd "$NOIR_CKB_REPO"

cargo fmt --all -- --check
cargo check --locked --workspace --all-targets
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
```

Expected normal-suite summary:

```text
artifact-adapter unit tests:          4 passed
adapter interoperability tests:       7 passed
binary-dependent Capsule tests:      12 ignored
binary-dependent verifier tests:      2 ignored
```

### Inspect the retained adapter boundary

```bash
cd "$NOIR_CKB_REPO"

cargo build --locked --release \
  -p artifact-adapter \
  --bin noir-ckb-adapter

target/release/noir-ckb-adapter \
  --vk tests/fixtures/week-10-capsule/verification_key.json \
  --proof tests/fixtures/week-10-capsule/proof.json \
  --public tests/fixtures/week-10-capsule/public.json \
  --negative-public tests/fixtures/week-10-capsule/wrong-new-state-public.json \
  --out target/reviewer-week-10-adapter
```

Expected semantic output:

```text
arkworks_positive_verify=accepted
arkworks_negative_verify=rejected
groth16_ckb_wire_roundtrip=accepted
public_input_count=7
vk_bytes=488
proof_bytes=128
public_inputs_bytes=228
vk_molecule_bytes=526
witness_molecule_bytes=386
vk_data_hash=069bf78f701ba1bfbda0e25739eee7f5bcb069e38a654820fb7e7bc24924af9f
```

### Run the 12-case CKB-VM matrix

```bash
cd "$NOIR_CKB_REPO"

export GROTH16_CKB_SCRIPT_BIN="$GROTH16_CKB_REPO/script/target/riscv64imac-unknown-none-elf/release/ckb-script"
export CKB_CAPSULE_BINDING_SCRIPT_BIN="$NOIR_CKB_REPO/contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding"

cargo test --locked \
  -p ckb-integration-tests \
  --test capsule_transition \
  -- --ignored --nocapture
```

Expected retained matrix:

| Case | Expected result |
|---|---|
| Valid proof and intended transition | Accept |
| Valid proof and changed new state | Reject, binding code `30` |
| Valid proof and changed Capsule ID | Reject, binding code `30` |
| Valid proof and changed replay domain | Reject, binding code `30` |
| Invalid proof with transaction matching supplied wrong vector | Reject, verifier code `5` |
| Missing VK Cell dependency | Reject, verifier code `12` |
| Truncated witness | Reject, verifier code `17` |
| Malformed Capsule args | Reject, binding code `21` |
| Malformed input Cell data | Reject, binding code `25` |
| Changed output verifier lock | Reject, binding code `32` |
| Duplicate verifier-lock input | Reject, binding code `33` |
| Duplicate Capsule group input | Reject, binding code `23` |

The retained run finished with 12 passed, zero failed, and
`week10_proof_bound_capsule_cycles=101625705` for the accepted transaction.

## 3. Full artifact regeneration

The remaining sections replace the committed proof with a newly generated
development proof. Generated setup material, witnesses, and proving keys stay
under ignored `target/` directories.

### Install the pinned Noir compiler

Noir documents `noirup` as its version manager. Install it if necessary, then
select beta.18:

```bash
curl -L https://raw.githubusercontent.com/noir-lang/noirup/main/install | bash

noirup --version 1.0.0-beta.18
nargo --version
```

The expected compiler source identifier is:

```text
noirc 1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
```

### Clone and build the pinned ACIR-to-R1CS backend

```bash
cd "$PREVIEW_ROOT"

git clone https://github.com/jamesbachini/Noir-Groth16.git
export NOIR_GROTH16_REPO="$PREVIEW_ROOT/Noir-Groth16"

git -C "$NOIR_GROTH16_REPO" checkout --detach \
  4b7caace1f2128e454c8d0fe50cac1ec46b1e272

cd "$NOIR_GROTH16_REPO"
cargo +1.95.0 build --locked -p noir-cli
```

### Compile and execute the Capsule circuit

```bash
export CAPSULE_CIRCUIT="$NOIR_CKB_REPO/circuits/proof-bound-capsule"
export FULL_OUT="$NOIR_CKB_REPO/target/reviewer-full-reproduction"

cd "$CAPSULE_CIRCUIT"

nargo check
nargo compile --print-acir
nargo execute witness

gzip -t target/witness.gz
```

Expected compiler classification:

```text
private parameters: [w7]
public parameters: [w0, w1, w2, w3, w4, w5, w6]
```

### Parse, solve, and lower to R1CS/WTNS

Start with a new `FULL_OUT` path. snarkjs setup commands generally refuse to
overwrite existing artifacts.

```bash
mkdir -p "$FULL_OUT"

cd "$NOIR_GROTH16_REPO"

target/debug/noir-cli compile-r1cs \
  "$CAPSULE_CIRCUIT/target/proof_bound_capsule.json" \
  --out "$FULL_OUT/parse"

target/debug/noir-cli witness \
  "$CAPSULE_CIRCUIT/target/proof_bound_capsule.json" \
  "$CAPSULE_CIRCUIT/inputs.json" \
  --out "$FULL_OUT/witness"

target/debug/noir-cli interop \
  "$CAPSULE_CIRCUIT/target/proof_bound_capsule.json" \
  "$CAPSULE_CIRCUIT/inputs.json" \
  --out "$FULL_OUT/interop"

npx --yes snarkjs@0.7.5 r1cs info \
  "$FULL_OUT/interop/circuit.r1cs"

npx --yes snarkjs@0.7.5 wtns check \
  "$FULL_OUT/interop/circuit.r1cs" \
  "$FULL_OUT/interop/witness.wtns"

npx --yes snarkjs@0.7.5 wtns export json \
  "$FULL_OUT/interop/witness.wtns" \
  "$FULL_OUT/interop/witness.json"
```

Expected structural results:

```text
opcode_count=3
opcode_variants=AssertZero
R1CS wires=11
R1CS constraints=5
public inputs=7
private inputs=1
witness=[1,11,65,5,66,1,96,13,7,49,91]
WITNESS IS CORRECT
```

The leading public wire order is essential. The backend is not accepted for a
circuit whose public Noir witnesses do not already occupy the required leading
positions.

### Generate a development-only Groth16 proof

The following setup uses public development entropy. It is deliberately
unsuitable for production.

```bash
export GROTH16_OUT="$FULL_OUT/groth16"
mkdir -p "$GROTH16_OUT"

npx --yes snarkjs@0.7.5 powersoftau new bn128 12 \
  "$GROTH16_OUT/pot12_0000.ptau"

npx --yes snarkjs@0.7.5 powersoftau contribute \
  "$GROTH16_OUT/pot12_0000.ptau" \
  "$GROTH16_OUT/pot12_0001.ptau" \
  --name="reviewer development-only contribution" \
  -e="public-reviewer-development-entropy"

npx --yes snarkjs@0.7.5 powersoftau prepare phase2 \
  "$GROTH16_OUT/pot12_0001.ptau" \
  "$GROTH16_OUT/pot12_final.ptau"

npx --yes snarkjs@0.7.5 powersoftau verify \
  "$GROTH16_OUT/pot12_final.ptau"

npx --yes snarkjs@0.7.5 groth16 setup \
  "$FULL_OUT/interop/circuit.r1cs" \
  "$GROTH16_OUT/pot12_final.ptau" \
  "$GROTH16_OUT/circuit_0000.zkey"

npx --yes snarkjs@0.7.5 zkey contribute \
  "$GROTH16_OUT/circuit_0000.zkey" \
  "$GROTH16_OUT/circuit_final.zkey" \
  --name="reviewer circuit-specific development contribution" \
  -e="public-reviewer-circuit-entropy"

npx --yes snarkjs@0.7.5 zkey verify \
  "$FULL_OUT/interop/circuit.r1cs" \
  "$GROTH16_OUT/pot12_final.ptau" \
  "$GROTH16_OUT/circuit_final.zkey"

npx --yes snarkjs@0.7.5 zkey export verificationkey \
  "$GROTH16_OUT/circuit_final.zkey" \
  "$GROTH16_OUT/verification_key.json"

npx --yes snarkjs@0.7.5 groth16 prove \
  "$GROTH16_OUT/circuit_final.zkey" \
  "$FULL_OUT/interop/witness.wtns" \
  "$GROTH16_OUT/proof.json" \
  "$GROTH16_OUT/public.json"

npx --yes snarkjs@0.7.5 groth16 verify \
  "$GROTH16_OUT/verification_key.json" \
  "$GROTH16_OUT/public.json" \
  "$GROTH16_OUT/proof.json"
```

The final verification must report `OK`. Groth16 proof and setup artifacts are
randomized, so fresh hashes are not expected to match the retained hashes.

### Enforce the intended public semantics

```bash
node -e '
const fs = require("fs");
const actual = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const expected = ["11", "65", "5", "66", "1", "96", "13"];
console.log("actual_public_vector=", actual);
console.log("public_vector_semantic_match=", JSON.stringify(actual) === JSON.stringify(expected));
if (JSON.stringify(actual) !== JSON.stringify(expected)) process.exit(1);
' "$GROTH16_OUT/public.json"
```

Copy the public negative vectors into the generated fixture directory and
confirm that the unchanged proof rejects a changed new state:

```bash
cp "$NOIR_CKB_REPO/tests/fixtures/week-10-capsule/wrong-new-state-public.json" \
  "$GROTH16_OUT/wrong-new-state-public.json"
cp "$NOIR_CKB_REPO/tests/fixtures/week-10-capsule/wrong-capsule-id-public.json" \
  "$GROTH16_OUT/wrong-capsule-id-public.json"
cp "$NOIR_CKB_REPO/tests/fixtures/week-10-capsule/wrong-replay-domain-public.json" \
  "$GROTH16_OUT/wrong-replay-domain-public.json"

npx --yes snarkjs@0.7.5 groth16 verify \
  "$GROTH16_OUT/verification_key.json" \
  "$GROTH16_OUT/wrong-new-state-public.json" \
  "$GROTH16_OUT/proof.json"

echo "expected_wrong_new_state_exit_code=$?"
```

The expected result is `Invalid proof` with exit code `1`.

### Convert the fresh proof into CKB wire artifacts

```bash
cd "$NOIR_CKB_REPO"

cargo build --locked --release \
  -p artifact-adapter \
  --bin noir-ckb-adapter

target/release/noir-ckb-adapter \
  --vk "$GROTH16_OUT/verification_key.json" \
  --proof "$GROTH16_OUT/proof.json" \
  --public "$GROTH16_OUT/public.json" \
  --negative-public "$GROTH16_OUT/wrong-new-state-public.json" \
  --out "$FULL_OUT/adapter"
```

The adapter must report positive arkworks verification, negative rejection,
successful pinned endpoint round trip, and seven public inputs.

### Run the fresh proof in CKB-VM

`NOIR_CKB_FIXTURE_DIR` redirects only the integration tests. It does not modify
the committed fixture.

```bash
cd "$NOIR_CKB_REPO"

export GROTH16_CKB_SCRIPT_BIN="$GROTH16_CKB_REPO/script/target/riscv64imac-unknown-none-elf/release/ckb-script"
export CKB_CAPSULE_BINDING_SCRIPT_BIN="$NOIR_CKB_REPO/contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding"
export NOIR_CKB_FIXTURE_DIR="$GROTH16_OUT"

cargo test --locked \
  -p ckb-integration-tests \
  --test capsule_transition \
  -- --ignored --nocapture
```

The fresh proof must produce the same semantic matrix: one accepted intended
transition and eleven rejected invalid, malformed, ambiguous, or mismatched
transactions. Record the actual cycle count from this run rather than assuming
the retained value.

## 4. Result interpretation

A successful run establishes only the tested development path:

```text
supported public-first Noir fixture
-> pinned experimental ACIR-to-R1CS backend
-> development-only BN254 Groth16 proof
-> strict arkworks/Molecule adapter
-> production groth16-ckb verifier in CKB-VM
-> transaction-derived Capsule binding
```

It does not establish:

- general Noir circuit compatibility;
- sound public/private witness remapping for arbitrary ACIR;
- a production trusted setup;
- audited contract security;
- CKB devnet or mainnet deployment;
- a final commitment, nullifier, or replay-domain construction; or
- stable performance across toolchain changes.

## 5. Reporting a reproduction result

Include the following when opening a
[GitHub issue](https://github.com/wamimi/noir-ckb-verifier/issues):

- operating system and architecture;
- `git rev-parse HEAD` for all three repositories;
- `nargo --version`, `rustc --version`, `cargo --version`, `node --version`,
  and `npm --version` where relevant;
- the failing command and complete output;
- whether the committed or freshly generated fixture was used; and
- the two RISC-V binary hashes.

The complete retained Week 10 command/result record is available in
[`../evidence/week-10.md`](../evidence/week-10.md).
