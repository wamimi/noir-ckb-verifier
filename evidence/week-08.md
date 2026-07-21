# Week 8 evidence record

**Policy:** A result remains pending until complete command output is retained and reviewed. Source inspection is identified separately from execution evidence.

## Scope

- pinned Noir-Groth16 source checkout
- locked backend build
- direct consumption of the Week 7 Noir beta.18 artifact
- strict ACIR-to-R1CS lowering and pedantic witness solving
- R1CS and WTNS inspection
- pinned snarkjs witness check
- development-only BN254 Groth16 setup, proof, and source verification
- public-input semantic check and negative verification
- artifact sizes and SHA-256 digests

Week 8 stops before arkworks conversion, Molecule encoding, CKB-VM verification of the Noir-derived proof, or Capsule transition execution.

## Expected compatibility set

| Component | Expected pin | Evidence status |
|---|---|---|
| Source Noir artifact | beta.18 / `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` | Re-hashed; matches Week 7 |
| Noir-Groth16 | `4b7caace1f2128e454c8d0fe50cac1ec46b1e272` | Checked out detached; clean worktree |
| Backend ACIR/ACVM runtime | Noir beta.19 / `74d6be658e1ad252f87943292ba09bdd4da80bd4` | Manifest and lockfile verified |
| Backend legacy parser | Noir beta.18 / `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` | Manifest and lockfile verified |
| snarkjs | `0.7.5` | Version and execution retained |
| Curve / scalar field | BN254 (`bn-128` / `bn128` in snarkjs output) | R1CS and WTNS inspection verified |

## Gate 1: backend source and host tools

Status: **Passed and reviewed 20 July 2026**

Record:

- exact commit and worktree status
- Cargo and Rust versions
- Nargo/noirc version
- Node.js and npm versions
- relevant dependency declarations and locked Noir source revisions

Retained results:

- repository cloned to `/Users/xiaomao/Noir-Groth16`
- detached HEAD: `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`
- commit date: `2026-06-13T08:57:44+01:00`
- commit subject: `memory materialization`
- worktree status: clean (`git status --short` produced no output)
- Rust: `rustc 1.95.0 (59807616e 2026-04-14)`
- Cargo: `cargo 1.95.0 (f2d3ce0bd 2026-03-21)`
- Nargo: `1.0.0-beta.18`
- noirc: `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`, source reported clean
- Node.js: `v24.3.0`
- npm: `11.4.2`
- runtime `acir`, `acvm`, and `bn254_blackbox_solver`: Noir tag `v1.0.0-beta.19`, locked source `74d6be658e1ad252f87943292ba09bdd4da80bd4`
- legacy `acir` parser: Noir tag `v1.0.0-beta.18`, locked source `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`
- `rg` was not installed; the equivalent `grep -nE` inspection succeeded

Input integrity:

| Input | SHA-256 |
|---|---|
| `circuits/square-root/target/square_root.json` | `6fc139050100c3083e48f31d4a3fb051d8d96e31bfa98865d103ce12d37d57cb` |
| `circuits/square-root/inputs.json` | `2e7e17d3a2a9d3a7545fb06b7c23aa150fc529c5a89a41a50351ad77413b9774` |

The artifact digest exactly matches the Week 7 record. The JSON input fixture is newly recorded for the backend experiment.

## Gate 2: locked CLI build

Status: **Passed; retained output reviewed 21 July 2026**

Build `noir-cli` with `cargo build --locked -p noir-cli`. Do not treat an unreviewed successful exit as proof that the Week 7 artifact is supported.

Retained results:

- command: `cargo build --locked -p noir-cli`
- Cargo result: `Finished dev profile [unoptimized + debuginfo] target(s) in 0.70s`
- exit code: `0`
- backend worktree: clean (`git status --short` produced no output)
- binary: `target/debug/noir-cli`
- displayed size: `27M`
- file type: `Mach-O 64-bit executable arm64`
- SHA-256: `9b2783fcec9a6ea8983134af5b9fbdf61974fe4362f95d3a75747548524ca092`

