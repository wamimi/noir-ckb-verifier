"""Participant join bundle: integrity, public-record cross-checks and step ordering (no network)."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import owned_counter as c  # noqa: E402

spec = importlib.util.spec_from_file_location("join", SCRIPTS / "join-counter-testnet.py")
join = importlib.util.module_from_spec(spec)
spec.loader.exec_module(join)

PUBLISHED = join.DEFAULT_BUNDLE
RECORD = join.DEFAULT_RECORD


class Fixture:
    """A synthetic release, setup and deployment receipt shaped like real runner output."""

    def __init__(self, root):
        self.root = Path(root)
        setup = self.root / "setup"
        contents = {"development.zkey": b"zkey", "verification_key.json": b'{"vk": 1}',
                    "interop/circuit.r1cs": b"r1cs", "circuit/target/owned_counter_v1.json": b'{"bytecode": "x"}'}
        for rel, data in contents.items():
            (setup / rel).parent.mkdir(parents=True, exist_ok=True)
            (setup / rel).write_bytes(data)
        (setup / "manifest.json").write_text(json.dumps(dict(
            status="passed", profile=c.PROFILE, backend_revision="828025f3a0090e2934940956c0f5dc8093eb5532",
            artifacts={rel: c.sha(setup / rel) for rel in contents})))
        build = self.root / "build"
        build.mkdir()
        (build / "owned-counter").write_bytes(b"\x7fELF type")
        (build / "vk.mol.bin").write_bytes(b"vk bytes")
        artifacts = {k: dict(path=str(build / n), sha256=c.sha(build / n), data_hash=c.hx(c.h((build / n).read_bytes())),
                             bytes=(build / n).stat().st_size) for k, n in join.ARTIFACT_FILES.items()}
        network = "0x" + "aa" * 32
        policy = dict(profile=c.PROFILE, network_domain=network, owner_code_hash=c.OWNER_CODE, owner_data_hash=c.OWNER_DATA,
                      owner_dep=dict(out_point=dict(tx_hash="0x" + "bb" * 32, index="0x0"), dep_type="dep_group"),
                      vk_data_hash=artifacts["vk"]["data_hash"])
        self.release = build / "release.json"
        self.release.write_text(json.dumps(dict(profile=c.PROFILE, policy=policy, setup=str(setup), artifacts=artifacts)))
        deploy_hash = "0x" + "cc" * 32
        self.receipt = self.root / "receipt.json"
        self.receipt.write_text(json.dumps(dict(
            status="committed-and-cells-checked", tx_hash=deploy_hash, network=network, release_sha256=c.sha(self.release),
            type=dict(tx_hash=deploy_hash, index="0x0"), vk=dict(tx_hash=deploy_hash, index="0x1"))))
        self.record = dict(
            policy=policy, artifacts={k: {f: v[f] for f in ("sha256", "data_hash", "bytes")} for k, v in artifacts.items()},
            setup=dict(artifacts_sha256={rel: c.sha(setup / rel) for rel in ("development.zkey", "verification_key.json", "interop/circuit.r1cs")}),
            transactions=dict(deployment=dict(hash=deploy_hash)))

    def bundle(self, name="bundle"):
        out = self.root / name
        join.make_bundle(join_args(release=self.release, deployment=self.receipt, out=out, path_map=None))
        return out

    def write_record(self, record=None):
        path = self.root / "record.json"
        path.write_text(json.dumps(record or self.record))
        return path


def join_args(**kw):
    class A:
        pass
    a = A()
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_with_public_record(self):
        bundle = self.fx.bundle()
        man = join.verify_bundle(bundle, self.fx.write_record())
        self.assertEqual(man["deployment"]["type"]["index"], "0x0")
        self.assertEqual(sorted(p.name for p in bundle.iterdir()),
                         sorted(["manifest.json", "owned-counter", "vk.mol.bin", *join.SETUP_FILES]))

    def test_circuit_artifact_paths_are_sanitized(self):
        artifact = self.fx.root / "setup/circuit/target/owned_counter_v1.json"
        artifact.write_text(json.dumps(dict(bytecode="x", abi={}, file_map={"51": dict(source="fn main(){}", path="/Users/someone/private/main.nr")})))
        manifest = c.read(self.fx.root / "setup/manifest.json")
        manifest["artifacts"]["circuit/target/owned_counter_v1.json"] = c.sha(artifact)
        (self.fx.root / "setup/manifest.json").write_text(json.dumps(manifest))
        bundle = self.fx.bundle()
        text = (bundle / "owned_counter_v1.json").read_text()
        self.assertNotIn("/Users/", text)
        self.assertEqual(c.read(bundle / "owned_counter_v1.json")["bytecode"], "x")

    def test_tampered_setup_file_rejected(self):
        bundle = self.fx.bundle()
        (bundle / "development.zkey").write_bytes(b"forged zkey")
        with self.assertRaises(ValueError):
            join.verify_bundle(bundle)

    def test_tampered_contract_rejected(self):
        bundle = self.fx.bundle()
        (bundle / "owned-counter").write_bytes(b"\x7fELF other")
        with self.assertRaises(ValueError):
            join.verify_bundle(bundle)

    def test_manifest_and_files_swapped_together_still_fail_record_check(self):
        bundle = self.fx.bundle()
        (bundle / "development.zkey").write_bytes(b"forged zkey")
        man = c.read(bundle / "manifest.json")
        man["files"]["development.zkey"].update(sha256=c.sha(bundle / "development.zkey"), bytes=11)
        (bundle / "manifest.json").write_text(json.dumps(man))
        join.verify_bundle(bundle)  # internally consistent ...
        with self.assertRaises(ValueError):
            join.verify_bundle(bundle, self.fx.write_record())  # ... but not what was publicly recorded

    def test_record_mismatches_rejected(self):
        bundle = self.fx.bundle()
        for mutate in (lambda r: r["policy"].update(vk_data_hash="0x" + "11" * 32),
                       lambda r: r["artifacts"]["type"].update(data_hash="0x" + "22" * 32),
                       lambda r: r["transactions"]["deployment"].update(hash="0x" + "33" * 32)):
            record = copy.deepcopy(self.fx.record)
            mutate(record)
            with self.assertRaises(ValueError):
                join.verify_bundle(bundle, self.fx.write_record(record))

    def test_policy_vk_must_match_bundled_vk(self):
        bundle = self.fx.bundle()
        man = c.read(bundle / "manifest.json")
        man["policy"]["vk_data_hash"] = "0x" + "44" * 32
        (bundle / "manifest.json").write_text(json.dumps(man))
        with self.assertRaises(ValueError):
            join.verify_bundle(bundle)

    def test_receipt_for_other_release_rejected(self):
        receipt = c.read(self.fx.receipt)
        receipt["release_sha256"] = "0" * 64
        self.fx.receipt.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):
            self.fx.bundle()

    def test_unsafe_names_rejected(self):
        for name in ("../zkey", "a/b", "", ".."):
            with self.assertRaises(ValueError):
                join.safe_name(name)


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=c.ROOT / "target" if (c.ROOT / "target").is_dir() else None))
        if not self.work.is_relative_to(c.ROOT / "target"):
            self.skipTest("needs the checkout's target/ directory")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def state(self, stage):
        (self.work / "state.json").write_text(json.dumps(dict(stage=stage, rpc="http://127.0.0.1:1", history=[])))

    def test_steps_refuse_wrong_stage(self):
        self.state("initialized")
        with self.assertRaises(ValueError):
            join.update(join_args(work=self.work))
        with self.assertRaises(ValueError):
            join.confirm(join_args(work=self.work, hash="0x" + "00" * 32))
        with self.assertRaises(ValueError):
            join.check(join_args(work=self.work))
        self.state("created")
        with self.assertRaises(ValueError):
            join.create(join_args(work=self.work, owner="0x" + "11" * 20, funding="0x" + "22" * 32 + ":0", capacity_ckb=200))

    def test_work_dir_must_be_below_target(self):
        with self.assertRaises(ValueError):
            join.out_dir(Path(tempfile.gettempdir()) / "elsewhere", must_exist=False)


@unittest.skipUnless((PUBLISHED / "manifest.json").is_file(), "published bundle not present")
class PublishedBundleTests(unittest.TestCase):
    def test_published_bundle_matches_public_record(self):
        man = join.verify_bundle(PUBLISHED, RECORD)
        self.assertEqual(man["network"], c.TESTNET)


if __name__ == "__main__":
    unittest.main()
