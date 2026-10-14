"""The text drawn in the LaTeX error videos (video/src/latexfix/data.js) must match the error pages it is copied from,
line for line: video/check-latexfix.mjs reads the pages and fails on any code or log line that is not on them.
Needs only node; skipped where node is not installed."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node not installed")
class LatexFixVideoText(unittest.TestCase):
    def test_every_video_line_is_on_its_page(self):
        r = subprocess.run(["node", "check-latexfix.mjs"], cwd=ROOT / "video", capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("NOT ON PAGE", r.stdout)

    def test_the_long_tutorial_covers_all_five_causes_on_the_page(self):
        out = subprocess.run(["node", "check-latexfix.mjs"], cwd=ROOT / "video", capture_output=True, text=True, timeout=60).stdout
        for slug in ("package", "name", "template", "class", "input"):
            self.assertIn(f"file-not-found-{slug}:", out)


if __name__ == "__main__":
    unittest.main()
