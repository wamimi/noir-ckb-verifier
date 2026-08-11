use std::{
    env, fs,
    path::{Path, PathBuf},
};

use serde::Deserialize;

use crate::error::CliError;

pub const CONFIG_VERSION: u32 = 1;
pub const DEVELOPMENT_PROFILE: &str = "development-only";

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub version: u32,
    pub profile: String,
    pub name: String,
    pub output_dir: PathBuf,
    pub circuit: CircuitConfig,
    pub repositories: RepositoryConfig,
    pub tools: ToolConfig,
    pub binding: BindingConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CircuitConfig {
    pub package_dir: PathBuf,
    pub artifact: PathBuf,
    pub inputs: PathBuf,
    pub expected_noir_version: String,
    pub expected_public_names: Vec<String>,
    pub expected_public_values: Vec<String>,
    pub expected_private_names: Vec<String>,
    pub expected_private_values: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RepositoryConfig {
    pub noir_groth16: PathBuf,
    pub noir_groth16_revision: String,
    pub groth16_ckb: PathBuf,
    pub groth16_ckb_revision: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ToolConfig {
    pub nargo_version: String,
    pub snarkjs_version: String,
    pub host_rust_toolchain: String,
    pub contract_rust_toolchain: String,
    pub ckb_target: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BindingConfig {
    pub action: String,
    pub public_sources: Vec<String>,
    pub negative_public: Vec<PathBuf>,
}

#[derive(Debug, Clone)]
pub struct LoadedConfig {
    pub config: Config,
    pub path: PathBuf,
    pub root: PathBuf,
}

impl LoadedConfig {
    pub fn load(path: &Path) -> Result<Self, CliError> {
        let path = absolutize(path)?;
        let text = fs::read_to_string(&path).map_err(|source| CliError::Read {
            path: path.clone(),
            source,
        })?;
        let config: Config = toml::from_str(&text).map_err(|source| CliError::ParseConfig {
            path: path.clone(),
            source,
        })?;
        let root = path
            .parent()
            .ok_or_else(|| CliError::Config("configuration path has no parent".into()))?
            .to_path_buf();
        let loaded = Self { config, path, root };
        loaded.validate()?;
        Ok(loaded)
    }

    pub fn circuit_dir(&self) -> PathBuf {
        self.resolve(&self.config.circuit.package_dir)
    }

    pub fn circuit_artifact(&self) -> PathBuf {
        self.circuit_dir().join(&self.config.circuit.artifact)
    }

    pub fn circuit_inputs(&self) -> PathBuf {
        self.circuit_dir().join(&self.config.circuit.inputs)
    }

    pub fn output_dir(&self) -> PathBuf {
        self.resolve(&self.config.output_dir)
    }

    pub fn noir_groth16_repo(&self) -> PathBuf {
        env::var_os("NOIR_GROTH16_REPO")
            .map(PathBuf::from)
            .unwrap_or_else(|| self.resolve(&self.config.repositories.noir_groth16))
    }

    pub fn groth16_ckb_repo(&self) -> PathBuf {
        env::var_os("GROTH16_CKB_REPO")
            .map(PathBuf::from)
            .unwrap_or_else(|| self.resolve(&self.config.repositories.groth16_ckb))
    }

    pub fn negative_public_paths(&self) -> Vec<PathBuf> {
        self.config
            .binding
            .negative_public
            .iter()
            .map(|path| self.resolve(path))
            .collect()
    }

    pub fn resolve(&self, path: &Path) -> PathBuf {
        if path.is_absolute() {
            path.to_path_buf()
        } else {
            self.root.join(path)
        }
    }

    fn validate(&self) -> Result<(), CliError> {
        let config = &self.config;
        if config.version != CONFIG_VERSION {
            return Err(CliError::Config(format!(
                "unsupported config version {}; expected {CONFIG_VERSION}",
                config.version
            )));
        }
        if config.profile != DEVELOPMENT_PROFILE {
            return Err(CliError::Config(format!(
                "unsupported profile `{}`; Week 11 accepts only `{DEVELOPMENT_PROFILE}`",
                config.profile
            )));
        }
        if config.name.trim().is_empty() {
            return Err(CliError::Config("project name cannot be empty".into()));
        }
        if config.circuit.expected_public_names.is_empty() {
            return Err(CliError::Config(
                "at least one expected public input is required".into(),
            ));
        }
        if config.circuit.expected_public_names.len() != config.circuit.expected_public_values.len()
        {
            return Err(CliError::Config(
                "public input names and development values have different lengths".into(),
            ));
        }
        if config.circuit.expected_private_names.len()
            != config.circuit.expected_private_values.len()
        {
            return Err(CliError::Config(
                "private input names and development values have different lengths".into(),
            ));
        }
        if config.binding.action.trim().is_empty() {
            return Err(CliError::Config("binding action cannot be empty".into()));
        }
        if config.binding.public_sources.len() != config.circuit.expected_public_names.len() {
            return Err(CliError::Config(
                "binding sources and public input names have different lengths".into(),
            ));
        }
        if config
            .binding
            .public_sources
            .iter()
            .any(|source| source.trim().is_empty())
        {
            return Err(CliError::Config(
                "binding sources cannot contain empty entries".into(),
            ));
        }
        if config.binding.negative_public.is_empty() {
            return Err(CliError::Config(
                "at least one negative public vector is required".into(),
            ));
        }
        Ok(())
    }
}

fn absolutize(path: &Path) -> Result<PathBuf, CliError> {
    if path.is_absolute() {
        Ok(path.to_path_buf())
    } else {
        let cwd = env::current_dir().map_err(|source| CliError::Read {
            path: PathBuf::from("."),
            source,
        })?;
        Ok(cwd.join(path))
    }
}
