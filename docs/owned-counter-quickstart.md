# Owned counter v1 developer preview

This is one **public proof-enforcement example**, not a privacy application or a
general circuit-to-contract generator. The four-public-Field Noir circuit proves
`new_count = old_count + 1` with bounded integers. A separate application Type
checks initialization, ownership, capacity, executable-pinned VK, and the consumed
Cell's OutPoint. A standard CKB ownership Lock requires the owner's signature.
The historical Capsule commands, statement and fixtures remain separate.

**No withdrawal, destruction, transfer, recovery or upgrade exists. Application
capacity remains locked, including if the counter reaches u64 maximum.** Use
isolated development funds first. Setup uses explicitly public development entropy;
it is not a production ceremony. No audit, production security or privacy is claimed.

## Supported environment

The reproduced packaging target is macOS ARM64, Python 3.9.6 or compatible newer
Python, Cargo/Rust host 1.95.0 and contract 1.94.1 with
`riscv64imac-unknown-none-elf`, Nargo 1.0.0-beta.18 / noirc
`99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`, and snarkjs 0.7.5 via npx.
Node: CKB 0.210.0 (`2592ddf0502cd4adfe886db893cccc866db3c60f`).
Wallet tool: ckb-cli 2.0.0 (`80efc21c30e9fc7847407a217034681b6e46c763`).
The installer verifies exact archive and executable SHA-256 pins; it does not
install into PATH. Other hosts need separately tested binary pins.

Keep a clean checkout of the maintained Noir-Groth16 fork at
`828025f3a0090e2934940956c0f5dc8093eb5532`. It is based on James Bachini's
Noir-Groth16; upstream attribution and licensing remain intact. Direct verifier
libraries remain Cecilia Mulandi's groth16-ckb at
`d64c769ffe2d2edb5eb308dc59058efda77c2f83`. No upstream PR or proof-system switch
is part of this preview.

Follow [the complete bootstrap](owned-counter-bootstrap.md) first: source/backend
checkout, host/compiler installation, exact toolchain pins and all three locked
Cargo caches plus the npx cache. Its commands distinguish tested warm-cache checks
from an untested full fresh-machine installation.

## One disposable local lifecycle

From this source checkout, use new output directories on each run:

```bash
# The bootstrap already created target/counter-tools.
export COUNTER_BACKEND="$(cd ../Noir-Groth16 && pwd)"
python3 scripts/local-owned-counter.py \
  --out target/counter-local \
  --ckb target/counter-tools/ckb_v0.210.0_aarch64-apple-darwin-portable/ckb \
  --ckb-cli target/counter-tools/ckb-cli_v2.0.0_aarch64-apple-darwin/ckb-cli \
  --backend "$COUNTER_BACKEND" \
  --rpc-port 18124 --p2p-port 18125 --mutations
```

For a different backend location, set COUNTER_BACKEND to its clean pinned checkout. The local runner
creates a private, disposable **local-only** account below ignored target files,
starts a loopback dev node with no outbound peers, generates fresh development
setup/proofs, builds the Type, runs range checks, signs/broadcasts local dependency
and initialization transactions, tests the update/negative/mutation matrix,
then signs/broadcasts the update. It checks commitment and live Cells and stops
its node on completion or failure. Never reuse its development keys on testnet.
The runner refuses account directories outside the checkout's ignored `target/`.

Expected final manifest: `status: locally-validated`, with committed-and-checked
`deployment`, `creation` and `update` receipts, genesis, release hash, matrix count
and mutation status. A failed run preserves commands/errors and does not become a
successful receipt. A transaction hash alone is not confirmation. If interrupted
around a broadcast, inspect the submitted receipt and node status before retrying;
do not blindly resubmit. A new output directory creates a separate chain, not a
retry on an existing chain.

## Individual operations

`cargo run --locked --offline -p noir-ckb-cli -- counter --help` lists the fixed
client commands. This command delegates to the Python source in this checkout;
copying the Rust executable alone is not a standalone distribution.
The equivalent direct entry point is `python3 scripts/owned_counter.py`.

- `inspect --release RELEASE`: checks artifact integrity and prints the fixed
  policy, executable/VK identities and release-manifest hash; no network or wallet.
- `preflight --rpc URL --genesis HASH --out policy.json`: checks genesis and the
  standard owner executable and Type hash from genesis; records its dep group.
