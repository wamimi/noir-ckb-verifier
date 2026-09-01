#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
groth16_ckb_repo="${GROTH16_CKB_REPO:-$(cd "$repo_root/.." && pwd)/groth16-ckb}"
expected_groth16_ckb_revision="d64c769ffe2d2edb5eb308dc59058efda77c2f83"
host_toolchain="1.95.0"
contract_toolchain="1.94.1"
target="riscv64imac-unknown-none-elf"
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="$repo_root/target/noir-ckb/reviewer-smoke/$run_id"
log_path="$run_dir/terminal.log"

mkdir -p "$run_dir"
exec > >(tee "$log_path") 2>&1

on_exit() {
  status=$?
  if [[ "$status" -ne 0 ]]; then
    echo "reviewer_smoke_status=failed" >&2
    echo "reviewer_smoke_log=$log_path" >&2
  fi
}
trap on_exit EXIT

fail() {
  echo "error: $*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "required command '$1' was not found"
  fi
}

echo "profile=retained-public-development-fixture"
echo "warning=this preview is pre-audit and is not suitable for production or mainnet"
echo "run_id=$run_id"
echo "noir_ckb_repo=$repo_root"
echo "groth16_ckb_repo=$groth16_ckb_repo"

require_command git
require_command cargo
require_command rustup

if [[ ! -d "$groth16_ckb_repo/.git" ]]; then
  fail "pinned groth16-ckb checkout not found; clone it beside noir-ckb-verifier or set GROTH16_CKB_REPO"
fi

actual_groth16_ckb_revision="$(git -C "$groth16_ckb_repo" rev-parse HEAD)"
if [[ "$actual_groth16_ckb_revision" != "$expected_groth16_ckb_revision" ]]; then
  fail "groth16-ckb revision mismatch: expected $expected_groth16_ckb_revision, found $actual_groth16_ckb_revision"
fi

if ! rustup run "$host_toolchain" rustc --version >/dev/null 2>&1; then
  fail "Rust $host_toolchain is missing; install it with: rustup toolchain install $host_toolchain --profile minimal"
fi

if ! rustup run "$contract_toolchain" rustc --version >/dev/null 2>&1; then
  fail "Rust $contract_toolchain is missing; install it with: rustup toolchain install $contract_toolchain --profile minimal --target $target"
fi

if ! rustup target list --installed --toolchain "$contract_toolchain" \
  | grep -q "^${target}$"; then
  fail "Rust target $target is missing for $contract_toolchain; install it with: rustup target add --toolchain $contract_toolchain $target"
fi

echo "noir_ckb_revision=$(git -C "$repo_root" rev-parse HEAD)"
echo "groth16_ckb_revision=$actual_groth16_ckb_revision"
echo "host_rustc=$(rustup run "$host_toolchain" rustc --version)"
echo "host_cargo=$(rustup run "$host_toolchain" cargo --version)"
echo "contract_rustc=$(rustup run "$contract_toolchain" rustc --version)"
echo "os=$(uname -s)"
echo "arch=$(uname -m)"

echo "stage=host_checks"
cd "$repo_root"
cargo "+$host_toolchain" fmt --all -- --check
cargo "+$host_toolchain" check --locked --workspace --all-targets
cargo "+$host_toolchain" clippy --locked --workspace --all-targets -- -D warnings
cargo "+$host_toolchain" test --locked --workspace

echo "stage=generic_verifier_build"
RUSTUP_TOOLCHAIN="$contract_toolchain" \
  "$groth16_ckb_repo/scripts/build-ckb-script.sh"

echo "stage=capsule_binding_build"
"$repo_root/scripts/build-capsule-binding.sh"

generic_verifier="$groth16_ckb_repo/script/target/$target/release/ckb-script"
capsule_binding="$repo_root/contracts/target/$target/release/capsule-binding"

[[ -f "$generic_verifier" ]] || fail "generic verifier binary was not produced"
[[ -f "$capsule_binding" ]] || fail "Capsule binding binary was not produced"

echo "stage=proof_bound_ckb_vm_matrix"
matrix_log="$run_dir/ckb-vm-matrix.log"
GROTH16_CKB_SCRIPT_BIN="$generic_verifier" \
CKB_CAPSULE_BINDING_SCRIPT_BIN="$capsule_binding" \
cargo "+$host_toolchain" test --locked \
  -p ckb-integration-tests \
  --test capsule_transition \
  -- --ignored --nocapture 2>&1 | tee "$matrix_log"

if ! grep -q "test result: ok. 12 passed; 0 failed; 0 ignored" "$matrix_log"; then
  fail "the expected 12-case CKB-VM result was not found in the retained log"
fi

accepted_cycles="$(grep -Eo 'week10_proof_bound_capsule_cycles=[0-9]+' "$matrix_log" \
  | tail -n 1 \
  | cut -d= -f2)"
[[ -n "$accepted_cycles" ]] || fail "the accepted CKB-VM cycle observation was not found"

echo "reviewer_smoke_status=passed"
echo "ckb_vm_cases_passed=12"
echo "accepted_cycles=$accepted_cycles"
echo "reviewer_smoke_log=$log_path"
