# Ballot vote circuit (`noir-ckb/ballot-box/v1`)

The circuit a voter proves to cast one vote in a ballot box. It is the circuit named by
`[binding.circuit.vote]` in
[`research/spikes/toolkit-architecture/specs/ballot-box.toml`](../../research/spikes/toolkit-architecture/specs/ballot-box.toml).
Only the circuit exists: no Type Script, no ballot box Cell, no client and no ceremony.
Nothing here is deployed.

## Statement

The prover knows a `secret` and a Merkle path such that:

1. **Membership.** `identity(secret)` is a leaf of the voter tree whose root is the public
   `voter_root`.
2. **Election-scoped nullifier.** The public `nullifier` equals
   `nullifier(secret, election_lo, election_hi)`. It is a function of the secret and the
   election id only, so one voter has one nullifier per election whatever the choice, and
   another nullifier in every other election.
3. **Binary choice.** The public `choice` is 0 or 1.

`ctx_lo` and `ctx_hi` are the two 128-bit halves of the context digest that the Type Script
will rebuild from the transaction. The circuit range-checks them and does nothing else with
them. The binding spec puts the nullifier and the choice into that digest.

One proof carries one nullifier. A vote transaction built for this circuit inserts exactly
one key into the ballot box's nullifier set.

## Hashes

Poseidon2 over BN254 as in `noir-lang/poseidon` v0.2.6, two or three inputs per call.

```
identity  = Poseidon2([TAG_IDENTITY, secret])
node      = Poseidon2([TAG_NODE, left, right])
election  = Poseidon2([TAG_ELECTION, election_lo, election_hi])
nullifier = Poseidon2([TAG_NULLIFIER, secret, election])
```

Each tag is the big-endian integer of the ASCII string `noir-ckb:ballot:v1:<name>` with
`<name>` one of `identity`, `node`, `election`, `nullifier` (23 to 28 bytes, below the
field modulus). Leaves and inner nodes are in different domains. An empty leaf is not
defined by the circuit; whoever builds the voter tree chooses a filler that is not the
identity commitment of a known secret.

The tree has depth 19 (524,288 leaves). Path bit `b_i` is 1 when the running node is the
right child at level `i`, counted from the leaf.

## Inputs

Private first, then public, all `Field`:

| Order | Name | Visibility |
| --- | --- | --- |
| 1 | `secret` | private |
| 2 to 20 | `s0` .. `s18`, the path siblings, leaf level first | private |
| 21 to 39 | `b0` .. `b18`, the position bits | private |
| 40 | `voter_root` | public |
| 41, 42 | `election_lo`, `election_hi`: the ballot box's 32-byte Type ID as two 128-bit halves | public |
| 43 | `nullifier` | public |
| 44 | `choice` | public |
| 45, 46 | `ctx_lo`, `ctx_hi` | public |

The path is 40 scalar parameters and not two arrays because the toolkit and the pinned
backend's public-input layout correction cover scalar `Field` parameters only.

## Packages

A workspace of its own, separate from `circuits/private-tally-v2`.

| Package | Kind | Content |
| --- | --- | --- |
| `hashes` (`ballot_hashes`) | library | tags, the four hashes, `root_from_path` |
| `vote` (`ballot_vote`) | binary | the statement, with 21 tests |
| `helper` (`ballot_helper`) | binary | returns identity, root and nullifier for given inputs; executed, never proved |

## Commands

```bash
cd circuits/ballot && nargo test --workspace
python3 -m unittest scripts/tests/test_ballot_vote_circuit.py
scripts/check-ballot-vote-circuit.py --out target/ballot-vote-check --noir-cli /path/to/noir-cli --dev-key
```

The last command needs Nargo 1.0.0-beta.18, the pinned backend's `noir-cli` and snarkjs
0.7.5. It compiles a private copy of the workspace, runs each case through `nargo execute`
and through the backend's R1CS, checks the public wire layout, prints the counts and scans
the kept files for voter secrets and identity commitments. `--dev-key` adds a throwaway
single-party key, one proof and three verifications.

## Result (15 November 2026)

Nargo 1.0.0-beta.18 (`99bb8b5c`, official Linux x86_64 binary), `noir-lang/poseidon`
v0.2.6 (`00f87918`), backend `828025f`, snarkjs 0.7.5. The backend's `noir-cli` was built
with Rust 1.97.0, not the pinned host Rust 1.95.0. Not yet repeated on the pinned macOS
toolchain.

This run was at depth 20. The depth was then set to 19, which the depth table below puts
at 16,255 constraints and a power-14 setup; the run has not been repeated at depth 19.

| Item | Value |
| --- | --- |
| Noir tests | 26 passed (5 in `hashes`, 21 in `vote`) |
| Differential cases, Noir execution against backend R1CS | 25 of 25 agreed: 8 accepted, 17 rejected |
| R1CS | 16,971 constraints, 16,993 wires, 41 private and 7 public inputs, 0 outputs |
| R1CS identical across accepted cases | yes (one SHA-256) |
| Public values in wires 1 to 7, in the listed order | yes, in every accepted case |
| Powers of tau needed | 2^15 (16,979 rows: constraints, public inputs and one) |
| Fits the private tally's 2^12 file (4,096) | **no** |
| Throwaway development key | local powers of tau of power 15, one contribution; proof verified; the same proof was rejected with the other choice and with another nullifier; proof time 3.3 s on a 2-core server (snarkjs, Node); key 9.6 MB; setup 13 min. Key and powers-of-tau file were deleted with the run |
| Leak scan | 14 values (7 voter secrets, 7 identity commitments), 0 hits. The run keeps one file, `results.json`, so the scan covers little: its use is to catch a later change that starts keeping more |

### The circuit does not fit a 2^12 setup

The private tally's ceremony used a powers-of-tau file of power 12. This circuit is more
than four times that size. One tree level costs 716 constraints and everything else costs
2,651 (three hashes and four 128-bit range checks), measured by compiling the same source
at other depths:

| Depth | Voters | Constraints | Power needed |
| ---: | ---: | ---: | ---: |
| 1 | 2 | 3,367 | 12 |
| 2 | 4 | 4,083 | 12 |
| 3 | 8 | 4,799 | 13 |
| 7 | 128 | 7,663 | 13 |
| 8 | 256 | 8,379 | 14 |
| 16 | 65,536 | 14,107 | 14 |
| 19 | 524,288 | 16,255 | 14 |
| 20 | 1,048,576 | 16,971 | 15 |

A power-12 setup holds an electorate of four. A ballot box for real use needs its own
setup of power 14 or 15. Depth 19 is the largest tree that fits power 14; depth 20, the
depth the research budget assumed, is 595 constraints over that line and needs power 15.
The depth is one constant plus the parameter lists, and has to be fixed before any
ceremony, because changing it changes the R1CS.

## What the circuit does not do

- It does not decide who is in the voter tree. One vote per enrolled secret is all it
  gives; one person per secret is a matter of enrollment.
- It does not hide the choice. The choice is public by design.
- It does not prevent a second vote by itself. The Type Script must refuse a nullifier
  that is already in the set.
- It does not make a vote appear on chain. A relayer or miner can leave a ballot out.
- `secret` is the only key. Whoever learns it can compute that voter's nullifier for any
  election and see whether and how they voted.
- No review of this circuit has taken place.
