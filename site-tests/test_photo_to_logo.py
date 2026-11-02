"""The Photo to Logo page (/tools/photo-to-logo/): the JSON-LD says what the page shows, the worker and its two
libraries are linked with stamps, the page carries no ads and no inline styles, and the tool is counted and listed.
Design: docs/designs/photo-to-logo.md. The geometry is tested in netlify/tests/photo-to-logo.test.mjs."""
import html
import json
import re
import unittest

from common import ROOT, SITE, EMOJI, read_site

SLUG = "photo-to-logo"
PAGE = f"tools/{SLUG}/index.html"


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def graph(page):
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', page, re.S)
    return {n["@type"]: n for n in json.loads(m.group(1))["@graph"]}


class PhotoToLogoPage(unittest.TestCase):
    def setUp(self):
        self.page = read_site(PAGE)

    def test_canonical_title_description_and_one_h1(self):
        p = self.page
        self.assertIn(f'<link rel="canonical" href="https://purplelink.llc/tools/{SLUG}/">', p)
        self.assertEqual(len(re.findall(r"<h1[ >]", p)), 1)
        title = html.unescape(re.search(r"<title>(.*?)</title>", p).group(1))
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)">', p).group(1))
        self.assertLessEqual(len(title), 65, title)
        self.assertLessEqual(len(desc), 160, desc)
        self.assertIn("never uploaded", desc)

    def test_schema_matches_the_visible_text(self):
        g = graph(self.page)
        for t in ("WebApplication", "HowTo", "FAQPage", "BreadcrumbList"):
            self.assertIn(t, g)
        howto = self.page.split('class="tool-howto"')[1].split("</ol>")[0]
        visible = [(html.unescape(a), html.unescape(b)) for a, b in re.findall(r"<li><strong>(.*?)\.</strong> (.*?)</li>", howto)]
        self.assertEqual(visible, [(s["name"], s["text"]) for s in g["HowTo"]["step"]])
        faq = self.page.split('class="tool-faq"')[1].split("</section>")[0]
        shown = [(text(q), text(a)) for q, a in re.findall(r'<summary>(.*?)</summary><div class="faq-body">(.*?)</div>', faq)]
        self.assertEqual(shown, [(q["name"], q["acceptedAnswer"]["text"]) for q in g["FAQPage"]["mainEntity"]])
        self.assertEqual(g["FAQPage"]["mainEntity"][0]["name"], "Is my photo uploaded?")

    def test_worker_and_libraries_are_linked_with_stamps(self):
        p = self.page
        self.assertRegex(p, r'<link rel="prefetch" as="script" data-logo-worker href="/tools/photo-to-logo/logo-worker\.js\?v=[0-9a-f]+">')
        self.assertRegex(p, r'<link rel="prefetch" as="script" data-logo-mask href="/tools/photo-to-logo/logo-mask\.js\?v=[0-9a-f]+">')
        self.assertRegex(p, r'<script src="/tools/photo-to-logo/logo-geometry\.js\?v=[0-9a-f]+" defer>')
        self.assertRegex(p, r'<script src="/tools/photo-to-logo/photo-to-logo\.js\?v=[0-9a-f]+" defer>')
        self.assertRegex(p, r'<link rel="stylesheet" href="/tools/photo-to-logo/photo-to-logo\.css\?v=[0-9a-f]+">')
        worker = read_site(f"tools/{SLUG}/logo-worker.js")
        self.assertIn('importScripts("/tools/photo-to-logo/logo-geometry.js?v="', worker)
        self.assertIn('"/tools/photo-to-logo/logo-mask.js?v="', worker)
        for f in ("sample-raven.webp", "example-raven.jpg"):
            self.assertTrue((SITE / "tools" / SLUG / f).is_file(), f)
        self.assertIn('data-src="/tools/photo-to-logo/sample-raven.webp"', p)

    def test_hard_constraints(self):
        p = self.page
        self.assertNotRegex(p, r"\sstyle=")
        self.assertNotIn("adsbygoogle", p, "the page handles people's photos and carries no ads")
        self.assertNotIn("ethicalads", p.lower())
        self.assertIsNone(EMOJI.search(text(p)))
        self.assertIn("The photo is never uploaded.", text(p))
        js = read_site(f"tools/{SLUG}/photo-to-logo.js")
        self.assertNotIn(".style.", js, "colours are classes, not inline styles (CSP)")
        self.assertNotIn("createObjectURL(", js.split("function save")[0], "object URLs only for downloads: img-src has no blob:")
        og = re.search(r'<meta property="og:image" content="https://purplelink\.llc/([^"]+)"', p).group(1)
        self.assertTrue((SITE / og).is_file(), og)
        self.assertNotIn("purplelink-card.png", og)

    def test_counted_listed_and_linked(self):
        counts = (ROOT / "netlify" / "lib" / "tool-counts.mjs").read_text()
        self.assertIn(f'"{SLUG}"', counts)
        index = read_site("tools/index.html")
        self.assertIn(f'<a class="tool-card" href="/tools/{SLUG}/">', index)
        self.assertIn(f'"url": "https://purplelink.llc/tools/{SLUG}/"', index)
        self.assertIn(f'href="/tools/{SLUG}/"', read_site("tools/png-to-ico/index.html"))
        self.assertIn(f"https://purplelink.llc/tools/{SLUG}/", read_site("sitemap.xml"))


if __name__ == "__main__":
    unittest.main()
