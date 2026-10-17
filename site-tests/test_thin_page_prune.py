"""Thin-page prune, 2026-10-12: photography place pages are noindex,follow (the kits stay indexable by decision)
and out of sitemap.xml; the digest is crawlable so its noindex can be read."""
import re
import unittest
from common import SITE, ORIGIN, has_noindex, sitemap_paths

HUB_DIRS = {"calendars", "license"}


def place_pages():
    out = []
    for f in sorted((SITE / "photography").glob("*/*/index.html")):
        country = f.parent.parent.name
        if country in HUB_DIRS or f.parent.name == "success":
            continue
        out.append(f)
    return out


def kit_pages():
    return [SITE / "kits" / "index.html"] + [
        f for f in sorted((SITE / "kits").glob("*/index.html")) if f.parent.name not in ("success", "assets")]


class PhotographyPlaces(unittest.TestCase):
    def test_count(self):
        self.assertEqual(len(place_pages()), 31)

    def test_noindex_follow_and_not_in_sitemap(self):
        paths = sitemap_paths()
        for f in place_pages():
            text = f.read_text(encoding="utf-8")
            self.assertIn('<meta name="robots" content="noindex, follow">', text, f)
            url = "/" + f.parent.relative_to(SITE).as_posix() + "/"
            self.assertNotIn(url, paths, url)

    def test_hubs_stay_indexable_and_listed(self):
        paths = sitemap_paths()
        for u in ["/photography/", "/photography/iceland/", "/photography/license/", "/photography/calendars/"]:
            text = (SITE / u.strip("/") / "index.html").read_text(encoding="utf-8")
            self.assertFalse(has_noindex(text), u)
            self.assertIn(u, paths, u)

    def test_reachable_from_country_hub(self):
        for f in place_pages():
            hub = (f.parent.parent / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'href="/photography/{f.parent.parent.name}/{f.parent.name}/"', hub, f)

    def test_generator_emits_noindex_for_places(self):
        src = (SITE.parent / "scripts" / "gen_photo_hubs.py").read_text(encoding="utf-8")
        self.assertIn('robots="noindex, follow"', src)


class Kits(unittest.TestCase):
    """Ben's call on 2026-10-12: the kits stay indexable (the report suggested noindex)."""

    def test_kits_stay_indexable_and_in_sitemap(self):
        paths = sitemap_paths()
        pages = kit_pages()
        self.assertEqual(len(pages), 4)
        for f in pages:
            self.assertFalse(has_noindex(f.read_text(encoding="utf-8")), f)
            url = "/" + f.parent.relative_to(SITE).as_posix() + "/"
            self.assertIn(url, paths)

    def test_still_linked_from_products(self):
        text = (SITE / "products" / "index.html").read_text(encoding="utf-8")
        self.assertRegex(text, r'href="/kits/')


class DigestPolicy(unittest.TestCase):
    def test_robots_txt_does_not_disallow_digest(self):
        robots = (SITE / "robots.txt").read_text(encoding="utf-8")
        for ln in robots.splitlines():
            if ln.strip().lower().startswith("disallow:"):
                self.assertNotIn("/blog/digest", ln)

    def test_digest_archive_removed_and_redirected(self):
        # Removed 2026-10-17 before the AdSense re-review: no pages left, old URLs redirect.
        self.assertFalse((SITE / "blog" / "digest").exists())
        toml = (SITE.parent / "netlify.toml").read_text(encoding="utf-8")
        self.assertIn('from = "/blog/digest/*"', toml)
        self.assertIn('from = "/blog/digest/feed.xml"', toml)
        linking = [str(p.relative_to(SITE)) for p in SITE.rglob("*.html")
                   if 'href="/blog/digest' in p.read_text(encoding="utf-8", errors="ignore")]
        self.assertEqual(linking, [])

    def test_digest_not_in_sitemap(self):
        self.assertFalse([p for p in sitemap_paths() if p.startswith("/blog/digest")])


if __name__ == "__main__":
    unittest.main()
