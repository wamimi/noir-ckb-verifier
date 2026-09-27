#!/usr/bin/env bash
# Build the pinned upstream fixture with its original lockfile and record evidence.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/target/week-13/logs"
log_dir="$(mktemp -d "$repo_root/target/week-13/logs/build.XXXXXX")"
log_file="$log_dir/terminal.log"

build_fixture() {
    local upstream="$repo_root/target/week-13/upstream/ckb-rust-algorithm-benchmarks"
    local revision="026d5cb7199d71fd5bee3f165b446dd2243079d0"
    local lock_hash="b99cb9964f07011e8f2dfc9de9b4bd7d20d42d6a856f2f68f202e4f82a2ad087"
    local target="riscv64imac-unknown-none-elf"
    cd "$upstream"
    test "$(git rev-parse HEAD)" = "$revision"
    test -z "$(git status --porcelain)"
    test "$(shasum -a 256 Cargo.lock | awk '{print $1}')" = "$lock_hash"

    local llvm_prefix
    llvm_prefix="$(brew --prefix llvm@19)"
    export TARGET_CC="$llvm_prefix/bin/clang"
    export TARGET_AR="$llvm_prefix/bin/llvm-ar"
    test -x "$TARGET_CC"
    test -x "$TARGET_AR"
    # Match the upstream SP1 benchmark's instruction features and debug assertions.
    export RUSTFLAGS="-C target-feature=+zba,+zbb,+zbc,+zbs,-a -C debug-assertions"
    export CARGO_TARGET_DIR="$upstream/target"

    printf 'week13_build_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'benchmark_revision=%s\n' "$revision"
    printf 'TARGET_CC=%s\nTARGET_AR=%s\nRUSTFLAGS=%s\n' "$TARGET_CC" "$TARGET_AR" "$RUSTFLAGS"
    rustc +1.94.0 --version
    cargo +1.94.0 --version
    rustup target list --installed --toolchain 1.94.0
    "$TARGET_CC" --version
    "$TARGET_AR" --version
    shasum -a 256 Cargo.lock contracts/sp1-test/src/entry.rs

    cargo +1.94.0 build --locked --release --target "$target" -p sp1-test

    local binary="$CARGO_TARGET_DIR/$target/release/sp1-test"
    test -f "$binary"
    ls -lh "$binary"
    wc -c "$binary"
    file "$binary"
    shasum -a 256 "$binary" Cargo.lock
    test "$(shasum -a 256 Cargo.lock | awk '{print $1}')" = "$lock_hash"
    git status --short
    test -z "$(git status --porcelain)"
    printf 'week13_build_status=passed\n'
    printf 'week13_verifier_binary=%s\n' "$binary"
    printf 'runtime_tests=not_run\n'
}

set +e
( set -e; build_fixture ) 2>&1 | tee "$log_file"
pipeline_codes=("${PIPESTATUS[@]}")
set -e
printf 'week13_build_exit_code=%s\n' "${pipeline_codes[0]}" | tee -a "$log_file"
printf 'week13_build_log=%s\n' "$log_file"
if [ "${pipeline_codes[1]}" -ne 0 ]; then
    printf 'error: unable to retain the complete log\n' >&2
    exit "${pipeline_codes[1]}"
fi
exit "${pipeline_codes[0]}"
