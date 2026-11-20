"""Static checks on the ballot vote Noir sources (circuits/ballot/README.md)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CIRCUIT = ROOT / "circuits/ballot"
POSEIDON_DEP = 'poseidon = { tag = "v0.2.6", git = "https://github.com/noir-lang/poseidon" }'
DEPTH = 20
PUBLIC = ["voter_root", "election_lo", "election_hi", "nullifier", "choice", "ctx_lo", "ctx_hi"]
PRIVATE = ["secret"] + [f"s{i}" for i in range(DEPTH)] + [f"b{i}" for i in range(DEPTH)]


def parameters(path):
    text = path.read_text()
    params = re.search(r"fn main\((.*?)\)\s*(->[^{]*)?\{", text, re.S).group(1)
    return [(m.group(1), bool(m.group(2))) for m in re.finditer(r"(\w+)\s*:\s*(pub\s+)?Field", params)]


class BallotVoteCircuit(unittest.TestCase):
    def test_every_poseidon2_call_takes_at_most_three_inputs(self):
        # poseidon v0.2.6 has a stale-cache bug for inputs longer than 3.
        calls = 0
        for path in sorted(CIRCUIT.rglob("*.nr")):
            if "target" in path.parts:
                continue
            text = path.read_text()
            for match in re.finditer(r"Poseidon2::hash\s*\(", text):
                calls += 1
                args = text[match.end():text.index(")", match.end())]
                array = re.match(r"\s*\[(.*?)\]\s*,\s*(\d+)\s*$", args, re.S)
                self.assertIsNotNone(array, f"{path}: Poseidon2::hash call must be ([..], N): {args!r}")
                items = [x for x in array.group(1).split(",") if x.strip()]
                self.assertLessEqual(len(items), 3, f"{path}: {args!r}")
                self.assertEqual(int(array.group(2)), len(items), f"{path}: length argument mismatch {args!r}")
            self.assertNotRegex(text, r"poseidon2_permutation|Poseidon2Hasher|hash_\d", f"{path}: only Poseidon2::hash is allowed")
        self.assertEqual(calls, 4, "identity, node, election and nullifier: four Poseidon2 calls, all in the library")

    def test_poseidon_dependency_is_pinned_once(self):
        manifests = [p.read_text() for p in CIRCUIT.rglob("Nargo.toml")]
        self.assertEqual(sum(POSEIDON_DEP in m for m in manifests), 1)
        self.assertEqual(sum("noir-lang/poseidon" in m for m in manifests), 1)

    def test_workspace_is_separate_from_the_private_tally(self):
        tally = (ROOT / "circuits/private-tally-v2/Nargo.toml").read_text()
        self.assertNotIn("ballot", tally)
        for manifest in CIRCUIT.rglob("Nargo.toml"):
            for line in manifest.read_text().splitlines():
                if "path" in line and not line.lstrip().startswith("#"):
                    self.assertEqual(re.findall(r'path = "([^"]*)"', line), ["../hashes"], f"{manifest}: {line}")

    def test_parameter_layout_is_private_first_then_public(self):
        expected = [(n, False) for n in PRIVATE] + [(n, True) for n in PUBLIC]
        self.assertEqual(parameters(CIRCUIT / "vote/src/main.nr"), expected)

    def test_helper_takes_the_same_private_inputs(self):
        expected = [(n, False) for n in PRIVATE + ["election_lo", "election_hi"]]
        self.assertEqual(parameters(CIRCUIT / "helper/src/main.nr"), expected)

    def test_depth_and_domain_tags(self):
        text = (CIRCUIT / "hashes/src/lib.nr").read_text()
        self.assertEqual(int(re.search(r"global DEPTH: u32 = (\d+);", text).group(1)), DEPTH)
        for name in ("identity", "node", "election", "nullifier"):
            value = re.search(rf"TAG_{name.upper()}: Field = (0x[0-9a-f]+);", text).group(1)
            self.assertEqual(int(value, 16), int.from_bytes(f"noir-ckb:ballot:v1:{name}".encode(), "big"))

    def test_public_inputs_match_the_binding_spec(self):
        spec = (ROOT / "research/spikes/toolkit-architecture/specs/ballot-box.toml").read_text()
        listed = re.search(r'\[binding\.circuit\.vote\].*?public = \[(.*?)\]', spec, re.S).group(1)
        self.assertEqual(re.findall(r'"(\w+)"', listed), PUBLIC)


if __name__ == "__main__":
    unittest.main()
