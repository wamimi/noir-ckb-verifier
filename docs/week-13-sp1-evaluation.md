# Week 13: evaluating SP1 PLONK verification on CKB

Status: local upstream benchmark and six-case verifier rejection matrix passed;
fresh application proofs and SP1 Cell-transition binding remain future work.
Research date: 27 September 2026.

## Why evaluate another proof system?

Community review identified the circuit-specific trusted setup in the current
direct Noir-to-Groth16 path as an obstacle to a general developer tool. Changing
the circuit changes its setup requirements. The retained development setup is
useful for testing but is not production ceremony material.

The proposed alternative is Xu Jiandong's optimized SP1 PLONK verifier for
CKB-VM. This is a meaningful candidate for evaluation. Selecting it as the
project's long-term backend requires evidence about verification, proving,
application binding, and the developer workflow.

The project's central requirement survives a backend change: the program whose
execution was proven and its public statement must authorize the actual Cell
transition.

## Findings from primary sources

### Setup assumptions

SP1's PLONK wrapper uses the universal Aztec Ignition setup. This removes the
need for an application-specific ceremony; it does not remove trusted setup
assumptions. A program verification key/hash is still needed to identify the
program whose execution is accepted. Generating that program identifier is
different from conducting a trusted setup ceremony.

SP1 also offers a Groth16 wrapper around its proof system. A shared zkVM wrapper
and a direct Groth16 circuit for each application have different setup
boundaries. The present experiment specifically targets the optimized PLONK
path recommended by the reviewer.

