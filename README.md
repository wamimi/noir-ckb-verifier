# noir-ckb-verifier

An experimental toolchain for turning Noir circuits into CKB-deployable Groth16 verification artifacts and binding proofs to typed Cell transitions.

## Status

This repository is research infrastructure. It is pre-audit, incomplete, and not suitable for production or mainnet use.

Week 7 established the two ends of the proposed pipeline without running an ACIR-to-Groth16 backend. Week 8 now evaluates a pinned backend in evidence-gated stages:

```text
Noir source
  -> version-pinned ACIR artifact and execution witness
  -> [Week 8: pinned ACIR-to-R1CS and BN254 Groth16 experiment]
  -> typed arkworks conversion
  -> Molecule-encoded VK Cell and transaction witness
  -> generic groth16-ckb verifier in CKB-VM
  -> application-specific Capsule transition binding
```

The central design rule is:

```text
proof verifies mathematically
!=
proof verifies the intended CKB state transition
```

The generic verifier can establish `verify(vk, public_inputs, proof)`. The consuming protocol must additionally prove that those public inputs commit to the exact old Cell, new Cell, Capsule identity, action, and replay domain represented by the transaction.

## Week 7 scope

- record the exact local toolchain
- compile and execute a minimal square-root Noir circuit
- inspect the ACIR artifact, ABI, and execution witness
- optionally produce a Barretenberg control proof, clearly labeled as non-Groth16
- reproduce the existing `groth16-ckb` CKB-VM endpoint
- document the architecture, compatibility boundary, and threat boundary

Running Noir-Groth16 or Sunspot was deliberately deferred to Week 8.

## Week 8 scope

- evaluate Noir-Groth16 at pinned commit `4b7caace1f2128e454c8d0fe50cac1ec46b1e272`
- consume the existing Noir beta.18 artifact directly
- require strict lowering and pedantic witness solving
- inspect iden3 R1CS and WTNS outputs
- create and verify a development-only BN254 Groth16 proof with pinned tooling
- confirm the exported public input is the intended `y = 49`
- retain a negative verification result and exact artifact hashes

Week 8 stops before arkworks conversion, Molecule encoding, CKB-VM verification of the Noir-derived proof, and Capsule transition tests. See [`docs/week-08-backend.md`](docs/week-08-backend.md) and [`evidence/week-08.md`](evidence/week-08.md).

### Week 8 compatibility finding

The pinned backend produced a valid Groth16 proof for the original private-first circuit, but exported private `x = 7` as its public input. That proof verified with `[7]` and rejected the Noir-intended `[49]`.

A separate public-first control assigned `y = 49` to leading ACIR witness `w0`. Its generated proof exported and verified with `[49]` and rejected `[7]`. This establishes a constrained working path and a regression case, not general Noir compatibility. Until witness-to-R1CS remapping is implemented, the toolchain must reject any artifact whose public witnesses do not already occupy the required leading wire positions.

## Repository layout

```text
circuits/square-root/              Minimal compatibility circuit and development inputs
circuits/square-root-public-first/ Week 8 public-wire compatibility control
crates/artifact-adapter/    Reserved for the future typed Rust conversion layer
docs/                       Architecture, compatibility, and threat-boundary notes
evidence/                   Reproducible command/result records
schemas/                    Reserved for Molecule schemas used by the adapter
scripts/                    Reproducible workflow scripts added after manual baselines
tests/fixtures/             Small, reviewable cross-implementation test vectors
toolchains/                 Pinned tool and artifact-provenance records
```

## Minimal circuit

The first fixture proves knowledge of a private field element `x` whose square equals the public field element `y`:

```noir
fn main(x: Field, y: pub Field) {
    assert(x * x == y);
}
```

The development fixture uses `x = 7` and `y = 49`. It is intentionally non-secret test data.

## Evidence policy

No command is recorded as successful until its complete output has been retained and reviewed. Generated proofs, benchmarks, binary hashes, test totals, and screenshots must never be inferred from documentation or a previous run.

See [`docs/artifact-inspection.md`](docs/artifact-inspection.md) for Noir artifact structure, [`docs/ckb-endpoint.md`](docs/ckb-endpoint.md) for the CKB verifier reproduction, [`evidence/week-07.md`](evidence/week-07.md) for the endpoint baseline, and [`evidence/week-08.md`](evidence/week-08.md) for the Groth16 experiment.

## References

- [Noir documentation](https://noir-lang.org/docs)
- [Nargo command reference](https://www.noir-lang.org/docs/reference/nargo_commands/)
- [Nervos CKB Molecule documentation](https://docs.nervos.org/docs/serialization/serialization-molecule-in-ckb)
- [groth16-ckb](https://github.com/CECILIA-MULANDI/groth16-ckb)
- [Noir-Groth16](https://github.com/jamesbachini/Noir-Groth16)
- [Sunspot](https://github.com/reilabs/sunspot)

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE).
