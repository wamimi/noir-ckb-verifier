# R5. Battleship: design note

Status: **design only, one page; nothing built; external review not done.** The spec is
[`spikes/toolkit-architecture/specs/battleship.toml`](spikes/toolkit-architecture/specs/battleship.toml)
and passes the linter. Battleship is the reference application for single-writer Cells
(R0 milestone M5).

## What it shows

Two players stake CKB on a game whose boards stay hidden. Every answer to a shot is proved
against a committed board, so nobody can lie about a hit, and a player who stops playing
loses. There are no signatures in the game itself: knowing a board's opening is the
authority to move, and the context digest binds each proof to one game Cell.

## State and actions

The Cell stores each player's fields under "mover" (must act next) and "waiter", plus
`status`, `pending` (the shot awaiting an answer) and `timeout`. Every turn swaps mover and
waiter with field-from-field checks in the script.

| Action | Proof | Script-side checks | Effect |
| --- | --- | --- | --- |
| `open` | `board`: the commitment opens to a legal fleet | counters zero, no opponent yet, `timeout ≥ 10` | First player waits; stake = Cell capacity |
| `join` | `join`: legal fleet, and `stake_out = 2 × stake_in` | status 0 → 1; first player becomes mover | Second player matches the stake |
| `turn` | `turn`: opens the mover's board; answers `pending` truthfully; adds a hit to the waiter's count if it hit; sets status 2 exactly when that count reaches 17; otherwise fires at a cell not fired at before | status is 1; the swap | One proof per turn answers the last shot and fires the next |
| `settle` | none | status is 2 | Pays `mover_lock`: after the last swap the mover is the winner |
| `timeout` | none | status ≤ 1; the Cell is at least `timeout` blocks old | Pays `waiter_lock`: nobody joined, or the mover stalled |

Board commitment: `H2(H2(TAG_BOARD, fleet), salt)` with Poseidon2, where `fleet` packs five
ships (position and orientation) into one field element and `salt` is fresh per game. The
circuit expands the fleet to a 100-bit map and checks bounds and no overlap.

## Budgets (estimates, from R0 and R4 measurements; nothing here was measured)

| Item | Estimate | From |
| --- | --- | --- |
| `turn`: 10 public inputs | 111M to 118M cycles per turn | R0 section 9 |
| `turn` circuit | 2,000 to 4,000 constraints: one board opening (about 1,430), a 100-bit map, one bit read and one bit write | R2: 713 constraints per hash |
| Browser proof per turn | about 0.1 s on a laptop, about 2 to 3 s on an entry-level phone | R4, tally (3,338 constraints) |
| Game length | at most 200 turns; 17 hits win | rules |
| Capacity | game Cell about 280 CKB plus the stakes | computed: 169 data bytes + 107 bytes of Cell overhead |
| Three circuits | three setups, each within a 2^12 powers-of-tau file | constraint estimates |

## The cheapest ways to break it, and why each fails

| Attack | Outcome |
| --- | --- |
| Lie about a hit, or play with no ships | No proof exists: the answer is checked against the committed, proven-legal fleet |
| Stop playing when losing | `timeout` pays the opponent the whole pot |
| Refuse to concede on the 17th hit | The honest `turn` sets status 2; refusing to send it is stalling, same outcome |
| A third party sends a turn | Needs the mover's board opening |
| Replay a turn in another game, or the same game later | Context holds the game id and the consumed OutPoint |
| Joiner rewrites the opponent's board, Lock or timeout | Refused by the linter rule found in R0: changed fields must be proven, pinned or declared free; `join` pins the opener's fields with field-from-field checks |
| Mover alters a field the proof does not cover during a turn | The swap checks pin every such field |
| Pay out to someone else | Payout Lock and amount are read from the Cell by the script |
| Fire twice at one cell to run the clock | The shots bitmap is in the proof |
| Reuse a board across games to learn it | Client rule: fresh salt and fleet per game; the commitment hides the fleet |

Not resolved:

- **Front-running `join`.** Two joiners race for one open game; the loser's transaction
  fails and costs nothing. Acceptable.
- **The winner must add a fee input to `settle`**, because the payout equals the Cell's
  capacity exactly. Any relayer can do it.
- **Timeout length is the opener's choice** (minimum 10 blocks). A short timeout favours
  whoever has the better connection.
- **A player who loses the board opening cannot move** and loses by timeout. The client
  stores it as the tally client stores its state.
- **The fleet encoding and the three circuits are not written.** The constraint numbers
  are estimates.

## Build steps (after R0 M1 to M4)

| # | Step | Acceptance test |
| --- | --- | --- |
| G1 | Three circuits with Noir tests | Illegal fleets, false answers, repeated shots and wrong hit counts fail |
| G2 | Script generated from the spec | Generated matrix and source mutations pass (`noir-ckb test`) |
| G3 | Local game | A scripted full game, a stalled game and an unjoined game end with the right payout |
| G4 | Testnet, two browsers | Two outside players finish a game; times per turn recorded |
