# Week 11 developer-preview evidence

## Status

The `noir-ckb build`, `noir-ckb prove`, and `noir-ckb test` developer-preview
path passed an evidence-retained run on the primary macOS arm64 development
checkout on 11 August 2026. Clean-clone and hosted CI results remain separate
release gates and are not claimed by this record.


## Evidence gate

Week 11 is complete only after the following outputs have been retained and
reviewed:

- exact source revisions and clean external checkout status;
- `cargo fmt`, `cargo check`, Clippy, and workspace test results;
- `noir-ckb build` compatibility result and build-manifest path;
- `noir-ckb prove` public vector, negative verification results, VK data hash,
  and proof-manifest path;
- `noir-ckb test` host result, 12-case CKB-VM result, accepted cycle count, and
  test-report path; and
- final repository status showing that generated proof/setup material remains
  ignored.

No result should be filled in from Week 10 retained output. Week 11 must record
the actual values produced by the packaged commands.

## Gate 1: host checks and CLI packaging

Status: **Passed and reviewed 11 August 2026**

The retained host checks returned:

| Check | Result |
|---|---:|
| `git diff --check` | exit code `0` |
| `cargo fmt --all -- --check` | exit code `0` |
| workspace check, all targets | exit code `0` |
| workspace Clippy with warnings denied | exit code `0` |
| normal workspace test suite | exit code `0` |

The normal suite passed 14 host tests: four adapter unit tests, seven adapter
interoperability tests, and three `noir-ckb` semantic-gate tests. It listed 14
binary-dependent CKB-VM tests as ignored, as intended for the normal suite.
The new semantic-gate tests included both the accepted public-first layout and
the required rejection of the private-first regression layout.

The pinned Rust 1.95.0 release build produced:

| Property | Retained value |
|---|---|
| binary | `target/release/noir-ckb` |
| version | `noir-ckb 0.1.0-alpha.1` |
| build exit code | `0` |
| version exit code | `0` |
| help exit code | `0` |
| exact bytes | `2,691,568` |
| file type | Mach-O 64-bit executable arm64 |
| SHA-256 | `239c2b376d3d16cdb5055be79f76c40fa71b60acc9822f892258139fb65cfd53` |

The final status contained only the intended Week 11 working-tree changes and
the separately isolated, untracked production-readiness roadmap. Generated
Rust output remained ignored.

The release binary was rebuilt after normalizing the snarkjs version field in
the JSON manifest. The focused formatting, check, Clippy, and three CLI tests
all returned exit code `0` before the corrected binary hash above was retained.

## Gate 2: packaged build and compatibility checks

Status: **Passed and reviewed 11 August 2026**

`noir-ckb build` returned exit code `0` and reported
`build_status=compatible`. Its source and tool preflight established:

| Input | Retained value |
|---|---|
| noir-ckb-verifier revision | `4f85a85c6b4dfd80e68b6bb7295ef4338474d561` |
| root working tree | dirty with the uncommitted Week 11 implementation |
| Noir-Groth16 revision | `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`, tracked files clean |
| groth16-ckb revision | `d64c769ffe2d2edb5eb308dc59058efda77c2f83`, tracked files clean |
| Nargo/noirc | `1.0.0-beta.18` / `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` |
| snarkjs | `0.7.5` |
| host Rust | `1.95.0` |
| contract Rust | `1.94.1` with `riscv64imac-unknown-none-elf` installed |

The command built the pinned backend, generic verifier, and Capsule binding
script; compiled the Noir package; lowered it to R1CS/WTNS; and independently
checked the witness with snarkjs. The compatibility summary was:

| Property | Retained value |
|---|---:|
| public inputs | 7 |
| private inputs | 1 |
| constraints | 5 |
| wires | 11 |
| outputs | 0 |
| witness check | correct |

The manifest retained the ordered public tuple
`[11, 65, 5, 66, 1, 96, 13]`, the corresponding seven binding sources, and
the following artifact hashes:

