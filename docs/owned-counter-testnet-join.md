# Create your own counter on CKB testnet

This guide lets you create and update **your own** owned counter on public
testnet, against the existing deployed contract and verification key. You do not
deploy anything, so you need about 262 testnet CKB, not the ~114,000 a fresh
deployment would take. You sign and broadcast with your own testnet account; the
tool never sees your keys or password.

Status: the full path is rehearsed on a local chain by `start-counter.py join-test`
(a second key joins a deployment made by the first). The first real testnet run is
the maintainer's; check [the evidence](../evidence/week-15-portable.md) for its
result before relying on it.

## What you are trusting, and what you are not

- **The published bundle** (`releases/owned-counter-v1-testnet/`) holds the
  development proving key, the verification key, the R1CS, the compiled circuit,
  the contract binary and the deployment's OutPoints. `init` checks every file
  against the [public deployment record](../evidence/week-15-public/deployment.json)
  published with the 7 October deployment, against the live testnet Cells, and
  against your own fresh compile and backend build.
- **The setup is single-party development material.** The maintainer could in
  principle have kept its secret and could forge counter proofs. For this counter
  that does not let anyone change *your* counter: your counter Cell is locked by
  your own signature, which every update also requires. (The planned private tally
  removes the signature, which is why it gets a multi-party ceremony first.)
- **Capacity is locked permanently.** The application has no withdrawal or
  destruction path. The 200 CKB in your counter Cell stays there. Testnet only.

## 0. Prerequisites

A native setup on macOS ARM64 or Ubuntu 24.04 that passes the doctor
([bootstrap](owned-counter-bootstrap.md)). The container route cannot be used for
this path yet: runs are network-isolated, and this path talks to a testnet RPC.

```bash
python3 -B scripts/start-counter.py doctor
```

Optional but recommended: rehearse the whole participant path on a throwaway
local chain first (no network transactions, no funds):

```bash
python3 -B scripts/start-counter.py join-test
```

## 1. Verify the bundle and your toolchain

Read-only on the chain. Builds the backend and a test proof locally.

```bash
export COUNTER_WORK="$PWD/target/testnet-join-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -B scripts/join-counter-testnet.py init --out "$COUNTER_WORK"
```

It checks, in order: bundle hashes and the public record; testnet genesis and the
standard ownership Lock; that the live code and key Cells hold exactly the bundled
bytes; that the proving key exports the published verification key; that your
Nargo produces the same circuit and your backend the same R1CS; and that a test
proof verifies and encodes to the deployed key. Any mismatch stops here.

## 2. A testnet account and one funding Cell

Use the pinned ckb-cli and a dedicated testnet-only account. The steps are the same
as sections 3 and 4 of the [operator guide](owned-counter-testnet.md): create the
account (`ckb-cli account new`, interactive password), note its testnet address
and `lock_arg`, and fund it from the faucet linked in the
[official testnet documentation](https://docs.nervos.org/docs/getting-started/blockchain-setup/testnet).

```bash
export COUNTER_CLI="$PWD/target/counter-tools/<platform>/ckb-cli"   # from fetch-counter-tools.py
export COUNTER_OWNER=0x...        # your 20-byte lock_arg (public)
export COUNTER_FUNDING=0x...:0    # one live, empty Cell you own, >= 262 CKB
```

The client spends exactly one funding Cell. If your faucet Cells are smaller, merge
them first (operator guide, "Optional consolidation"). Never share your password,
keys or wallet directory with anyone, including in bug reports.

## 3. Create your counter at zero

```bash
python3 -B scripts/join-counter-testnet.py create --work "$COUNTER_WORK" --owner "$COUNTER_OWNER" --funding "$COUNTER_FUNDING"
```

This prepares an **unsigned** transaction and prints the exact commands to review
it (`tx info`), sign it with your account (`tx sign-inputs --from-account`) and send
it (`tx send`). Run them yourself. Then confirm with the returned hash:

```bash
python3 -B scripts/join-counter-testnet.py confirm --work "$COUNTER_WORK" --hash 0x...
```

A timeout after sending does not mean failure: check the hash with
`"$COUNTER_CLI" --url https://testnet.ckb.dev rpc get_transaction --hash 0x...`
before ever sending again. Creation needs no proof; the contract checks the zero
start directly.

## 4. Update it with a fresh proof

```bash
python3 -B scripts/join-counter-testnet.py update --work "$COUNTER_WORK"
```

This prepares the update, generates a fresh proof bound to your counter's current
Cell, and checks it before you sign. It prints the sign, re-check, send and confirm
commands. Run `check` again after signing and before sending; it fails if anything
proof-bound changed. Repeat `update` for 1 → 2 and beyond.

Your transactions are visible at
`https://testnet.explorer.nervos.org/transaction/<hash>`.

## 5. Report your result

`python3 -B scripts/join-counter-testnet.py status --work "$COUNTER_WORK"` prints
your public transaction hashes and counts. Share those, your platform, the source
revision (`git rev-parse HEAD`) and any sanitized error through the review issue
template. Do not upload the work directory: it contains your test proof inputs and
command logs, and nothing in it is needed to verify a public transaction.
