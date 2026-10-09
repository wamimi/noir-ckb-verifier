# Guided counter validation — 9 October 2026

The guided launcher completed the existing local runner with fresh setup/proofs,
48 passing VM cases, three detected mutations, and committed-and-checked local
dependency deployment, zero-state creation and update to one. The node stopped
when the runner completed. This is another maintainer run on macOS ARM64 with
existing tools and caches, not an independent or fresh-machine reproduction.

- [Command and check summary](week-15-guided/validation.json)
- [Local result manifest](week-15-guided/local-run.json)
- [48 VM results](week-15-guided/matrix-results.json)
- [Mutation results](week-15-guided/mutations.json)
- [Range results](week-15-guided/range-results.json)

Nineteen Python tests passed, including launcher routing/failure boundaries; six
Rust CLI tests passed. CLI Clippy with warnings denied and formatting passed.
The Rust `counter start inspect` entry point printed the retained result.
Relative documentation links were checked. Final output-path normalization was
covered by a focused launcher regression check after the complete local run.

The retained public testnet proof verified with snarkjs 0.7.5 (exit zero, `OK!`).
A new read-only testnet check found all three existing transactions committed with
matching contents; the initial Cell was `unknown` and the successor live. The
committed update input establishes consumption. No new testnet transaction was sent.

Only selected public result records are copied here. Private account/wallet files,
proving keys and full generated directories remain ignored under target/. The
original 7 October evidence is preserved and is separate from this local run.
