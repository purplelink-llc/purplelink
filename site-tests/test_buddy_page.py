import html
import re
import unittest

from common import SITE, ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk, meta, read_site

URL = "/buddy/"
ZIP = "https://github.com/purplelink-llc/buddy/releases/latest/download/Buddy.zip"
REPO = "https://github.com/purplelink-llc/buddy"
NOT_AFFILIATED = (
    "Buddy is an independent open-source project by Purplelink LLC. It is not made by, affiliated with, "
    "or endorsed by Anthropic. Claude and Claude Code are trademarks of Anthropic."
)


def text_of(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


class BuddyPage(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")
        self.nodes = [d for b in jsonld_blocks(self.text) for d in walk(b)]

    def test_exists_canonical_title_description(self):
        self.assertEqual(canonical(self.text), ORIGIN + URL)
        title = html.unescape(re.search(r"<title>(.*?)</title>", self.text).group(1))
        self.assertLess(len(title), 60)
        self.assertLess(len(meta(self.text, "description")), 155)
        self.assertEqual(meta(self.text, "og:url"), ORIGIN + URL)
        self.assertTrue((SITE / "assets" / "og" / "buddy.png").is_file())
        self.assertNotIn("noindex", self.text.split("</head>")[0])

    def test_one_h1_no_inline_style_no_emoji_no_em_dash(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIsNone(EMOJI.search(self.text))
        self.assertNotIn("—", self.text)

    def test_json_ld(self):
        app = [d for d in self.nodes if d.get("@type") == "SoftwareApplication"][0]
        self.assertEqual(float(app["offers"]["price"]), 0)
        self.assertEqual(app["softwareVersion"], "0.6.0")
        self.assertEqual(app["operatingSystem"], "macOS 14.0 or later")
        self.assertEqual(app["downloadUrl"], ZIP)
        self.assertIn("BreadcrumbList", {d.get("@type") for d in self.nodes})

    def test_download_and_source_links(self):
        downloads = re.findall(r'<a [^>]*href="%s"[^>]*>' % re.escape(ZIP), self.text)
        self.assertGreaterEqual(len(downloads), 2)
        for tag in downloads:
            self.assertIn('data-track="download"', tag)
            self.assertIn('data-track-meta="buddy"', tag)
        self.assertIn('href="%s"' % REPO, self.text)

    def test_not_affiliated_statement_is_visible(self):
        self.assertIn(NOT_AFFILIATED, text_of(self.text))

    def test_access_section_keeps_every_item(self):
        m = re.search(r'<section [^>]*aria-labelledby="access-h">(.*?)</section>', self.text, re.S)
        body = text_of(m.group(1))
        for s in ("Claude Code events", "buddy-hook", "last 64 KB", "first 16 KB",
                  "Accessibility", "Automation", "Buddy uses the network for two things only", "Both can be turned off in Settings."):
            self.assertIn(s, body)

    def test_images_exist(self):
        srcs = re.findall(r'(?:src|srcset)="(/(?:buddy/img|assets)/[^"\s,]+)', self.text)
        self.assertTrue(srcs)
        for src in srcs:
            self.assertTrue((SITE / src.lstrip("/")).is_file(), src)

    def test_internal_links_resolve(self):
        for h in set(re.findall(r'href="(/[^"#?]*)', self.text)):
            if h.endswith("/"):
                self.assertTrue(h == "/" or page_of(h).is_file(), h)
            else:
                self.assertTrue((SITE / h.lstrip("/")).exists(), h)

    def test_listed_on_products_and_llms(self):
        self.assertIn('href="/buddy/"', read_site("products/index.html"))
        self.assertIn("### Buddy (macOS)", read_site("llms.txt"))


if __name__ == "__main__":
    unittest.main()
