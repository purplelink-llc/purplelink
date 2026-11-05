""""Send to my Mac" (docs/designs/send-to-mac.md): the stamped markup is current, the head script runs before the
first paint, the block starts hidden with a visible label, an unticked box and a status region, its products match the
function's templates, the privacy page names it, and no inline style or emoji slipped in."""
import re
import subprocess
import sys
import unittest

from common import EMOJI, ROOT, read, read_site

sys.path.insert(0, str(ROOT / "scripts"))
import apply_send_to_mac  # noqa: E402


def function_products():
    src = read("netlify/functions/send-to-mac.mjs")
    body = re.search(r"export const PRODUCTS = \{\n(.*?)\n\};", src, re.S).group(1)
    return set(re.findall(r'^  "?([a-z-]+)"?: \{', body, re.M))


class SendToMac(unittest.TestCase):
    def test_markup_is_current(self):
        r = subprocess.run([sys.executable, "scripts/apply_send_to_mac.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_products_match_function(self):
        self.assertEqual({slug for slug, _n, _d in apply_send_to_mac.PAGES.values()}, function_products())

    def test_head_script_is_blocking_and_before_the_stylesheets(self):
        for rel in apply_send_to_mac.PAGES:
            page = read_site(rel)
            head = page[: page.index("</head>")]
            m = re.search(r'<script src="/send-to-mac\.js(\?v=[0-9a-f]+)?"></script>', head)
            self.assertIsNotNone(m, rel)
            self.assertLess(head.index("/theme.js"), m.start(), rel)
            self.assertLess(m.start(), head.index('rel="stylesheet"'), rel)
            self.assertEqual(page.count("/send-to-mac.js"), 1, rel)

    def test_block_is_hidden_accessible_and_opt_in_is_unticked(self):
        for rel, (slug, _name, download) in apply_send_to_mac.PAGES.items():
            page = read_site(rel)
            box = page[page.index("<!-- send-to-mac:start -->"):page.index("<!-- send-to-mac:end -->")]
            self.assertRegex(box, r"<form[^>]*\sdata-send-to-mac[^>]*\shidden", rel)
            self.assertIn(f'data-product="{slug}"', box)
            self.assertRegex(box, r'<label[^>]*for="s2m-email"', rel)
            self.assertNotIn("visually-hidden", re.search(r"<label[^>]*for=\"s2m-email\"[^>]*>", box).group(0))
            checkbox = re.search(r'<input type="checkbox" name="news"[^>]*>', box).group(0)
            self.assertNotIn("checked", checkbox, rel)
            self.assertIn('role="status" aria-live="polite"', box, rel)
            self.assertIn('aria-describedby="s2m-note s2m-status"', box, rel)
            self.assertIn(f'href="{download}" data-s2m-anyway', box, rel)
            self.assertNotRegex(box, r"\sstyle\s*=", rel)
            self.assertNotRegex(box, r"\son[a-z]+\s*=", rel)
            self.assertIsNone(EMOJI.search(box), rel)
            self.assertNotIn("—", box, rel)
            # In the hero, after the buttons and the sentences that belong to them (trial-buy-path.test.mjs keeps the
            # Suite sentence directly under the buttons).
            self.assertLess(page.index('class="app-hero-actions"'), page.index("<!-- send-to-mac:start -->"), rel)
            self.assertLess(page.index("<!-- send-to-mac:end -->"), page.index('class="app-hero-window'), rel)

    def test_css_shows_the_block_only_under_the_class(self):
        css = read("site/styles.css")
        self.assertIn(".send-to-mac[hidden] { display: none; }", css)
        self.assertIn(":root.s2m .send-to-mac[hidden] { display: block; }", css)
        shows = re.findall(r"([^\n{}]*\.send-to-mac(?![\w-])[^\n{}]*)\{[^}]*display:\s*block", css)
        self.assertTrue(shows)
        for sel in shows:
            self.assertIn(":root.s2m", sel)

    def test_hero_test_layout_places_the_block(self):
        # exp-moderntex-hero.js arm B flattens the hero copy and orders every child (site/buy.css); without an order the
        # block jumps above the app name on phones.
        self.assertRegex(read("site/buy.css"), r"\.exp-hero-shot \.send-to-mac \{ order: 5; \}")

    def test_not_on_other_pages(self):
        for rel in ("index.html", "keyfeel/index.html", "de/moderntex/index.html", "privacy/index.html"):
            self.assertNotIn("data-send-to-mac", read_site(rel), rel)
            self.assertNotIn("/send-to-mac.js", read_site(rel), rel)

    def test_script_has_no_inline_style_or_storage(self):
        js = read("site/send-to-mac.js")
        self.assertNotRegex(js, r"\.style\.|localStorage|sessionStorage|document\.cookie|innerHTML")
        self.assertNotIn("—", js)

    def test_trial_counters_skip_intercepted_clicks(self):
        for rel in ("site/analytics.js", "site/reddit-pixel.js", "site/site.js"):
            self.assertIn('getAttribute("data-s2m-intercept")', read(rel), rel)
        self.assertRegex(read("site/analytics.js"), r"var FUNNEL = /\^\([^)]*\bsend_to_mac\b")

    def test_privacy_names_the_form(self):
        privacy = read_site("privacy/index.html")
        self.assertIn('id="send-to-mac"', privacy)
        para = re.search(r'<p id="send-to-mac">(.*?)</p>', privacy, re.S).group(1)
        for words in ("Resend", "not stored", "click id", "confirm"):
            self.assertIn(words, para)


if __name__ == "__main__":
    unittest.main()
