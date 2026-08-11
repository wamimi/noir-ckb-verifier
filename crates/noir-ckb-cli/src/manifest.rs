use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
};

use serde::{de::DeserializeOwned, Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::error::CliError;

pub const MANIFEST_VERSION: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CurrentManifest {
    pub manifest: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildManifest {
    pub version: u32,
    pub profile: String,
    pub project: String,
    pub run_id: String,
    pub repository_revision: String,
    pub repository_dirty: bool,
    pub noir_groth16_revision: String,
    pub groth16_ckb_revision: String,
    pub nargo_version: String,
    pub snarkjs_version: String,
    pub build_dir: PathBuf,
    pub circuit_artifact: PathBuf,
    pub r1cs: PathBuf,
    pub wtns: PathBuf,
    pub witness_json: PathBuf,
    pub expected_public_names: Vec<String>,
    pub binding_action: String,
    pub public_sources: Vec<String>,
    pub expected_public_values: Vec<String>,
    pub expected_private_names: Vec<String>,
    pub public_input_count: usize,
    pub private_input_count: usize,
    pub constraint_count: u64,
    pub wire_count: u64,
    pub hashes: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofManifest {
    pub version: u32,
    pub profile: String,
    pub project: String,
    pub run_id: String,
    pub build_manifest: PathBuf,
    pub proof_dir: PathBuf,
    pub fixture_dir: PathBuf,
    pub adapter_dir: PathBuf,
    pub verification_key: PathBuf,
    pub proof: PathBuf,
    pub public: PathBuf,
    pub public_values: Vec<String>,
    pub negative_public: Vec<PathBuf>,
    pub vk_data_hash: String,
    pub hashes: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestReport {
    pub version: u32,
    pub profile: String,
    pub project: String,
    pub run_id: String,
    pub proof_manifest: PathBuf,
    pub host_tests_passed: bool,
    pub ckb_vm_matrix_passed: bool,
    pub ckb_vm_passed_cases: usize,
    pub accepted_cycles: u64,
    pub report_dir: PathBuf,
    pub hashes: BTreeMap<String, String>,
}

pub fn write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), CliError> {
    let mut encoded =
        serde_json::to_vec_pretty(value).map_err(|source| CliError::SerializeJson {
            path: path.to_path_buf(),
            source,
        })?;
    encoded.push(b'\n');
    fs::write(path, encoded).map_err(|source| CliError::Write {
        path: path.to_path_buf(),
        source,
    })
}

pub fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T, CliError> {
    let bytes = fs::read(path).map_err(|source| CliError::Read {
        path: path.to_path_buf(),
        source,
    })?;
    serde_json::from_slice(&bytes).map_err(|source| CliError::ParseJson {
        path: path.to_path_buf(),
        source,
    })
}

pub fn sha256_file(path: &Path) -> Result<String, CliError> {
    let bytes = fs::read(path).map_err(|source| CliError::Read {
        path: path.to_path_buf(),
        source,
    })?;
    Ok(hex::encode(Sha256::digest(bytes)))
}
