//! Spike script: verifies the Groth16 payload in WitnessArgs.input_type (or output_type) of the first group
//! input against the verification key Cell whose data hash is args[0..32].
//! Used two ways: as a Lock with the verifier linked in, and as the child that
//! `verify-parent` spawns (a spawned program sees the same script and transaction).
//! Prints cycle counts at three points so the cost can be split.
#![no_std]
#![no_main]
ckb_std::entry!(program_entry);
ckb_std::default_alloc!();
use alloc::format;
use ckb_std::{
    ckb_constants::Source,
    error::SysError,
    high_level::*,
    syscalls::{current_cycles, debug},
};

fn run() -> Result<(), i8> {
    let args = load_script().map_err(|_| 40)?.args().raw_data();
    if args.len() < 32 {
        return Err(41);
    }
    // The recorded creation payloads sit in output_type; accept either field.
    let wa = load_witness_args(0, Source::GroupInput).map_err(|_| 48)?;
    let payload = wa.input_type().to_opt().or(wa.output_type().to_opt()).ok_or(48)?.raw_data();
    let (proof, public) = wire_decode::decode_witness_to_arkworks(&payload).map_err(|_| 48)?;
    let mut vk_data = None;
    for i in 0.. {
        match load_cell_data_hash(i, Source::CellDep) {
            Ok(h) if h[..] == args[..32] => vk_data = Some(load_cell_data(i, Source::CellDep).map_err(|_| 50)?),
            Ok(_) => (),
            Err(SysError::IndexOutOfBound) => break,
            Err(_) => return Err(40),
        }
    }
    let vk = wire_decode::decode_vk_to_arkworks(&vk_data.ok_or(50)?).map_err(|_| 50)?;
    debug(format!("cycles before verify: {}", current_cycles()));
    verifier_core::verify(&vk, &proof, &public).map_err(|_| 51)?;
    debug(format!("cycles after verify: {}", current_cycles()));
    Ok(())
}

pub fn program_entry() -> i8 {
    match run() {
        Ok(()) => 0,
        Err(e) => e,
    }
}
