# Week 10 evidence log

## Status

Week ending Sunday, 2 August 2026. The implementation was completed and the
evidence was reviewed on 3 August 2026 as Week 10 catch-up. All six gates below
are supported by retained terminal output. The results apply to the fixed
development fixture and do not establish production readiness or general Noir
compatibility.

## Gate 1: Noir semantics

The retained source baseline was:

```text
noir-ckb-verifier revision: b75c7726fdc9a383dee4a3fedb8ede942548748b
nargo: 1.0.0-beta.18
noirc: 1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9
```

`nargo check`, `nargo compile --print-acir`, and `nargo execute witness` each
returned exit code `0`. The compiler classified the witnesses as:

```text
private parameters: [w7]
public parameters: [w0, w1, w2, w3, w4, w5, w6]
```

The inspected ABI preserved the required order:

```text
w0 capsule_id                 public
w1 old_state_commitment       public
w2 old_nullifier              public
w3 new_state_commitment       public
w4 action_id                  public
w5 new_nullifier              public
w6 replay_domain              public
w7 authorization_secret       private
```

The printed ACIR contained three assertions:

```text
ASSERT w2 = -w7*w7 - w0 + w1
ASSERT w4 = -w1 + w3
ASSERT w5 = w6*w7 + w2
```

These are algebraically equivalent to the three source constraints documented
in the Week 10 design. The generated artifacts were:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `target/proof_bound_capsule.json` | 2,223 | `5e9397b08d4403e6a71b4976fbb99f95bc3428af36e289b8453abc0ec4a4f870` |
| `target/witness.gz` | 67 | `3d9321df9275ea202295a7bbb3b3669a7cdd601b87c3c47955a3674a6a8d54b3` |

`file` identified the program as JSON and the witness as gzip-compressed data
with a 372-byte original size. `gzip -t` returned exit code `0`.

## Gate 2: pinned backend lowering and wire semantics

The reviewed backend baseline was:

```text
Noir-Groth16 revision: 4b7caace1f2128e454c8d0fe50cac1ec46b1e272
noir-cli: Mach-O 64-bit executable arm64, approximately 27 MiB
noir-cli SHA-256: 9b2783fcec9a6ea8983134af5b9fbdf61974fe4362f95d3a75747548524ca092
snarkjs package selected by npx: 0.7.5
```

The attempted `snarkjs --version` probe printed the 0.7.5 banner and command
help, then returned exit code `99` because this CLI does not implement that
flag. This was a version-probe syntax result, not a circuit, witness, R1CS, or
proof failure.

The backend parser returned exit code `0` and reported:

```text
opcode_count=3
witness_count=8
opcode_variants=AssertZero
```

The backend witness solver returned exit code `0`. Its eight-entry ACIR witness
map preserved the values and ordering:

```text
w0=11, w1=65, w2=5, w3=66, w4=1, w5=96, w6=13, w7=7
```

Strict interop lowering returned exit code `0` and reported 11 R1CS wires, five
constraints, and a witness length of 11. Independent snarkjs inspection
confirmed zero outputs, seven public inputs, one private input, 11 labels, five
constraints, and no custom gates. `snarkjs wtns check` reported `WITNESS IS
CORRECT` and returned exit code `0`.

The exported R1CS witness vector was:

```text
[1, 11, 65, 5, 66, 1, 96, 13, 7, 49, 91]
```

Its semantic partition is:

```text
wire 0:     constant one
wires 1-7:  public [11, 65, 5, 66, 1, 96, 13]
wire 8:     private authorization secret 7
wires 9-10: intermediate products 49 and 91
```

The R1CS JSON independently recorded `nPubInputs = 7`, `nPrvInputs = 1`, and
`nConstraints = 5`. Its constraint terms reference the expected public,
private, and intermediate wire positions. This passes the Week 10 public-wire
semantic gate for the public-first compatibility fixture; it does not establish
general ACIR witness remapping.

