# R4. Proving in a browser, and signing

Status: **spiked; the private tally measured on a laptop, an entry-level phone and a server, the larger circuits on the server only; external review not done.** Spike code and exact
command: [`spikes/browser`](spikes/browser/README.md).

## 1. Problem and definition of done

A voter or a player should not have to install Nargo, a Rust toolchain and snarkjs. The
private inputs must also never leave their device (private tally spec, section 9). Both
point to proving in the browser. The target was a proof in under 10 seconds.

| # | Test | State |
| --- | --- | --- |
| D1 | The pinned backend compiled to wasm32 solves a witness in a browser, byte-identical to the native backend's | Passed (spike), four circuits |
| D2 | A Groth16 proof made in the browser from that witness verifies | Passed (spike), four circuits |
| D3 | Time per proof under 10 s for the grant's circuits | Private tally: 0.12 s on a laptop, 1.8 s on an entry-level phone (first proof 2.7 s). Vote-sized and join-split circuits: measured on a 2-core server only (3.9 s, 7.5 s, 9.8 s); **not measured on the laptop or the phone** |
| D4 | All circuits on the pinned Rust, on a laptop and a phone, in Chrome, Safari and Firefox | Partly: the private tally on a laptop (Chrome, Brave) and a phone (Chrome), 11 November 2026 |
| D5 | A page that builds a transaction, proves, and hands it to a wallet or a relayer | Not built |

## 2. What was believed, and what the spike found

| Belief or goal | Result |
| --- | --- |
| The backend compiles to wasm32 | **Held with one change outside the backend**: a randomness hook for `getrandom` 0.4.1 (spike). 4.3 MB module, 0.94 MB compressed |
| A browser proof takes under 10 seconds | **Held for the private tally on every device** (0.12 s laptop, 1.8 s entry-level phone). For the larger circuits it held on the server (3.9 s vote-sized; 9.7 to 10.0 s for the depth-32 join-split), which was 2.4 times faster than the phone on the tally. A vote-sized proof on that phone is therefore expected near 9 to 10 s (estimate: server time × 2.4), at the edge of the target, and is not measured |
| Witness solving is the slow part | **Broke**: 10 to 300 ms. Proving is over 95% of the time |
| The in-browser witness is the same as the native one | **Held**: byte-identical for all four circuits |
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

**Delivery.** A static bundle: the backend module (shared by every circuit), snarkjs, and
per circuit the artifact, the proving key and the verification key. Every file is fetched
by hash from the release manifest and checked before use, because a substituted artifact
or key makes the user prove a different statement.

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

- A proof in `input_type` of the application input's witness is outside a fee payer's
  signature, so it can be attached before or after signing.
- A proof in `output_type` at an index that is also one of the signer's inputs (a creation
  funded by input 0, application output 0) **is** covered: prove first, sign second.
- A batch payload (R3: 50 KB for 172 proofs) must sit in the application input's witness,
  never in a witness the fee payer's Lock reads, or the 32 KB limit rejects it.

Library survey:

