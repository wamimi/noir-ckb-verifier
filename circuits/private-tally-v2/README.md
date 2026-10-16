# Private tally v2 circuit

Noir workspace for the `noir-ckb/private-tally/v2` profile. Specification:
[private tally v2 design](../../docs/private-tally-v2-spec.md), sections 2–3.

| Package | Type | Purpose |
| --- | --- | --- |
| `commitment` | library | Domain tags and the commitment `C(v, r, key)`; two Poseidon2 calls of 3 inputs each |
| `circuit` | binary `private_tally_v2` | The proved statement: private `value_old, r_old, key, delta, r_new`; public `c_old, c_new, ctx_lo, ctx_hi` |
| `commit-helper` | binary | Prints `C(v, r, key)` for off-circuit tools, using the same library code |

Toolchain: Nargo 1.0.0-beta.18 (`99bb8b5c`); `noir-lang/poseidon` v0.2.6
(`00f879180a56720169cff92a56778d40678d8e26`).

## Checks

```bash
cd circuits/private-tally-v2
nargo fmt --workspace --check
nargo test --workspace
cd ../..
python3 -B -m unittest scripts/tests/test_private_tally_circuit.py
```

Noir execution against the pinned backend's R1CS (needs a built `noir-cli`,
for example from a previous counter run):

```bash
python3 -B scripts/check-private-tally-circuit.py \
  --noir-cli "$(ls -td target/counter-local-*/setup/backend-target/debug/noir-cli | head -1)" \
  --out target/private-tally-differential-1
```

The circuit is not frozen. Any change after the setup ceremony opens voids the
ceremony ([setup ceremony](../../docs/setup-ceremony.md)).
