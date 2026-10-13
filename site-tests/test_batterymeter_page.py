import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from common import SITE, ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk, meta

URL = "/batterymeter/"
ZIP = SITE / "batterymeter" / "BatteryMeter-1.1.0.zip"


def text_of(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


class BatteryMeterPage(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")
        self.nodes = [d for b in jsonld_blocks(self.text) for d in walk(b)]

    def test_exists_canonical_title_description(self):
        self.assertEqual(canonical(self.text), ORIGIN + URL)
        title = html.unescape(re.search(r"<title>(.*?)</title>", self.text).group(1))
        self.assertLess(len(title), 60)
        self.assertIn("Free", title)
        desc = meta(self.text, "description")
        self.assertLess(len(desc), 155)
        self.assertEqual(meta(self.text, "og:url"), ORIGIN + URL)
        self.assertNotIn("noindex", self.text.split("</head>")[0])

    def test_one_h1_no_inline_style_no_emoji_no_em_dash(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIsNone(EMOJI.search(self.text))
        self.assertNotIn("—", self.text)
        self.assertNotIn("data-pf-gated", self.text)
        self.assertNotIn("netlify/functions", self.text)

    def test_json_ld(self):
        app = [d for d in self.nodes if d.get("@type") == "SoftwareApplication"][0]
        self.assertEqual(float(app["offers"]["price"]), 0)
        self.assertEqual(app["offers"]["priceCurrency"], "USD")
        self.assertEqual(app["applicationCategory"], "UtilitiesApplication")
        self.assertEqual(app["softwareVersion"], "1.1.0")
        self.assertEqual(app["operatingSystem"], "macOS 13.0 or later")
        self.assertEqual(app["fileSize"], "%d bytes" % ZIP.stat().st_size)
        self.assertEqual(app["downloadUrl"], ORIGIN + "/batterymeter/BatteryMeter-1.1.0.zip")
        types = {d.get("@type") for d in self.nodes}
        self.assertIn("BreadcrumbList", types)
        self.assertIn("FAQPage", types)

    def test_faq_matches_visible(self):
        faq = [d for d in self.nodes if d.get("@type") == "FAQPage"][0]
        ld = [(q["name"], q["acceptedAnswer"]["text"]) for q in faq["mainEntity"]]
        vis = [
            (text_of(m.group(1)), text_of(m.group(2)))
            for m in re.finditer(r'<details class="faq-item">\s*<summary>(.*?)</summary>\s*<div class="faq-body">(.*?)</div>', self.text, re.S)
        ]
        self.assertTrue(4 <= len(ld) <= 8)
        self.assertEqual(ld, vis)

    def test_internal_links_resolve(self):
        for h in set(re.findall(r'href="(/[^"#?]*)', self.text)):
            if h.endswith("/"):
                self.assertTrue(h == "/" or page_of(h).is_file(), h)
            else:
                self.assertTrue((SITE / h.lstrip("/")).exists() or "/media/" in h, h)

    def test_download_link_and_tracking(self):
        links = re.findall(r'<a [^>]*href="/batterymeter/BatteryMeter-1\.1\.0\.zip"[^>]*>', self.text)
        self.assertGreaterEqual(len(links), 2)
        for tag in links:
            self.assertIn('data-track="download"', tag)
            self.assertIn('data-track-meta="batterymeter"', tag)
        self.assertTrue(ZIP.is_file())

    def test_sha_and_size_match_file(self):
        data = ZIP.read_bytes()
        m = re.search(r'id="bm-sha">([0-9a-f]{64})<', self.text)
        self.assertEqual(m.group(1), hashlib.sha256(data).hexdigest())
        s = re.search(r'id="bm-size">([\d,]+) bytes<', self.text)
        self.assertEqual(int(s.group(1).replace(",", "")), len(data))

    def test_zip_contains_signed_app(self):
        self.assertTrue(zipfile.is_zipfile(ZIP))
        with zipfile.ZipFile(ZIP) as z:
            self.assertTrue(any(n.startswith("BatteryMeter.app/") for n in z.namelist()))
        if not shutil.which("codesign") or not shutil.which("ditto"):
            self.skipTest("codesign or ditto is not available on this machine")
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["ditto", "-x", "-k", str(ZIP), tmp], check=True)
            app = Path(tmp) / "BatteryMeter.app"
            self.assertTrue(app.is_dir())
            r = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_video_markup_references_media(self):
        for p in (
            "/batterymeter/media/batterymeter-promo-16x9.mp4",
            "/batterymeter/media/batterymeter-poster.webp",
            "/batterymeter/media/batterymeter-promo-9x16.mp4",
        ):
            self.assertIn(p, self.text)
        self.assertRegex(self.text, r"<video controls playsinline preload=\"none\" poster=\"/batterymeter/media/batterymeter-poster\.webp\"")

    def test_images_exist_and_samples_say_so(self):
        for src in re.findall(r'(?:src|srcset)="(/batterymeter/img/[^"\s,]+)', self.text):
            self.assertTrue((SITE / src.lstrip("/")).is_file(), src)
        for n in ("sample-draining", "sample-low", "sample-full"):
            alt = re.search(r'<img src="/batterymeter/img/%s-1120\.webp"[^>]*alt="([^"]*)"' % n, self.text).group(1)
            self.assertIn("Sample values", alt)

    def test_consumers_section(self):
        m = re.search(r'<section [^>]*aria-labelledby="power-h">(.*?)</section>', self.text, re.S)
        self.assertIsNotNone(m)
        body = text_of(m.group(1))
        self.assertIn("Using the most power", body)
        self.assertIn("relative score, not watts", body)
        self.assertIn("Force Quit asks first", body)
        self.assertIn("Cancel is the default", body)
        alt = re.search(r'<img src="/batterymeter/img/sample-consumers-1120\.webp"[^>]*alt="([^"]*)"', m.group(1)).group(1)
        self.assertIn("Sample values", alt)
        self.assertRegex(m.group(1), r'sample-consumers-1120\.webp"[^>]*width="1120" height="776" loading="lazy"')
        for n in ("sample-consumers-1120", "sample-consumers-560"):
            self.assertTrue((SITE / "batterymeter" / "img" / (n + ".webp")).is_file())

    def test_consumers_faq_and_no_network_claim(self):
        faq = [d for d in self.nodes if d.get("@type") == "FAQPage"][0]
        answers = {q["name"]: q["acceptedAnswer"]["text"] for q in faq["mainEntity"]}
        self.assertIn("Force Quit asks you to confirm first", answers["Can it force quit apps?"])
        self.assertIn("relative score, not watts", answers["Does the energy impact number mean watts?"])
        self.assertIn("makes no network connection", self.text)
        self.assertNotRegex(self.text, r"(?i)\b(uploads?|sends? (?:your|process)|phones? home)\b")

    def test_wired_in_hub_home_changelog(self):
        for rel in ("products/index.html", "index.html", "changelog/index.html"):
            self.assertIn('href="/batterymeter/"', (SITE / rel).read_text(encoding="utf-8"), rel)
        suite = (SITE / "suite" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("BatteryMeter", suite)


if __name__ == "__main__":
    unittest.main()
