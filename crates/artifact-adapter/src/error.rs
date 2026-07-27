use std::path::PathBuf;

use thiserror::Error;

#[derive(Debug, Error)]
pub enum AdapterError {
    #[error("failed to read {path}: {source}")]
    Read {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to parse JSON at {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },

    #[error("unsupported protocol `{0}`; expected `groth16`")]
    UnsupportedProtocol(String),

    #[error("unsupported curve `{0}`; expected snarkjs `bn128`")]
    UnsupportedCurve(String),

    #[error("{label} is not a canonical unsigned decimal integer: `{value}`")]
    InvalidDecimal { label: String, value: String },

    #[error("{label} is outside the canonical {field} field range")]
    FieldOutOfRange { label: String, field: &'static str },

    #[error("{label} has projective marker `{observed}`; expected `{expected}`")]
    ProjectiveMarker {
        label: String,
        observed: String,
        expected: &'static str,
    },

    #[error("{label} is not on the BN254 curve")]
    PointNotOnCurve { label: String },

    #[error("{label} is not in the correct BN254 subgroup")]
    PointWrongSubgroup { label: String },

    #[error("{label} is the point at infinity")]
    PointAtInfinity { label: String },

    #[error(
        "public input count mismatch: verification key declares {declared}, supplied {supplied}, IC entries {ic_entries}"
    )]
    PublicInputCount {
        declared: usize,
        supplied: usize,
        ic_entries: usize,
    },

    #[error("arkworks rejected the proof for the supplied public inputs")]
    VerificationFailed,

    #[error("negative public-input fixture unexpectedly verified")]
    NegativeVerificationAccepted,

    #[error("canonical serialization failed for {label}: {message}")]
    Serialization { label: String, message: String },

    #[error("failed to create output directory {path}: {source}")]
    CreateOutput {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to write {path}: {source}")]
    Write {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("Molecule construction failed for {label}: {message}")]
    Molecule { label: String, message: String },

    #[error("pinned groth16-ckb wire decoder rejected {label}: {message}")]
    WireDecode { label: String, message: String },

    #[error("pinned groth16-ckb host verifier rejected the round trip: {0}")]
    EndpointVerification(String),

    #[error("wire round-trip changed {label}")]
    RoundTripMismatch { label: String },
}
