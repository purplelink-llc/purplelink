import re
import unittest
from common import SITE, read_site, page_of

GUIDE = "/guides/best-mac-latex-editors/"


def pages():
    out = sorted((SITE / "latex-errors").glob("*/index.html"))
    out.append(SITE / "latex-errors" / "index.html")
    out += [SITE / "templates" / s / "index.html" for s in ("acm-acmart", "apa7", "elsevier-elsarticle", "ieee-conference", "neurips")]
    return out


class EditorsGuideLinks(unittest.TestCase):
    def test_page_set_is_not_empty(self):
        self.assertGreaterEqual(len(pages()), 17)

    def test_every_page_links_to_the_guide(self):
        missing = [str(p.relative_to(SITE)) for p in pages() if not p.exists() or f'href="{GUIDE}' not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [])

    def test_guide_has_hands_on_anchor(self):
        text = page_of(GUIDE).read_text(encoding="utf-8")
        self.assertRegex(text, r'\bid="hands-on"')
