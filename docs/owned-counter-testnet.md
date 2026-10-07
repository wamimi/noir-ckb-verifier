# Counter v1: checked testnet operator batches

The existing operator-run deployment, initialization and update are confirmed;
see [receipts](../evidence/week-15-testnet.md). They authorize no further spending.
This guide is for **your own instance**, after the [local quickstart](owned-counter-quickstart.md).
Use the [bootstrap](owned-counter-bootstrap.md), macOS ARM64 pins and a source
revision containing this application. Run from the repository root in one Bash/zsh
session. No mainnet. Never send anyone passwords, keys, seed phrases or wallet files.

Each numbered batch ends at a review gate. In assisted execution, return only its
public output and wait for it to be checked before continuing. These are documented
commands, not authorization to execute signing or broadcasts. The lifecycle tools
were exercised locally and on testnet; account creation and consolidation below
were checked against pinned CLI help, not rerun during the documentation pass.

## 1. Variables and read-only preflight

Prerequisites: bootstrap complete, fresh output directory, reachable testnet RPC.
Creates local policy only; no signing, broadcast or spending. Keep an existing
policy intact: choose a new run directory instead of overwriting it.

```bash
export COUNTER_CLI="$PWD/target/counter-tools/ckb-cli_v2.0.0_aarch64-apple-darwin/ckb-cli"
export COUNTER_RPC=https://testnet.ckb.dev
export COUNTER_RUN="$(mktemp -d "$PWD/target/counter-testnet.XXXXXX")"
export COUNTER_GENESIS=0x10639e0895502b5688a6be8cf69460d76541bfa4821629d86d62ba0aae3f9606
git rev-parse HEAD
git status --short
"$COUNTER_CLI" --version
python3 scripts/owned_counter.py preflight --rpc "$COUNTER_RPC" --genesis "$COUNTER_GENESIS" --out "$COUNTER_RUN/policy.json"
```

Expected: pinned ckb-cli 2.0.0; policy with exact genesis above and standard-owner
code/data identities. HTTP failures are failures; TLS remains enabled. **Stop and
check** source state and policy. A different genesis is never acceptable.

## 2. Development setup and testnet build

Prerequisites: step 1 accepted, clean pinned backend, populated caches and compiler
exports from bootstrap. Writes development setup/build artifacts; no chain changes.
A new setup has a new VK and therefore a different executable identity. Never mix
a fresh setup with the maintainer's deployment receipt or a local-network build.

```bash
python3 scripts/setup-owned-counter.py --out "$COUNTER_RUN/setup" --backend "$COUNTER_BACKEND"
python3 scripts/owned_counter.py build --policy "$COUNTER_RUN/policy.json" --setup "$COUNTER_RUN/setup" --out "$COUNTER_RUN/build"
export COUNTER_RELEASE="$COUNTER_RUN/build/release.json"
python3 scripts/owned_counter.py inspect --release "$COUNTER_RELEASE"
```

Alternatively, use the setup directory from **your own completed local run**, with
its intact manifest, in `--setup`; still build again for the testnet policy. Do not
copy ignored maintainer artifacts. Expected: setup passed, artifacts-verified and
release SHA-256. **Stop and retain hashes.** Setup is public single-party development
material, not a production ceremony. State and circuit inputs are public.

## 3. Operator account and public identity

Prerequisites: an isolated testnet wallet directory chosen by you. The commands
below create a new account locally, with an interactive password; no broadcast or
spending. If using an existing dedicated testnet account, skip `account new` and
set its directory/identifier yourself. Never use the local runner's development key.

```bash
export CKB_CLI_HOME="$COUNTER_RUN/operator-wallet"
"$COUNTER_CLI" --local-only account new
```

**Stop.** Save the password privately. Set the following public variables from the
account output; values shown here are prompts, not usable account identifiers:

```bash
printf 'Public testnet ckt address: '; read -r COUNTER_ADDRESS
printf 'Public account identifier (lock_arg): '; read -r COUNTER_ACCOUNT
"$COUNTER_CLI" --local-only --output-format json util key-info --address "$COUNTER_ADDRESS"
printf 'Verified 0x-prefixed 20-byte lock_arg: '; read -r COUNTER_OWNER
```

Check the address is testnet and uses the standard sighash Lock. `COUNTER_OWNER`
must match the account's lock_arg. **Stop and check public identity only.** Never
attach `operator-wallet` or the entire run directory to evidence.

## 4. Funding and single-Cell selection

