"""German, Japanese and Simplified Chinese ModernTex pages and how-tos (2026-10-29).

The four ModernTex pages (en, de, ja, zh-Hans) must point at each other with reciprocal hreflang, in the page
head and in sitemap.xml. The Chinese pages must not load anything from Google, whose services are blocked in
mainland China. Every localized page keeps the price in USD, carries its own lang and canonical, and stays out
of the English search index.
"""
import re
import unittest
from html.parser import HTMLParser
from common import ORIGIN, SITE, EMOJI, canonical, jsonld_blocks, main_text, meta, read_site, walk

# url path -> (html lang, how the page names itself in hreflang)
PRODUCT_PAGES = {
    "/moderntex/": "en",
    "/de/moderntex/": "de",
    "/ja/moderntex/": "ja",
    "/zh-cn/moderntex/": "zh-Hans",
}
EXPECTED_ALTERNATES = {
    "de": ORIGIN + "/de/moderntex/",
    "ja": ORIGIN + "/ja/moderntex/",
    "zh-Hans": ORIGIN + "/zh-cn/moderntex/",
    "en": ORIGIN + "/moderntex/",
    "x-default": ORIGIN + "/moderntex/",
}
GUIDES = {
    "/de/guides/latex-auf-dem-mac-einrichten/": "de",
    "/ja/guides/mac-nihongo-latex/": "ja",
    "/zh-cn/guides/mac-xelatex-ctex-zhongwen-lunwen/": "zh-Hans",
}
LOCALIZED = {**{u: l for u, l in PRODUCT_PAGES.items() if l != "en"}, **GUIDES}

GOOGLE = re.compile(
    r"google|gstatic|googlesyndication|doubleclick|googletagmanager|googletagservices|adsbygoogle|youtube|youtu\.be|ytimg",
    re.I)


