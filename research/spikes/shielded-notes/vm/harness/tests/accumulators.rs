//! Cycle cost in CKB-VM of script-side accumulator operations (see the script's header).
use ckb_testtool::ckb_types::{
    bytes::Bytes,
    core::{Capacity, ScriptHashType, TransactionBuilder},
    packed::{CellDep, CellInput, CellOutput, Script, WitnessArgs},
    prelude::*,
};
use ckb_testtool::{ckb_hash::{blake2b_256, new_blake2b, Blake2b}, context::Context};
use sparse_merkle_tree::{default_store::DefaultStore, traits::Hasher, SparseMerkleTree, H256};
use std::{env, fs, path::PathBuf};

struct CkbBlake2b(Blake2b);
impl Default for CkbBlake2b {
    fn default() -> Self {
        CkbBlake2b(new_blake2b())
    }
}
impl Hasher for CkbBlake2b {
    fn write_h256(&mut self, h: &H256) {
        self.0.update(h.as_slice());
    }
    fn write_byte(&mut self, b: u8) {
        self.0.update(&[b]);
    }
    fn finish(self) -> H256 {
        let mut out = [0u8; 32];
        self.0.finalize(&mut out);
        out.into()
    }
}

/// Runs the script; returns (cycles of the measured part, whole script cycles, binary bytes).
fn run(mode: u8, input: Vec<u8>) -> Result<(u64, u64, usize, String), String> {
    let bin: Bytes = fs::read(PathBuf::from(env::var_os("SPIKE_BIN").expect("SPIKE_BIN")).join("acc-bench")).unwrap().into();
    let mut ctx = Context::new_with_deterministic_rng();
    ctx.set_capture_debug(true);
    let op = ctx.deploy_cell(bin.clone());
    let lock = Script::new_builder().code_hash(blake2b_256(&bin).pack()).hash_type(ScriptHashType::Data1)
        .args(Bytes::from(vec![mode]).pack()).build();
    let input_cell = ctx.create_cell(CellOutput::new_builder().capacity(Capacity::shannons(1000)).lock(lock).build(), Bytes::new());
    let witness = WitnessArgs::new_builder().input_type(Some(Bytes::from(input)).pack()).build();
    let tx = TransactionBuilder::default()
        .input(CellInput::new_builder().previous_output(input_cell).build())
        .output(CellOutput::new_builder().capacity(Capacity::shannons(900)).build())
        .output_data(Bytes::new().pack())
        .cell_dep(CellDep::new_builder().out_point(op).build())
        .witness(witness.as_bytes().pack())
        .build();
    let total = ctx.verify_tx(&tx, 3_500_000_000).map_err(|e| format!("{e:?}").chars().take(160).collect::<String>())?;
    let at = |key: &str| -> u64 {
        ctx.captured_messages().iter().find_map(|m| m.message.strip_prefix(key).map(|v| v.trim().parse().unwrap())).unwrap_or(0)
    };
    let root = ctx.captured_messages().iter().find_map(|m| m.message.split("root: ").nth(1).map(str::to_string)).unwrap_or_default();
    Ok((at("end:") - at("start:"), total, bin.len(), root))
}

fn le(n: usize) -> [u8; 4] {
    (n as u32).to_le_bytes()
}

#[test]
fn accumulators() {
    let (_, total, size, _) = run(9, vec![]).expect("Poseidon2 test vector");
    println!("ACC script: {size} bytes; Poseidon2 test vector of Noir's solver: matched ({total} cycles)");

    for k in [1usize, 10, 100] {
        let (c, _, _, _) = run(0, le(k).to_vec()).unwrap();
        println!("ACC poseidon2 permutations k={k}: {c} cycles ({} each)", c / k as u64);
    }
    for depth in [16usize, 20, 32] {
        for k in [1usize, 2, 8, 64] {
            let (c, _, _, root) = run(1, [le(depth), le(k)].concat()).unwrap();
            let (c3, _, _, root3) = run(3, [le(depth), le(k)].concat()).unwrap();
            assert_eq!(root, root3, "the two append methods disagree on the root");
            println!("ACC poseidon2 tree append depth={depth} k={k}: root after each leaf {c} cycles ({} per leaf); root once {c3} cycles ({} per leaf)", c / k as u64, c3 / k as u64);
        }
    }

    // Sparse Merkle tree with `size` existing keys; prove k fresh keys absent, then insert them.
    let key = |tag: &str, i: usize| -> H256 { blake2b_256(format!("{tag} {i}").as_bytes()).into() };
    let mut one = [0u8; 32];
    one[0] = 1;
    for size in [0usize, 1_000, 10_000] {
        let mut tree = SparseMerkleTree::<CkbBlake2b, H256, DefaultStore<H256>>::default();
        for i in 0..size {
            tree.update(key("existing", i), one.into()).unwrap();
        }
        for k in [1usize, 2, 8, 32] {
            let keys: Vec<H256> = (0..k).map(|i| key("fresh", i)).collect();
            let proof = tree.merkle_proof(keys.clone()).unwrap().compile(keys.clone()).unwrap();
            let mut input = tree.root().as_slice().to_vec();
            input.extend_from_slice(&le(k));
            keys.iter().for_each(|x| input.extend_from_slice(x.as_slice()));
            input.extend_from_slice(&proof.0);
            let (c, _, _, root) = run(2, input).unwrap();
            // The root the script computed must be the root of the tree after the insertions.
            let mut after = SparseMerkleTree::<CkbBlake2b, H256, DefaultStore<H256>>::new(*tree.root(), tree.store().clone());
            keys.iter().for_each(|x| { after.update(*x, one.into()).unwrap(); });
            assert_eq!(root, format!("{:02x?}", &after.root().as_slice()[..4]), "script and host disagree on the new root");
            println!("ACC blake2b SMT absent+insert tree={size} k={k}: {c} cycles ({} per key), proof {} bytes ({} per key)",
                c / k as u64, proof.0.len(), proof.0.len() / k);
        }
        // Negative: a key that is present must not pass as absent.
        if size > 0 {
            let keys = vec![key("existing", 0)];
            let proof = tree.merkle_proof(keys.clone()).unwrap().compile(keys.clone()).unwrap();
            let mut input = tree.root().as_slice().to_vec();
            input.extend_from_slice(&le(1));
            input.extend_from_slice(keys[0].as_slice());
            input.extend_from_slice(&proof.0);
            println!("ACC blake2b SMT tree={size}: present key claimed absent: {}", if run(2, input).is_err() { "rejected" } else { "ACCEPTED" });
        }
    }
}