Get test CKB using the faucet linked by the official
[testnet documentation](https://docs.nervos.org/docs/getting-started/blockchain-setup/testnet).
Faucet availability is external. Funding spends no mainnet CKB. Capacity is value
held in Cells, separate from transaction fees. The deployed example occupied
113,872 CKB for code/VK; add 200 CKB permanently locked in the app, at least 61 CKB
ordinary change and fees. Recalculate from **your** artifacts:

```bash
python3 -c 'import json,os; r=json.load(open(os.environ["COUNTER_RELEASE"])); print("dependency capacity CKB:",sum(61+a["bytes"] for a in r["artifacts"].values())); print("also reserve app 200 CKB, change >=61 CKB, and fees")'
"$COUNTER_CLI" --url "$COUNTER_RPC" wallet get-live-cells --address "$COUNTER_ADDRESS" --limit 15
```

Read-only. Expected: live empty, untyped Cells owned by this address. The wallet
listing requires an indexer-capable endpoint. If it fails, use the faucet's confirmed
transaction/explorer outputs; do not infer a Cell exists from the faucet request.
Select one sufficient output, then inspect it with `get_live_cell` below.
The application client accepts **one** funding Cell, not automatic coin selection.
Our operator received two 100,000 CKB Cells and needed consolidation first.

```bash
printf 'Selected funding OutPoint (0xhash:decimal-index): '; read -r COUNTER_FUNDING
python3 -B - "$COUNTER_RPC" "$COUNTER_FUNDING" <<'CHECK'
import sys,json
sys.path.insert(0,'scripts')
import owned_counter as c
print(json.dumps(c.live(sys.argv[1],c.op(sys.argv[2])),indent=2))
CHECK
```

**Stop** and check amount, Lock, empty data, no Type and liveness.

### Optional consolidation — separate approval and confirmation

Only when necessary, select two ordinary empty funding Cells belonging to the same
account. The following builds an unsigned self-payment; it does not broaden the
counter transaction builder. Set hashes/indices from checked live outputs. Choose
output capacity equal to their total **minus a reviewed fee** (for exactly two
100,000 CKB inputs and a 0.01 CKB fee: `199999.99`). Do not use that amount for
other input values. Check the serialized fee rate before approving.

```bash
printf 'First transaction hash: '; read -r FUND_A_HASH
printf 'First output index: '; read -r FUND_A_INDEX
printf 'Second transaction hash: '; read -r FUND_B_HASH
printf 'Second output index: '; read -r FUND_B_INDEX
printf 'Total minus reviewed fee, in CKB: '; read -r CONSOLIDATED_CKB
export COUNTER_TX="$COUNTER_RUN/consolidation.json"
"$COUNTER_CLI" tx init --tx-file "$COUNTER_TX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx add-input --tx-file "$COUNTER_TX" --tx-hash "$FUND_A_HASH" --index "$FUND_A_INDEX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx add-input --tx-file "$COUNTER_TX" --tx-hash "$FUND_B_HASH" --index "$FUND_B_INDEX"
"$COUNTER_CLI" tx add-output --tx-file "$COUNTER_TX" --to-sighash-address "$COUNTER_ADDRESS" --capacity "$CONSOLIDATED_CKB"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx info --tx-file "$COUNTER_TX"
```

**Stop** to review sole output, owner and fee. Use steps 6 and 7 separately only
with operator approval. After submission, verify committed raw transaction and
live output, without requiring an application release:

```bash
python3 -B - "$COUNTER_RPC" "$COUNTER_TX" "$COUNTER_HASH" <<'CHECK'
import sys,json
sys.path.insert(0,'scripts')
import owned_counter as c
c.network(sys.argv[1],'0x10639e0895502b5688a6be8cf69460d76541bfa4821629d86d62ba0aae3f9606')
e=json.load(open(sys.argv[2]))['transaction']; q=c.rpc(sys.argv[1],'get_transaction',[sys.argv[3]])
c.require(q and q['tx_status']['status']=='committed','not committed; stop')
c.require(all(q['transaction'][k]==v for k,v in e.items() if k!='witnesses'),'raw transaction mismatch')
c.require(len(e['outputs'])==1,'expected one self-payment')
x=c.live(sys.argv[1],dict(tx_hash=sys.argv[3],index='0x0'))
c.require(x['output']==e['outputs'][0] and x['data']['content']==e['outputs_data'][0],'live output differs')
print('committed-and-output-checked')
CHECK
export COUNTER_FUNDING="$COUNTER_HASH:0"
```

**Stop and check** before deploying. Consolidation spends a fee, not app capacity.

## 5. Prepare deployment

Prerequisites: checked release, supported owner and sufficient single live funding
Cell. Unsigned local JSON only; no signing/broadcast/spending:

```bash
export COUNTER_TX="$COUNTER_RUN/deploy.json"
python3 scripts/owned_counter.py prepare deploy --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --out "$COUNTER_TX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx info --tx-file "$COUNTER_TX"
```

Expected outputs: code index0, VK index1, owner change index2; default fee0.01 CKB.
**Stop** and compare artifact hashes/capacities/owner before signing.

## 6. Sign the reviewed transaction — operator only

Prerequisite: the specific `COUNTER_TX` has been reviewed and signing approved.
Signs locally, changes its JSON; no broadcast. Enter password privately.

```bash
"$COUNTER_CLI" --url "$COUNTER_RPC" tx sign-inputs --tx-file "$COUNTER_TX" --from-account "$COUNTER_ACCOUNT" --add-signatures --skip-check
```

**Stop**. `--skip-check` bypasses ckb-cli's restrictive template check, never node
verification. For an update, repeat the `check` command in step 10 after signing.
A changed raw transaction needs new signatures; a changed proof-bound field also
needs a new proof. Never reuse a stale proof/signature.

## 7. Submit only after separate operator approval

Prerequisite: reviewed signed transaction, no previous unresolved submission.
**Broadcasts**, consumes inputs, pays fees and creates the reviewed Cells:

```bash
"$COUNTER_CLI" --url "$COUNTER_RPC" tx send --tx-file "$COUNTER_TX" --skip-check
```

**Stop** and retain the returned hash. A timeout may occur after acceptance: check
status before any retry, never automatically rebroadcast. Set only the actual hash:

```bash
printf 'Returned transaction hash: '; read -r COUNTER_HASH
"$COUNTER_CLI" --url "$COUNTER_RPC" rpc get_transaction --hash "$COUNTER_HASH"
```

Read-only; pending/proposed is not confirmed. Proceed to the matching confirmation
batch only when committed. On error preserve output, diagnose and retest first.

## 8. Confirm deployment

Prerequisite: committed deployment from steps 5–7. Read-only RPC, new local receipt:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --deployment --out "$COUNTER_RUN/deployment-receipt.json"
export COUNTER_FUNDING="$COUNTER_HASH:2"
```

Require `committed-and-cells-checked`, matching release/network/code/VK and exact
live outputs. **Stop**. Preserve code/VK Cells unspent for availability.

## 9. Initialize and confirm zero

Prerequisite: accepted deployment receipt and its live change output. Builds
unsigned creation; application capacity **200 CKB has no withdrawal/destruction
path**. This is permanent for this protocol, not a refundable demo deposit.

```bash
export COUNTER_TX="$COUNTER_RUN/create.json"
python3 scripts/owned_counter.py prepare create --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --deployment "$COUNTER_RUN/deployment-receipt.json" --out "$COUNTER_TX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx info --tx-file "$COUNTER_TX"
```

**Stop**: inspect Type ID, same owner, count zero, capacity, change and fee. Then
perform steps 6 and 7 as separate approved batches. After commitment:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --out "$COUNTER_RUN/creation-receipt.json"
export COUNTER_APPLICATION="$COUNTER_HASH:0"
export COUNTER_FUNDING="$COUNTER_HASH:1"
```

**Stop**. Require checked live app output0 and funding change output1. No proof is
needed for fixed zero initialization; the Type checks it directly.

## 10. Prepare, prove and check one update

Prerequisite: checked live initial application and funding change; original setup
intact. Writes unsigned JSON/proof; read-only RPC; no signing/broadcast/spending.

```bash
python3 scripts/owned_counter.py prepare update --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --application "$COUNTER_APPLICATION" --deployment "$COUNTER_RUN/deployment-receipt.json" --out "$COUNTER_RUN/update-unsigned.json"
python3 scripts/owned_counter.py prove --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_RUN/update-unsigned.json" --out "$COUNTER_RUN/update-proof"
export COUNTER_TX="$COUNTER_RUN/update-proof/transaction.json"
python3 scripts/owned_counter.py check --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --proof "$COUNTER_RUN/update-proof"
```

Expected `checked-before-signing`: old0/new1, exact input OutPoint, same owner and
capacity, verified proof and fee. **Stop**. Perform step 6, repeat the `check`
command above, stop again, and only then perform approved step 7.

## 11. Confirm update and retain public evidence

Prerequisite: committed update; read-only RPC and new local receipt:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --out "$COUNTER_RUN/update-receipt.json"
```

Require `committed-and-cells-checked`, consumed intended input and exact successor:
count1, same owner, 200 CKB. **Stop** and record expected/observed state, hashes,
public OutPoints, source revision, release and policy. Exclude wallet directories,
passwords/keys and private inputs; do not archive the entire run directory.

`confirm` checks **currently live** outputs. After spending a change/app output,
an old confirmation command may correctly fail. Show saved receipts as historical
evidence; the curated demonstration can be rechecked using `review-counter.py`,
which distinguishes historical commitment from current liveness. Never broadcast
intentionally invalid cases. No step here authorizes a fresh public deployment.
