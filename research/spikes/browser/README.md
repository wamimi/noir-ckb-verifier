# Spike: proving in a browser

Research questions for [R4](../../browser.md): does the pinned backend compile to wasm32,
and how long does a proof take in a browser?

## What it is

- `backend-wasm/`: a 100-line wrapper crate that exposes the pinned Noir-Groth16 backend
  (witness solving and R1CS wire layout) as a wasm32 module with a plain C ABI, no
  JavaScript glue library. Input: the artifact JSON from `nargo compile` and an inputs JSON.
  Output: an iden3 `.wtns` file in memory.
- `web/`: a static page. For each circuit it solves the witness in the wasm backend and
  proves with snarkjs (`groth16.prove`), several times. After every run, outside the timed
  intervals, it compares that run's witness byte for byte with the witness the native
  backend wrote and verifies that run's proof. It then checks that the verifier rejects the
  last proof with one public input altered, and reports failure if any check fails. It
  counts the calls the backend makes to its randomness hook, per circuit.
- `prepare.py`: assembles artifacts, inputs, reference witnesses and keys for the page.
- `measure.cjs`: opens the page in headless Chromium through Playwright, prints the JSON,
  optionally writes it to a file, and exits non-zero if the page reported an error or any
  check failed.

The page checks no file hashes: it uses whatever the server sends. Its inputs and reference
witnesses are public test fixtures, written to disk and served like any other file.

## Command

```bash
BACKEND=/path/to/Noir-Groth16 NARGO=/path/to/nargo SNARKJS=/path/to/node_modules/.bin/snarkjs \
  research/spikes/browser/run.sh            # private tally only; headless measurement, then exit
FULL=1 ... research/spikes/browser/run.sh   # also the three note circuits (slow setup)
LAN=1 ...  research/spikes/browser/run.sh   # measure, then keep serving to the local network
MODE=serve ... research/spikes/browser/run.sh   # serve only, until Ctrl-C
RESULTS=out.json ... research/spikes/browser/run.sh   # also write the measured JSON
```

`MODE` is `measure` (the default; needs Playwright; exits non-zero if any check failed),
`serve` (no measurement; serves until stopped) or `both` (the default with `LAN=1`: measures,
then keeps serving until stopped, so a phone can open the page afterwards). The first
version stopped the server as soon as the headless measurement ended, which made `LAN=1`
useless on a machine with Playwright installed.

The page is served on localhost only unless `LAN=1` is set; with it, anyone on the same
network can open the page while the script runs. `?only=<circuit>` runs one circuit, which
limits memory on small devices; `?runs=N` sets the number of proofs.

## Result on a laptop and a phone (11 November 2026, private tally only)

Built on macOS with the pinned Rust; page opened by hand, numbers read from its table.

| Device | Chip, memory | OS, browser | Threads | Witness, median | Prove, first | Prove, median |
| --- | --- | --- | --- | --- | --- | --- |
| MacBook Pro | Apple Silicon | macOS; Chrome and Brave | 12 | 5 ms | 203 ms | 115 ms |
| Infinix Smart 8 (X6525), entry-level phone | Unisoc T606 (2 × Cortex-A75 + 6 × Cortex-A55), 3 GB | Android 13 (XOS 13.0); Chrome 157.0.8103.50 | 8 | 247 ms | 2,651 ms | 1,813 ms |

Both, with the page of that date: the last witness of the series was equal to the native
backend's and the last proof verified (the earlier runs were not checked; see below).
Backend module load, which on that page meant fetching, compiling and instantiating it
together: 73 ms on the laptop; 5,343 ms on the phone, which fetched it over Wi-Fi from the
laptop (a first-visit cost). The larger circuits were not run on these devices.

The first version of `run.sh` served the page on every network interface, which is how the
phone reached it. That was not intended. It now binds to localhost unless `LAN=1` is set.

## Result on a cloud server (11 November 2026, all four circuits)

Machine: 2 cores of an Intel Xeon at 2.1 GHz, 7 GB memory, Linux x86_64; headless Chromium
153 through Playwright; `navigator.hardwareConcurrency` = 2. snarkjs 0.7.5. Backend
`828025f` built for wasm32 with Rust 1.97.0 and `-Zbuild-std` (the pinned Rust could not be
downloaded there). Three runs per circuit; full output in
`results/2026-11-11-headless-chromium-2-core-xeon.json`. On the private tally its median
proof was 2.4 times faster than the entry-level phone's (761 against 1,813 ms) and its first
proof 2.9 times faster (920 against 2,651 ms); it was 6.6 times slower than the laptop.

| Circuit | Constraints | Witness (ms) | Prove (ms), three runs | Key file | Key, gzip |
| --- | --- | --- | --- | --- | --- |
| Private tally v2 (ceremony key) | 3,338 | 10 to 68 | 920, 741, 761 | 1.8 MB | 1.2 MB |
| Spend one note, depth 20 | 17,483 | 71 to 88 | 3,960, 3,934, 3,796 | 9.9 MB | 6.9 MB |
| Join-split, depth 20 | 37,862 | 163 to 170 | 7,453, 7,508, 7,695 | 21.0 MB | 14.6 MB |
| Join-split, depth 32 | 55,046 | 266 to 305 | 9,702, 9,756, 9,975 | 28.6 MB | 19.3 MB |

