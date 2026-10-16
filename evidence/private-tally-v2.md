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

Not yet done: development setup and proof, adapter conversion, client secret
handling, Type Script, CKB-VM matrix and setup ceremony. The circuit is not
frozen.
