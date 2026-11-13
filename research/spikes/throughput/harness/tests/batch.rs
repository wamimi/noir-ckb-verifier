//! N Groth16 proofs under one key in one CKB-VM script run: N separate verifications
//! against one randomized batch check. Proofs come from recorded case files.
//!
//! Every run is classified: accepted, rejected by the script with a given exit code, cycle
//! limit exceeded, or any other failure. A valid batch must be accepted (or exceed the
//! cycle limit, which is reported as such). An altered batch counts as rejected only when
//! the script ran to its own exit code and that code is the expected one; a run that was
//! skipped, ran out of cycles or failed in the loader is counted separately and proves
//! nothing about verification.
//!
//! The fixture is one script run on a Cell of 1,000 shannons: it measures the verifier,
//! not a transaction a node would relay (capacity rules are not checked by ckb-testtool).
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

#[derive(Debug, Clone, PartialEq)]
enum Outcome {
    Accepted(u64),
    Exit(i8),
    CycleLimit,
    Other(String),
}
use Outcome::*;

fn blob_of(payloads: &[Bytes]) -> Vec<u8> {
    let mut blob = (payloads.len() as u32).to_le_bytes().to_vec();
    for p in payloads {
        blob.extend_from_slice(&(p.len() as u32).to_le_bytes());
        blob.extend_from_slice(p);
    }
    blob
}

fn run(payloads: &[Bytes], vk: &Bytes, mode: u8) -> Outcome {
    run_blob(blob_of(payloads), vk, mode)
}

fn run_blob(blob: Vec<u8>, vk: &Bytes, mode: u8) -> Outcome {
    let bin: Bytes = fs::read(PathBuf::from(env::var_os("SPIKE_BIN").expect("SPIKE_BIN")).join("verify-batch")).unwrap().into();
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
    match ctx.verify_tx(&tx, BLOCK) {
        Ok(c) => Accepted(c),
        Err(e) => {
            let s = format!("{e:?}");
            if s.contains("ExceededMaximumCycles") {
                CycleLimit
            } else if let Some(code) = s.split("error code ").nth(1).and_then(|t| {
                t.chars().take_while(|c| c.is_ascii_digit() || *c == '-').collect::<String>().parse::<i8>().ok()
            }) {
                Exit(code)
            } else {
                Other(s.chars().take(160).collect())
            }
        }
    }
}

fn groups() -> Vec<(String, Vec<Bytes>, Bytes)> {
    // CASES = label=path,path;label=path,path  (each group: proofs under one key)
    env::var("CASES").expect("CASES").split(';').map(|group| {
        let (label, paths) = group.split_once('=').unwrap();
        let loaded: Vec<(Bytes, Bytes)> = paths.split(',').map(load).collect();
        let vk = loaded[0].1.clone();
        assert!(loaded.iter().all(|l| l.1 == vk), "{label}: proofs under different keys");
        (label.to_string(), loaded.into_iter().map(|l| l.0).collect(), vk)
    }).collect()
}

fn altered_last_public(payloads: &[Bytes], at: usize) -> Vec<Bytes> {
    let mut bad = payloads.to_vec();
    let mut b = bad[at].to_vec();
    let last = b.len() - 32;
    b[last] ^= 1;
    bad[at] = b.into();
    bad
}

/// Cycle sweep. Run with `--exact batch`.
#[test]
fn batch() {
    let sizes: Vec<usize> = env::var("SIZES").unwrap_or("1,2,4,8,16,32,64".into()).split(',').map(|s| s.parse().unwrap()).collect();
    for (label, proofs, vk) in groups() {
        println!("GROUP {label}: {} distinct proofs, payload {} bytes", proofs.len(), proofs[0].len());
        // rejections shown with exit code 51 / runs that exceeded the cycle limit / runs not made
        let (mut shown, mut exhausted, mut skipped) = (0, 0, 0);
        for &n in &sizes {
            let payloads: Vec<Bytes> = (0..n).map(|i| proofs[i % proofs.len()].clone()).collect();
            let bad = altered_last_public(&payloads, n - 1);
            for (name, mode) in [("separate", 0u8), ("batch", 1u8)] {
                // 31 separate verifications already exceed a block; they are not run above 32.
                if mode == 0 && n > 32 {
                    skipped += 1;
                    println!("BATCH {label} n={n} {name}: not run");
                    continue;
                }
                let valid = run(&payloads, &vk, mode);
                assert!(matches!(valid, Accepted(_) | CycleLimit), "{label} n={n} {name}: valid batch gave {valid:?}");
                let altered = run(&bad, &vk, mode);
                let verdict = match (&valid, &altered) {
                    (Accepted(_), Exit(51)) => { shown += 1; "rejected with 51" }
                    (CycleLimit, CycleLimit) | (CycleLimit, Exit(51)) => { exhausted += 1; "not shown: the valid batch exceeds the cycle limit" }
                    _ => panic!("{label} n={n} {name}: valid {valid:?}, altered {altered:?}"),
                };
                println!("BATCH {label} n={n} {name}: valid {valid:?}; last public input altered: {altered:?} ({verdict})");
            }
        }
        println!("SUMMARY {label}: {shown} rejections shown after an accepted control, {exhausted} not shown (cycle limit), {skipped} not run");
    }
}

