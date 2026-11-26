"""ModernPaper launches hidden: its pages are noindex and nothing on the site links to them."""
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
NOINDEX = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', re.I)


class ModernPaperUnlisted(unittest.TestCase):
    def test_pages_are_noindex(self):
        for rel in ("modernpaper/index.html", "modernpaper/success/index.html"):
            self.assertRegex((SITE / rel).read_text(encoding="utf-8"), NOINDEX, rel)

    def test_not_in_sitemap_or_lists(self):
        for rel in ("sitemap.xml", "llms.txt", "products/index.html", "index.html", "suite/index.html"):
            p = SITE / rel
            if p.exists():
                self.assertNotIn("modernpaper", p.read_text(encoding="utf-8").lower(), rel)

    def test_no_other_page_links_to_it(self):
        hits = []
        for p in SITE.rglob("*.html"):
            rel = p.relative_to(SITE).as_posix()
            if rel.startswith("modernpaper/"):
                continue
            if "/modernpaper/" in p.read_text(encoding="utf-8", errors="ignore"):
                hits.append(rel)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
