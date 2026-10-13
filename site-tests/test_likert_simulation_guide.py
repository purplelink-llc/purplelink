import html
import re
import unittest
from pathlib import Path
from common import ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk

URL = "/guides/simulate-likert-data-for-power-analysis/"
FX = Path(__file__).resolve().parent / "fixtures" / "likert_simulation"


class LikertSimulationGuide(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")
        self.blocks = [
            html.unescape(m).rstrip("\n")
            for m in re.findall(r"<pre><code>(.*?)</code></pre>", self.text, re.S)
        ]

    def test_exists_with_canonical(self):
        self.assertTrue(page_of(URL).is_file())
        self.assertEqual(canonical(self.text), ORIGIN + URL)

    def test_title_under_60(self):
        title = re.search(r"<title>(.*?)</title>", self.text).group(1)
        self.assertLess(len(title), 60)

    def test_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)

    def test_no_inline_style(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")

    def test_no_em_dash_or_emoji(self):
        self.assertNotIn("—", self.text)
        self.assertIsNone(EMOJI.search(self.text))

    def test_json_ld(self):
        types = {d.get("@type") for b in jsonld_blocks(self.text) for d in walk(b)}
        for t in ("Article", "BreadcrumbList", "FAQPage"):
            self.assertIn(t, types)

    def test_faq_json_ld_matches_visible_text(self):
        visible = html.unescape(re.sub(r"<[^>]+>", "", self.text))
        visible = re.sub(r"\s+", " ", visible)
        n = 0
        for b in jsonld_blocks(self.text):
            for d in walk(b):
                if d.get("@type") == "Question":
                    n += 1
                    self.assertIn(d["name"], visible)
                    self.assertIn(d["acceptedAnswer"]["text"], visible)
        self.assertTrue(3 <= n <= 4)

    def test_internal_links_resolve(self):
        hrefs = set(re.findall(r'href="(/[^"#?]*)', self.text))
        bad = [h for h in hrefs if h.endswith("/") and h != "/" and not page_of(h).is_file()]
        self.assertEqual(bad, [])

    def test_contextual_links(self):
        for dst in ("/guides/methodology-problems-peer-reviewers-flag/", "/tools/reproducibility-checker/"):
            self.assertIn('href="%s"' % dst, self.text)

    def test_inbound_link_from_guides_index(self):
        self.assertIn('href="%s"' % URL, page_of("/guides/").read_text(encoding="utf-8"))

    def test_integrity_statement(self):
        self.assertIn("Simulated data is not data about people.", self.text)
        self.assertIn("do not place results from it in a results section", self.text)
        self.assertIn("<code>synthetic_</code> filename prefix", self.text)

    def test_r_snippet_flagged_unexecuted(self):
        self.assertIn("this snippet was not executed and I show no output for it", self.text)

    def test_code_and_outputs_match_fixtures(self):
        for name in (
            "simulate_likert.py",
            "simulate_likert_output.txt",
            "synthetic_trust_intent_head.csv",
            "r_snippet_not_executed.R",
            "power_sim.py",
            "power_sim_output.txt",
        ):
            expected = (FX / name).read_text(encoding="utf-8").rstrip("\n")
            self.assertIn(expected, self.blocks, name)

    def test_quoted_numbers_appear_in_fixtures(self):
        out = (FX / "simulate_likert_output.txt").read_text() + (FX / "power_sim_output.txt").read_text()
        for n in ("0.337", "0.325", "0.796", "0.801", "0.701", "0.709", "0.447", "0.053", "79.4"):
            self.assertIn(n, out)

    def test_csv_head_marks_synthetic(self):
        head = (FX / "synthetic_trust_intent_head.csv").read_text().splitlines()
        self.assertTrue(head[0].endswith(",synthetic"))
        self.assertTrue(all(r.endswith(",True") for r in head[1:]))
        self.assertIn('"synthetic_trust_intent.csv"', (FX / "simulate_likert.py").read_text())


if __name__ == "__main__":
    unittest.main()
