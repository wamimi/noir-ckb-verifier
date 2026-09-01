# Week 12 evidence record

Week Ending: 16 August 2026

This is a Week 12 catch-up record finalized after the nominal week ending. Every
new result below must use its actual execution or review date. Pending gates are
not completion claims.

## Objective

Close the CKBuilder program with an externally reviewable developer preview,
retained local full-pipeline evidence, an explicit support boundary, and a
focused request for independent reproduction and post-program direction.

## Baseline

- `noir-ckb-verifier` baseline revision:
  `07247b4b6579e1bcdd904b43f5fc9b2cc02e28bc`
- Week 12 reviewer workflow revision:
  `9d3e41a1ff70b40155647bff1b032de10d165bc9`
  (`feat: add Week 12 reviewer smoke workflow`)
- Week 11 hosted retained-fixture CI: previously verified and documented; not a
  substitute for the Week 12 independent clean-clone gate.
- Upstream Noir-Groth16 issue:
  https://github.com/jamesbachini/Noir-Groth16/issues/1
- Issue opened: 20 August 2026.
- Status checked 1 September 2026: open, with no maintainer response retained at
  that time.

## Gate 1: reviewer surface

Status: **Passed 1 September 2026**

Required files:

- `scripts/reviewer-smoke.sh`
- `docs/reviewer-quickstart.md`
- `.github/ISSUE_TEMPLATE/reproduction.yml`

Static checks:

```bash
bash -n scripts/reviewer-smoke.sh
git diff --check
```

Retained results:

- `bash -n scripts/reviewer-smoke.sh` returned exit code `0`;
- `git diff --check` returned exit code `0`;
- the repository remained on baseline revision
  `07247b4b6579e1bcdd904b43f5fc9b2cc02e28bc`; and
- the production-readiness roadmap and Week 12 direction brief remained
  separate untracked planning files.

## Gate 2: local retained-fixture smoke test

Status: **Passed 1 September 2026**

Run from the repository root:

```bash
./scripts/reviewer-smoke.sh
echo "week12_local_smoke_exit_code=$?"
```

Retained terminal summary:

```text
test result: ok. 12 passed; 0 failed; 0 ignored
reviewer_smoke_status=passed
ckb_vm_cases_passed=12
accepted_cycles=101625705
reviewer_smoke_log=/Users/xiaomao/noir-ckb-verifier/target/noir-ckb/reviewer-smoke/20260901T145144Z/terminal.log
week12_local_smoke_exit_code=0
```

Recorded environment:

| Component | Retained value |
|---|---|
| `noir-ckb-verifier` HEAD | `07247b4b6579e1bcdd904b43f5fc9b2cc02e28bc` |
| `groth16-ckb` | `d64c769ffe2d2edb5eb308dc59058efda77c2f83` |
| Host Rust | `rustc 1.95.0 (59807616e 2026-04-14)` |
| Host Cargo | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` |
| Contract Rust | `rustc 1.94.1 (e408947bf 2026-03-25)` |
| Platform | Darwin arm64 |
| Run identifier | `20260901T145144Z` |

The normal workspace suite passed 14 host tests: four adapter unit tests, seven
cross-library interoperability tests, and three `noir-ckb` workflow unit tests.
The 12 Capsule transaction tests and two direct verifier tests were correctly
listed as ignored because the normal suite does not inject the required RISC-V
binaries.

Both RISC-V release scripts then built successfully. The explicit
binary-supplied matrix accepted the intended transition and rejected all eleven
negative cases:

| Case | Result / script exit code |
|---|---:|
| Intended proof-bound transition | accepted; `101625705` cycles |
| Truncated witness | `17` |
| Missing VK | `12` |
| Malformed Capsule args | `21` |
| Duplicate verifier-lock group | `33` |
| Duplicate Capsule input group | `23` |
| Changed verifier lock | `32` |
| Wrong Capsule identity | `30` |
| Malformed Capsule Cell data | `25` |
| Wrong new state | `30` |
| Wrong replay domain | `30` |
| Invalid proof with matching changed transition | `5` |

The cycle result was freshly observed in this run and happens to match the
earlier Week 10 retained value. It remains a comparison point, not a guarantee.

## Gate 3: full generated-proof commands

Status: **Passed 1 September 2026**

```bash
cargo +1.95.0 build --locked --release \
  -p noir-ckb-cli \
  --bin noir-ckb

