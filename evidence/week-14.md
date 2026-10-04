# Week 14 local implementation evidence

Status: tested scalar-fixture acceptance passed through fresh Groth16 proofs,
host adapter checks and the Capsule CKB-VM matrix. General compatibility and
upstream review remain outside this result. Evidence consolidated 2026-10-04.

## Baseline (before production code edits)

The backend was clean at `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`.
Fresh interop with its pre-existing binary produced leading public wire 7 for
private-first and 49 for public-first. snarkjs 0.7.5 accepted both R1CS/WTNS pairs.
Historical proof/key pairs were reverified: private-first accepted 7 and rejected
49; public-first accepted 49 and rejected 7. This was not fresh baseline proving.
The binary hash and commands are in `target/week-14/baseline/provenance.json` and
`commands.json`. The source was not rebuilt for that interop gate.

A new regression was then run against unchanged production source. After fixing
a missing trait import in the test, the actual semantic result was one passed,
one failed: private-first produced 7 where 49 was expected. Retained log:
`target/week-14/baseline/regression-corrected.txt`. The initial compile error is
also retained in `regression.txt` and is not counted as defect reproduction.

## Patched focused tests actually executed

| Command | Observed result |
| --- | --- |
| `cargo +1.95.0 test --locked --offline -p noir-r1cs --test week14_layout` | 7 passed |
| `cargo +1.95.0 test --locked --offline -p noir-cli --test cli` | 8 passed |
| `cargo +1.95.0 test --locked --offline -p noir-ckb-cli` (toolkit) | 5 passed |

Logs are in `target/week-14/patched/layout-final.txt`, `cli-final.txt`, and
`toolkit-compatibility.txt`. Formatting was run in both repositories; diff
whitespace checks passed. At the initial handoff the runner was syntax-checked
only; its subsequent successful executions are recorded below.

Regression development exposed two additional consumers: metadata range checks
must not treat insertion in the wire map as proof of an in-range ACIR index, and
`known_wire_value` must translate a wire before reading instance ACIR values.
Both were corrected and the focused suites rerun successfully. Intermediate
failing logs are retained separately where available.

The real compiler fixtures cover both squares, interleaved scalar Fields,
zero-public inputs and Capsule. Synthetic tests cover disjoint output ordering,
JSON mapping roundtrip, overlap rejection, invalid witness and constant-one
rejection. Toolkit tests explicitly reject arrays, structs and returns.

## Acceptance progression

At the initial handoff, workspace checks, fresh proofs and VM execution were
pending. The subsequent results below supersede that pending status only for
the named fixtures and commands. Historical evidence remains separate.

No commits, staging, PRs or external posts were made. The CKB verifier and
historical fixtures were not modified. Pre-existing toolkit planning documents
and Week 13 research files remain untouched.

## Separate behavior-preserving Clippy cleanup

Removed exactly six redundant `.into_iter()` calls passed as `.zip(...)`
arguments: `flattened` in noir-witness; two `digest` calls, `state`,
`field_to_bits_le(value, num_bits as usize)`, and `output_bits` in noir-r1cs.
All six expressions were independently confirmed in the original pinned revision.
`zip` already accepts `IntoIterator`, so iteration ownership and order are
unchanged. This is a lint-only follow-up, separate from the visibility fix.
No warnings were suppressed and no broad automatic fixes were used.

The isolated delta and before/after source hashes are retained under
`target/week-14/lint-cleanup-01/`; its `backend.patch` also snapshots the updated
combined tracked diff. This source snapshot does not establish rebuilt binary,
proof or test provenance. Subsequent strict Clippy, workspace tests and the
`local-check-02` rebuild passed after this cleanup. No staging or commit was
performed during this evidence update.

Both `target/week-14/local-check-01` and `local-check-02` are preserved. The runner
refuses existing output directories; any subsequent execution needs a fresh path.

## Post-cleanup quality and layout gates

