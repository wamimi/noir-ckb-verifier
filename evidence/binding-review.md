# Binding review and bounded validation — 2026-10-06

Status: locally reproduced. This is not an audit, production admission, public
node deployment, independent clean-clone reproduction, or a complete application.
The protection inventory was written before tests/mutations. Production contract,
circuit, schema, dependency pins and CLI protocol were not changed.

## Revisions and evidence sources

- Toolkit HEAD: `090461a901ac569e3331ded05fc4c3896f0457c5`.
- Maintained backend: `828025f3a0090e2934940956c0f5dc8093eb5532`.
- Generic verifier: `d64c769ffe2d2edb5eb308dc59058efda77c2f83`.
- Both sibling checkouts were clean; no checkout/reset was performed.
- Host Rust 1.95.0; contracts Rust 1.94.1, target `riscv64imac-unknown-none-elf`.
- Nargo beta.18 / noirc `99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`.
- snarkjs 0.7.5, invoked offline; locked dependencies unchanged.

Raw commands, working directories, selected environment overrides, exit statuses
and complete stdout/stderr are retained locally in:

- `target/binding-review-2026-10-06/validation-02/commands.json`
- `target/binding-review-2026-10-06/public-probe-01/commands.json`
- `target/binding-review-2026-10-06/quality-02/commands.json`

The [reviewable manifest](binding-review-manifest.json) retains revisions,
source/fixture/binary/log/reference hashes and results. Large artifacts and raw
logs remain under ignored `target/`; a fresh checkout must rerun the scripts.
The 21 new Rust tests initially had a type-inference compilation error, corrected
before baseline execution. That failed compile is not a successful test or mutation.

The original successful `validation-01` and `quality-01` are preserved. Final
`validation-02` repeats the bounded matrix after making code deployment identities
deterministic in the new reuse tests; named OutPoint/capacity/output changes now
vary independently of synthetic code identities. Final source hashes are in the
manifest. Both runs produced the same isolated binary hashes and named cycle
observations. Zero-public-input fresh proving was not attempted; Week 14's
zero-public evidence remains layout-only.

## Baseline and exact binaries

The Capsule proof/key/public files were reused from the **published-fork Week 14
normal CLI run**, `target/noir-ckb/proof-bound-capsule/proofs/1791143299589/fixture`.
This task did not generate a fresh Capsule proof or rerun the full CLI workflow.
Public vector: `[11,65,5,66,1,96,13]`. Fixture SHA-256 values are in the manifest.

The generic verifier was the retained binary, not rebuilt here. Capsule baseline
and each mutant were freshly built in separate copied contract workspaces with
`cargo +1.94.1 build --locked --offline --release --target
riscv64imac-unknown-none-elf -p capsule-binding`. Release profile: opt-level z,
LTO, one codegen unit, panic abort, overflow checks, strip enabled, debug false.
`RUSTFLAGS` are exactly retained per build: disable target feature a and remap
Cargo registry, Rust toolchain and copied repository paths to canonical paths.
No debug-assertion flag was added. Baseline output was byte-identical to the
existing Capsule binary. Original source and both original binaries were hashed
before and after and remained unchanged.

| Binary | SHA-256 | Bytes |
| --- | --- | ---: |
| Retained generic verifier | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` | 98464 |
| Fresh isolated Capsule baseline | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` | 28032 |
| Skip slot 3 comparison | `074bd5759af35f216ee4014be970432c4d9913a1289b5ed725ca8fcffc214f27` | 28096 |
| Remove matching-Lock input count predicate | `0ee031cc801b0fe80d0243c64f8ac3068c254afb7ea0a753807bc3fd04dfbfa7` | 28024 |

CKB personalized Blake2b executable data hashes are, respectively, generic
`5104ce90e20f4a0fe633c99f5a8a258b24433eaef087b46160e584601732e169` and baseline
Capsule `7d400279013c74af71a62aa5ec4a6adf11b778a91dfa75c93366c0caf451ccdd`.
These are not the testtool Script code_hash: the harness uses synthetic
`hash_type=Type` code identities. There is no deployment receipt.

