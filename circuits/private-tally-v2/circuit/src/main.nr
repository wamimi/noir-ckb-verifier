// noir-ckb/private-tally/v2 circuit. Specification: docs/private-tally-v2-spec.md.
//
// Statement: the prover knows (value_old, r_old, key, delta, r_new) such that
//   creation (c_old == 0): value_old == 0, delta == 0, c_new == C(0, r_new, key);
//   update   (c_old != 0): c_old == C(value_old, r_old, key), delta <= MAX_DELTA,
//                          c_new == C(value_old + delta, r_new, key);
// with value_old and value_old + delta below 2^64, and (ctx_lo, ctx_hi) the two
// 128-bit halves of the transaction context digest checked by the Type Script.
//
// Parameter order is private first, then public: the layout covered by the
// pinned backend's visibility-ordering correction. The commitment C is defined in
// the shared library ../commitment.
use private_tally_commitment::commit;

// Largest increment per update: 2^32 - 1, enforced as a 32-bit range check.
global MAX_DELTA_BITS: u32 = 32;

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
    value_old.assert_max_bit_size::<64>();
    delta.assert_max_bit_size::<64>();

    if c_old == 0 {
        assert(value_old == 0, "creation must start at zero");
        assert(delta == 0, "creation must not add");
    } else {
        assert(commit(value_old, r_old, key) == c_old, "old commitment does not open");
        delta.assert_max_bit_size::<MAX_DELTA_BITS>();
    }

    let value_new = value_old + delta;
    value_new.assert_max_bit_size::<64>();
    assert(c_new != 0, "zero is reserved as the creation sentinel");
    assert(commit(value_new, r_new, key) == c_new, "new commitment does not open");

    ctx_lo.assert_max_bit_size::<128>();
    ctx_hi.assert_max_bit_size::<128>();
}

// ---------------------------------------------------------------- tests

global KEY: Field = 0x1f2e3d4c5b6a79880123456789abcdef;
global R0: Field = 0x11111111111111111111;
global R1: Field = 0x22222222222222222222;
global R2: Field = 0x33333333333333333333;
global LO: Field = 0xffffffffffffffffffffffffffffffff; // 2^128 - 1
global HI: Field = 7;

#[test]
fn creation_at_zero() {
    main(0, 0, KEY, 0, R0, 0, commit(0, R0, KEY), LO, HI);
}

#[test(should_fail_with = "creation must start at zero")]
fn creation_with_nonzero_value() {
    main(5, 0, KEY, 0, R0, 0, commit(5, R0, KEY), LO, HI);
}

#[test(should_fail_with = "creation must not add")]
fn creation_with_increment() {
    main(0, 0, KEY, 1, R0, 0, commit(1, R0, KEY), LO, HI);
}

#[test]
fn update_adds_delta() {
    let c_old = commit(10, R0, KEY);
    main(10, R0, KEY, 5, R1, c_old, commit(15, R1, KEY), LO, HI);
}

#[test]
fn update_with_zero_delta_changes_commitment() {
    let c_old = commit(10, R0, KEY);
    let c_new = commit(10, R1, KEY);
    assert(c_old != c_new);
    main(10, R0, KEY, 0, R1, c_old, c_new, LO, HI);
}

#[test]
fn chained_updates() {
    let c0 = commit(0, R0, KEY);
    main(0, 0, KEY, 0, R0, 0, c0, LO, HI);
    let c1 = commit(3, R1, KEY);
    main(0, R0, KEY, 3, R1, c0, c1, LO, HI);
    let c2 = commit(7, R2, KEY);
    main(3, R1, KEY, 4, R2, c1, c2, LO, HI);
}

#[test]
fn update_with_max_delta() {
    let c_old = commit(1, R0, KEY);
    main(
        1,
        R0,
        KEY,
        0xffffffff,
        R1,
        c_old,
        commit(0x100000000, R1, KEY),
        LO,
        HI,
    );
}

#[test(should_fail)]
fn update_above_max_delta() {
    let c_old = commit(1, R0, KEY);
    main(
        1,
        R0,
        KEY,
        0x100000000,
        R1,
        c_old,
        commit(0x100000001, R1, KEY),
        LO,
        HI,
    );
}

#[test]
fn update_to_largest_u64() {
    let v = 0xffffffffffffffff - 7;
    let c_old = commit(v, R0, KEY);
    main(
        v,
        R0,
        KEY,
        7,
        R1,
        c_old,
        commit(0xffffffffffffffff, R1, KEY),
        LO,
        HI,
    );
}

#[test(should_fail)]
fn update_overflowing_u64() {
    let v = 0xffffffffffffffff;
    let c_old = commit(v, R0, KEY);
    main(
        v,
        R0,
        KEY,
        1,
        R1,
        c_old,
        commit(0x10000000000000000, R1, KEY),
        LO,
        HI,
    );
}

#[test(should_fail)]
fn old_value_above_u64() {
    let v = 0x10000000000000000;
    let c_old = commit(v, R0, KEY);
    main(v, R0, KEY, 0, R1, c_old, commit(v, R1, KEY), LO, HI);
}

#[test(should_fail_with = "old commitment does not open")]
fn update_with_wrong_key() {
    let c_old = commit(10, R0, KEY);
    main(
        10,
        R0,
        KEY + 1,
        1,
        R1,
        c_old,
        commit(11, R1, KEY + 1),
        LO,
        HI,
    );
}

#[test(should_fail_with = "old commitment does not open")]
fn update_with_wrong_old_blinding() {
    let c_old = commit(10, R0, KEY);
    main(10, R2, KEY, 1, R1, c_old, commit(11, R1, KEY), LO, HI);
}

#[test(should_fail_with = "old commitment does not open")]
fn update_claiming_wrong_old_value() {
    let c_old = commit(10, R0, KEY);
    main(9, R0, KEY, 2, R1, c_old, commit(11, R1, KEY), LO, HI);
}

#[test(should_fail_with = "new commitment does not open")]
fn new_commitment_for_a_different_value() {
    let c_old = commit(10, R0, KEY);
    main(10, R0, KEY, 1, R1, c_old, commit(12, R1, KEY), LO, HI);
}

#[test(should_fail_with = "new commitment does not open")]
fn new_commitment_under_a_different_key() {
    let c_old = commit(10, R0, KEY);
    main(10, R0, KEY, 1, R1, c_old, commit(11, R1, KEY + 1), LO, HI);
}

#[test(should_fail_with = "zero is reserved as the creation sentinel")]
fn zero_new_commitment() {
    main(0, 0, KEY, 0, R0, 0, 0, LO, HI);
}

#[test(should_fail)]
fn context_low_half_above_128_bits() {
    main(0, 0, KEY, 0, R0, 0, commit(0, R0, KEY), LO + 1, HI);
}

#[test(should_fail)]
fn context_high_half_above_128_bits() {
    main(0, 0, KEY, 0, R0, 0, commit(0, R0, KEY), LO, LO + 1);
}
