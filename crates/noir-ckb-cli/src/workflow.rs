use std::{
    collections::BTreeMap,
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

use artifact_adapter::{
    build_wire_artifacts, load_and_convert, load_public_inputs, verify, verify_endpoint_round_trip,
    write_wire_artifacts,
};
use serde::Deserialize;

use crate::{
    config::{LoadedConfig, DEVELOPMENT_PROFILE},
    error::CliError,
    manifest::{
        read_json, sha256_file, write_json, BuildManifest, CurrentManifest, ProofManifest,
        TestReport, MANIFEST_VERSION,
    },
    process::{require_path, CommandSpec},
};

const CURRENT_BUILD: &str = "current-build.json";
const CURRENT_PROOF: &str = "current-proof.json";
const CURRENT_TEST: &str = "current-test.json";

#[derive(Debug, Deserialize)]
struct NoirArtifact {
    noir_version: String,
    abi: NoirAbi,
}

#[derive(Debug, Deserialize)]
struct NoirAbi {
    parameters: Vec<NoirParameter>,
    return_type: serde_json::Value,
}

#[derive(Debug, Deserialize)]
struct NoirParameter {
    name: String,
    visibility: String,
    #[serde(rename = "type")]
    parameter_type: NoirParameterType,
}

#[derive(Debug, Deserialize)]
struct NoirParameterType {
    kind: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct R1csDescription {
    n_vars: u64,
    n_outputs: u64,
    n_pub_inputs: usize,
    n_prv_inputs: usize,
    n_constraints: u64,
}

pub fn build(loaded: &LoadedConfig) -> Result<(), CliError> {
    println!("profile={DEVELOPMENT_PROFILE}");
    println!("warning=generated setup material is not suitable for production");
    validate_required_inputs(loaded)?;

    let root_revision = git_revision(&loaded.root)?;
    let root_dirty = repository_has_tracked_changes(&loaded.root)?;
    let noir_groth16 = loaded.noir_groth16_repo();
    let groth16_ckb = loaded.groth16_ckb_repo();
    validate_external_repository(
        "Noir-Groth16",
        &noir_groth16,
        &loaded.config.repositories.noir_groth16_revision,
    )?;
    validate_external_repository(
        "groth16-ckb",
        &groth16_ckb,
        &loaded.config.repositories.groth16_ckb_revision,
    )?;

    let nargo_version = validate_nargo_version(loaded)?;
    let snarkjs_version = validate_snarkjs_version(loaded)?;
    validate_host_rust(loaded)?;
    validate_contract_rust(loaded)?;

    CommandSpec::new("cargo", &noir_groth16)
        .args([
            toolchain_arg(&loaded.config.tools.host_rust_toolchain),
            OsString::from("build"),
            OsString::from("--locked"),
            OsString::from("-p"),
            OsString::from("noir-cli"),
        ])
        .run()?;

    CommandSpec::new("./scripts/build-ckb-script.sh", &groth16_ckb)
        .env(
            "RUSTUP_TOOLCHAIN",
            &loaded.config.tools.contract_rust_toolchain,
        )
        .run()?;
    CommandSpec::new("./scripts/build-capsule-binding.sh", &loaded.root).run()?;

    let circuit_dir = loaded.circuit_dir();
    CommandSpec::new("nargo", &circuit_dir).arg("check").run()?;
    CommandSpec::new("nargo", &circuit_dir)
        .args(["compile", "--print-acir"])
        .run()?;

    let circuit_artifact = loaded.circuit_artifact();
    require_path(&circuit_artifact)?;
    validate_noir_artifact(loaded, &circuit_artifact)?;

    let run_id = new_run_id()?;
    let build_dir = loaded.output_dir().join("builds").join(&run_id);
    create_dir(&build_dir)?;
    let parse_dir = build_dir.join("parse");
    let witness_dir = build_dir.join("witness");
    let interop_dir = build_dir.join("interop");
    let backend = noir_groth16.join("target/debug/noir-cli");
    require_path(&backend)?;

    CommandSpec::new(&backend, &noir_groth16)
        .args([
            OsString::from("compile-r1cs"),
            circuit_artifact.as_os_str().to_owned(),
            OsString::from("--out"),
            parse_dir.as_os_str().to_owned(),
        ])
        .run()?;
    CommandSpec::new(&backend, &noir_groth16)
        .args([
            OsString::from("witness"),
            circuit_artifact.as_os_str().to_owned(),
            loaded.circuit_inputs().as_os_str().to_owned(),
            OsString::from("--out"),
            witness_dir.as_os_str().to_owned(),
        ])
        .run()?;
    CommandSpec::new(&backend, &noir_groth16)
        .args([
            OsString::from("interop"),
            circuit_artifact.as_os_str().to_owned(),
            loaded.circuit_inputs().as_os_str().to_owned(),
            OsString::from("--out"),
            interop_dir.as_os_str().to_owned(),
        ])
        .run()?;

    let r1cs = interop_dir.join("circuit.r1cs");
    let wtns = interop_dir.join("witness.wtns");
    let r1cs_json = interop_dir.join("circuit.r1cs.json");
    let witness_json = interop_dir.join("witness.json");
    require_path(&parse_dir.join("parsed.json"))?;
    require_path(&r1cs)?;
    require_path(&wtns)?;

    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("r1cs"),
            OsString::from("info"),
            r1cs.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("r1cs"),
            OsString::from("export"),
            OsString::from("json"),
            r1cs.as_os_str().to_owned(),
            r1cs_json.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("wtns"),
            OsString::from("check"),
            r1cs.as_os_str().to_owned(),
            wtns.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("wtns"),
            OsString::from("export"),
            OsString::from("json"),
            wtns.as_os_str().to_owned(),
            witness_json.as_os_str().to_owned(),
        ])
        .run()?;

    let r1cs_description: R1csDescription = read_json(&r1cs_json)?;
    let witness_values: Vec<String> = read_json(&witness_json)?;
    validate_r1cs_and_witness(loaded, &r1cs_description, &witness_values)?;

    let generic_verifier =
        groth16_ckb.join("script/target/riscv64imac-unknown-none-elf/release/ckb-script");
    let capsule_binding = loaded
        .root
        .join("contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding");
    require_path(&generic_verifier)?;
    require_path(&capsule_binding)?;

    let mut hashes = BTreeMap::new();
    record_hash(&mut hashes, "circuit_artifact", &circuit_artifact)?;
    record_hash(&mut hashes, "circuit_inputs", &loaded.circuit_inputs())?;
    record_hash(&mut hashes, "parsed_acir", &parse_dir.join("parsed.json"))?;
    record_hash(&mut hashes, "r1cs", &r1cs)?;
    record_hash(&mut hashes, "wtns", &wtns)?;
    record_hash(&mut hashes, "witness_json", &witness_json)?;
    record_hash(&mut hashes, "generic_verifier", &generic_verifier)?;
    record_hash(&mut hashes, "capsule_binding", &capsule_binding)?;

    let manifest = BuildManifest {
        version: MANIFEST_VERSION,
        profile: loaded.config.profile.clone(),
        project: loaded.config.name.clone(),
        run_id: run_id.clone(),
        repository_revision: root_revision,
        repository_dirty: root_dirty,
        noir_groth16_revision: loaded.config.repositories.noir_groth16_revision.clone(),
        groth16_ckb_revision: loaded.config.repositories.groth16_ckb_revision.clone(),
        nargo_version,
        snarkjs_version,
        build_dir: build_dir.clone(),
        circuit_artifact,
        r1cs,
        wtns,
        witness_json,
        expected_public_names: loaded.config.circuit.expected_public_names.clone(),
        binding_action: loaded.config.binding.action.clone(),
        public_sources: loaded.config.binding.public_sources.clone(),
        expected_public_values: loaded.config.circuit.expected_public_values.clone(),
        expected_private_names: loaded.config.circuit.expected_private_names.clone(),
        public_input_count: r1cs_description.n_pub_inputs,
        private_input_count: r1cs_description.n_prv_inputs,
        constraint_count: r1cs_description.n_constraints,
        wire_count: r1cs_description.n_vars,
        hashes,
    };
    let manifest_path = build_dir.join("build-manifest.json");
    write_json(&manifest_path, &manifest)?;
    update_current(&loaded.output_dir(), CURRENT_BUILD, &manifest_path)?;

    println!("build_status=compatible");
    println!("public_input_count={}", manifest.public_input_count);
    println!("private_input_count={}", manifest.private_input_count);
    println!("constraint_count={}", manifest.constraint_count);
    println!("wire_count={}", manifest.wire_count);
    println!("build_manifest={}", manifest_path.display());
    Ok(())
}

