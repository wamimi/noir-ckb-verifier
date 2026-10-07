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
const OWNER: i8 = 45;
const OWNER_CHANGED: i8 = 46;
const CAPACITY: i8 = 47;
const WITNESS: i8 = 48;
const PUBLIC: i8 = 49;
const VK: i8 = 50;
const PROOF: i8 = 51;
const LIMIT: i8 = 52;
const INIT: i8 = 53;
const MAX: usize = 64;
fn data(source: Source) -> Result<[u8; 9], i8> {
    let mut b = [0; 9];
    let n = syscalls::load_cell_data(&mut b, 0, 0, source).map_err(|_| STATE)?;
    if n != 9 || b[0] != 1 {
        return Err(STATE);
    }
    Ok(b)
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
fn application_cells(source: Source, n: usize, script: &Script) -> Result<usize, i8> {
    let mut found = 0;
    for i in 0..n {
        // Read only the fixed Script header, avoiding allocations for unrelated args.
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
fn owner_admission(lock: &Script, deps: usize) -> Result<(), i8> {
    if lock.code_hash().as_slice() != OWNER_CODE_HASH
        || lock.hash_type().as_slice() != [1]
        || lock.args().raw_data().len() != 20
    {
        return Err(OWNER);
    }
    let mut matches = 0;
    for i in 0..deps {
        if load_cell_type_hash(i, Source::CellDep).map_err(|_| LOAD)? == Some(OWNER_CODE_HASH) {
            matches += 1;
            if load_cell_data_hash(i, Source::CellDep).map_err(|_| LOAD)? != OWNER_DATA_HASH {
                return Err(OWNER);
            }
        }
    }
    if matches != 1 {
        return Err(OWNER);
    }
    Ok(())
}
fn run() -> Result<(), i8> {
    let script = load_script().map_err(|_| LOAD)?;
    let args = script.args().raw_data();
    if args.len() != 33 || args[0] != 1 || script.hash_type().as_slice() != [2] {
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
    let new = data(Source::GroupOutput)?;
    let successor = load_cell_lock(0, Source::GroupOutput).map_err(|_| LOAD)?;
    owner_admission(&successor, nd)?;
    if ai == 0 {
        // MUTATION-BEGIN: initial_zero
        if new[1..] != [0; 8] {
            return Err(INIT);
        }
        // MUTATION-END: initial_zero
        if load_cell_lock_hash(0, Source::Input).map_err(|_| LOAD)?
            != load_cell_lock_hash(0, Source::GroupOutput).map_err(|_| LOAD)?
        {
            return Err(OWNER_CHANGED);
        }
        return Ok(());
    }
    let old = data(Source::GroupInput)?;
    if load_cell_lock_hash(0, Source::GroupInput).map_err(|_| LOAD)?
        != load_cell_lock_hash(0, Source::GroupOutput).map_err(|_| LOAD)?
    {
        return Err(OWNER_CHANGED);
    }
    let capacity = load_cell_capacity(0, Source::GroupOutput).map_err(|_| LOAD)?;
    // MUTATION-BEGIN: capacity
    if load_cell_capacity(0, Source::GroupInput).map_err(|_| LOAD)? != capacity {
        return Err(CAPACITY);
    }
    // MUTATION-END: capacity
    let mut hash = ckb_hash::new_blake2b();
    hash.update(b"noir-ckb/owned-counter/context/v1\0");
    hash.update(&NETWORK_DOMAIN);
    hash.update(&ckb_hash::blake2b_256(b"noir-ckb/owned-counter/v1"));
    hash.update(&load_script_hash().map_err(|_| LOAD)?);
    hash.update(&args[1..]);
    hash.update(&[1]);
    hash.update(
        load_input_out_point(0, Source::GroupInput)
            .map_err(|_| LOAD)?
            .as_slice(),
    );
    hash.update(&old);
    hash.update(&new);
    hash.update(&load_cell_lock_hash(0, Source::GroupOutput).map_err(|_| LOAD)?);
    hash.update(&capacity.to_le_bytes());
    let mut digest = [0; 32];
    hash.finalize(&mut digest);
    let mut expected = [0u8; 132];
    expected[..4].copy_from_slice(&4u32.to_le_bytes());
    expected[4..12].copy_from_slice(&old[1..]);
    expected[36..44].copy_from_slice(&new[1..]);
    expected[68..84].copy_from_slice(&digest[..16]);
    expected[100..116].copy_from_slice(&digest[16..]);
    // Whole WitnessArgs bounded before allocation, including optional lock signature.
    let mut buf = [0u8; 512];
    let len = syscalls::load_witness(&mut buf, 0, 0, Source::GroupInput).map_err(|_| WITNESS)?;
    let wa = WitnessArgs::from_slice(&buf[..len]).map_err(|_| WITNESS)?;
    let payload = wa.input_type().to_opt().ok_or(WITNESS)?;
    let (proof, public) =
        wire_decode::decode_witness_to_arkworks(&payload.raw_data()).map_err(|_| WITNESS)?;
    if public.as_slice() != expected {
        return Err(PUBLIC);
    }
    let mut vk_index = None;
    for i in 0..nd {
        if load_cell_data_hash(i, Source::CellDep).map_err(|_| LOAD)? == VK_DATA_HASH {
            if vk_index.replace(i).is_some() {
                return Err(VK);
            }
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
