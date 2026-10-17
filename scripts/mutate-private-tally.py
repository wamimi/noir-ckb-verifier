#!/usr/bin/env python3
"""Mutation tests for the private tally v2 Type Script (docs/private-tally-v2-spec.md, section 10).

For each MUTATION-BEGIN/END block in contracts/crates/private-tally/src/main.rs,
a copy of the contracts workspace is built with that block removed. The mutant
must still accept a valid update (control) and must now ACCEPT the case that the
removed check exists to reject (target). A mutation counts as detected only by
that incorrect acceptance, not by an arbitrary failure. Fresh proofs are made
for every mutant, because the mutant's code hash changes every context digest.

One block is a second layer by design: `canonical`. The pinned verifier
(groth16-ckb verifier-core) also rejects public inputs at or above the field
modulus, so with the Type's check removed the target must still be rejected, by
the verifier (code 51). That outcome is required and recorded as such.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import owned_counter as c  # noqa: E402
import private_tally as pt  # noqa: E402

spec = importlib.util.spec_from_file_location("matrix", HERE / "check-private-tally.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)

SOURCE = "crates/private-tally/src/main.rs"
# mutation -> how to build the target transaction the removed check must reject
TARGETS = {
    "verification": "invalid proof bytes with the correct public vector",
    "guard": "successor Lock is not the guard (fresh proof for that transaction)",
    "canonical": "successor commitment encoded non-canonically (fresh proof)",
    "capacity": "capacity changed on update (fresh proof)",
}


# Mutations whose target must still be rejected by a later layer, with this code.
SECOND_LAYER = {"canonical": 51}


def strip(source, name):
    lines = source.splitlines()
    start = next(i for i, x in enumerate(lines) if f"// MUTATION-BEGIN: {name}" in x)
    end = next(i for i, x in enumerate(lines) if f"// MUTATION-END: {name}" in x)
    return "\n".join(lines[:start] + lines[end + 1:]) + "\n", lines[start:end + 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True, help="a passed check-private-tally.py output")
    ap.add_argument("--out", type=Path, required=True, help="new directory below target/")
    ap.add_argument("--nargo", default="nargo")
    args = ap.parse_args()
    base = c.read(args.baseline.resolve() / "summary.json")
    c.require(base.get("status") == "passed", "baseline matrix did not pass")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    found = set()
    source_text = (pt.ROOT / "contracts" / SOURCE).read_text()
    for line in source_text.splitlines():
        if "// MUTATION-BEGIN: " in line:
            found.add(line.split("// MUTATION-BEGIN: ")[1].strip())
    c.require(found == set(TARGETS), f"mutation markers {sorted(found)} differ from targets {sorted(TARGETS)}")
    records = []
    for name in sorted(TARGETS):
        dest = out / name
        dest.mkdir()
        shutil.copytree(pt.ROOT / "contracts", dest / "contracts", ignore=shutil.ignore_patterns("target"))
        mutated, removed = strip(source_text, name)
        (dest / "contracts" / SOURCE).write_text(mutated)
        m = matrix.Matrix(argparse.Namespace(setup=args.setup, out=dest / "run", nargo=args.nargo, keep_private=False))
        record = dict(mutation=name, target=TARGETS[name], removed_lines=removed)
        try:
            m.circuit = pt.Circuit(m.private, args.nargo)
            m.artifact = m.circuit.compile()
            m.build(contracts=dest / "contracts")
            record["mutant_elf_sha256"] = c.sha(m.out / "private-tally")
            (m.out / "cases").mkdir()
            m.creation()
            control = m.update_world(name="control")
            m.save("control-update-valid", None, control[:2])
            if name == "verification":
                tx, cells, payload, _ = control
                bad = m.create_payload[:-128] + payload[-128:]
                m.save("target", 51, (tx, cells), lambda t, cs: t["witnesses"].__setitem__(0, pt.witness_args(input_type=bad)))
            elif name == "guard":
                m.save("target", 45, m.update_world(name="target", successor=m.funding_lock)[:2])
            elif name == "canonical":
                m.save("target", 54, m.update_world(name="target", noncanonical_new=True)[:2])
            elif name == "capacity":
                m.save("target", 47, m.update_world(name="target", out_capacity=matrix.TALLY_CAPACITY - matrix.CKB)[:2])
            c.write(m.out / "cases" / "cases.json", m.cases)
            m.execute()
            results = c.read(m.out / "cases" / "results.json")
            control_ok = results[0]["result"].startswith("Ok(")
            target_accepted = results[1]["result"].startswith("Ok(")
            record.update(control_accepted=control_ok, target_result=results[1]["result"][:300])
            if name in SECOND_LAYER:
                code = SECOND_LAYER[name]
                held = f"error code {code}" in results[1]["result"] or f"code {code} " in results[1]["result"]
                record.update(expectation=f"second layer: verifier rejects (code {code})",
                              detected=control_ok and held)
            else:
                record.update(expectation="incorrect acceptance", detected=control_ok and target_accepted)
        except Exception as error:  # a mutant that fails to build or run is NOT detected
            record.update(detected=False, error=str(error)[:2000])
        finally:
            shutil.rmtree(m.private.path, ignore_errors=True)
            record["leak_scan"] = pt.leak_scan(m.out, m.secrets, exclude=[m.out / "contract-target"]) or "clean"
        records.append(record)
        (out / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
        outcome = record.get("expectation", "incorrect acceptance")
        print(f"{name}: {'as required (' + outcome + ')' if record['detected'] else 'NOT as required'}", flush=True)
    ok = all(r["detected"] and r["leak_scan"] == "clean" for r in records)
    print(f"{'passed' if ok else 'failed'}: {sum(r['detected'] for r in records)}/{len(records)} mutations as required. "
          f"{out / 'manifest.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
