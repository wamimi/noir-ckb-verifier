# Week 15 source-preview handoff validation — 7 October 2026

This pass completed documentation and read-only reviewer tooling after the operator's
confirmed testnet lifecycle. No deployed circuit/Type/setup/profile was changed.
No wallet was read, no transaction signed/broadcast, no Git staging/commit/push or
publication performed. Existing Capsule/history and unrelated drafts are preserved.

## Executed checks and scope

- Three committed testnet transactions independently read and checked through shared
  RPC with its honest User-Agent and normal TLS/timeout checks. Deployed code/VK
  hashes, raw transaction contents, consumed initial Cell, count0→1, same owner and
  200 CKB match. Current successor was live; [RPC result](week-15-public/live-check-2026-10-07.json).
- Retained public testnet proof verified by `npx --offline snarkjs@0.7.5 groth16
  verify` against curated public VK/vector: exit0, `OK!`. This is verification of
  an existing proof, not a new setup/proof-generation run.
- Twelve Python tests: six existing RPC header/error-handling cases plus six
  reviewer cases (recorded/no-network, successful content checks, changed raw
  transaction, context, proof witness, and unconfirmed transaction).
- Bootstrap first exposed absent cache entries: main/backend `anstyle-wincon
  v3.0.11`, contracts `zerocopy-derive v0.8.55`. All three documented `fetch --locked`
  commands succeeded, then all three offline metadata resolutions succeeded.
  Failures and successful fixes are retained in [bootstrap results](week-15-public/bootstrap-checks.json).
- The exact npm package-cache bootstrap succeeded with an initially empty isolated
  npm cache, followed by offline snarkjs version resolution. Its banner probe
  intentionally returns99, not proof success. Cargo/toolchains were not cold-installed.
- Markdown relative links, Bash/zsh snippet syntax and embedded Python syntax were
  checked. Pinned CLI help confirms documented flags; no account/consolidation
  transaction was executed during this pass. Counter CLI help starts offline.
- Deployed circuit/contract source hashes and 36 preserved historical and pre-existing files
  match their retained manifests. Public receipt copies match original receipt hashes.

[Focused command results](week-15-public/handoff-checks.json) record the exact
commands and exits. [Deployment provenance](week-15-public/deployment.json) uses
relative paths and normalized build prefixes; original release SHA-256 is retained.
The original source snapshot is retained as
`week-15-public/source-state.json`. It records the earlier working tree, including
unpublished planning files, and is historical evidence rather than a checkout
verification manifest. Documentation cleanup subsequently changed some files.
The separate [publication snapshot](week-15-public/publication-source-state.json)
covers only publishable files. Neither snapshot claims a new full lifecycle run.

## What was deliberately not rerun

The costly setup, 48-case VM matrix, three mutations and real local-node lifecycle
were already executed for the unchanged circuit/contract. Their original
[recorded evidence](week-15.md) remains authoritative for those exact builds.
This documentation/reviewer-only pass does not fabricate a new full run.
The fresh-directory attempt was on the same machine with caches/tools; a complete
fresh-machine install and independent external reviewer reproduction remain
unverified. Other platforms, standalone distribution and hosted counter CI are
not claimed. Explorer URLs identify RPC-verified transactions; no stable explorer
UI layout was assumed or independently rendered in this pass.

Source publication must identify an actual commit and verify its documentation
links. Independent developer reproduction and product demand are not established
by these checks.
