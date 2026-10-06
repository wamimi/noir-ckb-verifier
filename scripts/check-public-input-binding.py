#!/usr/bin/env python3
"""Development-only unused-public-input probe; does not alter the Capsule ABI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ptau", type=Path, required=True, help="existing PUBLIC DEVELOPMENT phase-2 ptau")
    parser.add_argument("--verifier", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve(); ptau = args.ptau.resolve(); verifier = args.verifier.resolve()
    if not out.is_relative_to(ROOT / "target"): raise SystemExit("Use fresh output below target")
    out.mkdir(parents=True, exist_ok=False)
    backend = ROOT.parent / "Noir-Groth16"
    commands = []
    manifest = {"status":"running", "profile":"public-development-only-unused-public-probe",
                "ptau":str(ptau), "ptau_sha256":sha(ptau), "verifier_sha256":sha(verifier)}
    def save():
        (out / "commands.json").write_text(json.dumps(commands,indent=2)+"\n")
        (out / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    def run(cmd,cwd=ROOT,env=None,expected=0):
        overrides=env or {}; e=os.environ.copy()
        for key in ["RUSTFLAGS","CARGO_TARGET_DIR","NOIR_CKB_FIXTURE_DIR","GROTH16_CKB_SCRIPT_BIN"]: e.pop(key,None)
        e.update(overrides)
        result=subprocess.run(list(map(str,cmd)),cwd=cwd,env=e,capture_output=True,text=True,timeout=600)
        commands.append(dict(command=list(map(str,cmd)),cwd=str(cwd),env=overrides,exit=result.returncode,stdout=result.stdout,stderr=result.stderr));save()
        print(f"{cmd}: exit={result.returncode}",flush=True)
        if result.returncode!=expected:raise RuntimeError(result.stdout+result.stderr)
        return result.stdout+result.stderr
    try:
        manifest["backend_revision"]=run(["git","rev-parse","HEAD"],cwd=backend).strip()
        assert manifest["backend_revision"]=="828025f3a0090e2934940956c0f5dc8093eb5532"
        assert not run(["git","status","--porcelain"],cwd=backend).strip()
        version=run(["nargo","--version"])
        assert "1.0.0-beta.18" in version and "99bb8b5cf33d7669adbdef096b12d80f30b4c0c9" in version
        manifest["nargo_version"]=version
        snark=["npx","--offline","snarkjs@0.7.5"]
        assert "snarkjs@0.7.5" in run(snark+["--version"],expected=99)
        run(["cargo","+1.95.0","build","--locked","--offline","-p","noir-cli"],cwd=backend,env={"CARGO_TARGET_DIR":str(out/"backend-target")})
        cli=out/"backend-target/debug/noir-cli";manifest["backend_binary_sha256"]=sha(cli)
        circuit=out/"circuit";(circuit/"src").mkdir(parents=True)
        (circuit/"Nargo.toml").write_text('[package]\nname = "unused_public"\ntype = "bin"\nauthors = []\n[dependencies]\n')
        (circuit/"src/main.nr").write_text('fn main(x: Field, y: pub Field, _context: pub Field) {\n    assert(x * x == y);\n}\n')
        (circuit/"Prover.toml").write_text('x = "7"\ny = "49"\n_context = "13"\n')
        run(["nargo","compile","--print-acir"],cwd=circuit)
        run(["nargo","execute"],cwd=circuit)
        artifact=circuit/"target/unused_public.json"
        for context in [13,14]:
            inputs=out/f"inputs-{context}.json";inputs.write_text(json.dumps({"x":"7","y":"49","_context":str(context)})+"\n")
            dest=out/f"interop-{context}"
            run([cli,"interop",artifact,inputs,"--out",dest],cwd=backend)
            run(snark+["wtns","check",dest/"circuit.r1cs",dest/"witness.wtns"])
            run(snark+["r1cs","export","json",dest/"circuit.r1cs",dest/"r1cs.json"])
            run(snark+["wtns","export","json",dest/"witness.wtns",dest/"witness.json"])
            description=json.loads((dest/"r1cs.json").read_text())
            assert description["nPubInputs"]==2 and description["nOutputs"]==0
            assignment=json.loads((dest/"witness.json").read_text());assert assignment[:3]==["1","49",str(context)]
            assert all("2" not in row for constraint in description["constraints"] for row in constraint), "context wire appears in an R1CS row"
        assert sha(out/"interop-13/circuit.r1cs")==sha(out/"interop-14/circuit.r1cs")
        run(snark+["powersoftau","verify",ptau])
        run(snark+["groth16","setup",out/"interop-13/circuit.r1cs",ptau,out/"initial.zkey"])
        run(snark+["zkey","contribute",out/"initial.zkey",out/"development.zkey","--name=public unused-input probe","-e=PUBLIC-DEVELOPMENT-ONLY-binding-probe-2026-10-06"])
        run(snark+["zkey","verify",out/"interop-13/circuit.r1cs",ptau,out/"development.zkey"])
        run(snark+["zkey","export","verificationkey",out/"development.zkey",out/"verification_key.json"])
        for context in [13,14]:
            run(snark+["groth16","prove",out/"development.zkey",out/f"interop-{context}/witness.wtns",out/f"proof-{context}.json",out/f"public-{context}.json"])
            assert json.loads((out/f"public-{context}.json").read_text())==["49",str(context)]
            run(snark+["groth16","verify",out/"verification_key.json",out/f"public-{context}.json",out/f"proof-{context}.json"])
        rejected=run(snark+["groth16","verify",out/"verification_key.json",out/"public-14.json",out/"proof-13.json"],expected=1)
        assert "Invalid proof" in rejected
        run(["cargo","+1.95.0","run","--locked","--offline","-p","artifact-adapter","--bin","noir-ckb-adapter","--",
             "--vk",out/"verification_key.json","--proof",out/"proof-13.json","--public",out/"public-13.json","--negative-public",out/"public-14.json","--out",out/"adapter"])
        fixture=out/"fixture";fixture.mkdir()
        for source,name in [("verification_key.json","verification_key.json"),("proof-13.json","proof.json"),("public-13.json","public.json"),("public-14.json","wrong-new-state-public.json")]:
            (fixture/name).write_bytes((out/source).read_bytes())
        result=run(["cargo","+1.95.0","test","--locked","--offline","-p","ckb-integration-tests","--test","verifier_vm","--","--ignored","--nocapture"],
                   env={"NOIR_CKB_FIXTURE_DIR":str(fixture),"GROTH16_CKB_SCRIPT_BIN":str(verifier)})
        assert "test result: ok. 2 passed; 0 failed; 0 ignored" in result
        manifest["status"]="passed"
        manifest["artifacts"]={str(p.relative_to(out)):sha(p) for p in out.rglob("*") if p.is_file() and "backend-target" not in p.parts and p.name not in ["manifest.json","commands.json"]}
    finally: save()
    print(f"unused_public_binding=passed\nmanifest={out/'manifest.json'}")
if __name__=="__main__": main()
