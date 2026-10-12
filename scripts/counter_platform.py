"""Host detection, pinned tool lookup and safe single-executable extraction.

All platform and tool pins come from toolchains/platforms.json. Nothing here
downloads, installs, signs or broadcasts; callers decide when to fetch.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import platform as _platform
import shutil
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "toolchains/platforms.json"
TOOL_NAMES = ("ckb", "ckb-cli", "nargo")
BREW_CLANG = (Path("/opt/homebrew/opt/llvm@18/bin/clang"), Path("/usr/local/opt/llvm@18/bin/clang"))
LINUX_CLANG = Path("/usr/lib/llvm-18/bin/clang")


class PlatformError(ValueError):
    """An unsupported host, missing pin or integrity failure."""


def load(path=METADATA):
    data = json.loads(Path(path).read_text())
    if data.get("schema") != "noir-ckb/counter-platforms/v1":
        raise PlatformError("unexpected platform metadata schema")
    return data


def detect(data=None, system=None, machine=None):
    """Return (key, entry) for this host, or raise PlatformError naming the host."""
    data = data or load()
    system = system or _platform.system()
    machine = (machine or _platform.machine()).lower()
    for key, entry in data["platforms"].items():
        if entry["match"]["system"] == system and machine in entry["match"]["machine"]:
            return key, entry
    supported = ", ".join(sorted(data["platforms"]))
    raise PlatformError(f"No pinned tools for {system}/{machine}. Pinned platforms: {supported}.")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tool_candidates(tools_dir, key, entry, name):
    """New layout first (<tools>/<platform>/<name>), then the Week 15 archive layout."""
    pin = entry["tools"][name]
    return [Path(tools_dir) / key / name, Path(tools_dir) / pin["member"]]


def find_tool(tools_dir, key, entry, name):
    """Return the first candidate whose bytes match the pin, else None."""
    pin = entry["tools"][name]
    for path in tool_candidates(tools_dir, key, entry, name):
        if path.is_file() and os.access(path, os.X_OK) and sha256_file(path) == pin["binary_sha256"]:
            return path
    return None


def extract_member(archive_bytes, archive_name, member):
    """Read exactly one regular-file member; reject links, devices and odd paths.

    Only the named executable is ever written by callers, so unrelated archive
    members (and their stored permissions) are never extracted.
    """
    parts = Path(member).parts
    if Path(member).is_absolute() or ".." in parts or not parts:
        raise PlatformError(f"unsafe pinned member path: {member}")
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            try:
                info = archive.getinfo(member)
            except KeyError:
                raise PlatformError(f"{archive_name}: missing member {member}") from None
            mode = (info.external_attr >> 16) & 0o170000
            if info.is_dir() or (mode and mode != 0o100000):
                raise PlatformError(f"{archive_name}: {member} is not a regular file")
            return archive.read(info)
    if archive_name.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            try:
                info = archive.getmember(member)
            except KeyError:
                raise PlatformError(f"{archive_name}: missing member {member}") from None
            if not info.isreg():
                raise PlatformError(f"{archive_name}: {member} is not a regular file")
            return archive.extractfile(info).read()
    raise PlatformError(f"unsupported archive format: {archive_name}")


def install_tool(archive_bytes, pin, destination):
    """Verify archive and executable digests, then write the executable as 0755."""
    archive_name = pin["url"].rsplit("/", 1)[-1]
    if sha256_bytes(archive_bytes) != pin["archive_sha256"]:
        raise PlatformError(f"{archive_name}: archive digest mismatch; nothing installed")
    binary = extract_member(archive_bytes, archive_name, pin["member"])
    if sha256_bytes(binary) != pin["binary_sha256"]:
        raise PlatformError(f"{archive_name}: executable digest mismatch; nothing installed")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise PlatformError(f"{destination} already exists; choose a new tools directory")
    temporary = destination.with_name(destination.name + ".partial")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.rename(destination)
    return destination


def clang_major(compiler, env=None):
    try:
        result = subprocess.run([str(compiler), "--version"], capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for token in (result.stdout + result.stderr).split():
        head = token.split(".")[0]
        if "." in token and head.isdigit():
            return int(head)
    return None


def find_clang(env):
    """Explicit CLANG/CC_riscv64 wins; then clang-18 on PATH; then known LLVM 18 prefixes."""
    explicit = env.get("CC_riscv64imac_unknown_none_elf") or env.get("CLANG")
    if explicit:
        return explicit
    on_path = shutil.which("clang-18", path=env.get("PATH"))
    if on_path:
        return on_path
    for candidate in (LINUX_CLANG,) + BREW_CLANG:
        if candidate.is_file():
            return str(candidate)
    return None


def tool_environment(env, tools_dir, key, entry):
    """Copy env, export the riscv C compiler and prefer a pinned nargo from tools_dir."""
    env = dict(env)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    compiler = find_clang(env)
    if compiler:
        env["CLANG"] = compiler
        env["CC_riscv64imac_unknown_none_elf"] = compiler
    nargo = find_tool(tools_dir, key, entry, "nargo")
    if nargo:
        env["PATH"] = str(nargo.parent) + os.pathsep + env.get("PATH", "")
    return env


def cargo_home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("CARGO_HOME") or Path.home() / ".cargo")


def rustup_home(env=None):
    env = os.environ if env is None else env
    return Path(env.get("RUSTUP_HOME") or Path.home() / ".rustup")
