"""Shared helpers for noir-ckb/private-tally/v2 (docs/private-tally-v2-spec.md).

Secret handling follows section 9 of the specification:
- keys and blinding factors are uniform non-zero BN254 scalars from `secrets`;
  this module has no way to import a user-chosen value;
- secret material lives only in a private directory (mode 0700) as files created
  exclusively with mode 0600; state files are versioned and never overwritten;
- `leak_scan` looks for every secret, in decimal, hex and raw 32-byte little- and
  big-endian form, in files that are kept outside the private directory.
"""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "circuits/private-tally-v2"
PROFILE = "noir-ckb/private-tally/v2"
P = 21888242871839275222246405745257275088548364400416034343698204186575808495617
MAX_DELTA = 2**32 - 1
POSEIDON_COMMIT = "00f879180a56720169cff92a56778d40678d8e26"
PARAMETERS = [("value_old", "private"), ("r_old", "private"), ("key", "private"), ("delta", "private"),
              ("r_new", "private"), ("c_old", "public"), ("c_new", "public"), ("ctx_lo", "public"),
              ("ctx_hi", "public")]
STATE_VERSION = 1
CREATION_WARNING = (
    "WARNING: the key and state in this folder are the only way to update this tally.\n"
    "If they are lost, the tally is frozen permanently and its capacity stays locked.\n"
    "Back the folder up (the `backup` command) and never share it."
)


def new_secret():
    """Uniform random BN254 scalar in [1, P-1]."""
    return secrets.randbelow(P - 1) + 1


class PrivateDir:
    """A 0700 directory holding secret files, each created exclusively with mode 0600."""

    def __init__(self, path, create=False):
        self.path = Path(path)
        if create:
            self.path.mkdir(mode=0o700, parents=False, exist_ok=False)
            os.chmod(self.path, 0o700)
        mode = stat.S_IMODE(self.path.stat().st_mode)
        if mode & 0o077:
            raise PermissionError(f"{self.path} must not be readable by others (mode {oct(mode)})")

    def write_new(self, name, text):
        target = self.path / name
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        return target

    def read(self, name):
        target = self.path / name
        mode = stat.S_IMODE(target.stat().st_mode)
        if mode & 0o077:
            raise PermissionError(f"{target} must have mode 0600 (found {oct(mode)})")
        return target.read_text()


class TallyState:
    """Versioned private state: state-0001.json, state-0002.json, ... never overwritten."""

    PATTERN = re.compile(r"state-(\d{4})\.json$")

    def __init__(self, private):
        self.private = private

    def versions(self):
        found = []
        for p in self.private.path.iterdir():
            m = self.PATTERN.match(p.name)
            if m:
                found.append(int(m.group(1)))
        return sorted(found)

    def latest(self):
        versions = self.versions()
        if not versions:
            raise FileNotFoundError("no tally state in this folder")
        data = json.loads(self.private.read(f"state-{versions[-1]:04d}.json"))
        if data.get("state_version") != STATE_VERSION or data.get("profile") != PROFILE:
            raise ValueError("unsupported tally state file")
        return data

    def append(self, *, key, value, blinding, commitment, label):
        for name, x in (("key", key), ("blinding", blinding), ("commitment", commitment)):
            if not 0 < x < P:
                raise ValueError(f"{name} must be a non-zero field element")
        if not 0 <= value < 2**64:
            raise ValueError("value must fit in 64 bits")
        seq = (self.versions() or [0])[-1] + 1
        record = dict(state_version=STATE_VERSION, profile=PROFILE, seq=seq, label=label,
                      key=str(key), value=str(value), blinding=str(blinding), commitment=str(commitment))
        self.private.write_new(f"state-{seq:04d}.json", json.dumps(record, indent=2) + "\n")
        return record


def backup(private, destination):
    """Copy the private folder to a new location, keeping 0700/0600 permissions."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"{destination} already exists")
    shutil.copytree(private.path, destination, copy_function=shutil.copy2)
    os.chmod(destination, 0o700)
    for p in destination.rglob("*"):
        os.chmod(p, 0o700 if p.is_dir() else 0o600)
    return destination


def secret_patterns(values):
    text, raw = set(), set()
    for v in values:
        if v > 2**40:  # small fixed values (tally counts like 5) are not secrets
            text |= {str(v), format(v, "x"), format(v, "064x")}
            raw |= {v.to_bytes(32, "little"), v.to_bytes(32, "big")}
    return text, raw


def leak_scan(root, values, exclude=()):
    """Return kept files under root (outside `exclude` dirs) that contain a secret in any encoding."""
    text, raw = secret_patterns(values)
    excluded = [Path(e).resolve() for e in exclude]
    hits = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if any(e == resolved or e in resolved.parents for e in excluded):
            continue
        data = path.read_bytes()
        lowered = data.decode("latin-1").lower()
        if any(t in lowered for t in text) or any(r in data for r in raw):
            hits.append(str(path.relative_to(root)))
    return sorted(hits)


class Circuit:
    """Private copy of the Noir workspace; Prover.toml files hold secrets and stay inside it."""

    def __init__(self, private, nargo="nargo"):
        self.ws = private.path / "private-tally-v2"
        shutil.copytree(CIRCUIT, self.ws, ignore=shutil.ignore_patterns("target", "Prover.toml"))
        self.nargo = nargo

    def run(self, *args):
        return subprocess.run([self.nargo, *args], cwd=self.ws, capture_output=True, text=True, timeout=900)

    def compile(self):
        q = self.run("compile", "--workspace")
        if q.returncode:
            raise RuntimeError(f"nargo compile failed:\n{q.stderr[-2000:]}")
        artifact = self.ws / "target/private_tally_v2.json"
        abi = json.loads(artifact.read_text())["abi"]
        found = [(p["name"], p["visibility"]) for p in abi["parameters"]]
        if found != PARAMETERS or abi.get("return_type") is not None:
            raise RuntimeError(f"unexpected circuit ABI: {found}")
        if not all(p["type"] == {"kind": "field"} for p in abi["parameters"]):
            raise RuntimeError("all circuit parameters must be Field")
        return artifact

    def commitment(self, value, blinding, key):
        (self.ws / "commit-helper/Prover.toml").write_text(
            f'value = "{value}"\nblinding = "{blinding}"\nkey = "{key}"\n')
        try:
            q = self.run("execute", "--package", "private_tally_commit_helper")
        finally:
            (self.ws / "commit-helper/Prover.toml").unlink(missing_ok=True)
        m = re.search(r"Circuit output: (0x[0-9a-f]+)", q.stdout + q.stderr)
        if q.returncode or not m:
            raise RuntimeError("commitment helper failed")
        return int(m.group(1), 16)