pub fn prove(loaded: &LoadedConfig) -> Result<(), CliError> {
    println!("profile={DEVELOPMENT_PROFILE}");
    println!("warning=the proving setup uses public development entropy");
    validate_required_inputs(loaded)?;
    validate_nargo_version(loaded)?;
    validate_snarkjs_version(loaded)?;

    let build_manifest_path = current_manifest_path(loaded, CURRENT_BUILD)?;
    let build_manifest: BuildManifest = read_json(&build_manifest_path)?;
    validate_build_manifest(loaded, &build_manifest)?;
    require_manifest_hash(
        &build_manifest.hashes,
        "circuit_artifact",
        &loaded.circuit_artifact(),
    )?;
    require_manifest_hash(
        &build_manifest.hashes,
        "circuit_inputs",
        &loaded.circuit_inputs(),
    )?;
    require_manifest_hash(&build_manifest.hashes, "r1cs", &build_manifest.r1cs)?;
    require_manifest_hash(&build_manifest.hashes, "wtns", &build_manifest.wtns)?;

    CommandSpec::new("nargo", loaded.circuit_dir())
        .args(["execute", "witness"])
        .run()?;
    let nargo_witness = loaded.circuit_dir().join("target/witness.gz");
    require_path(&nargo_witness)?;

    let run_id = new_run_id()?;
    let proof_dir = loaded.output_dir().join("proofs").join(&run_id);
    let groth16_dir = proof_dir.join("groth16");
    let fixture_dir = proof_dir.join("fixture");
    let adapter_dir = proof_dir.join("adapter");
    create_dir(&groth16_dir)?;
    create_dir(&fixture_dir)?;

    let pot0 = groth16_dir.join("pot12_0000.ptau");
    let pot1 = groth16_dir.join("pot12_0001.ptau");
    let pot_final = groth16_dir.join("pot12_final.ptau");
    let zkey0 = groth16_dir.join("circuit_0000.zkey");
    let zkey_final = groth16_dir.join("circuit_final.zkey");
    let verification_key = groth16_dir.join("verification_key.json");
    let proof = groth16_dir.join("proof.json");
    let public = groth16_dir.join("public.json");

    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("powersoftau"),
            OsString::from("new"),
            OsString::from("bn128"),
            OsString::from("12"),
            pot0.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("powersoftau"),
            OsString::from("contribute"),
            pot0.as_os_str().to_owned(),
            pot1.as_os_str().to_owned(),
            OsString::from("--name=noir-ckb Week 11 development-only contribution"),
            OsString::from(format!("-e=noir-ckb-public-development-entropy-{run_id}")),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("powersoftau"),
            OsString::from("prepare"),
            OsString::from("phase2"),
            pot1.as_os_str().to_owned(),
            pot_final.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("powersoftau"),
            OsString::from("verify"),
            pot_final.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("groth16"),
            OsString::from("setup"),
            build_manifest.r1cs.as_os_str().to_owned(),
            pot_final.as_os_str().to_owned(),
            zkey0.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("zkey"),
            OsString::from("contribute"),
            zkey0.as_os_str().to_owned(),
            zkey_final.as_os_str().to_owned(),
            OsString::from("--name=noir-ckb Week 11 circuit development contribution"),
            OsString::from(format!("-e=noir-ckb-public-circuit-entropy-{run_id}")),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("zkey"),
            OsString::from("verify"),
            build_manifest.r1cs.as_os_str().to_owned(),
            pot_final.as_os_str().to_owned(),
            zkey_final.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("zkey"),
            OsString::from("export"),
            OsString::from("verificationkey"),
            zkey_final.as_os_str().to_owned(),
            verification_key.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("groth16"),
            OsString::from("prove"),
            zkey_final.as_os_str().to_owned(),
            build_manifest.wtns.as_os_str().to_owned(),
            proof.as_os_str().to_owned(),
            public.as_os_str().to_owned(),
        ])
        .run()?;
    snarkjs(loaded, &loaded.root)
        .args([
            OsString::from("groth16"),
            OsString::from("verify"),
            verification_key.as_os_str().to_owned(),
            public.as_os_str().to_owned(),
            proof.as_os_str().to_owned(),
        ])
        .run()?;

    let public_values: Vec<String> = read_json(&public)?;
    require_exact_values(
        "Groth16 public vector",
        &loaded.config.circuit.expected_public_values,
        &public_values,
    )?;

    let fixture_vk = fixture_dir.join("verification_key.json");
    let fixture_proof = fixture_dir.join("proof.json");
    let fixture_public = fixture_dir.join("public.json");
    copy_file(&verification_key, &fixture_vk)?;
    copy_file(&proof, &fixture_proof)?;
    copy_file(&public, &fixture_public)?;

    let mut negative_public = Vec::new();
    for source in loaded.negative_public_paths() {
        let name = source.file_name().ok_or_else(|| {
            CliError::Config(format!(
                "negative fixture has no file name: {}",
                source.display()
            ))
        })?;
        let destination = fixture_dir.join(name);
        copy_file(&source, &destination)?;
        snarkjs(loaded, &loaded.root)
            .args([
                OsString::from("groth16"),
                OsString::from("verify"),
                verification_key.as_os_str().to_owned(),
                destination.as_os_str().to_owned(),
                proof.as_os_str().to_owned(),
            ])
            .require_failure()?;
        negative_public.push(destination);
    }

    let converted = load_and_convert(&fixture_vk, &fixture_proof, &fixture_public)?;
    if !verify(
        &converted.verifying_key,
        &converted.public_inputs,
        &converted.proof,
    )? {
        return Err(CliError::Compatibility(
            "arkworks rejected the generated proof".into(),
        ));
    }
    for negative in &negative_public {
        let values = load_public_inputs(negative)?;
        if verify(&converted.verifying_key, &values, &converted.proof)? {
            return Err(CliError::Compatibility(format!(
                "arkworks accepted negative public vector {}",
                negative.display()
            )));
        }
    }
    let wire = build_wire_artifacts(
        &converted.verifying_key,
        &converted.proof,
        &converted.public_inputs,
    )?;
    verify_endpoint_round_trip(&wire)?;
    write_wire_artifacts(&adapter_dir, &wire, converted.public_inputs.len())?;
    let vk_data_hash = hex::encode(wire.vk_data_hash);

    let mut hashes = BTreeMap::new();
    for (label, path) in [
        ("r1cs", build_manifest.r1cs.as_path()),
        ("wtns", build_manifest.wtns.as_path()),
        ("ptau_final", pot_final.as_path()),
        ("zkey_final", zkey_final.as_path()),
        ("verification_key", fixture_vk.as_path()),
        ("proof", fixture_proof.as_path()),
        ("public", fixture_public.as_path()),
        ("vk_molecule", adapter_dir.join("vk.mol.bin").as_path()),
        (
            "witness_molecule",
            adapter_dir.join("witness.mol.bin").as_path(),
        ),
    ] {
        record_hash(&mut hashes, label, path)?;
    }
    for path in &negative_public {
        let key = format!(
            "negative_{}",
            path.file_stem()
                .and_then(|name| name.to_str())
                .unwrap_or("public")
        );
        record_hash(&mut hashes, &key, path)?;
    }

    let manifest = ProofManifest {
        version: MANIFEST_VERSION,
        profile: loaded.config.profile.clone(),
        project: loaded.config.name.clone(),
        run_id: run_id.clone(),
        build_manifest: build_manifest_path,
        proof_dir: proof_dir.clone(),
        fixture_dir,
        adapter_dir,
        verification_key: fixture_vk,
        proof: fixture_proof,
        public: fixture_public,
        public_values,
        negative_public,
        vk_data_hash,
        hashes,
    };
    let manifest_path = proof_dir.join("proof-manifest.json");
    write_json(&manifest_path, &manifest)?;
    update_current(&loaded.output_dir(), CURRENT_PROOF, &manifest_path)?;

    println!("prove_status=verified");
    println!("public_vector={:?}", manifest.public_values);
    println!("vk_data_hash={}", manifest.vk_data_hash);
    println!("proof_manifest={}", manifest_path.display());
    Ok(())
}

