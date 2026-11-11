#!/usr/bin/env bash
# R3 spike: N Groth16 proofs under one key, verified separately and as one randomized batch,
# in CKB-VM (ckb-testtool).
# Usage: research/spikes/throughput/run.sh
# Needs: Rust 1.94.1 with the riscv64imac-unknown-none-elf target, Rust 1.95.0, clang 18, and
# the recorded tally matrix run under target/ (produced by scripts/check-private-tally.py).
# A full run takes several minutes; SIZES=1,8,32 shortens it.
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

(cd "$HERE/contracts" && $CONTRACT_CARGO build --locked --release --target riscv64imac-unknown-none-elf)
export SPIKE_BIN="$HERE/contracts/target/riscv64imac-unknown-none-elf/release"
RUN=${TALLY_RUN:-$ROOT/target/tally-testnet/local/matrix}
export CASES=${CASES:-tally=$RUN/cases/update-valid.json,$RUN/cases/create-valid.json}
export SIZES=${SIZES:-1,2,4,8,16,32,64,128,160,172,175,176}
echo "size verify-batch: $(wc -c < "$SPIKE_BIN/verify-batch") bytes"
(cd "$HERE/harness" && $HOST_CARGO test --locked --release -- --nocapture 2>&1 | grep -E "^GROUP|^BATCH|test result: (ok. 1|FAILED)|panicked|^error")
