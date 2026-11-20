# Research: foundations for the noir-ckb build

Research done 10 and 11 November 2026 to remove unknowns before the build period. The
goal of the build: a developer takes their own Noir circuit to CKB testnet with `noir-ckb`
and gets a generated Type Script that binds each proof to **one exact state transition of
one Cell**, with the tests that show it.

**External review so far:** R0 to R4 were each reviewed once by an outside model (11 to
18 November 2026). The findings (12, 8, 13, 7 and 12, all accepted) and the responses are
in the last section of each document; R5 lists three Battleship items that stay open and
R2 lists ten open items. The corrections made after each
review have not been reviewed again. Spike numbers are from the pinned toolchain where marked "pinned";
the rest are from Rust 1.97.0 and are marked.

| Topic | Document | Spike (command in its README) |
| --- | --- | --- |
| R0 Toolkit architecture | [toolkit-architecture.md](toolkit-architecture.md) | [spec reader](spikes/toolkit-architecture/README.md), [placement and public inputs](spikes/toolkit-architecture/placement/README.md) |
| R1 Noir 1.x: decoder bridge for release candidates | [noir-1x.md](noir-1x.md) | [noir-1x](spikes/noir-1x/README.md) |
| R2 Shielded notes | [shielded-notes.md](shielded-notes.md) | [shielded-notes](spikes/shielded-notes/README.md) |
| R3 Throughput | [throughput.md](throughput.md) | [throughput](spikes/throughput/README.md) |
| R4 Browser | [browser.md](browser.md) | [browser](spikes/browser/README.md) |
| R5 Battleship | [battleship.md](battleship.md) | none (design only) |
| Upstream proposal | [groth16-ckb single-product verification](upstream/groth16-ckb-single-product/README.md) | patch and tests |

## Decisions

| # | Decision | Where |
| --- | --- | --- |
| 1 | The claim is "one exact state transition of one Cell". Whole-transaction binding is an opt-in context item (`tx_hash`) | R0 3.6 |
| 2 | Noir is the rule language. No Rust hooks. Proof-less actions get three declarative checks: equality with a constant, comparison with a constant, field from field | R0 3.1, 3.4 |
| 3 | Every changed property of the Cell (data field, Lock, capacity) must be proven, pinned by an anchored equality or the Lock rule, an effect target, or declared free and committed in the context. Being in the context digest is not enough. Widened from data fields to all properties after the external review | R0 3.1, 3.10, 13 |
| 4 | The generator emits Rust source per application, Type Scripts only; Lock use cases go to zk-Lock | R0 6.1, 6.2 |
| 5 | New applications spawn the verifier from a shared Cell and are deployed under `data2`; the two deployed `data1` applications stay linked. The parent-to-child interface is specified and not yet run | R0 6.3 |
| 6 | Buffers are sized from the Molecule schema plus a declared allowance for other witness fields; at most 16 public inputs | R0 4 |
| 13 | `signer` exempts a creation from the binding rules only under a Lock rule that pins the code and declares that it signs the transaction. Named payout outputs have no Type and empty data unless the spec says otherwise | R0 3.4, 13 |
| 14 | Generated tests show that a script does what its spec says. Whether the spec says enough is tested by developer-written application properties and circuit relation tests, which the toolkit runs and cannot generate | R0 8 |
| 7 | Noir: the spike patch is a decoder bridge for one named release candidate and a validated instruction set, and is called that. Noir 1.x support is separate work: one pinned compiler/runtime pair with differential tests | R1 4, 10, 12 |
| 8 | Shared state: one Cell with relayer batching, over sharding and over a Cell per note | R2 4 |
| 9 | Many proofs: one randomized batch check per script run | R3 4 |
| 10 | Single proofs: verify with one pairing product (proposed upstream) | R3 11 |
| 11 | Browser: the pinned backend as wasm for the witness, snarkjs for the proof; CCC where a signature is needed; voters need no wallet | R4 4, 5 |
| 15 | The ballot box script pins the empty nullifier set and zero totals at creation and bounds the vote choice to 0 or 1 itself. It claims one vote per enrolled secret and membership; it does not claim that omitted ballots are detectable | R2 11 |
| 12 | Grant deliverable: the ballot box on the generator, VoteSecure as first consumer, with Battleship as the single-writer reference. The shielded pool is specified and costed for a later phase | R0 3.11, R2 |

