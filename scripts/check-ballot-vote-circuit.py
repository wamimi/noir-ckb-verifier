#!/usr/bin/env python3
"""Differential check, constraint counts and leak scan for the ballot vote circuit.

Each case runs through `nargo execute` (Noir's own semantics) and through
`noir-cli interop` + `snarkjs wtns check` (the pinned backend's R1CS). Both must agree
with the expected outcome, and accepted witnesses must expose exactly the seven public
values, in order, in wires 1..7 although the parameters are private first.

The run also records the R1CS constraint and wire counts and the smallest powers-of-tau
power a Groth16 setup for this circuit needs.

With --dev-key it makes a throwaway single-party key (a local powers-of-tau file and one
contribution, both deleted with the private directory), proves one accepted case and
checks that the proof verifies and that it fails with another choice and another
nullifier. This is not a ceremony and the key must never be deployed.

Voter secrets are fresh random field elements. They exist only under <out>/private
(mode 0700), which is deleted at the end unless --keep-private. results.json records case
names, outcomes and counts only. A final scan fails the run if a voter secret or a voter's
identity commitment appears in a kept file: a kept identity commitment next to a
nullifier would link a voter to a ballot. No network, wallet or chain is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import private_tally as pt  # noqa: E402  (nargo lookup and the leak scan)
CIRCUIT = ROOT / "circuits/ballot"
P = pt.P
DEPTH = 19
POSEIDON_COMMIT = pt.POSEIDON_COMMIT
PRIVATE = ["secret"] + [f"s{i}" for i in range(DEPTH)] + [f"b{i}" for i in range(DEPTH)]
PUBLIC = ["voter_root", "election_lo", "election_hi", "nullifier", "choice", "ctx_lo", "ctx_hi"]
NAMES = PRIVATE + PUBLIC
CEREMONY_POWER = 12  # the private tally's powers-of-tau file


def run(cmd, cwd, timeout=1800):
    return subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)


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
        self.noir_cli = args.noir_cli.resolve()
        self.snark = [args.snarkjs.resolve()] if args.snarkjs else ["npx", "--offline", "snarkjs@0.7.5"]
        args.nargo = pt.nargo_command(args.nargo)
        self.nargo = str(Path(args.nargo).resolve()) if os.sep in args.nargo else args.nargo
        self.secrets = set()
        self.r1cs_hashes = set()
        self.r1cs = None
        self.ws = self.private / "ballot"
        shutil.copytree(CIRCUIT, self.ws, ignore=shutil.ignore_patterns("target", "Prover.toml"))

    def secret(self):
        value = rand()
        self.secrets.add(value)
        return value

    def prepare(self):
        version = run([self.nargo, "--version"], HERE).stdout
        if "1.0.0-beta.18" not in version or "99bb8b5cf33d7669adbdef096b12d80f30b4c0c9" not in version:
            raise SystemExit("Nargo 1.0.0-beta.18 (99bb8b5c) required")
        snark = run(self.snark + ["--version"], HERE)
        if "snarkjs@0.7.5" not in snark.stdout + snark.stderr:
            raise SystemExit("snarkjs 0.7.5 required")
        q = run([self.nargo, "compile", "--workspace"], self.ws)
        if q.returncode:
            raise SystemExit(f"nargo compile failed:\n{q.stderr[-2000:]}")
        roots = [Path.home() / "nargo"] + ([Path(os.environ["NARGO_HOME"])] if os.environ.get("NARGO_HOME") else [])
        deps = [r / "github.com/noir-lang/poseidon/v0.2.6" for r in roots]
        heads = {str(d): run(["git", "-C", d, "rev-parse", "HEAD"], HERE).stdout.strip() for d in deps if d.is_dir()}
        if not heads or any(h != POSEIDON_COMMIT for h in heads.values()):
            raise SystemExit(f"poseidon v0.2.6 dependency must be {POSEIDON_COMMIT}; found {heads or 'none'}")
        q = run([self.nargo, "test", "--workspace"], self.ws)
        text = q.stdout + q.stderr
        self.noir_tests = sum(int(n) for n in re.findall(r"(\d+) tests? passed", text))
        if q.returncode or "failed" in text.lower().replace("should_fail", ""):
            raise SystemExit(f"nargo test failed:\n{text[-2000:]}")
        self.artifact = self.ws / "target/ballot_vote.json"

    def derive(self, secret, siblings, bits, election):
        """(identity, voter_root, nullifier) from Noir's own execution of the shared library."""
        values = dict(zip(PRIVATE, [secret] + siblings + bits), election_lo=election[0], election_hi=election[1])
        (self.ws / "helper/Prover.toml").write_text("".join(f'{k} = "{v}"\n' for k, v in values.items()))
        q = run([self.nargo, "execute", "--package", "ballot_helper"], self.ws)
        text = q.stdout + q.stderr
        if q.returncode or "Circuit output:" not in text:
            raise SystemExit("helper failed")
        identity, root, nullifier = [int(x, 16) for x in re.findall(r"0x[0-9a-f]+", text.split("Circuit output:")[1])][:3]
        self.secrets.add(identity)
        return identity, root, nullifier

    def voter(self, bits=None, election=None, choice=1):
        secret = self.secret()
        siblings = [rand() for _ in range(DEPTH)]
        bits = [secrets.randbelow(2) for _ in range(DEPTH)] if bits is None else bits
        election = election or (secrets.randbits(128), secrets.randbits(128))
        _, root, nullifier = self.derive(secret, siblings, bits, election)
        inputs = dict(zip(PRIVATE, [secret] + siblings + bits))
        inputs.update(voter_root=root, election_lo=election[0], election_hi=election[1], nullifier=nullifier,
                      choice=choice, ctx_lo=secrets.randbits(128), ctx_hi=secrets.randbits(128))
        return inputs

    def noir(self, inputs):
        (self.ws / "vote/Prover.toml").write_text("".join(f'{k} = "{inputs[k]}"\n' for k in NAMES))
        return run([self.nargo, "execute", "--package", "ballot_vote"], self.ws).returncode == 0

    def backend(self, name, inputs):
        work = self.private / "backend" / name
        work.mkdir(parents=True)
        (work / "inputs.json").write_text(json.dumps({k: str(inputs[k]) for k in NAMES}))
        q = run([self.noir_cli, "interop", self.artifact, work / "inputs.json", "--out", work / "interop"], HERE)
        if q.returncode or "[ERROR]" in q.stdout:
            return False, None
        r1cs, wtns = work / "interop/circuit.r1cs", work / "interop/witness.wtns"
        if run(self.snark + ["wtns", "check", r1cs, wtns], HERE).returncode:
            return False, "witness generated but R1CS not satisfied"
        self.r1cs_hashes.add(hashlib.sha256(r1cs.read_bytes()).hexdigest())
        self.r1cs = self.r1cs or r1cs
        self.accepted = self.accepted if hasattr(self, "accepted") else (work, inputs)
        run(self.snark + ["wtns", "export", "json", wtns, work / "wtns.json"], HERE)
        witness = json.loads((work / "wtns.json").read_text())
        layout = witness[1:1 + len(PUBLIC)] == [str(inputs[k]) for k in PUBLIC]
        return True, None if layout else "public wire layout mismatch"

    def cases(self, rounds):
        out = [(f"random-member-{i}", True, self.voter(choice=secrets.randbelow(2))) for i in range(rounds)]
        base = self.voter(choice=1)
        path = [base[f"s{i}"] for i in range(DEPTH)], [base[f"b{i}"] for i in range(DEPTH)]
        election = (base["election_lo"], base["election_hi"])
        # The same voter in another election: accepted there, with another nullifier.
        other_election = (election[0] ^ 1, election[1])
        _, _, other_nullifier = self.derive(base["secret"], *path, other_election)
        if other_nullifier == base["nullifier"]:
            raise SystemExit("nullifier does not depend on the election")
        elsewhere = dict(base, election_lo=other_election[0], nullifier=other_nullifier)
        # Another secret with the member's path: its own, correctly derived, nullifier.
        outsider = self.secret()
        _, _, outsider_nullifier = self.derive(outsider, *path, election)
        flip = next(i for i in range(DEPTH))
        out += [
            ("member-votes-zero", True, dict(base, choice=0)),
            ("member-votes-one", True, base),
            ("member-at-first-position", True, self.voter(bits=[0] * DEPTH)),
            ("member-at-last-position", True, self.voter(bits=[1] * DEPTH)),
            ("same-voter-in-another-election", True, elsewhere),
            ("non-member", False, dict(base, secret=outsider, nullifier=outsider_nullifier)),
            ("non-member-with-a-member-nullifier", False, dict(base, secret=outsider)),
            ("choice-two", False, dict(base, choice=2)),
            ("choice-minus-one", False, dict(base, choice=P - 1)),
            ("nullifier-of-another-secret", False, dict(base, nullifier=outsider_nullifier)),
            ("nullifier-of-another-election", False, dict(base, nullifier=other_nullifier)),
            ("nullifier-plus-one", False, dict(base, nullifier=(base["nullifier"] + 1) % P)),
            ("election-changed-nullifier-kept", False, dict(base, election_lo=other_election[0])),
            ("tampered-sibling-bottom", False, dict(base, s0=(base["s0"] + 1) % P)),
            ("tampered-sibling-top", False, dict(base, **{f"s{DEPTH - 1}": (base[f"s{DEPTH - 1}"] + 1) % P})),
            ("flipped-path-bit", False, dict(base, **{f"b{flip}": 1 - base[f"b{flip}"]})),
            ("path-bit-two", False, dict(base, b3=2)),
            ("wrong-voter-root", False, dict(base, voter_root=(base["voter_root"] + 1) % P)),
            ("election-lo-overflow", False, dict(base, election_lo=2**128)),
            ("election-hi-overflow", False, dict(base, election_hi=2**128)),
            ("ctx-lo-overflow", False, dict(base, ctx_lo=2**128)),
            ("ctx-hi-overflow", False, dict(base, ctx_hi=2**128)),
        ]
        return out

    def counts(self):
        text = run(self.snark + ["r1cs", "info", self.r1cs], HERE).stdout
        def get(label):
            return int(re.search(rf"# of {label}: (\d+)", text).group(1))
        c = dict(constraints=get("Constraints"), wires=get("Wires"), private_inputs=get("Private Inputs"),
                 public_inputs=get("Public Inputs"), outputs=get("Outputs"))
        # snarkjs sizes the evaluation domain for constraints + public inputs + 1.
        need = c["constraints"] + c["public_inputs"] + 1
        c["domain_rows"] = need
        c["ptau_power_needed"] = max(1, (need - 1).bit_length())
        c["fits_power_12"] = need <= 2**CEREMONY_POWER
        c["r1cs_sha256"] = sorted(self.r1cs_hashes)
        return c

    def dev_key(self, power):
        """Throwaway single-party key; everything stays in the private directory."""
        work, inputs = self.accepted
        key = self.private / "dev-key"
        key.mkdir()
        s, t0 = self.snark, time.time()
        steps = [
            s + ["powersoftau", "new", "bn128", power, key / "0.ptau"],
            s + ["powersoftau", "contribute", key / "0.ptau", key / "1.ptau", "--name=dev", f"-e={secrets.token_hex(32)}"],
            s + ["powersoftau", "prepare", "phase2", key / "1.ptau", key / "final.ptau"],
            s + ["groth16", "setup", self.r1cs, key / "final.ptau", key / "0.zkey"],
            s + ["zkey", "contribute", key / "0.zkey", key / "dev.zkey", "--name=dev", f"-e={secrets.token_hex(32)}"],
            s + ["zkey", "verify", self.r1cs, key / "final.ptau", key / "dev.zkey"],
            s + ["zkey", "export", "verificationkey", key / "dev.zkey", key / "vk.json"],
        ]
        for step in steps:
            q = run(step, HERE, timeout=3600)
            if q.returncode:
                raise SystemExit(f"dev key step failed: {step[1:3]}\n{(q.stdout + q.stderr)[-1500:]}")
        setup_seconds, t0 = time.time() - t0, time.time()
        q = run(s + ["groth16", "prove", key / "dev.zkey", work / "interop/witness.wtns", key / "proof.json", key / "public.json"], HERE)
        prove_seconds = time.time() - t0
        public = json.loads((key / "public.json").read_text())

        def verifies(values):
            (key / "try.json").write_text(json.dumps(values))
            return run(s + ["groth16", "verify", key / "vk.json", key / "try.json", key / "proof.json"], HERE).returncode == 0

        choice, nullifier = PUBLIC.index("choice"), PUBLIC.index("nullifier")
        other_choice = public[:choice] + [str(1 - int(public[choice]))] + public[choice + 1:]
        other_nullifier = public[:nullifier] + [str((int(public[nullifier]) + 1) % P)] + public[nullifier + 1:]
        return dict(kind="throwaway single-party development key; not a ceremony; deleted after the run",
                    ptau_power=power, zkey_bytes=(key / "dev.zkey").stat().st_size,
                    setup_seconds=round(setup_seconds, 1), prove_seconds=round(prove_seconds, 1),
                    public_vector_matches=public == [str(inputs[k]) for k in PUBLIC],
                    proof_verifies=q.returncode == 0 and verifies(public),
                    rejected_with_other_choice=not verifies(other_choice),
                    rejected_with_other_nullifier=not verifies(other_nullifier))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="new directory below target/")
    ap.add_argument("--noir-cli", type=Path, required=True, help="pinned backend noir-cli (828025f)")
    ap.add_argument("--nargo", default="nargo")
    ap.add_argument("--snarkjs", type=Path, help="snarkjs 0.7.5 executable (default: npx --offline snarkjs@0.7.5)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--dev-key", action="store_true", help="also make a throwaway key, prove and verify")
    ap.add_argument("--keep-private", action="store_true", help="keep throwaway secrets for debugging")
    args = ap.parse_args()
    h = Harness(args)
    summary = dict(status="failed", circuit="circuits/ballot (ballot_vote)", depth=DEPTH, poseidon_commit=POSEIDON_COMMIT)
    try:
        h.prepare()
        results = []
        for name, expected, inputs in h.cases(args.rounds):
            noir_ok = h.noir(inputs)
            backend_ok, problem = h.backend(name, inputs)
            row = dict(case=name, expected_accept=expected, noir_accept=noir_ok, backend_accept=backend_ok,
                       backend_problem=problem, agree=noir_ok == backend_ok == expected and problem is None)
            results.append(row)
            print(f"{'PASS' if row['agree'] else 'FAIL'} {name}", flush=True)
        counts = h.counts()
        ok = all(r["agree"] for r in results) and len(h.r1cs_hashes) == 1
        summary.update(noir_tests_passed=h.noir_tests, cases=len(results), counts=counts, results=results)
        print(f"R1CS: {counts['constraints']} constraints, {counts['wires']} wires, {counts['private_inputs']} private and "
              f"{counts['public_inputs']} public inputs; powers of tau: 2^{counts['ptau_power_needed']} needed; "
              f"fits 2^{CEREMONY_POWER}: {counts['fits_power_12']}")
        if args.dev_key:
            summary["dev_key"] = key = h.dev_key(counts["ptau_power_needed"])
            ok = ok and all(key[k] for k in ("public_vector_matches", "proof_verifies", "rejected_with_other_choice", "rejected_with_other_nullifier"))
            print(f"dev key (2^{key['ptau_power']}): proof verifies {key['proof_verifies']}; other choice rejected "
                  f"{key['rejected_with_other_choice']}; other nullifier rejected {key['rejected_with_other_nullifier']}; "
                  f"prove {key['prove_seconds']} s")
        summary["status"] = "passed" if ok else "failed"
    finally:
        if not args.keep_private:
            shutil.rmtree(h.private, ignore_errors=True)
    (h.out / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    leaks = pt.leak_scan(h.out, h.secrets, exclude=[h.private] if args.keep_private else [])
    scanned = sum(1 for p in h.out.rglob("*") if p.is_file())
    summary["leak_scan"] = dict(values=len(h.secrets), files=scanned, hits=leaks)
    if leaks:
        summary["status"] = "failed"
        print(f"FAIL secret material found in: {leaks}")
    (h.out / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"leak scan: {len(h.secrets)} secret values, {scanned} kept files, {len(leaks)} hits")
    print(f"{summary['status']}: {sum(r['agree'] for r in summary.get('results', []))}/{summary.get('cases', 0)} cases. {h.out / 'results.json'}")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
