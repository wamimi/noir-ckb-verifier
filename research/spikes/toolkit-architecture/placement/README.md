# Spike: verifier placement and the cost of public inputs

Questions for [R0](../../../toolkit-architecture.md), sections 4 and 6:

1. What does it cost to keep the Groth16 verifier in a shared Cell and `spawn` it, instead
   of linking it into every generated script?
2. How do verification cycles depend on the number and the size of public inputs?

## What it is

- `contracts/verify-linked`: a script that verifies the payload of its witness against a
  verification key Cell. `contracts/verify-parent`: a script without pairing code that
  decodes the payload and spawns `verify-linked` (RFC 0050).
- `harness/`: a `ckb-testtool` test that (a) replays recorded matrix transactions unchanged
  as a calibration, (b) runs the recorded proofs through both scripts, (c) optionally runs
  every case written by `npub.py`, (d) replays the recorded tally update inside
  transactions the prover never saw (`relayer_open`).
- `npub.py`: writes circuits with N public inputs, proves each with small and with
  full-width public values (development setup), and writes case files.

## Command

```bash
research/spikes/toolkit-architecture/placement/run.sh
```

With the pinned toolchains (Rust 1.94.1 + riscv64imac target, Rust 1.95.0, clang 18). For
the second question also set `NARGO`, `BACKEND_CLI`, `ADAPTER` and `SNARKJS` (see `run.sh`).

## Result on the pinned toolchain (11 November 2026)

Rust 1.94.1 (contracts), Rust 1.95.0 (harness), clang 18, macOS ARM64. Full output:
`results/2026-11-11-pinned-macos-arm64.txt`. The public-input part was not run on the
pinned toolchain; its table below is from Rust 1.97.0 only.

| Binary | Bytes |
| --- | --- |
| `verify-linked` | 103,560 |
| `verify-parent` | 31,888 |

| Recorded proof | Linked | Spawned | Difference |
| --- | --- | --- | --- |
| Tally update | 108,502,382 | 108,647,325 | +144,943 (0.13%) |
| Tally create | 105,835,593 | 105,980,550 | +144,957 |
| Counter update | 103,214,503 | 103,359,446 | +144,943 |

Before the pairing: 67,363 cycles linked, 206,168 spawned. The calibration replays and the
three `relayer_open` results were identical to the first run.

The recorded tally update costs 115,589,109 cycles as a whole transaction and 108,502,382
through `verify-linked`, both built with the pinned toolchain. The throughput spike's
binary verified the same proof with the same library in 114,906,306. The 7M spread is
between binaries, not between compilers, and its cause was not found. It is not binding
work: everything before the pairing costs under 0.1M here.

## Result on Rust 1.97.0 (10 November 2026, first run)

Not the pinned toolchain. The machine used could not download Rust 1.94.1 or the
RISC-V target. The scripts were built with Rust 1.97.0 (LLVM 22.1.6), `-Zbuild-std=core,alloc`
and `-C target-feature=-a,-zaamo,-zalrsc`; the harness used ckb-testtool 1.1.1 on Linux
x86_64. The pinned run above came out 3.5% higher in cycles and 35% larger in bytes.

Calibration: the two recorded tally transactions, replayed unchanged with their recorded
binaries, gave 115,589,109 (update) and 112,801,015 (create) cycles, equal to the
repository's records.

| Binary | Bytes |
| --- | --- |
| `verify-linked` (decode, key lookup, pairing) | 76,520 |
| `verify-parent` (decode, spawn, wait) | 19,320 |
| `private-tally` built the same way (for scale; 113,464 on the pinned toolchain) | 87,440 |

| Recorded proof | Linked | Spawned | Difference |
| --- | --- | --- | --- |
| Tally update | 104,860,094 | 105,002,719 | +142,625 (0.14%) |
| Tally create | 102,287,071 | 102,429,710 | +142,639 |
| Counter update | 99,755,219 | 99,897,813 | +142,594 |

Everything before the pairing (load, decode, key lookup) cost about 60,000 cycles linked
and 196,000 spawned.

| Public inputs | Small values (2, 3, ...) | Full-width values |
| --- | --- | --- |
| 1 | 96,487,596 | 99,025,865 |
| 2 | 96,759,036 | 101,882,832 |
| 4 | 97,261,777 | 107,355,844 |
| 6 | 97,817,752 | 113,209,741 |
| 8 | 98,338,518 | 118,691,747 |
| 16 | 100,552,784 | 141,414,297 |
| 32 | 105,146,625 | 186,363,736 |

Slope: about 0.28M cycles per small public input and 2.82M per full-width one, on a base of
about 96.2M. Payload, witness and key sizes of all 14 proofs matched 162 + 32n, 182 + 32n
and 302 + 32n bytes.

| Same proof | This build, verifier only | Recorded transaction, pinned build |
| --- | --- | --- |
| Tally update | 104,860,094 | 115,589,109 |
| Tally create | 102,287,071 | 112,801,015 |

The pinned run above showed this gap is mostly between binaries, not compilers.

## Fee inputs left open (`relayer_open` test)

The recorded tally update, with its recorded proof and the recorded pinned-build binary:

| Transaction | Result |
| --- | --- |
| A different funding Cell under a different Lock, different change output | accepted, 115,589,109 cycles |
| The original funding plus a second unrelated input and output | accepted, 115,591,669 cycles |
| Control: the tally successor's capacity raised by one shannon | rejected |

The proof authorizes the tally's transition whoever pays, and nothing else about the tally
Cell can be altered by the payer. This covers the tally only.

## What did not work

- `-C target-feature=-a` alone (the flag in `contracts/.cargo/config.toml`) failed on LLVM 22
  with `Cannot select: AtomicLoadAdd`. `-a,-zaamo,-zalrsc` built. A future toolchain bump
  of the repository will meet this.
- Building with the A extension enabled produced a binary that CKB-VM rejected
  (`InvalidInstruction`, an `lr.d`), under `data2` as well.
- The counter's recorded transaction is stored unsigned and was not replayed.
- Spawn was measured under `hash_type = data2` only, and only in ckb-testtool, not on a node.
