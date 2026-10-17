"""Academic email signature tool: page wiring, no inline styles, and the signature logic (run under node):
ORCID check digit, escaping, URL allowlist, DOI normalisation. The logic lives in
site/tools/academic-email-signature/signature-core.js, a plain script that also runs without a browser."""
import html
import json
import re
import shutil
from html.parser import HTMLParser
import subprocess
import unittest

from common import ROOT, SITE, EMOJI, read_site

SLUG = "academic-email-signature"
PAGE = f"tools/{SLUG}/index.html"
CORE = SITE / "tools" / SLUG / "signature-core.js"

NODE_DRIVER = r"""
const fs = require("fs"), vm = require("vm");
const w = {};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), { window: w, URL });
const C = w.SignatureCore;
const out = {};
out.orcid = ["0000-0002-1825-0097", "0000-0001-5109-3700", "0000-0003-4967-747X", "https://orcid.org/0000000218250097",
  "0000-0002-1825-0098", "0000-0002-1825-009", "abcd-0002-1825-0097", "0000-0002-1825-0097X", ""].map(s => C.parseOrcid(s));
const evil = '"><script>alert(1)</script>';
const fields = { name: evil, pronouns: evil, title: evil, dept: evil, institution: evil, email: "a@b.edu", phone: evil,
  orcid: "0000-0002-1825-0097", scholar: "https://scholar.google.com/citations?user=abc", website: "https://example.edu/?a=1&b=\"2",
  paperTitle: evil, paperDoi: "10.1000/a\"b<c>", office: evil, hoursNote: evil, custom: evil };
out.builds = ["minimal", "classic", "compact", "twocol"].map(t => [true, false].map(icon => C.build(fields, { template: t, icon, accent: "#5b2a86" }).html)).flat();
out.badUrls = ["javascript:alert(1)", "data:text/html,x", "vbscript:x", "ftp://example.edu", "//evil.example", "https://user:pw@example.edu", "not a url", "10.1/x"].map(u => C.safeWebUrl(u));
out.goodUrls = ["example.edu/lab", "http://example.edu", "https://www.example.edu/a?b=c"].map(u => C.safeWebUrl(u));
out.doi = ["doi:10.1000/xyz123", "https://doi.org/10.1000/xyz123", "https://dx.doi.org/10.1000/xyz123", "not a doi"].map(u => C.normalizeDoi(u));
out.scholar = ["https://scholar.google.com/citations?user=abc", "https://evil.example/scholar.google.com", "https://scholar.google.co.uk/citations?user=x"].map(u => C.parseScholar(u).ok);
out.badLink = C.build({ name: "A", website: "javascript:alert(1)", orcid: "0000-0002-1825-0098", email: "x" }, {}).errors;
out.empty = C.build({}, {}).empty;
out.text = C.build({ name: "Alex", title: "PhD Candidate", email: "a@b.edu" }, {}).text;
out.contrast = [C.contrastOnWhite("#ffffff"), C.contrastOnWhite("#000000"), C.contrastOnWhite("#5b2a86")];
console.log(JSON.stringify(out));
"""