Source: [SP1 security model](https://docs.succinct.xyz/docs/sp1/security/security-model).

### What the CKB port establishes

The [forum announcement](https://talk.nervos.org/t/optimized-sp1-verifier-for-ckb-vm/10144)
describes an SP1 6.0.2 fork using optimized BN254 arithmetic and `no_std`, with
approximately 63 million verification cycles and a 246 KB binary. These are
upstream measurements, not results reproduced by this project.

The [pinned benchmark README](https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks/blob/026d5cb7199d71fd5bee3f165b446dd2243079d0/README.md)
reports 63.2M cycles with ckb-debugger 1.1.0. Its
[SP1 benchmark source](https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks/blob/026d5cb7199d71fd5bee3f165b446dd2243079d0/contracts/sp1-test/src/entry.rs)
contains an embedded proof, a program key hash, and **empty public values**.
The local run demonstrated verification of that fixture. It did not demonstrate
proof generation, execution of a Noir circuit, or Capsule binding.

The benchmark measures the verifier call internally as well as being runnable
under ckb-debugger. Internal debug output uses units of 1024 cycles and truncates
when formatting; retain the debugger's exact total separately.

### The interface binds a program and public bytes

The pinned [PLONK entry point](https://github.com/XuJiandong/sp1/blob/0cc2b42f287bbfce66973e19defb8b39fa361732/crates/verifier/src/plonk/mod.rs)
accepts proof bytes, public-value bytes, a program verification-key hash, and
PLONK verifier-key bytes. Its normal verification path also checks successful
program exit and the expected recursion-key root.

A CKB application must pin the expected program identity and verifier version.
Letting the prover choose an arbitrary accepted program would permit proofs of
the wrong application. Public bytes must be decoded with an explicit schema and
compared to values derived from the transaction. Reusing the old Groth16
Molecule payload without a new format specification is not sufficient.

This fork calls CKB cycle syscalls inside PLONK verification. The first runtime
target is CKB-VM; ordinary native Rust test execution is not assumed compatible.

### SP1 is not a direct replacement for the Noir backend

SP1 proves execution of programs compiled for its zkVM. Its CKB verifier does
not consume Noir ACIR or the existing snarkjs proof format. A small Rust guest
that implements the Capsule relation could test SP1 application binding, but
would be a separate implementation of the relation, not Noir compatibility.

Preserving Noir as the frontend would require a separately evaluated bridge,
such as proving execution of an ACIR interpreter or verifying another proof
inside an SP1 guest. Each adds constraints, costs, and a new security boundary.
Neither bridge has been implemented or established by this research.

### Version and hardware requirements

The port uses the API and verifier keys from its pinned 6.0.2 source. Current
[off-chain verification documentation](https://docs.succinct.xyz/docs/sp1/generating-proofs/off-chain-verification)
describes a newer version and upstream `no_std` support; its API must not be
substituted blindly into this older fork. The claim that upstream lacks
`no_std` is historical context from the forum, not a current blanket claim.

The current [hardware guide](https://docs.succinct.xyz/docs/sp1/getting-started/hardware-requirements)
lists 64 GB or more RAM for local PLONK proving. This is guidance for planning,
not a measured requirement for the pinned fixture. Verification of an existing
proof does not require generating it again. The initial experiment therefore
does not install the full prover or use a paid proving service.

The pinned benchmark uses Rust 1.94.0. Its root Makefile states that the SP1
benchmark needs Clang 19 or newer. It enables RISC-V bit-manipulation features;
the VM version and compiler flags belong in every performance record.

## Comparison to retain in the report

| Question | Existing path | SP1 PLONK candidate |
| --- | --- | --- |
| Program input | Supported pinned Noir circuit | Program for SP1; Noir bridge unestablished |
| Application setup | Circuit-specific Groth16 phase 2 | Universal PLONK setup; program key still required |
| CKB evidence | Retained Capsule CKB-VM matrix | Upstream embedded proof verified locally; six-case verifier matrix passed |
| Public statement | Seven ordered field values | Bytes committed by the guest, requiring a schema |
| Transition binding | Implemented Capsule Type | Needs implementation and adversarial tests |
| Known size/cycles | 98,464-byte verifier; 101,625,705 cycles for the combined Capsule case | Local benchmark 248,624 bytes / 66,229,968 total cycles, for a different fixture |
| Proving effort | Retained small development circuit | Fresh local proving cost not measured |

The two cycle figures use different workloads and measurement boundaries. They
do not establish a speedup for an equivalent Capsule application.

## Pinned source candidates

| Component | Revision / version |
| --- | --- |
| Existing repository baseline | `4b89aba5a2d8447db13129b1aa65b12873c11abb` |
| Optimized SP1 fork | `0cc2b42f287bbfce66973e19defb8b39fa361732` |
| Fork workspace version | `6.0.2` |
| Benchmark repository | `026d5cb7199d71fd5bee3f165b446dd2243079d0` |
| Benchmark Rust toolchain | `1.94.0` |
| Published benchmark debugger | `1.1.0` |

Actual Cargo resolution, compiler versions, artifact hashes, and VM version must
be recorded from the reproduction. A manifest dependency range alone is not a
transitive dependency pin.

## Execution gates

Run each gate and review its output before proceeding. Preserve failed runs as
part of the evidence.

1. **Environment and source baseline.** Record host/architecture/RAM, available
   Rust targets, Clang/LLVM, debugger, repository status and pinned benchmark
   source. Run `bash scripts/week13-sp1-preflight.sh` from the repository root.
   This prepares only an ignored benchmark checkout and a terminal log.
2. **Unmodified upstream reproduction.** Resolve prerequisites, inspect and
   retain the benchmark lockfile, build only `sp1-test`, record ELF bytes and
   SHA-256, run it in CKB-VM, and retain exact cycles and exit status. Do not run
   the Makefile's broad install/CI targets. The documented `prepare` target
   downloads an old x86 Linux debugger, unsuitable as a generic macOS setup.
   After confirming Rust 1.94.0, its RISC-V target, and Homebrew LLVM 19, run
   `bash scripts/week13-sp1-build.sh`. It builds only `sp1-test` using the
   original lockfile and upstream Rust flags, captures the log, and records the
   binary size/hash. Runtime verification is a subsequent gate.
   The retained 27 September build produced a 248,624-byte benchmark executable.
   Run `bash scripts/week13-sp1-verify.sh` to execute that exact binary, pinned
   by hash, with debugger 1.1.1, script version 2, and a 250M cycle limit.
   Review the guest run result, exact total cycles, and command exit status.
   Retained result: guest and command exit codes `0`, total `66,229,968` cycles
   (debugger display `63.2M`). See the evidence record for measurement units.
3. **Verifier rejection matrix.** In an isolated experimental harness, verify
   the original fixture and reject a changed program hash, changed public-value
   bytes, changed proof body, truncated proof, and wrong verifier key. Record
   structured rejection, panic, or VM failure separately. Resource exhaustion
   is not a successful cryptographic rejection test.
   The prepared harness is documented in
   [the experiment README](../experiments/week13-sp1/README.md).
   Run `bash scripts/week13-sp1-matrix.sh build`, review its output, then run
   `bash scripts/week13-sp1-matrix.sh run`.
   Retained result: all six cases passed, with one acceptance and five expected
   structured rejections. Pairing-failure cases used approximately 129–131M
   whole-program cycles, compared with 66,281,578 for the harness positive case.
4. **Application-binding experiment.** Select a feasible proof-generation
   environment and produce a small guest with nonempty, versioned public
   values. Pin the program hash. Verify the same proof while changing actual
   Cell state/identity/domain and require the binding script to reject. Keep
   proof corruption tests distinct from valid-proof/wrong-transition tests.
   This gate is conditional on proving resources and is not yet implemented.
5. **Direction and report.** Compare results and remaining work. Decide whether
   to evaluate an SP1 application profile, investigate a Noir bridge, or retain
   the current backend while seeking narrower improvements. Finalize the Week
   13 report using actual dates and results, including any blockers.

Week 13 can provide a useful verifier evaluation even if fresh proving remains
blocked. That outcome must be described as verifier reproduction, not a working
SP1 Capsule integration.

## Questions for maintainers after reproduction

- Which exact prover release and proof-export command should pair with this
  verifier revision? Is a small nonempty-public-values fixture available with
  its guest source, ELF, program key, and generation provenance?
- Is this fork the preferred maintained CKB integration, and which fixes or
  advisories apply to its pinned version?
- What proving environment is practical for a small developer demonstration?
- For typed application state, which CKB verification placement and program-key
  pinning pattern do maintainers recommend?

The funding direction should be narrowed after these answers and local evidence,
rather than treating a verifier benchmark as a complete application toolkit.

## Decision after the first local experiments

The verifier is now an experimentally supported candidate for a CKB integration.
The next bounded task is obtaining a compatible guest/proof pair with nonempty
public values and specifying its mapping to Cell state. A Rust guest may be a
practical first experiment; it would establish an SP1 application path without
settling the separate question of a Noir frontend.

The measured rejection cost also belongs in the integration design. The pinned
verifier retries verification with a Blake3 public-value hash when its SHA-256
attempt fails, explaining the repeated parsing logs and roughly doubled cost in
the three pairing-failure cases. Cycle budgets must account for rejection paths;
the positive benchmark alone does not give an adversarial cost bound.

See the [retained experiment evidence](../evidence/week-13.md).
