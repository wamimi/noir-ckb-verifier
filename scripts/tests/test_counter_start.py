"""Launcher boundaries: no implicit network, install, or local transaction execution."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("counter_start", Path(__file__).resolve().parents[1] / "start-counter.py")
start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start)


class StartTests(unittest.TestCase):
    def test_inspect_skips_proving_prerequisites_and_network(self):
        with patch.object(start, "doctor", side_effect=AssertionError("unneeded prerequisites")), patch.object(start, "run_script", return_value=0) as run:
            self.assertEqual(start.main(["inspect"]), 0)
            self.assertEqual(run.call_args.args[:2], ("review-counter.py", []))

    def test_live_failure_is_not_recorded_success(self):
        with patch.object(start, "run_script", return_value=1) as run:
            self.assertEqual(start.main(["live", "--rpc", "https://example.invalid"]), 1)
            self.assertEqual(run.call_args.args[1], ["--rpc", "https://example.invalid"])

    def test_missing_prerequisite_never_starts_local_runner(self):
        with patch.object(start, "doctor", return_value=False), patch.object(start, "run_script") as run:
            self.assertEqual(start.main(["local", "--yes"]), 1)
            run.assert_not_called()

    def test_outside_target_and_existing_output_rejected(self):
        with patch.object(start, "doctor", return_value=True), patch.object(start, "run_script") as run:
            for out in (str(start.ROOT.parent / "elsewhere"), str(start.ROOT / "target")):
                with self.assertRaises(ValueError):
                    start.main(["local", "--yes", "--out", out])
            run.assert_not_called()

    def test_noninteractive_local_requires_explicit_yes(self):
        with patch.object(start, "doctor", return_value=True), patch.object(start, "validate_local"), patch.object(sys.stdin, "isatty", return_value=False), patch.object(start, "run_script") as run:
            with self.assertRaises(SystemExit) as error:
                start.main(["local"])
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_local_uses_mutations_and_preserves_failure(self):
        with patch.object(start, "doctor", return_value=True), patch.object(start, "validate_local"), patch.object(start, "run_script", return_value=7) as run:
            self.assertEqual(start.main(["local", "--yes"]), 7)
            self.assertEqual(run.call_args.args[0], "local-owned-counter.py")
            self.assertIn("--mutations", run.call_args.args[1])
            self.assertNotIn("--rpc", run.call_args.args[1])
            forwarded = run.call_args.args[1]
            self.assertTrue(forwarded[forwarded.index("--out") + 1].is_absolute())

    def test_doctor_never_starts_local_runner(self):
        with patch.object(start, "doctor", return_value=True), patch.object(start, "run_script") as run:
            self.assertEqual(start.main(["doctor"]), 0)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
