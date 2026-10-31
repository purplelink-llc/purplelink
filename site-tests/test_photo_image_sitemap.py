"""Licensable badge check, 2026-10-31: Search Console showed 0 of 333 sitemap images indexed, and every image was
listed under a photography place page that carries noindex. The image sitemap now lists each photograph under a
page Google may index (its country page, or a place page that opted in), and only licensable photographs carry
<image:license>. The same rule holds for the ImageObject JSON-LD on the pages."""
import json
import re
import unittest
from common import SITE, ORIGIN, has_noindex, jsonld_blocks, walk


def sitemap():
    return (SITE / "sitemap-images.xml").read_text(encoding="utf-8")


class ImageSitemap(unittest.TestCase):
    def test_every_listed_page_is_indexable(self):
        locs = re.findall(r"<loc>([^<]+)</loc>", sitemap())
        self.assertGreater(len(locs), 5)
        for url in locs:
            path = url.replace(ORIGIN, "").strip("/")
            text = (SITE / path / "index.html").read_text(encoding="utf-8")
            self.assertFalse(has_noindex(text), url)

    def test_atlanta_images_listed_under_their_own_page(self):
        block = sitemap().split("<loc>https://purplelink.llc/photography/united-states/atlanta/</loc>")[1].split("</url>")[0]
        self.assertIn("dsc-7629-1200.webp", block)
        self.assertIn("dsc-5165-1200.webp", block)

    def test_event_photographs_carry_no_license(self):
        data = json.loads((SITE / "photography" / "hub-data.json").read_text(encoding="utf-8"))
        events = {i["src"] for c in data["countries"] for p in c["places"] for i in p["images"] if i.get("event")}
        self.assertTrue(events)
        for img in re.findall(r"<image:image>.*?</image:image>", sitemap(), re.S):
            src = re.search(r"<image:loc>[^<]*?(/assets/[^<]+)</image:loc>", img).group(1)
            self.assertEqual(src in events, "<image:license>" not in img, src)

    def test_atlanta_jsonld_has_badge_fields(self):
        text = (SITE / "photography" / "united-states" / "atlanta" / "index.html").read_text(encoding="utf-8")
        objs = [o for b in jsonld_blocks(text) for o in walk(b) if isinstance(o, dict) and o.get("@type") == "ImageObject"]
        self.assertGreaterEqual(len(objs), 30)
        for o in objs:
            for k in ("contentUrl", "creator", "creditText", "copyrightNotice"):
                self.assertIn(k, o)
        licensed = [o for o in objs if "license" in o]
        self.assertTrue(all("acquireLicensePage" in o for o in licensed))


if __name__ == "__main__":
    unittest.main()
