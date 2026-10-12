# Advanced: deploy your own copy of the counter contract

**Most people don't need this.** To create your own counter on testnet, follow
[Try the counter](try-the-counter.md), Part 2. It joins the existing deployment
for about 262 testnet CKB.

This guide deploys a **separate copy** of the contract and its verification key,
with a fresh development setup of your own. Use it if you want your own
deployment end to end. It needs about **114,000 testnet CKB** (the contract and
key are stored on-chain), plus 200 CKB for the counter itself.

The existing deployment's receipts are in the
[testnet evidence](../evidence/week-15-testnet.md).

## Before you start

- Complete Part 1, option B (native) of [Try the counter](try-the-counter.md), and
  make sure `python3 -B scripts/start-counter.py doctor` passes.
- Testnet only. The tools never ask for keys or passwords; you sign with your own
  `ckb-cli` account. Never share passwords, keys or wallet folders.
- Each signing and sending step is yours to run. Review each transaction before
  signing it. If a send times out, check the transaction hash before sending again:
  a timeout does not mean it failed.

## 1. Set up a working folder and check the network

```bash
export COUNTER_CLI="$(ls target/counter-tools/*/ckb-cli | head -1)"
export COUNTER_RPC=https://testnet.ckb.dev
export COUNTER_RUN="$(mktemp -d "$PWD/target/counter-testnet.XXXXXX")"
export COUNTER_GENESIS=0x10639e0895502b5688a6be8cf69460d76541bfa4821629d86d62ba0aae3f9606
export COUNTER_BACKEND="$(cd ../Noir-Groth16 && pwd)"
python3 scripts/owned_counter.py preflight --rpc "$COUNTER_RPC" --genesis "$COUNTER_GENESIS" --out "$COUNTER_RUN/policy.json"
```

This confirms the RPC is really CKB testnet (by its genesis hash) and records the
standard ownership Lock it will use. It is read-only. A different genesis hash
means the wrong network: do not continue.

## 2. Make a fresh setup and build the contract for testnet

```bash
python3 scripts/setup-owned-counter.py --out "$COUNTER_RUN/setup" --backend "$COUNTER_BACKEND"
python3 scripts/owned_counter.py build --policy "$COUNTER_RUN/policy.json" --setup "$COUNTER_RUN/setup" --out "$COUNTER_RUN/build"
export COUNTER_RELEASE="$COUNTER_RUN/build/release.json"
python3 scripts/owned_counter.py inspect --release "$COUNTER_RELEASE"
```

The setup creates your own proving and verification keys (single-party
development material, not a production ceremony). The build compiles the
contract with your verification key and the testnet network built in. A new
setup always gives a new key, so this release can never be mixed with the
existing deployment. Keep the printed hashes.

## 3. Create a testnet account

Same as Part 2, step 3 of [Try the counter](try-the-counter.md):

```bash
export CKB_CLI_HOME="$HOME/.ckb-cli-noir-ckb-testnet"
"$COUNTER_CLI" account new
export COUNTER_ADDRESS=ckt1...your testnet address...
export COUNTER_ACCOUNT=0x...your lock_arg...
export COUNTER_OWNER="$COUNTER_ACCOUNT"
```

## 4. Fund it, and pick one funding Cell