The retained generated artifacts were:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `parse/parsed.json` | 90 | `2edfdfee74fcda757a9c38c73845b3a99e259545189beb4fb95740f7f6100a0f` |
| `witness/witness_map.json` | 618 | `0dd8cc7d0ee43d9897556876ad2d5629ce366f82c568b447d64e976357026c93` |
| `witness/witness.bin` | 288 | `da792c481bde40a1bffdd00521eb4f1746d5ee176c543c26aafa86430098e8c1` |
| `witness/witness.wtns` | 364 | `921ce5915ae04d7ce712e75865863ba790fd056d3c08f9750a3986aaa4e32b0c` |
| `interop/circuit.r1cs` | 944 | `7aa020246d9b4f25c113e36eb5b975051086601bd79fc41a5c2b769ca2624a02` |
| `interop/witness.wtns` | 428 | `3d025058780ff5ce1dabe3deb04a3553b511ef63ba2e50f682104ac9800f3a47` |
| `interop/witness.json` | 75 | `624516f5ed88e122e7ce949be5bdd9f92df94f50c27403a56272be91a2d45340` |
| `interop/circuit.r1cs.json` | 1,363 | `f4cbe3317f240b7e3a6f335e516fd0899654bc3bb9e702838ab2db8c054da19c` |

## Gate 3A: development setup and circuit-specific key

The contributed Week 8 Powers of Tau file was reverified for the Week 10 run.
snarkjs reported both `Powers Of tau file OK!` and `Powers of Tau Ok!`, listed
the retained Week 8 contribution, and returned exit code `0`.

```text
pot12_final_contributed.ptau SHA-256:
29c1d78626c2501f8d452b3c91c4e7b19e651674740e8961d7fb969899b677da
```

Circuit-specific Groth16 setup completed with exit code `0`. The initial key,
the named Week 10 development contribution, key binding verification, and
verification-key export all returned exit code `0`. Binding verification
recomputed the same circuit hash and reported `ZKey Ok!`:

```text
Circuit hash:
1f88ce00 766746b2 32809d02 f2584c2f
059135cf 01968e33 2f7fab1e 61c8fc43
7d601e3e 4a3dcc65 5c293639 14009fc7
787ebf4e d5bed745 d9cdbe72 4737b629

Week 10 contribution hash:
b91fc47c c34cdfcd 1843adb9 9a8cafea
062b4b1e 29dc6bc6 bdad54f3 1087a62c
eb27ac96 ac5f44f9 2fa2064f 86eb33a9
e1c26979 6eb3a35b 819d3e04 1e46b8de
```

The contribution uses recorded public development entropy. These keys are not
production ceremony artifacts.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `circuit_0000.zkey` | 6,512 | `6424d74c11777c269ab9282a37c2cfc9828d4bed5ea7973dd16b8193cc0d0e93` |
| `circuit_final.zkey` | 6,964 | `24dcf28a49f308f2ff6e8f983c2f3d7c819794244c516bd1510472b462b47f56` |
| `verification_key.json` | 4,026 | `75402addb04f0d27264b3d807a7ae4ac3b7ce115161fb9ed0a22971c3e186ff0` |

The reviewed expected and single-field negative vector hashes are:

| Fixture | SHA-256 |
|---|---|
| `intended-public.json` | `b3f9428976048e2a3d1b5d6b42adb61e2fdaa07c523c3304a3537cbf74b7d3d2` |
| `wrong-capsule-id-public.json` | `948764a87743f517e72ab115113beac0cae1db97214de10dc066ba30991accbb` |
| `wrong-new-state-public.json` | `0fa76bcc458e982d4737999db88cd1d995d23853daa2e0919a6758e5ade822f1` |
| `wrong-replay-domain-public.json` | `bcf49057589b5b116b679d8384df36b76a86d2de1fdb62b4d67261e4764066ce` |

This gate establishes R1CS, setup, contribution, and key consistency. Proof
generation, public-vector semantics, and positive or negative proof verification
remain separate gates.

## Gate 3B: Groth16 proof and semantic negatives

Groth16 proof generation returned exit code `0`. The generated public vector
was:

```text
[11, 65, 5, 66, 1, 96, 13]
```

A JSON semantic comparison against `intended-public.json` returned `True` and
exit code `0`. This establishes that the prover exported the intended Capsule
tuple rather than merely producing a proof that verifies for some vector.

The verification matrix was:

