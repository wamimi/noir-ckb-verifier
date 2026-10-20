#!/usr/bin/env python3
"""Coordinator tool for the private tally v2 phase 2 ceremony (docs/setup-ceremony.md).

  open      freeze check, initial key tally_0000.zkey, transcript and README
  issue     print the GitHub issue text for the next contributor
  accept    verify a returned key and record the contribution
  finalize  apply the announced CKB block hash as beacon, verify, export the key
  check     re-verify the recorded transcript (anyone can run this)

Every key is checked with `snarkjs zkey verify` against the frozen R1CS and the
pinned phase 1 file before it is recorded. Nothing secret is handled here: the
coordinator never sees a contributor's randomness.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import owned_counter as c  # noqa: E402
import private_tally as pt  # noqa: E402

spec = importlib.util.spec_from_file_location("setup", HERE / "setup-private-tally.py")
setup_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_mod)

ROOT = pt.ROOT
DIR = ROOT / "ceremony/private-tally-v2"
SNARK = ["npx", "--offline", "snarkjs@0.7.5"]
RAW = "https://raw.githubusercontent.com/wamimi/noir-ckb-verifier/main/ceremony/private-tally-v2/zkeys"
BEACON_ITERATIONS = 10
DRY_RUN = False
PTAU = ROOT / "target/ppot_0080_12.ptau"  # local copy; never recorded (paths are machine-specific)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def snark(*args, timeout=3600):
    q = subprocess.run(SNARK + [str(a) for a in args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    out = re.sub(r"\x1b\[[0-9;]*m", "", q.stdout + q.stderr)
    return q.returncode, out


def contributions(verify_output):
    """[(index, name, hash)] from `zkey verify` output, oldest first."""
    lines = [l for l in verify_output.splitlines() if l.strip()]
    found = []
    for i, line in enumerate(lines):
        m = re.search(r"contribution #(\d+) (.*):\s*$", line)
        if m:
            words = " ".join(lines[i + 1:i + 5]).split()
            found.append((int(m.group(1)), m.group(2), "".join(words)))
    return sorted(found)


def norm(h):
    h = h.strip().lower()
    h = h[2:] if h.startswith("0x") else h
    return re.sub(r"[^0-9a-f]", "", h)


def transcript():
    return c.read(DIR / "transcript.json")


def save(t):
    (DIR / "transcript.json").write_text(json.dumps(t, indent=2) + "\n")
    rows = "\n".join(
        f"| {k['index']} | {k['name']} | `{k['input_sha256'][:16]}…` | `{k['hash'][:16]}…` | "
        f"{('[link](' + k['attestation'] + ')') if k.get('attestation') else '—'} | `{k['zkey']}` |"
        for k in t["contributions"])
    final = t.get("final")
    status = ("**Complete.** Final key `tally_final.zkey` (SHA-256 `" + final["zkey_sha256"] + "`), verification key "
              "`verification_key.json` (SHA-256 `" + final["vk_sha256"] + "`).") if final else (
        "**Open.** Contributions are made one at a time; see the [contributor guide](../../docs/setup-ceremony.md).")
    beacon = t["beacon"]
    beacon_line = (f"CKB mainnet block **{beacon['height']}**, announced before the first contribution. "
                   f"Applied with `snarkjs zkey beacon … <block hash> {BEACON_ITERATIONS}`.")
    if final:
        beacon_line += f" Block hash: `{final['beacon_hash']}`."
    (DIR / "README.md").write_text(f"""# Private tally v2 setup ceremony

{status}

