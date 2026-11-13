# R0. Toolkit architecture: the `[binding]` format and the generator

Status: **design complete; external review not done (section 13).** Nothing in this work changed
`circuits/private-tally-v2`, `ceremony/` or either deployed script.

Every statement is tagged: **measured** (a number from a run, with its file), **source**
(read in the cited code or RFC), **spike** (result of code under
[`spikes/toolkit-architecture`](spikes/toolkit-architecture/README.md)), **computed**
(arithmetic on sourced values) or **estimate**.

Wording used throughout, decided on 10 November 2026: a generated script binds a proof to
**one exact state transition of one Cell**. It does not bind a proof to one exact
transaction unless the spec asks for it. The reason is a recorded case: in
`update-unrelated-change` the tally's own matrix accepts one proof in two different
transactions that differ only in the fee change output (section 3.6).

## 1. Problem and definition of done

A developer writes a rule in Noir. `noir-ckb` must turn that circuit plus a short
description of the Cell it governs into a CKB Type Script that accepts a proof only for
the state transition the proof was made for, together with the tests that show it.

Today that script is written by hand twice (`owned-counter`, 190 lines; `private-tally`,
223 lines). The files share most of their text and differ in a small number of decisions.
The format captures those decisions, and the ones a game, a ballot box and a note pool add.

| # | Test a third party can run | State |
| --- | --- | --- |
| D1 | Five specs (counter, tally, Battleship, ballot box, shielded pool) pass the linter | Passed (spike) |
| D2 | A reader of the counter and tally specs reaches the result of the hand-written scripts on the recorded CKB-VM cases, up to the pairing | Pre-pairing agreement on the recorded subset: 49/49 and 48/48 (spike). An accepted proof and a pairing failure are not told apart, and `v1`, `since`, effects and named outputs have no recorded cases |
| D3 | The linter refuses a list of unsafe specs, each for a named reason | 29 of 29, each for the expected reason (spike) |
| D4 | The generated tally and counter scripts accept the recorded proofs with a byte-identical public vector, and reject the recorded rejections | Not built (milestone M2) |
| D5 | The generated matrix contains every operator of section 8 and every source mutation is detected | Not built (M3) |
| D6 | Battleship, generated from its spec, plays a full game on a local chain | Not built (M5) |
| D7 | A circuit not written by the maintainer goes from `nargo new` to a testnet transaction; time recorded against the 15-minute target | Not built (M6) |

## 2. Facts the design rests on

| Fact | Value | Basis |
| --- | --- | --- |
| Proof payload | `Groth16Witness` Molecule table: version, proof (128 bytes), public vector (`u32` count + 32 bytes each) | source: `groth16-ckb@d64c769` `schemas/groth16.mol`, `wire-decode/src/lib.rs` |
| Sizes for n public inputs | payload 162 + 32n; witness 182 + 32n; key Cell data 302 + 32n bytes | computed; confirmed on 14 generated proofs, n = 1 to 32 (spike) |
| Fixed buffers in both scripts | witness 512 bytes, key 512 bytes | source: both `main.rs` |
| `wire-decode` checks | Molecule structure and version only; not that public values are below the modulus | source |
| Verification cycles, small public values | 96.5M (n = 1) to 105.1M (n = 32): about 0.28M per input | spike, Rust 1.97.0 build |
| Verification cycles, full-width public values | 99.0M (n = 1) to 186.4M (n = 32): about 2.82M per input | spike, Rust 1.97.0 build |
| Recorded whole transactions, pinned build | counter update 111.2M; tally create 112.8M, update 115.6M | measured: `target/.../results.json`, `evidence/` |
| Same tally proofs, verifier only, pinned build | create 105.8M, update 108.5M (102.3M and 104.9M on Rust 1.97.0) | spike |
| Spawning the verifier instead of linking it | +144,900 cycles (0.13%); thin script 31,888 bytes against 103,560 linked | spike, pinned build |
| Type Script with the verifier linked in | 113,464 bytes (tally on testnet) | measured: `evidence/private-tally-testnet.md` |
| Script groups and witnesses | A Type Script runs once per group of inputs and outputs with the identical script; group input i reads the witness at that input's position | source: RFC 0022 |
| Transaction hash | Covers every field except `witnesses` | source: RFC 0022, appendix A |
| `since` | Expresses "not before" only | source: RFC 0017 |
| Consensus cycle limit | Per block only (`max_block_cycles`) | source: RFC 0014 |

The placement numbers were measured on the pinned toolchain (11 November 2026). The two
public-input rows were measured only on Rust 1.97.0, which came out 3.5% faster than the
pinned build on the placement measurements. One thing stays unexplained: the same library
verified the same tally update proof in 108.5M cycles in one pinned binary, 114.9M in
another, and the recorded transaction costs 115.6M. The spread is between binaries; the
binding checks account for under 0.1M of it. Budgets below therefore carry a range, not
one number.

"About 117M cycles regardless of circuit size" did not hold as stated. Circuit size does
not enter verification. The number of public inputs does, and their size matters ten times
more than their count: about 10,000 cycles per significant bit (computed from the two
slopes).

## 3. The `[binding]` format, version 2

Version 1 is the `[binding]` table in today's `noir-ckb.toml`. Version 2 replaces it.
Complete specs for the five applications:
[`spikes/toolkit-architecture/specs/`](spikes/toolkit-architecture/specs/).

### 3.1 Design rules

1. **Noir is the rule language; the script has a small fixed set of checks.** There are no
   expressions and no hand-written Rust hooks. Rules about values are written in the
   circuit. For actions that carry no proof the script offers three declarative checks and
   nothing else (section 3.4): equality with a constant, comparison with a constant, and
   equality of one field with another.
2. **Two channels.** A fact the circuit must reason about is a public input of its own
   (*statement*). A fact that only has to be pinned goes into one BLAKE2b-256 digest that
   enters the circuit as two 128-bit public inputs (*context*). The circuit range-checks
   the two halves and does nothing else with them.
3. **Fixed width everywhere.** Cell data, args and every context item have a fixed length.
4. **Unchanged unless declared, and declared means constrained.** On an update the Lock,
   the capacity and every data field must be equal before and after unless listed under
   `change`; on creation all of them count as changed. One analysis covers data fields, the
   Lock and the capacity alike. Each changed property must be exactly one of: *proven* (a
   statement public input, in full: both halves of a 32-byte value); *pinned* (by the Lock
   rule, or by an equality check whose other side is a constant or is itself anchored,
   section 3.4); the target of an effect; or declared `free` and, when the action has a
   proof, committed in the context. Being in the context is not a constraint: it stops a
   third party from altering a value, but the prover chooses it.