This is recorded as an incremental build validation, not a clean-from-scratch rebuild. The short duration and the binary timestamp (`20 July, 16:04`) show that Cargo could reuse existing build outputs. The binary hash identifies the exact local executable used by the following gates, but a debug binary hash is not expected to be portable across machines or source paths.

## Gate 3: beta.18 artifact parse

Status: **Passed 21 July 2026**

Input artifact expected before execution:

```text
path: circuits/square-root/target/square_root.json
SHA-256 from Week 7: 6fc139050100c3083e48f31d4a3fb051d8d96e31bfa98865d103ce12d37d57cb
```

Run the backend's parse command directly against this existing artifact. Do not invoke the backend's one-shot script yet because it recompiles its own circuit and would not isolate beta.18 artifact compatibility.

The pinned `noir-cli` directly consumed the unchanged Week 7 artifact and returned:

```text
opcode_count=1 witness_count=2 opcode_variants=AssertZero
artifact_parse_exit_code=0
```

Generated parse summary:

```json
{
  "opcode_count": 1,
  "witness_count": 2,
  "opcode_variants": [
    "AssertZero"
  ]
}
```

| Artifact | Size | Type | SHA-256 |
|---|---:|---|---|
| `target/week-08/parse-beta18/parsed.json` | 90 bytes | JSON data | `1ef2e569e359417568965dfb7c81f2ceb87d89dda88beb521353ca449c8ae845` |

The final `git status --short` in the backend checkout produced no output. This gate proves artifact parsing compatibility at the pinned revisions; it does not yet prove witness solving or ACIR-to-R1CS semantic compatibility.

## Gate 4: pedantic witness solving and strict interop

- Witness-solving status: **Passed 21 July 2026**
- Strict interop status: **Passed 21 July 2026**

Use the committed ABI-shaped development input:

```json
{
  "x": "7",
  "y": "49"
}
```

Do not pass `--allow-unsupported` or `--no-pedantic` during the baseline.

The default pedantic witness command returned:

```text
witness_count=3 witness_map_entries=2
witness_solve_exit_code=0
```

The count of three includes the leading constant-one slot in the emitted witness vector. The two Noir witness assignments were:

| Noir witness | Hex value | Decimal interpretation | ABI role from Week 7 ACIR |
|---:|---|---:|---|
| `0` | `0x07` | 7 | private `x` |
| `1` | `0x31` | 49 | public `y` |

Generated artifacts:

| Artifact | Size | File classification | SHA-256 |
|---|---:|---|---|
| `target/week-08/witness-beta18/witness_map.json` | 156 bytes | JSON data | `861dcc7a6cdf677a2849aabb3460b3443953fc25099de36be87db9f1ff5c7091` |
| `target/week-08/witness-beta18/witness.bin` | 96 bytes | data | `85ce06ebaf308cea591698cb285f55309681a180f18b518119ed5748278c8af6` |
| `target/week-08/witness-beta18/witness.wtns` | 172 bytes | data | `137529d627364b78b4d8c964ca1fadb2f565b2c2e339d9144aaaccf6b3f51bd6` |

The final backend `git status --short` produced no output. This establishes beta.18 ABI assignment and ACVM solving under the backend's default pedantic mode. It does not establish R1CS satisfaction or correct Groth16 public-wire classification.

The strict `interop` command was run without `--allow-unsupported` and without `--no-pedantic`. It returned:

```text
n_wires=4 n_constraints=2 witness_len=4
strict_interop_exit_code=0
```

The output directory contained only the expected binary artifacts; no `unsupported_opcodes.json` report was emitted.

| Artifact | Size | File classification | SHA-256 |
|---|---:|---|---|
| `target/week-08/interop-beta18/circuit.r1cs` | 384 bytes | data | `79b3c2b6312182538763f0c3a0e369830879a32263a454c8133614c81a0afa47` |
| `target/week-08/interop-beta18/witness.wtns` | 204 bytes | data | `6be37d42e016a48d12a01ad0ff7f30699c129cfb2d90b22ef1b0861ffac2e884` |

