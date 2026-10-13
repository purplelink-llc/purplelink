import re
import unittest
from common import ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk

URL = "/guides/latexdiff-online/"


class LatexdiffGuide(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")

    def test_exists_with_canonical(self):
        self.assertTrue(page_of(URL).is_file())
        self.assertEqual(canonical(self.text), ORIGIN + URL)

    def test_title_under_60(self):
        title = re.search(r"<title>(.*?)</title>", self.text).group(1)
        self.assertLess(len(title), 60)

    def test_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)

    def test_no_inline_style(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")

    def test_no_em_dash_or_emoji(self):
        self.assertNotIn("—", self.text)
        self.assertIsNone(EMOJI.search(self.text))

    def test_json_ld(self):
        types = {d.get("@type") for b in jsonld_blocks(self.text) for d in walk(b)}
        self.assertIn("Article", types)
        self.assertIn("BreadcrumbList", types)

    def test_internal_links_resolve(self):
        hrefs = set(re.findall(r'href="(/[^"#?]*)', self.text))
        bad = [h for h in hrefs if h.endswith("/") and h != "/" and not page_of(h).is_file()]
        self.assertEqual(bad, [])

    def test_inbound_links(self):
        for src in ("/guides/latex-track-changes/", "/tools/latex-diff/"):
            self.assertIn('href="%s"' % URL, page_of(src).read_text(encoding="utf-8"))