## Measured numbers

| Quantity | Value | Toolchain |
| --- | --- | --- |
| Spec reader against recorded CKB-VM cases, pre-pairing agreement on the recorded subset | tally 49/49 (two runs), counter 48/48 | n/a |
| Unsafe or malformed specs refused by the linter for the expected reason | 29 of 29; the external review found five holes the first 12 cases had missed | n/a |
| One verification, `groth16-ckb` benchmark, 1 / 64 public inputs | 99.8M / 118.5M cycles | pinned |
| The same with single-product verification | 79.2M / 97.8M (20.66M saved) | pinned |
| Recorded tally update, whole transaction | 115.6M | pinned |
| Same proof through three different binaries | 108.5M, 114.9M, 115.6M (spread unexplained) | pinned |
| Cost of one more public input, small / full-width value | 0.28M / 2.82M | 1.97.0 |
| Spawned verifier against linked | +144,943 cycles (0.13%); thin script 31,888 bytes against 103,560 | pinned |
| Fee inputs left open | recorded proof accepted with another payer and with extra inputs; successor change rejected | pinned |
| Batch verification | 79M + 19.9M per proof; 172 repeated proof checks under 3.5B cycles in a script-only VM fixture (173 and 174 not run); 30 one by one | pinned, script before the review changes |
| Batch rejection | 18 size-sweep rejections with exit code 51 after an accepted control; 39 of 39 adversarial cases as expected | 1.97.0, after the review |
| `v1` envelope overhead | 25 bytes plus one per named output (an earlier figure of 12 was wrong); a `v1` witness is 527 bytes at 10 public inputs | computed |
| Nullifier absent-then-insert, script side | 0.93M to 1.28M cycles | pinned |
| Poseidon2 permutation, script side | 412,000 cycles | pinned |
| Tree append, depth 20, one leaf / 64 leaves | 8.27M / 0.54M per leaf | pinned |
| Merkle membership, depth 16 / 20 / 32 | 11,459 / 14,323 / 22,915 constraints | pinned Nargo and backend |
| Ballot vote circuit, depth 20 | 16,971 constraints, 16,993 wires, 7 public inputs; 716 per tree level plus 2,651; powers of tau 2^15 | pinned Nargo; backend at the pinned revision built with 1.97.0 |
| Join-split 2-in 2-out, depth 20 / 32 | 37,862 / 55,046 constraints | pinned Nargo and backend |
| Tally compiled with Noir 1.0.0-rc.7, read through the decoder bridge | frozen ceremony R1CS byte for byte; ceremony-key proof verified. One circuit; not evidence of Noir 1.x support | backend built with 1.97.0 |
| Browser proof, private tally | 0.12 s laptop; 1.8 s (first 2.7 s) entry-level phone; 0.76 s 2-core server | pinned build on the laptop |
| Browser proof, vote-sized / join-split depth 32 | 3.9 s / 9.8 s on the server only (11 November); 3.6 s / 8.3 s in a rerun of 18 November with every witness compared and every proof verified | 1.97.0 |

## The targets set at the start, and how close

| Target | Result |
| --- | --- |
| Noir circuit to testnet in 15 minutes | Not measurable yet: the tool is not built. It is the acceptance test of milestone 8 |
| 100+ proof checks per block | 172 repeated proof checks in a script-only VM fixture (pinned), not a relayable transaction. Complete ballots per block are not measured: 160 is the upper bound of a model that leaves 281,250 cycles per ballot for everything it omits; 100 leaves 14.3M per ballot and is the planning figure |
| Browser proof under 10 s | Met for the tally on every device. A vote-sized proof on the entry-level phone is not measured; two unvalidated extrapolations from the tally give about 9.4 s for a median proof and about 11.4 s for a first proof, which is the one a voter makes |
| Generated scripts pass an adversarial matrix nobody wrote by hand | Not built. The operators are defined and reproduce all 49 hand-written tally cases; the linter refused 29 unsafe specs, of which earlier versions accepted 3 and the version before the external review accepted further ones |

