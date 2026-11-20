#!/usr/bin/env python3
"""R2 spike: R1CS constraint counts, from the pinned backend, for Poseidon2 Merkle
membership and for note-spending circuits at several tree depths.

For each circuit it writes a Noir package, a helper package that computes the public values
from the same private inputs, compiles both with the pinned Nargo, lowers the circuit with
the pinned backend, and reads the counts from `snarkjs r1cs info`. The witness is checked
against the R1CS. Nothing is proven; no key is made.

Usage: constraints.py --nargo PATH --backend-cli PATH --snarkjs PATH --out DIR [--depths 16,20,32]
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

POSEIDON = 'poseidon = { tag = "v0.2.6", git = "https://github.com/noir-lang/poseidon" }'
LIB = '''use poseidon::poseidon2::Poseidon2;

// Domain tags (distinct small constants; a real design derives them from strings).
global TAG_OWNER: Field = 1;
global TAG_NOTE: Field = 2;
global TAG_NULLIFIER: Field = 3;

fn h2(a: Field, b: Field) -> Field { Poseidon2::hash([a, b], 2) }
fn h3(a: Field, b: Field, c: Field) -> Field { Poseidon2::hash([a, b, c], 3) }

// One level of a Merkle path: `bit` chooses the side of the running node.
fn level(node: Field, sibling: Field, bit: Field) -> Field {
    assert(bit * (bit - 1) == 0);
    let left = node + bit * (sibling - node);
    let right = sibling + bit * (node - sibling);
    h2(left, right)
}

fn owner_of(secret: Field) -> Field { h2(TAG_OWNER, secret) }
// commitment = H(H(tag, value, owner), blinding): every call takes at most 3 inputs.
fn note(value: Field, owner: Field, blinding: Field) -> Field { h2(h3(TAG_NOTE, value, owner), blinding) }
fn nullifier(secret: Field, commitment: Field) -> Field { h3(TAG_NULLIFIER, secret, commitment) }
'''


def run(cmd, cwd=None):
    q = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=3600)
    if q.returncode or "[ERROR]" in q.stdout:
        raise SystemExit(f"failed: {' '.join(map(str, cmd[:4]))}\n{q.stdout[-1500:]}{q.stderr[-1500:]}")
    return q.stdout + q.stderr


def path_params(prefix, d):
    return [f"{prefix}s{i}" for i in range(d)] + [f"{prefix}b{i}" for i in range(d)]


def climb(prefix, d, start):
    lines = [f"    let mut {prefix}node = {start};"]
    lines += [f"    {prefix}node = level({prefix}node, {prefix}s{i}, {prefix}b{i});" for i in range(d)]
    return "\n".join(lines)


def circuits(d):
    """name -> (private names, public names, constraint body, expressions that yield the public values)."""
    out = {}
    # 1. Membership only.
    out[f"membership-d{d}"] = (
        ["leaf"] + path_params("", d), ["root"],
        climb("", d, "leaf") + "\n    assert(node == root);",
        ["node"], climb("", d, "leaf"))
    # 2. Spend one note: ownership, membership, nullifier, 64-bit value, context halves.
    body = ("    let owner = owner_of(secret);\n    let cm = note(value, owner, blinding);\n"
            + climb("", d, "cm") + "\n    let nf = nullifier(secret, cm);")
    out[f"spend-1-d{d}"] = (
        ["secret", "value", "blinding"] + path_params("", d), ["root", "nf_pub", "ctx_lo", "ctx_hi"],
        body + "\n    value.assert_max_bit_size::<64>();\n    assert(node == root);\n    assert(nf == nf_pub);\n"
               "    ctx_lo.assert_max_bit_size::<128>();\n    ctx_hi.assert_max_bit_size::<128>();",
        ["node", "nf", "5", "7"], body)
    # 3. Join-split: two notes in, two notes out, public in/out and fee.
    pre = ""
    for n in (0, 1):
        pre += (f"    let owner{n} = owner_of(secret{n});\n    let cm_in{n} = note(value{n}, owner{n}, blinding{n});\n"
                + climb(f"p{n}", d, f"cm_in{n}") + f"\n    let nf{n} = nullifier(secret{n}, cm_in{n});\n")
    pre += "    let out0 = note(out_value0, out_owner0, out_blinding0);\n    let out1 = note(out_value1, out_owner1, out_blinding1);\n"
    checks = pre + "".join(f"    {v}.assert_max_bit_size::<64>();\n" for v in
                           ("value0", "value1", "out_value0", "out_value1", "public_in", "public_out", "fee"))
    checks += ("    assert(p0node == root);\n    assert(p1node == root);\n    assert(nf0 == nf0_pub);\n    assert(nf1 == nf1_pub);\n"
               "    assert(out0 == cm0_pub);\n    assert(out1 == cm1_pub);\n"
               "    assert(value0 + value1 + public_in == out_value0 + out_value1 + public_out + fee);\n"
               "    ctx_lo.assert_max_bit_size::<128>();\n    ctx_hi.assert_max_bit_size::<128>();")
    priv = []
    for n in (0, 1):
        priv += [f"secret{n}", f"value{n}", f"blinding{n}"] + path_params(f"p{n}", d)
    priv += ["out_value0", "out_owner0", "out_blinding0", "out_value1", "out_owner1", "out_blinding1"]
    out[f"joinsplit-2x2-d{d}"] = (
        priv, ["root", "nf0_pub", "nf1_pub", "cm0_pub", "cm1_pub", "public_in", "public_out", "fee", "ctx_lo", "ctx_hi"],
        checks, ["p0node", "nf0", "nf1", "out0", "out1"], pre)
    return out


def values(name, priv):
    """Private inputs. Both join-split inputs use the same note and path, so one root serves both."""
    v = {}
    for p in priv:
        if re.fullmatch(r"(p\d)?s\d+", p):
            v[p] = 1000 + int(re.search(r"\d+$", p).group())
        elif re.fullmatch(r"(p\d)?b\d+", p):
            v[p] = int(re.search(r"\d+$", p).group()) % 2
        elif p.startswith("secret"):
            v[p] = 12345
        elif p.startswith("blinding"):
            v[p] = 777
        elif p.startswith("value"):
            v[p] = 100
        elif p.startswith("out_value"):
            v[p] = 90
        elif p.startswith("out_owner"):
            v[p] = 4242
        elif p.startswith("out_blinding"):
            v[p] = 99 + int(p[-1])
        else:
            v[p] = 55
    return v


def main():
    ap = argparse.ArgumentParser()
    for a in ("nargo", "backend-cli", "snarkjs", "out"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--depths", default="16,20,32")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in map(int, a.depths.split(",")):
        for name, (priv, pub, body, pub_exprs, helper_body) in circuits(d).items():
            pkg = name.replace("-", "_")
            w = out / name
            for sub, src in (("circuit", f"fn main({', '.join(f'{p}: Field' for p in priv)}, {', '.join(f'{p}: pub Field' for p in pub)}) {{\n{body}\n}}\n"),
                             ("helper", f"fn main({', '.join(f'{p}: Field' for p in priv)}) -> pub [Field; {len(pub_exprs)}] {{\n{helper_body}\n    [{', '.join(pub_exprs)}]\n}}\n")):
                (w / sub / "src").mkdir(parents=True, exist_ok=True)
                (w / sub / "Nargo.toml").write_text(f'[package]\nname = "{pkg}_{sub}"\ntype = "bin"\nauthors = []\n\n[dependencies]\n{POSEIDON}\n')
                (w / sub / "src/main.nr").write_text(LIB + "\n" + src)
            v = values(name, priv)
            (w / "helper/Prover.toml").write_text("".join(f'{k} = "{x}"\n' for k, x in v.items()))
            text = run([a.nargo, "execute"], w / "helper")
            got = [int(x, 16) for x in re.findall(r"0x[0-9a-f]+", text.split("Circuit output:")[1])]
            public = dict(zip(pub, got))
            if name.startswith("joinsplit"):  # balance: 100 + 100 + in = 90 + 90 + out + fee
                public.update(public_in=0, public_out=15, fee=5, ctx_lo=5, ctx_hi=7)
            run([a.nargo, "compile"], w / "circuit")
            (w / "inputs.json").write_text(json.dumps({k: str(x) for k, x in {**v, **public}.items()}))
            run([a.backend_cli, "interop", w / f"circuit/target/{pkg}_circuit.json", w / "inputs.json", "--out", w / "interop"])
            info = run([a.snarkjs, "r1cs", "info", w / "interop/circuit.r1cs"])
            n = {k.strip(): int(x) for k, x in re.findall(r"# of ([\w ]+?): (\d+)", info)}
            ok = "WITNESS IS CORRECT" in run([a.snarkjs, "wtns", "check", w / "interop/circuit.r1cs", w / "interop/witness.wtns"])
            row = dict(circuit=name, depth=d, constraints=n["Constraints"], wires=n["Wires"], private_inputs=n["Private Inputs"],
                       public_inputs=n["Public Inputs"], witness_satisfies=ok)
            rows.append(row)
            print(json.dumps(row), flush=True)
    (out / "constraints.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
