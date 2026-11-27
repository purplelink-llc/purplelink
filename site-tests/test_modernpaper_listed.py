"""ModernPaper is public: its page is indexable and listed in the sitemap, llms.txt and the products page."""
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
NOINDEX = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', re.I)


class ModernPaperListed(unittest.TestCase):
    def test_product_page_is_indexable(self):
        html = (SITE / "modernpaper/index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, NOINDEX)
        self.assertIn("index, follow", html)
        self.assertIn('property="og:image"', html)
        self.assertTrue((SITE / "assets/og/modernpaper.png").exists())

    def test_success_page_stays_noindex(self):
        html = (SITE / "modernpaper/success/index.html").read_text(encoding="utf-8")
        self.assertRegex(html, NOINDEX)

    def test_listed(self):
        self.assertIn("https://purplelink.llc/modernpaper/", (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn("https://purplelink.llc/modernpaper/", (SITE / "llms.txt").read_text(encoding="utf-8"))
        self.assertIn("/modernpaper/", (SITE / "products/index.html").read_text(encoding="utf-8"))
        self.assertIn("/modernpaper/", (SITE / "suite/index.html").read_text(encoding="utf-8"))

    def test_price_and_suite_copy(self):
        html = (SITE / "modernpaper/index.html").read_text(encoding="utf-8")
        self.assertIn("$49", html)
        self.assertNotIn("$79", html)
        self.assertIn("$99.99", html)


if __name__ == "__main__":
    unittest.main()
