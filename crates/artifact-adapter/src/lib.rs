mod convert;
mod error;
pub mod json;
mod wire;

use std::path::Path;

pub use convert::{convert, convert_public_inputs, verify, ConvertedArtifacts};
pub use error::AdapterError;
pub use wire::{
    build_wire_artifacts, verify_endpoint_round_trip, write_wire_artifacts, WireArtifacts,
};

use json::{read_json, SnarkJsProof, SnarkJsVerifyingKey};

pub fn load_and_convert(
    vk_path: &Path,
    proof_path: &Path,
    public_path: &Path,
) -> Result<ConvertedArtifacts, AdapterError> {
    let vk: SnarkJsVerifyingKey = read_json(vk_path)?;
    let proof: SnarkJsProof = read_json(proof_path)?;
    let public_values: Vec<String> = read_json(public_path)?;
    convert(&vk, &proof, &public_values)
}

pub fn load_public_inputs(path: &Path) -> Result<Vec<ark_bn254::Fr>, AdapterError> {
    let values: Vec<String> = read_json(path)?;
    convert_public_inputs(&values)
}
