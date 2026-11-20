//! Runs recorded Groth16 payloads through the linked and the spawned verifier in CKB-VM
//! (ckb-testtool) and prints sizes and cycles. Also replays the recorded transactions
//! unchanged, as a calibration of this harness against the repository's own records.
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::{ScriptHashType, TransactionBuilder},
    packed::{CellDep, CellInput, CellOutput, OutPoint},
    prelude::*,
};
use ckb_testtool::{ckb_hash::blake2b_256, ckb_jsonrpc_types as json, context::Context};
use serde_json::Value;
use std::{env, fs, path::PathBuf};

const MAX: u64 = 3_500_000_000;

fn bytes(v: &Value) -> Bytes {
    hex::decode(v.as_str().unwrap().trim_start_matches("0x")).unwrap().into()
}

fn case(name: &str) -> Option<Value> {
    let p = PathBuf::from(env::var_os(name)?);
    Some(serde_json::from_slice(&fs::read(p).unwrap()).unwrap())
}

/// The recorded transaction, exactly as the repository's matrix ran it.
fn replay(case: &Value) -> Option<u64> {
    let mut ctx = Context::new_with_deterministic_rng();
    for c in case["cells"].as_array().unwrap() {
        let op: json::OutPoint = serde_json::from_value(c["out_point"].clone()).unwrap();
        let output: json::CellOutput = serde_json::from_value(c["output"].clone()).unwrap();
        let (op, output): (OutPoint, CellOutput) = (op.into(), output.into());
        ctx.create_cell_with_out_point(op, output, bytes(&c["data"]));
    }
    let t: json::Transaction = serde_json::from_value(case["transaction"].clone()).unwrap();
    let tx: ckb_testtool::ckb_types::packed::Transaction = t.into();
    ctx.verify_tx(&tx.into_view(), MAX).ok()
}

/// Witness and verification key of a recorded case, run under one of the spike scripts.
fn run(case: &Value, split: bool) -> (u64, Vec<String>) {
    let dir = PathBuf::from(env::var_os("SPIKE_BIN").expect("SPIKE_BIN"));
    let linked: Bytes = fs::read(dir.join("verify-linked")).unwrap().into();
    let parent: Bytes = fs::read(dir.join("verify-parent")).unwrap().into();
    let vk = case["cells"].as_array().unwrap().iter().map(|c| bytes(&c["data"]))
        .find(|d| d.len() > 300 && d.len() < 4096 && d[4..8] == [0x0c, 0, 0, 0]).expect("vk cell");
    let witness = case["transaction"]["witnesses"].as_array().unwrap().iter().map(bytes)
        .find(|w| w.len() > 200).expect("proof witness");

    let mut ctx = Context::new_with_deterministic_rng();
    ctx.set_capture_debug(true);
    let linked_op = ctx.deploy_cell(linked.clone());
    let parent_op = ctx.deploy_cell(parent.clone());
    let vk_op = ctx.deploy_cell(vk.clone());
    let mut args = blake2b_256(&vk).to_vec();
    let code = if split {
        args.extend_from_slice(&blake2b_256(&linked));
        &parent
    } else {
        &linked
    };
    let lock = ckb_testtool::ckb_types::packed::Script::new_builder()
        .code_hash(blake2b_256(code).pack())
        .hash_type(ScriptHashType::Data2)
        .args(Bytes::from(args).pack())
        .build();
    let input = ctx.create_cell(
        CellOutput::new_builder().capacity(ckb_testtool::ckb_types::core::Capacity::shannons(1000)).lock(lock).build(),
        Bytes::new(),
    );
    let tx = TransactionBuilder::default()
        .input(CellInput::new_builder().previous_output(input).build())
        .output(CellOutput::new_builder().capacity(ckb_testtool::ckb_types::core::Capacity::shannons(900)).build())
        .output_data(Bytes::new().pack())
        .cell_dep(CellDep::new_builder().out_point(linked_op).build())
        .cell_dep(CellDep::new_builder().out_point(parent_op).build())
        .cell_dep(CellDep::new_builder().out_point(vk_op).build())
        .witness(witness.pack())
        .build();
    let cycles = ctx.verify_tx(&tx, MAX).expect("spike transaction");
    (cycles, ctx.captured_messages().iter().map(|m| m.message.clone()).collect())
}