The final backend `git status --short` again produced no output. Strict lowering and derived-witness materialization therefore completed at this gate. Binary metadata, witness consistency, and public-wire semantics remain separate checks.

## Gate 5: R1CS/WTNS inspection and witness check

- Binary consistency status: **Passed 21 July 2026**
- Noir public-input semantic status: **Failed at the R1CS boundary**

Record at minimum:

- field/curve identifier reported by the tools
- wire, constraint, private-input, public-input, and public-output counts
- witness count and consistency result
- file sizes and SHA-256 digests

Pinned tool:

```text
snarkjs@0.7.5
```

R1CS inspection returned exit code `0` and reported:

| Property | Value |
|---|---:|
| Curve | `bn-128` |
| Wires | 4 |
| Constraints | 2 |
| Private inputs | 1 |
| Public inputs | 1 |
| Labels | 4 |
| Outputs | 0 |

The independent WTNS check returned exit code `0` and reported `WITNESS IS CORRECT` and `WITNESS CHECKING FINISHED SUCCESSFULLY`. This proves that the emitted four-element witness satisfies the emitted two-constraint R1CS.

WTNS JSON export also returned exit code `0`:

```json
[
  "1",
  "7",
  "49",
  "49"
]
```

| Artifact | Size | SHA-256 |
|---|---:|---|
| `target/week-08/interop-beta18/witness.json` | 28 bytes | `cc2c951acfbff250aa5e249d9a41c2c69605b916ef52be3c78842a59419e9dd6` |

### Semantic incompatibility found

The R1CS header declares zero public outputs followed by one public input. In the iden3 R1CS wire layout, that makes wire 1 the public input. The exported wire vector assigns wire 1 the value `7`; the value `49` appears at wires 2 and 3.

This conflicts with the Week 7 Noir artifact:

```text
private parameters: [w0]  -> x = 7
public parameters:  [w1]  -> y = 49
```

Therefore, the generated R1CS is internally satisfiable but does not preserve the Noir public/private ABI semantics for this parameter ordering. Binary consistency is not semantic compatibility. The artifact set cannot be accepted as a correct Noir-to-Groth16 conversion. Later proof generation confirmed the diagnosis: Groth16 `public.json` exposed `7`, not the intended `49`.

### Exact constraint inspection

`snarkjs r1cs print` returned exit code `1` because it attempted to open a companion `circuit.sym` file, which the selected backend does not emit. The failure was:

```text
ENOENT: no such file or directory, open '.../circuit.sym'
```

This is retained as a tooling/inspection limitation, not an R1CS validation failure. The independent `r1cs export json` command returned exit code `0` and produced a complete 569-byte JSON representation:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `target/week-08/interop-beta18/circuit.r1cs.json` | 569 bytes | `4d871845af54f0bb44ba7ffd61504061df1bd2545de6f834335a179693accb51` |

The JSON confirms:

- BN254 scalar-field prime: `21888242871839275222246405745257275088548364400416034343698204186575808495617`
- `nVars = 4`
- `nOutputs = 0`
- `nPubInputs = 1`
- `nPrvInputs = 1`
- `nConstraints = 2`
- identity wire map: `[0,1,2,3]`

The constraints reduce to:

```text
wire1 * wire1 = wire3
1 * (-wire2 + wire3) = 0
```

Together with `[wire0, wire1, wire2, wire3] = [1,7,49,49]`, these constraints correctly encode `7² = 49`. The incompatibility is specifically the interface classification: with zero outputs and one public input, wire 1 is public, although Noir declared the value at its original witness 0 (`x = 7`) private.

## Gate 6: development-only Groth16

