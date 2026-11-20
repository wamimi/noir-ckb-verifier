# R4. Proving in a browser, and signing

Status: **spiked; the private tally measured on a laptop, an entry-level phone and a server, the larger circuits on the server only; one external review recorded in section 11.** Spike code and exact
command: [`spikes/browser`](spikes/browser/README.md).

## 1. Problem and definition of done

A voter or a player should not have to install Nargo, a Rust toolchain and snarkjs. The
private inputs must also never leave their device (private tally spec, section 9). Both
point to proving in the browser. The target was a proof in under 10 seconds.

| # | Test | State |
| --- | --- | --- |
| D1 | The pinned backend compiled to wasm32 solves a witness in a browser, byte-identical to the native backend's | Passed (spike), four circuits, one fixed input set each, every run checked (18 November). Boundary and malformed inputs not tested (section 8) |
| D2 | A Groth16 proof made in the browser from that witness verifies | Passed (spike), four circuits, every proof verified and an altered public input rejected (18 November). The 11 November run verified only the last proof of each series |
| D3 | Time per proof under 10 s for the grant's circuits | Private tally: 0.12 s on a laptop, 1.8 s on an entry-level phone (first proof 2.7 s). Vote-sized and join-split circuits: measured on a 2-core server only (3.9 s, 7.5 s, 9.8 s); **not measured on the laptop or the phone** |
| D4 | All circuits on the pinned Rust, on a laptop and a phone, in Chrome, Safari and Firefox | Partly: the private tally on a laptop (Chrome, Brave) and a phone (Chrome), 11 November 2026 |
| D5 | A page that builds a transaction, proves, and hands it to a wallet or a relayer | Not built |

## 2. What was believed, and what the spike found

| Belief or goal | Result |
| --- | --- |
| The backend compiles to wasm32 | **Held with one change outside the backend**: a randomness hook for `getrandom` 0.4.1 (spike). 4.3 MB module, 0.94 MB compressed |
| A browser proof takes under 10 seconds | **Held for the private tally on every device** (0.12 s laptop, 1.8 s entry-level phone, 2.7 s for its first proof). For the larger circuits, on the server only: proving alone took 3.8 to 4.0 s (vote-sized) and 9.7 to 10.0 s (depth-32 join-split) on 11 November; with witness solving, the slowest depth-32 run took 10.24 s (265.8 ms + 9,975.4 ms), over the target. On the phone a vote-sized proof was not measured; the two extrapolations in section 6 give about 9.4 s for a median proof and about 11.4 s for a first proof. Neither is validated |
| Witness solving is the slow part | **Broke**: 10 to 300 ms on the server, 247 ms (median) on the phone for the tally. Proving was 88% of witness-plus-proving time on the phone (medians) and 96% to 98% on the laptop and the server |
| The in-browser witness is the same as the native one | **Held** for one fixed input set per circuit: byte-identical for all four circuits, in every run of 18 November |
| Download size is negligible | **Broke for the larger circuits**: the proving key is 1.8 MB for the tally, 9.9 MB for a vote-sized circuit and 21 to 29 MB for a join-split, and compresses by only about 30% |

## 3. Prior art

