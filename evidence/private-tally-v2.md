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

Not yet done: client `create`/`update` commands (they depend on the Type
Script's context digest), Type Script, CKB-VM matrix, mutations and the setup
ceremony. The circuit is not frozen.
