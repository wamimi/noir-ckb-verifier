// Prints C(value, blinding, key) so off-circuit tools compute commitments with
// exactly the circuit's code. Not proved or deployed.
use private_tally_commitment::commit;

fn main(value: Field, blinding: Field, key: Field) -> pub Field {
    commit(value, blinding, key)
}