Results below were supplied as terminal output by the developer. Tests were not
rerun during documentation consolidation. Artifact hashes and the correspondence
of the current backend patch/new files to `local-check-02` were checked locally.

| Gate | Result |
| --- | --- |
| Backend formatting | Passed |
| Backend Clippy, workspace/all-targets/all-features, warnings denied | Passed |
| Backend default workspace tests | 95 passed, 0 failed, 3 ignored |
| Toolkit formatting and workspace/all-targets Clippy, warnings denied | Passed |
| Toolkit default workspace tests | 16 passed, 0 failed, 14 VM tests ignored |
| Refreshed layout runner, `local-check-02` | Passed; five R1CS/WTNS pairs checked by snarkjs 0.7.5 |

The three ignored backend tests are the Nargo compatibility corpus and two
expensive witness-driven MSM tests. They were not executed by the reported
workspace command. The 14 ignored toolkit VM tests were executed separately
with the fresh Capsule fixture, as recorded below.

## Fresh setup, proofs and host verification

The retained development Powers of Tau file verified successfully. Its SHA-256
is `29c1d78626c2501f8d452b3c91c4e7b19e651674740e8961d7fb969899b677da`.
Each of the following circuits received fresh circuit-specific setup and a
development contribution; each resulting zkey verified before proof generation.
Public development entropy was used. This is not production-safe setup material.

| Fixture | Generated public vector | snarkjs positive | snarkjs negative |
| --- | --- | --- | --- |
| Private-first square | `[49]` | Accepted | `[7]` rejected, Invalid proof, exit 1 |
| Public-first square | `[49]` | Accepted | `[7]` rejected, Invalid proof, exit 1 |
| Interleaved scalars | `[49,121]` | Accepted | `[121,49]` rejected, Invalid proof, exit 1 |
| Capsule | `[11,65,5,66,1,96,13]` | Accepted | No separate fresh snarkjs negative run recorded |

All four fresh proof/key/public sets passed arkworks positive verification and
the CKB host wire-decoder roundtrip. Arkworks rejected `[7]` for each square,
the swapped vector for interleaved, and the retained wrong-new-state vector for
Capsule. `week14_fresh_adapter_checks_exit_code=0`.

This establishes the corrected public statement for the reproduced scalar
fixtures. It does not establish arbitrary ABI ordering or support for other
Noir versions and features.

## Fresh Capsule CKB-VM execution

`NOIR_CKB_FIXTURE_DIR` selected the absolute path to
`target/week-14/local-check-02/capsule-vm-fixture`. The proof, key and public
JSON files match the fresh Capsule artifacts byte-for-byte. The negative vector
was copied from the retained Week 10 fixture. The harness converts JSON to wire
artifacts itself; it does not consume the adapter-output directory directly.

| Binary | SHA-256 |
| --- | --- |
| Pinned generic verifier | `9a6ed1137687a8d55037488bbdafa7d1f60aacc771d87ef82dde1a2023e011f8` |
| Capsule binding | `6ccc3e145c55c7b2b4f5eb62d79b1174b602f0adc5dab9e0196b4754ed218962` |

The `verifier_vm` and `capsule_transition` targets ran with `--ignored
--nocapture`: 2 and 12 passed respectively, with no failures or ignored cases.
`week14_fresh_capsule_vm_exit_code=0`.

| Measurement | Cycles |
| --- | ---: |
| Fresh Capsule verifier test | 101577918 |
| Fresh Capsule bound-transition test | 101627127 |

Rejection codes observed: truncated witness 17; missing VK 12; invalid proof 5;
wrong state/capsule identity/replay domain binding 30; malformed args 21;
duplicate Capsule input group 23; changed lock 32; duplicate verifier lock
group 33; malformed Cell data 25. The `week10_` log prefixes are inherited test
labels, not a claim that the historical proof was used.

## Provenance and remaining scope