5. **One spec, one script, one kind of Cell, one application Cell per transaction.**
6. **The generator fails closed.** A spec the linter refuses produces no script.
7. **Shared mode follows single-writer mode.** The generator is built for single-writer
   Cells first (milestones M1 to M6). Shared mode (section 3.8) and effects were gated on
   R2's measurements; R2 found them affordable (a nullifier insertion costs about 1.2M
   cycles), and the grant deliverable decided on 11 November 2026 is the ballot box, so
   shared mode is in scope as milestone M7.

### 3.2 Structure

```toml
[binding]
format    = 2
profile   = "noir-ckb/private-tally/v2"   # hashed into every context
placement = "type"                         # "type" | "lock" (section 6)
envelope  = "bare"                         # "bare" | "v1"   (section 3.5)
hash_type = "data1"

[binding.circuit.tally]                    # an application may have several circuits
package = "circuits/private-tally-v2/circuit"
public  = ["c_old", "c_new", "ctx_lo", "ctx_hi"]   # must equal the compiled ABI order

[binding.cell]
args = [{ name = "version", type = "u8", const = 1 }, { name = "id", type = "type_id" }]
data = [{ name = "version", type = "u8", const = 1 },
        { name = "commitment", type = "field", nonzero = true }]
lock = { code_hash = "pin:guard", hash_type = "data1", args = "0x" }

[[binding.action]]
name    = "update"
id      = 1                                # one byte, hashed into the context
shape   = "update"                         # "create" 0→1 | "update" 1→1 | "destroy" 1→0
circuit = "tally"                          # omit for an action without a proof
proof   = "input_type"
change  = ["data.commitment"]
public  = { c_old = "in.data.commitment", c_new = "out.data.commitment",
            ctx_lo = "context.lo", ctx_hi = "context.hi" }
context = ["tag:noir-ckb/private-tally/context/v2", "network", "profile", "script_hash",
           "args.id", "action", "in.outpoint", "public.c_old", "public.c_new",
           "out.lock_hash", "out.capacity"]
```

Field types: `u8`, `u16`, `u32`, `u64`, `u128` (little-endian), `field` (32 bytes,
little-endian, below the BN254 scalar modulus; `nonzero` optional), `bytes32`, `type_id`,
each with an optional `count`. `const` fixes a value.

`pin:<name>` is a 32-byte value compiled into the script: the network (genesis hash), Lock
code hashes, the verifier code hash, and one key data hash per circuit. Key pins are
derived by the tool from the setup and cannot be written by hand.

### 3.3 Sources

| Source | Bytes | Meaning |
| --- | --- | --- |
| `in.data.<f>`, `out.data.<f>`, `args.<f>` | field width | A field of the consumed Cell, the successor, or the args |
| `in.data`, `out.data` | whole data | Context only |
| `in.outpoint` | 36 | OutPoint of the consumed application Cell |
| `in.capacity`, `out.capacity` | 8 | |
| `in.lock_hash`, `out.lock_hash` | 32 | |
| `<name>.lock_hash`, `.capacity`, `.type_hash`, `.data_hash` | 32 / 8 | A named output of the action |
| `network`, `profile`, `script_hash`, `action` | 32, 32, 32, 1 | Genesis hash pin; BLAKE2b of the profile string; hash of the running script; action id |
| `tx_hash` | 32 | Opt-in: binds the proof to the whole transaction (section 3.6) |
| `tag:<text>` | text + one zero byte | Context only; domain separation |
| `zero`, `zero:<n>`, `const:<int>` | | Constants |
| `public.<name>` | 32 | A public input of this action |
| `witness` | 32 | Public input taken from the payload as sent; the script checks it is below the modulus |
| `any:<array field>` | 32 | Public input equal to one element of a data array (shared mode) |
| `context.lo`, `context.hi` | 16 each | The halves of the context digest |
| `aux.<i>` | variable | Unproven helper data in the envelope (shared mode) |

A 32-byte source used as a public input takes two public inputs, `<source>:lo` and
`<source>:hi`. Integers are the cheapest public inputs: cost follows bit length (section 2).

### 3.4 What an action may contain

| Key | Checked by the script |
| --- | --- |
| `shape` | Number of application Cells consumed and created. Cells with the same code but other args count too, so two instances never share a transaction |
| `change` | The only parts allowed to differ between input and successor |
| `require = [...]` | The declarative checks, below |
| `free = [...]` | Data fields, `lock` or `capacity` that the creator or prover chooses. With a proof each must be in the context |
| `signer = "out.lock_hash"` | Input 0 of the transaction has the successor's Lock hash (input 0 is the input the Type ID is derived from; the deployed counter checks the same input). It exempts a proof-less creation from rule 4 only under a Lock rule that pins the Lock's code and declares `signs = "transaction"`, see below |
| `since = { kind, min }` | The consumed Cell's `since` is of this kind and at least `min`; consensus enforces the wait (RFC 0017) |
| `outputs = { name = {...} }` | A further output with these properties must exist (a payout); two named outputs may not be the same output. Decided after review, not in the spike: a named output must have no Type and empty data unless the spec states `type_hash` and `data_hash`, because a Type can restrict spending of an output whose Lock is right (RFC 0022: Lock and Type run independently) |
| `circuit`, `proof`, `public`, `context` | The proof, where it sits, and the two channels |
| `shared`, `effects` | Shared mode; specified, not generated in version 2 |

The declarative checks are exactly these three forms. `left` and `right` are sources.

```toml
require = [
  { left = "in.data.status",       op = "eq", const = 1 },                       # equality with a constant
  { left = "out.data.timeout",     op = "ge", const = 10 },                      # eq ne lt le gt ge, integers up to 128 bits
  { left = "out.data.mover_lock",  op = "eq", right = "in.data.waiter_lock" },   # field from field, equal widths
]
```

An `eq` check pins a successor property only when its other side is *anchored*: a constant;
a value of the consumed Cell, the args or a compiled pin; or another successor property that
is unchanged or already proven, pinned or an effect target. An equality with a witness
value, a `free` property or a second unpinned property pins nothing, and the linter refuses
the spec (two fields set equal to each other and to nothing else are the simplest case).
Ordering checks do not pin a field and are not allowed on hashes or field elements. There is
no arithmetic and no conditional: anything beyond these three forms is a circuit rule.

