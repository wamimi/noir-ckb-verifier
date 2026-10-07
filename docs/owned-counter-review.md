# Test the owned-counter developer preview

This preview demonstrates a supported Noir circuit proving a public counter
increment, with CKB enforcing ownership, initialization and the specific Cell
transition. It is one fixed reference application, not yet a toolkit that can
generate arbitrary applications from your circuit.

## Start here: choose the counter, not the historical Capsule

The counter uses `scripts/local-owned-counter.py` and `noir-ckb counter ...`.
The top-level `noir-ckb build/prove/test` and `scripts/reviewer-smoke.sh` still
exercise Capsule. Neither accepts your external circuit as a new application.
For a new machine, begin with [complete prerequisites](owned-counter-bootstrap.md).
For a quick no-wallet view from this source checkout:

```bash
python3 -B scripts/review-counter.py
```

This prints **recorded evidence**, not a live transaction. To refresh read-only:

```bash
python3 -B scripts/review-counter.py --rpc https://testnet.ckb.dev
```

Expected: three committed transactions, state 0→1, 200 CKB, consumed input and
current successor status. No keys, signatures or broadcasts. The portable public
manifest is [here](../evidence/week-15-public/deployment.json); historical local
paths are unnecessary. A currently spent successor does not invalidate the
historical committed update; its current status is shown separately.

## Choose a review path

### 1. Inspect the deployed demonstration — no wallet required

Open the [deployment, initialization and update evidence](../evidence/week-15-testnet.md).
Follow its explorer links and compare the initial and successor Cell data,
ownership, capacity, and consumed input. State encoding is a version byte `01`
followed by a little-endian u64: zero is `010000000000000000`, and one is
`010100000000000000`.

This is read-only review, not a browser playground. You cannot update the
maintainer-owned counter without its ownership signature. Do not request or
share its keys.

### 2. Run your own disposable local instance

Follow the [local quickstart](owned-counter-quickstart.md). The reproduced platform
is macOS ARM64. Start with the toolchain/cache prerequisites; the runner uses
offline builds and will not install every prerequisite automatically.

The local workflow generates development artifacts, starts an isolated node,
creates an account, initializes the counter, proves an update, and checks the
committed Cells. It always runs the negative matrix; `--mutations` additionally runs isolated
mutations. Expected evidence includes 48 VM cases and three detected mutations.
See the [test matrix](owned-counter-test-matrix.md) for what those checks mean.

Use new output directories. Never reuse generated local account keys publicly.
The installed Rust executable alone is not a standalone package: current counter
commands require the Python scripts and source checkout.

### 3. Deploy your own testnet instance — advanced/operator-assisted

Use the [testnet workflow](owned-counter-testnet.md) after local reproduction.
It requires your own testnet account, funds, network-specific build and explicit
signing. Public example receipts are evidence, not portable configuration for a
fresh setup/VK. The guide gives reusable, separately reviewed operator batches; it is not an
automated public-deployment script.

The demonstrated code/VK occupied 113,872 CKB, plus 200 CKB for the application,
ordinary change and fees. Recalculate from your artifacts. Use faucet test tokens,
never mainnet funds. Application capacity has no withdrawal path. Funding split
across Cells may require consolidation because this client selects one funding
Cell. Review unsigned transactions before signing and confirm before retries.

## Feedback that helps decide the product direction

Please use the **Owned counter v1 preview review** issue template. Separate:

- Reproduction: platform, revision, steps attempted, elapsed setup time, exact
  failure or success, and whether you inspected, ran locally, or used testnet.
- Application need: what you want to build, what the proof would establish,
  which Cell operation it would authorize, and the specific missing capability
  preventing integration today.
- Follow-up: whether you would test a supported integration for that use case.

Do not attach wallet directories, private inputs, secrets, or entire target folders.
Enthusiasm and working tests do not alone establish developer demand. Concrete
integration needs and actual reproduction attempts are the purpose of this preview.

## Source provenance

The [publication source snapshot](../evidence/week-15-public/publication-source-state.json)
records hashes for the publishable source and evidence. Use a published commit
containing this guide when reporting reproduction results. The preview is a
source-checkout workflow, not a standalone binary distribution.
