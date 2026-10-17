//! noir-ckb/private-tally/v2 Type Script (docs/private-tally-v2-spec.md, sections 4-6).
//!
//! The proof is the authority: the Cell is held by an always-success guard Lock,
//! so every rule lives here. Cheap structural checks run first; the Groth16
//! verification runs last, against a public vector rebuilt from this transaction.
#![no_std]
#![no_main]
ckb_std::entry!(program_entry);
ckb_std::default_alloc!();
use ckb_std::{
    ckb_constants::{CellField, Source},
    ckb_types::{
        packed::{Script, WitnessArgs},
        prelude::*,
    },
    error::SysError,
    high_level::*,
    syscalls,
};
include!(concat!(env!("OUT_DIR"), "/policy.rs"));

// Stable application errors; verification is deliberately last.
const LOAD: i8 = 40;
const ARGS: i8 = 41;
const SHAPE: i8 = 42;
const STATE: i8 = 43;
const ID: i8 = 44;
const GUARD: i8 = 45;
const CAPACITY: i8 = 47;
const WITNESS: i8 = 48;
const PUBLIC: i8 = 49;
const VK: i8 = 50;
const PROOF: i8 = 51;
const LIMIT: i8 = 52;
const COMMITMENT: i8 = 54;
const MAX: usize = 64;
const DATA1: u8 = 2;
const VERSION: u8 = 1;
// BN254 scalar field modulus, little-endian.
const MODULUS_LE: [u8; 32] = [
    0x01, 0x00, 0x00, 0xf0, 0x93, 0xf5, 0xe1, 0x43, 0x91, 0x70, 0xb9, 0x79, 0x48, 0xe8, 0x33, 0x28,
    0x5d, 0x58, 0x81, 0x81, 0xb6, 0x45, 0x50, 0xb8, 0x29, 0xa0, 0x31, 0xe1, 0x72, 0x4e, 0x64, 0x30,
];

/// Tally data: 0x01 || commitment (32 bytes, little-endian, canonical, non-zero).
fn commitment(source: Source) -> Result<[u8; 32], i8> {
    let mut b = [0u8; 34];
    let n = syscalls::load_cell_data(&mut b, 0, 0, source).map_err(|_| STATE)?;
    if n != 33 || b[0] != VERSION {
        return Err(STATE);
    }
    let mut c = [0u8; 32];
    c.copy_from_slice(&b[1..33]);
    // MUTATION-BEGIN: canonical
    if c == [0; 32] || !less_than_modulus(&c) {
        return Err(COMMITMENT);
    }
    // MUTATION-END: canonical
    Ok(c)
}

fn less_than_modulus(le: &[u8; 32]) -> bool {
    for i in (0..32).rev() {
        if le[i] != MODULUS_LE[i] {
            return le[i] < MODULUS_LE[i];
        }
    }
    false
}

fn count(source: Source) -> Result<usize, i8> {
    for i in 0..=MAX {
        match load_cell_capacity(i, source) {
            Ok(_) if i == MAX => return Err(LIMIT),
            Ok(_) => (),
            Err(SysError::IndexOutOfBound) => return Ok(i),
            Err(_) => return Err(LOAD),
        }
    }
    Err(LIMIT)
}

/// Cells whose Type uses this code, whatever their args (no batching of tallies).
fn application_cells(source: Source, n: usize, script: &Script) -> Result<usize, i8> {
    let mut found = 0;
    for i in 0..n {
        let mut b = [0u8; 49];
        match syscalls::load_cell_by_field(&mut b, 0, i, source, CellField::Type) {
            Ok(_) | Err(SysError::LengthNotEnough(_)) => {
                if b[16..48] == script.code_hash().as_slice()[..]
                    && b[48] == script.hash_type().as_slice()[0]
                {
                    found += 1;
                }
            }
            Err(SysError::ItemMissing) => (),
            Err(_) => return Err(LOAD),
        }
    }
    Ok(found)
}

/// The Lock must be the pinned always-success guard: code by data hash, data1, empty args.
fn guard(source: Source) -> Result<(), i8> {
    let lock = load_cell_lock(0, source).map_err(|_| LOAD)?;
    // MUTATION-BEGIN: guard
    if lock.code_hash().as_slice() != GUARD_DATA_HASH
        || lock.hash_type().as_slice() != [DATA1]
        || !lock.args().raw_data().is_empty()
    {
        return Err(GUARD);
    }
    // MUTATION-END: guard
    Ok(())
}