## Beliefs tested

| Belief | Result |
| --- | --- |
| "Verification costs about 117M cycles regardless of circuit size" | Broke: 79M to 186M depending on public inputs and on the verifier |
| "The binding leaves fee inputs open so any relayer can pay safely" | Held for the tally in an experiment; for generated scripts it depends on the linter |
| "The backend only needs small changes for Noir 1.x" | Held only for reading the deployed circuits' artifacts. Broke for circuits with arrays, whose R1CS changes, and broke in review: the backend's beta.19 VM executes some rc Brillig instructions differently, and the bridge admitted them |
| "A wrong witness is refused before proving" | Broke: the check guarantees that the witness satisfies the R1CS, not that an unconstrained value is the intended one |
| "The ballot box needs only the nullifier set and the generator" | Broke: it also needed a ballot circuit (written on 15 November 2026, not reviewed), and still needs a setup of its own, a defined rule for several effects in one transaction, and an upstream dependency issue resolved |
| "Binds each proof to one exact transaction" | Broke as worded; reworded |

## Risks, most serious first

| Risk | State |
| --- | --- |
| The linter is the trusted part of the generator, and the first external review found five holes in it that its own negative tests had missed | R0 to R4 reviewed and corrected. The corrected linter has not been reviewed again |
| A soundness issue in an upstream dependency, reported privately; the ballot box and shielded pool must not rely on multi-key SMT proofs until it is resolved | Prerequisite of milestone 6 (R2 S2b). No ballot box or pool deployment before it is resolved |
| The ballot vote circuit is unreviewed, was run with a throwaway key only, and at 16,971 constraints needs a powers-of-tau file of power 15 at depth 20; depth 19 was chosen, which needs power 14. The tally's power-12 file holds an electorate of four | Review, a rerun at depth 19 and a new setup before milestone 6 (R2 S2a) |
| A relayer or miner can leave ballots out, and closing makes that final | Stated as an assumption; no detection is claimed |
| The decoder bridge admits Brillig that the backend's VM executes differently, and several of its fail-closed claims did not hold | Bridge restricted to a validated instruction set (R1 N2); Noir 1.x support moved to its own milestone |
| A spec can lack a rule the application needs; generated tests cannot see that | Application properties and circuit relation tests written by the developer (R0 section 8); a limit of the approach, not a solved problem |
| Battleship: payout exclusivity, the timeout as a race, and the first-turn sentinel are undecided | Open items in R5 |
| The note scheme has open defects from review (nullifier scope, dummy inputs, tags, full tree, pool creation) and the script-side Poseidon2 port was checked against one vector | Ten open items in R2 section 11; needed for the pool, not for the ballot box |
| Batch soundness rests on a challenge derivation written in a spike | Reviewed without a finding on the equation, transcript or chunking; key validation and a bound on N were missing and were added. Soundness is about Q/2^128 for a prover who tries Q candidate batches |
| The batch script changed after the pinned measurements | Rerun `spikes/throughput/run.sh` on the pinned toolchain |
| Relayers can be made to waste work by invalid or conflicting submissions, and a batch can fail with every proof valid when the shared Cell was spent first | Rule rewritten in R3 section 12 with a failure classification; not built |
| Shared mode, batching and effects exist only as specifications and spikes | Milestone 6 |
| Vote-sized proving on low-end phones may miss the target: the first-proof extrapolation is about 11.4 s | Measure on the phone, with memory, before claiming (R4 B1); fallbacks listed in R4 |
| The browser page pins no hashes, and relayers see each voter's IP address, timing, nullifier and choice and can delay a ballot past `close` | R4 sections 4 and 10; timely inclusion is an assumption |
| The same proof costs 108.5M to 115.6M cycles in different binaries for an unknown reason | Budgets carry a range |
| Noir 1.0.0 final did not exist; results are for release candidates | A final release is a new pin and a new acceptance run (milestone 4), not covered by the bridge |
| Several R1 statements had no archived evidence | Marked as observed, not archived; the acceptance run in R1 N1 archives everything it cites |
| Spawned verifier measured in ckb-testtool only, with a spike interface that is not the generator's | One testnet transaction and four interface tests in milestone 2 |

