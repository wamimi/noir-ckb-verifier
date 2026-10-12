// SPIKE ONLY: checks Poseidon2 lowering, conditional branches and private-first
// layout in the pinned backend. Not the reviewed private tally v2 protocol;
// domain tags and MAX_DELTA are placeholders.
use poseidon::poseidon2::Poseidon2;

global TAG_STATE: Field = 0x7461_6c6c_792d_7374_6174_65; // "tally-state"
global TAG_INNER: Field = 0x7461_6c6c_792d_696e_6e65_72; // "tally-inner"
global MAX_DELTA: u64 = 4294967295;

fn commit(value: Field, blinding: Field, key: Field) -> Field {
    let inner = Poseidon2::hash([TAG_INNER, blinding, key], 3);
    Poseidon2::hash([TAG_STATE, value, inner], 3)
}

fn main(
    value_old: Field,
    r_old: Field,
    key: Field,
    delta: Field,
    r_new: Field,
    c_old: pub Field,
    c_new: pub Field,
    ctx_lo: pub Field,
    ctx_hi: pub Field,
) {
    assert(value_old == (value_old as u64) as Field);
    assert(delta == (delta as u64) as Field);
    if c_old == 0 {
        // Creation: the first commitment must open to zero with no increment.
        assert(value_old == 0);
        assert(delta == 0);
    } else {
        assert(commit(value_old, r_old, key) == c_old);
        assert(delta as u64 <= MAX_DELTA);
    }
    let value_new = value_old + delta;
    assert(value_new == (value_new as u64) as Field);
    assert(commit(value_new, r_new, key) == c_new);
    assert(ctx_lo == (ctx_lo as u128) as Field);
    assert(ctx_hi == (ctx_hi as u128) as Field);
}