| Artifact | SHA-256 |
|---|---|
| Capsule binding binary | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |
| Noir circuit artifact | `5e9397b08d4403e6a71b4976fbb99f95bc3428af36e289b8453abc0ec4a4f870` |
| circuit input JSON | `f49ccc1dd144111fe78fb9a5ba0e178b0318978976d9af7dac91162d48c3c9a1` |
| generic verifier binary | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |
| parsed ACIR summary | `2edfdfee74fcda757a9c38c73845b3a99e259545189beb4fb95740f7f6100a0f` |
| R1CS | `7aa020246d9b4f25c113e36eb5b975051086601bd79fc41a5c2b769ca2624a02` |
| exported witness JSON | `624516f5ed88e122e7ce949be5bdd9f92df94f50c27403a56272be91a2d45340` |
| WTNS | `3d025058780ff5ce1dabe3deb04a3553b511ef63ba2e50f682104ac9800f3a47` |

The corrected build used run ID `1786440542305`. Its 2,668-byte
`build-manifest.json` had SHA-256
`28276404d557b51f17c18dc7a757bbf6684017f35ac1854d868078fedda52ec8`.
All generated build artifacts remained below ignored `target/` paths.

## Gate 3: packaged proof generation and wire artifacts

Status: **Passed and reviewed 11 August 2026**

`noir-ckb prove` returned exit code `0` and reported
`prove_status=verified`. The command used explicitly public development
entropy; its Powers of Tau contribution, prepared phase-2 file, and
circuit-specific ZKey all passed snarkjs verification. This is development
setup evidence, not a production ceremony.

The generated proof verified with the exact configured public vector:

```text
[11, 65, 5, 66, 1, 96, 13]
```

The unchanged proof was then required to reject each altered vector:

| Negative case | snarkjs result |
|---|---|
| changed new state | `Invalid proof` |
| changed Capsule ID | `Invalid proof` |
| changed replay domain | `Invalid proof` |

The command reached its success manifest only after the corresponding
arkworks positive/negative checks and the pinned CKB endpoint round trip also
completed. The emitted wire manifest recorded version 1, BN254, seven public
inputs, and arkworks 0.5 canonical compressed serialization inside the
`groth16-ckb` version-1 Molecule schema.

The proof run used ID `1786440704127`. Its retained proof inputs and setup
hashes were:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| proof manifest | 2,707 | `11f9694aff35dcf74808938ed40d0abf292f4e7051fe56bceec891be1569e5bd` |
| snarkjs proof JSON | 806 | `cb2feb091b53a88b4c0d790734c3dcb1fac51d988f74493637d75aa912a5d3ac` |
| public JSON | 49 | `ad6f5ea7390ce0b72d6741fd1f24299008f992f6da56dd9ffa5e184c90cd2b08` |
| verification key JSON | 4,024 | `91b19278d6141b1518d1a87e1d9611926f1cdef8f64d3f862ce578c81664545a` |
| prepared phase-2 Powers of Tau | — | `3720296946259fd4e67c1002c22efb5dbf917fbad1e6a9f7b4c14d5dd0fbb57f` |
| final circuit ZKey | — | `f3dc7e4cb4cba06ce09a12d57351e177931260d2d69c176ae98c5927d2a7f618` |

The three copied negative-vector hashes matched their checked-in Week 10
sources. The adapter emitted:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| canonical VK | 488 | `c7ad2d7ad6bbc835fae6ee0333c5176629375500ec1b5a1beba91513f57cc8a7` |
| canonical proof | 128 | `1d8d403f3c37d1973277b63f8c1082dfb4d2d994863ba2a19f7e9e20a8274624` |
| seven-input public buffer | 228 | `af32562d082bb7cf0c4572e43c3ea549a9a66a6ef9e72f31feb05eb258b5b88b` |
| Molecule VK payload | 526 | `dd90be499e1f7da3611fb15007a8d53cc4dafb783f9002bd2ad640f3f7609c2c` |
| Molecule witness payload | 386 | `b923f80fb19464731cef89603c7d0951ad97a3374e76f5c79873f10faad57684` |
| VK data-hash file | 32 | `e9ab106cdb03dd56006c000c4479bd3a7b22912b327a744f9d30e7b1ce3937f7` |

