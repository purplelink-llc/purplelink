"""LinkedIn short links in netlify.toml: /li/<slug> -> 302 to a real page with the UTM tags, no wildcard."""
import tomllib
import unittest
from urllib.parse import urlsplit, parse_qs

from common import ROOT, SITE, page_of, read

EXPECTED = {
    "/li/moderntex": "/moderntex/",
    "/li/vitae": "/vitae/",
    "/li/outbound-veil": "/outbound-veil/",
    "/li/tapefolio": "/tapefolio/",
    "/li/paper-review": "/tools/paper-review/",
    "/li/legroom": "/legroom/",
    "/li/guides": "/guides/",
    "/li/tools": "/tools/",
    "/li/keyfeel": "/keyfeel/",
    "/li/panely": "/panely/",
    "/li/summonly": "/summonly/",
    "/li/batterymeter": "/batterymeter/",
}
# The one placeholder rule, /li/g/:slug -> /guides/:slug/, is checked with the other channels' rules in
# test_social_redirects.py.
GUIDE_RULE = "/li/g/:slug"


class LinkedinRedirects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = tomllib.loads(read("netlify.toml"))["redirects"]
        cls.li = [r for r in cls.rules if r["from"].startswith("/li") and r["from"] != GUIDE_RULE]

    def test_exactly_the_expected_sources(self):
        self.assertEqual(sorted(r["from"] for r in self.li), sorted(EXPECTED))

    def test_no_wildcard_or_splat(self):
        for r in self.rules:
            if r["from"].startswith("/li") and r["from"] != GUIDE_RULE:
                self.assertNotIn("*", r["from"])
                self.assertNotIn(":", r["from"])
                self.assertNotIn(":splat", r["to"])
        self.assertFalse([r for r in self.rules if r["from"] in ("/li/*", "/li", "/li/", "/*/")])

    def test_each_is_a_302_to_an_existing_page_with_the_utm_tags(self):
        for r in self.li:
            slug = r["from"].rsplit("/", 1)[1]
            self.assertEqual(r["status"], 302, r["from"])
            self.assertNotIn("force", r)
            u = urlsplit(r["to"])
            self.assertEqual(u.path, EXPECTED[r["from"]])
            self.assertTrue(page_of(u.path).exists(), u.path)
            self.assertEqual(
                parse_qs(u.query),
                {"utm_source": ["linkedin"], "utm_medium": ["social"], "utm_campaign": [f"li-{slug}"]},
                r["from"],
            )

    def test_rules_come_before_the_catch_all_404(self):
        order = [r["from"] for r in self.rules]
        last_li = max(i for i, f in enumerate(order) if f.startswith("/li/"))
        self.assertLess(last_li, order.index("/*"))

    def test_short_paths_are_not_in_sitemap_or_search_index(self):
        for rel in ("sitemap.xml", "search-index.json"):
            f = SITE / rel
            if f.exists():
                self.assertNotIn("/li/", f.read_text(encoding="utf-8"), rel)


if __name__ == "__main__":
    unittest.main()
