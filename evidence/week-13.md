# Week 13 evidence record

Status: upstream SP1 benchmark and six-case verifier matrix passed;
fresh application proofs and SP1 Cell-transition binding remain future work.
Research and preparation date: 27 September 2026.
Reporting-period ending date: not yet assigned for the program extension.

## Objective

Evaluate community feedback recommending SP1 PLONK on CKB-VM, reproduce its
verifier baseline, and assess how the existing proof-to-Cell binding work could
apply to this backend. Final report claims must distinguish source inspection,
upstream measurements, local verification, and fresh proof generation.

## Source inspection

Inspected on 27 September 2026:

- [SP1 CKB forum announcement](https://talk.nervos.org/t/optimized-sp1-verifier-for-ckb-vm/10144).
- [Optimized verifier source](https://github.com/XuJiandong/sp1/blob/0cc2b42f287bbfce66973e19defb8b39fa361732/crates/verifier/src/plonk/mod.rs).
- [Pinned benchmark fixture](https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks/blob/026d5cb7199d71fd5bee3f165b446dd2243079d0/contracts/sp1-test/src/entry.rs).
- [Benchmark build requirements](https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks/blob/026d5cb7199d71fd5bee3f165b446dd2243079d0/Makefile).
- [SP1 security model](https://docs.succinct.xyz/docs/sp1/security/security-model).
- [SP1 hardware requirements](https://docs.succinct.xyz/docs/sp1/getting-started/hardware-requirements).

The fork's short revision `0cc2b42` resolves to
`0cc2b42f287bbfce66973e19defb8b39fa361732`. Its workspace declares SP1 `6.0.2`.
The benchmark revision selected for reproduction is
`026d5cb7199d71fd5bee3f165b446dd2243079d0`.

The benchmark contains an embedded proof and supplies empty public values.
The source therefore supports a verifier-fixture experiment, not a claim of
Noir-to-SP1 or Capsule-transition support.

The upstream report gives 63.2M cycles and a 246 KB binary. The local reproduction
below records 66,229,968 exact total cycles (displayed by the debugger as 63.2M)
and a 248,624-byte benchmark executable.

## Local execution gates

| Gate | Status | Evidence required |
| --- | --- | --- |
| Environment and pinned benchmark checkout | Passed 27 September 2026 | Retained preflight log; build prerequisites identified below |
| Upstream verifier build | Passed 27 September 2026 | Retained build log, unchanged lockfile, ELF size/hash |
| Upstream proof verification in CKB-VM | Passed 27 September 2026 | Guest result 0; 66,229,968 total cycles; debugger 1.1.1 |
| Verifier rejection matrix | Passed 27 September 2026 | One acceptance and five expected structured rejections |
| Fresh application proof | Pending feasibility assessment | Guest source/ELF, program key, public bytes, proof provenance |
| SP1 proof bound to actual Cells | Pending implementation | Valid proof + correct transition accept; wrong transition reject |

Preparation uses the existing repository baseline
`4b89aba5a2d8447db13129b1aa65b12873c11abb`. The untracked production roadmap and
post-program direction brief predate this work and are not part of the experiment.

## Gate 1: retained preflight

User-executed command: `bash scripts/week13-sp1-preflight.sh`.
Run time: `2026-09-27T10:44:45Z`.
Both the script and enclosing command returned exit code `0`.
The local raw log was inspected at
`target/week-13/logs/preflight.TMXi2v/terminal.log`.

| Item | Observed value |
| --- | --- |
| Host | Darwin arm64, macOS 15.8, build 24H23 |
| Physical RAM | 25,769,803,776 bytes (24 GiB) |
| Active Rust | `rustc 1.95.0 (59807616e 2026-04-14)` |
| Active Cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` |
| Other installed versioned Rust | `1.94.1` |
| Benchmark Rust `1.94.0` | Not installed |
| Active toolchain installed target | `aarch64-apple-darwin` |
| CKB debugger | `1.1.1` |
| Selected Clang | Homebrew `18.1.8` |
| Benchmark checkout | `026d5cb7199d71fd5bee3f165b446dd2243079d0`, clean |
| Locked SP1 verifier | `6.0.2`, revision `0cc2b42f287bbfce66973e19defb8b39fa361732` |
| Locked BN254 implementation | `ckb-alt-bn128 0.1.6` |
| Locked CKB standard-library versions | `0.18.0` and `1.0.2` in the upstream workspace |

SHA-256 of upstream files:

```text
contracts/sp1-test/src/entry.rs
0d04bab7d78bd41e137e3d17b3a8cf20baf60147c893bc9e039eb4cfa4f6222a

Cargo.lock
b99cb9964f07011e8f2dfc9de9b4bd7d20d42d6a856f2f68f202e4f82a2ad087
```

The next prerequisite gate is installing Rust 1.94.0 with its
`riscv64imac-unknown-none-elf` target and LLVM/Clang 19. The existing upstream
lockfile is retained; no dependency update is indicated by this preflight.
The local debugger is 1.1.1, while the published benchmark names 1.1.0. Local
results will therefore identify this environment difference explicitly.

The host's 24 GiB RAM is below the current documented 64 GB local PLONK proving
guidance. Existing-proof verification remains the first experiment; fresh local
PLONK proving has not been attempted or declared feasible on this host.

## Gate 1 follow-up: build prerequisites

User-provided installation and version output reviewed on 27 September 2026:

- Rust installation returned `week13_rust_install_exit_code=0`.
- `rustc 1.94.0 (4a4ef493e 2026-03-02)`.
- `cargo 1.94.0 (85eff7c80 2026-01-15)`.
- Rust 1.94.0 lists both `aarch64-apple-darwin` and
  `riscv64imac-unknown-none-elf` as installed targets.
- Homebrew Clang and LLVM archiver both report `19.1.7`.
- CKB debugger remains `1.1.1`.

LLVM availability is established by version output; a Homebrew installation exit
code was not supplied. The updated preflight rerun has not been supplied. These
observations are sufficient to proceed to the locked build, whose script records
the selected tools again. No build or runtime result was established at this gate.

## Gate 2a: locked upstream benchmark build

User-executed command: `bash scripts/week13-sp1-build.sh`.
Run start: `2026-09-27T10:52:35Z`.
The script and enclosing command both returned exit code `0`.
The local raw log was inspected at
`target/week-13/logs/build.fh30Eu/terminal.log`.

The build used Rust/Cargo 1.94.0, Clang/LLVM 19.1.7, and:

```text
RUSTFLAGS=-C target-feature=+zba,+zbb,+zbc,+zbs,-a -C debug-assertions
cargo +1.94.0 build --locked --release --target riscv64imac-unknown-none-elf -p sp1-test
```

The compiler output confirmed `sp1-verifier 6.0.2` from the pinned fork and
`ckb-alt-bn128 0.1.6`. Cargo reported completion in `1m 29s`; this is the build
duration reported for this run, not proof generation or verification time.

| Artifact property | Retained result |
| --- | --- |
| Binary | Upstream `target/riscv64imac-unknown-none-elf/release/sp1-test` |
| Exact size | 248,624 bytes |
| Format | ELF 64-bit LSB, RISC-V/RVC, soft-float ABI, statically linked, stripped |
| SHA-256 | `eb681935694ff4d8582a15d2a575e364b4087c9b8a45c83e9ab0d6d6772d4e45` |
| Lockfile SHA-256 after build | `b99cb9964f07011e8f2dfc9de9b4bd7d20d42d6a856f2f68f202e4f82a2ad087` |
| Upstream worktree | Clean after build |

This is the benchmark executable, including its embedded proof fixture. The
build did not execute the verifier or generate a new proof. The next gate runs
this exact binary in ckb-debugger 1.1.1, retaining the guest result separately
from the debugger process exit code and cycle count.

## Gate 2b: upstream proof verification in CKB-VM

User-executed command: `bash scripts/week13-sp1-verify.sh`.
Run time: `2026-09-27T10:56:21Z`.
Raw local log inspected:
`target/week-13/logs/verify.SEZ1rD/terminal.log`.

```text
ckb-debugger 1.1.1
script_version=2
mode=fast
max_cycles=250000000
fixture=upstream_embedded_proof
public_values=empty
Script log: load_plonk_verifying_key_from_bytes costs: 17892 K cycles
Script log: load_plonk_proof_from_bytes costs: 82 K cycles
Script log: cost of sp1(zkVM) verifying cycles: 64610 K
Run result: 0
All cycles: 66229968(63.2M)
week13_verification_command_exit_code=0
week13_verify_script_exit_code=0
```

The executed binary matched the retained SHA-256
`eb681935694ff4d8582a15d2a575e364b4087c9b8a45c83e9ab0d6d6772d4e45`.
The guest returned zero, so the benchmark's assertion that its embedded proof
verifies succeeded. The debugger and enclosing script also returned zero.

Use **66,229,968 cycles** as the exact whole-program measurement. The displayed
`63.2M` corresponds to scaling by 1,048,576 and rounding. The source's internal
`64610 K` counter divides by 1024 and truncates, and covers only the verifier
call; it is not an exact whole-program total. The published and local rounded
displays match, but the published exact cycle count is not established here.

This verifies the upstream fixture with empty public values. No new SP1 proof
was generated, no Noir program was executed through SP1, and no Capsule Cell
transition was checked by this benchmark.

## Gate 3 preparation: verifier rejection matrix

Added `experiments/week13-sp1` and `scripts/week13-sp1-matrix.sh`. The harness
uses an extracted copy of the same 964-byte public proof. It is built in a
separate ignored checkout using the same upstream lockfile. Six cases cover the
positive control and changed program hash, public values, proof body, proof
length, and wrapper verifier key. Specific returned errors are required;
crashes and cycle exhaustion fail the test. Compilation and execution passed as
recorded below.

### Harness build

User-executed command: `bash scripts/week13-sp1-matrix.sh build`.
Run start: `2026-09-27T11:01:45Z`.
Raw local log inspected:
`target/week-13/logs/matrix-build.vomrGg/terminal.log`.
Both the build script and enclosing command returned exit code `0`.

The build retained Rust/Cargo 1.94.0, Clang/LLVM 19.1.7, the original Rust flags,
and the original lockfile. Cargo reported release compilation in `6.11s`.

| Artifact | Retained value |
| --- | --- |
| Experimental benchmark binary size | 247,576 bytes |
| Binary format | Statically linked, stripped 64-bit RISC-V ELF |
| Binary SHA-256 | `5ed55c5772c9a779ece036f8876fdf17eb593a2a6cd2221b173246c9ae437336` |
| Harness entry source SHA-256 | `eca330cc83fb3a206af2b1fce963131a55a7aafe20201fb10080e456e8380814` |
| Extracted fixture source SHA-256 | `d150124ad050bffe11712cc224173f85f192ee54f0fac4e8c9a81c109f55c85a` |
| Upstream Cargo.lock SHA-256 | `b99cb9964f07011e8f2dfc9de9b4bd7d20d42d6a856f2f68f202e4f82a2ad087` |

The experimental checkout reports exactly the intended modified
`contracts/sp1-test/src/entry.rs` and added
`contracts/sp1-test/src/week13_fixture.rs`. The original benchmark checkout is
preserved separately. The experimental binary size is not a replacement for the
248,624-byte original benchmark measurement. No matrix cases ran during this
build.

### Harness execution

User-executed command: `bash scripts/week13-sp1-matrix.sh run`.
Run time: `2026-09-27T11:02:46Z`.
Raw local log inspected:
`target/week-13/logs/matrix-run.KEqTdS/terminal.log`.
Each case also has a separate log in that directory.

The executable passed its retained SHA-256 check. Runs used debugger 1.1.1,
script version 2, fast mode, and a maximum of 250,000,000 cycles per case.

| Case | Verifier outcome | Verifier-call cycles | Whole-program cycles |
| --- | --- | ---: | ---: |
| Original fixture | Accepted | 66,158,965 | 66,281,578 |
| Wrong program hash | `PairingCheckFailed` | 131,200,057 | 131,326,663 |
| Wrong public-value bytes | `PairingCheckFailed` | 130,827,021 | 130,954,090 |
| Changed proof body | `PairingCheckFailed` | 128,681,601 | 128,808,382 |
| Proof truncated to 99 bytes | `GeneralError(InvalidData)` | 614 | 130,253 |
| Changed wrapper verifier key | `PlonkVkeyHashMismatch` | 1,807,321 | 1,934,174 |

Every case logged the expected outcome and guest `Run result: 0`. On negative
cases the guest returns zero only after the expected verifier error matches;
this does not mean that the verifier accepted the altered input.

```text
week13_matrix_status=passed
week13_matrix_cases_passed=6
week13_matrix_run_exit_code=0
week13_matrix_run_command_exit_code=0
```

The three pairing-failure cases cost roughly twice the positive verification.
Source inspection of the pinned `PlonkVerifier::verify_with_exit_code` shows a
first verification using a SHA-256 public-value digest, followed on failure by
another verification using Blake3. The repeated key/proof loading messages in
these logs agree with that path. This explains the observed cost pattern; it
does not establish a worst-case bound for all malformed inputs.

The wrong-key case exercises the wrapper-key fingerprint check. The truncated
case exercises the top-level minimum-length check. Neither establishes broad
decoder robustness or a security audit. The changed-public-values case replaces
an empty byte string with `[1]`; it is not a successful proof of a nonempty
application statement.

## Week 13 scope conclusion

The upstream verifier and the bounded rejection matrix are locally reproduced.
The next technical gate needs an SP1 guest and a compatible proof with nonempty,
versioned public values, followed by actual CKB Cell-binding tests. Local fresh
PLONK proving has not been attempted on this 24 GiB host. An existing maintained
fixture or a suitable proving environment is needed to proceed sensibly.

This is enough evidence for a Week 13 verifier-evaluation report, without
claiming that the existing Noir pipeline has migrated to SP1. The report draft
is in [docs/week-13-report.md](https://github.com/wamimi/CKBuilder/blob/main/ckbuilder-journey/reports/week-13.md).

See [research and test plan](../docs/week-13-sp1-evaluation.md).
