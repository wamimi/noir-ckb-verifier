# noir-ckb-verifier

An experimental toolchain for turning Noir circuits into CKB-deployable Groth16 verification artifacts and binding proofs to typed Cell transitions.

## Status

This repository is research infrastructure. It is pre-audit, incomplete, and not suitable for production or mainnet use.

Week 7 establishes the two ends of the proposed pipeline without running an ACIR-to-Groth16 backend:

```text
Noir source
  -> version-pinned ACIR artifact and execution witness
  -> [Week 8: experimental BN254 Groth16 backend]
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

Running Noir-Groth16 or Sunspot is deliberately deferred to Week 8.

## Repository layout

```text
circuits/square-root/       Minimal compatibility circuit and development inputs
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

See [`docs/artifact-inspection.md`](docs/artifact-inspection.md) for artifact structure and [`evidence/week-07.md`](evidence/week-07.md) for the baseline checklist and result status.

## References

- [Noir documentation](https://noir-lang.org/docs)
- [Nargo command reference](https://www.noir-lang.org/docs/reference/nargo_commands/)
- [Nervos CKB Molecule documentation](https://docs.nervos.org/docs/serialization/serialization-molecule-in-ckb)
- [groth16-ckb](https://github.com/CECILIA-MULANDI/groth16-ckb)
- [Noir-Groth16](https://github.com/jamesbachini/Noir-Groth16)
- [Sunspot](https://github.com/reilabs/sunspot)

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE).
