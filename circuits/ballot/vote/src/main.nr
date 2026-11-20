// noir-ckb/ballot-box/v1 vote circuit. Description: circuits/ballot/README.md. Binding spec:
// research/spikes/toolkit-architecture/specs/ballot-box.toml.
//
// Statement: the prover knows `secret` and a Merkle path (siblings s0..s18 and position bits
// b0..b18, lowest level first) such that
//   1. identity(secret) is a leaf of the voter tree with root `voter_root`;
//   2. nullifier == nullifier(secret, election_lo, election_hi);
//   3. choice is 0 or 1;
// and (ctx_lo, ctx_hi) are the two 128-bit halves of the context digest the Type Script
// rebuilds. The context holds the nullifier and the choice, so a proof cannot be reused
// with another choice.
//
// One proof carries one nullifier: a vote transaction inserts exactly one key into the
// ballot box's nullifier set.
//
// Parameter order is private first, then public, in the order the binding spec lists the
// public inputs. Every parameter is a Field: the toolkit and the pinned backend's layout
// correction cover scalar parameters only, which is why the path is 40 parameters and not
// two arrays.
use ballot_hashes::{identity, nullifier as nullifier_of, root_from_path};

fn main(
    secret: Field,
    s0: Field, s1: Field, s2: Field, s3: Field, s4: Field,
    s5: Field, s6: Field, s7: Field, s8: Field, s9: Field,
    s10: Field, s11: Field, s12: Field, s13: Field, s14: Field,
    s15: Field, s16: Field, s17: Field, s18: Field,
    b0: Field, b1: Field, b2: Field, b3: Field, b4: Field,
    b5: Field, b6: Field, b7: Field, b8: Field, b9: Field,
    b10: Field, b11: Field, b12: Field, b13: Field, b14: Field,
    b15: Field, b16: Field, b17: Field, b18: Field,
    voter_root: pub Field,
    election_lo: pub Field,
    election_hi: pub Field,
    nullifier: pub Field,
    choice: pub Field,
    ctx_lo: pub Field,
    ctx_hi: pub Field,
) {
    let siblings = [
        s0, s1, s2, s3, s4, s5, s6, s7, s8, s9,
        s10, s11, s12, s13, s14, s15, s16, s17, s18,
    ];
    let bits = [
        b0, b1, b2, b3, b4, b5, b6, b7, b8, b9,
        b10, b11, b12, b13, b14, b15, b16, b17, b18,
    ];
    assert(root_from_path(identity(secret), siblings, bits) == voter_root, "not a member of the voter set");
    assert(nullifier_of(secret, election_lo, election_hi) == nullifier, "nullifier does not match the secret and election");
    assert(choice * (choice - 1) == 0, "choice is not 0 or 1");

    election_lo.assert_max_bit_size::<128>();
    election_hi.assert_max_bit_size::<128>();
    ctx_lo.assert_max_bit_size::<128>();
    ctx_hi.assert_max_bit_size::<128>();
}

// ---------------------------------------------------------------- tests
use ballot_hashes::DEPTH;

global ALICE: Field = 0x1f2e3d4c5b6a79880123456789abcdef;
global BOB: Field = 0x0fedcba98765432100112233445566778899;
global MALLORY: Field = 0x5555555555555555555555555555;
global ELECTION_LO: Field = 0xffffffffffffffffffffffffffffffff; // 2^128 - 1
global ELECTION_HI: Field = 0x0123456789abcdef0123456789abcdef;
global OTHER_LO: Field = 0xfffffffffffffffffffffffffffffffe;
global LO: Field = 13;
global HI: Field = 17;

// A voter tree described by one path: Alice at position `bits`, Bob as her neighbour at
// level 0, and fixed values for the other siblings.
fn alice_siblings() -> [Field; DEPTH] {
    let mut siblings = [0; DEPTH];
    for i in 0..DEPTH {
        siblings[i] = 1000 + i as Field;
    }
    siblings[0] = identity(BOB);
    siblings
}

fn alice_bits() -> [Field; DEPTH] {
    let mut bits = [0; DEPTH];
    for i in 0..DEPTH {
        bits[i] = if (i % 3) == 1 { 1 } else { 0 };
    }
    bits
}

fn root() -> Field {
    root_from_path(identity(ALICE), alice_siblings(), alice_bits())
}

// Calls main with a path given as arrays.
fn vote(
    secret: Field,
    s: [Field; DEPTH],
    b: [Field; DEPTH],
    voter_root: Field,
    election_lo: Field,
    election_hi: Field,
    nullifier: Field,
    choice: Field,
    ctx_lo: Field,
    ctx_hi: Field,
) {
    main(
        secret,
        s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9], s[10], s[11], s[12], s[13], s[14], s[15], s[16], s[17], s[18],
        b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15], b[16], b[17], b[18],
        voter_root,
        election_lo,
        election_hi,
        nullifier,
        choice,
        ctx_lo,
        ctx_hi,
    );
}

