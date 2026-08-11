mod config;
mod error;
mod manifest;
mod process;
mod workflow;

use std::path::PathBuf;

use clap::{Parser, Subcommand};

use crate::{config::LoadedConfig, error::CliError};

#[derive(Debug, Parser)]
#[command(name = "noir-ckb", version)]
#[command(about = "Build, prove, and test the pinned Noir-to-CKB developer-preview path")]
struct Cli {
    /// Path to the versioned Noir-to-CKB project configuration.
    #[arg(long, default_value = "noir-ckb.toml", global = true)]
    config: PathBuf,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Compile the circuit, lower it to R1CS, enforce public-wire semantics,
    /// and build the pinned CKB scripts.
    Build,
    /// Generate and validate a development-only Groth16 proof, then emit CKB
    /// wire artifacts.
    Prove,
    /// Run host validation and the proof-bound Capsule CKB-VM matrix against
    /// the latest generated proof.
    Test,
}

fn run(cli: Cli) -> Result<(), CliError> {
    let loaded = LoadedConfig::load(&cli.config)?;
    match cli.command {
        Command::Build => workflow::build(&loaded),
        Command::Prove => workflow::prove(&loaded),
        Command::Test => workflow::test(&loaded),
    }
}

fn main() {
    if let Err(error) = run(Cli::parse()) {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
