# Private tally v2: implementation evidence

Profile `noir-ckb/private-tally/v2`; specification in
[private tally v2 design](../docs/private-tally-v2-spec.md).

## Circuit (16 October 2026)

Source: [`circuits/private-tally-v2/`](../circuits/private-tally-v2/), committed in
`dc3b8a2`. Toolchain: Nargo 1.0.0-beta.18 (`99bb8b5c`), `noir-lang/poseidon`
v0.2.6 (`00f87918`), backend `828025f3`, snarkjs 0.7.5. Host: macOS ARM64.

| Check | Result |
| --- | --- |
| `nargo test --workspace` | 21 passed (2 commitment library, 19 circuit) |
| `nargo fmt --workspace --check` | Clean |
| Static checks (`scripts/tests/test_private_tally_circuit.py`) | 4 passed: every Poseidon2 call has at most 3 inputs, parameter layout private first then public, domain tags equal their ASCII strings, poseidon dependency pinned once |
| Differential, Noir execution vs backend R1CS (`scripts/check-private-tally-circuit.py`) | 20/20 agreed (3 random updates, 4 valid fixed cases, 13 rejections); public values in wires 1–4 in order; leak scan clean |
| R1CS size | 3,338 constraints and wires; 5 private, 4 public inputs, 0 outputs |

A second run with `--rounds 0` (17/17 agreed) kept its private folder only to
read the R1CS size, and was then deleted.

## Development setup, proofs and adapter (16 October 2026)

`scripts/setup-private-tally.py` ran twice on macOS ARM64 (Python 3.9), both
`passed` with a clean leak scan:

| Run | Phase 1 | Result |
| --- | --- | --- |
| `private-tally-setup-1` | Local single-party Powers of Tau, power 13 | Passed |
| `private-tally-setup-ppot-2` | PSE `ppot_0080_12.ptau` (power 12) | Passed in 43 min, of which the one-time chain verification took most |

Each run compiled the circuit with an exact ABI check, generated fresh random
secrets inside a 0700 folder, checked that the public values occupy wires 1–4,
ran a single-party phase 2 (development only, not the ceremony), proved a
creation (0) and an update (0 → 7), and confirmed that changing any of the four
public values makes each proof fail (8 rejections per run). The private folder
was deleted and the kept files contained none of the secrets.

Phase 1 file: `snarkjs powersoftau verify` reported `Powers of Tau Ok!` with 61
contributions plus the final beacon (iteration exponent 31). BLAKE2b-512:
`3ee85ae13672d1d742117566126f31d678cf72d480f0df8e2aec78d77771433392ae01bb2b11c4ea0e60b244415be0a12a02e51d3f7a4a8b5c1c982fa208c4cd`.
The power-12 file was sufficient for the 3,338-constraint circuit.

Adapter (`noir-ckb-adapter`, update proof of the PSE run): arkworks positive
verification accepted, altered public input rejected, CKB wire round trip
accepted; 4 public inputs; verification key 392 bytes (Molecule 430), proof 128
bytes, public inputs 132 bytes, witness Molecule 290 bytes. These sizes match
the deployed counter's verification key layout (also four public inputs).

Secret-handling helpers (`scripts/private_tally.py`): 11 unit tests passed
(owner-only permissions, refusal of readable folders and files, versioned state
without overwriting, backup permissions, leak scan of decimal, hex and raw
32-byte encodings, commitment helper consistency).

## Type Script and CKB-VM matrix (17 October 2026)

Source: `contracts/crates/private-tally/` (Type Script), driver
`scripts/check-private-tally.py`, runner
`crates/ckb-integration-tests/tests/private_tally.rs`. The Type Script was built
with Rust 1.94.1 for `riscv64imac-unknown-none-elf` (113,984 bytes), pinned to an
isolated test network domain, the development verification key of
`private-tally-setup-1` and the always-success guard Lock. Four fresh proofs were
generated for the run (creation, update, zero-delta cover update, and an update
proved for a different network).

**46 of 46 cases matched their expected outcome** in CKB-VM (ckb-testtool),
leak scan clean:

| Outcome | Cases |
| --- | --- |
| Accepted (6) | Creation (113,067,366 cycles); update 0 → 5 (115,668,811); zero-delta cover update (115,855,014); reordered dependencies; tally at input/output index 1; changed fee change output |
| 41 args version, 44 Type ID (2) | Unknown args version; wrong Type ID on creation |
| 42 shape (3) | Duplicate tally output; destruction; two tally inputs |
| 43 data encoding (2) | Wrong data version; short data |
| 45 guard Lock (4) | Successor not the guard (creation, update); guard with args; input not the guard |
| 47 capacity (1) | Capacity changed on update |
| 48 witness (8) | Proof missing (creation, update), in the wrong WitnessArgs field (creation, update), truncated, trailing byte, oversized witness, wrong wire version |
| 49 public vector (8) | Other commitment and changed capacity on creation; update proof used as creation; creation proof used as update; wrong input commitment; replay on another OutPoint; replay on another tally Cell; proof made for another network |
| 50 verification key (3) | Missing, altered and duplicated VK dependency |
| 51 proof (4) | Valid proof bytes with a recomputed vector for: another commitment (creation), another OutPoint, swapped commitments; proof bytes from a different statement |
| 52 limits (1) | 65 outputs |
| 54 commitment (4) | Zero and non-canonical commitment on creation; zero successor; non-canonical input |

