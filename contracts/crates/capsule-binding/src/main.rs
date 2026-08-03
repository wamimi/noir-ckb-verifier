#![cfg_attr(not(any(feature = "library", test)), no_std)]
#![cfg_attr(not(test), no_main)]

#[cfg(any(feature = "library", test))]
extern crate alloc;

#[cfg(not(any(feature = "library", test)))]
ckb_std::entry!(program_entry);
#[cfg(not(any(feature = "library", test)))]
ckb_std::default_alloc!();

use alloc::vec::Vec;

use ckb_std::{
    ckb_constants::Source,
    error::SysError,
    high_level::{load_cell_data, load_cell_lock_hash, load_script, load_witness_args},
};

const VERSION: u8 = 1;
const FIELD_LEN: usize = 32;
const ARGS_LEN: usize = 1 + 2 * FIELD_LEN;
const CELL_DATA_LEN: usize = 1 + 2 * FIELD_LEN;
const PUBLIC_INPUT_COUNT: usize = 7;
const PUBLIC_INPUT_PREFIX_LEN: usize = 4;

const ERROR_SCRIPT_LOAD: i8 = 20;
const ERROR_ARGS_LENGTH: i8 = 21;
const ERROR_ARGS_VERSION: i8 = 22;
const ERROR_GROUP_SHAPE: i8 = 23;
const ERROR_CELL_DATA_LOAD: i8 = 24;
const ERROR_CELL_DATA_ENCODING: i8 = 25;
const ERROR_WITNESS_LOAD: i8 = 26;
const ERROR_WITNESS_INPUT_TYPE_MISSING: i8 = 27;
const ERROR_WITNESS_DECODE: i8 = 28;
const ERROR_PUBLIC_INPUT_SHAPE: i8 = 29;
const ERROR_PUBLIC_INPUT_MISMATCH: i8 = 30;
const ERROR_LOCK_HASH_LOAD: i8 = 31;
const ERROR_LOCK_CHANGED: i8 = 32;
const ERROR_LOCK_GROUP_SHAPE: i8 = 33;

fn load_single_group_cell(source: Source) -> Result<Vec<u8>, i8> {
    let data = load_cell_data(0, source).map_err(|_| ERROR_CELL_DATA_LOAD)?;
    match load_cell_data(1, source) {
        Err(SysError::IndexOutOfBound) => Ok(data),
        Ok(_) => Err(ERROR_GROUP_SHAPE),
        Err(_) => Err(ERROR_CELL_DATA_LOAD),
    }
}

fn validate_cell_data(data: &[u8]) -> Result<(), i8> {
    if data.len() != CELL_DATA_LEN || data[0] != VERSION {
        return Err(ERROR_CELL_DATA_ENCODING);
    }
    Ok(())
}

fn count_lock_hash(target: &[u8; 32], source: Source) -> Result<usize, i8> {
    let mut count = 0usize;
    let mut index = 0usize;
    loop {
        match load_cell_lock_hash(index, source) {
            Ok(candidate) => {
                if candidate == *target {
                    count += 1;
                }
                index += 1;
            }
            Err(SysError::IndexOutOfBound) => return Ok(count),
            Err(_) => return Err(ERROR_LOCK_HASH_LOAD),
        }
    }
}

fn validate_lock_group() -> Result<(), i8> {
    let input_lock =
        load_cell_lock_hash(0, Source::GroupInput).map_err(|_| ERROR_LOCK_HASH_LOAD)?;
    let output_lock =
        load_cell_lock_hash(0, Source::GroupOutput).map_err(|_| ERROR_LOCK_HASH_LOAD)?;
    if input_lock != output_lock {
        return Err(ERROR_LOCK_CHANGED);
    }

    let matching_inputs = count_lock_hash(&input_lock, Source::Input)?;
    let matching_outputs = count_lock_hash(&input_lock, Source::Output)?;
    if matching_inputs != 1 || matching_outputs != 1 {
        return Err(ERROR_LOCK_GROUP_SHAPE);
    }
    Ok(())
}

fn load_public_inputs() -> Result<Vec<u8>, i8> {
    let witness = load_witness_args(0, Source::GroupInput).map_err(|_| ERROR_WITNESS_LOAD)?;
    let input_type = witness
        .input_type()
        .to_opt()
        .ok_or(ERROR_WITNESS_INPUT_TYPE_MISSING)?;
    let (_, public_inputs) =
        wire_decode::decode_witness_to_arkworks(input_type.raw_data().as_ref())
            .map_err(|_| ERROR_WITNESS_DECODE)?;

    let expected_len = PUBLIC_INPUT_PREFIX_LEN + PUBLIC_INPUT_COUNT * FIELD_LEN;
    if public_inputs.len() != expected_len
        || public_inputs[..PUBLIC_INPUT_PREFIX_LEN] != (PUBLIC_INPUT_COUNT as u32).to_le_bytes()
    {
        return Err(ERROR_PUBLIC_INPUT_SHAPE);
    }
    Ok(public_inputs)
}

fn require_public_input(actual: &[u8], index: usize, expected: &[u8]) -> Result<(), i8> {
    let start = PUBLIC_INPUT_PREFIX_LEN + index * FIELD_LEN;
    let end = start + FIELD_LEN;
    if actual.get(start..end) != Some(expected) {
        return Err(ERROR_PUBLIC_INPUT_MISMATCH);
    }
    Ok(())
}

pub fn program_entry() -> i8 {
    let script = match load_script() {
        Ok(script) => script,
        Err(_) => return ERROR_SCRIPT_LOAD,
    };
    let args = script.args().raw_data();
    if args.len() != ARGS_LEN {
        return ERROR_ARGS_LENGTH;
    }
    if args[0] != VERSION {
        return ERROR_ARGS_VERSION;
    }

    let input_data = match load_single_group_cell(Source::GroupInput) {
        Ok(data) => data,
        Err(code) => return code,
    };
    let output_data = match load_single_group_cell(Source::GroupOutput) {
        Ok(data) => data,
        Err(code) => return code,
    };
    if let Err(code) = validate_cell_data(&input_data) {
        return code;
    }
    if let Err(code) = validate_cell_data(&output_data) {
        return code;
    }
    if let Err(code) = validate_lock_group() {
        return code;
    }

    let public_inputs = match load_public_inputs() {
        Ok(public_inputs) => public_inputs,
        Err(code) => return code,
    };
    let mut update_action = [0u8; FIELD_LEN];
    update_action[0] = 1;

    let expected = [
        &args[1..33],
        &input_data[1..33],
        &input_data[33..65],
        &output_data[1..33],
        update_action.as_slice(),
        &output_data[33..65],
        &args[33..65],
    ];
    for (index, value) in expected.into_iter().enumerate() {
        if let Err(code) = require_public_input(&public_inputs, index, value) {
            return code;
        }
    }

    0
}