The CKB data hash of the Molecule VK payload was
`9ea09446b2406dcbcbbbe3d9562f216d7181c1e67725da4dc5ccd9de6c4259e9`.
Generated setup, proof, witness, and adapter files remained below ignored
`target/` paths.

## Gate 4: packaged CKB-VM test matrix

Status: **Passed and reviewed 11 August 2026**

`noir-ckb test` returned exit code `0`. It first reran the normal workspace
suite, which passed all 14 host tests and listed the 14 binary-dependent tests
as ignored. It then selected the freshly generated proof fixture from Gate 3
and ran the explicit Capsule transaction matrix in CKB-VM.

The matrix returned 12 passed, zero failed, and zero ignored:

| Case | Retained result |
|---|---|
| valid proof and intended transition | accept |
| valid proof and wrong new state | reject, binding code `30` |
| valid proof and wrong Capsule ID | reject, binding code `30` |
| valid proof and wrong replay domain | reject, binding code `30` |
| invalid proof with matching altered transition | reject, verifier code `5` |
| missing VK Cell | reject, verifier code `12` |
| truncated witness | reject, verifier code `17` |
| malformed Capsule args | reject, binding code `21` |
| malformed Cell data | reject, binding code `25` |
| changed verifier lock | reject, binding code `32` |
| duplicate verifier-lock input | reject, binding code `33` |
| duplicate Capsule input | reject, binding code `23` |

The accepted transaction consumed `101,665,331` CKB-VM cycles. This is the
actual result for the newly generated Week 11 proof and retained binaries, not
a performance guarantee for other builds or dependency revisions.

The test run used ID `1786440846691`. Its 936-byte `test-report.json` had
SHA-256
`5cf48a51db3b81bc7c9942dfc61117f601b335ccff6f927bee94b2e943b7518d`.
The report linked proof run `1786440704127` and retained these hashes:

| Input | SHA-256 |
|---|---|
| Capsule binding binary | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |
| generic verifier binary | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |
| generated proof JSON | `cb2feb091b53a88b4c0d790734c3dcb1fac51d988f74493637d75aa912a5d3ac` |
| generated public JSON | `ad6f5ea7390ce0b72d6741fd1f24299008f992f6da56dd9ffa5e184c90cd2b08` |
| generated verification key JSON | `91b19278d6141b1518d1a87e1d9611926f1cdef8f64d3f862ce578c81664545a` |

`git diff --check` returned exit code `0` after the test. The final repository
status did not expose generated setup, proof, witness, adapter, or test-report
files because all remained below ignored `target/` paths. The separately
drafted production-readiness roadmap remained untracked and outside Week 11.

## Hosted CI attempt 1

Status: **Failed at a missing runner dependency; diagnosed 11 August 2026**

GitHub Actions run
[`31521030261`](https://github.com/wamimi/noir-ckb-verifier/actions/runs/31521030261)
tested revision `650d62f154e221c834f744626c2f81f281d9a4f6`. Repository checkout,
Rust toolchain installation, formatting, Clippy, all host tests, and checkout
of the pinned generic verifier passed. The combined CKB-script build step then
returned exit code `101` while compiling `ckb-std` for the generic verifier:

```text
error occurred in cc-rs: failed to find tool "riscv64-unknown-elf-gcc"
```

The retained failure therefore does not establish a proof, adapter, contract,
or CKB-VM regression. It establishes that the hosted Ubuntu runner lacked the
bare-metal RISC-V C compiler required by the pinned CKB dependency. The
workflow now installs `gcc-riscv64-unknown-elf`, prints the compiler version,
and builds the generic verifier and Capsule binding script in separate steps.
The hosted CI gate remains unverified until a corrected run completes
successfully.

## Commands to retain

Run from the repository root:

```bash
cargo fmt --all -- --check
cargo check --locked --workspace --all-targets
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace

cargo +1.95.0 build --locked --release \
  -p noir-ckb-cli \
  --bin noir-ckb

./target/release/noir-ckb build
./target/release/noir-ckb prove
./target/release/noir-ckb test
```

The command output and generated JSON manifests must be reviewed before this
record is changed from pending to verified.
