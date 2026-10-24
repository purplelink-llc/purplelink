import html
import json
import re
import unittest

from common import SITE, ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk, meta

URL = "/batterymeter/"
# The appcast and zips are not in site/ any more: they live in the batterymeter-files Blobs store and are served by
# netlify/functions/batterymeter-download.mjs (see netlify/tests/batterymeter-download.test.mjs). The facts of the
# published 1.4.1 zip are pinned here so the page text still has to match them.
ZIP_SHA256 = "a0bd930f9ff7caabe538e15c7eb643ebc3b633cd4f937e2c24ec2d17d2dc0b2e"
ZIP_BYTES = 1344487
TOML = SITE.parent / "netlify.toml"


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
        self.assertEqual(app["softwareVersion"], "1.4.1")
        self.assertEqual(app["operatingSystem"], "macOS 13.0 or later")
        self.assertEqual(app["fileSize"], "%d bytes" % ZIP_BYTES)
        self.assertEqual(app["downloadUrl"], ORIGIN + "/batterymeter/BatteryMeter-1.4.1.zip")
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
        self.assertTrue(4 <= len(ld) <= 10)
        self.assertEqual(ld, vis)

    def test_internal_links_resolve(self):
        for h in set(re.findall(r'href="(/[^"#?]*)', self.text)):
            if h.endswith("/"):
                self.assertTrue(h == "/" or page_of(h).is_file(), h)
            else:
                self.assertTrue((SITE / h.lstrip("/")).exists() or "/media/" in h or  # release zips are served from Blobs
                             re.fullmatch(r"/batterymeter/BatteryMeter-[0-9.]+\.zip", h), h)

    def test_download_link_and_tracking(self):
        links = re.findall(r'<a [^>]*href="/batterymeter/BatteryMeter-1\.4\.1\.zip"[^>]*>', self.text)
        self.assertGreaterEqual(len(links), 2)
        for tag in links:
            self.assertIn('data-track="download"', tag)
            self.assertIn('data-track-meta="batterymeter"', tag)

    def test_sha_and_size_match_published_zip(self):
        m = re.search(r'id="bm-sha">([0-9a-f]{64})<', self.text)
        self.assertEqual(m.group(1), ZIP_SHA256)
        s = re.search(r'id="bm-size">([\d,]+) bytes<', self.text)
        self.assertEqual(int(s.group(1).replace(",", "")), ZIP_BYTES)

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
        self.assertNotIn("makes no network connection", self.text)
        self.assertNotIn("No network</h3>", self.text)
        self.assertNotIn("no network,", self.text)
        self.assertNotRegex(self.text, r"(?i)no network connection")
        self.assertNotRegex(self.text, r"(?i)\b(uploads?|sends? (?:your|process)|phones? home)\b")

    def test_update_check_privacy_statement(self):
        statement = "Once a day it fetches purplelink.llc/batterymeter/appcast.xml"
        self.assertIn(statement, self.text)
        self.assertIn("no account, no battery data and no list of processes", self.text)
        faq = [d for d in self.nodes if d.get("@type") == "FAQPage"][0]
        answers = {q["name"]: q["acceptedAnswer"]["text"] for q in faq["mainEntity"]}
        self.assertIn(statement, answers["Does it send anything?"])
        upd = answers["How does it update?"]
        for s in ("once a day", "asks before it installs", "signed", "1.1.0 or earlier", "by hand", "changelog"):
            self.assertIn(s, upd)
        self.assertIn("download the current version from this page", upd)
        self.assertIn('href="/changelog/"', self.text)
        for rel in ("privacy/index.html", "products/index.html",
                    "guides/check-mac-battery-health-voltage-and-cycle-count/index.html"):
            s = (SITE / rel).read_text(encoding="utf-8")
            for line in s.splitlines():
                if "BatteryMeter" in line:
                    self.assertNotIn("makes no network connection", line, rel)
        llms = (SITE / "llms.txt").read_text(encoding="utf-8")
        section = llms.split("### BatteryMeter", 1)[1].split("\n### ", 1)[0]
        self.assertNotIn("no network connection", section)
        self.assertIn("appcast.xml", section)

    def test_update_check_toggle_stated_everywhere(self):
        sentence = ("A menu item, Check for updates automatically, turns the daily check off. "
                    "With it off, the app makes no network request until you choose Check for updates.")
        faq = [d for d in self.nodes if d.get("@type") == "FAQPage"][0]
        answers = {q["name"]: q["acceptedAnswer"]["text"] for q in faq["mainEntity"]}
        self.assertIn(sentence, answers["Does it send anything?"])
        self.assertIn(sentence, text_of(self.text))
        self.assertIn(sentence, (SITE / "privacy" / "index.html").read_text(encoding="utf-8"))
        llms = (SITE / "llms.txt").read_text(encoding="utf-8")
        self.assertIn(sentence.replace("Check for updates.", "Check for updates."), llms)
        pages = [self.text, (SITE / "privacy" / "index.html").read_text(encoding="utf-8"), llms,
                 (SITE / "llms-full.txt").read_text(encoding="utf-8"),
                 (SITE / "products" / "index.html").read_text(encoding="utf-8"),
                 (SITE / "guides" / "check-mac-battery-health-voltage-and-cycle-count" / "index.html").read_text(encoding="utf-8")]
        for s in pages:
            self.assertNotRegex(s, r"(?i)no setting to turn the (daily )?check off")
            self.assertNotRegex(s, r"(?i)has no setting to turn")
        log = (SITE / "changelog" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<h2>BatteryMeter 1.4.1</h2>", log)
        self.assertLess(log.index("BatteryMeter 1.4.1"), log.index("BatteryMeter 1.2.1"))

    def test_download_line_matches_zip(self):
        self.assertIn(ZIP_SHA256, self.text)
        self.assertIn("{:,} bytes".format(ZIP_BYTES), self.text)
        self.assertIn("Version 1.4.1, released October 24, 2026", self.text)
        self.assertNotIn("404 KB", self.text)
        self.assertNotIn("464,618", self.text)

    def test_release_files_are_not_static_and_are_rewritten_to_the_function(self):
        folder = SITE / "batterymeter"
        self.assertEqual(sorted(p.name for p in folder.glob("*.zip")), [])
        self.assertFalse((folder / "appcast.xml").exists())
        toml = TOML.read_text(encoding="utf-8")
        for src, dst in (
            ("/batterymeter/appcast.xml", "/.netlify/functions/batterymeter-download?file=appcast.xml"),
            ("/batterymeter/BatteryMeter-*", "/.netlify/functions/batterymeter-download?file=BatteryMeter-:splat"),
        ):
            m = re.search(r'\[\[redirects\]\]\s*from = "%s"\s*to = "%s"\s*status = 200\s*force = true' % (re.escape(src), re.escape(dst)), toml)
            self.assertIsNotNone(m, src)
        self.assertNotIn('for = "/batterymeter/appcast.xml"', toml)

    def test_wired_in_hub_home_changelog(self):
        for rel in ("products/index.html", "index.html", "changelog/index.html"):
            self.assertIn('href="/batterymeter/"', (SITE / rel).read_text(encoding="utf-8"), rel)
        suite = (SITE / "suite" / "index.html").read_text(encoding="utf-8")
        # The shared footer lists every product, so check the page itself: the Suite does not include BatteryMeter.
        body = re.sub(r"<footer\b.*?</footer>", "", suite, flags=re.S | re.I)
        self.assertNotIn("BatteryMeter", body)


if __name__ == "__main__":
    unittest.main()
