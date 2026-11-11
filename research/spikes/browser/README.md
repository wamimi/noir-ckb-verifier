# Spike: proving in a browser

Research questions for [R4](../../browser.md): does the pinned backend compile to wasm32,
and how long does a proof take in a browser?

## What it is

- `backend-wasm/`: a 100-line wrapper crate that exposes the pinned Noir-Groth16 backend
  (witness solving and R1CS wire layout) as a wasm32 module with a plain C ABI, no
  JavaScript glue library. Input: the artifact JSON from `nargo compile` and an inputs JSON.
  Output: an iden3 `.wtns` file in memory.
- `web/`: a static page. For each circuit it solves the witness in the wasm backend,
  compares it byte for byte with the witness the native backend wrote, proves with snarkjs
  (`groth16.prove`), verifies, and shows the times.
- `prepare.py`: assembles artifacts, inputs, reference witnesses and keys for the page.
- `measure.cjs`: opens the page in headless Chromium through Playwright and prints the JSON.

## Command

```bash
BACKEND=/path/to/Noir-Groth16 NARGO=/path/to/nargo SNARKJS=/path/to/node_modules/.bin/snarkjs \
  research/spikes/browser/run.sh            # private tally only
FULL=1 ... research/spikes/browser/run.sh   # also the three note circuits (slow setup)
```

## Result (11 November 2026)

Machine: 2 cores of an Intel Xeon at 2.1 GHz, 7 GB memory, Linux x86_64; headless Chromium
153 through Playwright; `navigator.hardwareConcurrency` = 2. snarkjs 0.7.5. Backend
`828025f` built for wasm32 with Rust 1.97.0 and `-Zbuild-std` (the pinned Rust could not be
downloaded there). Three runs per circuit; full output in
`results/2026-11-11-headless-chromium-2-core-xeon.json`. **This is a slow machine; it is
not a phone and not a laptop.** No other device was measured.

| Circuit | Constraints | Witness (ms) | Prove (ms), three runs | Key file | Key, gzip |
| --- | --- | --- | --- | --- | --- |
| Private tally v2 (ceremony key) | 3,338 | 10 to 68 | 920, 741, 761 | 1.8 MB | 1.2 MB |
| Spend one note, depth 20 | 17,483 | 71 to 88 | 3,960, 3,934, 3,796 | 9.9 MB | 6.9 MB |
| Join-split, depth 20 | 37,862 | 163 to 170 | 7,453, 7,508, 7,695 | 21.0 MB | 14.6 MB |
| Join-split, depth 32 | 55,046 | 266 to 305 | 9,702, 9,756, 9,975 | 28.6 MB | 19.3 MB |

- Every witness solved in the browser was byte-identical to the native backend's, and
  every proof verified in the page with the matching verification key.
- Backend module: 4,345,095 bytes (939,496 gzip); instantiated in 60 ms. snarkjs:
  710,896 bytes (153,628 gzip).
- The three note circuits used a development-only setup made for the spike.

## What did not work, and what the build needed

- The backend did not build for `wasm32-unknown-unknown` as is: `getrandom` 0.4.1, pulled
  in through the ECDSA black-box solvers of ACVM, has no default backend there. Building
  with `--cfg getrandom_backend="custom"` and supplying the hook in the wrapper crate (it
  calls `crypto.getRandomValues`) was the only change. No backend source was modified.
- The backend's own witness writer needs a file system. The wrapper writes the `.wtns`
  bytes itself; the first version wrote format version 2 where the backend writes 1, which
  the byte comparison caught.
- Memory use, mobile browsers, Safari and Firefox were not measured.
- Proving used the snarkjs default (worker threads). Single-thread mode was not measured.
