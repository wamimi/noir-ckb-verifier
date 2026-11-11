# Spike: can the draft `[binding]` format express the two deployed applications?

Research question for [R0](../../toolkit-architecture.md): is the draft format precise enough
that a program reading only a spec file reaches the same verdict as the hand-written Type
Scripts, case by case?

## What it is

- `bindspec.py`: a reference reader for the draft format (about 620 lines of Python, standard
  library only; `tomli` is needed on Python 3.10 and older).
  - `lint` applies the format's rules to a spec.
  - `replay` evaluates a spec against recorded CKB-VM matrix cases: for each recorded
    transaction it runs every check the spec implies, in the generated check order, and
    compares its verdict and error code with what CKB-VM returned for the hand-written
    script. It does not evaluate the pairing: a case that passes every binding check is
    reported as `PAIRING` and matches a recorded acceptance or a recorded error 51.
- `specs/`: five draft specs. `private-tally.toml` and `owned-counter.toml` describe the
  deployed scripts. `battleship.toml` is a design inside generator version 2.
  `ballot-box.toml` and `shielded-pool.toml` use shared mode, which is specified and
  linted but outside generator version 2. Nothing was built for these three.
- `negative_lint.py`: twelve deliberately unsafe edits of the specs; the linter must refuse all.
- `run.sh`: the whole spike in one command.
- [`placement/`](placement/README.md): a separate spike on verifier placement and the cost
  of public inputs, with its own command.

## Command

```bash
research/spikes/toolkit-architecture/run.sh
```

It needs two recorded matrix runs under `target/` (not in Git). They are produced by
`scripts/check-private-tally.py` and `scripts/check-owned-counter.py`; other run
directories can be given with `TALLY_RUN=` and `COUNTER_RUN=`.

## Result (10 November 2026, Python 3.10.12, Linux aarch64)

| Check | Result |
| --- | --- |
| Five specs lint | 5 of 5 |
| Noir public parameter order equals the spec (tally, counter) | 2 of 2 |
| Private tally, `target/tally-testnet/local/matrix` (ceremony key) | 49 of 49 cases agree |
| Private tally, `target/private-tally-matrix-3` (development key) | 49 of 49 cases agree |
| Owned counter, `target/week-15-guided-validation-20261009/matrix` | 48 of 48 cases agree; 2 of them were rejected by the secp256k1 Lock, which the spec does not describe |
| Twelve unsafe spec edits (`negative_lint.py`) | 12 of 12 refused by the linter |

"Agree" means: the same error code for every case the hand-written script rejected before
the pairing, and `PAIRING` for every case it accepted or rejected with error 51.

Sensitivity check (run by hand, not kept in `run.sh`): removing `out.capacity` from the
tally contexts produced 13 mismatches, removing `nonzero` produced 2, and a wrong Lock
`hash_type` produced 38, so agreement is not an artefact of a permissive comparison.

## What did not work or is not covered

- Negative tests found three holes in earlier versions of the linter, all now closed:
  - a public input of a shared action could read the running vote total, because any field
    named in an effect was exempt (`vote-reads-running-total`);
  - a changed field covered only by the context digest counted as bound, so a Battleship
    joiner could have rewritten the opponent's fields (`battleship-joiner-rewrites-opponent`,
    `battleship-swap-incomplete`). The context fixes the prover's choice; it does not
    constrain it;
  - a creation without proof or signer could leave the Lock and capacity unstated
    (`counter-created-unbound`, `ballot-created-capacity-unstated`).
- The pairing check, curve-point validity and the verification key decode were not
  evaluated; they belong to `verifier-core`, which a generated script links unchanged.
- `envelope = "v1"`, `effects`, named `outputs`, `since` and `placement = "lock"` are
  parsed and linted but not executed. No recorded transactions exist for them. `require`
  is executed, but the recorded matrices exercise only one check (the counter's creation at zero).
- The replay reads the matrix JSON written by the existing Python harnesses. It was not run
  against transactions fetched from testnet (the sandbox used for this spike had no access
  to a CKB RPC endpoint).
- The Noir check compares parameter names in the source text. The generator must compare
  against the compiled ABI instead.