`signer` and what it does not prove. A matching Lock hash on an input shows that the Lock
script ran; what its witness covers is the Lock's own business (RFC 0022). The format
therefore accepts `signer` as a reason to leave a creation's data, Lock and capacity
otherwise unconstrained only when the Lock rule pins the Lock's code and carries
`signs = "transaction"`. That key is the spec author's statement that the pinned code
checks a signature over the transaction hash, as secp256k1-blake160 sighash-all does; the
linter cannot verify it and the build output prints it as an assumption. Without it the
creation needs explicit constraints like any other action.

### 3.5 Selecting the action, and the payload envelope

`envelope = "bare"`: the payload is the `groth16-ckb` wire witness and the shape selects
the action. Used by the two deployed profiles; requires one action per shape.

`envelope = "v1"`, for every new profile:

```
vector Bytes    <byte>;
table BindingPayload {
    action:  byte,      // selects among actions; also a mandatory context item
    outputs: Bytes,     // one byte per named output of the action, in declared order: its output index
    proof:   Bytes,     // Groth16Witness, or empty for an action without a proof
}
```

It sits in `WitnessArgs.input_type` of the application input, or `output_type` at the
application output's index on creation. Taking the action byte from the witness is safe
because the same byte is in the context: a proof made for one action fails the public
vector comparison under another, and an action without a proof is fully decided by its
checks. Shared mode adds an `aux` field in a later envelope version.

Size (computed from the schema, checked by the external review): the table costs 16 bytes of
header, 1 action byte and two 4-byte length prefixes, so a `v1` payload is 25 bytes plus
one byte per named output longer than the bare payload. An earlier version of this document
said 12.

### 3.6 The context digest, and what "bound" means

`context` is an ordered list of sources; the digest is
`blake2b_256("ckb-default-hash", item_0 ‖ item_1 ‖ ...)`. An ordered list lets the two
deployed layouts be written exactly.

Every context must start with a `tag:`, contain `network`, `profile`, `script_hash` and
`action`, and contain a **freshness anchor**: `in.outpoint`; or `tx_hash`; or, on
creation, a `type_id` args field.

**Default: one exact state transition of one Cell.** With `in.outpoint` as anchor the proof
authorizes spending this OutPoint into this successor. Everything else in the transaction
is open: fee inputs, change, other Cells. This is deliberate, so that anyone can pay the
fee, and it is what the deployed scripts do. The recorded evidence is the matrix case
`update-unrelated-change` (tally) and `unrelated-change-capacity` / `unrelated-change-data`
(counter): the proof of the valid case is accepted unchanged in a transaction whose change
output differs, that is, in a different transaction.

**Opt-in: one exact transaction.** Adding `tx_hash` to the context binds the proof to every
non-witness byte of the transaction. Nobody can then add or change an input or output
after the proof is made; the prover must know the fee inputs before proving.

What the default leaves to the application: a transaction may contain other scripts'
Cells. A design in which some other script treats "this application Cell was updated in
my transaction" as permission for something must use `tx_hash` or bind that other Cell as
a named output.

### 3.7 Placement

`placement = "type"`: the script runs when the Cell is created, updated or destroyed.
`placement = "lock"`: it runs only when the Cell is spent and cannot constrain creation.
Section 6 compares them. Generator version 2 emits Type Scripts only.

### 3.8 Shared Cells

OutPoint binding is correct for a Cell with one writer at a time. For a ballot box or a
pool it is wrong: the OutPoint changes whenever anyone else's transaction lands first, and
every pending proof dies.

An action marked `shared = true` therefore may not read `in.outpoint`, `tx_hash`,
whole-data sources, capacities, or any data field some action can change, in its public
inputs or context. It may read immutable fields, `any:` membership in a ring of recent
roots, and witness values anchored by a nullifier that a `set-insert` effect records. The
mutable part of the Cell is updated by effects (`set-insert`, `tree-append`, `add`,
`capacity-add`, `capacity-sub`) computed by the script when the transaction is assembled,
so a relayer can rebuild the transaction around the same proof.

This moves hashing work into CKB-VM. R2 measured it on the pinned toolchain: about 1.2M
cycles to prove a nullifier absent and insert it, and 8.3M to append one commitment to a
depth-20 Poseidon2 tree (0.54M each in a batch of 64). The ballot box needs only the
first. The spike linter still labels these specs "specified only"; the generator accepts
them from milestone M7.

CKB cannot express "not after" (RFC 0017), so a ballot box cannot refuse votes after a
time. The spec uses an explicit `close` action that anyone may send once `close_after` has
passed; ballots are accepted until that transaction lands. VoteSecure's architecture
(v2.3, a design proposal) has the same shape and states the same limit: "nothing in a
script closes at a time; only a state change (SEAL) closes the box", with the close rule
listed among its open problems.

### 3.9 Generated check order and error codes

Cheapest first, pairing last; codes 40 to 54 are those of the deployed scripts.

| Step | Check | Code |
| --- | --- | --- |
| 1 | Args length, constants, own `hash_type` | 41 |
| 2 | Fewer than 64 inputs, outputs and resolved dependencies | 52 |
| 3 | Shape; one application Cell per side; envelope and action | 42, 48 |
| 4 | Type ID on creation | 44 |
| 5 | Successor: Lock rule (45), data length and constants (43), field values (54) | |
| 6 | Consumed Cell: the same three | |
| 7 | Unchanged unless declared: Lock (46), capacity (47), data fields (55) | |
| 8 | `require` (53), `since` (56), `signer` (46), named outputs (57) | |
| 9 | Proof payload present, within the computed size, well formed | 48 |
| 10 | Public vector rebuilt from the transaction equals the payload's | 49 |
| 11 | Exactly one dependency with the pinned key hash | 50 |
| 12 | Groth16 verification | 51 |

### 3.10 Linter rules

A spec is refused when:

1. a circuit's `public` list differs from the compiled Noir ABI, or an action's map does not cover it exactly;
2. a context lacks a tag, a mandatory item or a freshness anchor;
3. a source does not exist for the action's shape or placement;
4. a changed data field, a changed Lock or a changed capacity (all of them, at creation) is neither proven, pinned, an effect target nor declared `free`; context alone is refused, with that reason; an equality whose other side is not anchored is refused, with that reason; one half of a 32-byte value as a public input is refused;
5. a `free` data field, Lock or capacity of a proven action is missing from the context;
6. `signer` is used as an exemption without a Lock rule that pins the code and declares `signs = "transaction"`, or is not `out.lock_hash`;
7. a `witness` public input is used nowhere;
8. a check is not one of the three forms, compares different widths, or orders a hash;
9. a `shared` action's proof reads anything another user's action can change;
10. `envelope = "bare"` is used with two actions of one shape; action ids repeat; two named outputs could coincide;
11. a circuit has more than 16 public inputs; a field count is not a positive integer; `envelope`, `hash_type`, `verifier`, the proof location or a `since` kind is outside its closed list; a `signer` or `since` source does not exist;
12. `verifier = "spawn"` is used without `hash_type = "data2"`.

The spike linter is still a Python program over a parsed TOML dictionary. The generator
needs a closed, typed schema that rejects unknown keys before any of these rules run
(milestone M2); until then "lints" means "passed these rules", not "has a defined meaning
for every key".

### 3.11 The five applications

| Application | Proofs | Uses | Generator v2 | Status |
| --- | --- | --- | --- | --- |
| Owned counter | update | `signer` and one `require` on a proof-less creation; Lock pinned by type hash with its code pinned by data hash | yes | Spec agrees with the deployed script on 48 of 48 recorded cases |
| Private tally | create, update | core only | yes | Spec agrees on 49 of 49 recorded cases, two runs |
| Battleship | open, join, turn (3 circuits, 10 public inputs on `turn`) | `v1` envelope, `require` in all three forms, `since`, payouts; two proof-less endings | yes | Lints; R5 completes it |
| Ballot box | vote | `shared`, nullifier anchor, effects, explicit `close` | from M7; the grant deliverable | Lints |
| Shielded pool, single Cell variant | deposit, transfer, withdraw | the above plus `any:`, tree append, capacity effects, bound payout | next phase, not a grant deliverable | Lints; layout confirmed by R2 |

Battleship shows what the three checks buy. The players' fields are stored as "mover" and
"waiter" and every turn swaps them with field-from-field checks. The circuit then never
needs to know who is A or B, a finished game pays `mover_lock`, and a stalled game pays
`waiter_lock` after a `since` wait: two proof-less endings instead of the five the first
draft needed with constants only.

### 3.12 Evidence

Command: `research/spikes/toolkit-architecture/run.sh`.

- Reader against recorded CKB-VM results, pre-pairing agreement on the recorded subset:
  tally 49/49 (ceremony-key run) and 49/49 (development-key run); counter 48/48, two of
  them rejected by the secp256k1 Lock, which is outside the spec. Same error code wherever
  the hand-written script rejected before the pairing. The pairing was not evaluated, so a
  recorded acceptance and a recorded error 51 both count as agreement. This shows that the
  format can state the two deployed rule sets; it does not show that generated Rust would
  be correct, and it says nothing about `v1`, `since`, effects or named outputs.
- Weakened tally specs disagreed with the record (13, 2 and 38 mismatches).
- 29 unsafe or malformed spec edits were each refused, and each for the expected reason
  (the test fails if a spec is refused for another reason). Three were not refused by the
  first linter: a joiner able to rewrite the opponent's fields because only the context
  covered them; a free field outside the context; a creation whose Lock and capacity nobody
  stated. The external review (section 13) then found that the fix had been applied to data
  fields only. Before the correction of 11 November 2026 the linter accepted a changed Lock
  or capacity that was merely mentioned in the context, a free Lock or capacity outside the
  context, an equality with an unconstrained field, one half of a hash as a proof of the
  whole, and a `signer` under any Lock. Seventeen cases were added for these.
- Three of the five specs failed the corrected linter and were changed. The tally creation
  and Battleship `open` left the capacity to the creator with only the context naming it:
  both now declare `free = ["capacity"]`, which is what the deployed tally does. The counter
  creation relied on `signer` under a Lock rule that did not say what the Lock signs: its
  Lock rule now carries `signs = "transaction"`. None of the three changes alters what a
  script would check; they make an existing choice explicit.

### 3.13 What held and what broke

| Belief or goal | Result |
| --- | --- |
| "Binds each proof to one exact transaction" | **Broke as worded** (section 3.6). Reworded to "one exact state transition of one Cell"; `tx_hash` is the opt-in. |
| "The binding leaves fee inputs open so any relayer can pay safely" | **Held for the tally in an experiment.** The recorded update proof was accepted, with the recorded binary, in a transaction funded by a different Cell under a different Lock and in one with an extra unrelated input and output; a one-shannon change to the tally successor's capacity was rejected (spike, `relayer_open`). For generated applications it holds only because rules 4 to 6 force every changeable part to be constrained; operators A2 and A3 in section 8 repeat the experiment per application. |
| OutPoint binding suits every application | **Broke** for shared Cells (3.8). |
| Being in the context digest constrains a value | **Broke.** It only fixes the prover's choice. Found by a negative test on Battleship `join`. |
| Every context item is tested by the existing matrices | **Broke.** `out.lock_hash` and `out.capacity` on update are shadowed by an earlier check; no transaction can make the digest decide (operator S1). |
| The linter rules for "pinned", "bound" and `signer` were complete | **Broke** in external review (section 13, findings 1, 2, 5): the rules were syntactic and covered data fields only. |
| The 512-byte buffers are general | **Broke**: 6 public inputs at most (section 4). |
| "About 117M cycles regardless of circuit size" | **Broke as stated** (section 2): 96M to 186M depending on the public inputs. |
| A deadline can close a vote | **Broke** (3.8). |

### 3.14 What version 2 cannot express

- Arithmetic or conditions outside a circuit. Battleship's stake rule (`out = 2 × in`) is a
  circuit rule with both capacities as public inputs.
- Variable-length state, more than one application Cell per transaction, several proofs
  in one transaction (R3).
- "Not after" conditions (a CKB property).
- An application Type on a Cell that already has another Type, such as xUDT: a Cell has
  one Type slot (RFC 0022).

## 4. The public-input limit

