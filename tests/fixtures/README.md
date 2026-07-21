# Test fixtures

Small, reviewable cross-implementation fixtures will be added after a Week 8 backend is selected.

Each fixture must include producer versions and revisions, file hashes, public-input ordering, and verification results. Private application witnesses and toxic-waste material must not be committed.

## Week 8 public-input diagnostic

`week-08-intended-public.json` contains the one-element public vector intended by the Noir ABI: `y = 49`.

It is used only as a negative fixture against the diagnostic proof generated from the selected backend's original R1CS. That R1CS incorrectly classifies private `x = 7` as its public wire, so the expected source-verifier behavior is:

```text
generated public vector [7] -> proof verifies
intended Noir vector [49]   -> same proof is rejected
```

The result was reproduced with snarkjs 0.7.5 on 21 July 2026: generated `[7]` verified with exit code `0`, while this intended `[49]` vector was rejected with `Invalid proof` and exit code `1`. This demonstrates the incompatibility; it does not make the diagnostic R1CS acceptable. The fixture contains no private or setup material.

`week-08-private-value-as-public.json` contains `["7"]`. It is the inverse negative fixture for the public-first control. If that control exports and verifies intended public `[49]`, the same proof must reject `[7]`. Together, the fixtures distinguish mathematical proof validity from the intended Noir public interface in both directions.
