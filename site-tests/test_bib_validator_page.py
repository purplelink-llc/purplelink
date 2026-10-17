"""BibTeX validator page: title and description lengths, the seeded-fault demo, no inline styles.
The demo's messages must match output saved from the tool's own validation code (fixtures/)."""
import html
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from common import ROOT, EMOJI, meta, jsonld_blocks, walk, read_site

PAGE = "tools/bib-validator/index.html"
FIX = Path(__file__).resolve().parent / "fixtures"


def demo_section(text):
    m = re.search(r'<section class="tool-howto bib-demo".*?</section>', text, re.S)
    assert m, "demo section missing"
    return m.group(0)


class BibValidatorPage(unittest.TestCase):
    def setUp(self):
        self.text = read_site(PAGE)
        self.fixture = json.loads((FIX / "bib_validator_demo_output.json").read_text())

    def test_title_and_description_length(self):
        title = html.unescape(re.search(r"<title>(.*?)</title>", self.text).group(1))
        self.assertLess(len(title), 60)
        self.assertIn("BibTeX Validator", title)
        desc = meta(self.text, "description")
        self.assertLess(len(desc), 155)
        for k, v in (("og:title", title), ("twitter:title", title),
                     ("og:description", desc), ("twitter:description", desc)):
            self.assertEqual(meta(self.text, k), v, k)
        self.assertEqual(meta(self.text, "twitter:image:alt"), title)

    def test_jsonld_parses(self):
        nodes = [d for b in jsonld_blocks(self.text) for d in walk(b)]
        self.assertIn("WebApplication", {d.get("@type") for d in nodes})

    def test_demo_input_matches_fixture(self):
        sec = html.unescape(demo_section(self.text))
        bib = (FIX / "bib_validator_demo.bib").read_text().rstrip()
        self.assertIn(bib, sec)

    def test_demo_messages_come_from_fixture(self):
        sec = html.unescape(demo_section(self.text))
        comments = [l for l in self.fixture["annotated_bib"].split("\n") if l.startswith("% [bib-validator]")]
        self.assertEqual(len(comments), 5)
        for c in comments:
            self.assertIn(c, sec)
        s = self.fixture["summary"]
        self.assertIn(f'{s["ok"]} OK, {s["warning"]} warnings, {s["error"]} errors, {s["total"]} entries total', sec)
        # the repeated key is flagged, and the one disclosed non-detection (the skipped entry) is still true
        keys = [e["key"] for e in self.fixture["entries"]]
        self.assertEqual(len(keys), 5)
        self.assertEqual(len(set(keys)), 4)
        self.assertEqual([e["duplicate_of"] for e in self.fixture["entries"]], ["", "", "", "", "ampel2023trust"])
        self.assertEqual(s["duplicate_keys"], 1)
        self.assertIn("DUPLICATE KEY", self.fixture["annotated_bib"])
        self.assertNotIn("does not check for duplicate keys", sec)
        self.assertEqual((FIX / "bib_validator_demo.bib").read_text().count("\n@"), 5)  # six entries in the file

    def test_copy_says_five_checks_and_duplicate_keys(self):
        self.assertIn("duplicate", meta(self.text, "description"))
        self.assertIn("It checks five things", self.text)
        self.assertNotIn("four things", self.text)

    def test_fixture_matches_live_tool_code(self):
        try:
            import bibtexparser  # noqa: F401
        except ImportError:
            self.skipTest("bibtexparser not installed")
        out = subprocess.run([sys.executable, str(FIX / "bib_validator_harness.py"), str(FIX / "bib_validator_demo.bib")],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), self.fixture)

    def test_links(self):
        for href in ("/guides/fix-bibtex-errors/", "/guides/build-bibtex-from-dois/"):
            self.assertIn(f'href="{href}"', demo_section(self.text))
            self.assertTrue((ROOT / "site" / href.strip("/") / "index.html").is_file())

    def test_no_inline_styles_or_emoji(self):
        self.assertIsNone(re.search(r'\sstyle\s*=', self.text))
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIsNone(EMOJI.search(demo_section(self.text)))


if __name__ == "__main__":
    unittest.main()
