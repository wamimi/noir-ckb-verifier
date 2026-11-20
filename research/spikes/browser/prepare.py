#!/usr/bin/env python3
"""R4 spike: assemble the files the browser page needs, under web/circuits/.

  private-tally-v2     a copy of the repository circuit, the ceremony key (read only)
  spend-1-d20, joinsplit-2x2-d20, joinsplit-2x2-d32
                       the R2 counting circuits (spikes/shielded-notes/constraints.py output),
                       with a development-only setup made here from --ptau

For each circuit: artifact.json (nargo), inputs.json, witness.wtns written by the native
backend (the page compares its own witness with it), circuit.zkey, vkey.json.

Usage: prepare.py --repo DIR --nargo PATH --backend-cli PATH --snarkjs PATH --web DIR
                  [--shielded DIR --ptau FILE]
Development keys made here are public and worthless.
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

KEY, R0 = 0x1F2E3D4C5B6A79880123456789ABCDEF, 0x11111111111111111111
SHIELDED = ["spend-1-d20", "joinsplit-2x2-d20", "joinsplit-2x2-d32"]


def run(cmd, cwd=None):
    q = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=7200)
    if q.returncode or "[ERROR]" in q.stdout:
        raise SystemExit(f"failed: {' '.join(map(str, cmd[:4]))}\n{q.stdout[-1500:]}{q.stderr[-1500:]}")
    return q.stdout + q.stderr


def constraints(a, r1cs):
    return int(re.search(r"# of Constraints: (\d+)", run([a.snarkjs, "r1cs", "info", r1cs])).group(1))


def main():
    ap = argparse.ArgumentParser()
    for name in ("repo", "nargo", "backend-cli", "snarkjs", "web"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--shielded")
    ap.add_argument("--ptau")
    a = ap.parse_args()
    repo, web = Path(a.repo).resolve(), Path(a.web).resolve()
    out = web / "circuits"
    shutil.rmtree(out, ignore_errors=True)
    work = web.parent / "target" / "prepare"
    shutil.rmtree(work, ignore_errors=True)
    manifest = []

    # Private tally: creation at zero, proved with the ceremony key.
    ws = work / "tally"
    shutil.copytree(repo / "circuits/private-tally-v2", ws, ignore=shutil.ignore_patterns("target", "Prover.toml"))
    run([a.nargo, "compile", "--workspace"], ws)
    (ws / "commit-helper/Prover.toml").write_text(f'value = "0"\nblinding = "{R0}"\nkey = "{KEY}"\n')
    c0 = int(re.search(r"Circuit output: (0x[0-9a-f]+)", run([a.nargo, "execute", "--package", "private_tally_commit_helper"], ws)).group(1), 16)
    d = out / "private-tally-v2"
    d.mkdir(parents=True)
    inputs = dict(value_old=0, r_old=0, key=KEY, delta=0, r_new=R0, c_old=0, c_new=c0, ctx_lo=5, ctx_hi=7)
    (d / "inputs.json").write_text(json.dumps({k: str(v) for k, v in inputs.items()}))
    shutil.copyfile(ws / "target/private_tally_v2.json", d / "artifact.json")
    run([a.backend_cli, "interop", d / "artifact.json", d / "inputs.json", "--out", work / "tally-interop"])
    shutil.copyfile(work / "tally-interop/witness.wtns", d / "witness.wtns")
    shutil.copyfile(repo / "ceremony/private-tally-v2/zkeys/tally_final.zkey", d / "circuit.zkey")
    shutil.copyfile(repo / "ceremony/private-tally-v2/verification_key.json", d / "vkey.json")
    manifest.append(dict(name="private-tally-v2", constraints=constraints(a, work / "tally-interop/circuit.r1cs")))

    if a.shielded and a.ptau:
        for name in SHIELDED:
            src, d = Path(a.shielded) / name, out / name
            d.mkdir(parents=True)
            pkg = name.replace("-", "_")
            shutil.copyfile(src / f"circuit/target/{pkg}_circuit.json", d / "artifact.json")
            shutil.copyfile(src / "inputs.json", d / "inputs.json")
            shutil.copyfile(src / "interop/witness.wtns", d / "witness.wtns")
            run([a.snarkjs, "groth16", "setup", src / "interop/circuit.r1cs", a.ptau, d / "circuit.zkey"])
            run([a.snarkjs, "zkey", "export", "verificationkey", d / "circuit.zkey", d / "vkey.json"])
            manifest.append(dict(name=name, constraints=constraints(a, src / "interop/circuit.r1cs")))
            print("prepared", name, flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