#[test]
fn placement() {
    let dir = PathBuf::from(env::var_os("SPIKE_BIN").expect("SPIKE_BIN"));
    for name in ["verify-linked", "verify-parent"] {
        println!("size {name}: {} bytes", fs::metadata(dir.join(name)).unwrap().len());
    }
    for var in ["CASE_TALLY_UPDATE", "CASE_TALLY_CREATE", "CASE_COUNTER_UPDATE"] {
        let Some(c) = case(var) else { continue };
        match replay(&c) {
            Some(n) => println!("{var}: recorded transaction replayed: {n} cycles"),
            None => println!("{var}: recorded transaction not replayed (it is stored unsigned)"),
        }
        for split in [false, true] {
            let (cycles, log) = run(&c, split);
            println!("{var}: {}: {cycles} cycles; {}", if split { "spawned" } else { "linked" }, log.join("; "));
        }
    }
    // Optional: every case file in CASES_DIR (written by ../public-inputs/npub.py), linked only.
    if let Some(dir) = env::var_os("CASES_DIR") {
        let mut files: Vec<_> = fs::read_dir(dir).unwrap().map(|e| e.unwrap().path()).collect();
        files.sort();
        for f in files {
            let c: Value = serde_json::from_slice(&fs::read(&f).unwrap()).unwrap();
            let (cycles, _) = run(&c, false);
            println!("CASE {}: linked: {cycles} cycles", f.file_stem().unwrap().to_string_lossy());
        }
    }
}

/// "Any relayer can pay": the recorded tally update, with its recorded proof, in three
/// transactions the prover never saw. Uses the recorded (pinned-build) tally binary.
#[test]
fn relayer_open() {
    let Some(base) = case("CASE_TALLY_UPDATE") else { return };
    let other = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
    // Index of the funding Cell (the input that is not the tally) among the recorded cells.
    let funding = base["transaction"]["inputs"][1]["previous_output"].clone();
    let pos = base["cells"].as_array().unwrap().iter().position(|c| c["out_point"] == funding).unwrap();

    // 1. Another payer: a different funding Cell under a different Lock, different change.
    let mut c = base.clone();
    c["cells"][pos]["out_point"]["tx_hash"] = other.into();
    c["cells"][pos]["output"]["lock"]["args"] = "0x02".into();
    c["transaction"]["inputs"][1]["previous_output"]["tx_hash"] = other.into();
    c["transaction"]["outputs"][1]["lock"]["args"] = "0x02".into();
    c["transaction"]["outputs"][1]["capacity"] = "0x174860e100".into();
    println!("relayer_open: other payer and change: {:?}", replay(&c).map(|n| format!("accepted, {n} cycles")));
    assert!(replay(&c).is_some());

    // 2. The original payer plus a second, unrelated input and output.
    let mut c = base.clone();
    let mut extra = base["cells"][pos].clone();
    extra["out_point"]["tx_hash"] = other.into();
    c["cells"].as_array_mut().unwrap().push(extra.clone());
    let mut input = base["transaction"]["inputs"][1].clone();
    input["previous_output"]["tx_hash"] = other.into();
    c["transaction"]["inputs"].as_array_mut().unwrap().push(input);
    c["transaction"]["witnesses"].as_array_mut().unwrap().push("0x".into());
    c["transaction"]["outputs"].as_array_mut().unwrap().push(extra["output"].clone());
    c["transaction"]["outputs_data"].as_array_mut().unwrap().push("0x".into());
    println!("relayer_open: extra input and output: {:?}", replay(&c).map(|n| format!("accepted, {n} cycles")));
    assert!(replay(&c).is_some());

    // 3. Control: the same proof with the tally's successor capacity raised by the payer.
    let mut c = base.clone();
    c["transaction"]["outputs"][0]["capacity"] = "0x4a817c801".into();
    println!("relayer_open: successor capacity changed (control): {}", if replay(&c).is_none() { "rejected" } else { "ACCEPTED" });
    assert!(replay(&c).is_none());
}
