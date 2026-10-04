#!/usr/bin/env python3
"""Explicit local-patch validation. Does not bypass noir-ckb CLI pin checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "4b7caace1f2128e454c8d0fe50cac1ec46b1e272"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, default=ROOT.parent / "Noir-Groth16")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    backend = args.backend.resolve()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "target/week-14"):
        raise SystemExit("Output must be a fresh directory below target/week-14")
    out.mkdir(parents=True, exist_ok=False)
    records = []

    def run(command, cwd=backend, expected=0):
        result = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True, text=True)
        records.append(dict(command=list(map(str, command)), cwd=str(cwd),
                            exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        print(result.stdout, end="")
        print(result.stderr, end="")
        if result.returncode != expected:
            raise SystemExit(f"STOP: expected exit {expected}, observed {result.returncode}")
        return result.stdout

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(backend), *arguments])

    if git("rev-parse", "HEAD").decode().strip() != BASE:
        raise SystemExit("STOP: unexpected backend base revision")
    if git("branch", "--show-current").decode().strip() != "fix/week14-public-wire-layout":
        raise SystemExit("STOP: select the dedicated Week 14 fix branch")
    patch = git("diff", "--binary", "HEAD")
    if not patch:
        raise SystemExit("STOP: expected a local backend patch")
    (out / "backend.patch").write_bytes(patch)
    new_files = {}
    for raw in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if raw:
            path = Path(raw.decode())
            if not (str(path).startswith("test-vectors/week14/") or
                    str(path) == "crates/noir-r1cs/tests/week14_layout.rs" or
                    str(path) == "docs/week14-wire-layout.md"):
                raise SystemExit(f"STOP: unreviewed backend untracked file: {path}")
            data = (backend / path).read_bytes()
            new_files[str(path)] = hashlib.sha256(data).hexdigest()
            destination = out / "backend-new-files" / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    identity = dict(base_revision=BASE, profile="local-week14-development-only",
                    patch_sha256=hashlib.sha256(patch).hexdigest(), new_files=new_files,
                    status="validation-pending")
    manifest = out / "provenance.json"
    manifest.write_text(json.dumps(identity, indent=2) + "\n")
    run(["cargo", "+1.95.0", "test", "--locked", "--offline", "-p", "noir-r1cs", "--test", "week14_layout"])
    run(["cargo", "+1.95.0", "test", "--locked", "--offline", "-p", "noir-cli", "--test", "cli"])
    run(["cargo", "+1.95.0", "build", "--locked", "--offline", "-p", "noir-cli"])
    cli = backend / "target/debug/noir-cli"
    identity["backend_binary_sha256"] = hashlib.sha256(cli.read_bytes()).hexdigest()
    snarkjs = ["npx", "--offline", "snarkjs@0.7.5"]
    version = run(snarkjs + ["--version"], expected=99)
    if "snarkjs@0.7.5" not in version:
        raise SystemExit("STOP: unexpected snarkjs banner")
    for name in ["square-root", "square-root-public-first", "interleaved", "zero_public", "proof-bound-capsule"]:
        fixture = backend / "test-vectors/week14" / name
        dest = out / name
        run([cli, "interop", fixture / "artifact.json", fixture / "inputs.json", "--out", dest])
        run(snarkjs + ["wtns", "check", dest / "circuit.r1cs", dest / "witness.wtns"])
        run(snarkjs + ["wtns", "export", "json", dest / "witness.wtns", dest / "witness.json"])
        run(snarkjs + ["r1cs", "export", "json", dest / "circuit.r1cs", dest / "r1cs.json"])
        expected = json.loads((fixture / "expected-public.json").read_text())
        witness = json.loads((dest / "witness.json").read_text())
        metadata = json.loads((dest / "r1cs.json").read_text())
        if witness[0] != "1" or witness[1:1+len(expected)] != expected:
            raise SystemExit(f"STOP: public statement mismatch in {name}")
        if metadata["nOutputs"] != 0 or metadata["nPubInputs"] != len(expected):
            raise SystemExit(f"STOP: public metadata mismatch in {name}")
        if metadata["nVars"] != len(witness):
            raise SystemExit(f"STOP: wire count mismatch in {name}")
        (dest / "intended-public.json").write_text(json.dumps(expected) + "\n")
    if git("diff", "--binary", "HEAD") != patch:
        raise SystemExit("STOP: backend changed during validation")
    for name, digest in new_files.items():
        if hashlib.sha256((backend / name).read_bytes()).hexdigest() != digest:
            raise SystemExit("STOP: backend fixture changed during validation")
    identity["status"] = "layout-and-wtns-checks-passed; fresh-proofs-and-vm-pending"
    identity["artifacts"] = {
        str(path.relative_to(out)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in out.rglob("*") if path.is_file() and path != manifest
    }
    manifest.write_text(json.dumps(identity, indent=2) + "\n")
    print(f"week14_layout_checks=passed\nprovenance={manifest}\nfresh_proof_and_vm_status=pending")


if __name__ == "__main__":
    main()
