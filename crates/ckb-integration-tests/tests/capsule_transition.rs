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
const VERSION: u8 = 1;
const FIELD_LEN: usize = 32;

const ERROR_VERIFICATION_FAILED: i8 = 5;
const ERROR_VK_CELL_NOT_FOUND: i8 = 12;
const ERROR_VERIFIER_WITNESS_DECODE: i8 = 17;
const ERROR_ARGS_LENGTH: i8 = 21;
const ERROR_GROUP_SHAPE: i8 = 23;
const ERROR_CELL_DATA_ENCODING: i8 = 25;
const ERROR_PUBLIC_INPUT_MISMATCH: i8 = 30;
const ERROR_LOCK_CHANGED: i8 = 32;
const ERROR_LOCK_GROUP_SHAPE: i8 = 33;

fn binary_from_env(variable: &str) -> Bytes {
    let path = std::env::var_os(variable)
        .map(PathBuf::from)
        .unwrap_or_else(|| panic!("{variable} must point to a RISC-V script binary"));
    let bytes = std::fs::read(&path)
        .unwrap_or_else(|error| panic!("failed to read {}: {error}", path.display()));
    bytes.into()
}

fn wire_with_public(public_file: &str) -> WireArtifacts {
    let converted = load_and_convert(
        &fixture_path("verification_key.json"),
        &fixture_path("proof.json"),
        &fixture_path("public.json"),
    )
    .expect("Week 10 fixture must convert");
    let public_inputs =
        load_public_inputs(&fixture_path(public_file)).expect("public vector must parse");
    build_wire_artifacts(&converted.verifying_key, &converted.proof, &public_inputs)
        .expect("Week 10 fixture must encode")
}

fn intended_wire() -> WireArtifacts {
    wire_with_public("public.json")
}

fn public_value(wire: &WireArtifacts, index: usize) -> [u8; FIELD_LEN] {
    let start = 4 + index * FIELD_LEN;
    wire.public_inputs_bytes[start..start + FIELD_LEN]
        .try_into()
        .expect("public input is exactly 32 bytes")
}

#[derive(Clone, Copy)]
enum Case {
    Intended,
    WrongNewState,
    WrongCapsuleId,
    WrongReplayDomain,
    InvalidProofForMatchingTransition,
    MissingVkCell,
    TruncatedWitness,
    MalformedArgs,
    MalformedInputData,
    ChangedOutputLock,
    DuplicateVerifierLockInput,
    DuplicateCapsuleInput,
}

fn scalar(value: u8) -> [u8; FIELD_LEN] {
    let mut encoded = [0u8; FIELD_LEN];
    encoded[0] = value;
    encoded
}

fn capsule_args(wire: &WireArtifacts, case: Case) -> Vec<u8> {
    let capsule_id = match case {
        Case::WrongCapsuleId => scalar(12),
        _ => public_value(wire, 0),
    };
    let replay_domain = match case {
        Case::WrongReplayDomain => scalar(14),
        _ => public_value(wire, 6),
    };

    let mut args = Vec::with_capacity(1 + 2 * FIELD_LEN);
    args.push(VERSION);
    args.extend_from_slice(&capsule_id);
    args.extend_from_slice(&replay_domain);
    if matches!(case, Case::MalformedArgs) {
        args.pop();
    }
    args
}

fn capsule_data(state: &[u8; FIELD_LEN], nullifier: &[u8; FIELD_LEN]) -> Vec<u8> {
    let mut data = Vec::with_capacity(1 + 2 * FIELD_LEN);
    data.push(VERSION);
    data.extend_from_slice(state);
    data.extend_from_slice(nullifier);
    data
}

