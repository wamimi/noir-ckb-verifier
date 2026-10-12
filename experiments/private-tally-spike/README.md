# Private tally spike (feasibility only)

Not the private tally v2 protocol. Domain tags, `MAX_DELTA` and the circuit
shape are placeholders, chosen only to answer feasibility questions before
the v2 spec is written:

1. **Hash availability.** Noir 1.0.0-beta.18 keeps `std::hash::poseidon2::Poseidon2::hash`
   private; only the raw `std::hash::poseidon2_permutation` blackbox is public.
   The official `noir-lang/poseidon` library supplies the sponge:
   - v0.4.0 (with the `perform_duplex` stale-cache fix) does not compile on beta.18;
   - v0.2.6 (`00f879180a56720169cff92a56778d40678d8e26`) compiles. Its non-oracle
     tests pass on beta.18 (oracle tests need an external resolver), and its
     1-, 2- and 3-input Poseidon2 vectors are identical to v0.4.0's.
   - Rule: **every `Poseidon2::hash` call takes at most 3 inputs.** Longer
     inputs hit the unfixed stale-cache path. The spike commits as
     `H(tag_state, value, H(tag_inner, blinding, key))`.
2. **Backend lowering.** `check_lowering.py` runs each case through `nargo execute`
   (Noir semantics) and through the pinned backend's `noir-cli interop` +
   `snarkjs wtns check` (R1CS), requiring agreement and that the four public
   values occupy wires 1..4 even though the five private inputs come first.
   Cases cover creation at zero, updates, delta = 0 cover updates, maximum
   delta, wrong key/blinding/value/commitments, delta and value overflow,
   invalid creation and context-limb overflow.
3. **Secret handling.** Throwaway secrets live only in `<out>/private` (0700),
   deleted at the end; `results.json` records outcomes only; a final scan fails
   the run if any secret (decimal, hex, raw little/big-endian bytes) remains.

Run (needs the backend `noir-cli` built from the pinned fork, e.g. from a
counter run's `setup/backend-target/debug/noir-cli`):

```bash
python3 -B experiments/private-tally-spike/check_lowering.py \
  --noir-cli "$(ls -td target/counter-local-*/setup/backend-target/debug/noir-cli | head -1)" \
  --out target/spike-differential-1
```

Recorded 12 October 2026: Noir-only half 19/19 on Linux x86_64; full
differential 19/19 on macOS ARM64 with the pinned backend. See
[portable evidence](../../evidence/week-15-portable.md).
