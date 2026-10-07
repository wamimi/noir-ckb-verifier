# Week 15: operator-confirmed CKB testnet lifecycle

Recorded 7 October 2026. The operator ran signing and broadcast commands locally.
The confirmation client reported `committed-and-cells-checked` for deployment,
creation, and update. This document preserves those existing receipts; its author
did not rebroadcast transactions or independently rerun the chain queries.

## Public transaction references

| Stage | Transaction | Receipt |
| --- | --- | --- |
| Contract and VK deployment | [0x0ee39d…27ad1](https://testnet.explorer.nervos.org/transaction/0x0ee39d547101eb348bc72a93f9a08b301353267487f3061f54a0070c44f27ad1) | [Deployment](week-15/testnet-deployment-receipt.json) |
| Counter creation at zero | [0x57ee42…b269b](https://testnet.explorer.nervos.org/transaction/0x57ee42444304f1c1508c1b6136c4e1c33adb1ff8086eb885bd5abdd5080b269b) | [Creation](week-15/testnet-creation-receipt.json) |
| Proof-authorized update 0 → 1 | [0x24a336…13bb6](https://testnet.explorer.nervos.org/transaction/0x24a336fbc09ea5330b83adcbaaf17e6eaafcb21776e13df6ec01d00daa613bb6) | [Update](week-15/testnet-update-receipt.json) |

Genesis: `0x10639e0895502b5688a6be8cf69460d76541bfa4821629d86d62ba0aae3f9606`.
Release manifest SHA-256: `6d659fc15c73c9cee8e3ed2a1de68415cd2b07e0fb9d14d9d857025ce381c887`.
Type ELF SHA-256: `1bb0449d63dc4c8e0f321bbe3dfbb4cafb790cad2d407ab489444d45fe8b3ed3`.
Type CKB data hash: `0x79d7e7614ff1689cb6c6fbbd376ab2fa959dc92394abea35cbafb1bd2b7d0a88`.
VK CKB data hash: `0x685bc8cd974970ba3a030025f683c7fd6fce0715c2e9f286660634a8b35058fe`.

The implementation was uncommitted on base revision
`b155300c8145916a485696bf461e36f055bb5135`; that base alone does not reproduce
this deployment. The retained local release manifest contains build/source hashes.
Archiving that public manifest and build metadata in a portable release bundle,
and tying it to the final source commit, remains a publication gate.

## What was checked

The client checked network identity, transaction commitment, raw-transaction
equality, input consumption, and exact live output data, Type, Lock and capacity.
Deployment confirmation also compared code/VK data hashes to the release.
These are point-in-time observations; output Cells may be consumed later.

Deployment outputs 0 and 1 hold the code and VK. Initialization output 0 held
count zero. The update consumed that Cell and created count one at output 0,
preserving its ownership Lock and 200 CKB. Output 1 is ordinary change.
The pre/post-signing update checks agreed on the public statement:

```json
["0", "1", "154725372892316643625601094939967772637", "263158646073569369253601295048711988710"]
```

The last two fields encode the selected-operation context. The proof was generated
for the actual input OutPoint, not reused from a local-chain example.

## Boundaries

This establishes the legitimate testnet lifecycle for one fixed public counter.
The 48 adversarial VM cases and mutation results remain separate local evidence.
No production ceremony, audit, private-state security, arbitrary circuit support,
or independent external reproduction is claimed. Application capacity has no
withdrawal/destruction path. Owner-controlled code/VK dependencies must be retained
for application liveness. No wallet files, private keys, or signing secrets are
included here.

## Subsequent independent read-only recheck — 7 October 2026

The original author statement above describes the receipt-curation pass. During
the later handoff pass, `python3 -B scripts/review-counter.py --rpc
https://testnet.ckb.dev` independently queried the public node, checked testnet
genesis and all three committed transactions, compared raw transaction contents,
code/VK lengths and hashes, input linkage, states, owner/capacity, derived statement
and proof witness hash. [Actual result](week-15-public/live-check-2026-10-07.json):
successor currently live, count1, same owner and 200 CKB. Initial Cell status was
`unknown`; its consumption is established by the committed update input reference.
No signing or broadcast occurred. This is independent read-only checking of the
operator's transactions, **not independent external reproduction**.

[Portable public provenance](week-15-public/deployment.json) now retains the
original release hash, deployed source hashes, normalized build flags, exact
artifact identities, setup provenance and receipt hashes. The public proof/VK
also pass snarkjs verification. The [final source snapshot](week-15-public/source-state.json)
identifies the uncommitted handoff; recording a real published commit is still
a publication gate. The old machine-local release was not overwritten.

Onboarding finding: the operator received two 100,000 CKB funding Cells and
consolidated them before deployment because the client accepts one funding Cell.
The operator guide documents this extra step; no multi-input builder expansion
was made. The 200 CKB application has no withdrawal/destruction path.
