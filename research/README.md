# Research: foundations for the noir-ckb build

Research done 10 and 11 November 2026 to remove unknowns before the build period. The
goal of the build: a developer takes their own Noir circuit to CKB testnet with `noir-ckb`
and gets a generated Type Script that binds each proof to **one exact state transition of
one Cell**, with the tests that show it.

**None of these documents has had an external review.** Each ends with the items a
reviewer must examine. Spike numbers are from the pinned toolchain where marked "pinned";
the rest are from Rust 1.97.0 and are marked.

| Topic | Document | Spike (command in its README) |
| --- | --- | --- |
| R0 Toolkit architecture | [toolkit-architecture.md](toolkit-architecture.md) | [spec reader](spikes/toolkit-architecture/README.md), [placement and public inputs](spikes/toolkit-architecture/placement/README.md) |
| R1 Noir 1.x | [noir-1x.md](noir-1x.md) | [noir-1x](spikes/noir-1x/README.md) |
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
| 3 | Changed fields must be proven, pinned, an effect target or declared free. Being in the context digest is not enough | R0 3.1, 3.10 |
| 4 | The generator emits Rust source per application, Type Scripts only; Lock use cases go to zk-Lock | R0 6.1, 6.2 |
| 5 | The verifier is spawned from a shared Cell by default; linked stays as a build option | R0 6.3 |
| 6 | Buffers are sized from the spec; at most 16 public inputs | R0 4 |
| 7 | Noir 1.0: add a decoder to the backend and keep its runtime; pin one release | R1 4 |
| 8 | Shared state: one Cell with relayer batching, over sharding and over a Cell per note | R2 4 |
| 9 | Many proofs: one randomized batch check per script run | R3 4 |
| 10 | Single proofs: verify with one pairing product (proposed upstream) | R3 11 |
| 11 | Browser: the pinned backend as wasm for the witness, snarkjs for the proof; CCC where a signature is needed; voters need no wallet | R4 4, 5 |
| 12 | Grant deliverable: the ballot box on the generator, VoteSecure as first consumer, with Battleship as the single-writer reference. The shielded pool is specified and costed for a later phase | R0 3.11, R2 |

## Measured numbers

| Quantity | Value | Toolchain |
| --- | --- | --- |
| Spec reader against recorded CKB-VM cases | tally 49/49 (two runs), counter 48/48; 12/12 unsafe specs refused | n/a |
| One verification, `groth16-ckb` benchmark, 1 / 64 public inputs | 99.8M / 118.5M cycles | pinned |
| The same with single-product verification | 79.2M / 97.8M (20.66M saved) | pinned |
| Recorded tally update, whole transaction | 115.6M | pinned |
| Same proof through three different binaries | 108.5M, 114.9M, 115.6M (spread unexplained) | pinned |
| Cost of one more public input, small / full-width value | 0.28M / 2.82M | 1.97.0 |
| Spawned verifier against linked | +144,943 cycles (0.13%); thin script 31,888 bytes against 103,560 | pinned |
| Fee inputs left open | recorded proof accepted with another payer and with extra inputs; successor change rejected | pinned |
| Batch verification | 79M + 19.9M per proof; 172 proofs in one block; 30 one by one | pinned |
| Nullifier absent-then-insert, script side | 0.93M to 1.28M cycles | pinned |
| Poseidon2 permutation, script side | 412,000 cycles | pinned |
| Tree append, depth 20, one leaf / 64 leaves | 8.27M / 0.54M per leaf | pinned |
| Merkle membership, depth 16 / 20 / 32 | 11,459 / 14,323 / 22,915 constraints | pinned Nargo and backend |
| Join-split 2-in 2-out, depth 20 / 32 | 37,862 / 55,046 constraints | pinned Nargo and backend |
| Tally under Noir 1.0.0-rc.7 with the backend patch | frozen ceremony R1CS byte for byte; ceremony-key proof verified | backend built with 1.97.0 |
| Browser proof, private tally | 0.12 s laptop; 1.8 s (first 2.7 s) entry-level phone; 0.76 s 2-core server | pinned build on the laptop |
| Browser proof, vote-sized / join-split depth 32 | 3.9 s / 9.8 s on the server only | 1.97.0 |

## The targets set at the start, and how close

