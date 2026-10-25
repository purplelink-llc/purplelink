"""The "Write to Ben" support box: markup is current, topics match the function's allowlist,
no inline styles or scripts, the no-JS fallback is a visible mailto link, privacy names it."""
import re
import subprocess
import sys
import unittest

from common import EMOJI, ROOT, read, read_site

PAGES = ["support", "moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "panely", "summonly", "vitae", "batterymeter", "haea"]


def function_topics():
    src = read("netlify/functions/support-message.mjs")
    body = re.search(r"export const TOPICS = \{(.*?)\};", src, re.S).group(1)
    return set(re.findall(r'^\s*"?([a-z-]+)"?:', body, re.M))


class SupportBox(unittest.TestCase):
    def test_markup_is_current(self):
        r = subprocess.run([sys.executable, "scripts/apply_support_box.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_topics_match_function(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import apply_support_box
        self.assertEqual(set(apply_support_box.TOPICS), function_topics())

    def test_each_page_has_one_box_script_and_mailto(self):
        for slug in PAGES:
            html = read_site(f"{slug}/index.html")
            self.assertEqual(html.count("data-support-box"), 1, slug)
            self.assertRegex(html, r'<script src="/support-box\.js\?v=[0-9a-f]+" defer>', slug)
            box = html[html.index("<!-- support-box:start -->"):html.index("<!-- support-box:end -->")]
            self.assertIn('href="mailto:ben@purplelink.llc?subject=Support', box, slug)
            self.assertRegex(box, r"<form[^>]*\shidden", slug)
            self.assertNotRegex(box, r"\sstyle\s*=", slug)
            self.assertNotRegex(box, r"\son[a-z]+\s*=", slug)
            self.assertIn('role="status" aria-live="polite"', box, slug)
            self.assertRegex(box, r'<label for="sb-email">', slug)
            self.assertRegex(box, r'<label for="sb-message">', slug)
            for field in ("email", "message"):
                self.assertIn(f'aria-describedby="sb-{field}-hint sb-{field}-error"', box, slug)
            self.assertIsNone(EMOJI.search(box), slug)
            self.assertNotIn("—", box, slug)

    def test_topic_presets(self):
        for slug in PAGES[1:]:
            self.assertIn(f'data-support-topic="{slug}"', read_site(f"{slug}/index.html"), slug)

    def test_not_in_footer_or_everywhere(self):
        self.assertNotIn("data-support-box", read_site("index.html"))
        self.assertNotIn("data-support-box", read_site("privacy/index.html"))

    def test_script_has_no_inline_style_or_storage(self):
        js = read("site/support-box.js")
        self.assertNotRegex(js, r"\.style\.|localStorage|sessionStorage|document\.cookie|innerHTML")
        self.assertNotIn("—", js)

    def test_privacy_names_the_form(self):
        html = read_site("privacy/index.html")
        self.assertIn('id="support-form"', html)
        self.assertRegex(html, r"support form.*?Resend", )


if __name__ == "__main__":
    unittest.main()