class _NoScript(HTMLParser):
    """Collects the markup of a page with the contents of <script> and <style> left out."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.skip = 0
        self.tags = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif not self.skip:
            self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        if tag not in ("script", "style") and not self.skip:
            self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1


def tags_outside_scripts(text):
    p = _NoScript()
    p.feed(text)
    p.close()
    return p.tags


def page(url):
    return read_site(url.strip("/") + "/index.html")


def head_alternates(text):
    head = text.split("</head>", 1)[0]
    return dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', head))


class ProductPages(unittest.TestCase):
    def test_html_lang_and_self_canonical(self):
        for url, lang in PRODUCT_PAGES.items():
            t = page(url)
            self.assertIn(f'<html lang="{lang}">', t, url)
            self.assertEqual(canonical(t), ORIGIN + url, url)

    def test_hreflang_is_reciprocal_and_identical_on_all_four(self):
        for url in PRODUCT_PAGES:
            self.assertEqual(head_alternates(page(url)), EXPECTED_ALTERNATES, url)

    def test_each_hreflang_target_names_its_own_language(self):
        # The page behind hreflang="de" must be a German page, and so on, so a copy-paste slip cannot cross them.
        for hreflang, target in EXPECTED_ALTERNATES.items():
            if hreflang == "x-default":
                self.assertEqual(target, ORIGIN + "/moderntex/")
                continue
            self.assertIn(f'<html lang="{hreflang}">', page(target[len(ORIGIN):]), hreflang)

    def test_language_switcher_links_every_version(self):
        for url in PRODUCT_PAGES:
            t = page(url)
            m = re.search(r'<nav class="lang-switch"[^>]*>(.*?)</nav>', t, re.S)
            self.assertIsNotNone(m, url)
            for path in PRODUCT_PAGES:
                self.assertIn(f'href="{path}"', m.group(1), f"{url} switcher -> {path}")

    def test_price_stays_usd_and_json_ld_is_localized(self):
        for url, lang in PRODUCT_PAGES.items():
            blocks = jsonld_blocks(page(url))
            apps = [d for b in blocks for d in walk(b) if d.get("@type") == "SoftwareApplication"]
            self.assertEqual(len(apps), 1, url)
            offer = apps[0]["offers"]
            self.assertEqual((offer["price"], offer["priceCurrency"]), ("19.99", "USD"), url)
            # inLanguage on the app lists the languages of its interface (English and German, since 2.0); the
            # language of the page is on the WebPage and the FAQPage.
            self.assertEqual(apps[0]["inLanguage"], ["en", "de"], url)
            pages = [d for b in blocks for d in walk(b) if d.get("@type") == "WebPage"]
            self.assertEqual([p["inLanguage"] for p in pages], [lang], url)
            if lang != "en":
                faqs = [d for b in blocks for d in walk(b) if d.get("@type") == "FAQPage"]
                self.assertTrue(faqs and len(faqs[0]["mainEntity"]) >= 10, url)
                self.assertEqual(faqs[0]["inLanguage"], lang, url)

    def test_translated_head_and_cards(self):
        english = page("/moderntex/")
        for url, lang in PRODUCT_PAGES.items():
            if lang == "en":
                continue
            t = page(url)
            for key in ("og:title", "og:description", "twitter:title", "twitter:description"):
                self.assertTrue(meta(t, key), f"{url} {key}")
                self.assertNotEqual(meta(t, key), meta(english, key), f"{url} {key} is still English")
            self.assertEqual(meta(t, "og:url"), ORIGIN + url)
            self.assertTrue(meta(t, "og:locale"))
            img = meta(t, "og:image")
            self.assertTrue((SITE / img[len(ORIGIN):].lstrip("/")).is_file(), img)

    def test_usd_price_is_visible_on_each_page(self):
        for url in LOCALIZED:
            if url in GUIDES:
                continue
            self.assertIn("19.99", main_text(page(url)), url)

    def test_no_em_dash_emoji_or_inline_style(self):
        for url in LOCALIZED:
            t = page(url)
            text = main_text(t)
            self.assertNotIn("—", text, url)
            self.assertNotIn("―", text, url)
            self.assertFalse(EMOJI.search(text), url)
            self.assertEqual([tag for tag, attrs in tags_outside_scripts(t) if "style" in attrs], [], url)

    def test_no_version_number_to_go_stale(self):
        for url in PRODUCT_PAGES:
            if url == "/moderntex/":
                continue
            self.assertNotIn("softwareVersion", page(url), url)


class ChinesePagesLoadNothingFromGoogle(unittest.TestCase):
    def pages(self):
        files = sorted((SITE / "zh-cn").rglob("*.html"))
        self.assertTrue(len(files) >= 2)
        return files

    def test_no_google_or_youtube_reference_in_any_zh_cn_page(self):
        for f in self.pages():
            t = f.read_text(encoding="utf-8")
            # Visible text and JSON-LD may name Google Sheets in prose; what must not appear is a URL, a script,
            # a stylesheet, an iframe or a data attribute that fetches from Google.
            fetchers = re.findall(r'(?:src|href|data-[a-z-]+|content)="([^"]*)"', t)
            bad = [u for u in fetchers if GOOGLE.search(u) and not u.startswith("mailto:")]
            self.assertEqual(bad, [], f"{f.relative_to(SITE)}")
            self.assertNotIn("adsbygoogle", t, f.name)
            self.assertNotIn("data-youtube-id", t, f.name)
            self.assertNotIn("<iframe", t, f.name)

    def test_zh_cn_scripts_are_first_party_or_cloudflare(self):
        for f in self.pages():
            t = f.read_text(encoding="utf-8")
            for src in re.findall(r'<script[^>]+src="([^"]+)"', t):
                self.assertTrue(src.startswith("/") or src.startswith("https://static.cloudflareinsights.com/"), f"{f.name}: {src}")

    def test_scripts_loaded_by_zh_cn_pages_do_not_embed_google_urls(self):
        seen = set()
        for f in self.pages():
            for src in re.findall(r'<script[^>]+src="(/[^"?]+)', f.read_text(encoding="utf-8")):
                seen.add(src)
        for src in sorted(seen):
            js = (SITE / src.lstrip("/")).read_text(encoding="utf-8")
            hits = re.findall(r"https?://[^\s\"'`)]*(?:google|gstatic|doubleclick|googlesyndication)[^\s\"'`)]*", js, re.I)
            self.assertEqual(hits, [], src)


class Guides(unittest.TestCase):
    def test_lang_canonical_and_json_ld(self):
        for url, lang in GUIDES.items():
            t = page(url)
            self.assertIn(f'<html lang="{lang}">', t, url)
            self.assertEqual(canonical(t), ORIGIN + url, url)
            arts = [d for b in jsonld_blocks(t) for d in walk(b) if d.get("@type") == "TechArticle"]
            self.assertEqual(len(arts), 1, url)
            self.assertEqual(arts[0]["inLanguage"], lang)
            self.assertTrue(arts[0]["datePublished"] and arts[0]["dateModified"])

    def test_each_guide_links_the_localized_product_page(self):
        for url in GUIDES:
            code = url.split("/")[1]
            self.assertIn(f'href="/{code}/moderntex/"', page(url), url)

    def test_no_hreflang_without_a_true_twin(self):
        for url in GUIDES:
            self.assertEqual(head_alternates(page(url)), {}, url)

    def test_own_social_card_exists(self):
        for url in GUIDES:
            img = meta(page(url), "og:image")
            code, slug = url.strip("/").split("/")[0], url.strip("/").split("/")[-1]
            self.assertTrue(img.endswith(f"/assets/og/cards/{code}-guides-{slug}.jpg"), img)
            self.assertTrue((SITE / img[len(ORIGIN):].lstrip("/")).is_file(), img)

    def test_code_is_present_and_escaped(self):
        for url in GUIDES:
            t = page(url)
            self.assertGreaterEqual(t.count("<pre><code>"), 3, url)
            self.assertNotIn("<documentclass", t)
            self.assertIn("\\documentclass", t, url)


class SitemapRobotsLlmsSearch(unittest.TestCase):
    def test_sitemap_has_xhtml_alternates_for_all_four(self):
        xml = read_site("sitemap.xml")
        self.assertIn('xmlns:xhtml="http://www.w3.org/1999/xhtml"', xml)
        blocks = {m.group(1): m.group(2) for m in re.finditer(r"<url>\s*<loc>([^<]+)</loc>(.*?)</url>", xml, re.S)}
        for url in PRODUCT_PAGES:
            block = blocks.get(ORIGIN + url)
            self.assertIsNotNone(block, f"{url} not in sitemap")
            alts = dict(re.findall(r'<xhtml:link rel="alternate" hreflang="([^"]+)" href="([^"]+)"/>', block))
            self.assertEqual(alts, EXPECTED_ALTERNATES, url)

    def test_sitemap_alternates_match_the_page_heads(self):
        xml = read_site("sitemap.xml")
        for url in PRODUCT_PAGES:
            m = re.search(r"<loc>%s</loc>(.*?)</url>" % re.escape(ORIGIN + url), xml, re.S)
            alts = dict(re.findall(r'hreflang="([^"]+)" href="([^"]+)"', m.group(1)))
            self.assertEqual(alts, head_alternates(page(url)), url)

    def test_all_localized_pages_are_in_the_sitemap(self):
        xml = read_site("sitemap.xml")
        for url in LOCALIZED:
            self.assertIn(f"<loc>{ORIGIN}{url}</loc>", xml, url)

    def test_translations_stay_out_of_the_english_search_index(self):
        import json
        urls = [r["u"] for r in json.loads(read_site("search-index.json"))]
        self.assertEqual([u for u in urls if u.startswith(("/de/", "/ja/", "/zh-cn/"))], [])
        self.assertIn("/desk/", urls)  # the prefix rule must not swallow /desk/ (it starts with "de")

    def test_robots_txt_welcomes_chinese_and_ai_crawlers(self):
        robots = read_site("robots.txt")
        for agent in ("Baiduspider", "Bytespider", "GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot"):
            self.assertRegex(robots, r"User-agent: %s\nAllow: /\n" % agent, agent)
        self.assertNotRegex(robots, r"(?m)^Disallow:\s*/(de|ja|zh-cn)?/?\s*$")

    def test_llms_txt_lists_every_localized_page_under_moderntex(self):
        llms = read_site("llms.txt")
        m = re.search(r"^### ModernTex \(macOS\)\n(.*?)^### ", llms, re.S | re.M)
        section = m.group(1)
        for url in LOCALIZED:
            self.assertIn(ORIGIN + url, section, url)


if __name__ == "__main__":
    unittest.main()
