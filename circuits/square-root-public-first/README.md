# Public-first square-root compatibility control

This circuit states the same mathematical relation as the original Week 7 fixture:

```text
x is private
y is public
x * x = y
```

It changes only the source parameter order, declaring public `y` before private `x`.

The fixture was added after the Week 8 diagnostic showed that the selected Noir-Groth16 backend preserves original witness indices as R1CS wire indices while declaring a public-input count. For the original private-first circuit, that behavior made private `x = 7` the leading R1CS public wire and moved intended public `y = 49` into a private position.

This control tests whether a public-first ACIR layout can pass the backend's current interface convention. A successful control is not a general repair. Production tooling must either:

- remap public outputs, public inputs, private inputs, and remaining witnesses into the target R1CS wire convention; or
- reject artifacts whose witness layout does not already satisfy that convention.

The original `circuits/square-root` fixture remains unchanged as a regression case.
