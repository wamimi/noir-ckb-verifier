# Week 15 — portable counter packaging and private-input feasibility

Recorded 12 October 2026. All runs below used disposable local chains; no public
transaction was prepared, signed or broadcast. Each result states its own scope.

## Packaging changes under test

Central host/tool pins (`toolchains/platforms.json`), a consent-first fetcher
that verifies archive and executable SHA-256, a platform-aware launcher with a
labelled `quick` mode, an Ubuntu 24.04 container route run with `--network none`,
and corrected single-party setup wording. Linux archive pins were computed from
the official GitHub release downloads; the macOS ARM64 downloads reproduced the
existing Week 15 pins exactly.

## Results

| Platform | Mode | Result | Scope and caveats |
| --- | --- | --- | --- |
| macOS ARM64, native | quick | `quick-lifecycle-validated` in 1 min 30 s | Maintainer machine, existing tools/caches; 40 Python and 6 Rust CLI tests also passed. Not a fresh-machine test. |
| Ubuntu 24.04 ARM64, container (Colima on Apple Silicon) | doctor, quick | doctor passed; `quick-lifecycle-validated`, exit 0, about 3 min | Image built from pinned sources (build about 18 min); run with no network. |
| Ubuntu 24.04 ARM64, container (Colima on Apple Silicon) | local (full) | `locally-validated`, exit 0, 4 min 48 s: 6/6 range checks, 48/48 VM cases, 3/3 mutations detected, signed lifecycle committed | Same image as the quick run; no network. Maintainer machine; container runs as root under Colima. |
| Ubuntu x86_64 (cloud workspace) | partial | Pinned tools verified; circuit compiled; local chain, key, preflight passed; stopped at the Rust build | Rust toolchain downloads were blocked by that environment's network policy. Not a lifecycle result. |
| Ubuntu 24.04 x86_64 and ARM64, GitHub Actions | quick | Run 1 failed: backend git ownership check under a non-root uid. Run 2 passed the doctor and backend build, then failed writing Cargo's default `target/`. **Run 3 (commit `9079b21`) passed on both runners** in 6 min 17 s | Hosted runners, non-root uid, no network during the run; first x86_64 lifecycle; confirms the pinned base digest resolves on amd64. Matrix and mutations not run in CI. |

Circuit identity: the compiled `owned_counter_v1` ACIR bytecode is identical on
macOS ARM64 and Linux x86_64 (Nargo beta.18), which the testnet "join existing
deployment" path relies on.

Container provenance (both ARM64 runs): image
`sha256:78e37c6fd181f3a70b9a54eaf7e54e739fbd2dd4e86ea0934124c0fdc39b8c65`,
`linux/arm64`, Docker server 27.4.0. The build log resolved `ubuntu:24.04` to
`sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`.
The image was built from commit `00a812951c9206fa0c942d8f8a6e0d205805b2a3` plus
the then-uncommitted rustup `HOME` and git-safe backend changes; it predates the
base-digest pin and the writable `target/` change.

Correction: those runs' `container-provenance.json` files record the host
checkout at run time (`00a8129…` for quick, `9c2687e…` for local) and the host
Dockerfile's base line, not the image's own source. The run script now stamps
source revision, dirty-path count, Dockerfile hash and base image into image
labels at build time and copies them into each run's provenance.

Local receipts (isolated development chains, not public transactions):

| Run | Genesis | Deployment | Creation | Update |
| --- | --- | --- | --- | --- |
| macOS ARM64 quick | `0xd84317…f3c2` | `0x69cc1a…4b56` | `0xe4175e…b7c7` | `0xa84582…5283` |
| Linux ARM64 container quick | `0xaaf3e7…b1c0` | `0x9a3aa5…baa4` | `0x4b310f…09d9` | `0xeece30…c5df` |
| Linux ARM64 container local | `0x4169ac…d5e8` | `0x382361…f172` | `0x4ddf30…0bd3` | `0x8e13ee…9e01` |

## Private-input feasibility spike

`experiments/private-tally-spike/` (feasibility only, not the v2 protocol).

- Noir beta.18 keeps `std::hash::poseidon2::Poseidon2::hash` private; only the
  raw permutation blackbox is public. `noir-lang/poseidon` v0.4.0 does not compile
  on beta.18; v0.2.6 (`00f879180a56720169cff92a56778d40678d8e26`) does, its
  non-oracle tests pass, and its 1-3 input Poseidon2 vectors equal v0.4.0's.
  v0.2.6 retains the stale-cache bug for inputs longer than three elements, so
  every hash call is limited to at most three inputs.
- Differential check on macOS ARM64 with the pinned backend `noir-cli`
  (SHA-256 prefix `9b1f82e4`, from the 9 October setup): **19/19 cases agree**
  between Noir execution and backend R1CS + `snarkjs wtns check`, including
  creation at zero, delta = 0 cover updates, maximum delta, wrong key/blinding/
  value/commitments, value and delta overflow, invalid creation and context-limb
  overflow. Accepted witnesses expose the four public values in wires 1..4 with
  five private inputs declared first. About 16 s.
- Secret handling: throwaway secrets were deleted after the run; only outcome
  records were kept, and the leak scan (decimal, hex, raw little/big-endian)
  found nothing. The scan was separately shown to detect planted leaks.

This establishes that the pinned backend handles Poseidon2 (via v0.2.6) and the
creation branch for these cases. It is not a proof of general Poseidon2 or
conditional-lowering correctness, a reviewed protocol, or a setup ceremony.
