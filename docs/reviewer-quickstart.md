# Reviewer quickstart

This guide provides the shortest public test of the current `noir-ckb`
developer preview. It executes a retained, non-secret Noir-derived Groth16
fixture through the production `groth16-ckb` RISC-V verifier and the
application-specific Capsule binding Type Script in CKB-VM.

The preview is pre-audit research software. It is not a production setup,
mainnet deployment, or arbitrary-Noir compatibility claim.

## What the smoke test demonstrates

The test constructs one accepted transaction and eleven rejected transactions:

```text
valid proof + intended Capsule transition       -> accept
valid proof + changed state/identity/domain     -> reject
invalid proof                                   -> reject
missing VK or truncated witness                 -> reject
malformed Cell data or Type Script args         -> reject
changed verifier lock or ambiguous input groups -> reject
```

It does not regenerate the private witness, Powers of Tau transcript, proving
key, or proof. The longer workflow is documented under
[Full generated-proof path](#full-generated-proof-path).

## Prerequisites

- Git
- [`rustup`](https://rustup.rs/)
- Bash
- a native C toolchain
- on Ubuntu/Debian, `gcc-riscv64-unknown-elf`

Install the Linux cross compiler when necessary:

```bash
sudo apt-get update
sudo apt-get install --yes gcc-riscv64-unknown-elf
```

## Clone and run

The parent directory can have any name. The two repository folder names below
are used only so the smoke script can find the generic verifier beside this
repository.

```bash
mkdir -p noir-ckb-review
cd noir-ckb-review

git clone https://github.com/wamimi/noir-ckb-verifier.git
git clone https://github.com/CECILIA-MULANDI/groth16-ckb.git

git -C groth16-ckb checkout --detach \
  d64c769ffe2d2edb5eb308dc59058efda77c2f83

rustup toolchain install 1.95.0 --profile minimal
rustup component add --toolchain 1.95.0 rustfmt clippy
rustup toolchain install 1.94.1 \
  --profile minimal \
  --target riscv64imac-unknown-none-elf

cd noir-ckb-verifier
./scripts/reviewer-smoke.sh
```

If the generic verifier is stored elsewhere, select it explicitly:

```bash
GROTH16_CKB_REPO=/absolute/path/to/groth16-ckb \
  ./scripts/reviewer-smoke.sh
```

The script validates the pinned verifier revision, records tool and source
versions, checks formatting and linting, runs the normal host suite, builds both
RISC-V scripts, and executes the 12-case CKB-VM matrix.

The final lines should have this shape:

```text
test result: ok. 12 passed; 0 failed; 0 ignored
reviewer_smoke_status=passed
ckb_vm_cases_passed=12
accepted_cycles=<machine observation>
reviewer_smoke_log=<absolute path to terminal.log>
```

The cycle value is an observation for the exact binaries and environment, not a
performance guarantee.

## Share a result

Please report both successes and failures using the
[developer-preview reproduction issue](https://github.com/wamimi/noir-ckb-verifier/issues/new?template=reproduction.yml).
Include the complete generated `terminal.log`. It contains public test data and
tool versions, but verify it before sharing. Never attach private witnesses,
secrets, `.ptau` files, or `.zkey` files.

## Full generated-proof path

The complete preview starts from the checked-in Noir source, creates fresh
development-only Groth16 artifacts, converts them into the CKB wire format, and
passes the generated fixture into the same transaction matrix. It additionally
requires:

- Nargo/noirc `1.0.0-beta.18`;
- Node.js and `npx`;
- The maintained Noir-Groth16 fork at
  `828025f3a0090e2934940956c0f5dc8093eb5532` beside this repository.

Follow the [current generated-proof setup](current-generated-proof-workflow.md)
to obtain that exact checkout. The retained smoke path above does not use this
backend and does not test the new layout correction.

After installing those dependencies:

```bash
cargo +1.95.0 build --locked --release \
  -p noir-ckb-cli \
  --bin noir-ckb

./target/release/noir-ckb build
./target/release/noir-ckb prove
./target/release/noir-ckb test
```

Expected final status fields:

```text
build_status=compatible
prove_status=verified
test_status=passed
ckb_vm_cases_passed=12
```

The generated setup uses public development entropy and must not be used in
production. Current setup instructions are in
[the generated-proof guide](current-generated-proof-workflow.md); the original
Week 10 procedure is retained in [`reproducing-week-10.md`](reproducing-week-10.md).

## Supported boundary

The current application harness supports the checked-in
`proof-bound-capsule` circuit and exact pinned toolchain. The patched backend has
additional private-first, public-first and interleaved scalar layout evidence.
The toolkit still rejects any public vector that disagrees with the configured
Noir statement, including the historical private-value exposure. It does not
yet support arbitrary Noir circuits, production commitment and
replay constructions, a production trusted setup, deployment, or an audit.
