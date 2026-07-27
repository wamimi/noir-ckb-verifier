use std::{fs, path::Path};

use serde::de::DeserializeOwned;
use serde::Deserialize;

use crate::AdapterError;

pub type G1Json = [String; 3];
pub type G2Json = [[String; 2]; 3];

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SnarkJsProof {
    pub pi_a: G1Json,
    pub pi_b: G2Json,
    pub pi_c: G1Json,
    pub protocol: String,
    pub curve: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SnarkJsVerifyingKey {
    pub protocol: String,
    pub curve: String,
    #[serde(rename = "nPublic")]
    pub n_public: usize,
    pub vk_alpha_1: G1Json,
    pub vk_beta_2: G2Json,
    pub vk_gamma_2: G2Json,
    pub vk_delta_2: G2Json,
    // snarkjs exports this precomputed value, but arkworks derives the
    // equivalent pairing preparation from the core VK points.
    pub vk_alphabeta_12: serde_json::Value,
    #[serde(rename = "IC")]
    pub ic: Vec<G1Json>,
}

pub fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T, AdapterError> {
    let bytes = fs::read(path).map_err(|source| AdapterError::Read {
        path: path.to_path_buf(),
        source,
    })?;
    serde_json::from_slice(&bytes).map_err(|source| AdapterError::Json {
        path: path.to_path_buf(),
        source,
    })
}