pub fn test(loaded: &LoadedConfig) -> Result<(), CliError> {
    println!("profile={DEVELOPMENT_PROFILE}");
    let proof_manifest_path = current_manifest_path(loaded, CURRENT_PROOF)?;
    let proof_manifest: ProofManifest = read_json(&proof_manifest_path)?;
    validate_proof_manifest(loaded, &proof_manifest)?;
    let build_manifest: BuildManifest = read_json(&proof_manifest.build_manifest)?;
    validate_build_manifest(loaded, &build_manifest)?;

    let groth16_ckb = loaded.groth16_ckb_repo();
    validate_external_repository(
        "groth16-ckb",
        &groth16_ckb,
        &loaded.config.repositories.groth16_ckb_revision,
    )?;
    validate_host_rust(loaded)?;

    let generic_verifier =
        groth16_ckb.join("script/target/riscv64imac-unknown-none-elf/release/ckb-script");
    let capsule_binding = loaded
        .root
        .join("contracts/target/riscv64imac-unknown-none-elf/release/capsule-binding");
    require_path(&generic_verifier)?;
    require_path(&capsule_binding)?;
    require_path(&proof_manifest.fixture_dir.join("verification_key.json"))?;
    require_path(&proof_manifest.fixture_dir.join("proof.json"))?;
    require_path(&proof_manifest.fixture_dir.join("public.json"))?;
    for negative in &proof_manifest.negative_public {
        require_path(negative)?;
        let key = format!(
            "negative_{}",
            negative
                .file_stem()
                .and_then(|name| name.to_str())
                .unwrap_or("public")
        );
        require_manifest_hash(&proof_manifest.hashes, &key, negative)?;
    }
    require_manifest_hash(
        &proof_manifest.hashes,
        "verification_key",
        &proof_manifest.verification_key,
    )?;
    require_manifest_hash(&proof_manifest.hashes, "proof", &proof_manifest.proof)?;
    require_manifest_hash(&proof_manifest.hashes, "public", &proof_manifest.public)?;
    require_manifest_hash(
        &build_manifest.hashes,
        "generic_verifier",
        &generic_verifier,
    )?;
    require_manifest_hash(&build_manifest.hashes, "capsule_binding", &capsule_binding)?;

    CommandSpec::new("cargo", &loaded.root)
        .args([
            toolchain_arg(&loaded.config.tools.host_rust_toolchain),
            OsString::from("test"),
            OsString::from("--locked"),
            OsString::from("--workspace"),
        ])
        .env_remove("GROTH16_CKB_SCRIPT_BIN")
        .env_remove("CKB_CAPSULE_BINDING_SCRIPT_BIN")
        .env_remove("NOIR_CKB_FIXTURE_DIR")
        .run()?;

    let matrix = CommandSpec::new("cargo", &loaded.root)
        .args([
            toolchain_arg(&loaded.config.tools.host_rust_toolchain),
            OsString::from("test"),
            OsString::from("--locked"),
            OsString::from("-p"),
            OsString::from("ckb-integration-tests"),
            OsString::from("--test"),
            OsString::from("capsule_transition"),
            OsString::from("--"),
            OsString::from("--ignored"),
            OsString::from("--nocapture"),
        ])
        .env("GROTH16_CKB_SCRIPT_BIN", generic_verifier.as_os_str())
        .env(
            "CKB_CAPSULE_BINDING_SCRIPT_BIN",
            capsule_binding.as_os_str(),
        )
        .env(
            "NOIR_CKB_FIXTURE_DIR",
            proof_manifest.fixture_dir.as_os_str(),
        )
        .capture_success()?;

    let combined = format!("{}\n{}", matrix.stdout, matrix.stderr);
    if !combined.contains("test result: ok. 12 passed; 0 failed; 0 ignored") {
        return Err(CliError::Compatibility(
            "CKB-VM output did not contain the required 12-pass matrix summary".into(),
        ));
    }
    let accepted_cycles = parse_cycles(&combined)?;

    let run_id = new_run_id()?;
    let report_dir = loaded.output_dir().join("tests").join(&run_id);
    create_dir(&report_dir)?;
    let mut hashes = BTreeMap::new();
    record_hash(&mut hashes, "generic_verifier", &generic_verifier)?;
    record_hash(&mut hashes, "capsule_binding", &capsule_binding)?;
    record_hash(
        &mut hashes,
        "verification_key",
        &proof_manifest.verification_key,
    )?;
    record_hash(&mut hashes, "proof", &proof_manifest.proof)?;
    record_hash(&mut hashes, "public", &proof_manifest.public)?;

    let report = TestReport {
        version: MANIFEST_VERSION,
        profile: loaded.config.profile.clone(),
        project: loaded.config.name.clone(),
        run_id,
        proof_manifest: proof_manifest_path,
        host_tests_passed: true,
        ckb_vm_matrix_passed: true,
        ckb_vm_passed_cases: 12,
        accepted_cycles,
        report_dir: report_dir.clone(),
        hashes,
    };
    let report_path = report_dir.join("test-report.json");
    write_json(&report_path, &report)?;
    update_current(&loaded.output_dir(), CURRENT_TEST, &report_path)?;

    println!("test_status=passed");
    println!("ckb_vm_cases_passed=12");
    println!("accepted_cycles={accepted_cycles}");
    println!("test_report={}", report_path.display());
    Ok(())
}

