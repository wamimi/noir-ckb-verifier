use std::path::{Path, PathBuf};

use artifact_adapter::{
    build_wire_artifacts, convert, json::read_json, load_and_convert, load_public_inputs, verify,
    verify_endpoint_round_trip, AdapterError,
};

fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/week-09-public-first")
        .join(name)
}

fn converted() -> artifact_adapter::ConvertedArtifacts {
    load_and_convert(
        &fixture("verification_key.json"),
        &fixture("proof.json"),
        &fixture("public.json"),
    )
    .expect("fixture must convert")
}

#[test]
fn retained_proof_verifies_with_49_and_rejects_7() {
    let converted = converted();
    assert!(verify(
        &converted.verifying_key,
        &converted.public_inputs,
        &converted.proof
    )
    .expect("positive verification should execute"));

    let wrong = load_public_inputs(&fixture("wrong-public.json")).expect("negative fixture parses");
    assert!(!verify(&converted.verifying_key, &wrong, &converted.proof)
        .expect("negative verification should execute"));
}

#[test]
fn molecule_round_trip_matches_endpoint_and_verifies() {
    let converted = converted();
    let wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )
    .expect("wire encoding succeeds");

    assert_eq!(wire.proof_bytes.len(), 128);
    assert_eq!(wire.public_inputs_bytes.len(), 36);
    verify_endpoint_round_trip(&wire).expect("pinned endpoint round trip verifies");
}

#[test]
fn conversion_rejects_wrong_protocol() {
    let vk = read_json(&fixture("verification_key.json")).expect("VK fixture parses");
    let mut proof: artifact_adapter::json::SnarkJsProof =
        read_json(&fixture("proof.json")).expect("proof fixture parses");
    let public: Vec<String> = read_json(&fixture("public.json")).expect("public fixture parses");
    proof.protocol = "plonk".to_owned();

    assert!(matches!(
        convert(&vk, &proof, &public),
        Err(AdapterError::UnsupportedProtocol(_))
    ));
}

#[test]
fn conversion_rejects_public_input_count_mismatch() {
    let mut vk: artifact_adapter::json::SnarkJsVerifyingKey =
        read_json(&fixture("verification_key.json")).expect("VK fixture parses");
    let proof = read_json(&fixture("proof.json")).expect("proof fixture parses");
    let public: Vec<String> = read_json(&fixture("public.json")).expect("public fixture parses");
    vk.n_public = 2;

    assert!(matches!(
        convert(&vk, &proof, &public),
        Err(AdapterError::PublicInputCount { .. })
    ));
}

#[test]
fn endpoint_rejects_wrong_public_input_after_wire_round_trip() {
    let converted = converted();
    let wrong = load_public_inputs(&fixture("wrong-public.json")).expect("negative fixture parses");
    let wire = build_wire_artifacts(&converted.verifying_key, &converted.proof, &wrong)
        .expect("negative wire encoding is structurally valid");

    assert!(matches!(
        verify_endpoint_round_trip(&wire),
        Err(AdapterError::EndpointVerification(_))
    ));
}

#[test]
fn endpoint_decoder_rejects_wrong_wire_version() {
    let converted = converted();
    let mut wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )
    .expect("wire encoding succeeds");

    let version_offset = u32::from_le_bytes(
        wire.vk_molecule[4..8]
            .try_into()
            .expect("Molecule table offset is four bytes"),
    ) as usize;
    wire.vk_molecule[version_offset..version_offset + 2].copy_from_slice(&2u16.to_le_bytes());

    assert!(matches!(
        verify_endpoint_round_trip(&wire),
        Err(AdapterError::WireDecode { .. })
    ));
}

#[test]
fn endpoint_decoder_rejects_truncated_molecule_witness() {
    let converted = converted();
    let mut wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )
    .expect("wire encoding succeeds");
    wire.witness_molecule.pop();

    assert!(matches!(
        verify_endpoint_round_trip(&wire),
        Err(AdapterError::WireDecode { .. })
    ));
}
