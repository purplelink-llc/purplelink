"""Social poster short links in netlify.toml: /<p>/<app> and /<p>/g/:slug for every channel prefix, 302 with UTM tags,
in step with scripts/social (core.LINK_PREFIX, events.PRODUCTS)."""
import sys
import tomllib
import unittest
from urllib.parse import parse_qs, urlsplit

from common import ROOT, SITE, page_of, read

sys.path.insert(0, str(ROOT / "scripts" / "social"))
from core import LINK_PREFIX, UTM_SOURCE  # noqa: E402
from events import PRODUCTS  # noqa: E402


class SocialRedirects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = tomllib.loads(read("netlify.toml"))["redirects"]
        cls.by_from = {r["from"]: r for r in cls.rules}

    def test_every_channel_has_a_rule_per_product_and_one_guide_rule(self):
        for ch, p in LINK_PREFIX.items():
            for app, path in PRODUCTS.items():
                r = self.by_from.get(f"/{p}/{app}")
                self.assertIsNotNone(r, f"/{p}/{app}")
                u = urlsplit(r["to"])
                self.assertEqual(u.path, path)
                self.assertTrue(page_of(path).exists(), path)
                self.assertEqual(parse_qs(u.query), {"utm_source": [UTM_SOURCE[ch]], "utm_medium": ["social"],
                                                     "utm_campaign": [f"{p}-{app}"]}, r["from"])
                self.assertEqual(r["status"], 302)
                self.assertNotIn("force", r)
            g = self.by_from.get(f"/{p}/g/:slug")
            self.assertIsNotNone(g, f"/{p}/g/:slug")
            u = urlsplit(g["to"])
            self.assertEqual(u.path, "/guides/:slug/")
            self.assertEqual(parse_qs(u.query), {"utm_source": [UTM_SOURCE[ch]], "utm_medium": ["social"],
                                                 "utm_campaign": [f"{p}-guide"]})
            self.assertEqual(g["status"], 302)
            self.assertNotIn("force", g)

    def test_no_other_rule_under_a_channel_prefix(self):
        """Nothing but the exact product rules and the one guide rule: no splat, no bare prefix."""
        allowed = {f"/{p}/{a}" for p in LINK_PREFIX.values() for a in PRODUCTS}
        allowed |= {f"/{p}/g/:slug" for p in LINK_PREFIX.values()}
        allowed |= {"/li/paper-review", "/li/guides", "/li/tools"}  # PR 89
        for r in self.rules:
            first = r["from"].strip("/").split("/")[0]
            if first in LINK_PREFIX.values():
                self.assertIn(r["from"], allowed)
                self.assertNotIn("*", r["from"])
                self.assertNotIn(":splat", r["to"])

    def test_prefixes_do_not_shadow_site_folders(self):
        for p in LINK_PREFIX.values():
            self.assertFalse((SITE / p).exists(), p)

    def test_rules_come_before_the_catch_all_404(self):
        order = [r["from"] for r in self.rules]
        last = max(i for i, f in enumerate(order) if f.strip("/").split("/")[0] in LINK_PREFIX.values())
        self.assertLess(last, order.index("/*"))

    def test_short_paths_are_not_in_sitemap_or_search_index(self):
        for rel in ("sitemap.xml", "search-index.json"):
            f = SITE / rel
            if f.exists():
                text = f.read_text(encoding="utf-8")
                for p in LINK_PREFIX.values():
                    self.assertNotIn(f"purplelink.llc/{p}/", text, (rel, p))


if __name__ == "__main__":
    unittest.main()
