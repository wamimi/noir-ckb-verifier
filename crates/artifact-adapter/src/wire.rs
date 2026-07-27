use std::{
    fs,
    path::{Path, PathBuf},
};

use ark_bn254::{Bn254, Fr};
use ark_groth16::{Proof, VerifyingKey};
use ark_serialize::CanonicalSerialize;
use groth16_schema::{
    Bn254Witness, Byte32, FrVec, G1Compressed, G1Vec, G2Compressed, Groth16VerifyingKey,
    Groth16Witness, ProofBn254, Uint16, VerifyingKeyBn254, VerifyingKeyContent, WitnessContent,
};
use molecule::prelude::{Builder, Entity};
use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::AdapterError;

const WIRE_VERSION: u16 = 1;

#[derive(Clone, Debug)]
pub struct WireArtifacts {
    pub vk_bytes: Vec<u8>,
    pub proof_bytes: Vec<u8>,
    pub public_inputs_bytes: Vec<u8>,
    pub vk_molecule: Vec<u8>,
    pub witness_molecule: Vec<u8>,
    pub vk_data_hash: [u8; 32],
}

#[derive(Debug, Serialize)]
struct OutputFileRecord {
    file: &'static str,
    bytes: usize,
    sha256: String,
}

#[derive(Debug, Serialize)]
struct OutputManifest {
    wire_version: u16,
    curve: &'static str,
    serialization: &'static str,
    public_input_count: usize,
    files: Vec<OutputFileRecord>,
}

fn canonical_bytes<T: CanonicalSerialize>(value: &T, label: &str) -> Result<Vec<u8>, AdapterError> {
    let mut bytes = Vec::with_capacity(value.compressed_size());
    value
        .serialize_compressed(&mut bytes)
        .map_err(|error| AdapterError::Serialization {
            label: label.to_owned(),
            message: error.to_string(),
        })?;
    Ok(bytes)
}

fn fixed_entity<T: Entity>(bytes: &[u8], label: &str) -> Result<T, AdapterError> {
    T::from_slice(bytes).map_err(|error| AdapterError::Molecule {
        label: label.to_owned(),
        message: error.to_string(),
    })
}

pub fn build_wire_artifacts(
    verifying_key: &VerifyingKey<Bn254>,
    proof: &Proof<Bn254>,
    public_inputs: &[Fr],
) -> Result<WireArtifacts, AdapterError> {
    let vk_bytes = canonical_bytes(verifying_key, "verification key")?;
    let proof_bytes = canonical_bytes(proof, "proof")?;

    let mut public_inputs_bytes = Vec::with_capacity(4 + public_inputs.len() * 32);
    public_inputs_bytes.extend_from_slice(&(public_inputs.len() as u32).to_le_bytes());
    for (index, public_input) in public_inputs.iter().enumerate() {
        public_inputs_bytes.extend_from_slice(&canonical_bytes(
            public_input,
            &format!("public input {index}"),
        )?);
    }

    let alpha = fixed_entity::<G1Compressed>(
        &canonical_bytes(&verifying_key.alpha_g1, "vk.alpha_g1")?,
        "vk.alpha_g1",
    )?;
    let beta = fixed_entity::<G2Compressed>(
        &canonical_bytes(&verifying_key.beta_g2, "vk.beta_g2")?,
        "vk.beta_g2",
    )?;
    let gamma = fixed_entity::<G2Compressed>(
        &canonical_bytes(&verifying_key.gamma_g2, "vk.gamma_g2")?,
        "vk.gamma_g2",
    )?;
    let delta = fixed_entity::<G2Compressed>(
        &canonical_bytes(&verifying_key.delta_g2, "vk.delta_g2")?,
        "vk.delta_g2",
    )?;

    let mut ic_builder = G1Vec::new_builder();
    for (index, point) in verifying_key.gamma_abc_g1.iter().enumerate() {
        let bytes = canonical_bytes(point, &format!("vk.IC[{index}]"))?;
        ic_builder = ic_builder.push(fixed_entity::<G1Compressed>(
            &bytes,
            &format!("vk.IC[{index}]"),
        )?);
    }

    let vk_bn254 = VerifyingKeyBn254::new_builder()
        .alpha_g1(alpha)
        .beta_g2(beta)
        .gamma_g2(gamma)
        .delta_g2(delta)
        .gamma_abc_g1(ic_builder.build())
        .build();
    let version = fixed_entity::<Uint16>(&WIRE_VERSION.to_le_bytes(), "wire version")?;
    let vk_molecule = Groth16VerifyingKey::new_builder()
        .version(version.clone())
        .content(VerifyingKeyContent::from(vk_bn254))
        .build()
        .as_slice()
        .to_vec();

    let proof_bn254 = ProofBn254::new_builder()
        .a(fixed_entity::<G1Compressed>(
            &canonical_bytes(&proof.a, "proof.a")?,
            "proof.a",
        )?)
        .b(fixed_entity::<G2Compressed>(
            &canonical_bytes(&proof.b, "proof.b")?,
            "proof.b",
        )?)
        .c(fixed_entity::<G1Compressed>(
            &canonical_bytes(&proof.c, "proof.c")?,
            "proof.c",
        )?)
        .build();

    let mut public_builder = FrVec::new_builder();
    for (index, public_input) in public_inputs.iter().enumerate() {
        let bytes = canonical_bytes(public_input, &format!("public[{index}]"))?;
        public_builder =
            public_builder.push(fixed_entity::<Byte32>(&bytes, &format!("public[{index}]"))?);
    }
    let witness_bn254 = Bn254Witness::new_builder()
        .proof(proof_bn254)
        .public_inputs(public_builder.build())
        .build();
    let witness_molecule = Groth16Witness::new_builder()
        .version(version)
        .content(WitnessContent::from(witness_bn254))
        .build()
        .as_slice()
        .to_vec();

    let vk_data_hash = ckb_hash::blake2b_256(&vk_molecule);

    Ok(WireArtifacts {
        vk_bytes,
        proof_bytes,
        public_inputs_bytes,
        vk_molecule,
        witness_molecule,
        vk_data_hash,
    })
}