- Initial Powers of Tau creation: **Passed 21 July 2026**
- Initial Phase 2 preparation: **Passed 21 July 2026**
- Initial transcript verification: **Failed as expected for an uncontributed transcript**
- Contributed transcript verification: **Passed 21 July 2026**
- Circuit-specific Groth16 setup: **Passed 21 July 2026**
- Circuit-specific contribution: **Passed 21 July 2026**
- ZKey/R1CS/PTAU binding verification: **Passed on corrected rerun 21 July 2026**
- Verification-key export: **Passed 21 July 2026**
- Groth16 diagnostic proof generation: **Passed 21 July 2026**
- Noir public-input semantic gate: **Failed conclusively at proof export**

Record the exact Powers of Tau power, snarkjs version, setup/contribution commands, proof-generation result, and source verification result. The transcript and proving keys are disposable development artifacts, not a trusted production setup.

The experiment used the backend workflow's default power `12` on BN254. `powersoftau new bn128 12` returned exit code `0` and printed this initial hash:

```text
9e63a5f6 2b96538d aaed2372 481920d1
a40b9195 9ea38ef9 f5f6a303 3b886516
0710d067 c09d0961 5f928ea5 17bcdf49
ad75abd2 c8340b40 0e3b18e9 68b4ffef
```

`powersoftau prepare phase2` also returned exit code `0`. The subsequent verification correctly returned exit code `1`:

```text
[ERROR] snarkJS: This file has no contribution! It cannot be used in production
```

This failure is retained rather than treated as a successful setup. An explicit local development contribution was subsequently added, prepared, and verified under a new filename before Groth16 setup continued.

| Artifact | Exact size | SHA-256 | Status |
|---|---:|---|---|
| `pot12_0000.ptau` | 1,573,072 bytes | `18dd67751dd0659bcd6f58d961ef478d855f1695325ad9db9cd68e30e411e24a` | Initial uncontributed transcript |
| `pot12_final.ptau` | 4,718,528 bytes | `292590c1c700cef65f58a6b87f5e799e05429000f13ba7d7da848bc67fd752ef` | Phase 2 prepared but verification rejected due to no contribution |

Even after a local contribution verifies structurally, the resulting transcript remains unsuitable for production: it is a single-participant development setup with disclosed commands and no independent ceremony guarantees.

The remediation added the named contribution `Nelly Week 8 development-only contribution` using explicitly public development entropy. Contribution and Phase 2 preparation both returned exit code `0`. Verification returned exit code `0` and reported `Powers Of tau file OK!` and `Powers of Tau Ok!`.

Contribution response hash:

```text
87abdb2e f7036e7f 0dec8771 ed11a2a9
2dbfa23c 1e6f1aff 25cd25b5 4eb60629
383c3074 aee14a70 31b5a9f0 e6083744
5662bf85 5c4bd9d9 70e7b049 0eab643f
```

Next challenge hash:

```text
9623e604 1b87236c a083a1f6 b9d77d25
938d4316 864b397f 55d1173d 9bf557a0
c0adeb11 c4337d60 5c30adba 0d7f9ef5
40cd89f3 d40ddcc0 da51c233 df5afd1a
```

| Artifact | Exact size | SHA-256 | Status |
|---|---:|---|---|
| `pot12_0001.ptau` | 1,574,620 bytes | `9640d90f0c2bf63c387bc6fa8a489bd9b842de4b282c96c07800330af11c97fd` | One named local development contribution |
| `pot12_final_contributed.ptau` | 4,720,076 bytes | `29c1d78626c2501f8d452b3c91c4e7b19e651674740e8961d7fb969899b677da` | Phase 2 prepared and structurally verified |

The final backend `git status --short` produced no output. Only `pot12_final_contributed.ptau` advances to the circuit-specific diagnostic setup; the rejected uncontributed `pot12_final.ptau` is not used.

The initial Groth16 setup returned exit code `0` and reported circuit hash:

```text
7345b061 9ea6b47b deae8103 7e3e40dd
f693d961 320b403c 2d2ed77b 3cfd2a27
ea10a27f 66087a8e 33d89f8e dd360156
0d8baeef 5ab82653 dcbb2191 1847b09a
```

