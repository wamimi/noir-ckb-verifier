# Binding lessons for noir-ckb

Inspected 2026-10-06. The product direction is a developer toolkit for supported
Noir circuits: compile/prove, create CKB verification artifacts, bind public
statements to application Cells, and test positive and adversarial operations.
The work stays Noir → Groth16 → CKB.

## Exchange chronology and evidence labels

The complete supplied attachment was read. Its earlier June/August entries are
headings, so it is not a transcript of every post. The HTML/web-reader route
failed, but `https://talk.nervos.org/t/10368.json` was retrieved with curl; it
contains posts 1–11, including the earlier bodies. The retained JSON and source
hashes are under `target/binding-review-2026-10-06/references/`.

Arthur's June 22 post asks about tooling that connects a proof to the intended
Cell transition. His August 28 post distinguishes a creation-committed proof gate
from a spend-derived transition and asks about identities, codecs, witness
placement, replay binding and adversarial/resource evidence. These are retrieved
posts, not reconstructed questions.

Cecilia's September 24 response (September 23 23:07 UTC in forum JSON) distinguishes:

| Arrangement | Fixed at creation | Derived at spend |
| --- | --- | --- |
| Static proof gate | VK and public-statement commitment | Proof for that statement |
| Committed body plus context | VK and body commitment | Context scalar for one group input OutPoint and output 0 Cell/data |
| Fully dynamic statement | Depends on explicit profile/identity policy | Selected old/new Cells, action and transaction/application context |

Her bound-lock context is
`blake2b_ckb(input_outpoint || blake2b_ckb(output0_cell || output0_data))[..31] || 0x00`.
This covers those selected objects; it is not whole-transaction binding. Her
reported mutation tests and direct-linked build/cycle measurements remain
**reported**, not independently reproduced here. Her no-Spawn-yet qualification
belongs to that response and implementation, not Arthur's later work.

Arthur's September 27 response tentatively targets CellScript 0.32, one exact
verifier profile, explicit VK/codec identities, a context envelope, and actual
Spawn/IPC measurements. His October 4 update **reports** creation, two updates
and a tested replay rejection on a local CKB node, using a real secret-knowledge
counter, pinned VK and single-party setup, without public deployment. We did not
run CellScript's node suite or reproduce its resource measurements.

## Pinned CellScript source comparison

