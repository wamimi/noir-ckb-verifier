#!/usr/bin/env bash
set -euo pipefail

stage="${1:-}"
case "$stage" in build|run) ;; *) echo 'usage: bash scripts/week13-sp1-matrix.sh build|run' >&2; exit 2 ;; esac
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream="$repo_root/target/week-13/upstream/ckb-rust-algorithm-benchmarks"
experiment="$repo_root/target/week-13/sp1-rejection-experiment"
templates="$repo_root/experiments/week13-sp1"
revision="026d5cb7199d71fd5bee3f165b446dd2243079d0"
lock_hash="b99cb9964f07011e8f2dfc9de9b4bd7d20d42d6a856f2f68f202e4f82a2ad087"
mkdir -p "$repo_root/target/week-13/logs"
log_dir="$(mktemp -d "$repo_root/target/week-13/logs/matrix-$stage.XXXXXX")"
log_file="$log_dir/terminal.log"

matrix_stage() {
    printf 'week13_matrix_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'stage=%s\n' "$stage"
    test "$(git -C "$upstream" rev-parse HEAD)" = "$revision"
    test -z "$(git -C "$upstream" status --porcelain)"
    test "$(shasum -a 256 "$upstream/contracts/sp1-test/src/entry.rs" | awk '{print $1}')" = "0d04bab7d78bd41e137e3d17b3a8cf20baf60147c893bc9e039eb4cfa4f6222a"

    if [ "$stage" = build ] && [ ! -e "$experiment" ]; then
        git clone --no-hardlinks --no-checkout "$upstream" "$experiment"
        git -C "$experiment" checkout --detach "$revision"
        cp "$templates/entry.rs" "$experiment/contracts/sp1-test/src/entry.rs"
        cp "$templates/fixture.rs" "$experiment/contracts/sp1-test/src/week13_fixture.rs"
    fi
    cd "$experiment"
    test "$(git rev-parse HEAD)" = "$revision"
    test "$(shasum -a 256 Cargo.lock | awk '{print $1}')" = "$lock_hash"
    cmp "$templates/entry.rs" contracts/sp1-test/src/entry.rs
    cmp "$templates/fixture.rs" contracts/sp1-test/src/week13_fixture.rs
    git diff --exit-code -- . ':(exclude)contracts/sp1-test/src/entry.rs'
    shasum -a 256 Cargo.lock contracts/sp1-test/src/entry.rs contracts/sp1-test/src/week13_fixture.rs

    local binary="$experiment/target/riscv64imac-unknown-none-elf/release/sp1-test"
    if [ "$stage" = build ]; then
        local llvm_prefix
        llvm_prefix="$(brew --prefix llvm@19)"
        export TARGET_CC="$llvm_prefix/bin/clang"
        export TARGET_AR="$llvm_prefix/bin/llvm-ar"
        export RUSTFLAGS="-C target-feature=+zba,+zbb,+zbc,+zbs,-a -C debug-assertions"
        export CARGO_TARGET_DIR="$experiment/target"
        rustc +1.94.0 --version
        cargo +1.94.0 --version
        "$TARGET_CC" --version
        "$TARGET_AR" --version
        printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
        cargo +1.94.0 build --locked --release --target riscv64imac-unknown-none-elf -p sp1-test
        wc -c "$binary"
        file "$binary"
        shasum -a 256 "$binary" | tee "$experiment/target/week13-matrix-binary.sha256"
        test "$(shasum -a 256 Cargo.lock | awk '{print $1}')" = "$lock_hash"
        printf 'week13_matrix_build_status=passed\nruntime_tests=not_run\n'
    else
        test "$(ckb-debugger --version)" = "ckb-debugger 1.1.1"
        ckb-debugger --version
        shasum -a 256 -c "$experiment/target/week13-matrix-binary.sha256"
        printf 'script_version=2\nmode=fast\nmax_cycles_per_case=250000000\n'
        local case_name expected case_log
        for case_name in valid wrong-program wrong-public-values changed-proof truncated-proof wrong-verifier-key; do
            expected=reject
            if [ "$case_name" = valid ]; then expected=accept; fi
            case_log="$log_dir/$case_name.log"
            ckb-debugger --bin "$binary" --mode fast --script-version 2 \
                --max-cycles 250000000 -- "$case_name" 2>&1 | tee "$case_log"
            grep -Fq "week13_case=$case_name expected=$expected observed=$expected status=passed" "$case_log"
            grep -Eq '^Run result: 0[[:space:]]*$' "$case_log"
        done
        printf 'week13_matrix_status=passed\nweek13_matrix_cases_passed=6\n'
    fi
    git status --short
}

set +e
( set -e; matrix_stage ) 2>&1 | tee "$log_file"
pipeline_codes=("${PIPESTATUS[@]}")
set -e
printf 'week13_matrix_%s_exit_code=%s\n' "$stage" "${pipeline_codes[0]}" | tee -a "$log_file"
printf 'week13_matrix_log=%s\n' "$log_file"
if [ "${pipeline_codes[1]}" -ne 0 ]; then exit "${pipeline_codes[1]}"; fi
exit "${pipeline_codes[0]}"
