//! Private tally v2 Type Script matrix. Cases are generated with fresh proofs by
//! scripts/check-private-tally.py; no signatures are involved (guard Lock).
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    packed::{CellOutput, OutPoint},
    prelude::*,
};
use ckb_testtool::{ckb_jsonrpc_types as json, context::Context};
use serde_json::Value;
use std::{env, fs, path::PathBuf};

fn bytes(v: &Value) -> Bytes {
    hex::decode(v.as_str().unwrap().trim_start_matches("0x"))
        .unwrap()
        .into()
}

#[test]
#[ignore = "requires a case directory from scripts/check-private-tally.py"]
fn private_tally_matrix() {
    let dir = PathBuf::from(env::var_os("TALLY_CASES").expect("TALLY_CASES"));
    let list: Vec<String> =
        serde_json::from_slice(&fs::read(dir.join("cases.json")).unwrap()).unwrap();
    let mut results = Vec::new();
    let mut failures = Vec::new();
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
        let result = ctx.verify_tx(&tx.into_view(), 300_000_000);
        let expected = case["error"].as_i64();
        let matched = match (&result, expected) {
            (Ok(_), None) => true,
            (Err(e), Some(n)) => {
                e.to_string().contains(&format!("error code {n}"))
                    || e.to_string().contains(&format!("code {n}"))
            }
            _ => false,
        };
        println!(
            "{} {name}: {result:?}",
            if matched { "PASS" } else { "FAIL" }
        );
        if !matched {
            failures.push(name.clone());
        }
        results.push(serde_json::json!({
            "case": name,
            "expected_error": expected,
            "passed": matched,
            "result": format!("{result:?}"),
        }));
        fs::write(
            dir.join("results.json"),
            serde_json::to_vec_pretty(&results).unwrap(),
        )
        .unwrap();
    }
    assert!(failures.is_empty(), "failed cases: {failures:?}");
}
