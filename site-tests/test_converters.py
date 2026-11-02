"""In-browser converter pages (/tools/heic-to-jpg/ and siblings, scripts/gen_converter_pages.py).

The JSON-LD has to say what the page shows (HowTo steps, FAQ), every page carries the shared shell and its worker
link, the slugs are counted, the index lists them, and the CSP gains 'wasm-unsafe-eval' and nothing broader.
Design: docs/designs/browser-file-converters.md."""
import html
import json
import re
import sys
import tomllib
import unittest

from common import ROOT, SITE, EMOJI, read_site

sys.path.insert(0, str(ROOT / "scripts"))
import gen_converter_pages as G  # noqa: E402

SLUGS = [p["slug"] for p in G.PAGES]


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def graph(page):
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', page, re.S)
    return {n["@type"]: n for n in json.loads(m.group(1))["@graph"]}


class ConverterPages(unittest.TestCase):
    def test_pages_exist_with_canonical_title_and_one_h1(self):
        for p in G.PAGES:
            page = read_site(f"tools/{p['slug']}/index.html")
            self.assertIn(f'<link rel="canonical" href="https://purplelink.llc/tools/{p["slug"]}/">', page, p["slug"])
            self.assertEqual(len(re.findall(r"<h1[ >]", page)), 1, p["slug"])
            self.assertIn(f"<title>{html.escape(p['title'])}</title>", page)
            self.assertLessEqual(len(p["description"]), 160, p["slug"])
            self.assertLessEqual(len(p["title"]), 65, p["slug"])

    def test_schema_matches_the_visible_text(self):
        for p in G.PAGES:
            page = read_site(f"tools/{p['slug']}/index.html")
            g = graph(page)
            for t in ("WebApplication", "HowTo", "FAQPage", "BreadcrumbList"):
                self.assertIn(t, g, p["slug"])
            visible_steps = re.findall(r"<li><strong>(.*?)\.</strong> (.*?)</li>", page.split('class="tool-howto"')[1].split("</ol>")[0])
            self.assertEqual([(html.unescape(a), html.unescape(b)) for a, b in visible_steps],
                             [(s["name"], s["text"]) for s in g["HowTo"]["step"]], p["slug"])
            faq = page.split('class="tool-faq"')[1].split("</section>")[0]
            visible = [(text(q), text(a)) for q, a in re.findall(r"<summary>(.*?)</summary><div class=\"faq-body\">(.*?)</div>", faq)]
            schema = [(q["name"], q["acceptedAnswer"]["text"]) for q in g["FAQPage"]["mainEntity"]]
            self.assertEqual(visible, schema, p["slug"])
            self.assertEqual(g["FAQPage"]["mainEntity"][0]["name"], "Are my files uploaded?")

    def test_shell_wiring_and_hard_constraints(self):
        for slug in SLUGS:
            page = read_site(f"tools/{slug}/index.html")
            self.assertIn(f'class="tool-app cv-app" data-convert="{slug}"', page)
            self.assertRegex(page, r'<link rel="prefetch" as="script" data-convert-worker href="/tools/convert/convert-worker\.js\?v=[0-9a-f]+">')
            self.assertRegex(page, r'<script src="/tools/convert/convert-core\.js\?v=[0-9a-f]+" defer>')
            self.assertRegex(page, r'<script src="/tools/convert/convert-shell\.js\?v=[0-9a-f]+" defer>')
            self.assertNotRegex(page, r"\sstyle=")
            self.assertNotIn("adsbygoogle", page, "the converters carry no ads: they handle people's photos")
            self.assertIsNone(EMOJI.search(text(page)), slug)
            self.assertIn("Nothing is uploaded.", page)
            og = re.search(r'<meta property="og:image" content="https://purplelink\.llc/([^"]+)"', page).group(1)
            self.assertTrue((SITE / og).is_file(), og)
            self.assertNotIn("purplelink-card.png", og, f"{slug}: render its card with gen_og_cards.py --only tools/{slug}")

    def test_core_table_matches_the_pages(self):
        core = read_site("tools/convert/convert-core.js")
        for p in G.PAGES:
            self.assertIn(f'"{p["slug"]}": {{', core)
        self.assertFalse((SITE / "tools" / "convert" / "index.html").exists(), "the shared folder is not a page")

    def test_slugs_are_counted_and_listed(self):
        counts = (ROOT / "netlify" / "lib" / "tool-counts.mjs").read_text()
        index = read_site("tools/index.html")
        for slug in SLUGS:
            self.assertIn(f'"{slug}"', counts)
            self.assertIn(f'<a class="tool-card" href="/tools/{slug}/">', index)
            self.assertIn(f'"url": "https://purplelink.llc/tools/{slug}/"', index)

    def test_csp_allows_wasm_and_nothing_broader(self):
        conf = tomllib.loads((ROOT / "netlify.toml").read_text())
        csp = next(h["values"]["Content-Security-Policy"] for h in conf["headers"]
                   if "Content-Security-Policy" in h.get("values", {}))
        script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
        self.assertIn("'wasm-unsafe-eval'", script_src)
        self.assertNotIn("'unsafe-eval'", csp)

    def test_vendored_decoder_has_license_and_readme(self):
        d = SITE / "assets" / "vendor" / "libheif-1.23.5"
        for f in ("libheif.js", "libheif.wasm", "LICENSE", "README.txt"):
            self.assertTrue((d / f).is_file(), f)
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", (d / "LICENSE").read_text())
        self.assertIn("/assets/vendor/libheif-1.23.5/", read_site("tools/convert/convert-worker.js"))


if __name__ == "__main__":
    unittest.main()