// Byte offsets inside the Molecule encodings (schemas/groth16.mol at the pinned commit).
const W_INNER: usize = 18; // Groth16Witness: 12 header, 2 version, 4 union tag
const W_A: usize = 30; // then the 12-byte Bn254Witness header
const W_B: usize = 62;
const W_C: usize = 126;
const W_COUNT: usize = 158;
const K_INNER: usize = 18;
const K_ALPHA: usize = 42; // after the 24-byte VerifyingKeyBn254 header
const K_BETA: usize = 74;
const K_GAMMA: usize = 138;
const K_DELTA: usize = 202;
const K_COUNT: usize = 266;
const K_IC: usize = 270;

/// arkworks compressed identity: zero bytes with the infinity flag in the last byte.
fn identity(bytes: &Bytes, at: usize, len: usize) -> Bytes {
    let mut b = bytes.to_vec();
    b[at..at + len].fill(0);
    b[at + len - 1] = 0x40;
    b.into()
}

fn put_u32(b: &mut [u8], at: usize, v: usize) {
    b[at..at + 4].copy_from_slice(&(v as u32).to_le_bytes());
}

/// The same encoding with the last `drop` 32-byte items removed from its trailing vector.
fn shorten(bytes: &Bytes, inner: usize, count_at: usize, drop: usize) -> Bytes {
    let mut b = bytes.to_vec();
    let have = u32::from_le_bytes(b[count_at..count_at + 4].try_into().unwrap()) as usize;
    b.truncate(b.len() - 32 * drop);
    let len = b.len();
    put_u32(&mut b, 0, len);
    put_u32(&mut b, inner, len - inner);
    put_u32(&mut b, count_at, have - drop);
    b.into()
}

