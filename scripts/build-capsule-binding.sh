#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="riscv64imac-unknown-none-elf"
package="capsule-binding"

export PATH="$HOME/.cargo/bin:$PATH"

if ! rustup target list --installed | grep -q "^${target}$"; then
  echo "error: rust target ${target} is not installed" >&2
  exit 1
fi

cargo_home="${CARGO_HOME:-$HOME/.cargo}"
rustup_home="${RUSTUP_HOME:-$HOME/.rustup}"
export RUSTFLAGS="-C target-feature=-a --remap-path-prefix=${cargo_home}/registry/src=/cargo-registry --remap-path-prefix=${rustup_home}/toolchains=/rustup-toolchains --remap-path-prefix=${repo_root}=/build"

cd "$repo_root/contracts"
cargo build \
  --locked \
  --release \
  --target "$target" \
  -p "$package"

binary="$repo_root/contracts/target/$target/release/$package"
test -f "$binary"
echo "built: $binary"