The named `Nelly Week 8 circuit-specific development contribution` returned exit code `0` and contribution hash:

```text
5eaa8f0c 9459fa48 ff62e8c2 6717f20e
18738bad d9731ac4 eefdf027 0b084d0e
3e58571c a30edead db719840 b6e25074
bd2b3c60 e3eaf7e4 9f45c723 b1f774c4
```

The first binding-verification invocation included an extra literal `r1cs`. snarkjs printed `Invalid number of parameters`, displayed its usage, and returned exit code `99`. This was a command-line syntax failure, not cryptographic rejection of the key. The corrected invocation used the pinned CLI's `zkey verify` alias without the extra literal and passed as recorded below.

Verification-key export independently returned exit code `0`.

| Artifact | Exact size | SHA-256 |
|---|---:|---|
| `circuit_0000.zkey` | 2,712 bytes | `0355232d1e2a547f555835ab9a4aa9b51247cf67707b03805295e6e4cdacd78d` |
| `circuit_final.zkey` | 3,160 bytes | `e95de61ebae26e7b2b50c83e5b76151138ae261953109b06f783d4d1440d597c` |
| `verification_key.json` | 2,928 bytes | `15fcf947c110698b050b6e45ea6a83509cc080c4a8ecd1489a073497acebefb4` |

The two ZKey files were classified as binary data and the verification key as JSON data. The final backend `git status --short` produced no output.

The corrected command used the pinned CLI's `zkey verify` alias without the extra literal `r1cs`. It returned exit code `0`, recomputed the same circuit hash from both sides, listed the named circuit-specific contribution with the expected contribution hash, and reported:

```text
ZKey Ok!
```

This establishes that `circuit_final.zkey` matches the exact emitted R1CS and the contributed Powers of Tau transcript. It does not repair or weaken the already-observed public-wire semantic mismatch.

The pinned `groth16 prove` command returned exit code `0` and emitted a JSON proof with `protocol = groth16` and `curve = bn128`. Proof generation is randomized; this exact proof is retained by its digest and must not be regenerated when reproducing the remaining verification checks.

The generated public vector was:

```json
[
  "7"
]
```

This conclusively confirms the R1CS-layer diagnosis: the source backend exports private Noir input `x = 7` as the Groth16 public input instead of public Noir input `y = 49`.

| Artifact | Size | Type | SHA-256 |
|---|---:|---|---|
| `proof.json` | 803 bytes | JSON data | `f9ae81a114a745622adb5ce3a2f2453fc2cccf5a332ac8aea3aae8627fcc8eeb` |
| `public.json` | 8 bytes | JSON data | `a00f79c38314728d88946e6d517d5f02b2f7e27b863f8650551054f53c3d0462` |

The final backend `git status --short` produced no output. The proof and generated public vector remain ignored diagnostic artifacts.

## Gate 7: semantic and negative checks

- Generated-vector source verification: **Passed 21 July 2026**
- Intended-Noir-vector verification: **Rejected 21 July 2026, confirming the incompatibility**
- Overall Noir semantic compatibility: **Failed**

The expected exported public input vector contains one field element representing decimal `49`. Verification success with a different vector does not pass this gate.

After the positive check, alter a copy of the public input or proof and confirm that verification rejects it. Preserve the original generated files unchanged for hashing.

The unchanged diagnostic proof verified with the backend-generated public vector:

```text
[INFO] snarkJS: OK!
generated_public_verify_exit_code=0
```

The same proof was then checked against the committed Noir-intended public vector `["49"]`:

```text
[ERROR] snarkJS: Invalid proof
intended_noir_public_verify_exit_code=1
```

The negative fixture SHA-256 is:

```text
8b868b99fafcb64835a031e26fa9c6e2656cdbd9a47ac522f00366f24f7918a6
```

The final re-hash confirmed that verification did not modify the source artifacts:

