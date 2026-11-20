// Hashes for noir-ckb/ballot-box/v1 (circuits/ballot/README.md). Poseidon2 over BN254 as in
// noir-lang/poseidon v0.2.6; every call takes 2 or 3 inputs.
//
//   identity  = Poseidon2([TAG_IDENTITY, secret])                 a voter's leaf
//   node      = Poseidon2([TAG_NODE, left, right])                an inner node of the voter tree
//   election  = Poseidon2([TAG_ELECTION, election_lo, election_hi])
//   nullifier = Poseidon2([TAG_NULLIFIER, secret, election])
//
// Leaves and inner nodes are in different domains (two inputs against three, and different
// tags), so an inner node cannot be presented as a leaf.
use poseidon::poseidon2::Poseidon2;

// Depth of the voter tree: 2^19 = 524,288 voters.
pub global DEPTH: u32 = 19;

// Big-endian integers of the ASCII strings named in the test below (at most 28 bytes each,
// so below the BN254 scalar modulus).
pub global TAG_IDENTITY: Field = 0x6e6f69722d636b623a62616c6c6f743a76313a6964656e74697479;
pub global TAG_NODE: Field = 0x6e6f69722d636b623a62616c6c6f743a76313a6e6f6465;
pub global TAG_ELECTION: Field = 0x6e6f69722d636b623a62616c6c6f743a76313a656c656374696f6e;
pub global TAG_NULLIFIER: Field = 0x6e6f69722d636b623a62616c6c6f743a76313a6e756c6c6966696572;

pub fn identity(secret: Field) -> Field {
    Poseidon2::hash([TAG_IDENTITY, secret], 2)
}

pub fn node(left: Field, right: Field) -> Field {
    Poseidon2::hash([TAG_NODE, left, right], 3)
}

// The election id is the ballot box's 32-byte Type ID, passed as two 128-bit halves.
pub fn nullifier(secret: Field, election_lo: Field, election_hi: Field) -> Field {
    let election = Poseidon2::hash([TAG_ELECTION, election_lo, election_hi], 3);
    Poseidon2::hash([TAG_NULLIFIER, secret, election], 3)
}

// Root of the tree that has `leaf` at the position whose bits, lowest level first, are `bits`.
// A bit of 1 means the running node is the right child at that level.
pub fn root_from_path(leaf: Field, siblings: [Field; DEPTH], bits: [Field; DEPTH]) -> Field {
    let mut current = leaf;
    for i in 0..DEPTH {
        let bit = bits[i];
        assert(bit * (bit - 1) == 0, "path bit is not 0 or 1");
        let left = current + bit * (siblings[i] - current);
        let right = siblings[i] + bit * (current - siblings[i]);
        current = node(left, right);
    }
    current
}

#[test]
fn tags_are_the_documented_ascii_strings() {
    let identity_tag: [u8; 27] = TAG_IDENTITY.to_be_bytes();
    let node_tag: [u8; 23] = TAG_NODE.to_be_bytes();
    let election_tag: [u8; 27] = TAG_ELECTION.to_be_bytes();
    let nullifier_tag: [u8; 28] = TAG_NULLIFIER.to_be_bytes();
    assert(identity_tag == "noir-ckb:ballot:v1:identity".as_bytes());
    assert(node_tag == "noir-ckb:ballot:v1:node".as_bytes());
    assert(election_tag == "noir-ckb:ballot:v1:election".as_bytes());
    assert(nullifier_tag == "noir-ckb:ballot:v1:nullifier".as_bytes());
}

#[test]
fn hashes_depend_on_every_input() {
    assert(identity(1) != identity(2));
    assert(node(1, 2) != node(2, 1));
    assert(node(1, 2) != node(1, 3));
    let base = nullifier(1, 2, 3);
    assert(base != nullifier(2, 2, 3));
    assert(base != nullifier(1, 3, 3));
    assert(base != nullifier(1, 2, 4));
    assert(base != nullifier(1, 3, 2));
}

#[test]
fn a_leaf_is_not_an_inner_node() {
    // identity(x) hashes [TAG_IDENTITY, x]; node(l, r) hashes [TAG_NODE, l, r].
    assert(identity(7) != node(7, 0));
    assert(identity(7) != node(0, 7));
}

#[test]
fn path_bit_selects_the_side() {
    let siblings = [5; DEPTH];
    let left_bits = [0; DEPTH];
    let mut right_bits = [0; DEPTH];
    right_bits[0] = 1;
    let as_left = root_from_path(9, siblings, left_bits);
    let as_right = root_from_path(9, siblings, right_bits);
    assert(as_left != as_right);
    // Position 0 with sibling 5 and position 1 with sibling 9 describe the same pair of leaves.
    let mut swapped = siblings;
    swapped[0] = 9;
    assert(root_from_path(5, swapped, right_bits) == as_left);
}

#[test(should_fail_with = "path bit is not 0 or 1")]
fn path_bit_must_be_boolean() {
    let mut bits = [0; DEPTH];
    bits[3] = 2;
    let _ = root_from_path(9, [5; DEPTH], bits);
}