fn alice_votes(choice: Field) {
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, choice, LO, HI);
}

#[test]
fn member_votes_zero() {
    alice_votes(0);
}

#[test]
fn member_votes_one() {
    alice_votes(1);
}

#[test]
fn second_member_of_the_same_tree_votes() {
    // Bob is Alice's neighbour: same path with level 0 mirrored, same root.
    let mut siblings = alice_siblings();
    siblings[0] = identity(ALICE);
    let mut bits = alice_bits();
    bits[0] = 1;
    let nf = nullifier_of(BOB, ELECTION_LO, ELECTION_HI);
    assert(nf != nullifier_of(ALICE, ELECTION_LO, ELECTION_HI));
    vote(BOB, siblings, bits, root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test]
fn members_at_the_first_and_last_position_vote() {
    let siblings = alice_siblings();
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    let first = [0; DEPTH];
    let last = [1; DEPTH];
    vote(ALICE, siblings, first, root_from_path(identity(ALICE), siblings, first), ELECTION_LO, ELECTION_HI, nf, 0, LO, HI);
    vote(ALICE, siblings, last, root_from_path(identity(ALICE), siblings, last), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test]
fn nullifier_is_fixed_per_election_and_differs_between_elections() {
    // The same voter in the same election has one nullifier whatever the choice, so a
    // second vote meets a used nullifier. In another election the nullifier differs and
    // the same voter can vote there.
    let here = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    let there = nullifier_of(ALICE, OTHER_LO, ELECTION_HI);
    assert(here != there);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, here, 0, LO, HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, here, 1, LO, HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), OTHER_LO, ELECTION_HI, there, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn non_member_is_rejected() {
    // Mallory uses a real member's path and her own, correctly derived, nullifier.
    let nf = nullifier_of(MALLORY, ELECTION_LO, ELECTION_HI);
    vote(MALLORY, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "choice is not 0 or 1")]
fn choice_two_is_rejected() {
    alice_votes(2);
}

#[test(should_fail_with = "choice is not 0 or 1")]
fn choice_minus_one_is_rejected() {
    alice_votes(0 - 1);
}

#[test(should_fail_with = "nullifier does not match the secret and election")]
fn nullifier_of_another_secret_is_rejected() {
    let nf = nullifier_of(BOB, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "nullifier does not match the secret and election")]
fn nullifier_of_another_election_is_rejected() {
    let nf = nullifier_of(ALICE, OTHER_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "nullifier does not match the secret and election")]
fn nullifier_with_election_halves_exchanged_is_rejected() {
    let nf = nullifier_of(ALICE, ELECTION_HI, ELECTION_LO);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "nullifier does not match the secret and election")]
fn arbitrary_nullifier_is_rejected() {
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, 12345, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn tampered_sibling_is_rejected() {
    let mut siblings = alice_siblings();
    siblings[7] += 1;
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, siblings, alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn tampered_top_sibling_is_rejected() {
    let mut siblings = alice_siblings();
    siblings[DEPTH - 1] += 1;
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, siblings, alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn flipped_path_bit_is_rejected() {
    let mut bits = alice_bits();
    bits[4] = 1 - bits[4];
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), bits, root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "path bit is not 0 or 1")]
fn non_boolean_path_bit_is_rejected() {
    let mut bits = alice_bits();
    bits[4] = 2;
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), bits, root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn wrong_voter_root_is_rejected() {
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root() + 1, ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail_with = "not a member of the voter set")]
fn inner_node_presented_as_a_voter_is_rejected() {
    // A prover who claims the level-1 node as a leaf would need a secret whose identity
    // equals it; using the node's value as the secret does not work.
    let level_one = ballot_hashes::node(identity(ALICE), identity(BOB));
    let nf = nullifier_of(level_one, ELECTION_LO, ELECTION_HI);
    vote(level_one, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail)]
fn election_half_above_128_bits_is_rejected() {
    let wide = 0x100000000000000000000000000000000; // 2^128
    let nf = nullifier_of(ALICE, wide, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), wide, ELECTION_HI, nf, 1, LO, HI);
}

#[test(should_fail)]
fn context_half_above_128_bits_is_rejected() {
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 1, 0x100000000000000000000000000000000, HI);
}

#[test]
fn context_halves_at_their_maximum() {
    let max = 0xffffffffffffffffffffffffffffffff;
    let nf = nullifier_of(ALICE, ELECTION_LO, ELECTION_HI);
    vote(ALICE, alice_siblings(), alice_bits(), root(), ELECTION_LO, ELECTION_HI, nf, 0, max, max);
}
