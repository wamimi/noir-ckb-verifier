//! Explicit boundaries of the current protocol, including accepted exclusions.
//! These tests do not claim node consensus validation or production replay safety.
use artifact_adapter::{build_wire_artifacts, load_and_convert, WireArtifacts};
use ckb_integration_tests::fixture_path;
use ckb_testtool::ckb_error::Error as CkbError;
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::TransactionBuilder,
    packed::{CellDep, CellInput, CellOutput, OutPoint, WitnessArgs},
    prelude::*,
};
use ckb_testtool::{builtin::ALWAYS_SUCCESS, context::Context};

const MAX_CYCLES: u64 = 250_000_000;
#[derive(Default)]
struct Case {
    mismatch: Option<usize>,
    changed_public: Option<usize>,
    another_operation: bool,
    swapped_public: bool,
    corrupt_proof: bool,
    wrong_key: bool,
    rebind_wrong_key: bool,
    input_id: u8,
    capacity: Option<u64>,
    unrelated_output: bool,
    duplicate_lock_input: bool,
    duplicate_lock_output: bool,
    duplicate_type_output: bool,
    prefix_input: bool,
    misplaced_witness: bool,
    missing_input_type: bool,
    creation: bool,
    destruction: bool,
    nonverifier_lock: bool,
}
fn binary(name: &str) -> Bytes {
    std::fs::read(std::env::var_os(name).unwrap_or_else(|| panic!("missing {name}")))
        .expect("read actual RISC-V binary")
        .into()
}
fn data(a: &[u8; 32], b: &[u8; 32]) -> Bytes {
    let mut bytes = vec![1];
    bytes.extend(a);
    bytes.extend(b);
    bytes.into()
}
fn value(wire: &WireArtifacts, i: usize) -> [u8; 32] {
    wire.public_inputs_bytes[4 + i * 32..4 + (i + 1) * 32]
        .try_into()
        .unwrap()
}
fn run(case: Case) -> Result<u64, CkbError> {
    let mut converted = load_and_convert(
        &fixture_path("verification_key.json"),
        &fixture_path("proof.json"),
        &fixture_path("public.json"),
    )
    .unwrap();
    if let Some(i) = case.changed_public {
        converted.public_inputs[i] +=
            artifact_adapter::convert_public_inputs(&["1".into()]).unwrap()[0];
    }
    if case.another_operation {
        // Another satisfiable operation, with public fixture secret 8:
        // 80=8*8+11+5; 81=80+1; 109=8*13+5.
        converted.public_inputs = [11u64, 80, 5, 81, 1, 109, 13]
            .into_iter()
            .map(Into::into)
            .collect();
    }
    if case.swapped_public {
        converted.public_inputs.swap(0, 6);
    }
    if case.corrupt_proof {
        converted.proof.c = -converted.proof.c;
    }
    let wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )
    .unwrap();
    let mut fields: Vec<_> = (0..7).map(|i| value(&wire, i)).collect();
    if let Some(i) = case.mismatch {
        fields[i][0] ^= 1;
    }
    let alternate = if case.wrong_key || case.rebind_wrong_key {
        // A well-formed, same-width different key, not a malformed encoding.
        converted.verifying_key.alpha_g1 = -converted.verifying_key.alpha_g1;
        Some(
            build_wire_artifacts(
                &converted.verifying_key,
                &converted.proof,
                &converted.public_inputs,
            )
            .unwrap(),
        )
    } else {
        None
    };
    // Keep deployed code identities fixed across reuse cases so only the named
    // input/output change varies the raw transaction.
    let mut context = Context::new_with_deterministic_rng();
    let verifier_op = context.deploy_cell(binary("GROTH16_CKB_SCRIPT_BIN"));
    let binding_op = context.deploy_cell(binary("CKB_CAPSULE_BINDING_SCRIPT_BIN"));
    let always_op = context.deploy_cell(ALWAYS_SUCCESS.clone());
    let always = context.build_script(&always_op, Bytes::new()).unwrap();
    let committed_hash = if case.rebind_wrong_key {
        alternate.as_ref().unwrap().vk_data_hash
    } else {
        wire.vk_data_hash
    };
    let verifier = context
        .build_script(&verifier_op, Bytes::from(committed_hash.to_vec()))
        .unwrap();
    let lock = if case.nonverifier_lock {
        always.clone()
    } else {
        verifier
    };
    let binding = context
        .build_script(&binding_op, data(&fields[0], &fields[6]))
        .unwrap();
    let vk_op = context.deploy_cell(Bytes::from(
        alternate.as_ref().unwrap_or(&wire).vk_molecule.clone(),
    ));
    let old = CellOutput::new_builder()
        .capacity(1_000u64)
        .lock(lock.clone())
        .type_(Some(binding.clone()).pack())
        .build();
    let outpoint = OutPoint::new_builder()
        .tx_hash([case.input_id; 32])
        .index(0u32)
        .build();
    context.create_cell_with_out_point(outpoint.clone(), old.clone(), data(&fields[1], &fields[2]));
    let output = CellOutput::new_builder()
        .capacity(case.capacity.unwrap_or(500))
        .lock(lock.clone())
        .type_(Some(binding).pack())
        .build();
    let mut inputs = Vec::new();
    let mut witnesses = Vec::new();
    if case.prefix_input || case.creation {
        let op = context.create_cell(
            CellOutput::new_builder()
                .capacity(1_000u64)
                .lock(always.clone())
                .build(),
            Bytes::new(),
        );
        inputs.push(CellInput::new_builder().previous_output(op).build());
        witnesses.push(WitnessArgs::default().as_bytes().pack());
    }
    let input_type = if case.missing_input_type {
        None
    } else {
        Some(Bytes::from(wire.witness_molecule))
    };
    let proof_witness = WitnessArgs::new_builder()
        .input_type(input_type.pack())
        .build()
        .as_bytes()
        .pack();
    if !case.creation {
        inputs.push(CellInput::new_builder().previous_output(outpoint).build());
        witnesses.push(if case.misplaced_witness {
            WitnessArgs::default().as_bytes().pack()
        } else {
            proof_witness.clone()
        });
    }
    if case.misplaced_witness {
        witnesses.push(proof_witness);
    }
    if case.duplicate_lock_input {
        let op = context.create_cell(
            old.as_builder()
                .type_(Option::<ckb_testtool::ckb_types::packed::Script>::None.pack())
                .build(),
            Bytes::new(),
        );
        inputs.push(CellInput::new_builder().previous_output(op).build());
    }
    let mut outputs = Vec::new();
    let mut output_data = Vec::new();
    if !case.destruction {
        outputs.push(output.clone());
        output_data.push(data(&fields[3], &fields[5]).pack());
    }
    if case.duplicate_type_output {
        outputs.push(output);
        output_data.push(data(&fields[3], &fields[5]).pack());
    }
    if case.duplicate_lock_output || case.unrelated_output || case.destruction {
        let other_lock = if case.duplicate_lock_output {
            lock
        } else {
            always
        };
        outputs.push(
            CellOutput::new_builder()
                .capacity(100u64)
                .lock(other_lock)
                .build(),
        );
        output_data.push(Bytes::from_static(b"unrelated output data").pack());
    }
    let tx = TransactionBuilder::default()
        .set_inputs(inputs)
        .set_outputs(outputs)
        .set_outputs_data(output_data)
        .set_witnesses(witnesses)
        .cell_deps(
            [verifier_op, binding_op, always_op, vk_op]
                .into_iter()
                .map(|op| CellDep::new_builder().out_point(op).build()),
        )
        .build();
    let tx = context.complete_tx(tx);
    eprintln!("boundary_raw_tx_hash={:?}", tx.hash());
    context.verify_tx(&tx, MAX_CYCLES)
}
fn reject(case: Case, code: i8) {
    let error = run(case).expect_err("named protection must reject");
    let rendered = error.to_string();
    let observed: i8 = rendered
        .split("code ")
        .nth(1)
        .expect("script error, not unrelated VM failure")
        .split(|c: char| !c.is_ascii_digit() && c != '-')
        .next()
        .unwrap()
        .parse()
        .unwrap();
    assert_eq!(observed, code, "{rendered}");
    eprintln!("expected_script_rejection={code}: {rendered}");
}
macro_rules! vm_test {
    ($name:ident, $body:block) => {
        #[test]
        #[ignore = "requires pinned verifier and Capsule RISC-V binaries"]
        fn $name() $body
    };
}
vm_test!(baseline_accepts, {
    eprintln!("binding_boundary_cycles={}", run(Case::default()).unwrap());
});
vm_test!(each_cell_statement_field_mismatch_rejects, {
    for i in [0, 1, 2, 3, 5, 6] {
        reject(
            Case {
                mismatch: Some(i),
                ..Case::default()
            },
            30,
        );
    }
});
vm_test!(
    old_proof_with_each_changed_public_value_rejects_in_verifier,
    {
        for i in 0..7 {
            reject(
                Case {
                    changed_public: Some(i),
                    ..Case::default()
                },
                5,
            );
        }
    }
);
vm_test!(old_proof_with_recomputed_valid_operation_rejects, {
    reject(
        Case {
            another_operation: true,
            ..Case::default()
        },
        5,
    );
});
vm_test!(
    swapped_public_values_with_matching_cells_reject_in_verifier,
    {
        reject(
            Case {
                swapped_public: true,
                ..Case::default()
            },
            5,
        );
    }
);
vm_test!(well_formed_invalid_proof_rejects, {
    reject(
        Case {
            corrupt_proof: true,
            ..Case::default()
        },
        5,
    );
});
vm_test!(well_formed_substituted_vk_fails_identity, {
    reject(
        Case {
            wrong_key: true,
            ..Case::default()
        },
        12,
    );
});
vm_test!(rebound_different_vk_rejects_old_proof, {
    reject(
        Case {
            rebind_wrong_key: true,
            ..Case::default()
        },
        5,
    );
});
vm_test!(same_proof_accepts_at_two_distinct_input_outpoints, {
    for input_id in [41, 42] {
        run(Case {
            input_id,
            ..Case::default()
        })
        .unwrap();
    }
});
vm_test!(same_proof_accepts_changed_capacity, {
    for capacity in [499, 501] {
        run(Case {
            capacity: Some(capacity),
            ..Case::default()
        })
        .unwrap();
    }
});
vm_test!(same_proof_accepts_unrelated_output, {
    run(Case {
        unrelated_output: true,
        ..Case::default()
    })
    .unwrap();
});
vm_test!(group_witness_at_nonzero_absolute_input_accepts, {
    run(Case {
        prefix_input: true,
        ..Case::default()
    })
    .unwrap();
});
vm_test!(proof_at_wrong_absolute_witness_rejects, {
    reject(
        Case {
            misplaced_witness: true,
            ..Case::default()
        },
        16,
    );
});
vm_test!(missing_input_type_rejects, {
    reject(
        Case {
            missing_input_type: true,
            ..Case::default()
        },
        16,
    );
});
vm_test!(duplicate_verifier_lock_input_rejects, {
    reject(
        Case {
            duplicate_lock_input: true,
            ..Case::default()
        },
        33,
    );
});
vm_test!(duplicate_verifier_lock_output_rejects, {
    reject(
        Case {
            duplicate_lock_output: true,
            ..Case::default()
        },
        33,
    );
});
vm_test!(duplicate_capsule_output_rejects, {
    reject(
        Case {
            duplicate_type_output: true,
            ..Case::default()
        },
        23,
    );
});
vm_test!(capsule_creation_is_unsupported, {
    reject(
        Case {
            creation: true,
            ..Case::default()
        },
        24,
    );
});
vm_test!(capsule_destruction_is_unsupported, {
    reject(
        Case {
            destruction: true,
            ..Case::default()
        },
        24,
    );
});
vm_test!(type_alone_does_not_authenticate_verifier_lock, {
    // Diagnostic acceptance documents the composition gap; not a desired security guarantee.
    run(Case {
        nonverifier_lock: true,
        corrupt_proof: true,
        ..Case::default()
    })
    .unwrap();
});
vm_test!(type_action_comparison_rejects_without_verifier, {
    // Isolates the Type's constant action comparison from the earlier pairing failure.
    reject(
        Case {
            nonverifier_lock: true,
            changed_public: Some(4),
            ..Case::default()
        },
        30,
    );
});
