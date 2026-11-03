"""Every paid link on the site must be countable by site/analytics.js.

analytics.js sends affiliate_click for an <a rel="sponsored"> using its data-aff program id (stamped by
scripts/affiliates.py apply), unless the link already carries its own data-track event (the /desk/ book cards).
A paid link with neither would be clicked uncounted, so it fails here.
"""
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
A_TAG = re.compile(r"<a\b[^>]*>", re.I)


class AffiliateClickTracking(unittest.TestCase):
    def test_analytics_counts_sponsored_links(self):
        js = (SITE / "analytics.js").read_text(encoding="utf-8")
        self.assertIn('closest(\'a[rel~="sponsored"]\')', js)
        self.assertIn('plTrack("affiliate_click"', js)

    def test_middle_click_on_a_paid_link_is_counted(self):
        # A middle click opens the link in a new tab and fires auxclick, never click, so a click listener alone
        # misses it (found 2026-10-29: a live middle click on the VPN guide sent no beacon).
        js = (SITE / "analytics.js").read_text(encoding="utf-8")
        self.assertRegex(js, r'addEventListener\("auxclick"')
        aux = js[js.index('addEventListener("auxclick"'):]
        self.assertRegex(aux[:400], r"ev\.button [!=]== 1")
        self.assertIn("countAffiliate(ev)", aux[:400])

    def test_every_sponsored_link_is_attributable(self):
        missing = []
        for top in ("guides", "blog", "tools", "desk"):
            for page in (SITE / top).rglob("*.html"):
                rel = page.relative_to(SITE).as_posix()
                if rel.startswith("blog/digest/"):
                    continue
                for tag in A_TAG.findall(page.read_text(encoding="utf-8", errors="ignore")):
                    m = re.search(r'\brel="([^"]*)"', tag)
                    if m and "sponsored" in m.group(1).split() and "data-aff=" not in tag and "data-track=" not in tag:
                        missing.append(f"{rel}: {tag[:90]}")
        self.assertEqual(missing, [], "run: python3 scripts/affiliates.py apply --write")


if __name__ == "__main__":
    unittest.main()
