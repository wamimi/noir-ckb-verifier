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