The cases with expected code 51 show that rebuilding the public vector for a
different transition does not help an attacker: the old proof no longer verifies.

A rerun with three added cases (`private-tally-matrix-3`) passed **49 of 49**.
The added cases carry proofs generated for exactly the offending transaction,
so only the Type Script's own rules can reject them: capacity changed (47),
successor Lock not the guard (45), and successor commitment encoded as
`c + p` (54).

## Mutation tests (17 October 2026)

`scripts/mutate-private-tally.py` rebuilt the Type Script four times, each time
with one `MUTATION` block removed, and ran a valid update (control) and the
attack that block exists to stop (target), with fresh proofs for each mutant.
Run `private-tally-mutations-2`: **4 of 4 as required**, leak scans clean.

| Removed check | Control | Target | Required outcome |
| --- | --- | --- | --- |
| `verification` | Accepted | Invalid proof bytes accepted (126,865 cycles, no pairing) | Incorrect acceptance |
| `guard` | Accepted | Non-guard successor accepted | Incorrect acceptance |
| `capacity` | Accepted | Capacity change accepted | Incorrect acceptance |
| `canonical` | Accepted | Rejected with code 51 by the verifier | Second layer |

The `canonical` block cannot be shown necessary by incorrect acceptance,
because two other layers already block what it checks: the circuit forbids a
zero commitment, and the pinned verifier (`groth16-ckb` `verifier-core` at
`d64c769f`) deserializes public inputs with arkworks, which rejects encodings at
or above the field modulus. The mutation run confirmed that second layer. The
Type Script keeps the check so that malformed state is rejected before the
roughly 115-million-cycle verification and independently of the verifier
library's behaviour.

The specification's "removed creation rule" mutation has no counterpart: the
Type Script has no separate creation rule. It fixes `c_old = 0` and action 0 in
the public statement, and the circuit enforces the zero start.

## Client and local lifecycle (17 October 2026)

Client: `scripts/private-tally-client.py` (build, prepare-deploy, confirm-deploy,
create, update, check, confirm, status, backup). It prepares unsigned
transactions only; the run signed the funding inputs with `ckb-cli` and a
disposable development key.

`scripts/local-private-tally.py` ran on a loopback CKB 0.210.0 dev chain on
macOS ARM64 (run `private-tally-local-1`, reusing `private-tally-setup-1`), with
status **`local-lifecycle-validated`**:

| Stage | Local transaction | Result |
| --- | --- | --- |
| Deploy Type Script, VK and guard Lock code | `0x5a1c5fa1…a3bc380d` | Committed; data hashes checked |
| Create at 0 | `0x12c996f5…113de819` | `check` passed before and after signing; committed; state version 1 |
| Update +7 | `0x2871194e…c82238bb` | Same; state version 2 |
| Cover update +0 | `0x349f01ad…9a3a2bbb` | Same; new commitment, unchanged value; state version 3 |

Final `status --show-value` reported value 7 at state version 3 with no pending
operation; the live tally Cell held exactly the commitment in the private state.
`backup` produced a 0700 copy. Each commitment differed from the previous one,
including across the zero-delta update. The leak scan of every kept file outside
the private folders was clean.

## Launcher and Linux container (17 October 2026)

The launcher gained `tally-quick` (fresh setup and signed local lifecycle) and
`tally-local` (the same plus the CKB-VM matrix and mutation tests); the
container image fetches the pinned `noir-lang/poseidon` dependency at build time
so runs need no network.

| Platform | Mode | Result |
| --- | --- | --- |
| macOS ARM64, native (`start-counter.py tally-quick`) | Fresh setup + lifecycle | `local-lifecycle-validated`; final value 7 at state version 3; leak scan clean |
| Ubuntu 24.04 ARM64, container (Colima, `--network none`) | `tally-local` | `local-validated`: lifecycle, 49/49 CKB-VM cases, 4/4 mutations as required, leak scan clean |

The container image was built from source revision `341aa59c` with six
uncommitted paths (the launcher and container changes recorded here), as its
provenance labels state.

Not yet done: x86_64 (CI), a tester guide, and the setup ceremony. The circuit
is not frozen.
