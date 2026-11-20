#!/usr/bin/env python3
"""R1 spike: does the pinned Noir-Groth16 backend accept the ACIR of a given Nargo?

For one Nargo binary it compiles a copy of circuits/private-tally-v2 (the original is
never touched), then pushes the artifact through the backend and snarkjs and records, as
one JSON object, how far it got and what the artifacts look like:

  compile -> ABI -> ACIR (decoded opcode census) -> commitments from the helper package
  -> backend `interop` for a creation and an update -> R1CS identity against the frozen
  ceremony R1CS -> witness check -> proof with the ceremony key -> verification.

Usage: probe.py --label L --nargo PATH --backend-cli PATH --snarkjs PATH --repo PATH
                [--poseidon TAG] --work DIR
"""
import argparse
import base64
import gzip
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

KEY, R0, R1 = 0x1F2E3D4C5B6A79880123456789ABCDEF, 0x11111111111111111111, 0x22222222222222222222
PARAMS = [("value_old", "private"), ("r_old", "private"), ("key", "private"), ("delta", "private"),
          ("r_new", "private"), ("c_old", "public"), ("c_new", "public"), ("ctx_lo", "public"), ("ctx_hi", "public")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, cwd=None):
    q = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=1800)
    return q.returncode, (q.stdout + q.stderr).strip()


def first_error(text):
    lines = [l for l in text.splitlines() if l.strip()]
    hits = [l for l in lines if re.match(r"\s*(error|Error|thread|panicked)", l)]
    return (hits or lines or [""])[0][:300]


def main():
    ap = argparse.ArgumentParser()
    for name in ("label", "nargo", "backend-cli", "snarkjs", "repo", "work"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--poseidon", help="replace the poseidon dependency tag in the copy")
    a = ap.parse_args()
    repo, work = Path(a.repo).resolve(), Path(a.work).resolve()
    out = dict(label=a.label, poseidon=a.poseidon or "v0.2.6 (as committed)")
    ws = work / "circuit"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(repo / "circuits/private-tally-v2", ws, ignore=shutil.ignore_patterns("target", "Prover.toml"))
    if a.poseidon:
        toml = ws / "commitment/Nargo.toml"
        toml.write_text(re.sub(r'tag = "v[0-9.]+"', f'tag = "{a.poseidon}"', toml.read_text()))

    def finish():
        (work / "result.json").write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))

    out["nargo"] = run([a.nargo, "--version"])[1].splitlines()[1]
    code, text = run([a.nargo, "compile", "--workspace"], ws)
    out["compile"] = "ok" if code == 0 else first_error(text)
    if code:
        return finish()
    code, text = run([a.nargo, "test", "--workspace"], ws)
    m = re.findall(r"(\d+) tests? passed", text)
    out["noir_tests"] = f"{sum(map(int, m))} passed" if code == 0 else first_error(text)

    artifact = ws / "target/private_tally_v2.json"
    art = json.loads(artifact.read_text())
    out["artifact_keys"] = sorted(k for k in art if k not in ("debug_symbols", "file_map"))
    out["abi_matches_spec"] = [(p["name"], p["visibility"]) for p in art["abi"]["parameters"]] == PARAMS
    program = gzip.decompress(base64.b64decode(art["bytecode"]))
    out["acir_bytes"], out["acir_sha256"] = len(program), hashlib.sha256(program).hexdigest()
    out["acir_first_bytes_hex"] = program[:8].hex()

    def commit(value, blinding):
        (ws / "commit-helper/Prover.toml").write_text(f'value = "{value}"\nblinding = "{blinding}"\nkey = "{KEY}"\n')
        code, text = run([a.nargo, "execute", "--package", "private_tally_commit_helper"], ws)
        m = re.search(r"Circuit output: (?:Field\()?(0x[0-9a-f]+)", text)
        if code or not m:
            raise RuntimeError(first_error(text))
        return int(m.group(1), 16)
    try:
        c0, c10, c15 = commit(0, R0), commit(10, R0), commit(15, R1)
    except RuntimeError as e:
        out["commitments"] = str(e)
        return finish()
    out["commitments_sha256"] = hashlib.sha256(f"{c0},{c10},{c15}".encode()).hexdigest()

    cases = dict(
        creation=dict(value_old=0, r_old=0, key=KEY, delta=0, r_new=R0, c_old=0, c_new=c0, ctx_lo=5, ctx_hi=7),
        update=dict(value_old=10, r_old=R0, key=KEY, delta=5, r_new=R1, c_old=c10, c_new=c15, ctx_lo=5, ctx_hi=7))
    frozen = repo / "ceremony/private-tally-v2/circuit.r1cs"
    zkey = repo / "ceremony/private-tally-v2/zkeys/tally_final.zkey"
    vk = repo / "ceremony/private-tally-v2/verification_key.json"
    for name, values in cases.items():
        d = work / name
        d.mkdir()
        (d / "inputs.json").write_text(json.dumps({k: str(v) for k, v in values.items()}))
        code, text = run([a.backend_cli, "interop", artifact, d / "inputs.json", "--out", d / "interop"])
        out[f"{name}_backend"] = "ok" if code == 0 else first_error(text)
        if code:
            continue
        r1cs = d / "interop/circuit.r1cs"
        out[f"{name}_r1cs_sha256"] = sha(r1cs)
        out[f"{name}_r1cs_is_frozen_ceremony_r1cs"] = sha(r1cs) == sha(frozen)
        info = run([a.snarkjs, "r1cs", "info", r1cs])[1]
        out[f"{name}_r1cs_info"] = {k: int(v) for k, v in re.findall(r"# of (\w[\w ]*?): (\d+)", info)}
        code, text = run([a.snarkjs, "wtns", "check", r1cs, d / "interop/witness.wtns"])
        out[f"{name}_witness_satisfies_r1cs"] = code == 0 and "WITNESS IS CORRECT" in text
        if out[f"{name}_r1cs_is_frozen_ceremony_r1cs"]:
            code, text = run([a.snarkjs, "groth16", "prove", zkey, d / "interop/witness.wtns", d / "proof.json", d / "public.json"])
            if code == 0:
                expected = [str(values[k]) for k in ("c_old", "c_new", "ctx_lo", "ctx_hi")]
                out[f"{name}_public_vector_as_declared"] = json.loads((d / "public.json").read_text()) == expected
                code, text = run([a.snarkjs, "groth16", "verify", vk, d / "public.json", d / "proof.json"])
                out[f"{name}_ceremony_key_proof"] = "verified" if code == 0 and "OK" in text else first_error(text)
            else:
                out[f"{name}_ceremony_key_proof"] = first_error(text)
        shutil.rmtree(d / "interop", ignore_errors=True)  # witness files are not kept
    finish()


if __name__ == "__main__":
    main()
