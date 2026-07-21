// Compatibility control for backends that preserve ACIR witness indices as R1CS wire indices.
// The original Week 7 fixture remains unchanged for regression evidence.
fn main(y: pub Field, x: Field) {
    assert(x * x == y);
}