fn validate_required_inputs(loaded: &LoadedConfig) -> Result<(), CliError> {
    for path in [
        loaded.path.clone(),
        loaded.circuit_dir(),
        loaded.circuit_inputs(),
        loaded.noir_groth16_repo(),
        loaded.groth16_ckb_repo(),
        loaded.root.join("scripts/build-capsule-binding.sh"),
    ] {
        require_path(&path)?;
    }
    for path in loaded.negative_public_paths() {
        require_path(&path)?;
        let values: Vec<String> = read_json(&path)?;
        if values.len() != loaded.config.circuit.expected_public_values.len() {
            return Err(CliError::Compatibility(format!(
                "negative vector {} has {} values; expected {}",
                path.display(),
                values.len(),
                loaded.config.circuit.expected_public_values.len()
            )));
        }
        if values == loaded.config.circuit.expected_public_values {
            return Err(CliError::Compatibility(format!(
                "negative vector {} equals the intended public vector",
                path.display()
            )));
        }
    }
    Ok(())
}

fn validate_external_repository(
    label: &str,
    path: &Path,
    expected_revision: &str,
) -> Result<(), CliError> {
    require_path(path)?;
    let actual = git_revision(path)?;
    if actual != expected_revision {
        return Err(CliError::Compatibility(format!(
            "{label} revision mismatch: expected {expected_revision}, observed {actual} at {}",
            path.display()
        )));
    }
    if repository_has_tracked_changes(path)? {
        return Err(CliError::Compatibility(format!(
            "{label} contains tracked changes at {}; use a clean checkout of the pinned revision",
            path.display()
        )));
    }
    Ok(())
}

