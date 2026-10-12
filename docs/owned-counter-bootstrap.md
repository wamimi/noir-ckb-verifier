# Counter source-preview prerequisites

Start at [the reviewer guide](owned-counter-review.md). This is a source checkout,
not a standalone executable: the demo compiles the circuit and contract fresh, so
Rust, Nargo, Node and LLVM 18 are required.

| Host | Status |
| --- | --- |
| macOS ARM64, native | Reproduced by the maintainer (existing caches) |
| Ubuntu 24.04 x86_64, native or [container](owned-counter-container.md) | Pinned tools; full lifecycle **pending validation** |
| Ubuntu 24.04 ARM64 (including Apple Silicon via Colima), [container](owned-counter-container.md) | Full `local` mode passed in the container (maintainer machine) |
| Intel macOS, WSL2, other Linux distributions, Windows | Not supported |

Pins for every host live in [`toolchains/platforms.json`](../toolchains/platforms.json).
Existing Linux CI is the Capsule path; its green badge does not establish counter execution.

The same-machine reproduction used existing package caches. The bootstrap below
makes those caches explicit; it is **not a claimed fresh-machine installation test**.
No wallet is needed for local reproduction. Stop on any failed prerequisite.

## Get the source and pinned backend

Run from a workspace parent directory. The five original counter/SP1 commits are
published through `836f2a1`. The tested guided launcher is published at
`4ae8a710f9ba71be21f8a19cef12dbdf87571f41`; the commands below pin that preview.
Record `git rev-parse HEAD` with your reproduction feedback.

```bash
git clone --no-checkout https://github.com/wamimi/noir-ckb-verifier.git
git -C noir-ckb-verifier checkout --detach 4ae8a710f9ba71be21f8a19cef12dbdf87571f41
git -C noir-ckb-verifier rev-parse HEAD
git clone https://github.com/wamimi/Noir-Groth16.git
git -C Noir-Groth16 checkout --detach 828025f3a0090e2934940956c0f5dc8093eb5532
cd noir-ckb-verifier
```

If you already have the supplied source checkout, start in it instead; do not reset
existing work. Clone a new backend sibling if necessary. From the toolkit root:

```bash
test -f scripts/local-owned-counter.py
export COUNTER_BACKEND="$(cd ../Noir-Groth16 && pwd)"
git -C "$COUNTER_BACKEND" rev-parse HEAD
git -C "$COUNTER_BACKEND" status --short
```

Expected backend revision is the pin above and an empty status. The counter uses
pinned verifier libraries through Cargo; it does not need a sibling groth16-ckb
checkout. That sibling is needed for some historical Capsule workflows only.

## Host tools and versions

**Ubuntu 24.04 (x86_64 or ARM64):** the container route installs everything below
for you. Natively, install `git python3 build-essential pkg-config clang-18 lld-18
nodejs npm` with apt and rustup from <https://rustup.rs/>; the launcher finds
`clang-18` on PATH. Ubuntu 22.04 does not ship clang-18 in its default repositories.
Then follow the rustup, cache and tool steps below (skip the macOS-only lines).

**macOS ARM64:** install Git, Xcode Command Line Tools, Python >=3.9, Node.js/npm, Homebrew LLVM 18
and rustup. These are host installations, not blockchain operations. If missing:
`xcode-select --install`; get rustup from <https://rustup.rs/>, Homebrew from
<https://brew.sh/>, and Node from <https://nodejs.org/en/download>.
The measured host used Python 3.9.6, Node 24.3.0, npm 11.4.2 and Homebrew clang
18.1.8; different host versions are not the exact reproduced environment.

```bash
brew install llvm@18
export PATH="$(brew --prefix llvm@18)/bin:$PATH"
export CLANG="$(brew --prefix llvm@18)/bin/clang"
export CC_riscv64imac_unknown_none_elf="$CLANG"
python3 --version
node --version
npm --version
clang --version
rustup toolchain install 1.95.0 --profile minimal --component rustfmt --component clippy
rustup toolchain install 1.94.1 --profile minimal --target riscv64imac-unknown-none-elf
```

Use a Bash or zsh terminal retaining these exports for the subsequent commands.
The target C compiler is explicit; Apple Clang alone is not the reproduced LLVM.
Do not change the contract toolchain to match the host toolchain.

