// Prints [identity, voter_root, nullifier] for a voter secret, a Merkle path and an election
// id, with the same library the vote circuit uses. Not a proved statement: it is executed
// with `nargo execute` by scripts/check-ballot-vote-circuit.py.
use ballot_hashes::{identity, nullifier, root_from_path};

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
    election_lo: Field,
    election_hi: Field,
) -> pub [Field; 3] {
    let leaf = identity(secret);
    let siblings = [
        s0, s1, s2, s3, s4, s5, s6, s7, s8, s9,
        s10, s11, s12, s13, s14, s15, s16, s17, s18,
    ];
    let bits = [
        b0, b1, b2, b3, b4, b5, b6, b7, b8, b9,
        b10, b11, b12, b13, b14, b15, b16, b17, b18,
    ];
    [leaf, root_from_path(leaf, siblings, bits), nullifier(secret, election_lo, election_hi)]
}