fn git_revision(path: &Path) -> Result<String, CliError> {
    Ok(CommandSpec::new("git", path)
        .args(["rev-parse", "HEAD"])
        .capture_success()?
        .stdout
        .trim()
        .to_owned())
}

fn repository_has_tracked_changes(path: &Path) -> Result<bool, CliError> {
    let output = CommandSpec::new("git", path)
        .args(["status", "--short", "--untracked-files=no"])
        .capture_success()?;
    Ok(!output.stdout.trim().is_empty())
}

fn validate_nargo_version(loaded: &LoadedConfig) -> Result<String, CliError> {
    let output = CommandSpec::new("nargo", &loaded.root)
        .arg("--version")
        .capture_success()?;
    let combined = format!("{}\n{}", output.stdout, output.stderr);
    let expected = &loaded.config.tools.nargo_version;
    if !combined.contains(&format!("nargo version = {expected}")) {
        return Err(CliError::Compatibility(format!(
            "Nargo version mismatch: expected {expected}, observed {}",
            combined.trim()
        )));
    }
    Ok(combined.trim().to_owned())
}

fn validate_snarkjs_version(loaded: &LoadedConfig) -> Result<String, CliError> {
    let output = snarkjs(loaded, &loaded.root).arg("--version").capture()?;
    let combined = format!("{}\n{}", output.stdout, output.stderr);
    let expected = &loaded.config.tools.snarkjs_version;
    // snarkjs 0.7.5 has no successful `--version` command: it prints its
    // version banner and help, then exits 99. Treat only the exact banner as
    // version evidence; all operational snarkjs commands still require zero.
    if !combined.contains(&format!("snarkjs@{expected}")) {
        return Err(CliError::Compatibility(format!(
            "snarkjs version mismatch: expected {expected}, observed {}",
            combined.trim()
        )));
    }
    Ok(format!("snarkjs@{expected}"))
}