class PageScan(HTMLParser):
    """Collects visible text, JSON-LD blocks, and the attributes of every tag inside <main>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.ld = []
        self.main_tags = []
        self._in_main = False
        self._skip = 0
        self._ld = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "main":
            self._in_main = True
        if self._in_main:
            self.main_tags.append((tag, d))
        if tag in ("script", "style"):
            self._skip += 1
            self._ld = tag == "script" and d.get("type") == "application/ld+json"
            if self._ld:
                self.ld.append("")

    def handle_endtag(self, tag):
        if tag == "main":
            self._in_main = False
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
            self._ld = False

    def handle_data(self, data):
        if self._ld:
            self.ld[-1] += data
        elif not self._skip:
            self.text.append(data)


def scan(page):
    s = PageScan()
    s.feed(page)
    s.close()
    return s


def run_core():
    p = subprocess.run(["node", "-e", NODE_DRIVER, str(CORE)], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class AcademicSignaturePage(unittest.TestCase):
    def setUp(self):
        self.page = read_site(PAGE)

    def test_head_and_schema(self):
        self.assertIn('<link rel="canonical" href="https://purplelink.llc/tools/academic-email-signature/">', self.page)
        self.assertTrue((SITE / "assets/og/academic-email-signature.png").is_file())
        graph = json.loads(scan(self.page).ld[0])["@graph"]
        self.assertEqual({g["@type"] for g in graph}, {"WebApplication", "FAQPage", "BreadcrumbList"})

    def test_no_inline_styles_or_handlers_in_page_markup(self):
        tags = scan(self.page).main_tags
        self.assertGreater(len(tags), 50)
        for tag, attrs in tags:
            self.assertNotIn("style", attrs, tag)
            self.assertFalse([k for k in attrs if k.startswith("on")], tag)

    def test_copy_is_plain(self):
        text = " ".join(scan(self.page).text)
        self.assertNotRegex(text, EMOJI)
        self.assertNotIn("\u2014", text)
        self.assertNotIn("\u2013", text)

    def test_registered_everywhere(self):
        self.assertIn("/tools/academic-email-signature/", read_site("tools/index.html"))
        self.assertIn("/tools/academic-email-signature/", read_site("sitemap.xml"))
        self.assertIn("/tools/academic-email-signature/", read_site("llms.txt"))
        self.assertIn("academic-email-signature", read_site("search-index.json"))
        self.assertTrue((SITE / "assets/tool-shots/academic-email-signature.webp").is_file())
        self.assertTrue((SITE / "assets/orcid-id-16.png").is_file())

    def test_no_third_party_loads(self):
        for name in ("academic-email-signature.js", "signature-core.js", "academic-email-signature.css"):
            src = (SITE / "tools" / SLUG / name).read_text(encoding="utf-8")
            hits = [u for u in re.findall(r"https?://[^\s\"')]+", src) if "purplelink.llc" not in u and "orcid.org" not in u
                    and "scholar.google" not in u and "doi.org" not in u and "example" not in u and "w3.org" not in u]
            self.assertEqual(hits, [], name)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SignatureCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_core()

    def test_orcid_check_digit(self):
        ok = [o.get("ok", False) for o in self.r["orcid"]]
        self.assertEqual(ok, [True, True, True, True, False, False, False, False, False])
        self.assertEqual(self.r["orcid"][3]["id"], "0000-0002-1825-0097")
        self.assertEqual(self.r["orcid"][2]["url"], "https://orcid.org/0000-0003-4967-747X")

    def test_user_input_is_escaped_in_every_layout(self):
        for h in self.r["builds"]:
            self.assertNotIn("<script", h)
            self.assertIn("&lt;script&gt;", h)
            # every href is http(s), mailto or tel
            for href in re.findall(r'href="([^"]*)"', h):
                self.assertRegex(href, r"^(https?://|mailto:|tel:)")
            # the DOI is percent-encoded, not raw
            self.assertIn("https://doi.org/10.1000/a%22b%3Cc%3E", h)

    def test_url_allowlist(self):
        self.assertEqual(self.r["badUrls"], [""] * 8)
        self.assertEqual(self.r["goodUrls"], ["https://example.edu/lab", "http://example.edu/", "https://www.example.edu/a?b=c"])

    def test_doi_and_scholar(self):
        self.assertEqual(self.r["doi"], ["https://doi.org/10.1000/xyz123"] * 3 + [""])
        self.assertEqual(self.r["scholar"], [True, False, True])

    def test_errors_and_empty(self):
        self.assertEqual(set(self.r["badLink"]), {"website", "orcid", "email"})
        self.assertTrue(self.r["empty"])

    def test_plain_text(self):
        self.assertEqual(self.r["text"], "-- \nAlex\nPhD Candidate\na@b.edu")

    def test_contrast(self):
        self.assertAlmostEqual(self.r["contrast"][0], 1.0, places=1)
        self.assertAlmostEqual(self.r["contrast"][1], 21.0, places=0)
        self.assertGreater(self.r["contrast"][2], 7)


if __name__ == "__main__":
    unittest.main()
