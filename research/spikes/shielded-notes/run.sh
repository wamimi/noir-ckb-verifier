#!/usr/bin/env bash
# R2 spikes. Usage: research/spikes/shielded-notes/run.sh
#
# Part 1 (always): CKB-VM cycles of script-side accumulator operations (Poseidon2
# permutation and tree append; BLAKE2b sparse Merkle tree absence proof and insertion).
#   Needs Rust 1.94.1 with the riscv64imac-unknown-none-elf target, Rust 1.95.0, clang 18.
# Part 2 (when NARGO, BACKEND_CLI and SNARKJS are set): R1CS constraint counts for Merkle
# membership and note-spending circuits at depths 16, 20 and 32.
#   NARGO: nargo 1.0.0-beta.18; BACKEND_CLI: noir-cli of wamimi/Noir-Groth16@828025f;
#   SNARKJS: snarkjs 0.7.5.
#
# On a machine without the pinned toolchains (the run recorded in README.md):
#   CONTRACT_CARGO="cargo -Zbuild-std=core,alloc" HOST_CARGO=cargo RUSTC_BOOTSTRAP=1 \
#   CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS="-C target-feature=-a,-zaamo,-zalrsc" ./run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
CONTRACT_CARGO=${CONTRACT_CARGO:-cargo +1.94.1}
HOST_CARGO=${HOST_CARGO:-cargo +1.95.0}
if [ -z "${CLANG:-}" ]; then
  CLANG=$(command -v clang-18 || true)
  [ -n "$CLANG" ] || CLANG="$(brew --prefix llvm@18 2>/dev/null)/bin/clang"
fi
export CLANG CC_riscv64imac_unknown_none_elf="$CLANG"
# Same flag as contracts/.cargo/config.toml in the repository root.
export CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS="${CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS:--C target-feature=-a}"
# sparse-merkle-tree depends on blake2b-rs, whose C file includes <string.h>; the script
# does not use that code, but it has to compile for the bare-metal target.
export CFLAGS_riscv64imac_unknown_none_elf="-I$HERE/vm/contracts/shim"

(cd "$HERE/vm/contracts" && $CONTRACT_CARGO build --locked --release --target riscv64imac-unknown-none-elf)
export SPIKE_BIN="$HERE/vm/contracts/target/riscv64imac-unknown-none-elf/release"
(cd "$HERE/vm/harness" && $HOST_CARGO test --locked --release -- --nocapture 2>&1 | grep -E "^ACC|test result: (ok. 1|FAILED)|panicked|^error")

if [ -n "${NARGO:-}" ] && [ -n "${BACKEND_CLI:-}" ] && [ -n "${SNARKJS:-}" ]; then
  python3 "$HERE/constraints.py" --nargo "$NARGO" --backend-cli "$BACKEND_CLI" --snarkjs "$SNARKJS" \
    --out "$ROOT/target/shielded-notes" --depths "${DEPTHS:-16,20,32}"
fi
