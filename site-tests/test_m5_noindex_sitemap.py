import re
import unittest
import xml.etree.ElementTree as ET
from common import SITE, ORIGIN, read_site, has_noindex, sitemap_locs, sitemap_paths

HIDDEN = ["/binnacle/", "/binnacle/terms/", "/budgetcast/", "/budgetcast/privacy/", "/watchlight/privacy/"]


class HiddenPages(unittest.TestCase):
    def test_noindex_and_not_in_sitemap(self):
        paths = sitemap_paths()
        for u in HIDDEN:
            text = (SITE / u.strip("/") / "index.html").read_text(encoding="utf-8")
            self.assertTrue(has_noindex(text), f"{u} should carry meta robots noindex")
            self.assertNotIn(u, paths, f"{u} must not be in sitemap.xml")


class Sitemap(unittest.TestCase):
    def test_well_formed(self):
        root = ET.fromstring((SITE / "sitemap.xml").read_bytes())
        self.assertTrue(root.tag.endswith("urlset"))

    def test_no_noindex_page_listed(self):
        bad = []
        for p in sorted(sitemap_paths()):
            f = SITE / p.strip("/") / "index.html"
            if f.is_file() and has_noindex(f.read_text(encoding="utf-8", errors="ignore")):
                bad.append(p)
        self.assertEqual(bad, [])

    def test_every_loc_maps_to_a_file(self):
        missing = []
        locs = sitemap_locs()
        self.assertGreater(len(locs), 100)
        for u in locs:
            self.assertTrue(u.startswith(ORIGIN), u)
            path = u[len(ORIGIN):].split("#")[0].split("?")[0]
            rel = path.strip("/")
            cands = [SITE / rel / "index.html", SITE / rel] if rel else [SITE / "index.html"]
            if path.endswith("/") or not rel:
                cands = [SITE / rel / "index.html"] if rel else [SITE / "index.html"]
            if not any(c.is_file() for c in cands):
                missing.append(u)
        self.assertEqual(missing, [])