All comparisons use [revision 35bf983db30aae80281f97e30bbce08a878d7c58](https://github.com/CellScript-Labs/CellScript/tree/35bf983db30aae80281f97e30bbce08a878d7c58).
Arthur's forum link itself points to an earlier `6616384b...` revision; it should
not be mistaken for this later comparison snapshot. The requested `script/src/main.rs`
is relative to `contracts/zk-private-counter/`, not repository root.

| Responsibility | CellScript source inspected | noir-ckb responsibility / implication |
| --- | --- | --- |
| Circuit | `contracts/zk-private-counter/src/lib.rs`: Rust/arkworks BN254 Groth16, knowledge of 32-byte secret, personalized Blake2b owner/state hashes, same owner, exactly +1 without u64 overflow; range/packing constraints for all 15 public limbs | Supported Noir ACIR lowers through our maintained backend; Capsule uses arithmetic placeholders, not that private authorization construction |
| Lifecycle Type | `contracts/zk-private-counter/script/src/main.rs`: Type ID initialization at zero, one group input/output, no burn, owner/Lock/capacity continuity; hash-resolved parent EXEC preserves current Script context | Capsule Type requires an update pair and compares selected statement fields; it does not initialize or authenticate the verifier Lock |
| Parent | `src/codegen/zk.rs`: derives current Script hash, group data hashes, consumed OutPoint and raw transaction hash; checks single group; fixed domain/action/VK from compiled profile | Capsule Type derives seven values and compares the witness statement; no transaction digest |
| Verifier child | `contracts/zk-transition-verifier/src/main.rs`: one inherited read fd, exact 464-byte request, EOF, codec/profile validation, hash-resolved 744-byte VK, duplicate-key rejection and 64-resolved-dep bound; linked pinned verifier-core | Our generic verifier Lock consumes versioned Molecule `input_type` and VK CellDep; no IPC layer |
| Identity | `docs/CELLSCRIPT_ZK_PROFILE.md`, client parent builder and generated parent: exact handle includes verifier profile/ABI/deployment identity; compiled VK commitment; child checks actual key bytes | Our configured Lock args bind Molecule VK bytes; Type continuity does not authenticate intended Lock code. Deployment policy remains undefined |
| Failure propagation | `src/codegen/runtime.rs` Wait helper checks syscall result and child exit byte; parent maps nonzero to 79 and cannot ignore success/failure; child errors 80–83 identify transport/envelope/key/proof locally | Scripts compose through transaction validation, not parent-child return values; tests assert specific script codes |
| Context | `crates/cellscript-artifact-checker/src/zk.rs`: 228-byte statement → 15 scalars via two u128 limbs per hash and u32 outpoint index, no reduction/truncation | Do not copy its schema. Specify our intended envelope before changing ours |
| Clients | Rust `PreparedIncrement` and TS `PreparedCounter` derive final statement, preserve witness fields and reject raw changes after proving; CCC prepares dependencies/fee/change first and signs only afterwards | Adopt finalization/error clarity as future toolkit DX work; existing CLI is an artifact and test workflow, not a wallet transaction builder |

Changing any raw transaction field invalidates the pinned CellScript statement;
Lock witness signatures can be added without changing raw hash. Its tests inspect
post-proof fee/output/since/dependency changes and overwritten proof fields. Node
source tests reuse the previous proof for the successor operation and require
parent 79; the optional CCC path also tests spent-input preflight rejection.
These are distinct replay scenarios, not proof of complete replay protection.
The setup and admission policy remain development-oriented; the profile records
local trust and no MPC/independent erasure proof. It is neither Noir nor a reason
to replace our prover.

Spawn/IPC solves CellScript's concrete separation between a generated parent
and an externally identified verifier executable. Our current two scripts already
compose without that transport. Introducing it now would add fd ownership,
partial-I/O, child identity, failure propagation and VM-resource obligations
without closing our missing context or admission checks. Keep the current
architecture for this bounded work.

## Bounded Battleship recommendation (proposal only)

A first proof demonstration should connect a board commitment and shot coordinate
to one hit/miss bit, and bind the proof to a game ID, player role, turn number,
consumed state and intended successor. Use a specified hiding/binding commitment
with salt and constrained coordinate/response ranges. Prove that the response is
for the committed board; public context comparison alone cannot establish that
application relation. No game or cryptographic construction is implemented here.

A real game additionally needs legal fleet/board validity, immutable board binding,
repeated-shot tracking, alternating turns, player authorization, response deadlines,
timeouts/forfeits, settlement, creation/destruction, unique game identity, value
preservation and recovery rules. Turn and replay-domain labels alone enforce none
of those. Board encodings may exceed the current scalar-only ABI/backend profile;
compatibility must be demonstrated before claiming support.

| Arrangement | Benefit | Work and tradeoff |
| --- | --- | --- |
| Current proof in Lock + binding Type | Reuses validated toolkit path and keeps proof verification separate | Proof possession is the Lock authority; Type must authenticate the intended verifier, define initialization/context and payment rules; ordinary wallet ownership is not automatically composed |
| Proof in application Type + conventional ownership Lock | Separates player spending authority from game-state proof validity; fits normal wallet fee/signature workflows | Application Type must invoke or link verification and own `input_type`; requires new binaries, lifecycle/witness/composition tests and measurements; not achieved by attaching two Types |

Recommendation: preserve the current path as a toolkit regression fixture. For a
future player-owned game, prefer an application Type that enforces proof and game
rules with a conventional ownership Lock, subject to explicit architecture approval.
This does not require Spawn specifically; linked versus spawned verification is a
separate measured design choice. The next authorization should be a single-turn
proof/state demonstration with a reviewed schema, not a complete Battleship game.
