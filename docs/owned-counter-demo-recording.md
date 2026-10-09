# Record the owned-counter demonstration yourself

Target length **approximately five minutes**, with seven scenes. This is a recording guide,
not a generated video or a public posting. All terminal commands below run from the
repository root. No new deployment/update, wallet access, signing or broadcast is
needed. This is a public proof-enforcement reference application, not privacy or a
bring-your-own-circuit generator. Speak naturally; the wording below is ready to use.

## Preparation checklist

- Open the source checkout containing Week15. Show [reviewer entry](owned-counter-review.md),
  [circuit](../circuits/owned-counter-v1/src/main.nr), [Type](../contracts/crates/owned-counter/src/main.rs),
  [quickstart](owned-counter-quickstart.md), [testnet evidence](../evidence/week-15-testnet.md)
  and [matrix](owned-counter-test-matrix.md) in readable editor tabs.
- Open these exact public explorer transaction pages beforehand:
  - [Deployment](https://testnet.explorer.nervos.org/transaction/0x0ee39d547101eb348bc72a93f9a08b301353267487f3061f54a0070c44f27ad1)
  - [Creation](https://testnet.explorer.nervos.org/transaction/0x57ee42444304f1c1508c1b6136c4e1c33adb1ff8086eb885bd5abdd5080b269b)
  - [Update](https://testnet.explorer.nervos.org/transaction/0x24a336fbc09ea5330b83adcbaaf17e6eaafcb21776e13df6ec01d00daa613bb6)
  RPC content/transaction IDs were checked; explorer layout/availability may change.
  If the explorer is unavailable, show the recorded evidence and live RPC output,
  not a mock UI or an invented explorer screen.
- Use a separate recording terminal with large text and a neutral prompt. Hide
  desktop notifications, unrelated tabs, shell history and personal directory names.
  Do not open wallet/account directories or show passwords, keys, tokens or seed phrases.
  Do not record a signing prompt. Public addresses/transaction hashes are not secrets.
- Bootstrap's npx cache must already be populated for the offline proof check.
  Run the no-wallet commands once before recording. There is no custom counter UI.
- Prepare the historical local-run result and public testnet receipts as editor tabs.
  These are **recorded results**, not new execution. Explain that on camera.
- Safe reruns: `review-counter.py` (without `--out`), its optional read-only RPC mode,
  `owned_counter.py --help`, and snarkjs verification below. Proof verification uses
  a cached package; it neither generates a proof nor modifies a transaction.
- Do not rerun setup, local lifecycle, account creation or any prepare/sign/send
  commands for the recording. Setup/local runner write artifacts and the local
  runner signs/broadcasts on its disposable node. Testnet `send` changes chain state.
- Long-running proof generation: show the implemented command and a previously
  generated result, explicitly saying it was generated earlier. Do not splice a
  cached result into footage labelled live proof generation. No extra live update
  is needed; any optional future update requires separate approval and live funding,
  original setup, current app Cell, a new context-bound proof and owner signature.

## Scene 1 — the developer problem (30 seconds)

**Show:** `docs/owned-counter-review.md`, opening paragraph; then the first paragraph
of `docs/owned-counter-quickstart.md`. Highlight “specific Cell transition”. No command.

**Say:** “A proof can verify mathematically and still be attached to the wrong
operation. For a CKB application, we also need to decide which Cell is being spent,
what its successor must contain, and who is allowed to authorize it. Week15 of
noir-ckb implements one small example of that complete path: a public counter.”

**Why:** Introduces application enforcement, not just a pairing benchmark.
**Transition:** “First, here is exactly what the Noir circuit proves.”

## Scene 2 — the Noir relation (30 seconds)

**Show:** `circuits/owned-counter-v1/src/main.nr`, lines1–8, all eight lines visible.
Highlight `new_count == old_count + 1`, the two u64 bounds and two context limbs.
No command; opening a file changes nothing.

**Say:** “The circuit proves a bounded increment: the new count is the old count
plus one. Both counts are public. Two more public fields carry the operation
context as halves of a digest. This is deliberately not a privacy demonstration.
The circuit proves the relation; the CKB Type has to derive the right statement
from the actual transaction.”

**Why:** Honest semantics; no arithmetic value is called a hiding commitment.
**Transition:** “The application rules are what connect those two parts.”

## Scene 3 — what CKB enforces (50 seconds)

**Show:** `contracts/crates/owned-counter/src/main.rs`, `run()` lines91–132, then
context construction lines134–161 and witness/VK/verification lines162–181. Use
editor navigation, not fast scrolling. Optionally show `build.rs` for compiled pins.
Highlight Type ID initialization, `owner_admission`, equal owner/capacity, input
OutPoint hash, expected-public comparison and `verifier_core::verify`.

**Say:** “Initialization creates one uniquely identified counter at zero and uses
a conventional ownership Lock. Updates preserve that owner and the application's
capacity. Inexpensive admission checks happen before proof verification. The Type
pins the verification key, derives context including this input's OutPoint, the
old and new states, ownership, capacity and profile, and compares the supplied
statement before verifying the proof. An old proof for another input does not work.
Fee-paying Cells and unrelated change are deliberately outside this proof context.
There is no withdrawal or destruction path: the application's capacity stays locked.”

**Why:** Separates owner signature, transaction-derived statement, and proof checks.
Do not say every transaction field is bound or all replay attacks are solved.
**Transition:** “Here is how developers exercise this fixed example.”

## Scene 4 — build, prove and check (65 seconds)

**Show:** quickstart “One disposable local lifecycle” and “Individual operations”,
then terminal. Do not run the local runner on camera. Its command generates setup,
builds, proves, signs locally and checks real node transactions; describe it as such.

**Say:** “From the source checkout, the local runner creates fresh development
setup, builds the Type, generates proofs, and runs initialization and an update
on an isolated node. The client also exposes separate build, prepare, prove and
check steps. This is one implemented application, not yet a compiler for your
own circuit. To keep this recording short, I am verifying the public proof we
already generated for the confirmed testnet update.”

**Run** (repository root, no wallet/network/broadcast; requires cached snarkjs):

```bash
npx --offline snarkjs@0.7.5 groth16 verify evidence/week-15-public/verification-key.snarkjs.json evidence/week-15-public/update-public.json evidence/week-15-public/update-proof.snarkjs.json
```

**Expected:** exit0 and `OK!`. This proves verification of the retained public proof,
not live generation or transaction authorization by itself. If it fails, stop and
fix the cache/artifact issue; do not narrate success.
**Also show:** the recorded setup artifacts listed in `evidence/week-15/setup-commands.json`:
ACIR artifact, `interop/circuit.r1cs`, `interop/witness.wtns`, Groth16 proof/public
vector, and the adapter's Molecule payload. Say: “The backend produces constraints
and a witness; Groth16 produces the proof; the adapter prepares it for CKB.”
These are previously generated artifacts, not live proof generation.

**Show a specific negative result:** open `evidence/week-15/matrix-results.json`.
Compare `update-valid.json` (`Ok`) with `invalid-proof-permitted-owner.json`
(Type error 51) and `missing-signature.json` (Lock error -2).
Say: “These are recorded VM tests. The valid update passed; an invalid proof was
rejected even with an allowed owner, and a missing owner signature was rejected
separately. We test rejection as well as acceptance. A negative test marked
passed means the expected rejection occurred.”

**Transition:** “Now we can connect that proof to the confirmed Cell operation.”

## Scene 5 — confirmed testnet result (55 seconds)

**Show:** creation explorer page output0, then update page input0 and output0.
The update input must reference creation hash `0x57ee4244…080b269b`, index0.
Initial data is `0x010000000000000000`; successor data is `0x010100000000000000`.
State is version byte01 plus little-endian u64. Same full Lock, Type and 200 CKB.
Show the portable checker output if explorer fields are inconvenient.

**Run** (repository root; public read-only RPC, no writes/signatures/broadcast):

```bash
python3 -B scripts/review-counter.py --rpc https://testnet.ckb.dev
```

**Expected:** mode reports three committed transactions and contents verified;
state `0 -> 1`, capacity200; currently initial nonlive and successor live. If the
successor has since been spent, describe current status separately from historical
commitment. RPC may return `unknown` for a spent Cell; the committed update's
input reference establishes which Cell was consumed, not that status word alone.

**Say:** “These are existing confirmed transactions, not a new deployment for this
video. The counter was created at zero. The update consumes that exact application
Cell and creates the successor at one, with the same owner and 200 CKB. The operator
signed locally. This read-only check compares the committed transactions, deployed
code and key identities, and the statement derived from the actual operation.”

**Fallback:** `python3 -B scripts/review-counter.py` reads only checked-in public
files and explicitly labels recorded evidence. Say “recorded evidence” if used.
**Transition:** “You can inspect this without a wallet, or run your own local instance.”

## Scene 6 — reviewer starting point (40 seconds)

Show `python3 -B scripts/start-counter.py inspect` as the short source-checkout
entry point. The menu and `doctor` reduce setup guesswork; prerequisites still apply.

**Show:** `docs/owned-counter-review.md` review paths, bootstrap cache section,
and `docs/owned-counter-test-matrix.md` mutation table.
No long-running command. Optionally show `evidence/week-15/local-run.json` as a
**previously recorded local run**, never as a live terminal result.

**Say:** “Start at the reviewer guide. It separates the counter from our historical
Capsule fixtures, lists prerequisites, and gives a disposable local path with
expected outputs. We recorded 48 VM cases, three detected missing-check mutations,
and a real local-node lifecycle. The fresh-directory reproduction was on the same
machine with installed tools and caches; it was not independent review. macOS ARM64
is the tested environment. Setup is development-only, and hosted CI still covers
Capsule rather than the complete counter lifecycle.”

**Why:** Reviewers can test the application themselves without a misleading clean-install claim.
**Transition:** “The next step is learning which real integrations would be useful.”

## Scene 7 — request useful feedback (30 seconds)

**Show:** reviewer guide feedback section and `.github/ISSUE_TEMPLATE/owned-counter-review.md`.
Only display a published link after it actually contains this source; until then
use the local document, not a fictional release/tag.

**Say:** “What would you build with supported Noir proofs on CKB? What would your
proof establish, and which Cell transition would it authorize? If you try this
example, tell us your platform, where reproduction worked or failed, and which
missing integration capability blocks your application today. Configurable
external-circuit support is proposal work. A successful counter test or a video
view is not proof of demand; concrete use cases and reproduction feedback are
what we need next.”

**End:** Hold the reviewer link and issue-template name briefly. Do not imply a
production launch, audited security, validated demand or a Battleship implementation.

## Screen/command checklist

| Screen | Exact item | Live or recorded? | Changes? |
| --- | --- | --- | --- |
| Problem/reviewer entry | `docs/owned-counter-review.md` | Current source text | None |
| Circuit | `circuits/owned-counter-v1/src/main.nr:1` | Current deployed circuit source | None |
| Application checks | `contracts/crates/owned-counter/src/main.rs:91` | Current deployed Type source | None |
| Build/prove workflow | `docs/owned-counter-quickstart.md` | Instructions, not executing a fresh run | None |
| Public proof check | Exact snarkjs command in scene4 | Live verification of retained proof | No transaction change |
| Chain check | Exact Python RPC command in scene5 | Live read-only query | None |
| Receipts | `evidence/week-15-testnet.md` and three linked receipts | Historical confirmed results | None |
| Local reproduction evidence | `evidence/week-15/local-run.json` | Historical same-machine run | None |
| Feedback | Review guide + issue template | Draft until published | None |
