"""The guide "Free offline file converters for Mac" is listed since the Née launch (2026-11-02).

It is indexable, in the sitemap and the guides index, and links /nee/ once, in one short section that says Née is
available for $14.99 after a 7-day trial.
"""
import html
import re
import unittest

from common import SITE, ORIGIN, EMOJI, ROOT, page_of, canonical, jsonld_blocks, walk, has_noindex, read_site, sitemap_paths

SLUG = "free-offline-file-converters-mac"
URL = f"/guides/{SLUG}/"


def strip_tags(text, sep=" "):
    return html.unescape(re.sub(r"<[^>]+>", sep, text))


class ConvertersGuide(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")

    # ---- listed
    def test_indexable(self):
        self.assertFalse(has_noindex(self.text))
        self.assertIn('<meta name="robots" content="index, follow">', self.text)

    def test_in_sitemap(self):
        self.assertIn(URL, sitemap_paths())

    def test_linked_from_guides_index(self):
        self.assertIn(URL, read_site("guides/index.html"))

    def test_in_llms_full_page_list(self):
        src = (ROOT / "scripts" / "gen_llms_full.py").read_text(encoding="utf-8")
        self.assertIn(f'"guides/{SLUG}/"', src)

    # ---- the Née section
    def test_launch_marker_gone_and_nee_linked_once(self):
        self.assertNotIn("launch: link", self.text)
        article = re.search(r"<article.*?</article>", self.text, re.S).group(0)
        self.assertEqual(len(re.findall(r'href="/nee/"', article)), 1)

    def test_nee_named_in_one_section_only(self):
        body = re.search(r"<article.*?</article>", self.text, re.S).group(0)
        sections = re.split(r"(?=<h2>)", body)
        with_nee = [sec for sec in sections if "Née" in strip_tags(sec)]
        self.assertEqual(len(with_nee), 1)
        text = " ".join(strip_tags(with_nee[0]).split())
        self.assertIn("$14.99", text)
        self.assertIn("7-day trial", text)
        self.assertIn("available", text)
        self.assertNotIn("not released", text.lower())
        self.assertNotIn("planned", text.lower())

    # ---- page hygiene
    def test_canonical_and_one_h1(self):
        self.assertEqual(canonical(self.text), ORIGIN + URL)
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)

    def test_og_card_exists(self):
        m = re.search(r'property="og:image" content="([^"]+)"', self.text)
        self.assertIn(f"guides-{SLUG}.jpg", m.group(1))
        self.assertTrue((SITE / "assets" / "og" / "cards" / f"guides-{SLUG}.jpg").is_file())

    def test_no_inline_style_em_dash_or_emoji(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertNotIn("—", self.text)
        self.assertIsNone(EMOJI.search(self.text))

    def test_internal_links_resolve(self):
        hrefs = set(re.findall(r'href="(/[^"#?]*)', self.text))
        bad = [h for h in hrefs if h.endswith("/") and h != "/" and not page_of(h).is_file()]
        self.assertEqual(bad, [])

    def test_json_ld_and_faq_match_visible_text(self):
        faq = None
        types = set()
        for b in jsonld_blocks(self.text):
            for d in walk(b):
                types.add(d.get("@type"))
                if d.get("@type") == "FAQPage":
                    faq = d
        self.assertTrue({"Article", "BreadcrumbList", "FAQPage"} <= types)
        entities = faq["mainEntity"]
        self.assertTrue(5 <= len(entities) <= 7)
        for q in entities:
            m = re.search(r"<h3>%s</h3>\s*<p>(.*?)</p>" % re.escape(html.escape(q["name"], quote=True)), self.text, re.S)
            self.assertIsNotNone(m, q["name"])
            self.assertEqual(" ".join(strip_tags(m.group(1), "").split()), " ".join(q["acceptedAnswer"]["text"].split()))

    def test_states_which_tools_upload(self):
        body = strip_tags(self.text)
        for tool in ("compress", "File to Markdown", "Markdown to PDF"):
            self.assertIn(tool, body)
        self.assertIn("upload", body)

    def test_claims_checked_on_this_mac_are_stated(self):
        body = strip_tags(self.text)
        # the two limits readers most often get wrong
        self.assertIn("afconvert cannot write MP3", " ".join(body.split()))
        self.assertIn("cannot save it", body)


if __name__ == "__main__":
    unittest.main()