The baseline ran with the fixture override and the actual isolated binary:

| Test target | Result |
| --- | --- |
| `capsule_transition` | 12 passed, none failed/ignored |
| `binding_boundaries` | 21 passed, none failed/ignored; several tests cover multiple cases |
| `verifier_vm` | 2 passed, none failed/ignored |

Observed cycles: original matrix valid transition `101642850`; new boundary
baseline `101643464`; standalone verifier `101593641`. These are exact-testtool-
transaction observations, not interchangeable benchmarks or node measurements.
`250000000` is the harness budget, not a consensus limit. No new peak-memory or
Spawn/IPC measurement is claimed.

## Two check mutations detected semantically

| Isolated change | Passing control | Target negative result |
| --- | --- | --- |
| `require_public_input`: add `index != 3 &&` to the mismatch condition | Original valid transition accepts | `valid_proof_and_wrong_new_state_reject` fails because the mutated binary accepts (101642429 cycles), instead of baseline Type 30 |
| `validate_lock_group`: remove only `matching_inputs != 1 ||` from the rejection predicate | Original valid transition accepts | `duplicate_verifier_lock_input_rejects_witness_ambiguity` fails because the mutated binary accepts (101644140 cycles), instead of baseline Type 33 |

Both cargo test failures are exit 101 with the targeted test name and
`transaction must be rejected: <cycles>` from `expect_err`, not compilation,
timeout, missing binary, or unrelated script failures. The runner demands that
signature. Each mutation changes one check; no cryptographic primitive is mutated.
Isolated mutant source/binaries remain labeled under `validation-02/` for review
and are never selected by the normal CLI. No baseline restoration was needed.

## Reuse and composition boundaries reproduced

Detailed names/source fields are mapped in the updated
[protection inventory](../docs/binding-protection-inventory.md).

- Changing Cell identity, old/new state, old/new nullifier or domain while keeping
  the valid original proof/public vector rejects at Type 30.
- Changing each of the seven public values while reusing the proof rejects at
  verifier 5; action comparison is separately isolated with the verifier absent.
- A different satisfiable operation using fixture secret 8 has recomputed tuple
  `[11,80,5,81,1,109,13]`. Supplying it with the old proof rejects at verifier 5.
  This checks old-proof/new-statement binding, not just Type comparison. We did
  not generate a second Capsule proof for that operation.
- Swapping Capsule ID/domain and making Cells match those supplied values still
  rejects cryptographically. A well-formed proof with negated C rejects as 5.
- Substituting a same-width valid-point VK (negated alpha) while retaining the
  original Lock args fails identity lookup with 12; rebinding Lock args to that
  key instead makes the old proof fail with 5. This is not a fresh setup-key test.
- The identical proof accepts for synthetic input OutPoints `[41;32]:0` and
  `[42;32]:0` with identical selected state, and for successor capacities 499
  and 501. It also accepts an additional unrelated output/data. Raw transaction
  hashes are logged. This directly demonstrates absent input/full-transaction
  binding and absent capacity preservation.
- Witness at the correct group slot accepts with an unrelated preceding input.
  Moving proof to the wrong absolute witness or omitting input_type rejects 16.
  Extra same-Lock output rejects 33; extra Capsule output rejects 23.
- Creation and destruction reject 24. Initial fixture Cells were installed by
  testtool, not created through this Type on a real chain.
- Same always-success input/output Lock plus the Type accepts an invalid proof.
  The Type does not authenticate intended verifier identity. This is a composition
  gap, not permission to claim the Type independently enforces proof validity.

## Declared-but-unused public input: fresh experiment

`scripts/check-public-input-binding.py` created a separate temporary Noir circuit:

```noir
fn main(x: Field, y: pub Field, _context: pub Field) {
    assert(x * x == y);
}
```

