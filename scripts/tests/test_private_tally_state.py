"""Private tally v2 secret handling (docs/private-tally-v2-spec.md, section 9). No network or chain."""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import private_tally as pt  # noqa: E402


def mode(p):
    return stat.S_IMODE(Path(p).stat().st_mode)


class SecretHandling(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.private = pt.PrivateDir(self.tmp / "private", create=True)
        self.state = pt.TallyState(self.private)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_secrets_are_nonzero_field_elements_and_distinct(self):
        values = {pt.new_secret() for _ in range(64)}
        self.assertEqual(len(values), 64)
        self.assertTrue(all(0 < v < pt.P for v in values))

    def test_private_dir_and_files_are_owner_only(self):
        self.assertEqual(mode(self.private.path), 0o700)
        f = self.private.write_new("x", "secret")
        self.assertEqual(mode(f), 0o600)

    def test_private_dir_with_open_permissions_is_refused(self):
        os.chmod(self.private.path, 0o755)
        with self.assertRaises(PermissionError):
            pt.PrivateDir(self.private.path)

    def test_existing_private_dir_is_never_reused_on_create(self):
        with self.assertRaises(FileExistsError):
            pt.PrivateDir(self.private.path, create=True)

    def test_state_is_versioned_and_never_overwritten(self):
        a = self.state.append(key=5 + 2**50, value=0, blinding=7 + 2**50, commitment=9, label="creation")
        b = self.state.append(key=5 + 2**50, value=3, blinding=8 + 2**50, commitment=10, label="update-1")
        self.assertEqual((a["seq"], b["seq"]), (1, 2))
        self.assertEqual(self.state.versions(), [1, 2])
        self.assertEqual(self.state.latest()["value"], "3")
        self.assertEqual(json.loads(self.private.read("state-0001.json"))["value"], "0")
        with self.assertRaises(FileExistsError):
            self.private.write_new("state-0002.json", "{}")

    def test_state_rejects_invalid_values(self):
        for bad in (dict(key=0), dict(blinding=pt.P), dict(commitment=0), dict(value=2**64)):
            args = dict(key=1, value=0, blinding=1, commitment=1, label="x") | bad
            with self.assertRaises(ValueError):
                self.state.append(**args)

    def test_state_file_with_open_permissions_is_refused(self):
        self.state.append(key=1, value=0, blinding=1, commitment=1, label="creation")
        os.chmod(self.private.path / "state-0001.json", 0o644)
        with self.assertRaises(PermissionError):
            self.state.latest()

    def test_backup_keeps_owner_only_permissions(self):
        self.state.append(key=1, value=0, blinding=1, commitment=1, label="creation")
        copy = pt.backup(self.private, self.tmp / "backup")
        self.assertEqual(mode(copy), 0o700)
        self.assertEqual(mode(copy / "state-0001.json"), 0o600)
        with self.assertRaises(FileExistsError):
            pt.backup(self.private, self.tmp / "backup")

    def test_leak_scan_finds_every_encoding_outside_the_private_dir(self):
        secret = pt.new_secret()
        kept = self.tmp / "kept"
        kept.mkdir()
        encodings = {
            "decimal.txt": str(secret).encode(),
            "hex.txt": format(secret, "x").encode(),
            "padded.txt": format(secret, "064x").upper().encode(),
            "le.bin": b"\0" + secret.to_bytes(32, "little"),
            "be.bin": secret.to_bytes(32, "big") + b"\0",
        }
        for name, data in encodings.items():
            (kept / name).write_bytes(data)
        self.private.write_new("inside", str(secret))
        (kept / "clean.txt").write_text("nothing here")
        hits = pt.leak_scan(self.tmp, {secret}, exclude=[self.private.path])
        self.assertEqual(hits, sorted(f"kept/{n}" for n in encodings))

    def test_small_values_are_not_treated_as_secrets(self):
        (self.tmp / "counts.txt").write_text("value 5")
        self.assertEqual(pt.leak_scan(self.tmp, {5}, exclude=[self.private.path]), [])


@unittest.skipUnless(os.environ.get("NARGO"), "set NARGO to a Nargo 1.0.0-beta.18 binary to run")
class Commitment(unittest.TestCase):
    def test_helper_matches_across_calls_and_leaves_no_prover_file(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            private = pt.PrivateDir(tmp / "private", create=True)
            circuit = pt.Circuit(private, os.environ["NARGO"])
            circuit.compile()
            a = circuit.commitment(3, 11, 13)
            self.assertEqual(a, circuit.commitment(3, 11, 13))
            self.assertNotEqual(a, circuit.commitment(4, 11, 13))
            self.assertTrue(0 < a < pt.P)
            self.assertFalse((circuit.ws / "commit-helper/Prover.toml").exists())
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
