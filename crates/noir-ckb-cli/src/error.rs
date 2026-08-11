use std::{path::PathBuf, process::ExitStatus};

use thiserror::Error;

#[derive(Debug, Error)]
pub enum CliError {
    #[error("failed to read {path}: {source}")]
    Read {
        path: PathBuf,
        source: std::io::Error,
    },

    #[error("failed to write {path}: {source}")]
    Write {
        path: PathBuf,
        source: std::io::Error,
    },

    #[error("failed to create directory {path}: {source}")]
    CreateDirectory {
        path: PathBuf,
        source: std::io::Error,
    },

    #[error("failed to copy {source_path} to {destination}: {source}")]
    Copy {
        source_path: PathBuf,
        destination: PathBuf,
        source: std::io::Error,
    },

    #[error("failed to parse TOML configuration {path}: {source}")]
    ParseConfig {
        path: PathBuf,
        source: toml::de::Error,
    },

    #[error("failed to parse JSON {path}: {source}")]
    ParseJson {
        path: PathBuf,
        source: serde_json::Error,
    },

    #[error("failed to serialize JSON for {path}: {source}")]
    SerializeJson {
        path: PathBuf,
        source: serde_json::Error,
    },

    #[error("invalid configuration: {0}")]
    Config(String),

    #[error("compatibility check failed: {0}")]
    Compatibility(String),

    #[error("required path does not exist: {0}")]
    MissingPath(PathBuf),

    #[error("failed to start command `{command}`: {source}")]
    CommandStart {
        command: String,
        source: std::io::Error,
    },

    #[error("command `{command}` failed with {status}")]
    CommandFailed { command: String, status: ExitStatus },

    #[error("command `{command}` unexpectedly succeeded; rejection was required")]
    ExpectedFailureAccepted { command: String },

    #[error("command `{command}` emitted non-UTF-8 output")]
    NonUtf8Output { command: String },

    #[error("system clock is before the Unix epoch")]
    Clock,

    #[error(transparent)]
    Adapter(#[from] artifact_adapter::AdapterError),
}
