use std::path::PathBuf;

use artifact_adapter::{
    build_wire_artifacts, load_and_convert, load_public_inputs, verify, verify_endpoint_round_trip,
    write_wire_artifacts, AdapterError,
};
use clap::Parser;

#[derive(Debug, Parser)]
#[command(name = "noir-ckb-adapter")]
#[command(about = "Convert validated snarkjs BN254 Groth16 JSON into groth16-ckb wire artifacts")]
struct Args {
    #[arg(long)]
    vk: PathBuf,
    #[arg(long)]
    proof: PathBuf,
    #[arg(long)]
    public: PathBuf,
    #[arg(long)]
    negative_public: Option<PathBuf>,
    #[arg(long)]
    out: PathBuf,
}

fn run(args: Args) -> Result<(), AdapterError> {
    let converted = load_and_convert(&args.vk, &args.proof, &args.public)?;
    let accepted = verify(
        &converted.verifying_key,
        &converted.public_inputs,
        &converted.proof,
    )?;
    if !accepted {
        return Err(AdapterError::VerificationFailed);
    }
    println!("arkworks_positive_verify=accepted");

    if let Some(path) = &args.negative_public {
        let negative = load_public_inputs(path)?;
        let accepted = verify(&converted.verifying_key, &negative, &converted.proof)?;
        if accepted {
            return Err(AdapterError::NegativeVerificationAccepted);
        }
        println!("arkworks_negative_verify=rejected");
    }

    let wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )?;
    verify_endpoint_round_trip(&wire)?;
    println!("groth16_ckb_wire_roundtrip=accepted");

    write_wire_artifacts(&args.out, &wire, converted.public_inputs.len())?;
    println!("public_input_count={}", converted.public_inputs.len());
    println!("vk_bytes={}", wire.vk_bytes.len());
    println!("proof_bytes={}", wire.proof_bytes.len());
    println!("public_inputs_bytes={}", wire.public_inputs_bytes.len());
    println!("vk_molecule_bytes={}", wire.vk_molecule.len());
    println!("witness_molecule_bytes={}", wire.witness_molecule.len());
    println!("vk_data_hash={}", hex::encode(wire.vk_data_hash));
    println!("output_directory={}", args.out.display());
    Ok(())
}

fn main() {
    if let Err(error) = run(Args::parse()) {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