fn proof_payload(source: Source, input_side: bool) -> Result<ckb_std::ckb_types::bytes::Bytes, i8> {
    // Whole WitnessArgs bounded before parsing.
    let mut buf = [0u8; 512];
    let len = syscalls::load_witness(&mut buf, 0, 0, source).map_err(|_| WITNESS)?;
    let wa = WitnessArgs::from_slice(&buf[..len]).map_err(|_| WITNESS)?;
    let field = if input_side {
        wa.input_type()
    } else {
        wa.output_type()
    };
    Ok(field.to_opt().ok_or(WITNESS)?.raw_data())
}

fn run() -> Result<(), i8> {
    let script = load_script().map_err(|_| LOAD)?;
    let args = script.args().raw_data();
    if args.len() != 33 || args[0] != VERSION || script.hash_type().as_slice() != [DATA1] {
        return Err(ARGS);
    }
    let ni = count(Source::Input)?;
    let no = count(Source::Output)?;
    let nd = count(Source::CellDep)?;
    let ai = application_cells(Source::Input, ni, &script)?;
    let ao = application_cells(Source::Output, no, &script)?;
    if ai > 1 || ao != 1 || count(Source::GroupOutput)? != 1 || count(Source::GroupInput)? != ai {
        return Err(SHAPE);
    }
    ckb_std::type_id::validate_type_id(&args[1..]).map_err(|_| ID)?;
    guard(Source::GroupOutput)?;
    let c_new = commitment(Source::GroupOutput)?;
    let capacity = load_cell_capacity(0, Source::GroupOutput).map_err(|_| LOAD)?;

    let creation = ai == 0;
    let mut outpoint = [0u8; 36];
    let mut c_old = [0u8; 32];
    if !creation {
        guard(Source::GroupInput)?;
        c_old = commitment(Source::GroupInput)?;
        // MUTATION-BEGIN: capacity
        if load_cell_capacity(0, Source::GroupInput).map_err(|_| LOAD)? != capacity {
            return Err(CAPACITY);
        }
        // MUTATION-END: capacity
        outpoint.copy_from_slice(
            load_input_out_point(0, Source::GroupInput)
                .map_err(|_| LOAD)?
                .as_slice(),
        );
    }

    let mut hash = ckb_hash::new_blake2b();
    hash.update(b"noir-ckb/private-tally/context/v2\0");
    hash.update(&NETWORK_DOMAIN);
    hash.update(&ckb_hash::blake2b_256(b"noir-ckb/private-tally/v2"));
    hash.update(&load_script_hash().map_err(|_| LOAD)?);
    hash.update(&args[1..]);
    hash.update(&[if creation { 0 } else { 1 }]);
    hash.update(&outpoint);
    hash.update(&c_old);
    hash.update(&c_new);
    hash.update(&load_cell_lock_hash(0, Source::GroupOutput).map_err(|_| LOAD)?);
    hash.update(&capacity.to_le_bytes());
    let mut digest = [0u8; 32];
    hash.finalize(&mut digest);

    // Public vector as encoded for the verifier: u32 count, then four 32-byte LE fields.
    let mut expected = [0u8; 132];
    expected[..4].copy_from_slice(&4u32.to_le_bytes());
    expected[4..36].copy_from_slice(&c_old);
    expected[36..68].copy_from_slice(&c_new);
    expected[68..84].copy_from_slice(&digest[..16]);
    expected[100..116].copy_from_slice(&digest[16..]);

    // Creation: output_type of the output's witness. Update: input_type of the input's witness.
    let payload = if creation {
        proof_payload(Source::GroupOutput, false)?
    } else {
        proof_payload(Source::GroupInput, true)?
    };
    let (proof, public) = wire_decode::decode_witness_to_arkworks(&payload).map_err(|_| WITNESS)?;
    if public.as_slice() != expected {
        return Err(PUBLIC);
    }
    let mut vk_index = None;
    for i in 0..nd {
        if load_cell_data_hash(i, Source::CellDep).map_err(|_| LOAD)? == VK_DATA_HASH
            && vk_index.replace(i).is_some()
        {
            return Err(VK);
        }
    }
    let mut vk_buf = [0u8; 512];
    let n = syscalls::load_cell_data(&mut vk_buf, 0, vk_index.ok_or(VK)?, Source::CellDep)
        .map_err(|_| VK)?;
    let vk = wire_decode::decode_vk_to_arkworks(&vk_buf[..n]).map_err(|_| VK)?;
    // MUTATION-BEGIN: verification
    verifier_core::verify(&vk, &proof, &expected).map_err(|_| PROOF)?;
    // MUTATION-END: verification
    Ok(())
}

pub fn program_entry() -> i8 {
    match run() {
        Ok(()) => 0,
        Err(e) => e,
    }
}
