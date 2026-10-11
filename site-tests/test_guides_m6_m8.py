import re
import unittest
from common import SITE, ORIGIN, EMOJI, read_site, page_of, canonical, jsonld_blocks, walk, meta, main_text
import json

GUIDES = ["/guides/before-you-paste-client-notes-into-chatgpt/", "/guides/what-ai-tools-leave-on-your-mac/"]
ARTICLE_TYPES = {"Article", "BlogPosting", "TechArticle", "NewsArticle"}


class NewGuides(unittest.TestCase):
    def each(self):
        for u in GUIDES:
            f = page_of(u)
            self.assertTrue(f.is_file(), u)
            yield u, f.read_text(encoding="utf-8")

    def test_canonical_is_live_url(self):
        for u, t in self.each():
            self.assertEqual(canonical(t), ORIGIN + u)

    def test_json_ld_parses_and_article_has_dates(self):
        for u, t in self.each():
            blocks = jsonld_blocks(t)
            self.assertTrue(blocks, u)
            arts = [d for b in blocks for d in walk(b) if (d.get("@type") in ARTICLE_TYPES or (isinstance(d.get("@type"), list) and ARTICLE_TYPES & set(d["@type"])))]
            self.assertTrue(arts, f"{u} has no Article JSON-LD")
            for a in arts:
                self.assertTrue(a.get("datePublished"), u)
                self.assertTrue(a.get("dateModified"), u)

    def test_listed_everywhere(self):
        index = read_site("guides/index.html")
        llms = read_site("llms.txt")
        sitemap = read_site("sitemap.xml")
        search = {r["u"] for r in json.loads(read_site("search-index.json"))}
        for u in GUIDES:
            self.assertIn(f'href="{u}"', index, f"guides index: {u}")
            self.assertIn(ORIGIN + u, llms, f"llms.txt: {u}")
            self.assertIn(f"<loc>{ORIGIN}{u}</loc>", sitemap, f"sitemap: {u}")
            self.assertIn(u, search, f"search-index: {u}")

    def test_og_image_exists(self):
        for u, t in self.each():
            img = meta(t, "og:image")
            self.assertTrue(img and img.startswith(ORIGIN + "/assets/og/"), f"{u}: {img}")
            self.assertTrue((SITE / img[len(ORIGIN):].lstrip("/")).is_file(), img)

    def test_no_em_dash_or_emoji_in_main_text(self):
        for u, t in self.each():
            text = main_text(t)
            self.assertGreater(len(text), 500, u)
            self.assertNotIn("—", text, f"em dash in {u}")
            self.assertIsNone(EMOJI.search(text), f"emoji in {u}")