**Where the limit is.** Both scripts read the witness and the key into stack arrays:
`let mut buf = [0u8; 512]` in `proof_payload` (tally) or `run` (counter), and
`let mut vk_buf = [0u8; 512]` in `run`. A longer witness returns error 48, a longer key
error 50. With 302 + 32n key bytes the key buffer allows n ≤ 6. A bare `WitnessArgs` with
nothing else in it is 182 + 32n bytes, so the witness buffer allows n ≤ 10; with the `v1`
envelope it is 207 + 32n plus one byte per named output, which allows n ≤ 9 (527 bytes at
n = 10, 719 at n = 16; computed, confirmed by the review's `check_sizes.py`). Anything else
in the same `WitnessArgs`, such as a Lock signature of 65 bytes plus its 4-byte prefix,
comes on top. Both deployed applications use n = 4. Battleship's `turn` uses 10.

**What raising it costs.**

| Cost of one more public input | Value | Basis |
| --- | --- | --- |
| Witness bytes in every transaction | 32 | computed |
| Key Cell capacity, once per circuit | 32 CKB | computed |
| Cycles, small value (a counter, a flag) | about 0.28M | spike |
| Cycles, 128-bit value (a context half, a bitmap) | about 1.6M | estimate from the per-bit slope |
| Cycles, full-width value (a commitment, a root) | about 2.82M | spike |
| Script memory | none that matters: n = 32 needs 1.2 KB and 1.3 KB buffers | computed |

**Options compared.**

| Option | Effect | Verdict |
| --- | --- | --- |
| A. Buffers sized by the generator from n | Removes the limit; costs as above | **Chosen** |
| B. Pack several small integers into one field element, unpacked in the circuit | Saves 32 bytes per packed input; saves almost no cycles, because cost follows bits, and adds range constraints | Not in version 2 |
| C. Hash the statement values into one digest in the script | Needs a circuit-friendly hash in CKB-VM; cost unknown until R2 | Not in version 2 |
| D. Move bind-only facts to the context | Free: the context is two 128-bit inputs however many facts it holds | Already rule 3.1.2 |

**Decision.** The generator computes the key buffer from n and the witness buffer from the
Molecule schema (n, the envelope and the named outputs) plus a declared allowance for the
other `WitnessArgs` fields (`limits.witness_other`, default 0 for a Type under a guard
Lock; a co-located Lock signature must be declared). It refuses n > 16.
At 16 full-width inputs verification measured 141M cycles on Rust 1.97.0; 16 is a
budget line, not a technical limit, and R3 may move it. Statement inputs should be
integers wherever the application allows, and a spec's cycle estimate is printed by
`noir-ckb build` from the declared types.

Acceptance test: a generated script for a 10-input and a 16-input circuit accepts a valid
proof. The same scripts built with both buffers forced to 512 bytes reject: with 48 at
witness loading wherever the witness exceeds 512 bytes (every `v1` witness from n = 10,
every witness at n = 16), and with 50 at key loading where only the key does (bare
envelope, n = 7 to 10). An earlier version of this test expected 50 in every case; the
witness is loaded first.

## 5. Prior art

| Work | What it does about binding | Relation |
| --- | --- | --- |
| [Tornado Cash `withdraw.circom`](https://github.com/tornadocash/tornado-core/blob/1ef6a263ac6a0e476d063fcb269a9df65a1bd56a/circuits/withdraw.circom) | `recipient`, `relayer`, `fee`, `refund` are public inputs that take part in no computation; the contract passes the actual call values | The context channel is this pattern with one digest instead of four inputs |
| [Semaphore `semaphore.circom`](https://github.com/semaphore-protocol/semaphore/blob/dbab5553c486a09d5e1042e5271e3316224cc176/packages/circuits/src/semaphore.circom) | `nullifier = Poseidon(scope, secret)`; `message` is bound by a dummy constraint | Model for the ballot box: the election id is the scope |
| [zk-Lock](https://github.com/CECILIA-MULANDI/zk-lock/tree/d09d768890455f8f5a568d8468ef22a8b18a81cc) (CKB, Circom) | A reusable Lock: args commit to a key hash and a public-input hash; a second mode binds to the transaction | Covers the Lock placement. `noir-ckb` generates Type Scripts and does not duplicate it |
| [groth16-ckb](https://github.com/CECILIA-MULANDI/groth16-ckb/tree/d64c769ffe2d2edb5eb308dc59058efda77c2f83) | Generic verifier, wire format, decoder | Linked or spawned unchanged |
| [Sunspot](https://github.com/reilabs/sunspot/tree/0a9f7d01070cfb8b34cbfa77e4782e18adacc096) (Solana) | Noir to Groth16 (gnark) and a generated verifier program per circuit; audited; requires Noir 1.0.0-beta.22 | Closest tool in shape. It generates a verifier, not a state binding; on Solana the calling program supplies the binding by hand |
| [VoteSecure architecture v2.3](https://github.com/psawyerberlin/votesecure/blob/f10e944fc6e4b61156f0823e5e5d24c0a159415e/docs/architecture.md) (CKB, design proposal, not implemented) | Sharded ballot box, relay batches, explicit SEAL transition because scripts have no upper time bound | Same close-by-state-change shape as the ballot box spec; a likely first outside user of shared mode |
| CKB [Type ID](https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0022-transaction-structure/0022-transaction-structure.md#type-id) | Unique identity from the first input | Used as instance identity and as the creation anchor |

Zcash and Aztec bind differently (a signature over the transaction hash under a key proven
in the circuit; a kernel circuit over the whole transaction). They matter for R2, not for
the format, and are treated there.

Not found: any tool, on CKB or elsewhere, that derives the script-side reconstruction of
public inputs and its adversarial tests from a declaration. The search covered the
repositories above and the CKB RFCs; this is absence of evidence only.

## 6. Options compared and the chosen design

### 6.1 How the script is produced

| Option | For | Against |
| --- | --- | --- |
| A. Generate Rust source per application from the spec | The output is readable and auditable as an ordinary script; no interpreter in consensus code; dead checks do not exist | One binary per application |
| B. One interpreter script that reads the spec from a Cell | One audited binary | Parsing a spec inside CKB-VM adds a second input language to consensus code and cycles to every transaction; a bug affects every application |
| C. Rust macros in a library crate | Familiar | The tests cannot be derived from a macro invocation as easily as from data |

**Chosen: A.** The generator is a host program. It emits one Rust crate from templates,
one `match` arm per action, all sizes and offsets as constants. The emitted source for the
tally and counter specs must differ from the hand-written files only in layout and naming
(reviewed by diff in M2).

### 6.2 Type or Lock

| | Type (chosen for the generator) | Lock |
| --- | --- | --- |
| Runs on | creation, update, destruction | spending only |
| Can enforce the initial state | yes | no: anyone can create a Cell with this Lock and any data |
| Sees its successor | yes, by group | no group output; successor must be found by index or bound by `tx_hash` |
| Cell can also carry xUDT | no | yes |
| Prior art on CKB | counter, tally | zk-Lock |

Every one of the five applications needs creation rules, so all are Types. A project that
needs a proof-gated Lock should use zk-Lock.

### 6.3 Linked or spawned verifier

| | Linked (today) | Spawned (RFC 0050) |
| --- | --- | --- |
| Application script size | 113,464 bytes (tally, pinned) | about 41,800 bytes (estimate: tally minus the measured linked/thin difference of 71,672) |
| Capacity locked per application | about 113,500 CKB | about 41,900 CKB, plus one shared 103,560-byte verifier for all applications (estimate) |
| Cycles | baseline | +144,900 (0.13%) (spike, pinned) |
| Needs | `data1` or later | `data2`. The same code under `data2` has another script hash than under `data1`: Cells of the deployed `data1` applications cannot move to it without a migration |
| Audit surface per application | binding code + pairing code | binding code only; the verifier binary is the same for all |
| Risk | none new | measured in ckb-testtool only, not on a node; the child must verify the same bytes the parent compared |

**Chosen: spawned for new applications, linked for the two deployed ones**
(`verifier = "spawn" | "linked"` under `[binding]`). `spawn` requires `hash_type = "data2"`
and the linter refuses it otherwise; with `data1` the verifier is linked. The placement
spike was repeated on the pinned toolchain; the decision remains conditional on one testnet
transaction (M1).

What the spike did and did not show. It measured the cost of spawning. Its parent decodes a
bare payload and does not compare a public vector; parent and child both read group-input
witness 0 and take `input_type` before `output_type`; the child takes the key hash from the
first 32 bytes of the running script's args. None of that is the generator's interface:
application args are a version and a Type ID, keys are compiled pins, creation reads
`output_type` at the output's index, and `v1` wraps the proof. The interface below is
specified and has not been run.

Parent-to-child interface, version 1 (to be exercised end to end in M1):

| Item | How it is passed | Why |
| --- | --- | --- |
| Verifier identity | The parent spawns the Cell dependency whose data hash equals its compiled `verifier` pin | Other code cannot be substituted without a hash collision |
| Interface version | `argv[0] = "1"` | The child refuses a version it does not know |
| Key | `argv[1]` = data hash of the key Cell (the parent's compiled `vk.<circuit>` pin for the selected action) | Several circuits per application |
| Witness | `argv[2]` = source (`input` or `output`), `argv[3]` = absolute index in the transaction, `argv[4]` = `input_type` or `output_type` | Creation and update read different places; no "first group input" convention |
| Envelope | `argv[5]` = `bare` or `v1`; under `v1` the child verifies the `proof` field of the `BindingPayload` | The child must verify the bytes the parent compared |
| Result | Exit code 0, or 50 (key) or 51 (proof); the parent returns a non-zero exit code or a spawn error unchanged as a rejection | |

The parent compares the reconstructed public vector with the payload's before it spawns;
the child loads the same witness field again by the same absolute index, so both act on the
same bytes of the same transaction. Tests M1 must contain: a child given another index, a
child given another key hash, a verifier dependency with other code, and a creation.

## 7. Exact interfaces

### 7.1 Files

```
noir-ckb.toml                    spec ([binding] format 2) and tool pins
target/noir-ckb/<profile>/
  script/                        generated crate: src/main.rs, build.rs (pins), Cargo.toml
  tests/                         generated ckb-testtool matrix and its case builder
  client/                        generated statement builder (computes the public vector for a transaction)
  bundle.json                    hashes of circuit, R1CS, keys, script, verifier; pins; setup status
```

### 7.2 Commands

| Command | Does | Fails when |
| --- | --- | --- |
| `noir-ckb new <name>` | Writes a circuit, a spec and an inputs file for the counter pattern | |
| `noir-ckb check` | Lints the spec against the compiled ABI; prints the cycle and capacity estimate | Any rule of 3.10 |
| `noir-ckb build --network <devnet|testnet>` | Compiles, lowers, runs or checks the setup, generates and builds the script | Unsupported compiler, opcode or layout; spec uses features not yet generated |
| `noir-ckb test` | Builds and runs the generated matrix and source mutations in CKB-VM | Any case or mutation disagrees |
| `noir-ckb prove --tx <file>` | Builds the public vector from a transaction, proves, writes the payload into the witness | Public vector differs from what the script will rebuild |
| `noir-ckb deploy --network testnet` | Prints the deployment transaction for signing with `ckb-cli` | Development setup on testnet without `--development` |

`noir-ckb` never holds a key and never sends a transaction.

### 7.3 Pins and witness layout

Pins (compiled in by `build.rs`, recorded in `bundle.json`): `network`, one
`vk.<circuit>` per circuit, `verifier` (spawn mode), and each `pin:` the spec names.
Witness: `WitnessArgs.input_type` (or `output_type` on creation) holds the bare wire
witness or a `BindingPayload` (3.5). Public vector: `u32` count, then one 32-byte
little-endian value per declared public input, in ABI order.

## 8. Generated adversarial tests

Every case is derived from the spec; none is written by hand. Three families.

**A. Transaction mutations** (start from a valid transaction per action).

| Operator | Expected | Hand-written tally cases it reproduces |
| --- | --- | --- |
| A1 valid, per action and per accepted variation (reordered dependencies, application Cell at another index) | accept | 5 |
| A2 unrelated change output altered | accept | 1 |
| A3 extra inputs and outputs of other scripts; a second funding input | accept, or 49 when the context has `tx_hash` | 0 (new) |
| A4 each data field: wrong length, wrong constant | 43 | 2 |
| A5 each `field`: zero if `nonzero`, the modulus, above it | 54 | 4 |
| A6 Lock rule: each component | 45 | 4 |
| A7 args: length, version, wrong Type ID | 41, 44 | 2 |
| A8 payload: missing, wrong field, truncated, trailing, oversized, wrong version, wrong action byte | 48 | 8 |
| A9 each context item changed, old proof | 49 | 6 |
| A10 each context item changed, vector recomputed, old proof | 51 | 3 |
| A11 proof of one action presented as another | 49 | 2 |
| A12 each unchanged part altered | 46, 47, 55 | 1 |
| A13 shape: duplicate output, duplicate input, destruction where no action allows it | 42 | 3 |
| A14 key dependency: missing, altered, duplicated | 50 | 3 |
| A15 invalid proof | 51 | 1 |
| A16 limits: 65 inputs, outputs, dependencies rejected; exactly 64 accepted | 52, accept | 1 |
| A17 each `require`: boundary value on each side | 53 | 0 (new) |
| A18 `since`: one below the minimum, wrong kind | 56 | 0 (new) |
| A19 named output: wrong Lock, wrong capacity, same index twice | 57 | 0 (new) |

All 49 hand-written tally cases map to A1 to A16 (46 cases) and F (3 cases), by inspection of `scripts/check-private-tally.py`. Applied to the
tally spec the operators also yield cases the hand-written matrix lacks: input and
dependency limits, malformed data on the consumed Cell, key faults on update, truncated
and trailing payloads on creation, and A3.

**F. Fresh-proof cases.** For every script-side rule (Lock rule, unchanged parts, field
values, `require`), a proof is made *for the violating transaction*, so only the script
rule can reject it. The tally matrix has three of these.

**S. Source mutations.** Each generated check is removed in turn and the matrix rerun; at
least one case must change from reject to accept. S1 covers shadowed context items: with
the shadowing check removed, the case must now be rejected with 49 by the digest. A
mutation that nothing detects fails `noir-ckb test`.

**What the generated tests cannot show.** All three families are derived from the spec. A
rule the application needs and the spec does not state is missing from the script, from the
mutation targets and from the expected results at once, and every case passes. The
generated matrix therefore tests that the script does what the spec says, not that the spec
says enough. Two things are added for the second question and neither is generated:

- *Application properties*, written by the developer in a separate file as statements over
  whole transactions with an expected verdict ("nobody but the mover can change
  `mover_board`", "a finished game pays exactly one output to the winner"). `noir-ckb test`
  runs them against the generated script; a project without any prints a warning.
- *Circuit relation tests.* For every statement public input the developer supplies at
  least one assignment that violates the intended relation, with its own consistent public
  vector and witness; proving must fail. An earlier version of this document proposed to
  prove with two values and require the second proof to fail against the first vector.
  That tests that the proof is bound to its public inputs, which Groth16 already
  guarantees; it does not test that the circuit restricts the value.

## 9. Budgets

| Item | Budget | Basis |
| --- | --- | --- |
| Binding checks before the pairing | under 1M cycles | spike: about 60,000 for load, decode and key lookup; the rest estimated |
| Verification | 96M + 0.28M per input + about 0.01M per significant bit on Rust 1.97.0; add 3.5% for the pinned build and up to 7M for the per-binary spread | spike |
| Spawn overhead | 0.15M cycles | spike, pinned |
| Battleship `turn` (10 inputs: 1 field, 2 bitmaps, 5 bytes, 2 context halves) | about 107M cycles on Rust 1.97.0; 111M to 118M on the pinned build with the spread | estimate from the slopes |
| Application script | 45,000 bytes or less with a spawned verifier | estimate; acceptance test in M1 |
| Witness | Bare: 182 + 32n bytes. `v1`: 207 + 32n plus one byte per named output. Other `WitnessArgs` fields (a Lock signature) are extra and budgeted separately | computed from the Molecule schema |
| `noir-ckb check` | under 1 second | target |

## 10. Pinned tools

As in `toolchains/platforms.json`: Nargo 1.0.0-beta.18, backend `wamimi/Noir-Groth16@828025f`,
snarkjs 0.7.5, host Rust 1.95.0, contract Rust 1.94.1, clang 18, CKB 0.210.0, ckb-cli
2.0.0, `groth16-ckb@d64c769`, ckb-std 1.1.0, ckb-testtool 1.1.1. R1 covers the move to
Noir 1.0. The spike toolchain (Rust 1.97.0, LLVM 22.1.6) is recorded in the spike README
and is not proposed as a pin; it exposed one thing a later bump will meet: with LLVM 22,
`-C target-feature=-a` no longer builds the scripts and `-a,-zaamo,-zalrsc` is needed.

## 11. Milestones

Each step ends with a command whose output decides pass or fail.

| # | Step | Acceptance test |
| --- | --- | --- |
| M1 | Shared verifier deployed once on testnet (placement confirmed on the pinned toolchain on 11 November 2026: 0.13% overhead) | One testnet transaction through a spawned verifier using the interface of section 6.3, plus the four interface tests listed there on a local chain |
| M2 | Generator core: specs in, crate out, for `bare` envelope, proofs on create and update, `signer`, `require` | Generated tally and counter scripts give the recorded verdict and code on all 97 recorded cases (public vectors byte-identical); `diff` review against the hand-written files |
| M3 | Generated tests: operators A1 to A16, F, S | For the tally and counter: generated matrix is a superset of the hand-written one by operator; every source mutation detected; a deliberately removed check in the generator template fails the run; application properties and circuit relation tests (section 8) run from their own files |
| M4 | `v1` envelope, several circuits, `since`, named outputs, computed buffers, A17 to A19 | A 16-input test application passes its generated matrix; forced 512-byte buffers fail with 48 or 50 as section 4 states; named outputs enforce the Type and data policy |
| M5 | Battleship from its spec (with R5) | A scripted full game, a timeout and a cancelled game on a local chain; generated matrix and mutations pass |
| M6 | CLI and first-user path | A person who has not seen the repository follows one page from `noir-ckb new` to a testnet transaction; time recorded |
| M7 | Shared mode and batching: the ballot box, the grant deliverable, with VoteSecure as first consumer | Ballot box spec generates; two voters' proofs made against the same state both land; a batch of 100 ballots is accepted in one transaction on a local chain; a second ballot with a used nullifier is rejected |

## 12. Risks and open questions

| Risk | Consequence | Handling |
| --- | --- | --- |
| The linter is the trusted part: a missed rule yields a script that verifies proofs and binds too little | Silent loss of the main property | Negative spec corpus kept as a test (29 today, each checked for its reason); every reviewer finding becomes a case. The first external review found five holes the corpus had missed, so the corpus is evidence of the holes already found, not of their absence. The F and S families detect a check the generator dropped from a spec; they do not detect a rule the spec never stated (section 8) |
| The linter cannot see inside the circuit | A statement public input the circuit ignores is unconstrained (the Week 8 class of failure) | Circuit relation tests supplied by the developer (section 8); documented as a limit: the toolkit cannot generate them |
| The public-input slopes were measured off the pinned toolchain, and verification cost varies by up to 7M between binaries for an unknown reason | Budgets carry a range | Rerun `placement/run.sh` with the public-input part; investigate the spread before quoting cycle guarantees |
| Spawn behaves differently on a node than in ckb-testtool | Fallback to linked: 113,500 CKB per application instead of about 41,900 | `verifier = "linked"` stays supported |
| Relayer-open default surprises an integrator | A proof is replayed inside a transaction the user did not expect | Stated in 3.6; `tx_hash` opt-in; `check` prints which parts of the transaction are open |
| Format grows expressions over time | Loses rule 3.1.1 | The three check forms are closed; anything else is a circuit rule or a format version |

Open: whether `noir-ckb new` should default to `tx_hash` for applications with a
`signer` (the signer already knows the whole transaction); how the cycle estimate handles
`field` inputs that are small in practice.

## 13. External review

One review by an outside model, at commit `206df77`, covering this document, the spike and
the five specs. It was a source and design review: finding 7 was reproduced by arithmetic,
the rest were argued from the code and RFCs 0017, 0022 and 0050. No exploit transaction was
built. Severities are the reviewer's and describe a generator built to the rules as they
stood, not the deployed tally. All twelve findings were accepted; none was dismissed.

| # | Severity | Finding | Response |
| --- | --- | --- | --- |
| 1 | High | The Lock and the capacity got a weaker analysis than data fields: being mentioned in any source, the context included, counted as bound, and the free-in-context rule covered data only | Accepted. Confirmed in `bindspec.py` (the separate Lock and capacity branches). Replaced by one analysis for all properties (rule 3.1.4, linter rules 4 and 5). Six new negative cases, all refused. Three supplied specs failed the corrected linter and were made explicit (section 3.12) |
| 2 | High | "Pinned" and "proven" were syntactic: any equality pinned its left side, and one half of a 32-byte value marked the whole as proven | Accepted. An equality now pins only when its other side is anchored, resolved to a fixed point so chains work and cycles do not; both halves are required. Three new negative cases. Byte-level tracking inside a field was not added: a field is the unit, and a public input always covers a whole field or a declared half |
| 3 | High | Battleship payouts fix a Lock hash and a capacity only. An output with the right Lock and a restrictive Type may be unspendable, and nothing stops the same output from also satisfying another script's obligation | Accepted. Format decision: a named output has no Type and empty data unless the spec states otherwise (section 3.4). Not implemented in the spike. Exclusivity against other scripts cannot be enforced by one script; it is recorded as an open item in `battleship.md` and as an application property to test |
| 4 | High | Generated tests cannot find a rule the spec lacks; the proposed two-proof circuit test checked proof binding, not the circuit's relation | Accepted. Section 8 now says what the generated families do not show and adds developer-written application properties and circuit relation tests; the two-proof test and the sentence that F and S "catch a missing check even when the linter is wrong" were removed |
| 5 | Medium | `signer` exempted a creation from the binding rules for any Lock; a matching Lock hash does not show that the Lock signs the outputs | Accepted. The exemption now needs `signer = "out.lock_hash"`, a Lock rule that pins the code, and a declared `signs = "transaction"` (rule 6). The declaration is an assumption the linter cannot check, and is printed as one. `signer` and `since` sources now go through the same source validation as the others. Two new negative cases |
| 6 | Medium | The spawned-verifier interface was neither specified nor exercised by the spike; defaulting to spawn under `data1` is wrong | Accepted. Section 6.3 now states what the spike did not do and specifies the interface; M1 has to exercise it. `spawn` requires `data2` (rule 12, one negative case); the three draft specs for new applications say so and the two deployed profiles stay linked |
| 7 | Medium | The envelope overhead is 25 bytes plus named outputs, not 12; a `v1` witness is 527 bytes at n = 10; sizing from n alone ignores other witness fields; the forced-512 test can fail with 48 before 50 | Accepted; the arithmetic was wrong. Sections 3.5, 4, 9 and M4 corrected |
| 8 | Medium | The Battleship timeout is a competing action. After the wait both `turn` and `timeout` are valid; consensus does not prefer one (RFC 0017 gives a lower bound only) | Accepted. `battleship.md` no longer says a player who stops playing loses; it states the race and the monitoring assumption and adds a test for both orderings |
| 9 | Medium | `open` sets `pending` to 255 and `join` keeps it; the `turn` circuit as described answers a shot on cells 0 to 99 and does not define 255 | Accepted. Recorded as an open item in `battleship.md` with the invariant to decide and three circuit tests. No circuit exists yet |
| 10 | Medium | The linter did not enforce the 16-input ceiling, positive counts or the closed lists, and did not validate `signer` and `since` sources | Accepted. Rule 11 and five negative cases. A closed typed schema is M2 work and is stated as missing under section 3.10 |
| 11 | Medium | "Verdict and error code on every recorded case" overstated a comparison that stops before the pairing; the reader's docstring claimed every rule | Accepted. D2, section 3.12, the spike README and the docstring now say "pre-pairing agreement on the recorded subset" and list what is not evaluated |
| 12 | Low | The reader rejected at 64 Cells where the scripts accept 64 and reject the 65th; it accepted a signer at any input where the counter requires input 0 | Accepted. Confirmed against `count` in both scripts and `owned-counter/src/main.rs:115`. The reader now does both as the scripts do, the format defines `signer` as input 0, and operator A16 tests 64 and 65. Agreement stayed at 49/49 and 48/48, which confirms the reviewer's point that the recorded cases do not reach either boundary |

The reviewer examined and reported no problem with: the tally's reconstruction of the public
vector before verification; witness selection by position; Type ID as a creation anchor and
the OutPoint as a consumption anchor; the domain separation given by script hash, action,
network pin and OutPoint; the Battleship `turn` mapping accounting for every changed field
(structure only, no circuit exists); verifier substitution under a fixed data hash; and the
fixed-buffer paths rejecting oversized loads. These are the reviewer's statements within a
review that ran no VM tests.

Still unreviewed: the generator itself (it does not exist), the spawn interface in
execution, and shared mode in execution.

## Sources

- CKB RFCs, `nervosnetwork/rfcs@0c94545`: [0014](https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0014-vm-cycle-limits/0014-vm-cycle-limits.md), [0017](https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0017-tx-valid-since/0017-tx-valid-since.md), [0022](https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0022-transaction-structure/0022-transaction-structure.md), [0050](https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0050-vm-syscalls-3/0050-vm-syscalls-3.md)
- The repositories linked in section 5, at the commits shown
- This repository: both Type Scripts, `scripts/check-private-tally.py`, `evidence/week-07.md`, `evidence/week-15.md`, `evidence/private-tally-v2.md`, `evidence/private-tally-testnet.md`
