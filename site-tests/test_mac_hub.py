import re
import unittest
from common import SITE, ORIGIN, EMOJI, read_site, page_of, canonical, jsonld_blocks, walk, meta

HUB = "/guides/mac/"


class MacHub(unittest.TestCase):
    def setUp(self):
        self.text = page_of(HUB).read_text(encoding="utf-8")

    def test_exists_with_canonical_and_title(self):
        self.assertTrue(page_of(HUB).is_file())
        self.assertEqual(canonical(self.text), ORIGIN + HUB)
        self.assertEqual(re.search(r"<title>(.*?)</title>", self.text).group(1), "Mac utility guides | Purplelink")
        self.assertNotIn("noindex", self.text.split("</head>")[0])

    def test_json_ld_collection_page_and_breadcrumb(self):
        nodes = [d for b in jsonld_blocks(self.text) for d in walk(b)]
        types = {d.get("@type") for d in nodes}
        self.assertIn("CollectionPage", types)
        self.assertIn("BreadcrumbList", types)
        lst = [d for d in nodes if d.get("@type") == "ItemList"][0]
        self.assertEqual(lst["numberOfItems"], len(lst["itemListElement"]))

    def test_links_valid(self):
        hrefs = re.findall(r'href="(/[^"#?]*)', self.text)
        bad = [h for h in set(hrefs) if h.endswith("/") and not page_of(h).is_file() and h != "/"]
        self.assertEqual(bad, [])
        items = [d["url"] for b in jsonld_blocks(self.text) for d in walk(b) if d.get("@type") == "ListItem" and "url" in d]
        for u in items:
            self.assertTrue(page_of(u.replace(ORIGIN, "")).is_file(), u)
            self.assertIn('href="%s"' % u.replace(ORIGIN, ""), self.text)

    def test_no_inline_style_or_emoji(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIsNone(EMOJI.search(self.text))

    def test_listed_on_guides_index_and_home(self):
        self.assertIn('href="/guides/mac/"', read_site("guides/index.html"))
        self.assertIn('href="/guides/mac/"', read_site("index.html"))


if __name__ == "__main__":
    unittest.main()