| Public vector | Expected | snarkjs result | Exit code |
|---|---|---|---:|
| Generated `[11,65,5,66,1,96,13]` | Accept | `OK!` | 0 |
| Retained intended fixture | Accept | `OK!` | 0 |
| New state changed from 66 to 67 | Reject | `Invalid proof` | 1 |
| Capsule ID changed from 11 to 12 | Reject | `Invalid proof` | 1 |
| Replay domain changed from 13 to 14 | Reject | `Invalid proof` | 1 |

The unchanged proof therefore cannot verify for any of the three tested
single-field statement changes. This is proof-level negative evidence; the
later CKB transaction test must separately demonstrate that the application
script derives these values from actual Cells and rejects a changed transition.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `verification_key.json` | 4,026 | `75402addb04f0d27264b3d807a7ae4ac3b7ce115161fb9ed0a22971c3e186ff0` |
| `proof.json` | 807 | `119e7276ec5aa4a8ef54502bb86cea41fe6b91302a8ba1074271714677de8e72` |
| `public.json` | 49 | `ad6f5ea7390ce0b72d6741fd1f24299008f992f6da56dd9ffa5e184c90cd2b08` |

## Gate 4: arkworks conversion and production wire encoding

The retained Rust toolchain was:

```text
rustc 1.95.0 (59807616e 2026-04-14)
cargo 1.95.0 (f2d3ce0bd 2026-03-21)
```

Formatting and locked workspace checking returned exit code `0`. The existing
locked suite ran 11 tests: four parser-validation unit tests and seven
interoperability integration tests. All 11 passed with no failures or ignored
tests. The release adapter build returned exit code `0` and retained the Week 9
binary identity:

```text
binary: target/release/noir-ckb-adapter
bytes: 2,025,776
format: Mach-O 64-bit executable arm64
SHA-256: ed0f37ff16ad5c80323a3bf72bb7b81e0a22d7365bc65b421d85ac14b81d6576
```

Adapter execution against the Week 10 proof returned exit code `0` and
reported:

```text
arkworks_positive_verify=accepted
arkworks_negative_verify=rejected
groth16_ckb_wire_roundtrip=accepted
public_input_count=7
```

This demonstrates strict conversion of the seven-input proof into validated
arkworks objects, rejection of the changed-new-state vector, canonical
serialization, version-1 Molecule encoding, exact endpoint decode round trip,
and pinned host verification.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `vk.bin` | 488 | `64a8272872c5ce8e3b81f3663ed16167f3e15ff383422e202da892e443181c6d` |
| `proof.bin` | 128 | `75bd84f21edfe5b7bfc6087b8c0f73c8c40df2ded22176ae8c6eab9086dfbdcb` |
| `public_inputs.bin` | 228 | `af32562d082bb7cf0c4572e43c3ea549a9a66a6ef9e72f31feb05eb258b5b88b` |
| `vk.mol.bin` | 526 | `85221da147e1b16c4dd4a7bdd262d27db3cc41a277bcb1bf06139db24d624cf5` |
| `witness.mol.bin` | 386 | `4b9ba6492654de51c6fc38346f3c9b4e1e4dfb829800cd671d24436279fdff21` |
| `vk_data_hash.bin` | 32 | `024e2c93495d17b317ed2125bcd0ed73f42f87dca7dc378cf4ba0e3bfc53ab09` |
| `manifest.json` | 1,046 | `8fb149ae83d10e52bb5dc809e07d1215de0e0f7fce9d42db74d5af6bac66a6eb` |

The CKB Blake2b data hash stored in `vk_data_hash.bin` is:

```text
069bf78f701ba1bfbda0e25739eee7f5bcb069e38a654820fb7e7bc24924af9f
```

The terminal hex display wrapped the final four characters onto a second line;
the concatenated value matches the adapter's direct output. This gate remains
host-side and does not establish CKB-VM execution.

## Gate 5: production verifier execution in CKB-VM

The production verifier source remained clean at pinned revision:

```text
d64c769ffe2d2edb5eb308dc59058efda77c2f83
```

`./scripts/build-ckb-script.sh` returned exit code `0` after an incremental
release build. The resulting binary retained its earlier modification time,
size, format, and hash, so this is recorded as an incremental build validation,
not a clean rebuild:

```text
binary: script/target/riscv64imac-unknown-none-elf/release/ckb-script
bytes: 98,464
format: ELF 64-bit LSB, UCB RISC-V, RVC, soft-float ABI, statically linked, stripped
SHA-256: 9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8
```

