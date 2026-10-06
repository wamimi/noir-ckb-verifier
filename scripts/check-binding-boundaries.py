#!/usr/bin/env python3
"""Build isolated baseline/mutants; retain exact commands and require semantic detection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = "riscv64imac-unknown-none-elf"
SOURCE = Path("contracts/crates/capsule-binding/src/main.rs")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verifier", required=True, type=Path)
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/week-10-capsule")
    args = parser.parse_args()
    out, verifier, fixture = args.out.resolve(), args.verifier.resolve(), args.fixture.resolve()
    if not out.is_relative_to(ROOT / "target"):
        raise SystemExit("Use a fresh output directory below target")
    out.mkdir(parents=True, exist_ok=False)
    records = []
    protected = [ROOT / SOURCE, verifier, ROOT / f"contracts/target/{TARGET}/release/capsule-binding"]
    before = {str(p): sha(p) for p in protected}
    manifest = {"status": "running", "protected_before": before,
                "fixture": str(fixture), "fixture_hashes": {p.name: sha(p) for p in fixture.glob("*.json")},
                "test_source_sha256": sha(ROOT / "crates/ckb-integration-tests/tests/binding_boundaries.rs"),
                "runner_sha256": sha(Path(__file__)), "binaries": {}, "mutations": []}
    def save():
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    def run(command, cwd=ROOT, env=None, expected=0):
        overrides = env or {}
        environment = os.environ.copy()
        for name in ["RUSTFLAGS", "CARGO_TARGET_DIR", "NOIR_CKB_FIXTURE_DIR", "GROTH16_CKB_SCRIPT_BIN", "CKB_CAPSULE_BINDING_SCRIPT_BIN"]:
            environment.pop(name, None)
        environment.update(overrides)
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=environment,
                                capture_output=True, text=True, timeout=300)
        records.append(dict(command=list(map(str, command)), cwd=str(cwd), env=overrides,
                            exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
        save()
        print(f"{command}: exit={result.returncode}", flush=True)
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout + result.stderr
    try:
        manifest["revision"] = run(["git", "rev-parse", "HEAD"]).strip()
        manifest["initial_status"] = run(["git", "status", "--short"])
        for repo, pin in [(ROOT.parent / "Noir-Groth16", "828025f3a0090e2934940956c0f5dc8093eb5532"),
                          (ROOT.parent / "groth16-ckb", "d64c769ffe2d2edb5eb308dc59058efda77c2f83")]:
            assert run(["git", "rev-parse", "HEAD"], cwd=repo).strip() == pin
            assert not run(["git", "status", "--porcelain"], cwd=repo).strip()
        for version in ["1.95.0", "1.94.1"]:
            run(["rustc", f"+{version}", "-vV"])
        cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
        rustup_home = Path(os.environ.get("RUSTUP_HOME", str(Path.home() / ".rustup")))
        original = (ROOT / SOURCE).read_text()
        mutations = [
            ("new-state-comparison", "if actual.get(start..end) != Some(expected) {",
             "if index != 3 && actual.get(start..end) != Some(expected) {", "valid_proof_and_wrong_new_state_reject"),
            ("lock-input-cardinality", "if matching_inputs != 1 || matching_outputs != 1 {",
             "if matching_outputs != 1 {", "duplicate_verifier_lock_input_rejects_witness_ambiguity"),
        ]
        for name, old, new, test in [("baseline", None, None, None)] + mutations:
            copy = out / name
            shutil.copytree(ROOT / "contracts", copy / "contracts", ignore=shutil.ignore_patterns("target"))
            source = copy / SOURCE
            if old:
                assert original.count(old) == 1
                source.write_text(original.replace(old, new))
                (copy / "mutation.json").write_text(json.dumps({"removed": old, "replacement": new}, indent=2)+"\n")
            flags = f"-C target-feature=-a --remap-path-prefix={cargo_home}/registry/src=/cargo-registry --remap-path-prefix={rustup_home}/toolchains=/rustup-toolchains --remap-path-prefix={copy}=/build"
            run(["cargo", "+1.94.1", "build", "--locked", "--offline", "--release", "--target", TARGET, "-p", "capsule-binding"],
                cwd=copy / "contracts", env={"RUSTFLAGS": flags})
            binary = copy / f"contracts/target/{TARGET}/release/capsule-binding"
            assert binary.read_bytes()[:4] == b"\x7fELF"
            manifest["binaries"][name] = {"path": str(binary), "sha256": sha(binary), "bytes": binary.stat().st_size,
                                           "source_sha256": sha(source), "rustflags": flags}
            env = {"GROTH16_CKB_SCRIPT_BIN": str(verifier), "CKB_CAPSULE_BINDING_SCRIPT_BIN": str(binary), "NOIR_CKB_FIXTURE_DIR": str(fixture)}
            command = ["cargo", "+1.95.0", "test", "--locked", "--offline", "-p", "ckb-integration-tests", "--test"]
            if name == "baseline":
                for target, count in [("capsule_transition",12),("binding_boundaries",21),("verifier_vm",2)]:
                    output = run(command + [target,"--","--ignored","--nocapture","--test-threads=1"], env=env)
                    assert f"test result: ok. {count} passed; 0 failed; 0 ignored" in output
            else:
                run(command + ["capsule_transition","valid_proof_and_correct_capsule_transition_accept","--","--exact","--ignored","--nocapture"], env=env)
                output = run(command + ["capsule_transition",test,"--","--exact","--ignored","--nocapture"], env=env, expected=101)
                assert "transaction must be rejected: " in output and "test result: FAILED. 0 passed; 1 failed" in output
                manifest["mutations"].append({"name":name,"test":test,"detected":"missing check allowed transaction; expect_err failed"})
        manifest["status"] = "passed"
    finally:
        manifest["protected_after"] = {str(p): sha(p) for p in protected}
        save()
        assert manifest["protected_after"] == before, "baseline source/binary changed"
    print(f"binding_boundary_validation=passed\nmanifest={out / 'manifest.json'}")

if __name__ == "__main__":
    main()
