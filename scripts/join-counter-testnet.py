#!/usr/bin/env python3
"""Join an existing owned-counter/v1 deployment with your own counter.

Instead of a new setup and a ~114,000 CKB deployment, a participant verifies a
published bundle (development proving key, verification key, R1CS, circuit,
contract binary and deployment OutPoints) and creates their own counter Cell
against the live code and key Cells, for about 200 CKB of locked capacity.

Subcommands:
  init     verify bundle, live deployment, toolchain identity and a test proof
  create   prepare an unsigned creation transaction (count 0)
  update   prepare, prove and check an unsigned update (count n -> n+1)
  check    re-check the prepared update after signing, before sending
  confirm  confirm a submitted transaction and record the new Cells
  status   show progress
  make-bundle  maintainer only: build a bundle from a release and receipt

This tool never reads wallets, keys or passwords, and never signs or broadcasts.
It prints the ckb-cli commands; you run them with your own testnet account.
The setup is single-party development material: whoever ran it could in
principle forge proofs. Testnet only.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import counter_platform as cp
import owned_counter as c

SCHEMA = "noir-ckb/counter-join-bundle/v1"
DEFAULT_BUNDLE = c.ROOT / "releases/owned-counter-v1-testnet"
DEFAULT_RECORD = c.ROOT / "evidence/week-15-public/deployment.json"
SNARK = ["npx", "--offline", "snarkjs@0.7.5"]
# bundle file -> location inside the setup directory that owned_counter.py expects
SETUP_FILES = {
    "development.zkey": "development.zkey",
    "verification_key.json": "verification_key.json",
    "circuit.r1cs": "interop/circuit.r1cs",
    "owned_counter_v1.json": "circuit/target/owned_counter_v1.json",
}
ARTIFACT_FILES = {"type": "owned-counter", "vk": "vk.mol.bin"}
RECORD_SETUP_KEYS = {  # public record's setup hash keys
    "development.zkey": "development.zkey",
    "verification_key.json": "verification_key.json",
    "circuit.r1cs": "interop/circuit.r1cs",
}
TEST_INPUTS = {"old_count": "0", "new_count": "1", "context_lo": "13", "context_hi": "17"}
APP_CAPACITY_CKB = 200
MIN_CHANGE_CKB = 61


def out_dir(path, must_exist):
    path = path.resolve()
    c.require(path.is_relative_to((c.ROOT / "target").resolve()), "work directory must be below this checkout's target/")
    if must_exist:
        c.require((path / "state.json").is_file(), f"{path} is not an initialized join directory")
    else:
        c.require(not path.exists(), f"{path} exists; choose a new directory")
    return path


def safe_name(name):
    c.require(name and "/" not in name and "\\" not in name and name not in (".", ".."), f"unsafe bundle file name: {name}")
    return name


# ---------------------------------------------------------------- bundle checks
def verify_bundle(bundle, record=None):
    """Check every bundled file against the bundle manifest and, when given, the public record."""
    bundle = Path(bundle).resolve()
    man = c.read(bundle / "manifest.json")
    c.require(man.get("schema") == SCHEMA, "unexpected bundle schema")
    c.require(man.get("profile") == c.PROFILE, "bundle is for a different profile")
    c.require(set(man["files"]) == set(SETUP_FILES), "bundle setup file set differs")
    for name, meta in man["files"].items():
        data = (bundle / safe_name(name)).read_bytes()
        c.require(cp.sha256_bytes(data) == meta["sha256"] and len(data) == meta["bytes"], f"bundle file changed: {name}")
    c.require(set(man["artifacts"]) == set(ARTIFACT_FILES), "bundle artifact set differs")
    for kind, meta in man["artifacts"].items():
        c.require(meta["file"] == ARTIFACT_FILES[kind], f"unexpected {kind} file name")
        data = (bundle / safe_name(meta["file"])).read_bytes()
        c.require(cp.sha256_bytes(data) == meta["sha256"] and len(data) == meta["bytes"]
                  and c.hx(c.h(data)) == meta["data_hash"], f"bundle artifact changed: {kind}")
    c.require(man["policy"]["vk_data_hash"] == man["artifacts"]["vk"]["data_hash"], "policy VK differs from bundled VK")
    c.require(man["policy"]["network_domain"] == man["network"], "policy network differs from bundle network")
    if record is not None:
        rec = c.read(record)
        c.require(rec["policy"] == man["policy"], "bundle policy differs from the public deployment record")
        for kind in ARTIFACT_FILES:
            for field in ("sha256", "data_hash", "bytes"):
                c.require(rec["artifacts"][kind][field] == man["artifacts"][kind][field],
                          f"bundle {kind} {field} differs from the public deployment record")
        for name, key in RECORD_SETUP_KEYS.items():
            c.require(rec["setup"]["artifacts_sha256"][key] == man["files"][name]["sha256"],
                      f"bundle {name} differs from the public deployment record")
        deployed = rec["transactions"]["deployment"]["hash"]
        c.require(all(man["deployment"][k]["tx_hash"] == deployed for k in ARTIFACT_FILES),
                  "bundle deployment OutPoints differ from the public deployment record")
    return man


def make_bundle(args):
    """Maintainer: package an existing release, its setup and deployment receipt."""
    out = args.out.resolve()
    c.require(not out.exists(), f"{out} exists")

    def mapped(path):
        path = str(path)
        for rule in args.path_map or []:
            old, new = rule.split("=", 1)
            if path.startswith(old):
                path = new + path[len(old):]
        return Path(path)

    release_path = args.release.resolve()
    release = c.read(release_path)
    c.require(release["profile"] == c.PROFILE, "release profile mismatch")
    setup = mapped(release["setup"])
    setup_manifest = c.read(setup / "manifest.json")
    receipt = c.read(args.deployment)
    c.require(receipt["status"] == "committed-and-cells-checked", "deployment receipt is not a confirmed deployment")
    c.require(receipt["network"] == release["policy"]["network_domain"], "receipt network differs from release policy")
    c.require(receipt["release_sha256"] == c.sha(release_path), "receipt belongs to a different release")
    out.mkdir(parents=True)
    files = {}
    for name, rel in SETUP_FILES.items():
        src = setup / rel
        c.require(c.sha(src) == setup_manifest["artifacts"][rel], f"setup file changed since setup: {rel}")
        shutil.copyfile(src, out / name)
        if name == "owned_counter_v1.json":
            # Debug file_map records the builder's absolute source path; nothing downstream needs it.
            artifact = c.read(out / name)
            for entry in artifact.get("file_map", {}).values():
                entry["path"] = "circuits/owned-counter-v1/src/main.nr"
            (out / name).write_text(json.dumps(artifact, separators=(",", ":")))
        files[name] = dict(sha256=c.sha(out / name), bytes=(out / name).stat().st_size)
    artifacts = {}
    for kind, name in ARTIFACT_FILES.items():
        src = mapped(release["artifacts"][kind]["path"])
        c.require(c.sha(src) == release["artifacts"][kind]["sha256"], f"release artifact changed: {kind}")
        shutil.copyfile(src, out / name)
        data = (out / name).read_bytes()
        artifacts[kind] = dict(file=name, sha256=cp.sha256_bytes(data), data_hash=c.hx(c.h(data)), bytes=len(data))
    manifest = dict(
        schema=SCHEMA, profile=c.PROFILE, network=release["policy"]["network_domain"], policy=release["policy"],
        deployment=dict(type=receipt["type"], vk=receipt["vk"]), files=files, artifacts=artifacts,
        source_release_sha256=c.sha(release_path), backend_revision=setup_manifest.get("backend_revision"),
        nargo=setup_manifest.get("nargo"), constraints=setup_manifest.get("constraints"),
        setup_note=("Single-party development setup. snarkjs mixed OS randomness into each contribution; "
                    "the person who ran it could in principle have kept it and forged proofs. Testnet only."),
        source_sha256=release.get("source_sha256"),
        circuit_artifact_note=("owned_counter_v1.json: debug file_map paths replaced with the repository-relative "
                               "source path; bytecode, ABI and debug symbols unchanged."))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_bundle(out)
    print(json.dumps(dict(bundle=str(out), files=sorted(os.listdir(out))), indent=2))


# --------------------------------------------------------------- participant flow
class Work:
    def __init__(self, path):
        self.path = path
        self.log = []

    @property
    def state(self):
        return c.read(self.path / "state.json")

    def save_state(self, state):
        (self.path / "state.json").write_text(json.dumps(state, indent=2) + "\n")

    def run(self, cmd, env=None, cwd=c.ROOT, expected=0):
        cmd = [str(x) for x in cmd]
        q = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=1800)
        self.log.append(dict(command=cmd, exit=q.returncode, stdout=q.stdout[-4000:], stderr=q.stderr[-4000:]))
        (self.path / "commands.json").write_text(json.dumps(self.log, indent=2) + "\n")
        c.require(q.returncode == expected and "[ERROR]" not in q.stdout, f"command failed: {cmd[:4]}\n{q.stdout[-2000:]}{q.stderr[-2000:]}")
        return q.stdout

    def client(self, *args):
        return self.run([sys.executable, "-B", c.ROOT / "scripts/owned_counter.py", *args])


def stage(n, total, text):
    print(f"== {n}/{total} {text}", flush=True)


def init(args):
    work = out_dir(args.out, must_exist=False)
    record = None if args.no_record else args.record
    stage(1, 7, "bundle integrity" + ("" if record else " (no public record cross-check)"))
    man = verify_bundle(args.bundle, record)
    bundle = args.bundle.resolve()
    work.mkdir(parents=True)
    w = Work(work)
    key, entry = cp.detect()
    env = cp.tool_environment(os.environ, args.tools.resolve(), key, entry)

    stage(2, 7, "network and ownership policy")
    c.network(args.rpc, man["network"])
    w.client("preflight", "--rpc", args.rpc, "--genesis", man["network"], "--out", work / "policy-live.json")
    live_policy = c.read(work / "policy-live.json")
    for field in ("network_domain", "owner_code_hash", "owner_data_hash", "owner_dep"):
        c.require(live_policy[field] == man["policy"][field], f"live chain {field} differs from the bundle")

    stage(3, 7, "deployed code and verification key Cells")
    (work / "artifacts").mkdir()
    for kind, meta in man["artifacts"].items():
        cell = c.live(args.rpc, man["deployment"][kind])
        data = c.raw(cell["data"]["content"])
        c.require(c.hx(c.h(data)) == meta["data_hash"] and data == (bundle / meta["file"]).read_bytes(),
                  f"live {kind} Cell does not hold the bundled bytes")
        shutil.copyfile(bundle / meta["file"], work / "artifacts" / meta["file"])

    stage(4, 7, "proving key matches the published verification key")
    setup = work / "setup"
    for name, rel in SETUP_FILES.items():
        (setup / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle / name, setup / rel)
    w.run(SNARK + ["zkey", "export", "verificationkey", setup / "development.zkey", work / "vk-from-zkey.json"], env)
    c.require(c.read(work / "vk-from-zkey.json") == c.read(setup / "verification_key.json"),
              "proving key does not export the published verification key")

    stage(5, 7, "your toolchain reproduces the circuit and R1CS")
    backend = args.backend.resolve()
    c.require(w.run(["git", "rev-parse", "HEAD"], env, cwd=backend).strip() == man["backend_revision"],
              f"backend must be at {man['backend_revision']}")
    c.require(not w.run(["git", "status", "--porcelain"], env, cwd=backend).strip(), "backend checkout must be clean")
    w.run(["cargo", "+1.95.0", "build", "--locked", "--offline", "-p", "noir-cli"],
          dict(env, CARGO_TARGET_DIR=str(setup / "backend-target")), cwd=backend)
    noir_cli = setup / "backend-target/debug/noir-cli"
    shutil.copytree(c.ROOT / "circuits/owned-counter-v1", work / "circuit-check")
    w.run(["nargo", "compile"], env, cwd=work / "circuit-check")
    fresh = c.read(work / "circuit-check/target/owned_counter_v1.json")
    published = c.read(setup / "circuit/target/owned_counter_v1.json")
    c.require(fresh["bytecode"] == published["bytecode"] and fresh["abi"] == published["abi"],
              "your Nargo compile differs from the published circuit")
    test = work / "test-proof"
    test.mkdir()
    c.write(test / "inputs.json", TEST_INPUTS)
    w.run([noir_cli, "interop", setup / "circuit/target/owned_counter_v1.json", test / "inputs.json", "--out", test / "interop"], env)
    c.require(c.sha(test / "interop/circuit.r1cs") == man["files"]["circuit.r1cs"]["sha256"],
              "your backend lowers the circuit to a different R1CS than the proving key was made for")

    stage(6, 7, "test proof and CKB encoding")
    w.run(SNARK + ["wtns", "check", test / "interop/circuit.r1cs", test / "interop/witness.wtns"], env)
    w.run(SNARK + ["groth16", "prove", setup / "development.zkey", test / "interop/witness.wtns", test / "proof.json", test / "public.json"], env)
    c.require(c.read(test / "public.json") == list(TEST_INPUTS.values()), "test proof public values out of order")
    w.run(SNARK + ["groth16", "verify", setup / "verification_key.json", test / "public.json", test / "proof.json"], env)
    wrong = list(TEST_INPUTS.values())
    wrong[0] = "1"
    c.write(test / "wrong.json", wrong)
    w.run(["cargo", "+1.95.0", "run", "--locked", "--offline", "-p", "artifact-adapter", "--bin", "noir-ckb-adapter", "--",
           "--vk", setup / "verification_key.json", "--proof", test / "proof.json", "--public", test / "public.json",
           "--negative-public", test / "wrong.json", "--out", test / "adapter"], env)
    c.require((test / "adapter/vk.mol.bin").read_bytes() == (work / "artifacts/vk.mol.bin").read_bytes(),
              "adapter VK encoding differs from the deployed VK Cell")

    stage(7, 7, "local release files")
    setup_manifest = dict(
        status="passed", profile=c.PROFILE, setup=man["setup_note"], backend_revision=man["backend_revision"],
        backend_binary_sha256=c.sha(noir_cli), joined_bundle_manifest_sha256=c.sha(bundle / "manifest.json"),
        artifacts={rel: c.sha(setup / rel) for rel in SETUP_FILES.values()})
    (setup / "manifest.json").write_text(json.dumps(setup_manifest, indent=2) + "\n")
    artifacts = {kind: dict(path=str(work / "artifacts" / meta["file"]), sha256=meta["sha256"],
                            data_hash=meta["data_hash"], bytes=meta["bytes"]) for kind, meta in man["artifacts"].items()}
    release = dict(profile=c.PROFILE, policy=man["policy"], setup=str(setup), artifacts=artifacts, development_only=True,
                   joined_deployment=True, bundle_manifest_sha256=c.sha(bundle / "manifest.json"))
    c.write(work / "release.json", release)
    c.write(work / "deployment.json", dict(status="published-deployment-checked-live", network=man["network"],
                                           release_sha256=c.sha(work / "release.json"),
                                           type=man["deployment"]["type"], vk=man["deployment"]["vk"]))
    w.save_state(dict(stage="initialized", rpc=args.rpc, network=man["network"], count=None, history=[]))
    minimum = c.minimum(c.output(0, c.owner("0x" + "00" * 20), dict(code_hash=man["artifacts"]["type"]["data_hash"],
                        hash_type="data1", args="0x" + "00" * 33)), c.hx(c.state(0))) // 100_000_000
    print(f"""
