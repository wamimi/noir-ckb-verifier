# Project history (Weeks 7–14)

This page keeps the week-by-week record that used to live in the top-level README.
It describes earlier milestones and the historical **Capsule** example, which is
not the current counter. **To try the project, use [Try the counter](try-the-counter.md).**
Commands below are kept as historical reproduction paths; the top-level
`noir-ckb build/prove/test` commands still refer to the Capsule example.

How the pipeline evolved:

```text
Week 7   Noir artifacts and the existing groth16-ckb verifier, both ends checked
Week 8   pinned ACIR-to-Groth16 backend; found it exposed a private input as public
Week 9   snarkjs -> arkworks -> CKB wire adapter
Week 10  Noir proof verified in CKB-VM and bound to a Capsule Cell transition
Week 11  packaged as noir-ckb build / prove / test
Week 12  reviewer path and direction review
Week 13  SP1 verifier evaluation (see week-13-sp1-evaluation.md)
Week 14  backend visibility fix: public values in the right wires
Week 15  owned counter, portable packaging, testnet participant path (see try-the-counter.md)
```

## Binding guarantees and current limits

The Capsule binding was reviewed on 6 October 2026 with explicit proof-reuse
tests and two isolated RISC-V check mutations. The review confirmed selected-field
comparison and cryptographic public-input binding, and showed that a valid proof
could still be reused at another OutPoint, with altered capacity, or alongside
unrelated outputs. The Capsule Type preserves the supplied Lock but does not
authenticate it as the intended verifier, and it does not support creation or
destruction. These findings shaped the owned counter's design in Week 15.
The review added 21 explicitly run VM tests (ignored by the default host
suite); the existing CLI transition matrix remains 12 cases.

## Week 10 developer preview (historical Capsule reproduction)

The fastest reviewer path uses the retained public development proof and runs
it through the real RISC-V verifier and Capsule binding scripts in CKB-VM. It
does not require a CKB node, wallet, devnet deployment, or trusted setup.

### Prerequisites

