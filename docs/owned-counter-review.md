# Test the owned-counter developer preview

This preview demonstrates a supported Noir circuit proving a public counter
increment, with CKB enforcing ownership, initialization and the specific Cell
transition. It is one fixed reference application, not yet a toolkit that can
generate arbitrary applications from your circuit.

**Limits upfront:** fixed public counter; public, development-only Groth16 setup;
local reproduction tested on macOS ARM64; no arbitrary-circuit generation;
no withdrawal/destruction from the application Cell. This is not audited or production-ready.

## Start here

You can read the evidence in your browser without installing tools, obtaining a
wallet or requesting faucet funds. To use the guided source-checkout launcher,
install Git and Python 3.9+, clone this repository, and run from its root:

```bash
python3 -B scripts/start-counter.py
```

The menu separates recorded inspection, live read-only checks, local reproduction
and prerequisite diagnostics. If the Rust CLI is already built, the equivalent is
`noir-ckb counter start`. The launcher requires this source checkout; it is not a
standalone binary or automatic system installer.

The historical top-level `noir-ckb build/prove/test` and `reviewer-smoke.sh`
exercise Capsule, not this counter. Use the counter paths below.

## Choose a review path

### 1. Inspect the existing demonstration — no wallet required

**Offline / recorded:** open the [testnet evidence](../evidence/week-15-testnet.md),
[public statement](../evidence/week-15-public/update-public.json),
[proof](../evidence/week-15-public/update-proof.snarkjs.json) and
[verification key](../evidence/week-15-public/verification-key.snarkjs.json).
With the source checkout and Python, run:

```bash
python3 -B scripts/start-counter.py inspect
```

This checks public artifact hashes and displays the recorded state 0→1 and 200 CKB.
It does not query a node or cryptographically verify the proof. For a separate
cryptographic check, install Node.js/npm, cache the pinned package once online,
and then verify the retained proof offline:

```bash
npm exec --yes --package=snarkjs@0.7.5 -- node -e 'console.log("snarkjs cached")'
npx --offline snarkjs@0.7.5 groth16 verify evidence/week-15-public/verification-key.snarkjs.json evidence/week-15-public/update-public.json evidence/week-15-public/update-proof.snarkjs.json
```

Expected proof verification: exit zero and `OK!`. This verifies an existing proof;
it does not generate a fresh proof or independently establish chain commitment.

**Live / read-only:** follow the evidence page's explorer links or run:

```bash
python3 -B scripts/start-counter.py live
```

This queries testnet and checks the three committed transactions, deployed artifact
identities, consumed input, statement, ownership and capacity. It reports current
Cell status separately. A successor spent later does not invalidate the historical
update. No signing or broadcast occurs. No current network check is claimed when
the network is unavailable; use the explicitly recorded path instead.

The application Type binds the public statement to the actual Cell operation and
verifies the proof. The conventional owner Lock requires an owner signature.
Neither a valid proof alone nor an owner signature alone is sufficient for an update.

### 2. Reproduce the complete application locally

The [bootstrap guide](owned-counter-bootstrap.md) covers the pinned compiler,
backend, Rust toolchains, dependency caches and node tools. Only this path needs
the full development toolchain. The supported reproduced environment is macOS ARM64.

```bash
python3 -B scripts/start-counter.py doctor
python3 -B scripts/start-counter.py local
```

The launcher reports missing prerequisites with remedies. Once they pass, it
chooses a fresh output directory and runs the existing disposable local lifecycle:
fresh development setup and proof generation, initialization, 48 VM cases,
three isolated mutations, and a signed update with committed Cells checked.
It creates its own local-only account and funds; you need no existing wallet or faucet.
Use `--help` for custom backend/tool paths, output directory and local ports.
`local --yes` supports non-interactive execution.

See the [quickstart](owned-counter-quickstart.md) for individual operations and
[negative-test matrix](owned-counter-test-matrix.md) for the checks. Failed runs
remain failures and retain diagnostics. Never share generated keys or entire
output directories. Full fresh-machine and independent reproduction remain unverified.

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

- Could you follow the instructions without help? Where did installation or execution fail?
- Were proof verification, owner authorization and Cell binding responsibilities clear?
- What would you want to prove in a CKB application? Do you have a Noir circuit or concrete application?
- Which public values would need to match your Cells?
- Would you try an early supported-circuit workflow with us? What would prevent adoption?

Include your revision, platform, attempted path, elapsed setup time and sanitized
errors. A concrete use case plus agreement to test is stronger demand evidence
than general interest; successful reproduction primarily validates usability.

Do not attach wallet directories, private inputs, secrets, or entire target folders.
Enthusiasm and working tests do not alone establish developer demand. Concrete
integration needs and actual reproduction attempts are the purpose of this preview.

## Source provenance

The [publication source snapshot](../evidence/week-15-public/publication-source-state.json)
records the original handoff's file hashes, not a rolling hash list for later
onboarding edits. The original five counter/SP1 commits were confirmed on GitHub
at `836f2a1fb8426a2f45ce788d4075331b8870854f`. Use `git rev-parse HEAD` to report
the exact revision of your checkout, including subsequent launcher changes. The preview is a
source-checkout workflow, not a standalone binary distribution.
