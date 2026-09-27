#!/usr/bin/env bash
# Run the retained upstream benchmark; inspect guest result and cycles in the log.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/target/week-13/logs"
log_dir="$(mktemp -d "$repo_root/target/week-13/logs/verify.XXXXXX")"
log_file="$log_dir/terminal.log"

run_fixture() {
    local upstream="$repo_root/target/week-13/upstream/ckb-rust-algorithm-benchmarks"
    local binary="$upstream/target/riscv64imac-unknown-none-elf/release/sp1-test"
    local expected_hash="eb681935694ff4d8582a15d2a575e364b4087c9b8a45c83e9ab0d6d6772d4e45"
    test "$(git -C "$upstream" rev-parse HEAD)" = "026d5cb7199d71fd5bee3f165b446dd2243079d0"
    test -z "$(git -C "$upstream" status --porcelain)"
    test "$(shasum -a 256 "$binary" | awk '{print $1}')" = "$expected_hash"
    local debugger_version
    debugger_version="$(ckb-debugger --version)"
    test "$debugger_version" = "ckb-debugger 1.1.1"
    printf 'week13_verification_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '%s\n' "$debugger_version"
    printf 'script_version=2\nmode=fast\nmax_cycles=250000000\n'
    printf 'fixture=upstream_embedded_proof\npublic_values=empty\n'
    wc -c "$binary"
    shasum -a 256 "$binary"
    ckb-debugger --bin "$binary" --mode fast --script-version 2 --max-cycles 250000000
}

set +e
( set -e; run_fixture ) 2>&1 | tee "$log_file"
pipeline_codes=("${PIPESTATUS[@]}")
set -e
printf 'week13_verification_command_exit_code=%s\n' "${pipeline_codes[0]}" | tee -a "$log_file"
printf 'week13_verification_log=%s\n' "$log_file"
if [ "${pipeline_codes[1]}" -ne 0 ]; then
    printf 'error: unable to retain the complete log\n' >&2
    exit "${pipeline_codes[1]}"
fi
exit "${pipeline_codes[0]}"
