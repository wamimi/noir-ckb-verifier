#!/usr/bin/env python3
"""Guided source-checkout entry point for the fixed public counter preview."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import shlex
import socket
import subprocess
import sys

import counter_platform as cp

ROOT = Path(__file__).resolve().parents[1]
BACKEND_REV = cp.load()["versions"]["backend_revision"]


def host():
    """(key, entry) for this host, or (None, None) when no pins exist."""
    try:
        return cp.detect()
    except cp.PlatformError:
        return None, None


def environment(tools=None):
    key, entry = host()
    if key is None:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env
    return cp.tool_environment(os.environ, tools or ROOT / "target/counter-tools", key, entry)


def probe(cmd, env, cwd=ROOT, expected=0, contains=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=120)
        output = result.stdout + result.stderr
        return result.returncode == expected and (contains is None or contains in output)
    except (OSError, subprocess.TimeoutExpired):
        return False


def doctor(args, env):
    """Check pinned prerequisites without installing or changing configuration."""
    failures = []

    def check(label, ok, remedy):
        print(f"{'OK' if ok else 'MISSING'}: {label}", flush=True)
        if not ok:
            failures.append(label)
            print(f"  {remedy}", flush=True)

    key, entry = host()
    check(f"pinned host platform ({key or platform.system() + '/' + platform.machine()})", key is not None,
          "No pinned tools for this host. Supported: macOS ARM64, Ubuntu 24.04 x86_64/ARM64 (Linux pending validation). "
          "Recorded inspection works anywhere.")
    if key is not None and entry["status"] != "validated":
        print(f"NOTE: {key} is {entry['status']}: {entry['status_detail']}", flush=True)
    check("Python >=3.9", sys.version_info >= (3, 9), "Install Python 3.9 or newer.")
    check("pinned clean backend", probe(["git", "rev-parse", "HEAD"], env, args.backend, contains=BACKEND_REV)
          and probe(["git", "diff", "--quiet", "HEAD"], env, args.backend)
          and clean_backend(args.backend, env),
          f"Clone the backend and check out {BACKEND_REV}; see docs/owned-counter-bootstrap.md.")
    check("Nargo beta.18 and compiler pin", probe(["nargo", "--version"], env, contains="1.0.0-beta.18")
          and probe(["nargo", "--version"], env, contains="99bb8b5cf33d7669adbdef096b12d80f30b4c0c9"),
          "Run: python3 scripts/fetch-counter-tools.py (pinned nargo), or: noirup --version 1.0.0-beta.18")
    check("Node.js", probe(["node", "--version"], env), "Install Node.js/npm.")
    check("cached snarkjs 0.7.5", probe(["npx", "--offline", "snarkjs@0.7.5", "--version"], env,
                                      expected=99, contains="snarkjs@0.7.5"),
          "Run: npm exec --yes --package=snarkjs@0.7.5 -- node -e 'console.log(1)'")
    compiler = env.get("CC_riscv64imac_unknown_none_elf")
    check("LLVM 18 target compiler", bool(compiler) and cp.clang_major(compiler, env) == 18,
          (entry["clang_hint"] if entry else "Install clang 18") + "; or export CLANG. See docs/owned-counter-bootstrap.md.")
    # Query rustup's list instead of running `rustc +x`, which can trigger an automatic toolchain download.
    installed = {version: installed_toolchain(version, env) for version in ("1.95.0", "1.94.1")}
    for version, ok in installed.items():
        check(f"Rust {version}", ok, f"Run: rustup toolchain install {version} --profile minimal")
    check("CKB RISC-V target", installed["1.94.1"] and probe(["rustup", "target", "list", "--installed", "--toolchain", "1.94.1"],
                                                            env, contains="riscv64imac-unknown-none-elf"),
          "Run: rustup target add --toolchain 1.94.1 riscv64imac-unknown-none-elf")
    for version, manifest in (("1.95.0", ROOT / "Cargo.toml"),
                              ("1.94.1", ROOT / "contracts/Cargo.toml"),
                              ("1.95.0", args.backend / "Cargo.toml")):
        check(f"offline dependencies: {manifest.parent.name}",
              installed[version] and probe(["cargo", f"+{version}", "metadata", "--locked", "--offline", "--format-version", "1",
                                            "--manifest-path", str(manifest)], env),
              f"Run: cargo +{version} fetch --locked --manifest-path {shlex.quote(str(manifest))}")
    for name in ("ckb", "ckb-cli"):
        ok = key is not None and cp.find_tool(args.tools, key, entry, name) is not None
        check(f"{name} pinned executable", ok,
              f"Run: python3 scripts/fetch-counter-tools.py --out {shlex.quote(str(args.tools))} (lists URLs and asks first).")
    print("Prerequisite checks passed." if not failures else
          f"Fix {len(failures)} prerequisite check(s), then rerun doctor. Full guide: docs/owned-counter-bootstrap.md.", flush=True)
    return not failures


def installed_toolchain(version, env):
    try:
        result = subprocess.run(["rustup", "toolchain", "list"], env=env, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and any(line.split()[0].startswith(version + "-")
                                          for line in result.stdout.splitlines() if line.strip())


def clean_backend(path, env):
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=path, env=env,
                                capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and not result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_script(name, args, env):
    return subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / name), *map(str, args)],
                          cwd=ROOT, env=env).returncode


def validate_local(args):
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / "target").resolve()) or out == (ROOT / "target").resolve():
        raise ValueError("Output must be a new directory below this checkout's target/.")
    if out.exists():
        raise ValueError("Output already exists. Choose a new --out directory; do not overwrite a previous run.")
    if args.rpc_port == args.p2p_port:
        raise ValueError("RPC and P2P ports must be different.")
    for port in (args.rpc_port, args.p2p_port):
        if not 1024 <= port <= 65535:
            raise ValueError("Choose ports from 1024 through 65535.")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("inspect", "live", "doctor", "quick", "local"),
                        help="quick: fresh proof + signed local lifecycle; local: quick plus 48 VM cases, range checks and 3 mutations")
    parser.add_argument("--rpc", default="https://testnet.ckb.dev", help="Read-only live inspection endpoint")
    parser.add_argument("--backend", type=Path, default=Path(os.environ.get("COUNTER_BACKEND", ROOT.parent / "Noir-Groth16")))
    parser.add_argument("--tools", type=Path, default=ROOT / "target/counter-tools")
    parser.add_argument("--out", type=Path, default=ROOT / "target" / ("counter-local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    parser.add_argument("--rpc-port", type=int, default=18124)
    parser.add_argument("--p2p-port", type=int, default=18125)
    parser.add_argument("--yes", action="store_true", help="Run local reproduction without an interactive prompt")
    args = parser.parse_args(argv)
    args.backend = args.backend.resolve()
    args.tools = args.tools.resolve()
    args.out = args.out.resolve()
    print("Public fixed counter · development setup · no arbitrary circuits · no application withdrawal", flush=True)
    if args.mode is None:
        if not sys.stdin.isatty():
            parser.error("Choose inspect, live, doctor or local in a non-interactive terminal.")
        print("1. Inspect recorded evidence (offline; no wallet)\n2. Check existing testnet transactions (read-only)\n"
              "3. Quick local run: fresh proof and signed local transactions (no wallet, no funds)\n"
              "4. Full local validation: quick run plus 48 VM cases, range checks and 3 mutations\n5. Check local prerequisites")
        choice = input("Choose 1–5: ").strip()
        if choice not in ("1", "2", "3", "4", "5"):
            parser.error("Choose 1, 2, 3, 4 or 5.")
        args.mode = {"1": "inspect", "2": "live", "3": "quick", "4": "local", "5": "doctor"}[choice]
    env = environment(args.tools)
    if args.mode in ("inspect", "live"):
        print("This checks evidence integrity/transaction contents. Cryptographic proof verification is a separate step in the reviewer guide.", flush=True)
        return run_script("review-counter.py", ["--rpc", args.rpc] if args.mode == "live" else [], env)
    if not doctor(args, env):
        return 1
    if args.mode == "doctor":
        return 0
    validate_local(args)
    quick = args.mode == "quick"
    scope = ("fresh development setup and proof, contract build, signed local deployment/creation/update with pre-signing proof check. "
             "Adversarial VM matrix, range checks and mutations are NOT run in this mode; use 'local' for those."
             if quick else "the quick lifecycle plus 48 VM cases, range checks and three contract mutations")
    print(f"Fresh run: {args.out}\nCreates a disposable local account and chain. Runs {scope} No public deployment. Builds/proofs can take time.\nStage 1/3: prerequisites passed. Stage 2/3: local lifecycle.", flush=True)
    if not args.yes:
        if not sys.stdin.isatty():
            parser.error("Local execution needs --yes in a non-interactive terminal.")
        if input("Start this local run? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Local run cancelled.")
            return 0
    key, entry = host()
    if key is None:
        raise ValueError("No pinned tools for this host; local execution is unavailable here.")
    runner = ["--out", args.out, "--backend", args.backend,
              "--ckb", cp.find_tool(args.tools, key, entry, "ckb"), "--ckb-cli", cp.find_tool(args.tools, key, entry, "ckb-cli"),
              "--rpc-port", args.rpc_port, "--p2p-port", args.p2p_port]
    code = run_script("local-owned-counter.py", runner + (["--quick"] if quick else ["--mutations"]), env)
    if code:
        print(f"Local run failed. Inspect {args.out}/commands.json and manifest.json; do not share wallet/private directories.")
    else:
        print(f"Stage 3/3: local runner completed. Result: {args.out}/manifest.json\nShare your source revision, platform, outcome and sanitized errors through the Owned counter v1 preview review issue template. Never upload the whole run directory.")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, EOFError) as error:
        sys.exit(f"error: {error}")
    except KeyboardInterrupt:
        sys.exit("Interrupted. Inspect any existing run before starting again.")