./target/release/noir-ckb build
./target/release/noir-ckb prove
./target/release/noir-ckb test
```

Required status fields:

```text
build_status=compatible
prove_status=verified
test_status=passed
ckb_vm_cases_passed=12
```

Generated setup material is development-only. Never commit or publish the
witness, Powers of Tau transcript, proving keys, or `.zkey` files.

### Build-stage result

The release CLI build returned exit code `0` and produced:

| Property | Retained value |
|---|---|
| Binary | `target/release/noir-ckb` |
| Exact size | `2,691,568` bytes |
| Format | Mach-O 64-bit executable arm64 |
| SHA-256 | `239c2b376d3d16cdb5055be79f76c40fa71b60acc9822f892258139fb65cfd53` |

The `noir-ckb build` command returned exit code `0` with:

```text
build_status=compatible
public_input_count=7
private_input_count=1
constraint_count=5
wire_count=11
```

The new build run identifier was `1788274891639`. Noir reported public
witnesses `[w0, w1, w2, w3, w4, w5, w6]`, private witness `[w7]`, and three
`AssertZero` opcodes. The backend emitted an 11-wire, five-constraint R1CS and
an 11-element witness. Pinned snarkjs reported seven public inputs, one private
input, no outputs, no custom gates, and `WITNESS IS CORRECT`.

The build manifest preserved the required ordered statement:

```text
capsule_id, old_state_commitment, old_nullifier, new_state_commitment,
action_id, new_nullifier, replay_domain

