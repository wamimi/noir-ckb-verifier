//! Spike script: cycle cost in CKB-VM of the accumulator operations a shielded pool or a
//! ballot box would run in a script. args[0] selects the operation; the input is
//! WitnessArgs.input_type of the first group input. Each mode prints the cycle counter
//! before and after the measured part.
//!
//!   0  K chained Poseidon2 permutations                     input: u32 K
//!   1  append K leaves to a Poseidon2 Merkle tree of depth D, keeping only the frontier,
//!      recomputing the root after each                       input: u32 D, u32 K
//!   3  the same K appends with the root computed once at the end   input: u32 D, u32 K
//!   2  BLAKE2b sparse Merkle tree (256 levels): prove K keys absent under a root, then
//!      compute the root with them present                   input: root(32), u32 K, keys, compiled proof
//!   9  Poseidon2 test vector of Noir's solver (all-zero state)
#![no_std]
#![no_main]
ckb_std::entry!(program_entry);
ckb_std::default_alloc!();
mod poseidon2;
use alloc::{format, vec::Vec};
use ark_bn254::Fr;
use ark_ff::{BigInteger, PrimeField, Zero};
use ckb_std::{
    ckb_constants::Source,
    high_level::*,
    syscalls::{current_cycles, debug},
};
use sparse_merkle_tree::{traits::Hasher, CompiledMerkleProof, H256};

struct Blake2b(ckb_hash::Blake2b);
impl Default for Blake2b {
    fn default() -> Self {
        Blake2b(ckb_hash::new_blake2b())
    }
}
impl Hasher for Blake2b {
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

fn u32_at(b: &[u8], at: usize) -> Result<usize, i8> {
    Ok(u32::from_le_bytes(b.get(at..at + 4).ok_or(48)?.try_into().map_err(|_| 48)?) as usize)
}

fn mark(what: &str) {
    debug(format!("{what}: {}", current_cycles()));
}

fn run() -> Result<(), i8> {
    let mode = *load_script().map_err(|_| 40)?.args().raw_data().first().ok_or(41)?;
    let wa = load_witness_args(0, Source::GroupInput).map_err(|_| 48)?;
    let input = wa.input_type().to_opt().ok_or(48)?.raw_data();
    match mode {
        0 => {
            let k = u32_at(&input, 0)?;
            let mut s = [Fr::from(1u64), Fr::from(2u64), Fr::from(3u64), Fr::from(4u64)];
            mark("start");
            for _ in 0..k {
                poseidon2::permute(&mut s);
            }
            mark("end");
        }
        1 => {
            let (depth, k) = (u32_at(&input, 0)?, u32_at(&input, 4)?);
            // Empty-subtree hashes, then an append-only tree that stores one node per level.
            let mut zeros = Vec::with_capacity(depth + 1);
            zeros.push(Fr::zero());
            for i in 0..depth {
                zeros.push(poseidon2::hash2(zeros[i], zeros[i]));
            }
            let mut frontier = zeros[..depth].to_vec();
            mark("start");
            let mut root = zeros[depth];
            for index in 0..k {
                let mut node = Fr::from(index as u64 + 7);
                for level in 0..depth {
                    if (index >> level) & 1 == 0 {
                        frontier[level] = node;
                        node = poseidon2::hash2(node, zeros[level]);
                    } else {
                        node = poseidon2::hash2(frontier[level], node);
                    }
                }
                root = node;
            }
            mark("end");
            debug(format!("root: {:02x?}", &root.into_bigint().to_bytes_be()[..4]));
        }
        3 => {
            // As mode 1, but the root is computed once after all K leaves: a node is hashed
            // only when both children exist, then one pass up the frontier.
            let (depth, k) = (u32_at(&input, 0)?, u32_at(&input, 4)?);
            let mut zeros = Vec::with_capacity(depth + 1);
            zeros.push(Fr::zero());
            for i in 0..depth {
                zeros.push(poseidon2::hash2(zeros[i], zeros[i]));
            }
            let mut frontier = zeros[..depth].to_vec();
            mark("start");
            for index in 0..k {
                let mut node = Fr::from(index as u64 + 7);
                let mut level = 0;
                while (index >> level) & 1 == 1 {
                    node = poseidon2::hash2(frontier[level], node);
                    level += 1;
                }
                frontier[level] = node;
            }
            // Root of a tree holding k leaves, from the frontier.
            let mut node = zeros[0];
            for level in 0..depth {
                node = if (k >> level) & 1 == 1 { poseidon2::hash2(frontier[level], node) } else { poseidon2::hash2(node, zeros[level]) };
            }
            mark("end");
            debug(format!("root: {:02x?}", &node.into_bigint().to_bytes_be()[..4]));
        }
        2 => {
            let root: [u8; 32] = input.get(..32).ok_or(48)?.try_into().map_err(|_| 48)?;
            let k = u32_at(&input, 32)?;
            let keys = input.get(36..36 + 32 * k).ok_or(48)?;
            let proof = CompiledMerkleProof(input[36 + 32 * k..].to_vec());
            let mut one = [0u8; 32];
            one[0] = 1;
            let leaves = |v: [u8; 32]| -> Vec<(H256, H256)> {
                keys.chunks(32).map(|c| (H256::from(<[u8; 32]>::try_from(c).unwrap_or([0; 32])), H256::from(v))).collect()
            };
            mark("start");
            let absent = proof.clone().verify::<Blake2b>(&root.into(), leaves([0u8; 32])).map_err(|_| 58)?;
            if !absent {
                return Err(58);
            }
            let new_root = proof.compute_root::<Blake2b>(leaves(one)).map_err(|_| 58)?;
            mark("end");
            debug(format!("new root: {:02x?}", &new_root.as_slice()[..4]));
        }
        9 => {
            let mut s = [Fr::zero(); 4];
            poseidon2::permute(&mut s);
            let want: [&[u8]; 2] = [
                &[0x18, 0xDF, 0xB8, 0xDC, 0x9B, 0x82, 0x22, 0x9C],
                &[0x09, 0x5C, 0x23, 0x0D, 0x1D, 0x37, 0xA2, 0x46],
            ];
            for i in 0..2 {
                if s[i].into_bigint().to_bytes_be()[..8] != *want[i] {
                    return Err(70);
                }
            }
        }
        _ => return Err(41),
    }
    Ok(())
}

pub fn program_entry() -> i8 {
    match run() {
        Ok(()) => 0,
        Err(e) => e,
    }
}
