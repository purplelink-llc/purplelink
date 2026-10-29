import re
import unittest
from common import read_site


class W8(unittest.TestCase):
    def test_globepin_pricing_in_llms_txt(self):
        txt = read_site("llms.txt")
        m = re.search(r"^### GlobePin.*?(?=^#{2,3} |\Z)", txt, re.S | re.M)
        self.assertIsNotNone(m, "no GlobePin section")
        sec = m.group(0)
        self.assertIn("Pro", sec)
        self.assertIn("$9.99", sec)
        self.assertNotIn("no in-app purchase", sec.lower())

    def test_homepage_paper_review_button(self):
        self.assertRegex(read_site("index.html"), r">\s*Start a review, from \$9\s*<")