fn run_case(case: Case) -> Result<Cycle, CkbError> {
    let wire = match case {
        Case::InvalidProofForMatchingTransition => wire_with_public("wrong-new-state-public.json"),
        _ => intended_wire(),
    };
    let mut context = Context::default();

    let verifier_op = context.deploy_cell(binary_from_env("GROTH16_CKB_SCRIPT_BIN"));
    let binding_op = context.deploy_cell(binary_from_env("CKB_CAPSULE_BINDING_SCRIPT_BIN"));
    let vk_op = context.deploy_cell(Bytes::from(wire.vk_molecule.clone()));

    let verifier = context
        .build_script(&verifier_op, Bytes::from(wire.vk_data_hash.to_vec()))
        .expect("verifier lock script");
    let binding = context
        .build_script(&binding_op, Bytes::from(capsule_args(&wire, case)))
        .expect("Capsule binding type script");

    let mut old_data = capsule_data(&public_value(&wire, 1), &public_value(&wire, 2));
    if matches!(case, Case::MalformedInputData) {
        old_data.pop();
    }
    let new_state = match case {
        Case::WrongNewState => scalar(67),
        _ => public_value(&wire, 3),
    };
    let new_data = capsule_data(&new_state, &public_value(&wire, 5));

    let input_out_point = context.create_cell(
        CellOutput::new_builder()
            .capacity(1_000u64)
            .lock(verifier.clone())
            .type_(Some(binding.clone()).pack())
            .build(),
        Bytes::from(old_data.clone()),
    );
    let input = CellInput::new_builder()
        .previous_output(input_out_point)
        .build();

    let always_success = if matches!(case, Case::ChangedOutputLock) {
        let op = context.deploy_cell(ALWAYS_SUCCESS.clone());
        let script = context
            .build_script(&op, Bytes::new())
            .expect("alternate output lock");
        Some((op, script))
    } else {
        None
    };
    let output_lock = always_success
        .as_ref()
        .map_or_else(|| verifier.clone(), |(_, script)| script.clone());
    let output = CellOutput::new_builder()
        .capacity(500u64)
        .lock(output_lock)
        .type_(Some(binding.clone()).pack())
        .build();

    let mut witness_molecule = wire.witness_molecule;
    if matches!(case, Case::TruncatedWitness) {
        witness_molecule.truncate(witness_molecule.len() / 2);
    }
    let witness = WitnessArgs::new_builder()
        .input_type(Some(Bytes::from(witness_molecule)).pack())
        .build();

    let mut builder = TransactionBuilder::default()
        .input(input)
        .output(output)
        .output_data(Bytes::from(new_data).pack())
        .cell_dep(CellDep::new_builder().out_point(verifier_op).build())
        .cell_dep(CellDep::new_builder().out_point(binding_op).build())
        .witness(witness.as_bytes().pack());

    if !matches!(case, Case::MissingVkCell) {
        builder = builder.cell_dep(CellDep::new_builder().out_point(vk_op).build());
    }
    if let Some((op, _)) = always_success {
        builder = builder.cell_dep(CellDep::new_builder().out_point(op).build());
    }

    if matches!(
        case,
        Case::DuplicateVerifierLockInput | Case::DuplicateCapsuleInput
    ) {
        let duplicate_type = if matches!(case, Case::DuplicateCapsuleInput) {
            Some(binding).pack()
        } else {
            Option::<ckb_testtool::ckb_types::packed::Script>::None.pack()
        };
        let duplicate_out_point = context.create_cell(
            CellOutput::new_builder()
                .capacity(1_000u64)
                .lock(verifier)
                .type_(duplicate_type)
                .build(),
            Bytes::from(old_data),
        );
        builder = builder.input(
            CellInput::new_builder()
                .previous_output(duplicate_out_point)
                .build(),
        );
    }

    let tx = context.complete_tx(builder.build());
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

fn require_rejection(case: Case, expected: i8, label: &str) {
    let error = run_case(case).expect_err("transaction must be rejected");
    assert_exit_code(&error, expected);
    eprintln!("{label}={expected}");
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn valid_proof_and_correct_capsule_transition_accept() {
    let cycles = run_case(Case::Intended)
        .expect("the proof and transaction-derived public inputs must agree");
    eprintln!("week10_proof_bound_capsule_cycles={cycles}");
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn valid_proof_and_wrong_new_state_reject() {
    require_rejection(
        Case::WrongNewState,
        ERROR_PUBLIC_INPUT_MISMATCH,
        "week10_wrong_new_state_binding_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn valid_proof_and_wrong_capsule_id_reject() {
    require_rejection(
        Case::WrongCapsuleId,
        ERROR_PUBLIC_INPUT_MISMATCH,
        "week10_wrong_capsule_id_binding_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn valid_proof_and_wrong_replay_domain_reject() {
    require_rejection(
        Case::WrongReplayDomain,
        ERROR_PUBLIC_INPUT_MISMATCH,
        "week10_wrong_replay_domain_binding_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn invalid_proof_with_matching_changed_transition_rejects_in_verifier() {
    require_rejection(
        Case::InvalidProofForMatchingTransition,
        ERROR_VERIFICATION_FAILED,
        "week10_invalid_proof_verifier_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn missing_vk_cell_rejects_in_verifier() {
    require_rejection(
        Case::MissingVkCell,
        ERROR_VK_CELL_NOT_FOUND,
        "week10_missing_vk_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn truncated_witness_rejects_in_verifier() {
    require_rejection(
        Case::TruncatedWitness,
        ERROR_VERIFIER_WITNESS_DECODE,
        "week10_truncated_witness_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn malformed_capsule_args_reject() {
    require_rejection(
        Case::MalformedArgs,
        ERROR_ARGS_LENGTH,
        "week10_malformed_args_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn malformed_capsule_cell_data_reject() {
    require_rejection(
        Case::MalformedInputData,
        ERROR_CELL_DATA_ENCODING,
        "week10_malformed_cell_data_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn changed_verifier_lock_reject() {
    require_rejection(
        Case::ChangedOutputLock,
        ERROR_LOCK_CHANGED,
        "week10_changed_lock_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn duplicate_verifier_lock_input_rejects_witness_ambiguity() {
    require_rejection(
        Case::DuplicateVerifierLockInput,
        ERROR_LOCK_GROUP_SHAPE,
        "week10_duplicate_lock_group_exit_code",
    );
}

#[test]
#[ignore = "requires the pinned verifier and Capsule binding RISC-V binaries"]
fn duplicate_capsule_input_rejects_group_ambiguity() {
    require_rejection(
        Case::DuplicateCapsuleInput,
        ERROR_GROUP_SHAPE,
        "week10_duplicate_capsule_group_exit_code",
    );
}