Request testnet CKB from the [CKB testnet faucet](https://faucet.nervos.org).
To see exactly how much your release needs:

```bash
python3 -c 'import json,os; r=json.load(open(os.environ["COUNTER_RELEASE"])); print("contract + key:",sum(61+a["bytes"] for a in r["artifacts"].values()),"CKB, plus 200 CKB counter, 61 CKB change and a small fee")'
"$COUNTER_CLI" --url "$COUNTER_RPC" wallet get-live-cells --address "$COUNTER_ADDRESS" --limit 15
```

The client spends **one** funding Cell, so you need a single Cell large enough
for everything. Note its transaction hash and output index, then check it:

```bash
export COUNTER_FUNDING=0x...tx_hash...:0
python3 -B - "$COUNTER_RPC" "$COUNTER_FUNDING" <<'CHECK'
import sys,json
sys.path.insert(0,'scripts')
import owned_counter as c
print(json.dumps(c.live(sys.argv[1],c.op(sys.argv[2])),indent=2))
CHECK
```

It should be live, owned by your address, with no data and no Type.

### If your CKB arrived as several smaller Cells

Merge two of them into one by paying yourself. The output amount is their total
minus a small fee (for two 100,000 CKB Cells and a 0.01 CKB fee: `199999.99`).

```bash
export COUNTER_TX="$COUNTER_RUN/consolidation.json"
"$COUNTER_CLI" tx init --tx-file "$COUNTER_TX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx add-input --tx-file "$COUNTER_TX" --tx-hash 0x...first... --index 0
"$COUNTER_CLI" --url "$COUNTER_RPC" tx add-input --tx-file "$COUNTER_TX" --tx-hash 0x...second... --index 0
"$COUNTER_CLI" tx add-output --tx-file "$COUNTER_TX" --to-sighash-address "$COUNTER_ADDRESS" --capacity 199999.99
"$COUNTER_CLI" --url "$COUNTER_RPC" tx info --tx-file "$COUNTER_TX"
```

Check the single output and the fee, then sign and send it as in the next section.
Use the merged Cell (`<hash>:0`) as `COUNTER_FUNDING`.

## How to sign and send any transaction

Every step below prepares an **unsigned** transaction file in `$COUNTER_TX`. To
sign and send it:

```bash
"$COUNTER_CLI" --url "$COUNTER_RPC" tx info --tx-file "$COUNTER_TX"
"$COUNTER_CLI" --url "$COUNTER_RPC" tx sign-inputs --tx-file "$COUNTER_TX" --from-account "$COUNTER_ACCOUNT" --add-signatures --skip-check
"$COUNTER_CLI" --url "$COUNTER_RPC" tx send --tx-file "$COUNTER_TX" --skip-check
export COUNTER_HASH=0x...the returned hash...
"$COUNTER_CLI" --url "$COUNTER_RPC" rpc get_transaction --hash "$COUNTER_HASH"
```

`--skip-check` only skips ckb-cli's template check for custom scripts; the node
still fully verifies the transaction. Wait until the status is `committed` before
the next step. If anything in a transaction changes after signing, it must be
signed again.

## 5. Deploy the contract and verification key

```bash
export COUNTER_TX="$COUNTER_RUN/deploy.json"
python3 scripts/owned_counter.py prepare deploy --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --out "$COUNTER_TX"
```

Outputs: contract (index 0), verification key (index 1), your change (index 2).
Sign and send it, then confirm:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --deployment --out "$COUNTER_RUN/deployment-receipt.json"
export COUNTER_FUNDING="$COUNTER_HASH:2"
```

Keep the contract and key Cells unspent: every counter using this deployment
depends on them.

## 6. Create your counter at zero

The 200 CKB placed in the counter is **permanently locked**; this contract has no
withdrawal or destruction path.

```bash
export COUNTER_TX="$COUNTER_RUN/create.json"
python3 scripts/owned_counter.py prepare create --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --deployment "$COUNTER_RUN/deployment-receipt.json" --out "$COUNTER_TX"
```

Sign and send it, then confirm:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --out "$COUNTER_RUN/creation-receipt.json"
export COUNTER_APPLICATION="$COUNTER_HASH:0"
export COUNTER_FUNDING="$COUNTER_HASH:1"
```

Creation needs no proof: the contract checks the zero start directly.

## 7. Update to one with a proof

```bash
python3 scripts/owned_counter.py prepare update --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING" --application "$COUNTER_APPLICATION" --deployment "$COUNTER_RUN/deployment-receipt.json" --out "$COUNTER_RUN/update-unsigned.json"
python3 scripts/owned_counter.py prove --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_RUN/update-unsigned.json" --out "$COUNTER_RUN/update-proof"
export COUNTER_TX="$COUNTER_RUN/update-proof/transaction.json"
python3 scripts/owned_counter.py check --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --proof "$COUNTER_RUN/update-proof"
```

`check` should print `checked-before-signing`. Sign the transaction, run the same
`check` command again (it confirms signing changed nothing the proof depends on),
then send and confirm:

```bash
python3 scripts/owned_counter.py confirm --release "$COUNTER_RELEASE" --rpc "$COUNTER_RPC" --tx "$COUNTER_TX" --hash "$COUNTER_HASH" --out "$COUNTER_RUN/update-receipt.json"
```

The result should be `committed-and-cells-checked`: the counter at 1, same owner,
200 CKB.

## Keeping a record

Keep the receipts, transaction hashes, release hash and source revision. Do not
publish the run folder: it contains your setup files and logs, and `CKB_CLI_HOME`
contains your wallet. `confirm` checks Cells that are live *now*; once a Cell is
spent by a later update, re-running an older `confirm` correctly fails, so the
saved receipts are the historical record.