fn validate_host_rust(loaded: &LoadedConfig) -> Result<(), CliError> {
    let expected = &loaded.config.tools.host_rust_toolchain;
    let output = CommandSpec::new("rustc", &loaded.root)
        .args([toolchain_arg(expected), OsString::from("--version")])
        .capture_success()?;
    let combined = format!("{}\n{}", output.stdout, output.stderr);
    if !combined.contains(&format!("rustc {expected}")) {
        return Err(CliError::Compatibility(format!(
            "Rust toolchain mismatch: expected {expected}, observed {}",
            combined.trim()
        )));
    }
    Ok(())
}

fn validate_contract_rust(loaded: &LoadedConfig) -> Result<(), CliError> {
    let version = &loaded.config.tools.contract_rust_toolchain;
    let target = &loaded.config.tools.ckb_target;
    let version_output = CommandSpec::new("rustc", &loaded.root)
        .args([toolchain_arg(version), OsString::from("--version")])
        .capture_success()?;
    let version_text = format!("{}\n{}", version_output.stdout, version_output.stderr);
    if !version_text.contains(&format!("rustc {version}")) {
        return Err(CliError::Compatibility(format!(
            "contract Rust toolchain mismatch: expected {version}, observed {}",
            version_text.trim()
        )));
    }
    let targets = CommandSpec::new("rustup", &loaded.root)
        .args([
            OsString::from("target"),
            OsString::from("list"),
            OsString::from("--installed"),
            OsString::from("--toolchain"),
            OsString::from(version),
        ])
        .capture_success()?;
    if !targets.stdout.lines().any(|line| line.trim() == target) {
        return Err(CliError::Compatibility(format!(
            "CKB target {target} is not installed for Rust {version}"
        )));
    }
    Ok(())
}

fn validate_noir_artifact(loaded: &LoadedConfig, path: &Path) -> Result<(), CliError> {
    let artifact: NoirArtifact = read_json(path)?;
    if artifact.noir_version != loaded.config.circuit.expected_noir_version {
        return Err(CliError::Compatibility(format!(
            "Noir artifact version mismatch: expected {}, observed {}",
            loaded.config.circuit.expected_noir_version, artifact.noir_version
        )));
    }
    if !artifact.abi.return_type.is_null() {
        return Err(CliError::Compatibility(
            "circuit return values are not supported in this preview".into(),
        ));
    }
    let public = artifact
        .abi
        .parameters
        .iter()
        .filter(|parameter| parameter.visibility == "public")
        .map(|parameter| parameter.name.clone())
        .collect::<Vec<_>>();
    if artifact
        .abi
        .parameters
        .iter()
        .any(|parameter| parameter.parameter_type.kind != "field")
    {
        return Err(CliError::Compatibility(
            "this preview supports only Field circuit parameters".into(),
        ));
    }
    let private = artifact
        .abi
        .parameters
        .iter()
        .filter(|parameter| parameter.visibility == "private")
        .map(|parameter| parameter.name.clone())
        .collect::<Vec<_>>();
    let known = public.len() + private.len();
    if known != artifact.abi.parameters.len() {
        return Err(CliError::Compatibility(
            "Noir ABI contains an unsupported visibility".into(),
        ));
    }
    require_exact_values(
        "Noir public parameter order",
        &loaded.config.circuit.expected_public_names,
        &public,
    )?;
    require_exact_values(
        "Noir private parameter order",
        &loaded.config.circuit.expected_private_names,
        &private,
    )
}