pub fn verify_endpoint_round_trip(artifacts: &WireArtifacts) -> Result<(), AdapterError> {
    let decoded_vk =
        wire_decode::decode_vk_to_arkworks(&artifacts.vk_molecule).map_err(|error| {
            AdapterError::WireDecode {
                label: "verification key".to_owned(),
                message: format!("{error:?}"),
            }
        })?;
    let (decoded_proof, decoded_public) =
        wire_decode::decode_witness_to_arkworks(&artifacts.witness_molecule).map_err(|error| {
            AdapterError::WireDecode {
                label: "witness".to_owned(),
                message: format!("{error:?}"),
            }
        })?;

    for (label, expected, actual) in [
        ("verification key", &artifacts.vk_bytes, &decoded_vk),
        ("proof", &artifacts.proof_bytes, &decoded_proof),
        (
            "public inputs",
            &artifacts.public_inputs_bytes,
            &decoded_public,
        ),
    ] {
        if expected != actual {
            return Err(AdapterError::RoundTripMismatch {
                label: label.to_owned(),
            });
        }
    }

    verifier_core::verify(&decoded_vk, &decoded_proof, &decoded_public)
        .map_err(|error| AdapterError::EndpointVerification(format!("{error:?}")))
}

fn sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

fn write(path: PathBuf, bytes: &[u8]) -> Result<(), AdapterError> {
    fs::write(&path, bytes).map_err(|source| AdapterError::Write { path, source })
}

pub fn write_wire_artifacts(
    output: &Path,
    artifacts: &WireArtifacts,
    public_input_count: usize,
) -> Result<(), AdapterError> {
    fs::create_dir_all(output).map_err(|source| AdapterError::CreateOutput {
        path: output.to_path_buf(),
        source,
    })?;

    let files: [(&'static str, &[u8]); 6] = [
        ("vk.bin", &artifacts.vk_bytes),
        ("proof.bin", &artifacts.proof_bytes),
        ("public_inputs.bin", &artifacts.public_inputs_bytes),
        ("vk.mol.bin", &artifacts.vk_molecule),
        ("witness.mol.bin", &artifacts.witness_molecule),
        ("vk_data_hash.bin", &artifacts.vk_data_hash),
    ];

    let mut records = Vec::with_capacity(files.len());
    for (name, bytes) in files {
        write(output.join(name), bytes)?;
        records.push(OutputFileRecord {
            file: name,
            bytes: bytes.len(),
            sha256: sha256(bytes),
        });
    }

    let manifest = OutputManifest {
        wire_version: WIRE_VERSION,
        curve: "BN254",
        serialization: "arkworks-0.5-canonical-compressed-in-groth16-ckb-v1-molecule",
        public_input_count,
        files: records,
    };
    let manifest_bytes =
        serde_json::to_vec_pretty(&manifest).map_err(|error| AdapterError::Serialization {
            label: "output manifest".to_owned(),
            message: error.to_string(),
        })?;
    write(output.join("manifest.json"), &manifest_bytes)
}
