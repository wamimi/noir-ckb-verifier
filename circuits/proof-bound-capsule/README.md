# Proof-bound Capsule fixture

This development circuit makes the application authorization boundary explicit.
Its ordered Groth16 public-input vector is:

1. `capsule_id`
2. `old_state_commitment`
3. `old_nullifier`
4. `new_state_commitment`
5. `action_id`
6. `new_nullifier`
7. `replay_domain`

The private `authorization_secret` participates in constraints tying the old
state, new state, nullifier, identity, action, and replay domain together. The
fixture values are intentionally public test data and are not credentials.

The public-first parameter order is a pinned-backend compatibility restriction,
not a general Noir requirement. Week 8 demonstrated that the current
experimental backend misclassifies a private-first ACIR witness layout when it
copies witness indices directly into R1CS public-wire positions.

This circuit is an application-boundary prototype. Its arithmetic is deliberately
small and is not a production Capsule authorization protocol.