fn validate_r1cs_and_witness(
    loaded: &LoadedConfig,
    r1cs: &R1csDescription,
    witness: &[String],
) -> Result<(), CliError> {
    let expected_public = &loaded.config.circuit.expected_public_values;
    let expected_private = &loaded.config.circuit.expected_private_values;
    if r1cs.n_outputs != 0 {
        return Err(CliError::Compatibility(format!(
            "R1CS outputs are unsupported; observed {}",
            r1cs.n_outputs
        )));
    }
    if r1cs.n_pub_inputs != expected_public.len() {
        return Err(CliError::Compatibility(format!(
            "R1CS public input count mismatch: expected {}, observed {}",
            expected_public.len(),
            r1cs.n_pub_inputs
        )));
    }
    if r1cs.n_prv_inputs != expected_private.len() {
        return Err(CliError::Compatibility(format!(
            "R1CS private input count mismatch: expected {}, observed {}",
            expected_private.len(),
            r1cs.n_prv_inputs
        )));
    }
    if r1cs.n_vars as usize != witness.len() {
        return Err(CliError::Compatibility(format!(
            "R1CS wire count {} does not match witness length {}",
            r1cs.n_vars,
            witness.len()
        )));
    }
    if witness.first().map(String::as_str) != Some("1") {
        return Err(CliError::Compatibility(
            "WTNS wire 0 is not the required constant one".into(),
        ));
    }
    let public_end = 1 + expected_public.len();
    let private_end = public_end + expected_private.len();
    if witness.len() < private_end {
        return Err(CliError::Compatibility(format!(
            "witness has {} wires; at least {private_end} are required",
            witness.len()
        )));
    }
    require_exact_values(
        "R1CS leading public wires",
        expected_public,
        &witness[1..public_end],
    )?;
    require_exact_values(
        "R1CS private wires",
        expected_private,
        &witness[public_end..private_end],
    )
}

fn validate_build_manifest(
    loaded: &LoadedConfig,
    manifest: &BuildManifest,
) -> Result<(), CliError> {
    if manifest.version != MANIFEST_VERSION
        || manifest.profile != loaded.config.profile
        || manifest.project != loaded.config.name
    {
        return Err(CliError::Compatibility(
            "current build manifest does not match this configuration".into(),
        ));
    }
    if manifest.noir_groth16_revision != loaded.config.repositories.noir_groth16_revision
        || manifest.groth16_ckb_revision != loaded.config.repositories.groth16_ckb_revision
    {
        return Err(CliError::Compatibility(
            "build manifest source revisions do not match this configuration".into(),
        ));
    }
    if manifest.public_input_count != loaded.config.circuit.expected_public_names.len()
        || manifest.private_input_count != loaded.config.circuit.expected_private_names.len()
    {
        return Err(CliError::Compatibility(
            "build manifest public/private counts do not match this configuration".into(),
        ));
    }
    require_exact_values(
        "build manifest public names",
        &loaded.config.circuit.expected_public_names,
        &manifest.expected_public_names,
    )?;
    require_exact_values(
        "build manifest public values",
        &loaded.config.circuit.expected_public_values,
        &manifest.expected_public_values,
    )?;
    require_exact_values(
        "build manifest private names",
        &loaded.config.circuit.expected_private_names,
        &manifest.expected_private_names,
    )?;
    if manifest.binding_action != loaded.config.binding.action {
        return Err(CliError::Compatibility(format!(
            "build manifest binding action mismatch: expected {}, observed {}",
            loaded.config.binding.action, manifest.binding_action
        )));
    }
    require_exact_values(
        "build manifest public sources",
        &loaded.config.binding.public_sources,
        &manifest.public_sources,
    )
}

fn validate_proof_manifest(
    loaded: &LoadedConfig,
    manifest: &ProofManifest,
) -> Result<(), CliError> {
    if manifest.version != MANIFEST_VERSION
        || manifest.profile != loaded.config.profile
        || manifest.project != loaded.config.name
    {
        return Err(CliError::Compatibility(
            "current proof manifest does not match this configuration".into(),
        ));
    }
    require_exact_values(
        "proof manifest public vector",
        &loaded.config.circuit.expected_public_values,
        &manifest.public_values,
    )?;
    let expected_names = loaded
        .negative_public_paths()
        .iter()
        .filter_map(|path| path.file_name().map(|name| name.to_owned()))
        .collect::<Vec<_>>();
    let manifest_names = manifest
        .negative_public
        .iter()
        .filter_map(|path| path.file_name().map(|name| name.to_owned()))
        .collect::<Vec<_>>();
    if expected_names != manifest_names {
        return Err(CliError::Compatibility(format!(
            "proof manifest negative vectors mismatch: expected {expected_names:?}, observed {manifest_names:?}"
        )));
    }
    Ok(())
}

fn require_exact_values(
    label: &str,
    expected: &[String],
    actual: &[String],
) -> Result<(), CliError> {
    if expected == actual {
        Ok(())
    } else {
        Err(CliError::Compatibility(format!(
            "{label} mismatch: expected {expected:?}, observed {actual:?}"
        )))
    }
}

fn current_manifest_path(loaded: &LoadedConfig, pointer_name: &str) -> Result<PathBuf, CliError> {
    let pointer_path = loaded.output_dir().join(pointer_name);
    let pointer: CurrentManifest = read_json(&pointer_path)?;
    require_path(&pointer.manifest)?;
    Ok(pointer.manifest)
}

fn update_current(output: &Path, pointer_name: &str, manifest: &Path) -> Result<(), CliError> {
    create_dir(output)?;
    write_json(
        &output.join(pointer_name),
        &CurrentManifest {
            manifest: manifest.to_path_buf(),
        },
    )
}