| Target | Result |
| --- | --- |
| Noir circuit to testnet in 15 minutes | Not measurable yet: the tool is not built. It is the acceptance test of milestone 7 |
| 100+ proof checks per block | 172 for verification alone (pinned). About 160 complete ballots per block is an estimate from measured parts, not an end-to-end run |
| Browser proof under 10 s | Met for the tally on every device. A vote-sized proof on the entry-level phone is estimated at 9 to 10 s and is not measured |
| Generated scripts pass an adversarial matrix nobody wrote by hand | Not built. The operators are defined and reproduce all 49 hand-written tally cases; the linter refused 12 unsafe specs, 3 of which earlier versions accepted |

## Beliefs tested

| Belief | Result |
| --- | --- |
| "Verification costs about 117M cycles regardless of circuit size" | Broke: 79M to 186M depending on public inputs and on the verifier |
| "The binding leaves fee inputs open so any relayer can pay safely" | Held for the tally in an experiment; for generated scripts it depends on the linter |
| "The backend only needs small changes for Noir 1.x" | Held for the deployed circuits; broke for circuits with arrays, whose R1CS changes |
| "Binds each proof to one exact transaction" | Broke as worded; reworded |

## Risks, most serious first

| Risk | State |
| --- | --- |
| No external review of any design; the linter is the trusted part of the generator | Review prompts prepared; findings to be recorded in each document's last section |
| The note scheme and the script-side Poseidon2 port are unreviewed drafts; the port was checked against one vector | Required milestones in R2; not needed for the ballot box's nullifier set, needed for the pool |
| Batch soundness rests on a challenge derivation written in a spike | Spelled out with line numbers in R3 section 12 |
| Relayers can be made to waste work by invalid or conflicting submissions | Rule written in R3 section 12; not built |
| Shared mode, batching and effects exist only as specifications and spikes | Milestone 5 |
| Vote-sized proving on low-end phones is at the edge of the target | Measure before claiming; fallbacks listed in R4 |
| The same proof costs 108.5M to 115.6M cycles in different binaries for an unknown reason | Budgets carry a range |
| Noir 1.0.0 final did not exist; results are for release candidates | Repeat R1's spike on the final release |
| Spawned verifier measured in ckb-testtool only | One testnet transaction in milestone 2 |

## Grant milestone plan

Every milestone ends with something a judge can run. "Local" means a throwaway chain on
the judge's machine, as `try-the-counter` does today.

| # | Milestone | Demo a judge can run | Depends on |
| --- | --- | --- | --- |
| 1 | **Generator core.** Specs in, Type Script crate and test matrix out, for the two deployed applications | `noir-ckb test` on the counter and tally specs: the generated scripts give the recorded verdict on all 97 recorded cases, and every removed check is caught by a named test | R0 M2, M3 |
| 2 | **Cheaper verification.** Single-product verifier and a shared spawned verifier on testnet | A testnet explorer link to a transaction verified through the shared verifier; `placement/run.sh` reproduces the cycle table locally | R0 M1, R3 T2 |
| 3 | **Noir 1.0.** One named release supported next to beta.18 | `noir-ckb build` on a 1.0 copy of the tally prints the ceremony's R1CS hash; its proof is accepted by the tally already deployed on testnet | R1 N1 to N4 |
| 4 | **Battleship.** Generated from its spec | Two browser windows play a full game on testnet; a second game is abandoned and the timeout pays the opponent | R0 M4, M5; R5 |
| 5 | **Ballot box.** Shared mode, effects and batch verification in the generator | Local: one command casts 100 ballots in one transaction, then shows a second vote with a used nullifier rejected and two ballots proved against the same state both landing. Testnet: the judge is added to a voter list and votes | R0 M7; R2 S1 to S3; R3 T3 to T5 |
| 6 | **Vote from a phone.** Browser proving with no wallet, through a relayer | The judge opens a page on their phone, votes in the testnet election, and sees the proof time and the transaction | R4 B1 to B3 |
| 7 | **First-user path.** `noir-ckb new`, `check`, `build`, `test`, `prove`, `deploy`, one page of documentation | The judge follows the page with their own small circuit from `noir-ckb new` to a testnet transaction, with a timer; target 15 minutes | all above |
| 8 | **Review.** Findings from an outside reviewer on the binding and the batch check, each with a response and a regression test | The findings document; `noir-ckb test` includes the regression cases | 1, 5 |

VoteSecure integration is the first use of milestone 5 outside this repository and is not
a milestone of its own, because its schedule is not controlled here.