The original layout manifest remains unchanged. A separate
`target/week-14/fresh-validation-manifest.json` records selected fresh artifact
hashes and the observed results. It is a retrospective evidence record, not a
replacement for raw terminal logs or a rerun of the tests.

Backend tracked patch SHA-256:
`0814afc05b0cd5e50508d0311b5fbcbe1b0e3357c62a6da48c6c729fc8ce4fab`.
The tracked patch and snapshotted new backend files matched `local-check-02`
when checked on 2026-10-04.

Still outside acceptance: the three ignored backend tests; fresh proof/adapter/
VM validation for zero-public circuits; VM runs for the square and interleaved
fixtures; arrays, structs and Noir returns; a clean-checkout external review;
normal CLI integration of a published patched backend revision; upstream review
and release. Capsule remains a wiring fixture. No audit, testnet deployment,
production ceremony, Battleship implementation or general Noir support is claimed.

## Published fork integration — 2026-10-04

This section supersedes the earlier pending normal-CLI integration status, not
the historical patch snapshots or their hashes.

The backend fix was published to `wamimi/Noir-Groth16`, branch
`fix/week14-public-wire-layout`, commit
`828025f3a0090e2934940956c0f5dc8093eb5532`. The original project attribution and
license declaration remain intact. No upstream PR was opened. The user supplied
successful backend all-feature validation (95 passed, four ignored), followed
by the separate snarkjs interop smoke test (one passed, zero ignored).

The toolkit configuration now pins that exact fork commit. Historical pins in
earlier evidence remain unchanged. Active setup instructions are in
`docs/current-generated-proof-workflow.md`. The clean-revision check, ABI Field
restriction, return-value rejection and R1CS public/private semantic checks
remain enabled. An additional unit test covers both scalar visibility orders.

The following were executed directly on the local integration checkout:

| Check | Result |
| --- | --- |
| Formatting and whitespace | Passed |
| Strict workspace Clippy, all targets | Passed |
| Workspace tests | 17 passed; 14 binary-dependent VM tests ignored |
| Release CLI build | Passed |
| Normal `noir-ckb build` | `build_status=compatible` |
| Normal `noir-ckb prove` | `prove_status=verified` |
| Normal `noir-ckb test` | `test_status=passed`; 12 VM matrix cases passed |

The initial sandboxed build stopped at npm dependency resolution: an offline
attempt returned `ENOTCACHED`, and the waiting online attempt was interrupted.
The normal workflow then passed with approved network/sibling-build access.
No compatibility guard was bypassed.

Generated records under `target/noir-ckb/proof-bound-capsule/`:

- Build: `builds/1791143284259/build-manifest.json`.
- Proof: `proofs/1791143299589/proof-manifest.json`.
- VM result: `tests/1791143330810/test-report.json`.

The build manifest records the published backend commit, toolkit HEAD
`521e978449b31701d29e7e35c3a34d4f15bae43a` with `repository_dirty=true`,
seven public inputs, one private input, five constraints and eleven wires.
Both external dependency checkouts were clean. The CLI used its normal output
directory and updated current-manifest pointers while retaining old runs.

Fresh public vector: `[11,65,5,66,1,96,13]`. Snarkjs accepted it and rejected all
three configured altered vectors (new state, Capsule identity, replay domain).
The prove stage also completed its arkworks negative checks and positive wire
round trip. The normal test command ran all twelve Capsule transaction cases;
the two standalone verifier VM tests were not separately rerun in this stage.

Accepted transaction cycles: `101642850`. VK data hash:
`42e3da6aa750e2cc8cac4c2171e1936cf9ce0e5c2a7900dbfe8a2e3e785d21f1`.
These are observations for this fresh setup/proof, not universal performance
or deterministic proof-hash claims. Generated manifests retain artifact hashes.

This validates local integration of the published fork. Independent clean-clone
testing, wider Noir compatibility and security review remain outstanding.
Development setup and the arithmetic Capsule fixture remain unsuitable for
production. No commits or publication of the toolkit changes occurred in this
validation step.
