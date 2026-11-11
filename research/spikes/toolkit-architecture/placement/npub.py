#!/usr/bin/env python3
"""Spike: Groth16 verification cycles in CKB-VM against the number and size of public inputs.

For each N it writes a Noir circuit with one private and N public Field parameters,
lowers it with the pinned backend, runs a development-only setup, proves twice (small
public values, full-width public values), converts with the repository's adapter and
writes one case file per proof for the placement harness.

Usage: npub.py --nargo PATH --backend-cli PATH --snarkjs PATH --adapter PATH --ptau FILE --out DIR
Development entropy only: the keys made here are public and worthless.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

P = 21888242871839275222246405745257275088548364400416034343698204186575808495617
SIZES = [1, 2, 4, 6, 8, 16, 32]


def run(cmd, cwd=None):
    q = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=1800)
    if q.returncode or "[ERROR]" in q.stdout:
        raise SystemExit(f"failed: {' '.join(map(str, cmd[:4]))}\n{q.stdout[-800:]}{q.stderr[-800:]}")
    return q.stdout


def table(parts):
    head, pos, offs = 4 + 4 * len(parts), 4 + 4 * len(parts), []
    for p in parts:
        offs.append(pos)
        pos += len(p)
    return pos.to_bytes(4, "little") + b"".join(o.to_bytes(4, "little") for o in offs) + b"".join(parts)


def main():
    ap = argparse.ArgumentParser()
    for name in ("nargo", "backend-cli", "snarkjs", "adapter", "ptau", "out"):
        ap.add_argument("--" + name, required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    (out / "cases").mkdir(parents=True, exist_ok=True)
    for n in SIZES:
        d = out / f"n{n:02d}"
        (d / "src").mkdir(parents=True, exist_ok=True)
        (d / "Nargo.toml").write_text(f'[package]\nname = "npub{n}"\ntype = "bin"\nauthors = []\n\n[dependencies]\n')
        params = ", ".join(f"p{i}: pub Field" for i in range(n))
        body = "".join(f"    s = s * p{i} + 1;\n" for i in range(n))
        (d / "src/main.nr").write_text(f"fn main(x: Field, {params}) {{\n    let mut s = x;\n{body}    assert(s != 0);\n}}\n")
        run([a.nargo, "compile"], d)
        artifact = d / f"target/npub{n}.json"
        zkey = None
        for width in ("small", "full"):
            if width == "small":
                values = [i + 2 for i in range(n)]
            else:  # deterministic full-width values below the modulus
                values = [int.from_bytes(hashlib.sha256(f"npub {n} {i}".encode()).digest(), "big") % P for i in range(n)]
            w = d / width
            w.mkdir(exist_ok=True)
            (w / "inputs.json").write_text(json.dumps(dict(x="3", **{f"p{i}": str(v) for i, v in enumerate(values)})))
            run([a.backend_cli, "interop", artifact, w / "inputs.json", "--out", w / "interop"])
            if zkey is None:
                zkey = d / "development.zkey"
                run([a.snarkjs, "groth16", "setup", w / "interop/circuit.r1cs", a.ptau, zkey])
                run([a.snarkjs, "zkey", "export", "verificationkey", zkey, d / "verification_key.json"])
            run([a.snarkjs, "groth16", "prove", zkey, w / "interop/witness.wtns", w / "proof.json", w / "public.json"])
            assert json.loads((w / "public.json").read_text()) == [str(v) for v in values], "public vector differs"
            assert "OK" in run([a.snarkjs, "groth16", "verify", d / "verification_key.json", w / "public.json", w / "proof.json"])
            run([a.adapter, "--vk", d / "verification_key.json", "--proof", w / "proof.json", "--public", w / "public.json", "--out", w / "adapter"])
            payload = (w / "adapter/witness.mol.bin").read_bytes()
            vk = (w / "adapter/vk.mol.bin").read_bytes()
            assert len(payload) == 162 + 32 * n and len(vk) == 302 + 32 * n, (len(payload), len(vk))
            witness = table([b"", len(payload).to_bytes(4, "little") + payload, b""])
            (out / "cases" / f"n{n:02d}-{width}.json").write_text(json.dumps(dict(
                transaction=dict(witnesses=["0x" + witness.hex()]), cells=[dict(data="0x" + vk.hex())])))
            print(f"n={n} {width}: payload {len(payload)} bytes, key {len(vk)} bytes, witness {len(witness)} bytes", flush=True)


if __name__ == "__main__":
    main()
