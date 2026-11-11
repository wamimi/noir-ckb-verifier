#!/usr/bin/env python3
"""R1 survey: compile several circuits with two Nargo versions and compare, through the
patched backend, the decoded ACIR program and the emitted R1CS.

Usage: survey.py --old NARGO --new NARGO --backend-cli PATH --repo PATH --work DIR
"""
import argparse
import collections
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIRCUITS = {  # name: (path relative to the repository or this directory, package json, inputs)
    "owned-counter-v1": ("circuits/owned-counter-v1", dict(old_count=0, new_count=1, context_lo=5, context_hi=7)),
    "proof-bound-capsule": ("circuits/proof-bound-capsule", None),
    "square-root-public-first": ("circuits/square-root-public-first", dict(y=49, x=7)),
    "square-root (private first)": ("circuits/square-root", dict(x=7, y=49)),
    "wide (survey circuit)": (str(HERE / "wide"), dict(a=1000, b=7, idx=2, arr=["1", "2", "3", "4"], x=9)),
}


def run(cmd, cwd=None, env=None):
    q = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=1800,
                       env=dict(os.environ, **(env or {})))
    return q.returncode, q.stdout, q.stderr


def census(program):
    c = collections.Counter()
    for f in program["functions"]:
        for o in f["opcodes"]:
            k = next(iter(o))
            c[k + ("." + next(iter(o[k])) if k == "BlackBoxFuncCall" else "")] += 1
    return dict(sorted(c.items()))


def one(nargo, cli, src, work, inputs):
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(src, work, ignore=shutil.ignore_patterns("target", "Prover.toml"))
    code, out, err = run([nargo, "compile"], work)
    if code:
        return dict(compile=(out + err).strip().splitlines()[0][:200])
    artifact = next((work / "target").glob("*.json"))
    r = dict(compile="ok")
    env = dict(NOIR_CKB_DUMP_ACIR_JSON="1", NOIR_CKB_SPIKE_PERMISSIVE="1")
    code, out, err = run([cli, "compile-r1cs", artifact, "--out", work / "summary"], env=env)
    if code:
        r["decode"] = [l for l in err.splitlines() if "rc -> runtime" in l or "Error" in l][-1][:300]
        return r
    program = json.loads(err.splitlines()[0])
    r["decode"], r["program"], r["census"] = "ok", program, census(program)
    if inputs is None:
        inputs = json.loads((work / "inputs.json").read_text())
    (work / "in.json").write_text(json.dumps({k: (v if isinstance(v, list) else str(v)) for k, v in inputs.items()}))
    code, out, err = run([cli, "interop", artifact, work / "in.json", "--out", work / "interop"], env=dict(NOIR_CKB_SPIKE_PERMISSIVE="1"))
    lines = [l for l in (out + err).splitlines() if l.strip()]
    r["r1cs"] = hashlib.sha256((work / "interop/circuit.r1cs").read_bytes()).hexdigest() if code == 0 else "backend: " + lines[-1][:200]
    return r


def main():
    ap = argparse.ArgumentParser()
    for name in ("old", "new", "backend-cli", "repo", "work"):
        ap.add_argument("--" + name, required=True)
    a = ap.parse_args()
    rows = []
    for name, (path, inputs) in CIRCUITS.items():
        src = Path(path) if Path(path).is_absolute() else Path(a.repo) / path
        old = one(a.old, a.backend_cli, src, Path(a.work) / "old" / src.name, inputs)
        new = one(a.new, a.backend_cli, src, Path(a.work) / "new" / src.name, inputs)
        row = dict(circuit=name, old_compile=old["compile"], new_compile=new["compile"],
                   old_decode=old.get("decode"), new_decode=new.get("decode"),
                   opcodes_old=old.get("census"), opcodes_new=new.get("census"),
                   same_program=("program" in old and "program" in new and old["program"] == new["program"]),
                   old_r1cs=old.get("r1cs"), new_r1cs=new.get("r1cs"),
                   same_r1cs=(old.get("r1cs") == new.get("r1cs") and len(old.get("r1cs") or "") == 64))
        rows.append(row)
        print(json.dumps(row))
    (Path(a.work) / "survey.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
