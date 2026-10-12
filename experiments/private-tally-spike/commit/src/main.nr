// Helper for the spike harness: prints the commitment for given openings.
use poseidon::poseidon2::Poseidon2;

global TAG_STATE: Field = 0x7461_6c6c_792d_7374_6174_65;
global TAG_INNER: Field = 0x7461_6c6c_792d_696e_6e65_72;

fn main(value: Field, blinding: Field, key: Field) -> pub Field {
    let inner = Poseidon2::hash([TAG_INNER, blinding, key], 3);
    Poseidon2::hash([TAG_STATE, value, inner], 3)
}
