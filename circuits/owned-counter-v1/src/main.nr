// Public proof-enforcement example. No privacy or hiding commitment is claimed.
fn main(old_count: pub Field, new_count: pub Field, context_lo: pub Field, context_hi: pub Field) {
    assert(old_count == (old_count as u64) as Field);
    assert(new_count == (new_count as u64) as Field);
    assert(new_count == old_count + 1);
    assert(context_lo == (context_lo as u128) as Field);
    assert(context_hi == (context_hi as u128) as Field);
}