| Library | What it is | Fit |
| --- | --- | --- |
| [CCC](https://github.com/ckb-devrel/ccc) (`@ckb-ccc/*`) | Current CKB connector and transaction library. One `Signer` interface (`prepareTransaction`, `signOnlyTransaction`, `signTransaction`, `sendTransaction`) over packages for JoyID, OKX, UniSat, UTXO Global, Xverse, Rei, Nostr (NIP-07) and EVM wallets (EIP-6963); fee completion helpers | **Chosen** for any flow that needs a signature. `signOnlyTransaction` fits "sign what was built, change nothing" |
| [Lumos](https://github.com/ckb-js/lumos) | The earlier JavaScript framework; CCC ships patches for interoperating with it | Not for new code |
| [JoyID SDK](https://github.com/nervina-labs/joyid-sdk-js) | Passkey wallet SDK; reachable through CCC | Through CCC |
| `ckb-cli` | Command-line signing, used by this repository's scripts | Stays for the developer path |

Not verified in this spike: that each wallet behind CCC signs a transaction containing an
unknown Type Script and extra witness fields without rewriting it. That is test D5.

## 6. Measured budgets

Private tally v2 (3,338 constraints, ceremony key, 1.8 MB key file), witness identical to
the native backend's and proof verified on every device:

| Device | Chip, memory | OS, browser | Threads | Witness, median | Prove, first | Prove, median |
| --- | --- | --- | --- | --- | --- | --- |
| MacBook Pro | Apple Silicon | macOS; Chrome and Brave | 12 | 5 ms | 203 ms | 115 ms |
| Infinix Smart 8 (X6525), entry-level phone | Unisoc T606 (2 × Cortex-A75 + 6 × Cortex-A55), 3 GB | Android 13 (XOS 13.0); Chrome 157.0.8103.50 | 8 | 247 ms | 2,651 ms | 1,813 ms |
| Cloud server | 2 cores of an Intel Xeon at 2.1 GHz, 7 GB | Linux; headless Chromium 153 | 2 | 12 ms | 920 ms | 761 ms |

The phone is the low-end reference point. Its first proof is slower than later ones
(2.7 s against 1.8 s); a voter makes one proof, so the first-proof figure is the one that
counts.

The phone took 5,343 ms to load the 4.3 MB backend module, fetched over Wi-Fi from the
laptop serving the page (73 ms on the laptop itself, 60 ms on the server). That is a
first-visit cost of downloading and compiling the module, not a per-proof cost: a real
application caches the module (HTTP cache or a service worker), and later visits skip the
download.

Larger circuits, **measured on the cloud server only** (three runs each, spike). They were
not run on the laptop or the phone:

| Item | Value | Basis |
| --- | --- | --- |
| Prove, vote-sized (17,483 constraints) | 3.8 to 4.0 s | spike, server |
| Prove, join-split depth 20 / 32 | 7.5 to 7.7 s / 9.7 to 10.0 s | spike, server |
| Witness solving | 71 to 305 ms | spike, server |
| The same on the entry-level phone | about 9 to 10 s (vote-sized), 18 s and 24 s (join-splits) | **estimate**: server time × 2.4, the phone-to-server ratio measured on the tally. Unverified; memory may fail first (below) |
| Phone memory for a join-split | unknown. The depth-32 key is 28.6 MB on disk; snarkjs holds the key, the witness and several working buffers of similar size in memory. On a 3 GB phone this may not fit a browser tab | not measured |
| First-visit download for a ballot | about 8 MB compressed (key 6.9, backend 0.94, snarkjs 0.15) | spike |
| Backend module instantiation | 60 ms | spike |

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
   differential inputs of the circuit test suites, in CI (headless).
3. Refusals: an artifact, key or module whose hash differs from the manifest; a key for
   another circuit; inputs that do not satisfy the circuit (no proof must come out).
4. Secret handling: no private input in any network request, in `localStorage`, or in
   logs; checked by recording the page's network traffic during a proof.
5. Signing flows (D5) through CCC with at least JoyID and one EVM wallet: fee-only signing
   with the proof attached before and after; creation with the proof inside the signed
   witness.
6. A batch payload over 32 KB next to a secp256k1 fee input is accepted when placed in the
   application witness and rejected when placed in the signer's.

## 9. Milestones

| # | Step | Acceptance test |
| --- | --- | --- |
| B1 | The vote-sized circuit on the laptop and the entry-level phone (the tally was done on both on 11 November 2026) | Vote-sized proof under 10 s on the phone, with memory recorded |
| B2 | Backend wrapper as a published module with hash-checked loading | Test plan items 2 and 3 in CI |
| B3 | Ballot page: build the statement, prove, post to a relayer; no wallet | A vote cast from a phone browser lands on a local chain; traffic recording shows no secret |
| B4 | CCC signing for staked and owned applications | Test plan items 5 and 6 |

## 10. Risks and open questions

| Risk | Handling |
| --- | --- |
| The vote-sized and join-split circuits were measured on one server only; the phone estimate for a vote is at the edge of the 10 s target | Run `?only=spend-1-d20` on the phone (B1) before any claim about ballots; if it misses, use a shallower voter tree or the Rust prover of option B |
| A 7 MB key on a mobile connection | Cache with a service worker; show progress; the ballot circuit can drop to a shallower tree for small electorates |
| The page is the trust base: a served page can exfiltrate secrets or swap the statement | Hash-pinned static bundle; reproducible build; publish the bundle hash; a self-hosted copy stays possible |
| A voter without a wallet depends on a relayer | Any relayer works and none is trusted (R3); a wallet path remains as fallback |
| Worker threads or memory limits differ across browsers | B1; option B for proving if needed |
| `getrandom` custom hook | It only forwards to `crypto.getRandomValues`; witness solving of the tested circuits requested no randomness |

Open: whether the relayer endpoint is part of the grant deliverable or left to the first
consumer; whether to offer a native prover for users who prefer not to trust a web page.

## 11. External review

Not done. Items a reviewer must examine: the claim in section 5 about what the system Lock
signs (read the cited source); whether loading keys and artifacts by hash is enough to
bind the proved statement; and whether any private input can leave the page.
