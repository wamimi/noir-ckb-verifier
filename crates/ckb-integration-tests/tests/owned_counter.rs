//! Fresh counter cases only; no Capsule fixture substitution.
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::TransactionView,
    packed::{CellOutput, OutPoint, WitnessArgs},
    prelude::*,
    H256,
};
use ckb_testtool::{
    ckb_crypto::secp::Privkey,
    ckb_hash::{blake2b_256, new_blake2b},
    ckb_jsonrpc_types as json,
    context::Context,
};
use serde_json::Value;
use std::{env, fs, path::PathBuf};
fn bytes(v: &Value) -> Bytes {
    hex::decode(v.as_str().unwrap().trim_start_matches("0x"))
        .unwrap()
        .into()
}
fn sign(tx: TransactionView, ctx: &Context, key: &Privkey, mode: &str) -> TransactionView {
    if mode == "missing" {
        return tx;
    }
    let args = blake2b_256(key.pubkey().unwrap().serialize());
    let group: Vec<usize> = tx
        .inputs()
        .into_iter()
        .enumerate()
        .filter_map(|(i, input)| {
            let cell = &ctx.cells[&input.previous_output()].0;
            if cell.lock().args().raw_data().as_ref() == &args[..20] {
                Some(i)
            } else {
                None
            }
        })
        .collect();
    if group.is_empty() {
        return tx;
    }
    let first = group[0];
    let mut witnesses: Vec<Bytes> = tx.witnesses().into_iter().map(|b| b.raw_data()).collect();
    witnesses.resize_with(tx.inputs().len(), Bytes::new);
    let existing = if witnesses[first].is_empty() {
        WitnessArgs::default()
    } else {
        WitnessArgs::from_slice(&witnesses[first]).unwrap()
    };
    let placeholder = existing
        .clone()
        .as_builder()
        .lock(Some(Bytes::from(vec![0; 65])).pack())
        .build();
    let mut hash = new_blake2b();
    hash.update(tx.hash().as_slice());
    hash.update(&(placeholder.as_slice().len() as u64).to_le_bytes());
    hash.update(placeholder.as_slice());
    for &i in group.iter().skip(1) {
        hash.update(&(witnesses[i].len() as u64).to_le_bytes());
        hash.update(&witnesses[i]);
    }
    for w in witnesses.iter().skip(tx.inputs().len()) {
        hash.update(&(w.len() as u64).to_le_bytes());
        hash.update(w);
    }
    let mut digest = [0; 32];
    hash.finalize(&mut digest);
    if mode == "wrong" {
        digest[0] ^= 1;
    }
    let sig = key
        .sign_recoverable(&H256::from(digest))
        .unwrap()
        .serialize();
    witnesses[first] = existing
        .as_builder()
        .lock(Some(Bytes::from(sig)).pack())
        .build()
        .as_bytes();
    tx.as_advanced_builder()
        .set_witnesses(witnesses.into_iter().map(|w| w.pack()).collect())
        .build()
}
#[test]
#[ignore = "requires fresh counter case directory and isolated development key"]
fn owned_counter_matrix() {
    let dir = PathBuf::from(env::var_os("COUNTER_CASES").expect("COUNTER_CASES"));
    let key_path = PathBuf::from(env::var_os("COUNTER_TEST_KEY").expect("COUNTER_TEST_KEY"));
    assert!(
        key_path.canonicalize().unwrap().starts_with(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../target")
                .canonicalize()
                .unwrap()
        ),
        "only isolated ignored development key allowed"
    );
    let key =
        Privkey::from_slice(&hex::decode(fs::read_to_string(key_path).unwrap().trim()).unwrap());
    let list: Vec<String> =
        serde_json::from_slice(&fs::read(dir.join("cases.json")).unwrap()).unwrap();
    let mut results = Vec::new();
    for name in list {
        let case: Value = serde_json::from_slice(&fs::read(dir.join(&name)).unwrap()).unwrap();
        let mut ctx = Context::new_with_deterministic_rng();
        for c in case["cells"].as_array().unwrap() {
            let op: json::OutPoint = serde_json::from_value(c["out_point"].clone()).unwrap();
            let output: json::CellOutput = serde_json::from_value(c["output"].clone()).unwrap();
            let op: OutPoint = op.into();
            let output: CellOutput = output.into();
            ctx.create_cell_with_out_point(op, output, bytes(&c["data"]));
        }
        let t: json::Transaction = serde_json::from_value(case["transaction"].clone()).unwrap();
        let tx: ckb_testtool::ckb_types::packed::Transaction = t.into();
        let tx = sign(
            tx.into_view(),
            &ctx,
            &key,
            case["sign"].as_str().unwrap_or("valid"),
        );
        let result = ctx.verify_tx(&tx, 300_000_000);
        let expected = case["error"].as_i64();
        let matched = match (&result, expected) {
            (Ok(_), None) => true,
            (Err(e), Some(n)) => {
                e.to_string().contains(&format!("error code {n}"))
                    || e.to_string().contains(&format!("code {n}"))
            }
            _ => false,
        };
        println!("{name}: {result:?}");
        results
            .push(serde_json::json!({"case":name,"passed":matched,"result":format!("{result:?}")}));
        fs::write(
            dir.join("results.json"),
            serde_json::to_vec_pretty(&results).unwrap(),
        )
        .unwrap();
        assert!(
            matched,
            "case {name}: expected {expected:?}, got {result:?}"
        );
    }
}
