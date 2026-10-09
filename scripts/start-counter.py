#!/usr/bin/env python3
"""Guided source-checkout entry point for the fixed public counter preview."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import platform
import shlex
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_REV = "828025f3a0090e2934940956c0f5dc8093eb5532"
TOOLS = (
    ("ckb_v0.210.0_aarch64-apple-darwin-portable/ckb", "800d625b4baaa55cf6408b2f30ad744c4df90d52b94023ce226be875327c9493"),
    ("ckb-cli_v2.0.0_aarch64-apple-darwin/ckb-cli", "994166d983955fb59b6bab172485b3f65ff60487493b62a6569ad93eaa7adffb"),
)


def environment():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    compiler = env.get("CC_riscv64imac_unknown_none_elf") or env.get("CLANG")
    default = Path("/opt/homebrew/opt/llvm@18/bin/clang")
    if not compiler and default.is_file():
        compiler = str(default)
    if compiler:
        env["CLANG"] = compiler
        env["CC_riscv64imac_unknown_none_elf"] = compiler
    return env


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

    check("supported local host", (platform.system(), platform.machine()) == ("Darwin", "arm64"),
          "Local reproduction is tested on macOS ARM64. Recorded inspection is available separately.")
    check("Python >=3.9", sys.version_info >= (3, 9), "Install Python 3.9 or newer.")
    check("pinned clean backend", probe(["git", "rev-parse", "HEAD"], env, args.backend, contains=BACKEND_REV)
          and probe(["git", "diff", "--quiet", "HEAD"], env, args.backend)
          and clean_backend(args.backend, env),
          f"Clone the backend and check out {BACKEND_REV}; see docs/owned-counter-bootstrap.md.")
    check("Nargo beta.18 and compiler pin", probe(["nargo", "--version"], env, contains="1.0.0-beta.18")
          and probe(["nargo", "--version"], env, contains="99bb8b5cf33d7669adbdef096b12d80f30b4c0c9"),
          "Install with: noirup --version 1.0.0-beta.18")
    check("Node.js", probe(["node", "--version"], env), "Install Node.js/npm.")
    check("cached snarkjs 0.7.5", probe(["npx", "--offline", "snarkjs@0.7.5", "--version"], env,
                                      expected=99, contains="snarkjs@0.7.5"),
          "Run: npm exec --yes --package=snarkjs@0.7.5 -- node -e 'console.log(1)'")
    compiler = env.get("CC_riscv64imac_unknown_none_elf", "clang")
    check("LLVM 18 target compiler", probe([compiler, "--version"], env, contains="clang version 18."),
          "Install brew llvm@18 and export CLANG and CC_riscv64imac_unknown_none_elf; see bootstrap.")
    for version in ("1.95.0", "1.94.1"):
        check(f"Rust {version}", probe(["rustc", f"+{version}", "--version"], env, contains=version),
              f"Run: rustup toolchain install {version} --profile minimal")
    check("CKB RISC-V target", probe(["rustup", "target", "list", "--installed", "--toolchain", "1.94.1"],
                                     env, contains="riscv64imac-unknown-none-elf"),
          "Run: rustup target add --toolchain 1.94.1 riscv64imac-unknown-none-elf")
    for version, manifest in (("1.95.0", ROOT / "Cargo.toml"),
                              ("1.94.1", ROOT / "contracts/Cargo.toml"),
                              ("1.95.0", args.backend / "Cargo.toml")):
        check(f"offline dependencies: {manifest.parent.name}",
              probe(["cargo", f"+{version}", "metadata", "--locked", "--offline", "--format-version", "1",
                     "--manifest-path", str(manifest)], env),
              f"Run: cargo +{version} fetch --locked --manifest-path {shlex.quote(str(manifest))}")
    for relative, digest in TOOLS:
        binary = args.tools / relative
        ok = binary.is_file() and os.access(binary, os.X_OK) and hashlib.sha256(binary.read_bytes()).hexdigest() == digest
        check(relative.split("/")[-1] + " pinned executable", ok,
              f"Run: python3 scripts/fetch-counter-tools.py --out {shlex.quote(str(args.tools))}; use a new directory if it exists.")
    print("Prerequisite checks passed." if not failures else
          f"Fix {len(failures)} prerequisite check(s), then rerun doctor. Full guide: docs/owned-counter-bootstrap.md.", flush=True)
    return not failures


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
    parser.add_argument("mode", nargs="?", choices=("inspect", "live", "doctor", "local"))
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
        print("1. Inspect recorded evidence (offline; no wallet)\n2. Check existing testnet transactions (read-only)\n3. Reproduce locally (macOS ARM64)\n4. Check local prerequisites")
        choice = input("Choose 1–4: ").strip()
        if choice not in ("1", "2", "3", "4"):
            parser.error("Choose 1, 2, 3 or 4.")
        args.mode = {"1": "inspect", "2": "live", "3": "local", "4": "doctor"}[choice]
    env = environment()
    if args.mode in ("inspect", "live"):
        print("This checks evidence integrity/transaction contents. Cryptographic proof verification is a separate step in the reviewer guide.", flush=True)
        return run_script("review-counter.py", ["--rpc", args.rpc] if args.mode == "live" else [], env)
    if not doctor(args, env):
        return 1
    if args.mode == "doctor":
        return 0
    validate_local(args)
    print(f"Fresh run: {args.out}\nCreates a disposable local account and chain, generates a development proof, runs 48 VM cases and three mutations, and checks signed local transactions. No public deployment. Builds/proofs can take time.\nStage 1/3: prerequisites passed. Stage 2/3: local lifecycle.", flush=True)
    if not args.yes:
        if not sys.stdin.isatty():
            parser.error("Local execution needs --yes in a non-interactive terminal.")
        if input("Start this local run? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Local run cancelled.")
            return 0
    code = run_script("local-owned-counter.py", ["--out", args.out, "--backend", args.backend,
                      "--ckb", args.tools / TOOLS[0][0], "--ckb-cli", args.tools / TOOLS[1][0],
                      "--rpc-port", args.rpc_port, "--p2p-port", args.p2p_port, "--mutations"], env)
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
