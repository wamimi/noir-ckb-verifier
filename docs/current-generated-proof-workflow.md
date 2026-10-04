# Current generated-proof workflow

This development-only workflow uses the visibility-layout fix in the maintained
[Noir-Groth16 fork](https://github.com/wamimi/Noir-Groth16), based on James
Bachini and contributors' original backend. It is not an audit, production
setup, testnet deployment, or arbitrary Noir application generator.

## Dependencies and checkout

Use Bash or zsh, Git, Node.js/npm, a native C toolchain, and rustup. Install
Nargo/noirc `1.0.0-beta.18` (noirc revision
`99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`). On Ubuntu/Debian the CKB build also
requires `gcc-riscv64-unknown-elf`. The CLI obtains snarkjs `0.7.5` through npx;
its first invocation may need network access.

For a new workspace, from a parent directory of your choice:

```bash
git clone https://github.com/wamimi/noir-ckb-verifier.git
git clone https://github.com/wamimi/Noir-Groth16.git
git -C Noir-Groth16 checkout --detach 828025f3a0090e2934940956c0f5dc8093eb5532
git clone https://github.com/CECILIA-MULANDI/groth16-ckb.git
git -C groth16-ckb checkout --detach d64c769ffe2d2edb5eb308dc59058efda77c2f83

rustup toolchain install 1.95.0 --profile default
rustup toolchain install 1.94.1 --profile default --target riscv64imac-unknown-none-elf
cd noir-ckb-verifier
nargo --version
```

For an existing backend checkout, first inspect `git status --short` and preserve
any work. Fetch the fork commit and check it out only after the checkout is clean.
An existing clean branch at the exact revision is also accepted; detaching is
not required. Do not reset or discard local changes to satisfy the guard.

The default repository paths are sibling folders. For other locations, set
`NOIR_GROTH16_REPO` and `GROTH16_CKB_REPO` to their absolute paths.

## Build, prove, test

From `noir-ckb-verifier`, stop if any command fails:

```bash
cargo +1.95.0 build --locked --release -p noir-ckb-cli --bin noir-ckb &&
./target/release/noir-ckb build &&
./target/release/noir-ckb prove &&
./target/release/noir-ckb test
```

Expected success markers, in order:

```text
build_status=compatible
prove_status=verified
test_status=passed
ckb_vm_cases_passed=12
```

`build` checks clean external revisions and tool versions, compiles the Capsule,
builds both CKB scripts, and checks R1CS/WTNS counts and public/private values.
`prove` creates fresh development setup and a proof, checks its public vector,
and validates adapter conversion. `test` uses the generated fixture in the
Capsule transaction harness. This is local CKB-VM execution, not deployment.
The configured public vector remains `[11,65,5,66,1,96,13]`.

Runs and manifests are stored below `target/noir-ckb/proof-bound-capsule`.
New runs retain prior run directories and update the current-manifest pointers.
An old build manifest is rejected when its backend revision differs from the
configuration. Do not edit an old manifest to bypass that check.

## Compatibility and migration

The fork maps constraints and proving witnesses consistently by visibility.
Private-first and interleaved scalar fixtures were separately tested in Week 14;
the normal application harness still targets the configured Capsule binding.
Arrays, structs and Noir returns remain outside the toolkit profile. The
semantic gate still rejects the historical public `7` where `49` was intended.

Raw backend `witness` diagnostics now include `acir.wtns`; use the paired
`interop/circuit.r1cs` and `interop/witness.wtns` for proving. The CLI already
uses the latter. Regenerate setup keys and proofs when wire layout changes.
Never mix old keys with a newly compiled circuit.

The setup uses public development entropy. The Capsule commitments are arithmetic
placeholders, not a private protocol. Historical Week 8–12 guides and fixtures
retain their original revisions; they must not be relabeled as fork-generated.