| Artifact | SHA-256 after both checks |
|---|---|
| `verification_key.json` | `15fcf947c110698b050b6e45ea6a83509cc080c4a8ecd1489a073497acebefb4` |
| generated `public.json` (`["7"]`) | `a00f79c38314728d88946e6d517d5f02b2f7e27b863f8650551054f53c3d0462` |
| `proof.json` | `f9ae81a114a745622adb5ce3a2f2453fc2cccf5a332ac8aea3aae8627fcc8eeb` |

This result demonstrates that source-backend proof verification and preservation of Noir's intended public statement are different properties. Replacing `7` with `49` after proof generation is not a repair: the verifier correctly rejects that altered statement. The R1CS wire allocation itself must be corrected or rejected before setup and proving.

## Gate 8: artifact inventory

Status: **Passed 21 July 2026**

Inventory and hash:

- `circuit.r1cs`
- `witness.wtns`
- Powers of Tau final transcript
- initial and contributed `.zkey` files
- `verification_key.json`
- `proof.json`
- `public.json`

The final recursive inventory covered 27 files under `target/week-08`, returned exit code `0` for both exact-size and SHA-256 passes, and reported a total directory size of `13M`. Every digest matched the value captured at its earlier gate.

The inventory includes both the rejected uncontributed transcript and the accepted contributed transcript so the failed setup path remains auditable. All generated artifacts remain ignored by Git. The external backend checkout remained clean at detached HEAD; the standalone status contained only the expected Week 8 source/document changes and the preserved Week 7 documentation edit.

## Gate 9: public-first compatibility control

- Nargo check and compilation: **Passed 21 July 2026**
- Nargo execution: **Passed 21 July 2026**
- Backend parse and pedantic witness solving: **Passed 21 July 2026**
- Strict interop and snarkjs witness validation: **Passed 21 July 2026**
- Circuit-specific setup, contribution, binding verification, and VK export: **Passed 21 July 2026**
- Control proof generation and public export: **Passed 21 July 2026**
- Control positive/negative verification: **Passed 21 July 2026**

The original private-first artifact remains unchanged as regression evidence. A second circuit declares public `y` before private `x` while preserving `x * x = y` and the same non-secret values.

This control tests a narrow hypothesis: if Nargo assigns `y` to the leading ACIR witness, the selected backend's identity witness-to-wire mapping may produce the correct Groth16 public vector `[49]`.

Acceptance requires fresh retained evidence for compilation, ACIR witness positions, parsing, pedantic solving, strict interop, snarkjs witness checking, proof generation, public-vector inspection, positive verification with `49`, and negative verification with `7`.

A passing control does not make the backend generally compatible. The final toolchain must reject layouts that do not satisfy the R1CS public-wire convention or implement a sound general remapping.

The control was checked and compiled with Nargo/noirc beta.18. `nargo check` returned exit code `0`; its only output was the expected note that the committed development `Prover.toml` already existed. `nargo compile --print-acir` returned exit code `0` and established:

```text
Compiled ACIR for main:
func 0
private parameters: [w1]
public parameters: [w0]
return values: []
ASSERT w0 = w1*w1
```

Artifact inspection:

| Property | Value |
|---|---|
| Path | `circuits/square-root-public-first/target/square_root_public_first.json` |
| Displayed size | 1.1 KB |
| Type | JSON data |
| SHA-256 | `cfc9ffb05a68215412bfaed678ae5fca10eb248c48df02547f0b23e162aba946` |
| noirc | `1.0.0-beta.18+99bb8b5cf33d7669adbdef096b12d80f30b4c0c9` |

The artifact ABI lists public `y` first and private `x` second. This passed the control's first semantic checkpoint: intended public `y = 49` became ACIR witness `w0`, the position that the selected backend maps to leading R1CS wire 1. Later gates confirmed parsing, solving, lowering, Groth16 export, and positive/negative verification.

`nargo execute witness` independently solved the control and returned exit code `0`:

```text
[square_root_public_first] Circuit witness successfully solved
[square_root_public_first] Witness saved to target/witness.gz
```

