"""The daily how-to videos publish without a human look, so scripts/howto_gate.py must fail on every kind of bad
storyboard. Each test breaks one thing in a copy of a real storyboard and checks the gate names it (offline mode)."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "howto_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
GOOD = json.loads((ROOT / "video" / "storyboards" / "howto" / "latexmk-command-not-found.json").read_text())


def errors(sb):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "sb.json"
        p.write_text(json.dumps(sb))
        return gate.check(p, offline=True, rebuild=True)


class HowtoGate(unittest.TestCase):
    def test_the_real_storyboard_passes(self):
        self.assertEqual(errors(GOOD), [])

    def test_a_price_fails(self):
        sb = copy.deepcopy(GOOD); sb["scenes"][-1]["narration"] += " Only $19.99."
        self.assertTrue(any("price" in e for e in errors(sb)))

    def test_a_destructive_command_fails(self):
        sb = copy.deepcopy(GOOD); sb["scenes"][3]["lines"].append("$ sudo rm -rf /Library/TeX")
        self.assertTrue(any("destructive" in e or "not allowlisted" in e for e in errors(sb)))

    def test_sudo_outside_the_allowlist_fails(self):
        sb = copy.deepcopy(GOOD); sb["scenes"][3]["lines"].append("$ sudo pmset -a hibernatemode 0")
        self.assertTrue(any("not allowlisted" in e for e in errors(sb)))

    def test_output_that_was_never_recorded_fails(self):
        sb = copy.deepcopy(GOOD); sb["scenes"][4]["lines"][1] = "Latexmk, Version 99"
        self.assertTrue(any("not in any recorded verification run" in e for e in errors(sb)))

    def test_an_app_outside_the_rotation_fails(self):
        sb = copy.deepcopy(GOOD); sb["app"] = "rubblefront"
        self.assertTrue(any("not in the rotation" in e for e in errors(sb)))

    def test_hype_emoji_and_em_dash_fail(self):
        sb = copy.deepcopy(GOOD); sb["title"] = "The ultimate fix — instantly \U0001F525"
        e = " ".join(errors(sb))
        self.assertIn("hype word", e); self.assertIn("emoji", e); self.assertIn("em dash", e)

    def test_no_short_scene_fails(self):
        sb = copy.deepcopy(GOOD)
        for s in sb["scenes"]:
            s.pop("short", None)
        self.assertTrue(any("short" in e for e in errors(sb)))

    def test_one_thumbnail_template_fails(self):
        sb = copy.deepcopy(GOOD)
        sb["thumbs"] = {k: {"kind": "error", "msg": "x"} for k in "ABC"}
        self.assertTrue(any("two templates" in e for e in errors(sb)))


if __name__ == "__main__":
    unittest.main()
