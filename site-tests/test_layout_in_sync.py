"""The Netlify build runs scripts/apply_layout.py before publishing, so a nav or
footer edit made by hand in site/ (not in the script) is silently undone on
every deploy. PR 337 added a "Mac Suite" footer link that way; this keeps the
checked-in pages and the script in agreement."""
import subprocess
import sys
import unittest
from common import ROOT


class LayoutInSync(unittest.TestCase):
    def test_apply_layout_is_a_no_op(self):
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "apply_layout.py"), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            r.returncode, 0,
            r.stdout + r.stderr + "\nEdit the nav or footer in scripts/apply_layout.py, then run it.",
        )
