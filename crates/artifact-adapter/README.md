# artifact-adapter

Week 9 typed Rust adapter that will:

1. parse the selected Groth16 backend's proof, verification key, and public inputs;
2. validate BN254 field elements and curve points;
3. construct arkworks 0.5 objects;
4. verify the proof through an arkworks host verifier;
5. serialize with `CanonicalSerialize`;
6. encode the verifier's Molecule wire objects.

No adapter implementation belongs to the Week 7 baseline.
