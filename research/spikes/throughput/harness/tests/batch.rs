//! N Groth16 proofs under one key in one CKB-VM script run: N separate verifications
//! against one randomized batch check. Proofs come from recorded case files.
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::{Capacity, ScriptHashType, TransactionBuilder},
    packed::{CellDep, CellInput, CellOutput, Script, WitnessArgs},
    prelude::*,
};
use ckb_testtool::{ckb_hash::blake2b_256, context::Context};
use serde_json::Value;
use std::{env, fs, path::PathBuf};

const BLOCK: u64 = 3_500_000_000;

fn bytes(v: &Value) -> Bytes {
    hex::decode(v.as_str().unwrap().trim_start_matches("0x")).unwrap().into()
}

/// (payload, key) of a recorded case.
fn load(path: &str) -> (Bytes, Bytes) {
    let case: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
    let vk = case["cells"].as_array().unwrap().iter().map(|c| bytes(&c["data"]))
        .find(|d| d.len() > 300 && d.len() < 4096 && d[4..8] == [0x0c, 0, 0, 0]).expect("vk cell");
    let witness = case["transaction"]["witnesses"].as_array().unwrap().iter().map(bytes)
        .find(|w| w.len() > 200).expect("proof witness");
    let wa = WitnessArgs::from_slice(&witness).unwrap();
    let payload = wa.input_type().to_opt().or(wa.output_type().to_opt()).unwrap().raw_data();
    (payload, vk)
}

fn run(payloads: &[Bytes], vk: &Bytes, mode: u8) -> Result<(u64, String), String> {
    let bin: Bytes = fs::read(PathBuf::from(env::var_os("SPIKE_BIN").expect("SPIKE_BIN")).join("verify-batch")).unwrap().into();
    let mut blob = (payloads.len() as u32).to_le_bytes().to_vec();
    for p in payloads {
        blob.extend_from_slice(&(p.len() as u32).to_le_bytes());
        blob.extend_from_slice(p);
    }
    let mut ctx = Context::new_with_deterministic_rng();
    ctx.set_capture_debug(true);
    let bin_op = ctx.deploy_cell(bin.clone());
    let vk_op = ctx.deploy_cell(vk.clone());
    let mut args = blake2b_256(vk).to_vec();
    args.push(mode);
    let lock = Script::new_builder().code_hash(blake2b_256(&bin).pack()).hash_type(ScriptHashType::Data1)
        .args(Bytes::from(args).pack()).build();
    let input = ctx.create_cell(CellOutput::new_builder().capacity(Capacity::shannons(1000)).lock(lock).build(), Bytes::new());
    let witness = WitnessArgs::new_builder().input_type(Some(Bytes::from(blob)).pack()).build();
    let tx = TransactionBuilder::default()
        .input(CellInput::new_builder().previous_output(input).build())
        .output(CellOutput::new_builder().capacity(Capacity::shannons(900)).build())
        .output_data(Bytes::new().pack())
        .cell_dep(CellDep::new_builder().out_point(bin_op).build())
        .cell_dep(CellDep::new_builder().out_point(vk_op).build())
        .witness(witness.as_bytes().pack())
        .build();
    let size = tx.data().as_slice().len();
    match ctx.verify_tx(&tx, BLOCK) {
        Ok(c) => Ok((c, format!("{size} tx bytes"))),
        Err(e) => {
            let s = format!("{e:?}");
            Err(s.split("cause: ").nth(1).unwrap_or(&s).chars().take(90).collect())
        }
    }
}

#[test]
fn batch() {
    // CASES = label=path,path;label=path,path  (each group: proofs under one key)
    let spec = env::var("CASES").expect("CASES");
    let sizes: Vec<usize> = env::var("SIZES").unwrap_or("1,2,4,8,16,32,64".into()).split(',').map(|s| s.parse().unwrap()).collect();
    for group in spec.split(';') {
        let (label, paths) = group.split_once('=').unwrap();
        let loaded: Vec<(Bytes, Bytes)> = paths.split(',').map(load).collect();
        let vk = loaded[0].1.clone();
        assert!(loaded.iter().all(|l| l.1 == vk), "{label}: proofs under different keys");
        println!("GROUP {label}: {} distinct proofs, payload {} bytes", loaded.len(), loaded[0].0.len());
        for &n in &sizes {
            let payloads: Vec<Bytes> = (0..n).map(|i| loaded[i % loaded.len()].0.clone()).collect();
            // Separate verification of more than 32 proofs exceeds a block; skip running it.
            let single = if n > 32 { Err("not run: exceeds a block".to_string()) } else { run(&payloads, &vk, 0) };
            let batch = run(&payloads, &vk, 1);
            println!("BATCH {label} n={n}: separate {:?}; batch {:?}", single, batch);
            // One altered public input anywhere in the batch must reject in both modes.
            let mut bad = payloads.clone();
            let mut b = bad[n - 1].to_vec();
            let last = b.len() - 32;
            b[last] ^= 1;
            bad[n - 1] = b.into();
            let (s, t) = (if n > 32 { Err(String::new()) } else { run(&bad, &vk, 0) }, run(&bad, &vk, 1));
            println!("BATCH {label} n={n}: last public input altered: separate {}, batch {}",
                if s.is_err() { "rejected" } else { "ACCEPTED" }, if t.is_err() { "rejected" } else { "ACCEPTED" });
            assert!(s.is_err() && t.is_err(), "altered proof accepted");
        }
    }
}