Nargo: `python3 scripts/fetch-counter-tools.py` (below) also installs the pinned,
hash-checked Nargo executable into the tools directory, and the launcher prefers it.
Alternatively install noirup from the official [Noir installation guide](https://noir-lang.org/docs/getting_started/noir_installation), then:

```bash
noirup --version 1.0.0-beta.18
nargo --version
```

Require Nargo `1.0.0-beta.18` and noirc
`99bb8b5cf33d7669adbdef096b12d80f30b4c0c9`. The setup runner enforces both.
The official noirup `--version` installation flag was inspected; no installer or
system-wide tool upgrade was executed during this documentation pass.

## Populate caches before offline builds

Run from the toolkit root. These fetch dependencies over the network and write
local caches; they do not sign, broadcast or spend CKB. All Cargo files stay locked:

```bash
cargo +1.95.0 fetch --locked --manifest-path Cargo.toml
cargo +1.94.1 fetch --locked --manifest-path contracts/Cargo.toml
cargo +1.95.0 fetch --locked --manifest-path "$COUNTER_BACKEND/Cargo.toml"
npm exec --yes --package=snarkjs@0.7.5 -- node -e 'console.log("snarkjs package cached")'
```

The npm command populates the npx package cache used by `npx --offline
snarkjs@0.7.5`; installing an unrelated global snarkjs is not a substitute.
This npm cache sequence was checked using an empty isolated npm cache. It is still
not a full fresh-machine Cargo/toolchain install. Cargo cache checks were performed
on this machine's existing caches, not an empty Cargo home.

Confirm all three offline dependency graphs resolve and the CLI starts:

```bash
cargo +1.95.0 metadata --locked --offline --format-version 1 > /dev/null
cargo +1.94.1 metadata --locked --offline --manifest-path contracts/Cargo.toml --format-version 1 > /dev/null
cargo +1.95.0 metadata --locked --offline --manifest-path "$COUNTER_BACKEND/Cargo.toml" --format-version 1 > /dev/null
cargo +1.95.0 run --locked --offline -p noir-ckb-cli -- counter --help
python3 -B -m unittest discover -s scripts/tests -v
```

snarkjs 0.7.5's `--version` prints a banner and returns 99; the setup runner knows
this. Do not mistake that particular version probe for proof-verification success.
Actual proof verification must return zero and `OK!`.

Finally install the pinned node, wallet and Nargo executables for your host:

```bash
python3 scripts/fetch-counter-tools.py --list   # shows URLs and destinations only
python3 scripts/fetch-counter-tools.py          # asks before downloading
```

Each official GitHub archive and the single extracted executable are checked
against `toolchains/platforms.json`; only that executable is written (mode 0755)
under `target/counter-tools/<platform>/`. Tools already present with matching
digests are skipped; a mismatched existing file is never overwritten. Week 15
tool directories using the older archive layout are still recognized.
Then run the guided checks and either lifecycle:

```bash
python3 -B scripts/start-counter.py doctor
python3 -B scripts/start-counter.py quick   # fresh proof + signed local transactions
python3 -B scripts/start-counter.py local   # quick + 48 VM cases, ranges, 3 mutations
```

`quick` still performs fresh setup, compilation, proving, snarkjs verification,
contract build, pre-signing statement check and the signed deployment, creation
and update on a disposable local chain. Its manifest records `validation: quick`
and lists the skipped adversarial checks; it is not evidence that the matrix ran.

The doctor queries `rustup toolchain list` rather than invoking `rustc +VERSION`,
so checking never triggers an automatic toolchain download. The launcher finds an
explicit `CLANG`, then `clang-18` on PATH, then Homebrew/Ubuntu LLVM 18 locations,
and sets the target compiler environment for child processes. It does not install tools
or edit your shell configuration. Use `--tools PATH` for a different downloaded-tool
directory. The [local quickstart](owned-counter-quickstart.md) retains the direct commands.

## Resources and failures

The retained full local-run directory occupied about 1.5 GiB on the maintainer's
machine (measured after completion, including build outputs and mutations). This
is not peak disk/RAM demand or a guaranteed minimum; caches and host tools consume
additional space. Check `df -h .` and allow headroom. No reliable end-to-end timing
was logged, so no setup-duration benchmark is claimed. Record elapsed time on your
own run if reporting friction. Long builds/proofs should not be presented as instant.

Missing-cache errors: rerun the relevant locked fetch, not `cargo update`.
Wrong Nargo: install the exact version. Missing target C compiler: check the LLVM
exports. Busy ports: select unused `--rpc-port`/`--p2p-port`. RPC 403/network failures:
the shared helper sends the honest application User-Agent and reports errors without
turning off TLS; do not disable TLS or automatically retry a transaction broadcast.