- What this file covers and does not. The page of that date compared and verified only the
  last run of each series: for each circuit the third witness was byte-identical to the
  native backend's and the third proof verified. The first two witnesses and proofs of each
  series were not checked. A failed check did not make the page or `measure.cjs` report
  failure, and randomness calls were not counted. The run of 18 November (below) closed
  these gaps.
- Backend module: 4,345,095 bytes (939,496 gzip); 60 ms from the start of the fetch to an
  instantiated module, fetched from localhost (the figure includes fetching and compiling).
  snarkjs: 710,896 bytes (153,628 gzip).
- The three note circuits used a development-only setup made for the spike.

## Result on a cloud server after the review changes (18 November 2026, all four circuits)

Same kind of machine as the run above (2 cores of an Intel Xeon at 2.1 GHz, 7 GB, Linux
x86_64), possibly not the same host; headless Chromium 153.0.8010.12 through Playwright
1.63.0; snarkjs 0.7.5. Backend `828025f` with the changed wrapper (`lib.rs`), built for
wasm32 with Rust 1.97.0 and `-Zbuild-std`. Three runs per circuit. The circuit files were the
ones prepared for the 11 November run. Full output:
`results/2026-11-18-headless-chromium-153-2-core-xeon.json`. `measure.cjs` exited 0.

| Circuit | Witness (ms) | Prove (ms), three runs | Witness equal to native | Proof verified | Altered public input rejected | Randomness calls |
| --- | --- | --- | --- | --- | --- | --- |
| Private tally v2 | 62, 15, 14 | 916, 751, 776 | 3 of 3 | 3 of 3 | yes | 0 |
| Spend one note, depth 20 | 65, 78, 81 | 3,620, 3,573, 3,606 | 3 of 3 | 3 of 3 | yes | 0 |
| Join-split, depth 20 | 125, 245, 147 | 6,863, 6,655, 6,467 | 3 of 3 | 3 of 3 | yes | 0 |
| Join-split, depth 32 | 257, 245, 204 | 8,141, 8,387, 8,300 | 3 of 3 | 3 of 3 | yes | 0 |

- Backend module, 4,345,117 bytes, from localhost: fetch 49 ms, compile 16 ms, instantiate
  under 1 ms (65 ms in total). Chromium compiles WebAssembly lazily, so part of the
  compilation falls in the first witness solve of the page (62 ms against 14 to 15 ms
  afterwards).
- The randomness hook filled 131,073 bytes (three chunks) and returned an error code, not an
  exception, for a range outside memory.
- Median proof times were 8% to 15% lower than on 11 November for the three larger circuits
  (spend 3,935 to 3,606 ms; join-splits 7,508 to 6,655 and 9,756 to 8,300) and 2% higher for
  the tally (761 to 776). The run-to-run spread between two machines of the same
  description is therefore at least that large; the phone ratios in `research/browser.md`
  use the 11 November server run, which was measured on the same day as the phone.
- Before the full run, a witness with one byte flipped and a missing key file were each shown
  to make `measure.cjs` exit 1.

## What did not work, and what the build needed

- The backend did not build for `wasm32-unknown-unknown` as is: `getrandom` 0.4.1, pulled
  in through the ECDSA black-box solvers of ACVM, has no default backend there. Building
  with `--cfg getrandom_backend="custom"` and supplying the hook in the wrapper crate (it
  calls `crypto.getRandomValues`) was the only change. No backend source was modified. The
  first version of the hook passed the whole request to one `getRandomValues` call, which
  throws above 65,536 bytes, and let the exception escape the wasm call. Since 18 November
  the page fills in chunks of at most 65,536 bytes and returns an error code that the
  wrapper turns into a `getrandom` error.
- The backend's own witness writer needs a file system. The wrapper writes the `.wtns`
  bytes itself; the first version wrote format version 2 where the backend writes 1, which
  the byte comparison caught.
- Memory use, Safari and Firefox were not measured. Only one mobile browser (Chrome on the
  phone above) was measured, and only on the private tally.
- Proving used the snarkjs default (worker threads). Single-thread mode was not measured.
- The witness comparison covers one fixed input set per circuit. Not tested: writer
  boundary values (field elements 0, 1 and p − 1, values that cross byte boundaries) read
  back by an independent parser; inputs that exercise other branches and public/private
  layouts; malformed, negative, non-canonical and out-of-range inputs, which the native and
  wasm paths must refuse alike. Agreement shows that the two paths serialize the same
  witness; both run the same backend code, so it does not show that the circuit or its
  wire mapping is correct.
- Secret handling was not tested. The page has no explicit write of inputs to the network,
  to storage or to the console on its success path, by reading the code. A network
  recording alone would not detect a write to `localStorage`, `sessionStorage`, IndexedDB or
  the Cache Storage, or a `console` call; those need checks of their own, on success and on
  failure paths. Ordinary deallocation does not erase wasm memory. Browser fetch caching is
  not disabled.
