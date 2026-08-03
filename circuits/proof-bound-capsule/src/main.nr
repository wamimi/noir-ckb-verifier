// Week 10 compatibility fixture for an explicit, transaction-derived public tuple.
// Public parameters precede the private witness because the pinned experimental
// ACIR-to-R1CS backend does not yet implement general public-wire remapping.
fn main(
    capsule_id: pub Field,
    old_state_commitment: pub Field,
    old_nullifier: pub Field,
    new_state_commitment: pub Field,
    action_id: pub Field,
    new_nullifier: pub Field,
    replay_domain: pub Field,
    authorization_secret: Field,
) {
    assert(old_state_commitment == authorization_secret * authorization_secret + capsule_id + old_nullifier);
    assert(new_state_commitment == old_state_commitment + action_id);
    assert(new_nullifier == authorization_secret * replay_domain + old_nullifier);
}
