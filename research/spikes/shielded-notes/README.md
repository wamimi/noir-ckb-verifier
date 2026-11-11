# Spikes: what shielded notes cost, in constraints and in CKB-VM cycles

Research questions for [R2](../../shielded-notes.md):

1. How many R1CS constraints does Poseidon2 Merkle membership cost at depths 16, 20 and
   32, alone and inside a note-spending circuit, with the pinned backend?
2. How many CKB-VM cycles do the script-side accumulator operations cost: a Poseidon2
   tree append, and a sparse Merkle tree absence proof with insertion?

## What it is

- `constraints.py`: generates Noir circuits (membership; spend one note; 2-in 2-out
  join-split), compiles them with the pinned Nargo, lowers them with the pinned backend,
  checks the witness and reads the counts from `snarkjs r1cs info`.
- `vm/contracts/acc-bench`: one script with four operations (see its header), including a
  port of Noir's Poseidon2 permutation, checked in CKB-VM against the solver's own test
  vector.
- `vm/harness`: runs each operation in ckb-testtool. For the sparse Merkle tree it builds
  the tree on the host with the same hash, and requires the root the script computed to
  equal the host tree's root after the insertions.

## Command

```bash
research/spikes/shielded-notes/run.sh
```

Part 2 (constraints) runs when `NARGO`, `BACKEND_CLI` and `SNARKJS` are set.

## Result (11 November 2026)

Part 1 was run on the pinned toolchain (Rust 1.94.1 contracts, Rust 1.95.0 harness, clang
18, macOS ARM64); the cycle table below is from that run. An earlier run on Rust 1.97.0 is
kept in `results/` and was 4% to 5% lower on Poseidon2 and within 1% on the sparse tree.
Part 2 used the pinned Nargo 1.0.0-beta.18 and backend
`828025f` (built with Rust 1.97.0) and snarkjs 0.7.5.

### Constraints (`results/constraints-2026-11-11.json`)

| Circuit | Depth 16 | Depth 20 | Depth 32 | Public inputs |
| --- | --- | --- | --- | --- |
| Merkle membership only | 11,459 | 14,323 | 22,915 | 1 |
| Spend one note (ownership, membership, nullifier, 64-bit value, context) | 14,619 | 17,483 | 26,075 | 4 |
| Join-split, 2 notes in and 2 out, public in/out and fee | 32,134 | 37,862 | 55,046 | 10 |

One tree level costs 716 constraints (one Poseidon2 call plus the side selection). Every
witness satisfied its R1CS. Poseidon2 from `noir-lang/poseidon` v0.2.6, at most 3 inputs
per call.

### CKB-VM cycles, pinned toolchain (`results/vm-2026-11-11-pinned-macos-arm64.txt`)

Script size: 66,760 bytes.

| Operation | Cycles |
| --- | --- |
| One Poseidon2 permutation | 412,000 |
| Append one leaf, root recomputed, depth 16 / 20 / 32 | 6.62M / 8.27M / 13.23M |
| Append 2 leaves, root computed once, depth 20 / 32 | 8.69M / 13.64M |
| Append 64 leaves, root computed once, depth 20 / 32 | 34.4M / 39.3M (0.54M / 0.61M per leaf) |
| Sparse Merkle tree (BLAKE2b, 256 levels), one key: prove absent and insert | 0.93M (empty tree), 1.20M (1,000 keys), 1.28M (10,000 keys) |
| The same for 32 keys in one proof, 10,000-key tree | 36.28M (1.13M per key) |
| Proof bytes per key, 10,000-key tree | 564 for one key, 306 each for 32 |

Two keys already present were each refused as "absent". The two append methods gave the
same roots.

## What did not work

- `sparse-merkle-tree` 0.6.1 has a hard dependency on `blake2b-rs`, whose C source needs
  `<string.h>` and `<stdio.h>` and does not compile for the bare-metal target. Two shim
  headers (`vm/contracts/shim/string.h` and an empty `stdio.h`) make it build; the C code
  is never called. The spike was first delivered without `stdio.h`: it had been removed
  after a build that still had a cached object, and the first clean build on the pinned
  toolchain failed. `stdio.h` is used only by the library's `BLAKE2B_SELFTEST` code. It was
  added during the pinned rerun.
- A 100,000-key tree exhausted the memory of the machine building it on the host, so the
  largest tree measured is 10,000 keys.
- The spend and join-split circuits are for counting, not a reviewed design: the tags are
  small integers, the nullifier is derived from the commitment (the document chooses the
  leaf position instead), both join-split inputs use the same note, and there is no dummy
  input handling.
- No proving time was measured (R4).
- The Poseidon2 port was checked against one test vector (the all-zero state). That is not
  enough to rely on; see review item 3 in the R2 document.