Verified. Your toolchain reproduces the published circuit, R1CS and verification key,
and the live testnet Cells hold the published contract and key.

Next (see docs/try-the-counter.md, Part 2):
  1. Create a dedicated testnet-only account with your own ckb-cli and fund it from the faucet.
  2. Pick ONE live, empty funding Cell of at least {APP_CAPACITY_CKB + MIN_CHANGE_CKB + 1} CKB.
     {APP_CAPACITY_CKB} CKB becomes permanently locked in your counter (minimum allowed {minimum} CKB);
     there is no withdrawal or destruction path.
  3. python3 -B scripts/join-counter-testnet.py create --work {work} --owner <your lock_arg> --funding <0xhash:index>
""")


def print_sign_send(work, tx, rpc, owner, update):
    recheck = f"\npython3 -B scripts/join-counter-testnet.py check --work {work}" if update else ""
    print(f"""
Unsigned transaction: {tx}
Review, then sign and send with YOUR testnet account (password prompt is ckb-cli's, not this tool's):

export COUNTER_TX="{tx}"
"$COUNTER_CLI" --url "{rpc}" tx info --tx-file "$COUNTER_TX"
"$COUNTER_CLI" --url "{rpc}" tx sign-inputs --tx-file "$COUNTER_TX" --from-account {owner} --add-signatures --skip-check{recheck}
"$COUNTER_CLI" --url "{rpc}" tx send --tx-file "$COUNTER_TX" --skip-check

