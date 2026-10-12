#!/usr/bin/env python3
"""Differential check: Noir ACVM execution vs pinned-backend R1CS for the private tally spike.

Each case runs through `nargo execute` (Noir's own semantics) and through
`noir-cli interop` + `snarkjs wtns check` (the backend's R1CS). Both must agree
with the expected outcome, and accepted witnesses must expose exactly the four
public values, in order, in wires 1..4 despite the private-first parameters.

Secrets are fresh random field elements. They exist only under <out>/private
(mode 0700), which is deleted at the end unless --keep-private. results.json
records case names and outcomes only, and a final scan fails the run if any
secret value appears in a kept file. No network, wallet or chain is used.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = 21888242871839275222246405745257275088548364400416034343698204186575808495617
MAX_DELTA = 2**32 - 1
POSEIDON_COMMIT = "00f879180a56720169cff92a56778d40678d8e26"
SNARK = ["npx", "--offline", "snarkjs@0.7.5"]
NAMES = ["value_old", "r_old", "key", "delta", "r_new", "c_old", "c_new", "ctx_lo", "ctx_hi"]


def run(cmd, cwd):
    return subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=600)


def rand():
    return secrets.randbelow(P - 1) + 1


class Harness:
    def __init__(self, args):
        self.out = args.out.resolve()
        if not self.out.is_relative_to((ROOT / "target").resolve()):
            raise SystemExit("--out must be below this checkout's target/")
        self.out.mkdir(parents=True, exist_ok=False)
        self.private = self.out / "private"
        self.private.mkdir(mode=0o700)
        self.noir_cli = args.noir_cli.resolve() if args.noir_cli else None
        self.nargo = str(Path(args.nargo).resolve()) if os.sep in args.nargo else args.nargo
        self.secrets = set()
        for name in ("circuit", "commit"):
            shutil.copytree(HERE / name, self.private / name, ignore=shutil.ignore_patterns("target", "Prover.toml"))

    def secret(self, value=None):
        value = rand() if value is None else value
        self.secrets.add(value)
        return value

    def prepare(self):
        version = run([self.nargo, "--version"], HERE).stdout
        if "1.0.0-beta.18" not in version or "99bb8b5cf33d7669adbdef096b12d80f30b4c0c9" not in version:
            raise SystemExit("Nargo 1.0.0-beta.18 (99bb8b5c) required")
        for name in ("circuit", "commit"):
            q = run([self.nargo, "compile"], self.private / name)
            if q.returncode:
                raise SystemExit(f"nargo compile {name} failed:\n{q.stderr[-2000:]}")
        # Nargo clones git dependencies under ~/nargo; NARGO_HOME (noirup's ~/.nargo) is checked as a fallback.
        roots = [Path.home() / "nargo"] + ([Path(os.environ["NARGO_HOME"])] if os.environ.get("NARGO_HOME") else [])
        deps = [r / "github.com/noir-lang/poseidon/v0.2.6" for r in roots]
        heads = {str(d): run(["git", "-C", d, "rev-parse", "HEAD"], HERE).stdout.strip() for d in deps if d.is_dir()}
        if not heads or any(h != POSEIDON_COMMIT for h in heads.values()):
            raise SystemExit(f"poseidon v0.2.6 dependency must be {POSEIDON_COMMIT}; found {heads or 'none in ' + str([str(d) for d in deps])}")
        self.artifact = self.private / "circuit/target/private_tally_spike.json"

    def commitment(self, value, blinding, key):
        pkg = self.private / "commit"
        (pkg / "Prover.toml").write_text(f'value = "{value}"\nblinding = "{blinding}"\nkey = "{key}"\n')
        q = run([self.nargo, "execute"], pkg)
        match = re.search(r"Circuit output: (0x[0-9a-f]+)", q.stdout + q.stderr)
        if q.returncode or not match:
            raise SystemExit("commitment helper failed")
        return int(match.group(1), 16)

    def noir(self, inputs):
        pkg = self.private / "circuit"
        (pkg / "Prover.toml").write_text("".join(f'{k} = "{inputs[k]}"\n' for k in NAMES))
        q = run([self.nargo, "execute"], pkg)
        return q.returncode == 0, "Cannot satisfy constraint" in q.stdout + q.stderr or "Failed" in q.stdout + q.stderr

    def backend(self, name, inputs):
        work = self.private / "backend" / name
        work.mkdir(parents=True)
        (work / "inputs.json").write_text(json.dumps({k: str(inputs[k]) for k in NAMES}))
        q = run([self.noir_cli, "interop", self.artifact, work / "inputs.json", "--out", work / "interop"], HERE)
        if q.returncode or "[ERROR]" in q.stdout:
            return False, None
        r1cs, wtns = work / "interop/circuit.r1cs", work / "interop/witness.wtns"
        if run(SNARK + ["wtns", "check", r1cs, wtns], HERE).returncode:
            return False, "witness generated but R1CS not satisfied"
        run(SNARK + ["r1cs", "export", "json", r1cs, work / "r1cs.json"], HERE)
        run(SNARK + ["wtns", "export", "json", wtns, work / "wtns.json"], HERE)
        header = json.loads((work / "r1cs.json").read_text())
        witness = json.loads((work / "wtns.json").read_text())
        expected = [str(inputs[k]) for k in ("c_old", "c_new", "ctx_lo", "ctx_hi")]
        layout = header["nPubInputs"] == 4 and header["nOutputs"] == 0 and witness[1:5] == expected
        return True, None if layout else "public wire layout mismatch"

    def cases(self, rounds):
        out = []
        for i in range(rounds):
            key, r_old, r_new = self.secret(), self.secret(), self.secret()
            value_old, delta = self.secret(secrets.randbelow(2**40)), self.secret(secrets.randbelow(MAX_DELTA + 1))
            out.append((f"random-update-{i}", True, self.update(value_old, r_old, key, delta, r_new)))
        key, r_old, r_new, r0 = self.secret(), self.secret(), self.secret(), self.secret()
        base = self.update(5, r_old, key, 7, r_new)
        out += [
            ("valid-update", True, base),
            ("valid-cover-update-delta-zero", True, self.update(5, r_old, key, 0, r_new)),
            ("valid-max-delta", True, self.update(5, r_old, key, MAX_DELTA, r_new)),
            ("valid-creation-at-zero", True, self.create(0, 0, key, r0)),
            ("wrong-key", False, dict(base, key=self.secret())),
            ("wrong-r-old", False, dict(base, r_old=self.secret())),
            ("wrong-value-old", False, dict(base, value_old=6)),
            ("wrong-c-new", False, dict(base, c_new=(base["c_new"] + 1) % P)),
            ("wrong-c-old", False, dict(base, c_old=(base["c_old"] + 1) % P)),
            ("delta-above-max", False, self.update(5, r_old, key, MAX_DELTA + 1, r_new)),
            ("value-overflow", False, self.update(2**64 - 1, r_old, key, 1, r_new)),
            ("value-old-out-of-range", False, self.update(2**64, r_old, key, 0, r_new)),
            ("creation-nonzero-value", False, self.create(3, 0, key, r0)),
            ("creation-nonzero-delta", False, self.create(0, 1, key, r0)),
            ("ctx-lo-overflow", False, dict(base, ctx_lo=2**128)),
            ("ctx-hi-overflow", False, dict(base, ctx_hi=2**128)),
        ]
        return out

    def update(self, value_old, r_old, key, delta, r_new):
        return dict(value_old=value_old, r_old=r_old, key=key, delta=delta, r_new=r_new,
                    c_old=self.commitment(value_old, r_old, key),
                    c_new=self.commitment((value_old + delta) % P, r_new, key), ctx_lo=13, ctx_hi=17)

    def create(self, value_old, delta, key, r_new):
        return dict(value_old=value_old, r_old=0, key=key, delta=delta, r_new=r_new, c_old=0,
                    c_new=self.commitment((value_old + delta) % P, r_new, key), ctx_lo=13, ctx_hi=17)

    def leak_scan(self, keep_private):
        text_patterns, byte_patterns = set(), set()
        for value in self.secrets:
            if value > 2**40:  # small fixed test values like 5 are not secrets
                text_patterns |= {str(value), format(value, "x"), format(value, "064x")}
                byte_patterns |= {value.to_bytes(32, "little"), value.to_bytes(32, "big")}  # .wtns stores raw LE
        hits = []
        for path in self.out.rglob("*"):
            if path.is_file() and not (keep_private and self.private in path.parents):
                data = path.read_bytes()
                text = data.decode("latin-1").lower()
                if any(p in text for p in text_patterns) or any(p in data for p in byte_patterns):
                    hits.append(str(path.relative_to(self.out)))
        return sorted(set(hits))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="new directory below target/")
    ap.add_argument("--noir-cli", type=Path, help="pinned backend noir-cli (omit with --noir-only)")
    ap.add_argument("--noir-only", action="store_true", help="skip the backend half (records an incomplete result)")
    ap.add_argument("--nargo", default="nargo")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--keep-private", action="store_true", help="keep throwaway secrets for debugging")
    args = ap.parse_args()
    if not args.noir_cli and not args.noir_only:
        ap.error("--noir-cli is required unless --noir-only")
    h = Harness(args)
    try:
        h.prepare()
        results = []
        for name, expected, inputs in h.cases(args.rounds):
            noir_ok, _ = h.noir(inputs)
            row = dict(case=name, expected_accept=expected, noir_accept=noir_ok)
            if h.noir_cli:
                backend_ok, problem = h.backend(name, inputs)
                row.update(backend_accept=backend_ok, backend_problem=problem)
                row["agree"] = noir_ok == backend_ok == expected and problem is None
            else:
                row["agree"] = noir_ok == expected
            results.append(row)
            print(f"{'PASS' if row['agree'] else 'FAIL'} {name}", flush=True)
    finally:
        if not args.keep_private:
            shutil.rmtree(h.private, ignore_errors=True)
    summary = dict(status="passed" if all(r["agree"] for r in results) else "failed",
                   scope="noir-only (backend NOT checked)" if args.noir_only else "noir-vs-backend differential",
                   poseidon_commit=POSEIDON_COMMIT, cases=len(results), results=results)
    (h.out / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    leaks = h.leak_scan(args.keep_private)
    if leaks:
        summary["status"] = "failed"
        print(f"FAIL secret material found in: {leaks}")
    print(f"{summary['status']}: {sum(r['agree'] for r in results)}/{len(results)} cases ({summary['scope']}). {h.out/'results.json'}")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
