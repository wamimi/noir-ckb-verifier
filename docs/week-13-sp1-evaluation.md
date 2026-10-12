# Week 13: SP1 PLONK verification on CKB — evaluation

Evaluated 27 September 2026. **Outcome:** the optimized SP1 verifier was
reproduced on CKB-VM and passed a six-case rejection matrix. It was not adopted
for this stage, because it does not accept Noir circuits; the project continued
with Noir to Groth16. Retained results are in [evidence/week-13.md](../evidence/week-13.md).

## Why SP1 was evaluated

Community review identified the circuit-specific trusted setup of the direct
Noir-to-Groth16 path as an obstacle for a general developer tool: every circuit
change requires new setup material, and the development setup is not production
ceremony material. Xu Jiandong's optimized SP1 PLONK verifier for CKB-VM was
suggested as an alternative and evaluated on that basis.

The project's central requirement applies to any backend: the program whose
execution was proven, and its public statement, must authorize the actual Cell
transition.

## What was measured

| Check | Result |
| --- | --- |
| Build of the upstream `sp1-test` benchmark (pinned sources) | 248,624-byte RISC-V executable |
| Verification of the upstream embedded proof in CKB-VM (ckb-debugger 1.1.1, 250M cycle limit) | Guest and command exit `0`; **66,229,968** total cycles (debugger display 63.2M) |
| Rejection matrix (isolated harness) | **6 of 6** passed: one acceptance; changed program hash, changed public values, changed proof body, truncated proof and wrong verifier key all rejected with structured errors |
| Cost of a rejection | Pairing-failure cases used about 129–131M cycles, against 66,281,578 for the harness's positive case |

The upstream fixture uses **empty public values**. The evaluation therefore
verified a fixed proof; it did not generate a new proof, run a Noir circuit, or
bind an SP1 proof to a Cell transition.

The doubled rejection cost has a specific cause: when SHA-256 public-value
verification fails, the pinned verifier retries with a Blake3 public-value hash.
Cycle budgets for an integration must therefore be set from rejection paths, not
from the positive benchmark alone.

## What the evaluation established

