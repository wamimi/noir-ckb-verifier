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

**Part 1 was not run on the pinned toolchain**: Rust 1.97.0 (LLVM 22.1.6), `-Zbuild-std`,
ckb-testtool 1.1.1, Linux x86_64. On the two earlier spikes the pinned build came out 2% to
3.5% slower than this one. Part 2 used the pinned Nargo 1.0.0-beta.18 and backend
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

### CKB-VM cycles (`results/vm-2026-11-11-rust-1.97.0-build-std.txt`)

Script size: 48,128 bytes.

| Operation | Cycles |
| --- | --- |
| One Poseidon2 permutation | 394,000 |
| Append one leaf, root recomputed, depth 16 / 20 / 32 | 6.34M / 7.92M / 12.67M |
| Append 2 leaves, root computed once, depth 20 / 32 | 8.32M / 13.07M |
| Append 64 leaves, root computed once, depth 20 / 32 | 32.9M / 37.7M (0.51M / 0.59M per leaf) |
| Sparse Merkle tree (BLAKE2b, 256 levels), one key: prove absent and insert | 0.93M (empty tree), 1.19M (1,000 keys), 1.27M (10,000 keys) |
| The same for 32 keys in one proof, 10,000-key tree | 35.97M (1.12M per key) |
| Proof bytes per key, 10,000-key tree | 564 for one key, 306 each for 32 |

Two keys already present were each refused as "absent". The two append methods gave the
same roots.

## What did not work

- `sparse-merkle-tree` 0.6.1 has a hard dependency on `blake2b-rs`, whose C source needs
  `<string.h>` and does not compile for the bare-metal target. A one-file header shim
  (`vm/contracts/shim/string.h`) makes it build; the C code is never called.
- A 100,000-key tree exhausted the memory of the machine building it on the host, so the
  largest tree measured is 10,000 keys.
- The spend and join-split circuits are for counting, not a reviewed design: the tags are
  small integers, the nullifier is derived from the commitment (the document chooses the
  leaf position instead), both join-split inputs use the same note, and there is no dummy
  input handling.
- No proving time was measured (R4).
