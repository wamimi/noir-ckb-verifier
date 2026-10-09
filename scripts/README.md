# Scripts

Automation is added only after the corresponding manual command sequence has
been retained and reviewed. Scripts must preserve the toolchain, artifact
provenance, and compatibility assumptions established by the evidence logs.

## `build-capsule-binding.sh`

Builds the Week 10 Capsule binding Type Script as a stripped
`riscv64imac-unknown-none-elf` release binary using the separately pinned
contract workspace and lockfile.

## `reviewer-smoke.sh`

Runs the shortest retained-fixture reviewer path. It validates the pinned
`groth16-ckb` checkout and Rust toolchains, records source/tool versions, runs
formatting, lint, and host tests, builds both RISC-V scripts, and executes the
12-case proof-bound Capsule matrix in CKB-VM. Complete output is retained below
`target/noir-ckb/reviewer-smoke/<run-id>/terminal.log`.

The script uses public fixtures only. It does not regenerate witnesses, Powers
of Tau transcripts, proving keys, or proofs.

## Owned counter v1

`start-counter.py` offers a guided menu and scriptable `inspect`, `live`, `doctor`
and `local` modes. Local mode delegates to the existing runner with mutations enabled;
it checks prerequisites but does not install system tools.

See [the quickstart](../docs/owned-counter-quickstart.md). `fetch-counter-tools.py`
installs hash-pinned development tools into a new directory. `local-owned-counter.py`
executes the complete disposable local lifecycle; it signs and broadcasts only on
its loopback dev chain. `setup-owned-counter.py` generates fresh development setup;
`owned_counter.py` constructs unsigned transactions, proves, checks and confirms.
`check-owned-counter.py`, `check-counter-ranges.py` and `mutate-owned-counter.py`
validate this separate application's exact circuit and Type. No public deployment
is automatic. Keep private account directories out of evidence.
