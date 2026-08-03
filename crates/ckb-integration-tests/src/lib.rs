//! CKB-VM integration-test support.

use std::path::{Path, PathBuf};

/// Resolves a Groth16 fixture from an optional external directory.
///
/// `NOIR_CKB_FIXTURE_DIR` lets the reproduction workflow exercise freshly
/// generated artifacts without replacing the committed regression fixture.
pub fn fixture_path(name: &str) -> PathBuf {
    std::env::var_os("NOIR_CKB_FIXTURE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/fixtures/week-10-capsule")
        })
        .join(name)
}
