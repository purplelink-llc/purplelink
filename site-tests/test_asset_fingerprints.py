import subprocess
import sys
import unittest
from common import ROOT


class Fingerprints(unittest.TestCase):
    def test_check_passes(self):
        r = subprocess.run([sys.executable, "scripts/fingerprint_assets.py", "--check"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