| Artifact | Size | SHA-256 |
|---|---:|---|
| `circuits/square-root-public-first/target/witness.gz` | 47 bytes | `675c5ce31682ff63e3b26eb6fda0049331576b2e03e4b80e17391aa7674d06c9` |

The macOS `file` utility described the small stream as `gzip compressed data, max compression, truncated`; the dedicated `gzip -t` integrity check returned exit code `0`. The repository status showed only the expected Week 8 source/document changes and the preserved pre-existing documentation edit; circuit `target/` outputs remained ignored.

The pinned backend parsed the public-first artifact and returned:

```text
opcode_count=1 witness_count=2 opcode_variants=AssertZero
public_first_parse_exit_code=0
```

The default pedantic witness solver returned:

```text
witness_count=3 witness_map_entries=2
public_first_backend_witness_exit_code=0
```

The assignment order is the intended semantic order:

| ACIR witness | Value | Intended role |
|---:|---:|---|
| `w0` | 49 (`0x31`) | public `y` |
| `w1` | 7 (`0x07`) | private `x` |

Generated backend artifacts:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `public-first/parse/parsed.json` | 90 bytes | `1ef2e569e359417568965dfb7c81f2ceb87d89dda88beb521353ca449c8ae845` |
| `public-first/witness/witness_map.json` | 156 bytes | `3f8533a2a818dbea5287dd0175e4d6ccb9464f64ae6eb69a756d08e3c26f7a26` |
| `public-first/witness/witness.bin` | 96 bytes | `1a6d5b1fd2d4b32cc23f863807018bc4e11c630baed1a7c14c9fdfa6131975eb` |
| `public-first/witness/witness.wtns` | 172 bytes | `700258dc03c6da2cb88cbfc40bd5210fafdc80d3252318466fedd8b635e8d675` |

The backend `git status --short` produced no output. This establishes correct public/private assignment before R1CS lowering; the target R1CS classification remains a separate gate.

Strict interop returned exit code `0` without relaxed flags:

```text
n_wires=4 n_constraints=2 witness_len=4
```

Pinned snarkjs 0.7.5 independently reported:

| Property | Value |
|---|---:|
| Curve | BN254 (`bn-128` / `bn128`) |
| Wires | 4 |
| Constraints | 2 |
| Public inputs | 1 |
| Private inputs | 1 |
| Outputs | 0 |
| Custom gates | false |

The WTNS check returned exit code `0`, `WITNESS IS CORRECT`, and `WITNESS CHECKING FINISHED SUCCESSFULLY`. Its JSON wire vector is:

```json
[
  "1",
  "49",
  "7",
  "49"
]
```

With zero public outputs and one public input, leading wire 1 now contains intended public `y = 49`. This passes the control's R1CS semantic gate.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `public-first/interop/circuit.r1cs` | 384 bytes | `2c4f0098c2d5163574c733f47ef5fb415c3c7b0c7a3eee42ae3cb36dcaa97efc` |
| `public-first/interop/witness.wtns` | 204 bytes | `e95ff9609233e3b812c164fb633f2eecba9d3909ca01b6eead061ea83fc348fc` |
| `public-first/interop/witness.json` | 28 bytes | `d108c1af291b33d9d684ee0affe27b44083c1cc58a3c42c9189af24e465d441d` |

The backend worktree remained clean. A new circuit-specific ZKey is required because this corrected-layout R1CS has a different digest from the diagnostic private-first R1CS. The already verified contributed Powers of Tau transcript may be reused as universal setup material for this development control.

The public-first Groth16 setup used the corrected-layout R1CS and the already verified development Powers of Tau transcript. Every command returned exit code `0`.

Circuit hash:

```text
aefc061a 94f5dafb 34d38f21 1a8c49c8
3ba7c4ab baac13c7 795d4c4d a95ac63d
3bac198a 7f041389 3d6e8027 3a610cb7
c4ef1e49 fc95afc3 d68f86c0 a8307ebe
```

Named contribution: `Nelly Week 8 public-first development contribution`