/// Adversarial inputs at small N. Each case names the exit code both modes must return.
/// Run with `--exact adversarial`.
#[test]
fn adversarial() {
    let (label, proofs, vk) = groups().remove(0);
    assert!(proofs.len() >= 2, "needs two distinct proofs");
    let n = 4;
    let valid: Vec<Bytes> = (0..n).map(|i| proofs[i % 2].clone()).collect();
    let publics = u32::from_le_bytes(valid[0][W_COUNT..W_COUNT + 4].try_into().unwrap()) as usize;
    let ic = u32::from_le_bytes(vk[K_COUNT..K_COUNT + 4].try_into().unwrap()) as usize;
    assert_eq!(ic, publics + 1);
    let mut cases: Vec<(String, Vec<u8>, Bytes, Option<i8>)> = Vec::new(); // name, blob, key, exit code (None: accepted)
    let mut case = |name: String, payloads: &[Bytes], key: &Bytes, want: Option<i8>| cases.push((name, blob_of(payloads), key.clone(), want));

    case("valid".into(), &valid, &vk, None);
    case("valid, order reversed".into(), &valid.iter().rev().cloned().collect::<Vec<_>>(), &vk, None);
    case("valid, one proof four times (replay is an application rule, not a verification rule)".into(), &vec![proofs[0].clone(); n], &vk, None);
    for at in 0..n {
        case(format!("public input altered at index {at}"), &altered_last_public(&valid, at), &vk, Some(51));
        let mut bad = valid.clone();
        let mut b = bad[at].to_vec();
        b[W_C] ^= 1;
        bad[at] = b.into();
        case(format!("proof point C altered at index {at}"), &bad, &vk, Some(51));
    }
    case("public inputs altered at indices 0 and 3".into(), &altered_last_public(&altered_last_public(&valid, 0), 3), &vk, Some(51));
    for (point, at, len) in [("A", W_A, 32), ("B", W_B, 64), ("C", W_C, 32)] {
        let mut bad = valid.clone();
        bad[1] = identity(&bad[1], at, len);
        case(format!("identity proof point {point} at index 1"), &bad, &vk, Some(51));
    }
    let mut bad = valid.clone();
    let mut b = bad[2].to_vec();
    let last = b.len() - 32;
    b[last..].fill(0xff);
    bad[2] = b.into();
    case("public input not below the field modulus at index 2".into(), &bad, &vk, Some(51));
    let mut bad = valid.clone();
    bad[0] = shorten(&bad[0], W_INNER, W_COUNT, 1);
    case("one public input too few at index 0".into(), &bad, &vk, Some(51));
    if let Ok(path) = env::var("OTHER_KEY_CASE") {
        let other = load(&path).1;
        if other.len() == vk.len() && other != vk {
            case("valid proofs under another circuit's key of the same arity".into(), &valid, &other, Some(51));
        }
    }
    for (point, at, len) in [("alpha", K_ALPHA, 32), ("beta", K_BETA, 64), ("gamma", K_GAMMA, 64), ("delta", K_DELTA, 64),
        ("IC[0]", K_IC, 32), ("IC[last]", K_IC + 32 * (ic - 1), 32)] {
        case(format!("key with identity {point}"), &valid, &identity(&vk, at, len), Some(50));
    }
    case("key with no IC entry".into(), &valid, &shorten(&vk, K_INNER, K_COUNT, ic), Some(50));
    drop(case);

    // Framing: the blob is edited after it is built.
    let good = blob_of(&valid);
    let mut framing = |name: &str, edit: &dyn Fn(&mut Vec<u8>)| {
        let mut b = good.clone();
        edit(&mut b);
        cases.push((name.to_string(), b, vk.clone(), Some(48)));
    };
    framing("count 0 with no items", &|b| { b.truncate(4); put_u32(b, 0, 0) });
    framing("count 0 with four items present", &|b| put_u32(b, 0, 0));
    framing("count one more than the items present", &|b| put_u32(b, 0, 5));
    framing("count one fewer than the items present", &|b| put_u32(b, 0, 3));
    framing("count 257 (above the maximum)", &|b| put_u32(b, 0, 257));
    framing("count 0xffffffff", &|b| b[..4].fill(0xff));
    framing("one byte after the last item", &|b| b.push(0));
    framing("last item truncated by one byte", &|b| { b.pop(); });
    framing("first item length 0xffffffff", &|b| b[4..8].fill(0xff));
    framing("one byte appended inside the first item", &|b| {
        let len = u32::from_le_bytes(b[4..8].try_into().unwrap()) as usize;
        b.insert(8 + len, 0);
        put_u32(b, 4, len + 1);
    });
    drop(framing);

    let mut failed = 0;
    for (name, blob, key, want) in &cases {
        let got = [run_blob(blob.clone(), key, 0), run_blob(blob.clone(), key, 1)];
        let ok = got.iter().all(|g| match want { None => matches!(g, Accepted(_)), Some(code) => *g == Exit(*code) });
        failed += !ok as usize;
        println!("ADVERSARIAL {label} n={n}: {name}: separate {:?}, batch {:?}: {}", got[0], got[1],
            if ok { "as expected" } else { "UNEXPECTED" });
    }
    // The batch check runs its Miller loops in chunks of 8 pairs (N + 3 pairs in total):
    // sizes on both sides of a chunk boundary, batch mode only.
    for n in [5usize, 6, 13, 14] {
        let valid: Vec<Bytes> = (0..n).map(|i| proofs[i % 2].clone()).collect();
        let got = [run(&valid, &vk, 1), run(&altered_last_public(&valid, 0), &vk, 1), run(&altered_last_public(&valid, n - 1), &vk, 1)];
        let ok = matches!(got[0], Accepted(_)) && got[1] == Exit(51) && got[2] == Exit(51);
        failed += !ok as usize;
        println!("ADVERSARIAL {label} n={n} (chunk boundary), batch: valid {:?}, index 0 altered {:?}, last altered {:?}: {}",
            got[0], got[1], got[2], if ok { "as expected" } else { "UNEXPECTED" });
    }
    println!("SUMMARY adversarial: {} of {} cases as expected", cases.len() + 4 - failed, cases.len() + 4);
    assert_eq!(failed, 0);
}