## Grant milestone plan

Every milestone ends with something a judge can run. "Local" means a throwaway chain on
the judge's machine, as `try-the-counter` does today.

| # | Milestone | Demo a judge can run | Depends on |
| --- | --- | --- | --- |
| 1 | **Generator core.** Specs in, Type Script crate and test matrix out, for the two deployed applications | `noir-ckb test` on the counter and tally specs: the generated scripts give the recorded verdict on all 97 recorded cases, and every removed check is caught by a named test | R0 M2, M3 |
| 2 | **Cheaper verification.** Single-product verifier and a shared spawned verifier on testnet | A testnet explorer link to a transaction verified through the shared verifier; `placement/run.sh` reproduces the cycle table locally | R0 M1, R3 T2 |
| 3 | **Release-candidate bridge.** The backend reads artifacts of one named Noir release candidate, for a validated instruction set, next to beta.18. Not Noir 1.x support | `noir-ckb build` on a copy of the tally for that compiler prints the ceremony's R1CS hash and its proof is accepted by the tally already deployed on testnet; a run over the refusal list (other formats, relabelled artifacts, unlisted Brillig instructions, several functions) exits non-zero on any deviation | R1 N1 to N4 |
| 4 | **Noir 1.x.** One pinned compiler and its matching runtime (the final 1.0.0 if it exists), with differential tests of every admitted instruction against Noir's own execution | A circuit with integers, shifts and an unconstrained hint, not written for the test, gives the same witness as `nargo execute`; the documentation names the supported pair | R1 N6; 3 |
| 5 | **Battleship.** Generated from its spec | Two browser windows play a full game on testnet; a second game is abandoned and the timeout pays the opponent | R0 M4, M5; R5 open items |
| 6 | **Ballot box.** Shared mode, effects and batch verification in the generator. Prerequisites, each with its own test: (a) the ballot circuit (membership, election-scoped nullifier, binary choice): written and tested with a throwaway key, see `circuits/ballot`; review, depth decision and setup outstanding; (b) the upstream SMT dependency issue resolved, or nullifier-set updates that do not rely on multi-key proofs; (c) the spec fixes: empty set and zero totals pinned at creation (done), choice bounded in the script (done), a composition rule for several effects in one transaction | Local: one command casts 100 ballots in one transaction, then shows a second vote with a used nullifier rejected (also inside one batch), a ballot with choice 2 rejected, a box opened with a non-empty set rejected, and two ballots proved against the same state both landing; the cycles per complete ballot are printed. Testnet: the judge is added to a voter list and votes | R0 M7; R2 S2a, S2b, S3; R3 T3 to T5 |
| 7 | **Vote from a phone.** Browser proving with no wallet, through a relayer | The judge opens a page on their phone, votes in the testnet election, and sees the proof time and the transaction | R4 B1 to B3; 6 |
| 8 | **First-user path.** `noir-ckb new`, `check`, `build`, `test`, `prove`, `deploy`, one page of documentation | The judge follows the page with their own small circuit from `noir-ckb new` to a testnet transaction, with a timer; target 15 minutes | all above |
| 9 | **Review.** Findings from an outside reviewer on the binding, the batch check and the corrected linter, each with a response and a regression test | The findings document; `noir-ckb test` includes the regression cases | 1, 6 |

VoteSecure integration is the first use of milestone 6 outside this repository and is not
a milestone of its own, because its schedule is not controlled here.