The promoted public fixture was independently compared with the generated
Week 10 JSON. The verification key, proof, and public vector all matched
semantically and the comparison returned exit code `0`.

The expanded locked host suite returned exit code `0`: the 11 artifact-adapter
tests passed, while the two environment-dependent CKB-VM tests were correctly
listed as ignored in the normal suite. Formatting and locked all-target checking
also returned exit code `0`.

The explicit CKB-VM invocation supplied the pinned RISC-V verifier through
`GROTH16_CKB_SCRIPT_BIN`. Both ignored tests passed:

| CKB-VM case | Result |
|---|---|
| Noir-derived proof with intended seven-input vector | Accepted |
| Same proof with new-state public input changed | Rejected with verifier exit code 5 |

The positive transaction consumed exactly:

```text
101,576,496 cycles
```

This is the first retained CKB-VM execution of a Noir-derived proof in this
repository. It establishes production verifier execution and cryptographic
rejection of a changed public vector. It does not yet establish that those
inputs are derived from actual Capsule Cell data; that is the application Type
Script gate.

## Capsule Type Script build diagnostic

The first Capsule Type Script lockfile generation ran under the intended pinned
contract toolchain:

```text
rustc 1.94.1 (e408947bf 2026-03-25)
cargo 1.94.1 (29ea6fb6a 2026-03-24)
riscv64imac-unknown-none-elf installed
```

Lockfile generation returned exit code `0`, but Cargo selected
`ckb-gen-types 1.1.1` and `ckb-hash 1.1.1`. Both releases declare Rust 1.95 as
their minimum supported version. Contract checking, clippy, and the release
build therefore each stopped before compiling project code with exit code
`101`. No Capsule binary existed, and the subsequent `ls`, `wc`, `file`, and
`shasum` probes reported the missing path.

This is recorded as a dependency-resolution failure, not a contract-code or
CKB-VM failure. The pinned `groth16-ckb` script lockfile at revision
`d64c769ffe2d2edb5eb308dc59058efda77c2f83` uses `ckb-gen-types 1.1.0` and
`ckb-hash 1.1.0` with Rust 1.94.1. The Capsule manifest now constrains those
same versions explicitly before the corrected build rerun.

### Corrected dependency and build result

The corrected `cargo update` for `ckb-gen-types 1.1.1 -> 1.1.0` also
downgraded `ckb-hash 1.1.1 -> 1.1.0` because the manifest now constrains both
packages. It returned exit code `0`. The following explicit `ckb-hash@1.1.1`
update returned exit code `101` because that package ID was no longer present;
Cargo suggested the already-selected `ckb-hash@1.1.0`. This second result was a
redundant command targeting a package already removed from the graph, not a
dependency or build failure.

The inspected lockfile and dependency tree confirmed:

```text
ckb-gen-types 1.1.0
ckb-hash 1.1.0
ckb-std 1.1.0
wire-decode d64c769ffe2d2edb5eb308dc59058efda77c2f83
```

Formatting, release checking, and release clippy with warnings denied all
returned exit code `0`. The reproducible build script then compiled the Capsule
Type Script under the pinned contract toolchain and returned exit code `0`:

```text
binary: contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding
bytes: 28,032
format: ELF 64-bit LSB, UCB RISC-V, RVC, soft-float ABI, statically linked, stripped
SHA-256: 6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962
```

This establishes a successful application-script build. Correct-transition
acceptance and wrong-transition rejection remain CKB-VM execution gates.

## Gate 6: proof-bound Capsule execution in CKB-VM

The retained contract lockfile is 5,835 bytes with SHA-256:

```text
22749bccbd156bd7a408e0c6dd8608a7c92b99b76cca181e8867b82ff2ab5aff
```

After adding the CKB integration-test package, the retained root workspace
lockfile is 67,131 bytes with SHA-256:

```text
0615a881dde5a10fd62c13beef8335c532af1f152aa7051cd0467e4a9b0d1d82
```

Before the transaction tests, root-workspace formatting, locked all-target
checking, and locked clippy with warnings denied each returned exit code `0`.
The normal workspace suite also returned exit code `0`: 11 host tests passed,
and the six binary-dependent CKB-VM tests were listed as ignored as intended.

The explicit proof-bound Capsule invocation supplied both binaries:

```text
Groth16 verifier SHA-256:
9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8

Capsule binding script SHA-256:
6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962
```

All four initial transaction tests passed:

| CKB-VM transaction | Result |
|---|---|
| Valid proof and correct Capsule transition | Accepted |
| Same valid proof and changed new state | Rejected with binding exit code 30 |
| Same valid proof and changed Capsule ID | Rejected with binding exit code 30 |
| Same valid proof and changed replay domain | Rejected with binding exit code 30 |

The combined verifier-lock plus Capsule-type transaction consumed exactly:

```text
101,625,705 cycles
```

The earlier verifier-only transaction consumed 101,576,496 cycles. The
observed combined-minus-verifier delta is 49,209 cycles. Because the two tests
use different lock/type arrangements, this delta is recorded as an observed
transaction comparison rather than an isolated Type Script benchmark.

This gate establishes the central project invariant for the tested fixture:

```text
proof verifies mathematically
does not imply
proof authorizes a changed CKB Cell transition
```

The Type Script derives the ordered application inputs from actual script
arguments and input/output Cell data. A valid proof ceases to authorize the
transaction when any tested derived field changes.

## Expanded matrix compile diagnostic

The first expanded-matrix invocation passed formatting, then root checking,
clippy, the normal suite, and the explicit matrix command each stopped during
test-harness compilation with exit code `101`. Rust could not infer the packed
CKB type for an untyped `None.pack()` used when constructing the duplicate-lock
negative case. No expanded CKB-VM transaction executed in this attempt.

The harness now states the absent value as
`Option<ckb_testtool::ckb_types::packed::Script>::None` before packing. This is
a host test-construction correction; it does not change the already-built
Capsule Type Script or the four previously verified CKB-VM results.

### Corrected expanded-matrix result

After the type annotation was added, the corrected validation sequence
returned:

```text
cargo fmt --all -- --check:                         exit 0
cargo check --locked --workspace --all-targets:     exit 0
cargo clippy --locked --workspace --all-targets:    exit 0
cargo test --locked --workspace:                    exit 0
explicit 12-case Capsule CKB-VM matrix:              exit 0
```

The normal locked suite passed all 11 host tests. The 12 Capsule transaction
tests and two verifier-only CKB-VM tests were listed as ignored because their
RISC-V binaries are supplied explicitly through environment variables.

The explicit Capsule invocation supplied both pinned binaries and ran all 12
transaction cases. Every case passed:

| CKB-VM case | Observed result |
|---|---|
| Valid proof and correct Capsule transition | Accepted; `101,625,705` cycles |
| Valid proof and changed new state | Rejected by binding script, code `30` |
| Valid proof and changed Capsule ID | Rejected by binding script, code `30` |
| Valid proof and changed replay domain | Rejected by binding script, code `30` |
| Proof invalid for a transaction that matches its supplied public vector | Rejected by Groth16 verifier, code `5` |
| VK Cell dependency omitted | Rejected by Groth16 verifier, code `12` |
| Truncated Molecule witness | Rejected by Groth16 verifier, code `17` |
| Malformed Capsule script args | Rejected by binding script, code `21` |
| Malformed input Cell data | Rejected by binding script, code `25` |
| Output verifier lock changed | Rejected by binding script, code `32` |
| Duplicate input using the verifier lock | Rejected as witness ambiguity, code `33` |
| Duplicate Capsule group input | Rejected as group ambiguity, code `23` |

```text
test result: ok. 12 passed; 0 failed; 0 ignored
corrected_expanded_proof_bound_matrix_exit_code=0
```

This corrected rerun is the retained expanded-matrix result. The earlier
compile error remains documented because it explains why that first invocation
provides no CKB-VM evidence.

## Intended scope

- transition-aware Noir fixture
- pinned ACIR-to-Groth16 execution
- strict adapter and Molecule encoding
- production verifier execution in CKB-VM
- transaction-derived Capsule public inputs
- correct-transition acceptance
- valid-proof/wrong-transition rejection

## Evidence policy

Record the exact command, working directory, source revisions, tool versions,
exit code, artifact size, and artifact hash for each completed gate. Retain
failed diagnostic commands as failures and distinguish them from corrected
reruns. Development setup material and private witnesses remain ignored by Git.