Nargo compile/execute and a freshly rebuilt pinned backend were used. Backend
binary SHA-256: `91e1519440bff862cac32e912457d5cd7f806a00bb52c462223ccfa3e11bc62f`.
Both assignments (`x=7,y=49,context=13` and context 14) passed snarkjs WTNS checks.
R1CS had 5 wires, 2 public inputs, 1 private input and 2 constraints. Public
context is wire 2 and occurs in **none** of the A/B/C rows. R1CS bytes were
identical across the two assignments, SHA-256
`8c71b34f7d7c593b1d1ba981602dec4092e5d4b8472aa8445c4f03b8c7810012`.

The retained public-development ptau was verified, then fresh circuit setup,
public-entropy contribution, zkey verification and two proofs were generated.
Ptau SHA-256: `9f4a804834540389ff684ca19b2ad7b54648cc57750c20e8d8c8b82efcdc9b10`.
This is explicitly not a production ceremony.

| Check | Result |
| --- | --- |
| Fresh proof 13 + `[49,13]`, snarkjs | Accepted |
| Fresh proof 14 + `[49,14]`, same VK, snarkjs | Accepted |
| Proof 13 + `[49,14]`, snarkjs | Invalid proof, exit 1 |
| Proof 13 positive/negative, arkworks adapter | Accepted/rejected |
| Positive Molecule/endpoint host round trip | Accepted |
| Standalone generic verifier CKB-VM positive/negative | 2 passed, negative code 5 |

The standalone VM harness's inherited `week10_noir_capsule` and
`wrong-new-state-public.json` labels refer here to this explicit two-input probe,
not Capsule. Its measured positive verification was 100183276 cycles; do not
compare this different proof/circuit directly with Capsule performance.

Primary implementation inspection explains the result: arkworks v0.5.0
[`LibsnarkReduction`](https://github.com/arkworks-rs/groth16/blob/v0.5.0/src/r1cs_to_qap.rs)
adds an instance-variable domain segment to A, with matching witness-map values;
[`prepare_inputs`](https://github.com/arkworks-rs/groth16/blob/v0.5.0/src/verifier.rs)
uses every public scalar in `IC[0] + sum(public[i] * IC[i+1])`.
Our actual prover is snarkjs 0.7.5, not arkworks setup: inspected
`src/zkey_new.js` adds A/IC terms for every `s <= nPublic` at
`r1cs.nConstraints+s`. Backend allocation retains declared public wires even
when no application row references them. The pinned CKB verifier also rejects
infinity IC points. These are implementation-specific facts and empirical checks,
not a blanket theorem that every declared input in every backend is securely bound.

No script derives context for this isolated probe. It establishes cryptographic
binding only. Capsule still has no input-specific or transaction-specific slot;
all its current fields participate in application equations. Adding a derived
context requires an approved schema/protocol change.

## Quality gates and reproduction

Formatting passed; strict `cargo +1.95.0 clippy --locked --offline --workspace
--all-targets -- -D warnings` passed; workspace tests passed (17 host tests,
35 binary-dependent VM tests ignored there and run explicitly as above).
Both Python runners parsed successfully. No dependency lockfile changed.

Rerun using **fresh** output directories; both runners refuse reuse:

```bash
python3 scripts/check-binding-boundaries.py \
  --out target/binding-review-new/validation \
  --verifier /absolute/path/to/groth16-ckb/script/target/riscv64imac-unknown-none-elf/release/ckb-script \
  --fixture /absolute/path/to/retained-or-generated-capsule-fixture

python3 scripts/check-public-input-binding.py \
  --out target/binding-review-new/public-probe \
  --ptau /absolute/path/to/public-development-phase2.ptau \
  --verifier /absolute/path/to/groth16-ckb/script/target/riscv64imac-unknown-none-elf/release/ckb-script
```

Without `--fixture`, the first runner uses the committed Week 10 fixture; that
would be a different provenance from this recorded run. The existing historical
`week14-layout-check.py` expects the old uncommitted backend experiment and was
inspected but not run against the published fork. Previous validation directories
and current-build/proof/test pointers were not overwritten.

External claims, pinned source comparison and the bounded Battleship direction
are in [the exchange review](../docs/arthur-cecilia-binding-review.md). Current
behavior and future design are separated in [the proposed specification](../docs/binding-profile-v1.md).
