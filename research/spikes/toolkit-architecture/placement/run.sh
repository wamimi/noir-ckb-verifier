#!/usr/bin/env bash
# Linked verifier against spawned verifier, on recorded proofs, in CKB-VM (ckb-testtool).
# Usage: research/spikes/toolkit-architecture/placement/run.sh
# Needs: Rust 1.94.1 with the riscv64imac-unknown-none-elf target, Rust 1.95.0, clang 18,
# and the recorded matrix runs under target/ (see ../README.md).
#
# On a machine without the pinned toolchains (the run recorded in README.md):
#   CONTRACT_CARGO="cargo -Zbuild-std=core,alloc" HOST_CARGO=cargo RUSTC_BOOTSTRAP=1 \
#   CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS="-C target-feature=-a,-zaamo,-zalrsc" ./run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
CONTRACT_CARGO=${CONTRACT_CARGO:-cargo +1.94.1}
HOST_CARGO=${HOST_CARGO:-cargo +1.95.0}
if [ -z "${CLANG:-}" ]; then
  CLANG=$(command -v clang-18 || true)
  [ -n "$CLANG" ] || CLANG="$(brew --prefix llvm@18 2>/dev/null)/bin/clang"
fi
export CLANG CC_riscv64imac_unknown_none_elf="$CLANG"
# Same flag as contracts/.cargo/config.toml in the repository root.
export CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS="${CARGO_TARGET_RISCV64IMAC_UNKNOWN_NONE_ELF_RUSTFLAGS:--C target-feature=-a}"

(cd "$HERE/contracts" && $CONTRACT_CARGO build --locked --release --target riscv64imac-unknown-none-elf)
export SPIKE_BIN="$HERE/contracts/target/riscv64imac-unknown-none-elf/release"
export CASE_TALLY_UPDATE=${CASE_TALLY_UPDATE:-$ROOT/target/tally-testnet/local/matrix/cases/update-valid.json}
export CASE_TALLY_CREATE=${CASE_TALLY_CREATE:-$ROOT/target/tally-testnet/local/matrix/cases/create-valid.json}
export CASE_COUNTER_UPDATE=${CASE_COUNTER_UPDATE:-$ROOT/target/week-15-guided-validation-20261009/matrix/update-valid.json}

# Optional second part: cycles against the number and size of public inputs.
# Set NARGO (1.0.0-beta.18), BACKEND_CLI (noir-cli of the pinned backend), ADAPTER
# (noir-ckb-adapter) and SNARKJS (snarkjs 0.7.5) to run it.
if [ -n "${NARGO:-}" ] && [ -n "${BACKEND_CLI:-}" ] && [ -n "${ADAPTER:-}" ] && [ -n "${SNARKJS:-}" ]; then
  WORK="$HERE/target/public-inputs"; rm -rf "$WORK"; mkdir -p "$WORK"
  "$SNARKJS" powersoftau new bn128 8 "$WORK/p0.ptau" > /dev/null
  "$SNARKJS" powersoftau contribute "$WORK/p0.ptau" "$WORK/p1.ptau" --name=spike -e="public spike entropy, development only" > /dev/null
  "$SNARKJS" powersoftau prepare phase2 "$WORK/p1.ptau" "$WORK/final.ptau" > /dev/null
  python3 "$HERE/npub.py" --nargo "$NARGO" --backend-cli "$BACKEND_CLI" --snarkjs "$SNARKJS" --adapter "$ADAPTER" \
    --ptau "$WORK/final.ptau" --out "$WORK"
  export CASES_DIR="$WORK/cases"
fi
(cd "$HERE/harness" && $HOST_CARGO test --locked --release -- --nocapture 2>&1 | grep -E "^size |^CASE|^relayer_open|test result|panicked|error")
