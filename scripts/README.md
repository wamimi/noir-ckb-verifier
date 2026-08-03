# Scripts

Automation is added only after the corresponding manual command sequence has
been retained and reviewed. Scripts must preserve the toolchain, artifact
provenance, and compatibility assumptions established by the evidence logs.

## `build-capsule-binding.sh`

Builds the Week 10 Capsule binding Type Script as a stripped
`riscv64imac-unknown-none-elf` release binary using the separately pinned
contract workspace and lockfile.
