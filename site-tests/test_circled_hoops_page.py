import html
import re
import unittest

from common import SITE, ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk, meta, read_site

URL = "/circled-hoops/"
PLAY = "https://circledhoops.com/?ref=purplelink"


def text_of(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


class CircledHoopsPage(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")
        self.nodes = [d for b in jsonld_blocks(self.text) for d in walk(b)]

    def test_exists_canonical_title_description(self):
        self.assertEqual(canonical(self.text), ORIGIN + URL)
        title = html.unescape(re.search(r"<title>(.*?)</title>", self.text).group(1))
        self.assertLess(len(title), 65)
        self.assertLess(len(meta(self.text, "description")), 155)
        self.assertEqual(meta(self.text, "og:url"), ORIGIN + URL)
        self.assertTrue((SITE / "assets" / "og" / "circled-hoops.png").is_file())
        self.assertNotIn("noindex", self.text.split("</head>")[0])

    def test_one_h1_no_inline_style_no_emoji_no_em_dash(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIsNone(EMOJI.search(self.text))
        self.assertNotIn("—", self.text)

    def test_json_ld(self):
        app = [d for d in self.nodes if d.get("@type") == "SoftwareApplication"][0]
        self.assertEqual(app["applicationCategory"], "GameApplication")
        self.assertEqual(app["operatingSystem"], "Web, iOS")
        self.assertEqual(app["url"], "https://circledhoops.com")
        self.assertEqual(float(app["offers"]["price"]), 0)
        self.assertEqual(app["offers"]["priceCurrency"], "USD")
        self.assertEqual(app["publisher"]["@type"], "Organization")
        self.assertEqual(app["publisher"]["name"], "Purplelink LLC")
        self.assertIn("BreadcrumbList", {d.get("@type") for d in self.nodes})

    def test_links_and_statements(self):
        self.assertGreaterEqual(self.text.count('href="%s"' % PLAY), 2)
        self.assertIn('href="https://circledhoops.com/privacy"', self.text)
        self.assertIn('href="https://circledhoops.com/terms"', self.text)
        body = text_of(self.text)
        self.assertIn("Not affiliated with the NBA or any team.", body)
        self.assertIn("The iPhone app is in App Store review.", body)
        self.assertIn("$0.99 a month", body)
        self.assertNotIn("apps.apple.com", self.text)

    def test_images_exist(self):
        srcs = re.findall(r'(?:src|srcset)="(/assets/[^"\s,]+)', self.text)
        self.assertTrue(srcs)
        for src in srcs:
            self.assertTrue((SITE / src.lstrip("/")).is_file(), src)

    def test_internal_links_resolve(self):
        for h in set(re.findall(r'href="(/[^"#?]*)', self.text)):
            if h.endswith("/"):
                self.assertTrue(h == "/" or page_of(h).is_file(), h)
            else:
                self.assertTrue((SITE / h.lstrip("/")).exists(), h)

    def test_listed_on_products_home_sitemap_and_llms(self):
        self.assertIn('href="/circled-hoops/"', read_site("products/index.html"))
        self.assertIn('href="/circled-hoops/"', read_site("index.html"))
        self.assertIn("<loc>https://purplelink.llc/circled-hoops/</loc>", read_site("sitemap.xml"))
        self.assertIn("### Circled Hoops (web and iOS)", read_site("llms.txt"))


if __name__ == "__main__":
    unittest.main()
