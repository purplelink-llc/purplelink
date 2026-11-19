"""llms-full.txt names every page in the sitemap (title, URL, summary), so the short llms.txt (Buddy's facts block)
does not have to list them all."""
import re
import unittest

from common import SITE


class LlmsFullPageIndex(unittest.TestCase):
    def test_every_sitemap_page_is_listed(self):
        full = (SITE / "llms-full.txt").read_text(encoding="utf-8")
        self.assertIn("# Every page on purplelink.llc", full)
        index = full.split("# Every page on purplelink.llc", 1)[1]
        missing = []
        for url in re.findall(r"<loc>([^<]+)</loc>", (SITE / "sitemap.xml").read_text(encoding="utf-8")):
            if not url.endswith("/"):
                continue
            rel = url.split("purplelink.llc/", 1)[1]
            page = SITE / rel / "index.html"
            if not page.is_file() or "noindex" in page.read_text(encoding="utf-8")[:6000]:
                continue
            if f": {url}" not in index:
                missing.append(url)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
