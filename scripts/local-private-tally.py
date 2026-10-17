#!/usr/bin/env python3
"""Disposable LOCAL-ONLY private tally v2 lifecycle on a loopback CKB dev chain.

Stages: local chain, development setup (or --setup), Type Script build, signed
deployment of the Type Script, verification key and guard Lock code, then the
private tally client end to end: create at 0, update +7, cover update +0, with
`check` before and after signing, `confirm`, `status` and `backup`. Ends with a
leak scan of everything kept outside the private folders. With --full it also runs
the 49-case CKB-VM matrix and the four mutation tests against the same setup.

Development keys stay in the ignored run folder. Never use them on a public network.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import counter_platform as cp  # noqa: E402
import owned_counter as c  # noqa: E402
import private_tally as pt  # noqa: E402

BASE_STEPS = ["local chain", "development setup", "Type Script build", "deployment", "create at 0",
              "update +7", "cover update +0", "status, backup and leak scan"]
FULL_STEPS = ["49-case CKB-VM matrix", "mutation tests"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for n in ("out", "ckb", "ckb-cli"):
        ap.add_argument("--" + n, type=Path, required=True)
    ap.add_argument("--backend", type=Path, default=c.ROOT.parent / "Noir-Groth16")
    ap.add_argument("--setup", type=Path, help="reuse a passed setup-private-tally.py output")
    ap.add_argument("--rpc-port", type=int, default=18134)
    ap.add_argument("--p2p-port", type=int, default=18135)
    ap.add_argument("--full", action="store_true", help="also run the CKB-VM matrix and mutation tests")
    a = ap.parse_args()
    steps = BASE_STEPS + (FULL_STEPS if a.full else [])
    platform_key, entry = cp.detect()
    out = a.out.resolve()
    c.require(out.is_relative_to(c.ROOT / "target"), "development accounts must stay below ignored target/")
    c.require(c.sha(a.ckb) == entry["tools"]["ckb"]["binary_sha256"] and c.sha(a.ckb_cli) == entry["tools"]["ckb-cli"]["binary_sha256"],
              f"unsupported node/wallet binary; use the pinned {platform_key} releases")
    out.mkdir(parents=True, exist_ok=False)
    (out / "private").mkdir(mode=0o700)
    key = out / "private/owner.key"
    key.write_text(secrets.token_hex(32) + "\n")
    key.chmod(0o600)
    env = cp.tool_environment(os.environ, a.ckb.resolve().parent.parent, platform_key, entry)
    env["CKB_CLI_HOME"] = str(out / "wallet")
    url = f"http://127.0.0.1:{a.rpc_port}"
    logs, node = [], None
    manifest = dict(status="running", profile=pt.PROFILE, network="isolated-local-development", platform=platform_key,
                    platform_status=entry["status"], validation="full" if a.full else "quick",
                    skipped=[] if a.full else ["check-private-tally.py (49 CKB-VM cases)", "mutate-private-tally.py (4 mutations)"])

    def save():
        (out / "commands.json").write_text(json.dumps(logs, indent=2) + "\n")
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def run(cmd):
        cmd = [str(x) for x in cmd]
        q = subprocess.run(cmd, cwd=c.ROOT, env=env, capture_output=True, text=True, timeout=3600)
        logs.append(dict(command=cmd, exit=q.returncode, stdout=q.stdout, stderr=q.stderr))
        save()
        print(cmd[:4], "exit", q.returncode, flush=True)
        c.require(q.returncode == 0, q.stdout[-2000:] + q.stderr[-2000:])
        return q.stdout

    def stage(name):
        print(f"== Stage {steps.index(name) + 1}/{len(steps)}: {name}", flush=True)

    def client(*args):
        return run(["python3", "-B", c.ROOT / "scripts/private-tally-client.py", *args])

    def wallet(*args):
        return run([a.ckb_cli.resolve(), "--url", url, "--output-format", "json", "tx", *args])

    def mine(txhash):
        for _ in range(12):
            status = c.rpc(url, "get_transaction", [txhash])["tx_status"]
            if status["status"] == "committed":
                return
            c.require(status["status"] != "rejected", str(status))
            c.rpc(url, "generate_block", [])
            time.sleep(0.1)
        raise RuntimeError("transaction not committed")

    def sign_send(tx, check_work=None):
        before = c.read(tx)["transaction"]
        if check_work:
            client("check", "--work", check_work)
        wallet("sign-inputs", "--tx-file", tx, "--privkey-path", key, "--add-signatures", "--skip-check")
        c.require(c.read(tx)["transaction"] == before, "wallet modified the prepared transaction")
        if check_work:
            client("check", "--work", check_work)
        txhash = json.loads(wallet("send", "--tx-file", tx, "--skip-check"))
        mine(txhash)
        return txhash

    try:
        stage("local chain")
        arg = json.loads(run([a.ckb_cli.resolve(), "--local-only", "--output-format", "json", "util", "key-info",
                              "--privkey-path", key]))["lock_arg"]
        run([a.ckb.resolve(), "-C", out / "node", "init", "--chain", "dev", "--rpc-port", a.rpc_port, "--p2p-port",
             a.p2p_port, "--genesis-message", "noir-ckb-private-tally-v2-local-only", "--ba-arg", arg])
        spec = out / "node/specs/dev.toml"
        spec.write_text(spec.read_text().replace("[params]", "".join(
            f'[[genesis.issued_cells]]\ncapacity = 100_000_000_00000000\nlock.code_hash = "{c.OWNER_CODE}"\n'
            f'lock.args = "{arg}"\nlock.hash_type = "type"\n\n' for _ in range(3)) + "[params]"))
        config = out / "node/ckb.toml"
        config.write_text(config.read_text().replace("/ip4/0.0.0.0/tcp/", "/ip4/127.0.0.1/tcp/")
                          .replace("max_outbound_peers = 8", "max_outbound_peers = 0")
                          .replace("discovery_local_address = true", "discovery_local_address = false")
                          .replace('"Debug", "Terminal"]', '"Debug", "Terminal", "IntegrationTest", "Indexer"]'))
        with (out / "node.log").open("w") as log:
            node = subprocess.Popen([str(a.ckb.resolve()), "-C", str(out / "node"), "run"], stdout=log, stderr=subprocess.STDOUT)
        for _ in range(40):
            c.require(node.poll() is None, "node failed; inspect node.log")
            try:
                genesis = c.rpc(url, "get_block_hash", ["0x0"])
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("node RPC did not start")
        manifest["genesis"] = genesis
        run(["python3", "-B", c.ROOT / "scripts/owned_counter.py", "preflight", "--rpc", url, "--genesis", genesis,
             "--out", out / "policy.json"])
        g = c.rpc(url, "get_block_by_number", ["0x0"])["transactions"][0]
        funding = [f"{g['hash']}:{hex(i)}" for i, o in enumerate(g["outputs"]) if o["lock"]["args"] == arg]
        c.require(len(funding) >= 3, "expected three issued funding Cells")

        stage("development setup")
        if a.setup:
            setup = a.setup.resolve()
            manifest["setup"] = f"reused {setup}"
        else:
            setup = out / "setup"
            run(["python3", "-B", c.ROOT / "scripts/setup-private-tally.py", "--out", setup, "--backend", a.backend.resolve()])
            manifest["setup"] = "fresh"

        stage("Type Script build")
        client("build", "--policy", out / "policy.json", "--setup", setup, "--out", out / "build")
        release = out / "build/release.json"

        stage("deployment")
        client("prepare-deploy", "--release", release, "--rpc", url, "--owner", arg, "--funding", funding[0], "--out", out / "deploy.json")
        deployed = sign_send(out / "deploy.json")
        client("confirm-deploy", "--release", release, "--rpc", url, "--tx", out / "deploy.json", "--hash", deployed,
               "--out", out / "deployment.json")
        manifest["deployment"] = deployed

        work = out / "tally"
        stage("create at 0")
        client("create", "--release", release, "--deployment", out / "deployment.json", "--work", work, "--rpc", url,
               "--owner", arg, "--funding", funding[1])
        h = sign_send(work / "public/creation.json", work)
        client("confirm", "--work", work, "--hash", h)
        manifest["creation"] = h

        stage("update +7")
        client("update", "--work", work, "--funding", f"{h}:0x1", "--delta", "7")
        h = sign_send(work / "public/update-1.json", work)
        client("confirm", "--work", work, "--hash", h)
        manifest["update-1"] = h

        stage("cover update +0")
        client("update", "--work", work, "--funding", f"{h}:0x1", "--delta", "0")
        h = sign_send(work / "public/update-2.json", work)
        client("confirm", "--work", work, "--hash", h)
        manifest["update-2-cover"] = h

        stage("status, backup and leak scan")
        status = json.loads(client("status", "--work", work, "--show-value"))
        c.require(status["value"] == 7 and status["state_version"] == 3 and not status["pending"], f"unexpected final state {status}")
        client("backup", "--work", work, "--to", out / "private/tally-backup")
        on_chain = c.live(url, status["tally"])
        c.require(c.raw(on_chain["data"]["content"]) == pt.tally_data(int(status["commitment"], 16)), "chain and state differ")
        secrets_used = set()
        for path in (work / "private").glob("state-*.json"):
            s = json.loads(path.read_text())
            secrets_used |= {int(s["key"]), int(s["blinding"])}
        leaks = pt.leak_scan(out, secrets_used, exclude=[out / "private", work / "private", out / "build/target", out / "node", out / "setup/backend-target"])
        c.require(not leaks, f"secret material found in {leaks}")
        manifest.update(final_value_matches=True, state_versions=3, leak_scan="clean", release_sha256=c.sha(release))
        if a.full:
            stage("49-case CKB-VM matrix")
            run(["python3", "-B", c.ROOT / "scripts/check-private-tally.py", "--setup", setup, "--out", out / "matrix"])
            summary = c.read(out / "matrix/summary.json")
            c.require(summary["status"] == "passed", "CKB-VM matrix failed")
            stage("mutation tests")
            run(["python3", "-B", c.ROOT / "scripts/mutate-private-tally.py", "--setup", setup, "--baseline", out / "matrix",
                 "--out", out / "mutations"])
            mutations = c.read(out / "mutations/manifest.json")
            c.require(all(m["detected"] for m in mutations), "a mutation did not behave as required")
            manifest.update(matrix_cases=summary["cases"], mutations_as_required=len(mutations))
        manifest["status"] = "local-validated" if a.full else "local-lifecycle-validated"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)[-3000:]
        raise
    finally:
        if node is not None:
            node.terminate()
            try:
                node.wait(timeout=15)
            except subprocess.TimeoutExpired:
                node.kill()
                node.wait()
        save()
    print(out / "manifest.json")


if __name__ == "__main__":
    main()
