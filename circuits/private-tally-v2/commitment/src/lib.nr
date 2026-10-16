// Commitment for noir-ckb/private-tally/v2 (docs/private-tally-v2-spec.md, section 2):
//   inner        = Poseidon2([TAG_INNER, r, key])
//   C(v, r, key) = Poseidon2([TAG_STATE, v, inner])
// Both calls take exactly 3 inputs.
use poseidon::poseidon2::Poseidon2;

// Big-endian integers of the ASCII strings "noir-ckb:tally:v2:state" and
// "noir-ckb:tally:v2:inner" (23 bytes each, below the BN254 scalar modulus).
pub global TAG_STATE: Field = 0x6e6f69722d636b623a74616c6c793a76323a7374617465;
pub global TAG_INNER: Field = 0x6e6f69722d636b623a74616c6c793a76323a696e6e6572;

pub fn commit(value: Field, blinding: Field, key: Field) -> Field {
    let inner = Poseidon2::hash([TAG_INNER, blinding, key], 3);
    Poseidon2::hash([TAG_STATE, value, inner], 3)
}

#[test]
fn tags_are_the_documented_ascii_strings() {
    let state: [u8; 23] = TAG_STATE.to_be_bytes();
    let inner: [u8; 23] = TAG_INNER.to_be_bytes();
    assert(state == "noir-ckb:tally:v2:state".as_bytes());
    assert(inner == "noir-ckb:tally:v2:inner".as_bytes());
}

#[test]
fn commitment_depends_on_every_input() {
    let base = commit(1, 2, 3);
    assert(base != commit(2, 2, 3));
    assert(base != commit(1, 3, 3));
    assert(base != commit(1, 2, 4));
    assert(base != 0);
}
