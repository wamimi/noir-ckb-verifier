use std::path::PathBuf;

use artifact_adapter::{build_wire_artifacts, load_and_convert, load_public_inputs, WireArtifacts};
use ckb_integration_tests::fixture_path;
use ckb_testtool::builtin::ALWAYS_SUCCESS;
use ckb_testtool::ckb_error::Error as CkbError;
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::{Cycle, TransactionBuilder},
    packed::{CellDep, CellInput, CellOutput, WitnessArgs},
    prelude::*,
};
use ckb_testtool::context::Context;

const MAX_CYCLES: u64 = 250_000_000;
const ERROR_VERIFICATION_FAILED: i8 = 5;

fn verifier_binary() -> Bytes {
    let path = std::env::var_os("GROTH16_CKB_SCRIPT_BIN")
        .map(PathBuf::from)
        .expect("GROTH16_CKB_SCRIPT_BIN must point to the pinned production verifier binary");
    let bytes = std::fs::read(&path)
        .unwrap_or_else(|error| panic!("failed to read {}: {error}", path.display()));
    bytes.into()
}

fn intended_wire() -> WireArtifacts {
    let converted = load_and_convert(
        &fixture_path("verification_key.json"),
        &fixture_path("proof.json"),
        &fixture_path("public.json"),
    )
    .expect("Week 10 fixture must convert");
    build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )
    .expect("Week 10 fixture must encode")
}

fn wrong_new_state_wire() -> WireArtifacts {
    let converted = load_and_convert(
        &fixture_path("verification_key.json"),
        &fixture_path("proof.json"),
        &fixture_path("public.json"),
    )
    .expect("Week 10 fixture must convert");
    let wrong = load_public_inputs(&fixture_path("wrong-new-state-public.json"))
        .expect("negative public vector must parse");
    build_wire_artifacts(&converted.verifying_key, &converted.proof, &wrong)
        .expect("negative vector must remain structurally encodable")
}

fn run_tx(wire: &WireArtifacts) -> Result<Cycle, CkbError> {
    let mut context = Context::default();
    let verifier_op = context.deploy_cell(verifier_binary());
    let always_success_op = context.deploy_cell(ALWAYS_SUCCESS.clone());
    let vk_op = context.deploy_cell(Bytes::from(wire.vk_molecule.clone()));

    let verifier = context
        .build_script(&verifier_op, Bytes::from(wire.vk_data_hash.to_vec()))
        .expect("verifier script");
    let always_success = context
        .build_script(&always_success_op, Bytes::new())
        .expect("always-success lock");

    let input_out_point = context.create_cell(
        CellOutput::new_builder()
            .capacity(1_000u64)
            .lock(always_success.clone())
            .type_(Some(verifier).pack())
            .build(),
        Bytes::new(),
    );
    let input = CellInput::new_builder()
        .previous_output(input_out_point)
        .build();
    let output = CellOutput::new_builder()
        .capacity(500u64)
        .lock(always_success)
        .build();
    let witness = WitnessArgs::new_builder()
        .input_type(Some(Bytes::from(wire.witness_molecule.clone())).pack())
        .build();

    let tx = TransactionBuilder::default()
        .input(input)
        .output(output)
        .output_data(Bytes::new().pack())
        .cell_dep(CellDep::new_builder().out_point(verifier_op).build())
        .cell_dep(CellDep::new_builder().out_point(always_success_op).build())
        .cell_dep(CellDep::new_builder().out_point(vk_op).build())
        .witness(witness.as_bytes().pack())
        .build();
    let tx = context.complete_tx(tx);
    context.verify_tx(&tx, MAX_CYCLES)
}

fn assert_exit_code(error: &CkbError, expected: i8) {
    let rendered = error.to_string();
    let needle = format!("code {expected}");
    assert!(
        rendered.contains(&needle),
        "expected `{needle}` in CKB error, got: {rendered}"
    );
}

#[test]
#[ignore = "requires GROTH16_CKB_SCRIPT_BIN pointing to the pinned RISC-V verifier"]
fn noir_capsule_proof_verifies_in_ckb_vm() {
    let cycles = run_tx(&intended_wire()).expect("CKB-VM must accept the Noir-derived proof");
    eprintln!("week10_noir_capsule_verifier_cycles={cycles}");
}

#[test]
#[ignore = "requires GROTH16_CKB_SCRIPT_BIN pointing to the pinned RISC-V verifier"]
fn altered_new_state_public_input_is_rejected_in_ckb_vm() {
    let error = run_tx(&wrong_new_state_wire())
        .expect_err("CKB-VM must reject the unchanged proof with a changed public input");
    assert_exit_code(&error, ERROR_VERIFICATION_FAILED);
}
