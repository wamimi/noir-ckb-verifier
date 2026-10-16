"""Static checks on the private tally v2 Noir sources (docs/private-tally-v2-spec.md)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CIRCUIT = ROOT / "circuits/private-tally-v2"
POSEIDON_DEP = 'poseidon = { tag = "v0.2.6", git = "https://github.com/noir-lang/poseidon" }'


def sources():
    return sorted(CIRCUIT.rglob("*.nr"))


class PrivateTallyCircuit(unittest.TestCase):
    def test_every_poseidon2_call_takes_at_most_three_inputs(self):
        # poseidon v0.2.6 has a stale-cache bug for inputs longer than 3.
        calls = 0
        for path in sources():
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
        self.assertEqual(calls, 2, "the commitment uses exactly two Poseidon2 calls")

    def test_poseidon_dependency_is_pinned_once(self):
        manifests = [p.read_text() for p in CIRCUIT.rglob("Nargo.toml")]
        self.assertEqual(sum(POSEIDON_DEP in m for m in manifests), 1)
        self.assertEqual(sum("noir-lang/poseidon" in m for m in manifests), 1)

    def test_parameter_layout_is_private_first_then_public(self):
        text = (CIRCUIT / "circuit/src/main.nr").read_text()
        params = re.search(r"fn main\((.*?)\)\s*\{", text, re.S).group(1)
        names = [(m.group(1), bool(m.group(2))) for m in re.finditer(r"(\w+)\s*:\s*(pub\s+)?Field", params)]
        self.assertEqual(names, [
            ("value_old", False), ("r_old", False), ("key", False), ("delta", False), ("r_new", False),
            ("c_old", True), ("c_new", True), ("ctx_lo", True), ("ctx_hi", True),
        ])

    def test_domain_tags_match_the_specification(self):
        text = (CIRCUIT / "commitment/src/lib.nr").read_text()
        for name, label in (("TAG_STATE", "noir-ckb:tally:v2:state"), ("TAG_INNER", "noir-ckb:tally:v2:inner")):
            value = re.search(rf"{name}: Field = (0x[0-9a-f]+);", text).group(1)
            self.assertEqual(int(value, 16), int.from_bytes(label.encode(), "big"))


if __name__ == "__main__":
    unittest.main()