**Setup assumptions.** SP1's PLONK wrapper uses the universal Aztec Ignition
setup. That removes the application-specific ceremony, not trusted setup
assumptions altogether. A program verification key or hash still identifies the
program whose execution is accepted. SP1 also offers a Groth16 wrapper; this
evaluation covered the optimized PLONK path that was recommended.
Source: [SP1 security model](https://docs.succinct.xyz/docs/sp1/security/security-model).

**Upstream figures.** The [forum announcement](https://talk.nervos.org/t/optimized-sp1-verifier-for-ckb-vm/10144)
describes an SP1 6.0.2 fork with optimized BN254 arithmetic and `no_std`, about
63 million verification cycles and a 246 KB binary. The
[pinned benchmark README](https://github.com/XuJiandong/ckb-rust-algorithm-benchmarks/blob/026d5cb7199d71fd5bee3f165b446dd2243079d0/README.md)
reports 63.2M cycles with ckb-debugger 1.1.0. The local measurements above are
consistent with these.

**Interface.** The pinned [PLONK entry point](https://github.com/XuJiandong/sp1/blob/0cc2b42f287bbfce66973e19defb8b39fa361732/crates/verifier/src/plonk/mod.rs)
accepts proof bytes, public-value bytes, a program verification-key hash and
PLONK verifier-key bytes, and also checks successful program exit and the
expected recursion-key root. A CKB application would have to pin the expected
program identity and verifier version, and decode public bytes against an
explicit schema compared with values derived from the transaction. This fork
calls CKB cycle syscalls inside verification, so it targets CKB-VM rather than
native test execution.

**Noir compatibility.** SP1 proves programs compiled for its zkVM. Its CKB
verifier does not consume Noir ACIR or snarkjs proofs. A Rust guest implementing
the same rule would be a separate implementation of that rule, not Noir support.
Keeping Noir as the developer's language would require a separate bridge, for
example proving an ACIR interpreter inside SP1, or verifying another proof inside
an SP1 guest. Each adds cost and a new security boundary. No such bridge was
found established or built during this evaluation; that is not a claim that none
exists elsewhere.

**Proving resources.** The current
[hardware guide](https://docs.succinct.xyz/docs/sp1/getting-started/hardware-requirements)
lists 64 GB or more RAM for local PLONK proving. This was not measured here: the
evaluation verified existing proofs and did not install the full prover or use a
paid proving service. The pinned benchmark uses Rust 1.94.0 and requires Clang 19
or newer, with RISC-V bit-manipulation features enabled.

## Comparison

| Question | Noir to Groth16 (this project) | SP1 PLONK candidate |
| --- | --- | --- |
| Program input | Supported pinned Noir circuit | Program compiled for SP1; no Noir bridge established |
| Application setup | Circuit-specific Groth16 phase 2 | Universal PLONK setup; program key still required |
| CKB evidence | Capsule and counter CKB-VM matrices | Upstream fixture verified locally; six-case rejection matrix |
| Public statement | Ordered field values | Bytes committed by the guest; needs a schema |
| Transition binding | Implemented and tested | Not implemented |
| Size and cycles | 98,464-byte verifier; 101,625,705 cycles for the combined Capsule case | 248,624 bytes; 66,229,968 cycles for a different fixture |
| Proving effort | Small development circuits, proved locally | Not measured |

The cycle figures come from different workloads and measurement boundaries; they
do not show a speedup for an equivalent application.

## Decision

The project continued with the Noir-to-Groth16 path and its maintained
visibility-ordering fix. Adopting SP1 while keeping Noir would have required
building a Noir-to-SP1 bridge first, which is a separate project, and rewriting
circuits in Rust would have abandoned the Noir workflow the project exists to
support. The per-circuit setup cost remains real; the planned private tally
addresses it with a multi-party ceremony rather than a backend change.

This is a scoping decision for the current stage. It does not establish that
Groth16 is generally preferable. If a Noir-to-SP1 path becomes available, the
transaction-binding design is the part expected to carry over.

## Reproducing the experiment

All scripts run from the repository root and write only to ignored directories:

| Step | Command | Result recorded |
| --- | --- | --- |
| Environment and source baseline | `bash scripts/week13-sp1-preflight.sh` | Host, toolchains, pinned benchmark checkout |
| Build `sp1-test` only | `bash scripts/week13-sp1-build.sh` | 248,624-byte executable and its hash |
| Verify in CKB-VM | `bash scripts/week13-sp1-verify.sh` | Exit codes and exact cycles |
| Rejection matrix | `bash scripts/week13-sp1-matrix.sh build`, then `run` | Six cases, structured results |

Requirements: Rust 1.94.0 with its RISC-V target and LLVM 19. The benchmark's
broad Makefile install targets are not used; its `prepare` target downloads an
x86 Linux debugger unsuitable for macOS. Details are in the
[experiment README](../experiments/week13-sp1/README.md).

## Pinned sources

| Component | Revision / version |
| --- | --- |
| Repository baseline at evaluation | `4b89aba5a2d8447db13129b1aa65b12873c11abb` |
| Optimized SP1 fork | `0cc2b42f287bbfce66973e19defb8b39fa361732` |
| Fork workspace version | `6.0.2` |
| Benchmark repository | `026d5cb7199d71fd5bee3f165b446dd2243079d0` |
| Benchmark Rust toolchain | `1.94.0` |
| Debugger used locally | `1.1.1` (upstream figures used `1.1.0`) |

## Questions left open

- Which prover release and proof-export command pair with this verifier revision,
  and is a small fixture with non-empty public values (guest source, ELF, program
  key) available?
- Is this fork the preferred maintained CKB integration, and which fixes apply to
  its pinned version?
- What proving environment is practical for a small developer demonstration?
- Which CKB verification placement and program-key pinning pattern suits typed
  application state?