Every key below was checked with `snarkjs zkey verify` against the frozen
circuit and the phase 1 file before it was accepted. Anyone can repeat the whole
check: `python3 -B scripts/ceremony-private-tally.py check` (or the manual
commands in the [contributor guide](../../docs/setup-ceremony.md#verifying-the-ceremony-yourself)).

| Item | Value |
| --- | --- |
| Circuit | `circuits/private-tally-v2` at commit `{t['freeze_commit']}` |
| R1CS | `circuit.r1cs`, SHA-256 `{t['r1cs_sha256']}`, {t['constraints']} constraints |
| Phase 1 | `{t['ptau']['file']}` from [PSE Perpetual Powers of Tau]({t['ptau']['source']}), BLAKE2b-512 `{t['ptau']['blake2b']}` (not stored here) |
| Initial key | `zkeys/tally_0000.zkey`, SHA-256 `{t['initial_zkey_sha256']}` |
| Tool | snarkjs 0.7.5 |
| Beacon | {beacon_line} |

## Contributions

| # | Contributor | Input key SHA-256 | Contribution hash | Attestation | Key |
| --- | --- | --- | --- | --- | --- |
{rows if rows else '| — | (none yet) | | | | |'}

This is a public ceremony for a testnet developer preview, not an audited
production ceremony. It guarantees that nobody can forge private tally proofs as
long as at least one contributor's randomness was discarded.
""")


def latest_zkey(t):
    return DIR / "zkeys" / (t["contributions"][-1]["zkey"] if t["contributions"] else "tally_0000.zkey")


def verify(zkey, t):
    c.require(PTAU.is_file(), f"phase 1 file not found at {PTAU}; pass --ptau")
    code, out = snark("zkey", "verify", DIR / "circuit.r1cs", PTAU, zkey)
    c.require(code == 0 and "ZKey Ok!" in out, f"zkey verify FAILED for {zkey}:\n{out[-1500:]}")
    return out


def cmd_open(a):
    c.require(not DIR.exists(), f"{DIR} already exists")
    setup = a.setup.resolve()
    m = c.read(setup / "manifest.json")
    c.require(m.get("status") == "passed" and m.get("profile") == pt.PROFILE, "setup did not pass")
    c.require(sha(setup / "circuit.r1cs") == m["r1cs_sha256"], "setup R1CS changed")
    ptau = PTAU
    digest = setup_mod.blake2b(ptau)
    c.require(digest in setup_mod.PSE_PPOT.values(), "phase 1 file is not the pinned PSE ppot file")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not DRY_RUN:
        status = subprocess.run(["git", "status", "--porcelain", "circuits/private-tally-v2"], cwd=ROOT, capture_output=True, text=True).stdout
        c.require(not status.strip(), "circuit sources have uncommitted changes; commit and tag them first")
        tagged = subprocess.run(["git", "rev-parse", "private-tally-v2-circuit-freeze^{commit}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        c.require(tagged == head, "tag private-tally-v2-circuit-freeze must point at the current commit")
    # The setup's compiled program must equal what the committed sources compile to.
    private = pt.PrivateDir(Path(a.scratch).resolve() if a.scratch else ROOT / "target/ceremony-open-check", create=True)
    try:
        circuit = pt.Circuit(private, a.nargo)
        mine = c.read(circuit.compile())
    finally:
        shutil.rmtree(private.path, ignore_errors=True)
    theirs = c.read(setup / "circuit/private_tally_v2.json")
    c.require(mine["bytecode"] == theirs["bytecode"] and mine["abi"] == theirs["abi"], "setup was made for a different circuit")
    (DIR / "zkeys").mkdir(parents=True)
    shutil.copyfile(setup / "circuit.r1cs", DIR / "circuit.r1cs")
    t = dict(profile=pt.PROFILE, freeze_commit=head, r1cs_sha256=sha(DIR / "circuit.r1cs"), constraints=m["constraints"],
             ptau=dict(file=ptau.name, blake2b=digest,
                       source="https://github.com/privacy-ethereum/perpetualpowersoftau#prepared-and-truncated-files"),
             beacon=dict(network="CKB mainnet", height=a.beacon_height), contributions=[])
    code, out = snark("groth16", "setup", DIR / "circuit.r1cs", ptau, DIR / "zkeys/tally_0000.zkey")
    c.require(code == 0, out[-1500:])
    verify(DIR / "zkeys/tally_0000.zkey", t)
    t["initial_zkey_sha256"] = sha(DIR / "zkeys/tally_0000.zkey")
    save(t)
    if DRY_RUN:
        print(f"Opened a practice ceremony in {DIR} (nothing to commit or announce).")
    else:
        print(f"Opened. Commit and push ceremony/private-tally-v2/, then announce the beacon height {a.beacon_height}.")


def cmd_issue(a):
    t = transcript()
    c.require("final" not in t, "ceremony already finalized")
    n = len(t["contributions"]) + 1
    src = latest_zkey(t)
    guide = "https://github.com/wamimi/noir-ckb-verifier/blob/main/docs/setup-ceremony.md#contributing-about-1015-minutes"
    print(f"""TITLE (paste into the issue title):

Contribution {n}: {a.name}

BODY (paste everything between the two lines into the issue body):
----------------------------------------------------------------------
Thank you for contributing! Follow the guide step by step: {guide}

**Paste these three lines first:**

```bash
export IN={src.name}
export OUT=tally_{n:04d}.zkey
export URL={RAW}/{src.name}
```

**SHA-256 of the input** (step 2 must print exactly this):

```
{sha(src)}
```

Contribute with `--name="{a.name}"`. Within 48 hours, reply here with your zipped
output (`tally_{n:04d}.zip`) and your four-line contribution hash.
----------------------------------------------------------------------""")


def cmd_accept(a):
    t = transcript()
    c.require("final" not in t, "ceremony already finalized")
    n = len(t["contributions"]) + 1
    src = latest_zkey(t)
    out = verify(a.zkey.resolve(), t)
    found = contributions(out)
    c.require(len(found) == n, f"expected {n} contributions in the key, found {len(found)}")
    for k, (index, name, h) in zip(t["contributions"], found):
        c.require(k["name"] == name and k["hash"] == h, f"earlier contribution {index} changed; reject this key")
    if a.rpc:
        tip = int(c.rpc(a.rpc, "get_tip_block_number", []), 16)
        c.require(tip < t["beacon"]["height"], f"CKB mainnet is at block {tip}, at or past the beacon height "
                  f"{t['beacon']['height']}: no contribution may be accepted once the beacon is known")
    elif not DRY_RUN:
        raise ValueError("pass --rpc https://mainnet.ckb.dev/rpc so the tool can confirm the beacon block does not exist yet")
    index, name, h = found[-1]
    c.require(name == a.name, f"last contribution is named {name!r}, expected {a.name!r}")
    c.require(norm(a.hash) == h, "the contribution hash the contributor posted does not match the key")
    dest = DIR / "zkeys" / f"tally_{n:04d}.zkey"
    shutil.copyfile(a.zkey, dest)
    t["contributions"].append(dict(index=n, name=name, hash=h, input_sha256=sha(src), zkey=dest.name,
                                   zkey_sha256=sha(dest), attestation=a.attestation))
    save(t)
    print(f"Accepted contribution {n} from {name}." + ("" if DRY_RUN else f" Commit and push {dest.relative_to(ROOT)} and "
          "the transcript, then close the issue and open the next one."))


def cmd_finalize(a):
    t = transcript()
    c.require("final" not in t, "already finalized")
    c.require(len(t["contributions"]) >= 3, "at least three contributions are required before finalizing")
    beacon = norm(a.beacon_hash)
    c.require(len(beacon) == 64, "beacon must be a 32-byte block hash")
    if a.rpc:
        got = c.rpc(a.rpc, "get_block_hash", [hex(t["beacon"]["height"])])
        c.require(norm(got) == beacon, f"block {t['beacon']['height']} hash on {a.rpc} is {got}")
    final = DIR / "zkeys/tally_final.zkey"
    code, out = snark("zkey", "beacon", latest_zkey(t), final, beacon, BEACON_ITERATIONS,
                      f"-n=CKB mainnet block {t['beacon']['height']}")
    c.require(code == 0, out[-1500:])
    log = verify(final, t)
    (DIR / "verify-final.log").write_text(log)
    found = contributions(log)
    c.require(len(found) == len(t["contributions"]) + 1, "final key does not list every contribution plus the beacon")
    code, out = snark("zkey", "export", "verificationkey", final, DIR / "verification_key.json")
    c.require(code == 0, out[-1500:])
    t["final"] = dict(beacon_hash="0x" + beacon, zkey_sha256=sha(final), vk_sha256=sha(DIR / "verification_key.json"))
    save(t)
    print("Finalized." + ("" if DRY_RUN else " Commit and push, then ask every contributor to find their hash in verify-final.log."))


def cmd_check(a):
    t = transcript()
    c.require(setup_mod.blake2b(PTAU) == t["ptau"]["blake2b"], "phase 1 file hash differs")
    c.require(sha(DIR / "circuit.r1cs") == t["r1cs_sha256"], "R1CS differs from the transcript")
    for k in t["contributions"]:
        c.require(sha(DIR / "zkeys" / k["zkey"]) == k["zkey_sha256"], f"{k['zkey']} changed")
    key = DIR / "zkeys/tally_final.zkey" if "final" in t else latest_zkey(t)
    found = contributions(verify(key, t))
    for k, (_, name, h) in zip(t["contributions"], found):
        c.require(k["name"] == name and k["hash"] == h, f"contribution {k['index']} does not match the key")
    print(f"OK: {len(t['contributions'])} contributions verified" + (" plus the beacon" if "final" in t else "") + f" in {key.name}.")


def main():
    global PTAU, DIR, DRY_RUN
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("open")
    s.add_argument("--setup", type=Path, required=True, help="a passed setup-private-tally.py run (source of the R1CS)")
    s.add_argument("--beacon-height", type=int, required=True, help="future CKB mainnet block height")
    s.add_argument("--nargo", default="nargo")
    s.add_argument("--scratch", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_open)
    s = sub.add_parser("issue")
    s.add_argument("--name", required=True)
    s.set_defaults(func=cmd_issue)
    s = sub.add_parser("accept")
    s.add_argument("--zkey", type=Path, required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--hash", required=True, help="the four lines the contributor posted (quotes keep the spaces)")
    s.add_argument("--attestation", help="link to the contributor's own post of the hash")
    s.add_argument("--rpc", help="CKB mainnet RPC; contributions are refused once the beacon block exists")
    s.set_defaults(func=cmd_accept)
    s = sub.add_parser("finalize")
    s.add_argument("--beacon-hash", required=True)
    s.add_argument("--rpc", help="CKB mainnet RPC to cross-check the block hash, e.g. https://mainnet.ckb.dev/rpc")
    s.set_defaults(func=cmd_finalize)
    s = sub.add_parser("check")
    s.set_defaults(func=cmd_check)
    ap.add_argument("--ptau", type=Path, default=PTAU, help="local copy of ppot_0080_12.ptau (default target/)")
    ap.add_argument("--dry-run", action="store_true",
                    help="practice run in target/ceremony-dryrun (no freeze tag needed; nothing to publish)")
    args = ap.parse_args()
    PTAU = args.ptau.resolve()
    if args.dry_run:
        DRY_RUN = True
        DIR = ROOT / "target/ceremony-dryrun"
    try:
        args.func(args)
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
