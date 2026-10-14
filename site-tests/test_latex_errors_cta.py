"""Every LaTeX error page (and the hub) carries the ModernTex band exactly once, before the related-links nav,
with its links tagged so the funnel can attribute the visit (scripts/insert_latex_errors_cta.py)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import insert_latex_errors_cta as C  # noqa: E402


class LatexErrorsCta(unittest.TestCase):
    def pages(self):
        ps = C.pages(ROOT)
        self.assertGreaterEqual(len(ps), 13)
        return ps

    def test_each_page_has_the_band_once_before_the_nav(self):
        for p in self.pages():
            html = p.read_text(encoding="utf-8")
            self.assertEqual(html.count(C.MARKER), 1, p)
            self.assertLess(html.index(C.MARKER), html.index('<nav class="tool-related"'), p)

    def test_links_are_tagged_and_point_at_moderntex(self):
        for p in self.pages():
            html = p.read_text(encoding="utf-8")
            band = html[html.index(C.MARKER):html.index('<nav class="tool-related"')]
            hrefs = re.findall(r'href="([^"]+)"', band)
            self.assertEqual(hrefs, ["/moderntex/?from=latex-errors"] * 2, p)

    def test_insert_is_idempotent_and_refuses_a_missing_anchor(self):
        html = '<main>\n      <nav class="tool-related" aria-label="x"></nav>\n</main>'
        once, status = C.insert(html)
        self.assertEqual(status, "changed")
        twice, status2 = C.insert(once)
        self.assertEqual((twice, status2), (once, "skipped"))
        self.assertEqual(C.insert("<main></main>")[1], "anchor not found")

    def test_no_inline_styles_or_emoji_in_the_band(self):
        band = C.BLOCK
        self.assertNotIn("style=", band)
        self.assertFalse(re.search("[\U0001F300-\U0001FAFF☀-➿]", band))


if __name__ == "__main__":
    unittest.main()
