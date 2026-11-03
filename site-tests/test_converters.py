"""In-browser converter pages (/tools/heic-to-jpg/ and siblings, scripts/gen_converter_pages.py).

The JSON-LD has to say what the page shows (HowTo steps, FAQ), every page carries the shared shell and its worker
link, the slugs are counted, the index lists them, and the CSP gains 'wasm-unsafe-eval' and nothing broader.
Design: docs/designs/browser-file-converters.md."""
import hashlib
import html
import json
import re
import sys
import tomllib
import unittest

from common import ROOT, SITE, EMOJI, STAMP, read_site

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
            self.assertRegex(page, r'<link rel="prefetch" as="script" data-convert-worker href="/tools/convert/convert-worker\.js' + STAMP + r'">')
            self.assertRegex(page, r'<script src="/tools/convert/convert-core\.js' + STAMP + r'" defer>')
            self.assertRegex(page, r'<script src="/tools/convert/convert-shell\.js' + STAMP + r'" defer>')
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

    def test_options_and_worker_libraries(self):
        for p in G.PAGES:
            page = read_site(f"tools/{p['slug']}/index.html")
            app = page.split('class="tool-app cv-app"')[1].split("</fieldset>")[0] if "<fieldset" in page else ""
            # Every control the shell reads is marked with data-opt; ids alone are not read any more.
            for ctl in re.findall(r"<(?:input|select)\b[^>]*>", app):
                if 'id="cv-file"' in ctl:
                    continue
                self.assertIn("data-opt=", ctl, f"{p['slug']}: {ctl}")
            for when in re.findall(r'data-show-when="([^"]+)"', page):
                key = when.split("=")[0]
                self.assertIn(f'data-opt="{key}"', page, f"{p['slug']}: shows on an option it does not have")
            libs = re.findall(r'<link rel="prefetch" as="script" data-convert-lib="([\w-]+)" href="([^"]+)">', page)
            self.assertEqual([k for k, _ in libs], p.get("libs", []), p["slug"])
            for _, href in libs:
                if href.endswith(".mjs"):
                    # fingerprint_assets.py stamps .js and .css only; the folder name carries pdf.js's version instead.
                    self.assertRegex(href, r"^/assets/vendor/pdfjs-\d+\.\d+\.\d+/[\w.]+\.mjs$")
                else:
                    self.assertRegex(href, r"^/assets/vendor/.+\.js" + STAMP + r"$", "stamped, so the worker never loads a stale copy")
                self.assertTrue((SITE / href.split("?")[0].lstrip("/")).is_file(), href)
            if len(p["outputs"]) == 1 and "<fieldset" in page:
                # the quality and fill controls show only while output=jpg, so a one-output page still names it
                self.assertIn(f'<input type="hidden" data-opt="output" value="{p["outputs"][0][0]}">', page, p["slug"])
            self.assertEqual('id="cv-one"' in page, bool(p.get("combine")), p["slug"])
            self.assertRegex(page, r'<script src="/assets/vendor/jszip/jszip\.min\.js' + STAMP + r'" defer>', "the worker's JSZip URL comes from this tag")

    def test_page_range_is_not_remembered(self):
        page = read_site("tools/pdf-to-jpg/index.html")
        field = re.search(r'<input type="text" id="cv-pages"[^>]*>', page).group(0)
        self.assertIn("data-nostore", field)
        self.assertIn('aria-describedby="cv-pages-hint"', field)
        self.assertIn('id="cv-pages-hint"', page)
        self.assertIn('data-show-when="scale=width"', read_site("tools/svg-to-png/index.html"))

    def test_page_side_pairs_do_not_claim_a_worker(self):
        for slug in ("pdf-to-jpg", "svg-to-png"):
            privacy = re.search(r'<p class="tool-privacy">(.*?)</p>', read_site(f"tools/{slug}/index.html")).group(1)
            self.assertNotIn("worker", privacy, slug)

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

    def test_vendored_pdfjs_is_complete(self):
        d = SITE / "assets" / "vendor" / "pdfjs-6.4.299"
        for f in ("pdf.min.mjs", "pdf.worker.min.mjs", "LICENSE", "README.txt", "wasm/jbig2.wasm", "wasm/openjpeg.wasm",
                  "wasm/qcms_bg.wasm", "wasm/LICENSE_JBIG2", "wasm/LICENSE_OPENJPEG", "wasm/LICENSE_QCMS",
                  "cmaps/LICENSE", "standard_fonts/LICENSE_FOXIT", "standard_fonts/LICENSE_LIBERATION", "iccs/LICENSE"):
            self.assertTrue((d / f).is_file(), f)
        self.assertIn("Apache License", (d / "LICENSE").read_text())
        readme = (d / "README.txt").read_text()
        for f in ("pdf.min.mjs", "pdf.worker.min.mjs", "wasm/jbig2.wasm", "wasm/openjpeg.wasm", "wasm/qcms_bg.wasm"):
            self.assertIn(hashlib.sha256((d / f).read_bytes()).hexdigest() + "  " + f, readme, f"{f} differs from the README hash")
        self.assertTrue(any((d / "cmaps").glob("*.bcmap")))


if __name__ == "__main__":
    unittest.main()