Then, with the returned hash (check status before ever resending):
python3 -B scripts/join-counter-testnet.py confirm --work {work} --hash <tx hash>
""")


def create(args):
    work = out_dir(args.work, must_exist=True)
    w = Work(work)
    state = w.state
    c.require(state["stage"] == "initialized", f"create needs an initialized directory (current stage: {state['stage']})")
    c.owner(args.owner)
    tx = work / "create.json"
    c.require(not tx.exists(), "a creation was already prepared here; use a new work directory")
    w.client("prepare", "create", "--release", work / "release.json", "--rpc", state["rpc"], "--owner", args.owner,
             "--funding", args.funding, "--capacity", str(args.capacity_ckb * 100_000_000),
             "--deployment", work / "deployment.json", "--out", tx)
    state.update(stage="create-prepared", owner=args.owner, tx=str(tx))
    w.save_state(state)
    print(f"WARNING: {args.capacity_ckb} CKB will be permanently locked in your counter Cell.")
    print_sign_send(work, tx, state["rpc"], args.owner, update=False)


def update(args):
    work = out_dir(args.work, must_exist=True)
    w = Work(work)
    state = w.state
    c.require(state["stage"] in ("created", "updated"), f"update needs a confirmed counter (current stage: {state['stage']})")
    n = len(state["history"])
    unsigned, proof = work / f"update-{n}.json", work / f"update-{n}-proof"
    w.client("prepare", "update", "--release", work / "release.json", "--rpc", state["rpc"], "--owner", state["owner"],
             "--funding", state["funding"], "--application", state["application"],
             "--deployment", work / "deployment.json", "--out", unsigned)
    w.client("prove", "--release", work / "release.json", "--rpc", state["rpc"], "--tx", unsigned, "--out", proof)
    w.client("check", "--release", work / "release.json", "--rpc", state["rpc"], "--tx", proof / "transaction.json", "--proof", proof)
    state.update(stage="update-prepared", tx=str(proof / "transaction.json"), proof=str(proof))
    w.save_state(state)
    print_sign_send(work, proof / "transaction.json", state["rpc"], state["owner"], update=True)


def check(args):
    work = out_dir(args.work, must_exist=True)
    w = Work(work)
    state = w.state
    c.require(state["stage"] == "update-prepared", "nothing to check: prepare an update first")
    print(w.client("check", "--release", work / "release.json", "--rpc", state["rpc"], "--tx", state["tx"], "--proof", state["proof"]))


def confirm(args):
    work = out_dir(args.work, must_exist=True)
    w = Work(work)
    state = w.state
    c.require(state["stage"] in ("create-prepared", "update-prepared"), "nothing submitted to confirm")
    label = "creation" if state["stage"] == "create-prepared" else f"update-{len(state['history'])}"
    receipt = work / f"{label}-receipt.json"
    c.require(not receipt.exists(), f"{receipt} exists")
    w.client("confirm", "--release", work / "release.json", "--rpc", state["rpc"], "--tx", state["tx"],
             "--hash", args.hash, "--out", receipt)
    live = c.live(state["rpc"], dict(tx_hash=args.hash, index="0x0"))
    count = int.from_bytes(c.raw(live["data"]["content"])[1:], "little")
    state["history"].append(dict(label=label, tx_hash=args.hash, count=count))
    state.update(stage="created" if label == "creation" else "updated", count=count,
                 application=f"{args.hash}:0", funding=f"{args.hash}:1", tx=None, proof=None)
    w.save_state(state)
    print(f"Confirmed {label}: counter is now {count}. Application Cell {args.hash}:0, change {args.hash}:1.")
    print(f"Next update: python3 -B scripts/join-counter-testnet.py update --work {work}")


def status(args):
    work = out_dir(args.work, must_exist=True)
    print(json.dumps(Work(work).state, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("init")
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--rpc", default="https://testnet.ckb.dev")
    a.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    a.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    a.add_argument("--no-record", action="store_true", help="skip the public-record cross-check (local tests only)")
    a.add_argument("--backend", type=Path, default=Path(os.environ.get("COUNTER_BACKEND", c.ROOT.parent / "Noir-Groth16")))
    a.add_argument("--tools", type=Path, default=c.ROOT / "target/counter-tools")
    a.set_defaults(func=init)
    a = sub.add_parser("create")
    a.add_argument("--work", type=Path, required=True)
    a.add_argument("--owner", required=True, help="your 20-byte lock_arg (0x...)")
    a.add_argument("--funding", required=True, help="one live empty Cell you own: 0xhash:index")
    a.add_argument("--capacity-ckb", type=int, default=APP_CAPACITY_CKB)
    a.set_defaults(func=create)
    for name, func in (("update", update), ("check", check), ("status", status)):
        a = sub.add_parser(name)
        a.add_argument("--work", type=Path, required=True)
        a.set_defaults(func=func)
    a = sub.add_parser("confirm")
    a.add_argument("--work", type=Path, required=True)
    a.add_argument("--hash", required=True)
    a.set_defaults(func=confirm)
    a = sub.add_parser("make-bundle")
    a.add_argument("--release", type=Path, required=True)
    a.add_argument("--deployment", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--path-map", action="append", help="OLD_PREFIX=NEW_PREFIX for moved release paths")
    a.set_defaults(func=make_bundle)
    args = p.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, c.RpcError) as error:
        sys.exit(f"error: {error}")
