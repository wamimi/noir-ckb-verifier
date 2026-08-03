# Week 11 developer preview plan

## Objective

Week 11 should package the verified Week 10 path into a small reviewer-facing
command surface:

```bash
noir-ckb build
noir-ckb prove
noir-ckb test
```

The milestone is not a production SDK or network deployment. It is an external
developer preview that makes the supported path repeatable without requiring a
reviewer to manually coordinate Nargo, Noir-Groth16, snarkjs, the Rust adapter,
two RISC-V builds, and CKB-VM environment variables.

## Proposed command contract

### `noir-ckb build`

Inputs:

- a supported Noir package;
- its ABI-shaped public development input file;
- a versioned binding manifest;
- pinned tool and source revisions.

Responsibilities:

- verify the Nargo/noirc version;
- compile the Noir package;
- inspect the ABI and ACIR witness visibility;
- run strict ACIR-to-R1CS lowering;
- validate that public wires occupy the required R1CS positions;
- reject incompatible layouts before setup or proof generation;
- build the adapter and both RISC-V scripts; and
- write a build manifest with source revisions and artifact hashes.

### `noir-ckb prove`

Responsibilities:

- solve the development witness;
- check the emitted WTNS against the R1CS;
- consume an explicitly selected development setup;
- generate proof, verification key, and public vector;
- compare the public vector with the binding manifest;
- run positive and required negative source-verification checks;
- convert validated objects into canonical arkworks and Molecule artifacts; and
- write the VK data hash and artifact manifest.

The first preview must label all bundled setup material as development-only. It
must not silently create or describe a production ceremony.

### `noir-ckb test`

Responsibilities:

- run host parser and interoperability tests;
- execute the generated proof through the generic verifier in CKB-VM;
- construct the Capsule input/output transition from the binding manifest;
- run the correct-transition acceptance case;
- run valid-proof/wrong-transition cases;
- run malformed, invalid-proof, missing-dependency, changed-lock, and
  group-ambiguity cases;
- report script exit codes and accepted-transaction cycles; and
- emit a concise machine-readable test report.

## Binding manifest

The first manifest should make public-input meaning explicit instead of
inferring it from filenames or parameter positions. A candidate shape is:

```toml
version = 1
circuit = "proof-bound-capsule"
action = "update"

[[public_inputs]]
name = "capsule_id"
source = "type_args.capsule_id"

[[public_inputs]]
name = "old_state_commitment"
source = "input_cell.data.state_commitment"

[[public_inputs]]
name = "old_nullifier"
source = "input_cell.data.nullifier"

[[public_inputs]]
name = "new_state_commitment"
source = "output_cell.data.state_commitment"

[[public_inputs]]
name = "action_id"
source = "constant.update_action_id"

[[public_inputs]]
name = "new_nullifier"
source = "output_cell.data.nullifier"

[[public_inputs]]
name = "replay_domain"
source = "type_args.replay_domain"
```

This is a design candidate, not a committed stable schema. Week 11 should test
whether the manifest can drive both transaction construction and negative-test
generation before its field names are stabilized.

## Deliverables

- one top-level CLI binary named `noir-ckb`;
- `build`, `prove`, and `test` subcommands;
- a checked-in development configuration for `proof-bound-capsule`;
- explicit toolchain and repository-pin validation;
- a versioned binding-manifest draft;
- deterministic output directory layout;
- readable human output plus a JSON result manifest;
- clean-clone reproduction on the primary development platform;
- CI for formatting, clippy, host tests, and the retained CKB-VM fixture;
- installation and five-minute quick-start documentation; and
- an issue template for external reproduction feedback.

## Acceptance criteria

The Week 11 preview is complete only when a clean-clone reviewer can run the
documented commands and observe:

```text
build: compatible circuit and scripts produced
prove: intended seven-field public vector preserved
test:  correct transition accepted
test:  wrong transition rejected
```

The CLI must also fail clearly for:

- the private-first Week 8 regression circuit;
- a compiler or backend revision mismatch;
- a public-input count or ordering mismatch;
- missing RISC-V binaries or setup material; and
- malformed generated artifacts.

## Explicit non-goals

- production trusted setup
- arbitrary Noir circuit support
- devnet or mainnet deployment
- final Capsule commitment and replay construction
- stable public API promise
- audit or production-readiness claim

## Suggested implementation order

1. Extract the existing adapter CLI into a top-level `noir-ckb` command.
2. Define the output directory and JSON result manifest.
3. Implement toolchain and source-revision preflight checks.
4. Wrap the retained build, prove, and test commands without changing their
   semantics.
5. Add the binding-manifest experiment and generate the seven-field vector.
6. Preserve the Week 8 public-wire mismatch as a required CLI rejection case.
7. Add CI and run the clean-clone reviewer workflow.
8. Invite external testing and triage reproducibility feedback before adding
   network deployment.