fn snarkjs(loaded: &LoadedConfig, cwd: &Path) -> CommandSpec {
    CommandSpec::new("npx", cwd).args([
        OsString::from("--yes"),
        OsString::from(format!("snarkjs@{}", loaded.config.tools.snarkjs_version)),
    ])
}

fn toolchain_arg(version: &str) -> OsString {
    OsString::from(format!("+{version}"))
}

fn create_dir(path: &Path) -> Result<(), CliError> {
    fs::create_dir_all(path).map_err(|source| CliError::CreateDirectory {
        path: path.to_path_buf(),
        source,
    })
}

fn copy_file(source_path: &Path, destination: &Path) -> Result<(), CliError> {
    fs::copy(source_path, destination)
        .map(|_| ())
        .map_err(|source| CliError::Copy {
            source_path: source_path.to_path_buf(),
            destination: destination.to_path_buf(),
            source,
        })
}

fn record_hash(
    hashes: &mut BTreeMap<String, String>,
    label: &str,
    path: &Path,
) -> Result<(), CliError> {
    hashes.insert(label.to_owned(), sha256_file(path)?);
    Ok(())
}

fn require_manifest_hash(
    hashes: &BTreeMap<String, String>,
    label: &str,
    path: &Path,
) -> Result<(), CliError> {
    require_path(path)?;
    let expected = hashes
        .get(label)
        .ok_or_else(|| CliError::Compatibility(format!("manifest is missing the {label} hash")))?;
    let actual = sha256_file(path)?;
    if &actual == expected {
        Ok(())
    } else {
        Err(CliError::Compatibility(format!(
            "{label} hash mismatch at {}: expected {expected}, observed {actual}",
            path.display()
        )))
    }
}

fn new_run_id() -> Result<String, CliError> {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| CliError::Clock)?;
    Ok(duration.as_millis().to_string())
}

fn parse_cycles(output: &str) -> Result<u64, CliError> {
    const LABEL: &str = "week10_proof_bound_capsule_cycles=";
    let value = output
        .lines()
        .find_map(|line| line.trim().strip_prefix(LABEL))
        .ok_or_else(|| {
            CliError::Compatibility("CKB-VM output did not report accepted cycles".into())
        })?;
    value.parse::<u64>().map_err(|_| {
        CliError::Compatibility(format!(
            "invalid accepted cycle count in CKB-VM output: {value}"
        ))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{BindingConfig, CircuitConfig, Config, RepositoryConfig, ToolConfig};

    fn loaded() -> LoadedConfig {
        LoadedConfig {
            config: Config {
                version: 1,
                profile: DEVELOPMENT_PROFILE.into(),
                name: "fixture".into(),
                output_dir: "target".into(),
                circuit: CircuitConfig {
                    package_dir: "circuit".into(),
                    artifact: "target/circuit.json".into(),
                    inputs: "inputs.json".into(),
                    expected_noir_version: "test".into(),
                    expected_public_names: vec!["public".into()],
                    expected_public_values: vec!["49".into()],
                    expected_private_names: vec!["private".into()],
                    expected_private_values: vec!["7".into()],
                },
                repositories: RepositoryConfig {
                    noir_groth16: "backend".into(),
                    noir_groth16_revision: "backend-revision".into(),
                    groth16_ckb: "verifier".into(),
                    groth16_ckb_revision: "verifier-revision".into(),
                },
                tools: ToolConfig {
                    nargo_version: "test".into(),
                    snarkjs_version: "test".into(),
                    host_rust_toolchain: "test".into(),
                    contract_rust_toolchain: "test".into(),
                    ckb_target: "riscv64imac-unknown-none-elf".into(),
                },
                binding: BindingConfig {
                    action: "update".into(),
                    public_sources: vec!["output.data".into()],
                    negative_public: vec!["wrong.json".into()],
                },
            },
            path: "config.toml".into(),
            root: "/fixture".into(),
        }
    }

    #[test]
    fn semantic_gate_accepts_public_first_witness() {
        let r1cs = R1csDescription {
            n_vars: 4,
            n_outputs: 0,
            n_pub_inputs: 1,
            n_prv_inputs: 1,
            n_constraints: 2,
        };
        let witness = vec!["1".into(), "49".into(), "7".into(), "49".into()];
        validate_r1cs_and_witness(&loaded(), &r1cs, &witness).unwrap();
    }

    #[test]
    fn semantic_gate_rejects_private_first_witness() {
        let r1cs = R1csDescription {
            n_vars: 4,
            n_outputs: 0,
            n_pub_inputs: 1,
            n_prv_inputs: 1,
            n_constraints: 2,
        };
        let witness = vec!["1".into(), "7".into(), "49".into(), "49".into()];
        let error = validate_r1cs_and_witness(&loaded(), &r1cs, &witness).unwrap_err();
        assert!(error
            .to_string()
            .contains("R1CS leading public wires mismatch"));
    }

    #[test]
    fn cycle_parser_extracts_matrix_measurement() {
        let cycles = parse_cycles("week10_proof_bound_capsule_cycles=101625705\n").unwrap();
        assert_eq!(cycles, 101_625_705);
    }
}