[11, 65, 5, 66, 1, 96, 13]
```

Retained build artifact hashes:

| Artifact | SHA-256 |
|---|---|
| Capsule binding binary | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |
| Noir circuit artifact | `5e9397b08d4403e6a71b4976fbb99f95bc3428af36e289b8453abc0ec4a4f870` |
| Public development inputs | `f49ccc1dd144111fe78fb9a5ba0e178b0318978976d9af7dac91162d48c3c9a1` |
| Generic verifier binary | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |
| Parsed ACIR summary | `2edfdfee74fcda757a9c38c73845b3a99e259545189beb4fb95740f7f6100a0f` |
| R1CS | `7aa020246d9b4f25c113e36eb5b975051086601bd79fc41a5c2b769ca2624a02` |
| Exported witness JSON | `624516f5ed88e122e7ce949be5bdd9f92df94f50c27403a56272be91a2d45340` |
| WTNS | `3d025058780ff5ce1dabe3deb04a3553b511ef63ba2e50f682104ac9800f3a47` |

The build manifest recorded `repository_dirty=true` because the Week 12
reviewer documentation and script had not yet been committed. Generated build
artifacts remained below ignored `target/` paths, and the final Git status
contained only the expected source/document changes and the two pre-existing
untracked planning documents.

### Prove-stage result

The `noir-ckb prove` command created proof run `1788275180486` and returned exit
code `0` with:

```text
prove_status=verified
public_vector=["11", "65", "5", "66", "1", "96", "13"]
vk_data_hash=79c5f77da783462ee3a89f47e608a02a4d80e1430414fcfd85bfcc9d7f697d96
```

Nargo solved the circuit witness successfully. Pinned snarkjs then:

- created a fresh development-only power-12 BN254 transcript;
- added one explicitly public development contribution;
- prepared Phase 2 and reported `Powers Of tau file OK!` and
  `Powers of Tau Ok!`;
- generated and contributed to the circuit-specific ZKey;
- reported `ZKey Ok!` against the selected R1CS and transcript;
- exported the verification key and generated a Groth16 proof;
- accepted the generated intended public vector; and
- rejected changed new-state, Capsule-identity, and replay-domain vectors with
  `Invalid proof`.

The contribution labels retain `Week 11` because that is when the packaged CLI
was implemented. The run identifier, setup artifacts, and proof were generated
fresh on 1 September 2026 and remain development-only.

Public artifact sizes:

| Artifact | Exact size |
|---|---:|
| Verification key JSON | 4,027 bytes |
| Proof JSON | 803 bytes |
| Public vector JSON | 49 bytes |

Proof-manifest hashes:

| Artifact | SHA-256 |
|---|---|
| Wrong Capsule identity vector | `948764a87743f517e72ab115113beac0cae1db97214de10dc066ba30991accbb` |
| Wrong new-state vector | `0fa76bcc458e982d4737999db88cd1d995d23853daa2e0919a6758e5ade822f1` |
| Wrong replay-domain vector | `bcf49057589b5b116b679d8384df36b76a86d2de1fdb62b4d67261e4764066ce` |
| Proof | `3ce1baf76094c88d0d9115748b1d1256e5ff74afff62278e0f6ccc7ec01c9d7d` |
| Final development PTAU | `e351cfc26e04087a863c6dd4fdf1d21b947dc06aeefc006e819aa28537117a7d` |
| Public vector | `ad6f5ea7390ce0b72d6741fd1f24299008f992f6da56dd9ffa5e184c90cd2b08` |
| R1CS | `7aa020246d9b4f25c113e36eb5b975051086601bd79fc41a5c2b769ca2624a02` |
| Verification key | `283a567af23a97a70776316a82dd2c38ef3b8580bd3a9eff53f02faf8081fb10` |
| Molecule VK payload | `cccbfda1a80d80a612b4b957b2aa509b7c4bc31eaf187c6646cafabc0bbaa4ab` |
| Molecule witness payload | `04685886295a33e30650421d0066a8cb9d42c6082e71cc535b6393022fc935e1` |
| WTNS | `3d025058780ff5ce1dabe3deb04a3553b511ef63ba2e50f682104ac9800f3a47` |
| Final ZKey | `a3c2158dd92d910e8bb9181f957765a82b298d8a93ed8735963c3e92dd38d3ec` |

The proof, transcript, witness, and keys remain below ignored `target/` or
circuit target paths. The final Git status was unchanged from the build stage.

### Test-stage result

The `noir-ckb test` command selected proof run `1788275180486` through its
manifest, created test run `1788275589389`, and returned exit code `0` with:

```text
test_status=passed
ckb_vm_cases_passed=12
accepted_cycles=101640005
test_report=/Users/xiaomao/noir-ckb-verifier/target/noir-ckb/proof-bound-capsule/tests/1788275589389/test-report.json
week12_noir_ckb_test_exit_code=0
```

The normal workspace suite first passed 14 host tests: four adapter unit tests,
seven interoperability tests, and three `noir-ckb` workflow unit tests. The 14
tests requiring injected RISC-V binaries were listed as ignored in that normal
run, as designed.

The CLI then supplied the freshly built generic verifier and Capsule binding
binaries and the freshly generated proof fixture to the explicit CKB-VM
matrix. All 12 cases passed:

| Case | Result / script exit code |
|---|---:|
| Intended proof-bound transition | accepted; `101640005` cycles |
| Truncated witness | `17` |
| Missing VK | `12` |
| Malformed Capsule args | `21` |
| Duplicate verifier-lock group | `33` |
| Duplicate Capsule input group | `23` |
| Changed verifier lock | `32` |
| Wrong Capsule identity | `30` |
| Malformed Capsule Cell data | `25` |
| Wrong new state | `30` |
| Wrong replay domain | `30` |
| Invalid proof with matching changed transition | `5` |

The generated-fixture acceptance path used `101640005` cycles, which is 14,300
cycles above the retained-fixture smoke result. This is a freshly observed
proof-specific comparison point, not a stable benchmark or protocol limit.

The 936-byte JSON test report retained the exact proof-manifest relationship
and these artifact hashes:

| Artifact | SHA-256 |
|---|---|
| Capsule binding binary | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |
| Generic verifier binary | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |
| Generated proof | `3ce1baf76094c88d0d9115748b1d1256e5ff74afff62278e0f6ccc7ec01c9d7d` |
| Public vector | `ad6f5ea7390ce0b72d6741fd1f24299008f992f6da56dd9ffa5e184c90cd2b08` |
| Verification key | `283a567af23a97a70776316a82dd2c38ef3b8580bd3a9eff53f02faf8081fb10` |

The final `git diff --check` returned exit code `0`. Git status remained
unchanged: only the Week 12 reviewer files were modified or untracked, together
with the two pre-existing untracked planning documents.

## Gate 4: independent clean-clone reproduction

Status: **Pending external developer**

The external result may initially pass or fail. Retain:

- reviewer's name or public handle, with permission;
- date;
- operating system and architecture;
- repository revisions;
- Rust, Cargo, and relevant tool versions;
- exact commands;
- complete success or failure output; and
- any documentation or diagnostic fix made in response.

An external failure is useful evidence but does not satisfy an alpha release
gate until the blocker is resolved or explicitly scoped as unsupported.

## Gate 5: external direction review

Status: **Pending**

Required sequence:

1. Share the draft first with the CKBuilder mentor/coordinator.
2. Publish the project-review issue after incorporating factual corrections.
3. Share it with Neon and in the CKBuilders Telegram channel.
4. Ask Cecilia to review the `groth16-ckb` integration boundary.
5. Follow up on Noir-Groth16 issue #1 about a possible remapping PR.

Retain links to the published request and substantive responses. General praise
is welcome but does not count as technical or direction validation.

## Gate 6: alpha GitHub release

Status: **Blocked on Gate 4**

Candidate tag: `v0.1.0-alpha.1`

The release may be created only after:

- the clean-clone reviewer path passes on at least one fresh environment;
- documentation matches that result;
- the repository tree contains no generated secrets or setup material;
- normal tests and the 12-case CKB-VM matrix pass at the tagged revision; and
- release notes state the exact support and non-production boundaries.

Publishing to crates.io remains post-program work because package ownership,
installation behavior, API stability, and supported platforms are not yet
established.

## Week 12 claim boundary

The final report may claim only results supported by completed gates. It must
not claim arbitrary Noir support, a production trusted setup, finalized
commitment/nullifier/replay rules, testnet or mainnet deployment, an audit, or a
validated credential/KYC/proof-of-reserves product.
