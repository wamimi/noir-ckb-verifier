# Counter preview in a Linux container

Status: on Apple Silicon (Colima, `linux/arm64`) both `quick` and the full
`local` mode (48-case matrix, range checks, 3 mutations) passed on 12 October
2026; see [portable evidence](../evidence/week-15-portable.md). `linux/amd64`
has not yet passed. Treat a run on
your machine as new evidence and report it (see the end of this page).

The container runs the same `scripts/start-counter.py` workflow as the native
path on Ubuntu 24.04, with pinned Rust, clang-18, Nargo, snarkjs, CKB and ckb-cli.
It is for the **local, no-wallet** modes only. Public-testnet signing never happens
inside it.

## What a container does and does not establish

- The image architecture follows the Docker host: `linux/arm64` on Apple Silicon
  (Colima), `linux/amd64` on a typical Linux PC. Each is a separate result.
- A run inside Colima on a Mac is a **Linux ARM64** result, not a macOS result.
- Emulating x86_64 on Apple Silicon (`colima start --arch x86_64`) works but is
  much slower; prefer a native x86_64 Linux machine or CI for that platform.

## 1. Get a Docker engine

Docker Desktop is not required. On macOS, Colima provides the Docker engine in a
small Linux VM:

```bash
brew install colima docker
colima start --cpu 4 --memory 8 --disk 60
docker version            # Server should show linux/arm64 on Apple Silicon
```

The Rust builds need memory; 8 GiB is a recommendation, not a measured minimum.
If a mounted folder is read-only inside the VM, restart with
`colima start --mount "$HOME:w"`. Stop the VM afterwards with `colima stop`.

On Ubuntu 24.04, install Docker Engine from your distribution or Docker's
official instructions. The run script adds `--user "$(id -u):$(id -g)"` on Linux
so result files belong to you.

## 2. Build the image (network)

From the repository root:

```bash
scripts/run-counter-container.sh build
```

This downloads, inside the build only: Ubuntu packages, rustup-init 1.28.2
(checked against its published SHA-256), Rust 1.95.0 and 1.94.1 with the RISC-V
target, the backend fork at `828025f3…`, locked Cargo dependencies, snarkjs 0.7.5,
and the CKB/ckb-cli/Nargo archives (checked against `toolchains/platforms.json`).
`.dockerignore` keeps `target/`, `.local/`, key files and wallets out of the image.

The base image is pinned by digest (`ubuntu:24.04@sha256:534baea6…`, resolved by
the first verified build); `build` stamps it, with the source revision, into
the image's labels, and each run copies those labels into `container-provenance.json`.

## 3. Run

```bash
scripts/run-counter-container.sh doctor   # prerequisites inside the image
scripts/run-counter-container.sh quick    # fresh proof + signed local lifecycle
scripts/run-counter-container.sh local    # quick + 48 VM cases, ranges, 3 mutations
```

Runs use `--network none`: the disposable CKB chain lives on the container's own
loopback, Cargo and npx run offline, and nothing is downloaded at run time.
Each run creates `target/container-runs/<mode>-<UTC time>/` containing:

- `container-provenance.json` — image ID and architecture, the image's build
  labels (source revision, dirty-file count, Dockerfile hash, base image), Docker
  server, host, and separately the host checkout's current revision;
- `console.log` and `exit-code`;
- `run/` — the runner's output, including `manifest.json` and `commands.json`.

`run/private/` holds a disposable development key for the throwaway local chain.
Never reuse it anywhere and never upload the run directory.

## Reporting a result

Share only: `container-provenance.json`, `run/manifest.json`, elapsed time,
and sanitized error text. A `quick` result is a lifecycle result; only `local`
establishes that the adversarial matrix and mutations ran on that platform.
