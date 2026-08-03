# Week 10 Capsule public vectors

These files define the ordered public-input contract and retained public
Groth16 material for the proof-bound Capsule development fixture.
`intended-public.json` is the expected output of the pinned prover. The other
named public-vector files change exactly one transaction-derived field and must
be rejected when used with the unchanged proof.

The fixtures contain public development values only. The proving key, Powers
of Tau, R1CS, WTNS, and private witness are not committed. `manifest.json`
records the producer revisions, source hashes, normalization, and verification
scope.
