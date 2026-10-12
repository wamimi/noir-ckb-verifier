# noir-ckb-verifier

**Write a rule in Noir, prove it off-chain, and have a CKB script accept the proof
only for the exact Cell transition it was made for.**

A Groth16 proof can verify perfectly and still be about the wrong thing: the
wrong Cell, the wrong state, the wrong network, or (as Week 8 found) the wrong
public value. noir-ckb connects Noir circuits to CKB and makes the scripts check
both things: that the proof is valid, and that it describes the transaction it is
attached to.

```text
proof verifies mathematically
!=
proof authorizes this CKB state transition
```

## Try it

**[Try the counter →](docs/try-the-counter.md)**, one guide, start to finish:

1. Run it locally: a real proof and real signed transactions on a throwaway chain.
   No wallet, no money. macOS (Apple Silicon) or Ubuntu 24.04, natively or in a container.
2. Create and update your own counter on CKB testnet, against the deployed contract.
3. Tell us how it went.

## What exists today

- **Owned counter (v1)** on CKB testnet. A Noir circuit proves `new = old + 1`.
  The Type Script rebuilds the expected statement from the actual transaction
  (consumed Cell, old and new state, owner, capacity, network) and verifies the
  proof; the owner's signature is also required. Tested with 48 adversarial
  CKB-VM cases and three deliberately broken contracts.
- **Portable tooling**: pinned, hash-checked tools for macOS ARM64 and Ubuntu
  24.04 (x86_64, ARM64), a network-isolated container, and hosted CI.
- **Private tally (v2)**: an accepted design, not yet built, where a hidden value
  is updated and the proof itself is the authority. See the
  [design](docs/private-tally-v2-spec.md).

Status: research software. Pre-audit, testnet only, single-party development
setup. Not for mainnet or production.

## Documentation

- [Try the counter](docs/try-the-counter.md): start here
- [Documentation map](docs/README.md): how it works, security notes, design records
- [Project history](docs/project-history.md): Weeks 7–14 and the earlier Capsule example
- [Evidence](evidence/): retained command outputs and results for each milestone

## Repository layout

```text
circuits/owned-counter-v1/         Counter circuit (current reference application)
contracts/crates/owned-counter/    Counter Type Script (proof verification + binding)
scripts/                           Launcher, tool fetcher, testnet join tool, test runners
releases/owned-counter-v1-testnet/ Published files for joining the testnet deployment
containers/counter/                Pinned Ubuntu 24.04 container definition
toolchains/                        Pinned tool versions and per-platform hashes
crates/artifact-adapter/           snarkjs -> arkworks -> CKB wire format adapter
crates/ckb-integration-tests/      CKB-VM transaction test harness
crates/noir-ckb-cli/               Earlier build/prove/test CLI (Capsule example)
circuits/, contracts/ (other)      Earlier Capsule example, kept as a regression fixture
docs/                              Guides, design notes and records
evidence/                          Reproducible command and result records
experiments/                       Feasibility experiments (SP1, private tally)
```

## Credits

- The proving backend is a maintained fork of James Bachini's
  [Noir-Groth16](https://github.com/jamesbachini/Noir-Groth16), with a
  visibility-ordering fix.
- On-chain verification uses Cecilia Mulandi's
  [groth16-ckb](https://github.com/CECILIA-MULANDI/groth16-ckb).
- References: [Noir](https://noir-lang.org/docs),
  [CKB Molecule](https://docs.nervos.org/docs/serialization/serialization-molecule-in-ckb),
  [Sunspot](https://github.com/reilabs/sunspot).

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE).