```text
f998d682 74bd0d9f 00dd135d b3132842
bf5e5873 3832f527 2e512e50 aabeab9e
7eab5a61 663a3509 164dade5 8d1051c1
04f8e31f a317d95b 98eba088 1ad8e3f0
```

The binding verification recomputed the same circuit hash, listed that contribution, and reported `ZKey Ok!`. Verification-key export detected protocol `groth16` and completed successfully.

| Artifact | Exact size | SHA-256 |
|---|---:|---|
| `public-first/groth16/circuit_0000.zkey` | 2,712 bytes | `2acf8ff394f29fc3f80706017427bbe66cb1b1ee878b46352b99d393fd1ab966` |
| `public-first/groth16/circuit_final.zkey` | 3,156 bytes | `c5083db75ac384e7b72c6b5bd4c5066bb19f8b2a84447beb4bf5a2ccba8f0f46` |
| `public-first/groth16/verification_key.json` | 2,931 bytes | `19654ceb85017d4ce4b36c41acaabebb2421d42916aba57d4918944e8e1acc3d` |

The final backend `git status --short` produced no output. This establishes the key's binding to the corrected-layout R1CS, not yet proof correctness or exported public-input value.

The public-first `groth16 prove` command returned exit code `0` and was not rerun. The generated proof identifies protocol `groth16` and curve `bn128`.

The exported public vector is exactly the Noir-intended statement:

```json
[
  "49"
]
```

| Artifact | Size | Type | SHA-256 |
|---|---:|---|---|
| `public-first/groth16/proof.json` | 806 bytes | JSON data | `0487979648c2f7819a3544a2da7f8a2407057a15a6aaaa1d8b2fbc91933d715a` |
| `public-first/groth16/public.json` | 9 bytes | JSON data | `8d683c14535896df9e3f636c1cb3fa5483cb8cb950f4fd1e50f200077fcfb64b` |

This passes proof-export semantics for the narrow control. Source verification with `[49]` and rejection with `[7]` remain separate required checks.

The unchanged public-first proof verified against generated/intended `[49]`:

```text
[INFO] snarkJS: OK!
public_first_correct_verify_exit_code=0
```

The same proof rejected the fixture containing private value `[7]`:

```text
[ERROR] snarkJS: Invalid proof
public_first_wrong_verify_exit_code=1
```

The negative fixture SHA-256 is:

```text
6b76b7114eb9596b5a55eafb0a3d664e777806d53e5016c1f74b939d1a58b9f0
```

The final hashes remained unchanged after verification:

| Artifact | SHA-256 after both checks |
|---|---|
| `public-first/groth16/verification_key.json` | `19654ceb85017d4ce4b36c41acaabebb2421d42916aba57d4918944e8e1acc3d` |
| `public-first/groth16/public.json` (`["49"]`) | `8d683c14535896df9e3f636c1cb3fa5483cb8cb950f4fd1e50f200077fcfb64b` |
| `public-first/groth16/proof.json` | `0487979648c2f7819a3544a2da7f8a2407057a15a6aaaa1d8b2fbc91933d715a` |

The final backend `git status --short` produced no output.

### Control conclusion

For this circuit, placing public `y` first produces an ACIR witness order that happens to satisfy the selected backend's identity witness-to-R1CS-wire mapping. The resulting Groth16 proof preserves the intended public value and passes both positive and negative source-verifier checks.

This is a constrained compatibility result, not general support. The original private-first regression proves that arbitrary valid Noir parameter layouts can silently produce a source-verifiable Groth16 proof for the wrong public interface. Until a general wire remapper exists, tooling must fail closed unless all public output/input witnesses occupy exactly the leading R1CS positions required by the target format.

## Claim provenance

The completion claims in this record are limited to reviewed command output. The original private-first path completed parsing, solving, lowering, setup, proving, and source verification but failed public-input semantic preservation. The public-first control completed the same stages, preserved public input `49`, and passed the positive/negative verification pair. Neither result establishes general Noir compatibility, production setup security, arkworks interoperability, or CKB execution.