- Git
- [`rustup`](https://rustup.rs/)
- a Unix-like shell (`bash` or `zsh`)

`git clone` creates local folders named `noir-ckb-verifier` and `groth16-ckb`.
The parent directory can have any name and can live anywhere. Creating
`noir-ckb-preview` below is optional; it only keeps the two repositories next
to each other. A reviewer testing a fork changes only the first clone URL; the
default local folder remains `noir-ckb-verifier`. Run these commands in Bash,
zsh, Git Bash, or WSL:

```bash
mkdir -p noir-ckb-preview
cd noir-ckb-preview

git clone https://github.com/wamimi/noir-ckb-verifier.git
git clone https://github.com/CECILIA-MULANDI/groth16-ckb.git

cd groth16-ckb
git checkout --detach \
  d64c769ffe2d2edb5eb308dc59058efda77c2f83
cd ..

rustup toolchain install 1.95.0 --profile default
rustup toolchain install 1.94.1 \
  --profile default \
  --target riscv64imac-unknown-none-elf
```

Build the two CKB scripts:

```bash
cd groth16-ckb
RUSTUP_TOOLCHAIN=1.94.1 ./scripts/build-ckb-script.sh

cd ../noir-ckb-verifier
./scripts/build-capsule-binding.sh
```

Run the host checks. With the Week 11 candidate present, the normal suite is
expected to pass the host tests and list 14 binary-dependent CKB-VM tests as
ignored:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
```

Run the explicit 12-case CKB-VM transaction matrix:

```bash
GROTH16_CKB_SCRIPT_BIN="$(cd ../groth16-ckb && pwd)/script/target/riscv64imac-unknown-none-elf/release/ckb-script" \
CKB_CAPSULE_BINDING_SCRIPT_BIN="$PWD/contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding" \
cargo test --locked \
  -p ckb-integration-tests \
  --test capsule_transition \
  -- --ignored --nocapture
```

The retained result is:

```text
valid proof + intended Capsule transition       -> accept
valid proof + changed state/identity/domain     -> reject (binding code 30)
invalid proof                                   -> reject (verifier code 5)
missing VK, truncated witness, malformed data   -> reject
changed lock or ambiguous input groups          -> reject

test result: ok. 12 passed; 0 failed; 0 ignored
week10_proof_bound_capsule_cycles=101625705
```

The cycle count is included as a retained comparison point, not a performance
guarantee across different binaries or dependency revisions.

To regenerate the Noir, R1CS, Groth16, adapter, and CKB-VM artifacts instead
of using the retained proof fixture, follow
[`docs/reproducing-week-10.md`](reproducing-week-10.md). That guide also
lists expected intermediate output, known limitations, and the development-only
trusted-setup warning.

Review findings and reproduction failures are welcome through
[GitHub Issues](https://github.com/wamimi/noir-ckb-verifier/issues).

## Week 12 reviewer path

Week 12 closes the CKBuilder milestone around reproducibility and external
direction review. The shortest test is now one command after cloning the pinned
generic verifier and installing the documented Rust toolchains:

```bash
./scripts/reviewer-smoke.sh
```

The script records provenance, runs the host checks, builds both RISC-V scripts,
and executes the retained 12-case CKB-VM matrix. It does not regenerate private
witness or trusted-setup material. Complete setup instructions, expected output,
the full generated-proof alternative, and the support boundary are in the
[`reviewer quickstart`](reviewer-quickstart.md).

The local Week 12 results and pending external reproduction are recorded in
[`evidence/week-12.md`](../evidence/week-12.md). Any alpha release remains gated
on at least one successful independent clean-clone reproduction.

## Week 11 developer preview

Week 11 packages the verified Week 10 sequence behind a constrained alpha
command surface:

```bash
noir-ckb build
noir-ckb prove
noir-ckb test
```

The packaged path passed an evidence-retained run on the primary macOS arm64
development checkout. It checks the pinned repositories and tools, fails
closed on public/private witness-order mismatches, creates a fresh
development-only proof, converts it to the CKB wire format, and supplies it to
the existing CKB-VM transaction matrix. The fresh-proof run accepted the
intended transition and rejected all 11 negative cases. The checked-in project
and binding configuration is [`noir-ckb.toml`](../noir-ckb.toml); command behavior
and output layout are documented in
[`crates/noir-ckb-cli/README.md`](../crates/noir-ckb-cli/README.md).

```bash
cargo +1.95.0 build --locked --release \
  -p noir-ckb-cli \
  --bin noir-ckb

./target/release/noir-ckb build
./target/release/noir-ckb prove
./target/release/noir-ckb test
```

The proof setup is a single-party development setup (snarkjs mixes OS randomness with the public `-e` label; the contribution secret is not retained, but the person who ran setup could have kept it and forged proofs) and is unsuitable for
production. The retained local run covers the complete packaged command path.
The separate
[hosted retained-fixture workflow](https://github.com/wamimi/noir-ckb-verifier/actions/runs/31522089140)
passed the host checks, both RISC-V script builds, and 12-case CKB-VM matrix on
11 August 2026. A clean-clone reviewer run of the complete `build`, `prove`,
and `test` path remains a separate release gate.

## Week 7 scope

- record the exact local toolchain
- compile and execute a minimal square-root Noir circuit
- inspect the ACIR artifact, ABI, and execution witness
- optionally produce a Barretenberg control proof, clearly labeled as non-Groth16
- reproduce the existing `groth16-ckb` CKB-VM endpoint
- document the architecture, compatibility boundary, and threat boundary

Running Noir-Groth16 or Sunspot was deliberately deferred to Week 8.

## Week 8 scope

- evaluate Noir-Groth16 at pinned commit `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`
- consume the existing Noir beta.18 artifact directly
- require strict lowering and pedantic witness solving
- inspect iden3 R1CS and WTNS outputs
- create and verify a development-only BN254 Groth16 proof with pinned tooling
- confirm the exported public input is the intended `y = 49`
- retain a negative verification result and exact artifact hashes

Week 8 stops before arkworks conversion, Molecule encoding, CKB-VM verification of the Noir-derived proof, and Capsule transition tests. See [`docs/week-08-backend.md`](week-08-backend.md) and [`evidence/week-08.md`](../evidence/week-08.md).

### Week 8 compatibility finding

The pinned backend produced a valid Groth16 proof for the original private-first circuit, but exported private `x = 7` as its public input. That proof verified with `[7]` and rejected the Noir-intended `[49]`.

A separate public-first control assigned `y = 49` to leading ACIR witness `w0`. Its generated proof exported and verified with `[49]` and rejected `[7]`. This establishes a constrained working path and a regression case, not general Noir compatibility. Until witness-to-R1CS remapping is implemented, the toolchain must reject any artifact whose public witnesses do not already occupy the required leading wire positions.

## Week 9 scope

Week 9 implements the constrained cross-library path for the retained
public-first control:

```text
snarkjs BN254 Groth16 JSON
  -> validated arkworks 0.5 proof, VK, and public input
  -> arkworks positive/negative verification
  -> canonical compressed serialization
  -> groth16-ckb v1 Molecule VK and witness objects
  -> pinned endpoint decode and host verification
```

The retained fixture verified with `[49]` and rejected `[7]` in both snarkjs
0.7.5 and arkworks 0.5. The adapter emitted canonical bytes, version-1 Molecule
objects, and the VK data hash; the pinned `wire-decode` and `verifier-core`
host path decoded and accepted the positive payload. These results are limited
to one public-first compatibility fixture.

Week 9 stops before CKB-VM transaction execution and Capsule transition
binding. See [`docs/week-09-adapter.md`](week-09-adapter.md) and
[`evidence/week-09.md`](../evidence/week-09.md).

## Week 10: proof-bound Capsule

Week 10 completed the first retained transaction-level vertical slice: a
Noir-derived proof executes through the production CKB-VM verifier while an
application Type Script derives the same ordered public inputs from the
consumed and created Capsule Cells. The decisive security test keeps the proof
valid while changing the Cell transition and requires the transaction to fail.

The intended transition was accepted, while all 11 negative CKB-VM cases were
rejected at the expected verifier or binding boundary. This includes changed
state, identity, and replay-domain fields; invalid proof and malformed data;
and ambiguous Capsule or verifier-lock input groups. The explicit public tuple
and design are specified in
[`docs/week-10-proof-bound-capsule.md`](week-10-proof-bound-capsule.md),
with exact commands, exit codes, hashes, and cycle evidence in
[`evidence/week-10.md`](../evidence/week-10.md).

## Minimal circuit

The first fixture proves knowledge of a private field element `x` whose square equals the public field element `y`:

```noir
fn main(x: Field, y: pub Field) {
    assert(x * x == y);
}
```

The development fixture uses `x = 7` and `y = 49`. It is intentionally non-secret test data.

## Evidence policy

No command is recorded as successful until its complete output has been retained and reviewed. Generated proofs, benchmarks, binary hashes, test totals, and screenshots must never be inferred from documentation or a previous run.

See [`docs/artifact-inspection.md`](artifact-inspection.md) for Noir
artifact structure, [`docs/ckb-endpoint.md`](ckb-endpoint.md) for the CKB
verifier reproduction, [`evidence/week-07.md`](../evidence/week-07.md) for the
endpoint baseline, [`evidence/week-08.md`](../evidence/week-08.md) for the
Groth16 experiment, and [`evidence/week-09.md`](../evidence/week-09.md) for the
adapter and host wire-boundary results, and
[`evidence/week-10.md`](../evidence/week-10.md) for the proof-bound CKB-VM
transaction matrix. Week 11 packaged-command evidence is recorded in
[`evidence/week-11.md`](../evidence/week-11.md).

