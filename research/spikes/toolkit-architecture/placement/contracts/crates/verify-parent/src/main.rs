//! Spike script: the thin half of a split design. It reads and decodes the payload (as a
//! binding script must, to compare the public vector), then spawns the verifier whose
//! code hash is args[32..64] and returns its exit code. No pairing code is linked here.
#![no_std]
#![no_main]
ckb_std::entry!(program_entry);
ckb_std::default_alloc!();
use alloc::format;
use ckb_std::{
    ckb_constants::Source,
    ckb_types::core::ScriptHashType,
    high_level::*,
    syscalls::{current_cycles, debug, wait},
};

fn run() -> Result<(), i8> {
    let args = load_script().map_err(|_| 40)?.args().raw_data();
    if args.len() != 64 {
        return Err(41);
    }
    // The recorded creation payloads sit in output_type; accept either field.
    let wa = load_witness_args(0, Source::GroupInput).map_err(|_| 48)?;
    let payload = wa.input_type().to_opt().or(wa.output_type().to_opt()).ok_or(48)?.raw_data();
    wire_decode::decode_witness_to_arkworks(&payload).map_err(|_| 48)?;
    debug(format!("parent cycles before spawn: {}", current_cycles()));
    let pid = spawn_cell(&args[32..], ScriptHashType::Data2, &[], &[]).map_err(|_| 60)?;
    let code = wait(pid).map_err(|_| 61)?;
    debug(format!("parent cycles after wait: {}", current_cycles()));
    if code != 0 {
        return Err(code);
    }
    Ok(())
}

pub fn program_entry() -> i8 {
    match run() {
        Ok(()) => 0,
        Err(e) => e,
    }
}