- [snarkjs](https://github.com/iden3/snarkjs) 0.7.5: Groth16 proving in JavaScript and
  WebAssembly with worker threads; the prover used here and in every script of this
  repository.
- [zk-Lock](https://github.com/CECILIA-MULANDI/zk-lock/tree/d09d768890455f8f5a568d8468ef22a8b18a81cc):
  its README describes a live demo in which the browser builds a Circom proof and spends a
  testnet Cell with no wallet. The same no-wallet shape applies to proof-authorized Cells
  here.
- Noir's own browser path (`noir_js` with the Barretenberg backend) produces UltraHonk
  proofs, not Groth16, and cannot be used with the CKB verifier. From memory; not re-read.
- [CCC](https://github.com/ckb-devrel/ccc/tree/0961763da4a81c954e156a27c581aed0aeca9761),
  the CKB wallet connector library (section 5).

## 4. Options and the chosen design

**Witness solving**

| Option | Result | Verdict |
| --- | --- | --- |
| A. The pinned backend as a wasm32 module (the spike) | Same code as the native path, so the R1CS wire order cannot drift; 4.3 MB | **Chosen** |
| B. Noir's `noir_js` to execute ACIR, then a JavaScript port of the backend's wire mapping | Smaller download; a second implementation of the part where the Week 8 public-input fault lived | Rejected |
| C. Solve on a server | Private inputs leave the device | Rejected by the tally spec |

**Proving**

| Option | Result | Verdict |
| --- | --- | --- |
| A. snarkjs in the page | Measured; no new code | **Chosen** |
| B. A Rust prover (arkworks) compiled to wasm with threads | Possibly faster; needs cross-origin isolation headers for threads and a `.zkey` reader; not measured | Later, only if D4 shows phones miss the target |
| C. A hosted prover | Private inputs leave the device | Rejected |

**Delivery.** A static bundle: the page, the backend module (shared by every circuit),
snarkjs, and per circuit the artifact, the proving key and the verification key.

The spike checks no hashes. Its page uses whatever the server sends, and its manifest lists
only circuit names and constraint counts. What a real loader must do:

- Pin by hash every file that can change what is proved or what happens to the inputs: the
  page's HTML and JavaScript, snarkjs and its worker code, the backend wasm module, and per
  circuit the artifact, the proving key and the verification key.
- Take the expected hashes from a manifest that is authenticated independently of the
  server that delivers the bundle: a release signing key, or a bundle digest published
  somewhere else the user already trusts. A manifest served next to the files proves
  nothing: a mutually consistent substitute bundle with its own manifest passes every check
  that trusts the served manifest. The loader that performs the checks is part of what has
  to be authenticated.
- Tie the release to the audited circuit source and R1CS, the setup transcript, the order of
  the public inputs, and the verification key hash that the deployed Type Script pins.

Hash-checked files fix the statement the user proves. They do not bind the proof to a
transaction. That binding comes from the Type Script, which rebuilds the public inputs from
the transaction it is verifying and compares them with the proof's before it verifies
(private tally spec, section 5). The spike's tally fixture uses `ctx_lo = 5` and
`ctx_hi = 7`, which belong to no transaction: the page shows only that a proof verifies
against its own public inputs.

## 5. Signing and wallets

Who has to sign depends on the Lock, not on the proof.

| Application | Who signs | Wallet needed by the user |
| --- | --- | --- |
| Ballot box (guard Lock, proof is the authority, relayer pays) | Only the relayer, for its fee Cell | **None.** The voter's browser makes the proof and posts it to a relayer. A wallet would add a public fee payer and a link to the voter |
| Private tally, Battleship turns | Whoever pays the fee | None if a relayer pays; otherwise any wallet for the fee input |
| Battleship open and join (stake) | The player funding the stake | Yes |
| Owned counter | The owner (secp256k1 Lock on the Cell) | Yes |

What a signature covers matters for the order of steps. The system secp256k1 Lock signs
the transaction hash, every witness of its own input group (the whole `WitnessArgs` of the
first one, with only its `lock` field zeroed), and every witness whose index is at or
beyond the number of inputs (source: `ckb-system-scripts`,
`c/secp256k1_blake160_sighash_all.c`, header comment). It rejects witnesses over 32,768
bytes among those it reads. Consequences:

- A proof in `input_type` of the application input's witness can be attached before or
  after a fee payer signs **only if the application input is outside every fee signer's
  Lock group.** If the application Cell and a fee Cell use the same secp256k1 Lock (same code
  hash, hash type and args), the application input's witness is the first witness of the
  signer's group: the signature covers it, a later change to its `input_type` invalidates the
  signature, and a large application witness meets the 32,768-byte limit. The private tally
  and the ballot box keep the application Cell under the guard Lock, so the application
  input is in a group of its own and meets the condition. An application Cell under a
  user's secp256k1 Lock (the owned counter) does not: there the proof is attached before
  signing.
- A proof in `output_type` at an index that is also one of the signer's inputs (a creation
  funded by input 0, application output 0) **is** covered: prove first, sign second.
- A batch payload (R3: 50 KB for 172 proofs) must sit in the witness of an application
  input that is in no fee signer's Lock group (a guard-Lock input), never in a witness the
  fee payer's Lock reads, or the 32 KB limit rejects it. Application and node size limits
  still apply.

Library survey:

| Library | What it is | Fit |
| --- | --- | --- |
| [CCC](https://github.com/ckb-devrel/ccc) (`@ckb-ccc/*`) | Current CKB connector and transaction library. One `Signer` interface (`prepareTransaction`, `signOnlyTransaction`, `signTransaction`, `sendTransaction`) over packages for JoyID, OKX, UniSat, UTXO Global, Xverse, Rei, Nostr (NIP-07) and EVM wallets (EIP-6963); fee completion helpers | **Chosen** for any flow that needs a signature, with the check below. `signOnlyTransaction` is the entry point to use after explicit preparation, because it skips CCC's own `prepareTransaction` step; it does not guarantee that the wallet returns the transaction unchanged |
| [Lumos](https://github.com/ckb-js/lumos) | The earlier JavaScript framework; CCC ships patches for interoperating with it | Not for new code |
| [JoyID SDK](https://github.com/nervina-labs/joyid-sdk-js) | Passkey wallet SDK; reachable through CCC | Through CCC |
| `ckb-cli` | Command-line signing, used by this repository's scripts | Stays for the developer path |

**Accepting a signed transaction.** The base `Signer` class performs no comparison, and
the UTXO Global and JoyID adapters return the transaction the wallet sent back (CCC
`0961763`; JoyID's signing path also prepares witnesses). So the client keeps a snapshot of
the transaction before signing and, before accepting the result, compares every raw
transaction field (version, cell deps, header deps, inputs, outputs, outputs data) and every
witness byte other than the signer's own signature field with the snapshot. Any difference
is a refusal.

**Open incompatibility: JoyID subkeys.** A JoyID account that signs with a subkey uses the
`output_type` field of the first witness of its Lock group for the subkey's unlock entry (CCC
`packages/joy-id/src/ckb/index.ts`, `prepareTransactionForSubKey`). A creation proof in
`output_type` of the same witness (a fee input at index 0 and the application output at
index 0) competes for that field: when it is already filled, the adapter skips the subkey
entry; when the subkey entry is prepared first, it occupies the field the proof needs.
Read in the adapter's source by the external review, not executed. To be tested with a
root-key and a subkey account separately (test plan item 5); until then this wallet,
account type and witness layout are treated as incompatible, and a creation flow uses a
layout where the application output's index is not a JoyID fee input's index.

Not verified in this spike: that each wallet behind CCC signs a transaction containing an
unknown Type Script and extra witness fields without rewriting it. That is test D5. JoyID
and UTXO Global send the whole transaction to wallet-controlled code, so only a test per
wallet and version can show what they accept. The EVM adapter has the wallet sign a derived
message and sets the Lock itself, so an EVM wallet never interprets the CKB transaction.
There is no basis yet for naming a wallet that refuses unknown Type Scripts.

## 6. Measured budgets

Private tally v2 (3,338 constraints, ceremony key, 1.8 MB key file). On every device the
last witness of each series was identical to the native backend's and the last proof
verified (11 November; the earlier runs of those series were not checked). The server
was rerun on 18 November with every run checked (below):

| Device | Chip, memory | OS, browser | Threads | Witness, median | Prove, first | Prove, median |
| --- | --- | --- | --- | --- | --- | --- |
| MacBook Pro | Apple Silicon | macOS; Chrome and Brave | 12 | 5 ms | 203 ms | 115 ms |
| Infinix Smart 8 (X6525), entry-level phone | Unisoc T606 (2 × Cortex-A75 + 6 × Cortex-A55), 3 GB | Android 13 (XOS 13.0); Chrome 157.0.8103.50 | 8 | 247 ms | 2,651 ms | 1,813 ms |
| Cloud server | 2 cores of an Intel Xeon at 2.1 GHz, 7 GB | Linux; headless Chromium 153 | 2 | 12 ms | 920 ms | 761 ms |

The phone is the low-end reference point. Its first proof is slower than later ones
(2.7 s against 1.8 s); a voter makes one proof, so the first-proof figure is the one that
counts.

The phone took 5,343 ms to fetch, compile and instantiate the 4.3 MB backend module,
fetched over Wi-Fi from the laptop serving the page (73 ms on the laptop itself, 60 ms on
the server, both fetching from localhost). These three figures cover fetching, compiling
and instantiating together; the page of 11 November did not separate them. The server
rerun of 18 November did: fetch 49 ms, compile 16 ms, instantiate under 1 ms, from
localhost. Chromium compiles WebAssembly lazily, so part of the compilation falls into the
first witness solve (62 ms on the server against 14 to 15 ms afterwards). On the phone the
5.3 s was mostly a first-visit cost of downloading and compiling the module, not a
per-proof cost: a real application caches the module (HTTP cache or a service worker), and
later visits skip the download.

Larger circuits, **measured on the cloud server only** (three runs each, spike). They were
not run on the laptop or the phone. Both phone extrapolations below are separate
estimates, neither has been checked against a phone, and neither includes witness solving.
Circuit size, worker start-up, memory allocation, heat and memory pressure can each change
the ratio, so they do not show that a first ballot on that phone is near the 10 s target:

| Item | Value | Basis |
| --- | --- | --- |
| Prove, vote-sized (17,483 constraints) | 3.8 to 4.0 s (11 November); 3.6 s (18 November) | spike, server |
| Prove, join-split depth 20 / 32 | 7.5 to 7.7 s / 9.7 to 10.0 s (11 November); 6.5 to 6.9 s / 8.1 to 8.4 s (18 November) | spike, server |
| Witness solving | 71 to 305 ms | spike, server |
| Witness solving plus proving, depth-32 join-split, slowest run | 10.24 s (265.8 ms + 9,975.4 ms, 11 November), over the target | spike, server |
| The same on the entry-level phone, warm | about 9.4 s (vote-sized), 17.9 s and 23.2 s (join-splits) for a median proof | **unvalidated extrapolation**: server median × 2.38, the ratio of the tally's median proofs (1,813 ms phone, 761 ms server, 11 November) |
| The same on the entry-level phone, cold | about 11.4 s (vote-sized), 21.5 s and 28.0 s (join-splits) for a first proof | **unvalidated extrapolation**: server first proof × 2.88, the ratio of the tally's first proofs (2,651 ms phone, 920 ms server, 11 November). A voter makes one proof, so this is the figure that counts; it is over the target |
| Phone memory for a join-split | unknown. The depth-32 key is 28.6 MB on disk; snarkjs holds the key, the witness and several working buffers of similar size in memory. On a 3 GB phone this may not fit a browser tab | not measured |
| First-visit download for a ballot | about 8 MB if served compressed (key 6.9, backend 0.94, snarkjs 0.15) | **estimate**: the sum of the gzip sizes of the files for the vote-sized proxy circuit, computed with gzip. Not a measured page transfer; the spike's server sends files uncompressed |
| Backend module load, from localhost | 60 ms for fetch, compile and instantiate together (11 November); 49 + 16 + under 1 ms (18 November) | spike, server |

On the server, proving time grew roughly linearly: about 0.17 ms per constraint plus about
0.6 s (least-squares fit of the four median times).

To run the larger circuits on a device: `FULL=1 LAN=1 research/spikes/browser/run.sh`, then
open `http://<address>:8765/?only=spend-1-d20` (one circuit per page load, to limit memory).

## 7. Pinned tools

snarkjs 0.7.5; backend `wamimi/Noir-Groth16@828025f` built for `wasm32-unknown-unknown`
with `--cfg getrandom_backend="custom"`; `getrandom` 0.4.1; Nargo 1.0.0-beta.18; CCC at the
version current when D5 is built (surveyed at `0961763`). The spike build used Rust 1.97.0.

## 8. Test plan

1. D4 matrix: the page on the pinned Rust build, on a recent laptop and a mid-range Android
   phone, in Chrome, Safari and Firefox; three runs each; memory recorded.
2. Witness equality with the native backend for every supported circuit and for the
   differential inputs of the circuit test suites, in CI (headless). Not tested yet, and
   needed in addition: writer-level vectors with field values 0, 1 and p − 1 and values that
   cross byte boundaries, read back by an independent parser; inputs that exercise each
   branch and each public/private layout; malformed, negative, non-canonical and
   out-of-range inputs, which the native and wasm paths must refuse alike. Agreement between
   the two paths shows that they serialize the same witness; both run the same backend code,
   so it does not show that the circuit or its wire mapping is correct.
3. Refusals: an artifact, key, module, page script or snarkjs file whose hash differs from
   the manifest; a manifest that fails its independent authentication; a key for another
   circuit; inputs that do not satisfy the circuit (no proof must come out).
4. Secret handling, each part checked on its own, on the success path and on failure paths
   (unsatisfiable inputs, a missing file): no private input in any network request (traffic
   recording); none in `localStorage`, `sessionStorage`, IndexedDB or the Cache Storage
   (inspected after the page finishes); none in console output (captured). A network
   recording alone would pass a page that writes inputs to storage. Not tested yet. The
   spike page serves public test fixtures (`inputs.json`, a full `witness.wtns`) as files
   and does not disable fetch caching, so it is not a model of a client holding real
   secrets.
5. Signing flows (D5) through CCC with at least JoyID and one EVM wallet: fee-only signing
   with the proof attached before and after; creation with the proof inside the signed
   witness.
6. A batch payload over 32 KB next to a secp256k1 fee input is accepted when placed in the
   application witness and rejected when placed in the signer's.

## 9. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| B1 | The vote-sized circuit on the laptop and the entry-level phone (the tally was done on both on 11 November 2026) | Vote-sized proof under 10 s on the phone, with memory recorded |
| B2 | Backend wrapper as a published module with hash-checked loading against an independently authenticated manifest | Test plan items 2 and 3 in CI |
| B3 | Ballot page: build the statement, prove, post to a relayer; no wallet | A vote cast from a phone browser lands on a local chain; test plan item 4 passes (network, storage and console separately) |
| B4 | CCC signing for staked and owned applications | Test plan items 5 and 6 |

## 10. Risks and open questions

| Risk | Handling |
| --- | --- |
| The vote-sized and join-split circuits were measured on one server only; the phone estimate for a vote is at the edge of the 10 s target | Run `?only=spend-1-d20` on the phone (B1) before any claim about ballots; if it misses, use a shallower voter tree or the Rust prover of option B |
| A 7 MB key on a mobile connection | Cache with a service worker; show progress; the ballot circuit can drop to a shallower tree for small electorates |
| The page is the trust base: a served page can exfiltrate secrets or swap the statement | Hash-pinned static bundle whose manifest is authenticated independently of the server (section 4); reproducible build; publish the bundle hash; a self-hosted copy stays possible. Not built: the spike pins nothing |
| A voter without a wallet depends on a relayer | A relayer is not needed for authorization: the proof is the authority and a relayer cannot change a bound ballot. It is still a privacy observer and an availability dependency. It sees the connection's IP address, the time of submission, the nullifier and, since choices are public, the choice; removing the voter's fee input does not remove these. It can drop or delay a ballot, and nothing in the design stops it or makes it visible. The client keeps the submitted ballot, watches for its nullifier on chain, and resubmits through another relayer or a wallet-funded transaction if it does not appear in time. Retrying preserves the right to submit, not the voting window: a ballot held back until after `close` cannot be cast. Timely inclusion is an assumption (R2 section 4, R3 section 12) |
| Worker threads or memory limits differ across browsers | B1; option B for proving if needed |
| `getrandom` custom hook | It forwards to `crypto.getRandomValues` in chunks of at most 65,536 bytes and returns an error code instead of throwing (since 18 November; the first version threw above 65,536 bytes). The page counts calls: 0 for each of the four circuits on 18 November. That covers those four input sets, not every input a circuit accepts |

Open: whether the relayer endpoint is part of the grant deliverable or left to the first
consumer; whether to offer a native prover for users who prefer not to trust a web page.

## 11. External review

One review by an outside model, at commit `206df77`, covering this document, the spike, the
private tally spec, `c/secp256k1_blake160_sighash_all.c` of `ckb-system-scripts` (master) and
CCC at `0961763`. Findings 9 and 6 were partly reproduced (a 65,537-byte request to Web
Crypto; the loop scope of the checks); the rest were read from source or computed from the
published numbers. All twelve findings were accepted.

| # | Severity | Finding | Response |
| --- | --- | --- | --- |
| 1 | High | Hash checking needs a trust root independent of the served manifest, and hash-checked files do not bind a proof to a transaction. The spike checks no hashes | Accepted. Section 4 states that the spike checks nothing, lists what a real loader must pin and that the manifest needs independent authentication, and that the Type Script's rebuild of the public inputs is what binds a proof to a transition. Test plan item 3 and milestone B2 updated |
| 2 | Medium | Attaching a proof after signing is safe only if the application input is outside every fee signer's Lock group | Accepted. Section 5 states the condition, and that the guard-Lock tally and ballot layouts meet it while an application Cell under a user's secp256k1 Lock does not. Batch placement reworded the same way |
| 3 | Medium | `signOnlyTransaction` does not make the wallet leave the transaction unchanged; adapters return what the wallet sent | Accepted. Section 5 now requires a snapshot comparison of raw fields and non-signature witness bytes before a signed transaction is accepted |
| 4 | Medium | JoyID subkey signing and a creation proof both use `output_type` of the first witness | Accepted as an open incompatibility (section 5); test plan item 5 covers root-key and subkey accounts. Not executed |
| 5 | Medium | "Any relayer works and none is trusted" omitted what a relayer observes and that it can delay a ballot past `close` | Accepted. Section 10 and R3 section 12 describe relayers as unnecessary for authorization but privacy observers and an availability dependency, and state timely inclusion as an assumption |
| 6 | Medium | Only the last proof of each series was verified and only the last witness compared, and a failed check did not fail the page or `measure.cjs` | Accepted and fixed. Every run is now checked outside the timed intervals, an altered public input must be rejected, the page reports failure and `measure.cjs` exits non-zero. Rerun on 18 November: all checks passed. The spike README states what the 11 November file did and did not cover |
| 7 | Medium | The phone estimate used the warm ratio (2.38) although the first proof is the one that counts; the cold ratio (2.88) gives about 11.4 s | Accepted. Section 6 gives both as separate unvalidated extrapolations; section 2 no longer suggests a first ballot on the phone is near the target |
| 8 | Low | Several timing statements overstated what was measured: "under 10 s on the server" (10.24 s with witness solving), "over 95%" (88% on the phone), the load figure (includes fetch and compile), the download figure (an estimate), and a stale "mobile browsers were not measured" | Accepted. Each corrected in sections 2 and 6 and in the spike README; the page now times fetch, compile and instantiate separately |
| 9 | Low | The randomness hook threw above 65,536 bytes and let the exception escape the wasm call; zero calls was not instrumented | Accepted and fixed. The hook fills in chunks and returns an error code that the wrapper maps to a `getrandom` error; a self-test at page load exercises both; calls are counted per circuit (0 for all four) |
| 10 | Low | Four fixed witnesses do not validate the `.wtns` writer over boundary or malformed inputs | Accepted. Added to test plan item 2 and the spike README's limitations as not yet tested |
| 11 | Low | The secret-handling test (a network recording) cannot detect storage or console disclosure; the fixtures serve inputs and witnesses as files | Accepted. Test plan item 4 now checks network, storage and console separately, on failure paths too; not yet tested. The spike README says so |
| 12 | Low | With Playwright installed, `run.sh` stopped the server after the headless run, so `LAN=1` could not serve a phone | Accepted and fixed: `MODE=measure`, `serve` or `both`; `LAN=1` defaults to `both` |

Examined by the reviewer and found correct: the stated coverage of the secp256k1 Lock (the
transaction hash; each covered witness's length; the first group witness with its 65-byte
`lock` zeroed; later group witnesses; witnesses at or beyond the input count; the
32,768-byte limit); that a creation proof in a signed `output_type` must come before
signing; that a batch in a guard-Lock input's witness escapes that Lock's size limit; the
`.wtns` writer's header, modulus, byte order and version against the native writer; that
the module's only import is `host_random` and that the tally fixture made no randomness
call; that the phone estimates were labelled as estimates and phone memory as unknown; and
that the tally spec binds a proof to an application transition by rebuilding the public
vector, not to every byte of one transaction.

Open: the JoyID subkey layout (finding 4), the storage and console checks (finding 11), the
writer boundary tests (finding 10), and a vote-sized proof measured on the phone, with
memory (milestone B1).