- `build --policy policy.json --setup SETUP --out BUILD`: verifies the completed
  setup's integrity and fixed circuit source, compiles policy/VK pins, records ELF,
  VK, source hashes and exact build flags. Non-testnet RPC is restricted to loopback.
- `prepare deploy|create|update`: constructs **unsigned** ckb-cli transaction JSON.
  Required flags are `--release`, `--rpc`, `--owner` (20-byte public identifier),
  `--funding TXHASH:INDEX`, `--out`; create/update also use `--deployment`, and
  update uses `--application TXHASH:INDEX`. Creation defaults to 200 CKB, locked
  permanently; `--capacity` is in shannons. `--fee` defaults to 1,000,000 shannons
  (0.01 CKB), paid from an ordinary funding Cell. This client selects one explicit
  funding Cell; it is not a coin-selection wallet.
- `prove --release RELEASE --rpc URL --tx UPDATE_JSON --out PROOF_DIR`: reads the
  live input, derives the four scalars, checks the setup R1CS, proves under the
  existing development key, verifies with snarkjs and the adapter, and attaches
  `input_type` while preserving other witness fields. It does not redo setup.
- `check --release RELEASE --rpc URL --tx PROOF_DIR/transaction.json --proof PROOF_DIR`:
  rechecks live input, context, owner/capacity, artifacts/deps, fee/change and proof
  before signing. Repeat after transaction assembly changes. Covered changes need
  a new proof. Raw transaction changes always need new owner signatures.
- `confirm --release RELEASE --rpc URL --tx TXFILE --hash TXHASH --out RECEIPT`:
  requires commitment, raw transaction equality, consumed inputs, and exact live
  output data/Type/Lock/capacity. Add `--deployment` for the dependency receipt.

Fresh setup alone is implemented by
`python3 scripts/setup-owned-counter.py --out SETUP --backend BACKEND`.
The local runner provides the complete tested orchestration. Do not point it at
public networks. [Testnet operator batches](owned-counter-testnet.md) start with
read-only preflight; public deployment needs explicit approval.

## Artifacts, limits and common failures

Public artifacts include circuit/R1CS, VK, Type executable, proof/public vector,
policy, transaction JSON and receipts. This circuit has no secret witness inputs;
its counter and statement are public. Local owner keys are **not** public artifacts:
keep `target/.../private/`, wallet directories and generated account state out of
logs, archives and Git. Runners never print generated key contents. Do not share
an entire target directory; use the curated evidence manifest.

Release manifests include SHA-256 integrity and CKB personalized Blake2b data hashes;
these are different algorithms and serve different purposes. Builds pin the new
VK in code, require one matching resolved VK dependency, and use immutable Data1
code resolution. Changing setup, domain or code creates a different executable
identity. This version has no migration. Owner-controlled code/VK Cells must be
retained unspent for liveness, or identical bytes redeployed and deps updated.
The client does not offer code/VK withdrawal management.

The Type supports at most 64 inputs, 64 outputs and 64 resolved deps, one application
instance per transaction, canonical 9-byte state and 33-byte args, a maximum
512-byte application WitnessArgs, and the fixed four-scalar profile. The operator
client is narrower: one application Cell plus one funding input/change output.
Fee inputs/change are outside the proof context but remain signature/policy checked.
No automatic input/output sorting occurs.

| Failure | Meaning / remedy |
| --- | --- |
| Existing output directory | Use a new directory; historical evidence is never overwritten |
| Offline dependency missing | Populate the pinned dependency cache; do not change versions |
| Setup failed | Inspect commands.json; even zero-exit snarkjs ERROR output is failure |
| Network mismatch | Use the correct policy/node; never submit a dev-domain build on testnet |
| 41 / 43 / 44 | Invalid args / state encoding / Type ID |
| 42 / 52 | Unsupported lifecycle/group shape / resource bound |
| 45 / 46 / 47 | Unsupported owner or resolved code / changed owner / changed capacity |
| 48 / 49 | Malformed or misplaced proof witness / public statement mismatch |
| 50 / 51 | Missing, duplicate or wrong pinned VK / proof verification failed |
| Standard Lock -2 / -31 in tested cases | Missing signature / signature does not authorize this transaction |
| Submitted, not committed | Poll status and diagnose rejection; never infer success from a hash |

`ckb-cli tx sign-inputs/send --skip-check` bypasses that client's restrictive
standard-template check for our custom Type; it does **not** disable the node's
script verification. Use the implemented `check` plus operator review before
signing. Invalid examples run in VM, never by intentionally broadcasting them.
