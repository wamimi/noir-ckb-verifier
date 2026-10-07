# Week 15 Phase 1 — inspection and feasibility

Historical feasibility snapshot: no new application protocol was implemented at
this stage. Toolkit baseline: `b155300c8145916a485696bf461e36f055bb5135`.
Subsequent implementation and execution results are recorded in
[Week 15 evidence](week-15.md) and [testnet evidence](week-15-testnet.md).

The required README/config/workflow, binding inventory/specification, exchange
review, architecture/threat notes and binding evidence/manifest were inspected,
alongside contract, verifier, CLI, test and validation-runner source. Retained
binding-review command logs and source files match their manifest SHA-256 values.
Their 35-test/mutation/unused-public results remain earlier recorded results;
this Phase 1 run did not repeat those entire experiments.

## Direct library feasibility reproduced

The unchanged pinned verifier script already links `no_std` verifier-core and
wire-decode; `verifier_vm.rs` installs that binary as a **Type** alongside an
always-success Lock. A fresh isolated rebuild and its two existing VM tests passed:
valid retained proof accepted; changed public state rejected with verifier code 5.
This proves direct in-Type library execution is feasible, not that the proposed
counter lifecycle or real ownership signature has been implemented.

- Generic verifier source: `d64c769ffe2d2edb5eb308dc59058efda77c2f83`; clean sibling.
- Maintained Noir-Groth16 source inspected at `828025f3a0090e2934940956c0f5dc8093eb5532`; clean sibling.
- Contract Rust 1.94.1; host tests Rust 1.95.0; target riscv64imac-unknown-none-elf.
- Fresh binary: 98464 bytes; SHA-256 `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8`.
- Positive test cycles: **101576496**; harness budget 250,000,000 (not consensus limit).
- Proof/key/public: committed `tests/fixtures/week-10-capsule`, **not fresh proving**.
- Release profile: opt-level z, LTO, codegen-units 1, overflow-checks true,
  panic abort, strip true, debug false. No debug-assertion flag added.
- Exact RUSTFLAGS: `-C target-feature=-a --remap-path-prefix=/Users/xiaomao/.cargo/registry/src=/cargo-registry --remap-path-prefix=/Users/xiaomao/.rustup/toolchains=/rustup-toolchains --remap-path-prefix=/Users/xiaomao/noir-ckb-verifier/target/week-15/phase1-01/verifier-copy=/build`.

Build command inside `target/week-15/phase1-01/verifier-copy/script`:

```bash
cargo +1.94.1 build --locked --offline --release \
  --target riscv64imac-unknown-none-elf -p ckb-script
```

The existing `verifier_vm` target ran with `--ignored --nocapture --test-threads=1`,
GROTH16_CKB_SCRIPT_BIN selecting that fresh binary and NOIR_CKB_FIXTURE_DIR selecting
the committed fixture. Full commands, cwd, environment overrides, output and exit
codes: `target/week-15/phase1-01/commands.json`. Provenance and fixture hashes:
`target/week-15/phase1-01/manifest.json`. Existing tracked/untracked source hashes
were captured in `workspace-before.json` and verified unchanged after the run.
This is the first completed feasibility run. No baseline binary was overwritten.

## Architecture comparison

| Option | Actual evidence | Integration consequence |
| --- | --- | --- |
| Directly linked verifier in Type | Fresh existing binary 98464 bytes, two VM tests pass, 101576496 cycles for the recorded retained seven-input proof | Reuse pinned byte-slice verify API; new Type adds lifecycle, VK admission and statement derivation; no child transport |
| Existing verifier Lock + Capsule Type | Earlier binding evidence documents the composition and missing admission/context/bootstrap | Keep as historical fixture; it does not meet the proposed owned lifecycle |
| Spawn/IPC verifier child | CellScript source was inspected at `35bf983db30aae80281f97e30bbce08a878d7c58`; no same-workload spawned binary was built/measured in this toolkit | Requires child identity/ABI, fd ownership, bounded transfer, Wait/failure propagation and separate resource tests; no demonstrated need for this narrow application |

No size/cycle delta between direct and spawned routes is claimed. The new four-input
application Type and its owner signature have not been built or measured. The
98,464-byte existing binary is a feasibility datum, not a predicted final size,
fee estimate, deployment receipt or directly comparable benchmark for another build.
A Spawn implementation solely to obtain a number would expand scope before the
architecture gate; direct linking is already supported by source and execution.

The pinned ckb-std Type ID helper was inspected: it hashes the first Molecule input
and u64_le output index, and permits burning. The proposed Type must explicitly
reject destruction and scan application-code counts beyond the exact Script group.
The existing CLI is Capsule-specific and has no initialization/deployment/wallet
commands; the new client functionality is proposed, not advertised as implemented.

## Environment and pending gates

Host is Darwin arm64. Nargo and Docker CLI 28.3.0 are present. Neither `ckb` nor
`ckb-cli` was found on PATH or in the checked Homebrew/local binary locations.
No Docker daemon availability, local-node lifecycle, wallet interface or testnet
connection has been validated. Supported node/wallet tooling and a disposable local-node run were still pending
at this stage. This is a pending
prerequisite, not proof that local execution is impossible. No personal wallet,
authentication files, public-network keys or funds were accessed.

The [acceptance specification](../docs/week-15-acceptance-spec.md) defines the
proposed relation, four public fields, canonical context, ownership admission,
Type ID initialization, capacity preservation, lifecycle, test/mutation matrix
and operator gates. At this stage the architecture was proposed. No Week 15 contract,
circuit or client has been implemented; none is ready for operator execution or
confirmed on testnet. No staging, commits, pushes, PRs or deployment occurred.
