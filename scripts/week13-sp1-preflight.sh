#!/usr/bin/env bash
# Record the environment and prepare a pinned, disposable upstream checkout.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/target/week-13/logs" "$repo_root/target/week-13/upstream"
log_dir="$(mktemp -d "$repo_root/target/week-13/logs/preflight.XXXXXX")"
log_file="$log_dir/terminal.log"

record_preflight() {
    cd "$repo_root"
    printf 'week13_preflight_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'repository=%s\n' "$repo_root"
    git rev-parse HEAD
    git status --short --branch
    uname -sm
    if command -v sw_vers >/dev/null 2>&1; then
        sw_vers
        printf 'physical_memory_bytes='
        sysctl -n hw.memsize
    fi

    rustup toolchain list
    rustc --version
    cargo --version
    rustup target list --installed
    if rustup toolchain list | grep -q '^1\.94\.0-'; then
        rustup run 1.94.0 rustc --version
        rustup target list --installed --toolchain 1.94.0
    else
        printf 'upstream_rust_1_94_0=not_installed\n'
    fi

    if command -v ckb-debugger >/dev/null 2>&1; then
        ckb-debugger --version
    else
        printf 'ckb_debugger=not_installed\n'
    fi

    for compiler in clang clang-19 clang-20 clang-21; do
        if command -v "$compiler" >/dev/null 2>&1; then
            command -v "$compiler"
            "$compiler" --version
        fi
    done
    # Homebrew LLVM can be installed without being selected by PATH.
    for llvm_dir in /opt/homebrew/opt/llvm /opt/homebrew/opt/llvm@19 /opt/homebrew/opt/llvm@20 /opt/homebrew/opt/llvm@21 /usr/local/opt/llvm /usr/local/opt/llvm@19; do
        if [ -x "$llvm_dir/bin/clang" ]; then
            printf 'llvm_candidate=%s\n' "$llvm_dir"
            "$llvm_dir/bin/clang" --version
            if [ -x "$llvm_dir/bin/llvm-ar" ]; then
                "$llvm_dir/bin/llvm-ar" --version
            fi
        fi
    done

    local upstream="$repo_root/target/week-13/upstream/ckb-rust-algorithm-benchmarks"
    local revision="026d5cb7199d71fd5bee3f165b446dd2243079d0"
    if [ ! -e "$upstream" ]; then
        git clone --no-checkout \
            https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks.git \
            "$upstream"
        git -C "$upstream" checkout --detach "$revision"
    fi
    if [ ! -d "$upstream/.git" ]; then
        printf 'error: expected a Git checkout at %s\n' "$upstream" >&2
        return 1
    fi
    local actual
    actual="$(git -C "$upstream" rev-parse HEAD)"
    if [ "$actual" != "$revision" ]; then
        printf 'error: upstream revision mismatch: %s\n' "$actual" >&2
        return 1
    fi
    if [ -n "$(git -C "$upstream" status --porcelain)" ]; then
        printf 'error: upstream checkout has changes; inspect before reuse\n' >&2
        git -C "$upstream" status --short
        return 1
    fi

    printf 'benchmark_revision=%s\n' "$actual"
    printf 'sp1_verifier_candidate_revision=0cc2b42f287bbfce66973e19defb8b39fa361732\n'
    printf 'benchmark_toolchain='
    cat "$upstream/rust-toolchain"
    cat "$upstream/contracts/sp1-test/Cargo.toml"
    shasum -a 256 "$upstream/contracts/sp1-test/src/entry.rs"
    if [ -f "$upstream/Cargo.lock" ]; then
        shasum -a 256 "$upstream/Cargo.lock"
        grep -n -A 5 -E '^name = "(sp1-verifier|ckb-alt-bn128|ckb-std)"' "$upstream/Cargo.lock"
    else
        printf 'benchmark_lockfile=absent\n'
    fi
    printf 'week13_preflight_status=collected\n'
    printf 'runtime_tests=not_run\n'
}

set +e
( set -e; record_preflight ) 2>&1 | tee "$log_file"
pipeline_codes=("${PIPESTATUS[@]}")
set -e
printf 'week13_preflight_exit_code=%s\n' "${pipeline_codes[0]}" | tee -a "$log_file"
printf 'week13_preflight_log=%s\n' "$log_file"
if [ "${pipeline_codes[1]}" -ne 0 ]; then
    printf 'error: unable to retain the complete log\n' >&2
    exit "${pipeline_codes[1]}"
fi
exit "${pipeline_codes[0]}"
