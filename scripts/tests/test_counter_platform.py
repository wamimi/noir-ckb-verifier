"""Platform metadata, tool integrity and extraction boundaries (no network)."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import counter_platform as cp  # noqa: E402

spec = importlib.util.spec_from_file_location("fetch_tools", SCRIPTS / "fetch-counter-tools.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def tar_bytes(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "symlink":
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                archive.addfile(info)
            else:
                info.size, info.mode = len(data), 0o777
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def zip_bytes(name, data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


def pin_for(archive, member, binary, url_suffix=".tar.gz"):
    return dict(url="https://example.invalid/tool" + url_suffix, member=member,
                archive_sha256=hashlib.sha256(archive).hexdigest(),
                binary_sha256=hashlib.sha256(binary).hexdigest())


class MetadataTests(unittest.TestCase):
    def test_every_platform_pins_every_tool_with_sha256(self):
        data = cp.load()
        self.assertEqual(set(data["platforms"]), {"darwin-arm64", "linux-x86_64", "linux-arm64"})
        for key, entry in data["platforms"].items():
            self.assertIn(entry["status"], ("validated", "pending-validation"))
            self.assertEqual(set(entry["tools"]), set(cp.TOOL_NAMES), key)
            for pin in entry["tools"].values():
                for field in ("archive_sha256", "binary_sha256"):
                    self.assertRegex(pin[field], r"^[0-9a-f]{64}$")
                self.assertTrue(pin["url"].startswith("https://github.com/"))

    def test_only_darwin_is_marked_validated(self):
        statuses = {k: v["status"] for k, v in cp.load()["platforms"].items()}
        self.assertEqual(statuses["darwin-arm64"], "validated")
        self.assertEqual(statuses["linux-x86_64"], "pending-validation")
        self.assertEqual(statuses["linux-arm64"], "pending-validation")

    def test_week15_darwin_pins_unchanged(self):
        tools = cp.load()["platforms"]["darwin-arm64"]["tools"]
        self.assertEqual(tools["ckb"]["binary_sha256"], "800d625b4baaa55cf6408b2f30ad744c4df90d52b94023ce226be875327c9493")
        self.assertEqual(tools["ckb-cli"]["binary_sha256"], "994166d983955fb59b6bab172485b3f65ff60487493b62a6569ad93eaa7adffb")

    def test_detection(self):
        self.assertEqual(cp.detect(system="Darwin", machine="arm64")[0], "darwin-arm64")
        self.assertEqual(cp.detect(system="Linux", machine="x86_64")[0], "linux-x86_64")
        self.assertEqual(cp.detect(system="Linux", machine="aarch64")[0], "linux-arm64")
        for system, machine in (("Darwin", "x86_64"), ("Windows", "AMD64"), ("Linux", "riscv64")):
            with self.assertRaises(cp.PlatformError):
                cp.detect(system=system, machine=machine)


class ExtractionTests(unittest.TestCase):
    def test_installs_only_verified_member_as_0755(self):
        binary = b"\x7fELF pinned"
        archive = tar_bytes([("pkg/README.md", b"x", "file"), ("pkg/tool", binary, "file")])
        with tempfile.TemporaryDirectory() as tmp:
            dest = cp.install_tool(archive, pin_for(archive, "pkg/tool", binary), Path(tmp) / "plat" / "tool")
            self.assertEqual(dest.read_bytes(), binary)
            self.assertEqual(os.stat(dest).st_mode & 0o777, 0o755)
            self.assertEqual(sorted(p.name for p in Path(tmp, "plat").iterdir()), ["tool"])

    def test_archive_digest_mismatch_installs_nothing(self):
        archive = tar_bytes([("pkg/tool", b"a", "file")])
        pin = pin_for(archive, "pkg/tool", b"a")
        pin["archive_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(cp.PlatformError):
                cp.install_tool(archive, pin, Path(tmp) / "tool")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_executable_digest_mismatch_installs_nothing(self):
        archive = tar_bytes([("pkg/tool", b"tampered", "file")])
        pin = pin_for(archive, "pkg/tool", b"expected")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(cp.PlatformError):
                cp.install_tool(archive, pin, Path(tmp) / "tool")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_symlink_member_rejected(self):
        archive = tar_bytes([("pkg/tool", b"", "symlink")])
        with self.assertRaises(cp.PlatformError):
            cp.extract_member(archive, "x.tar.gz", "pkg/tool")

    def test_unsafe_member_paths_rejected(self):
        for member in ("/abs/tool", "../tool", "pkg/../../tool"):
            with self.assertRaises(cp.PlatformError):
                cp.extract_member(b"", "x.tar.gz", member)

    def test_zip_member_and_missing_member(self):
        data = zip_bytes("pkg/ckb", b"bin")
        self.assertEqual(cp.extract_member(data, "x.zip", "pkg/ckb"), b"bin")
        with self.assertRaises(cp.PlatformError):
            cp.extract_member(data, "x.zip", "pkg/other")

    def test_existing_destination_not_overwritten(self):
        archive = tar_bytes([("pkg/tool", b"bin", "file")])
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "tool"
            dest.write_bytes(b"old")
            with self.assertRaises(cp.PlatformError):
                cp.install_tool(archive, pin_for(archive, "pkg/tool", b"bin"), dest)
            self.assertEqual(dest.read_bytes(), b"old")


class ToolLookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.entry = {"tools": {"ckb": {"member": "legacy-dir/ckb", "binary_sha256": hashlib.sha256(b"good").hexdigest()}}}

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, relative, data):
        path = self.dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755)
        return path

    def test_new_and_legacy_layouts_require_matching_digest(self):
        self.assertIsNone(cp.find_tool(self.dir, "plat", self.entry, "ckb"))
        legacy = self.put("legacy-dir/ckb", b"good")
        self.assertEqual(cp.find_tool(self.dir, "plat", self.entry, "ckb"), legacy)
        self.put("plat/ckb", b"wrong")
        self.assertEqual(cp.find_tool(self.dir, "plat", self.entry, "ckb"), legacy)

    def test_non_executable_rejected(self):
        self.put("plat/ckb", b"good").chmod(0o644)
        self.assertIsNone(cp.find_tool(self.dir, "plat", self.entry, "ckb"))


class CompilerTests(unittest.TestCase):
    def test_explicit_compiler_wins(self):
        self.assertEqual(cp.find_clang({"CLANG": "/x/clang", "PATH": ""}), "/x/clang")
        self.assertEqual(cp.find_clang({"CC_riscv64imac_unknown_none_elf": "/y", "CLANG": "/x"}), "/y")

    def test_clang18_on_path_before_fixed_prefixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            clang = Path(tmp) / "clang-18"
            clang.write_text("#!/bin/sh\necho 'Ubuntu clang version 18.1.3'\n")
            clang.chmod(0o755)
            self.assertEqual(cp.find_clang({"PATH": tmp}), str(clang))
            self.assertEqual(cp.clang_major(clang), 18)

    def test_nothing_found(self):
        with patch.object(cp, "LINUX_CLANG", Path("/nonexistent/clang")), patch.object(cp, "BREW_CLANG", ()):
            self.assertIsNone(cp.find_clang({"PATH": "/nonexistent"}))


class FetchConsentTests(unittest.TestCase):
    def test_list_and_noninteractive_never_download(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(fetch, "download", side_effect=AssertionError("network")):
            self.assertEqual(fetch.main(["--out", tmp, "--list"]), 0)
            with patch.object(sys.stdin, "isatty", return_value=False):
                with self.assertRaises(SystemExit):
                    fetch.main(["--out", tmp])

    def test_unknown_tool_rejected(self):
        with self.assertRaises(SystemExit):
            fetch.main(["--tools", "ckb,wallet"])


if __name__ == "__main__":
    unittest.main()
