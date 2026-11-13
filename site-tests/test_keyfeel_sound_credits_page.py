import re
import unittest

from common import SITE, page_of

URL = "/keyfeel/sound-credits/"
# Names as the app shows them (Keyfeel Profiles.swift): 17 recorded, 14 synthesized. Marble exists in both groups.
EXPECTED = [
    "Tactile", "Cherry MX Brown", "Dome", "IBM Model M",
    "Cat", "Dog", "Duck", "Boing", "Bubble pop", "Water drops",
    "Soft wood", "Glass and ceramic", "Marble (Calm)", "Kalimba", "Chimes", "Clickers", "Bubble wrap",
    "Blue Clack", "Brown Bump", "Red Linear", "Relay", "Deep Thock", "Creamy", "Marble (Thock)",
    "Typewriter", "Terminal", "Droplet", "Wood Block", "Glass Tap", "Pillow", "Felt",
]


class KeyfeelSoundCreditsPage(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")
        m = re.search(r"<table\b.*?</table>", self.text, re.S)
        self.assertIsNotNone(m)
        self.table = m.group(0)

    def test_one_row_per_built_in_sound(self):
        names = re.findall(r'<tbody>.*?</tbody>', self.table, re.S)[0]
        names = re.findall(r'<tr><th scope="row">(.*?)</th>', names)
        self.assertEqual(names, EXPECTED)

    def test_table_is_accessible(self):
        self.assertIn("<caption>", self.table)
        self.assertEqual(len(re.findall(r'<th scope="col">', self.table)), 4)
        self.assertIn('class="table-scroll', self.text)
        self.assertIn("Where each sound comes from", self.text)

    def test_unknowns_are_not_invented(self):
        cells = re.findall(r"<td>(.*?)</td>", self.table)
        self.assertTrue(any(c == "Not recorded" for c in cells))
        self.assertEqual(self.table.count("Made by the app (synthesized), not a recording."), 14)

    def test_existing_per_file_list_kept(self):
        self.assertGreaterEqual(len(re.findall(r"<li><strong>", self.text)), 70)

    def test_no_inline_style_and_no_version_number_promise(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")
        self.assertIn("Since version 1.8.0, the app also shows this", self.text)

    def test_stylesheet_has_no_color_scheme_rule_for_table(self):
        css = (SITE / "styles.css").read_text(encoding="utf-8")
        tail = css[css.index("Keyfeel sound credits: provenance table"):]
        self.assertNotIn("prefers-color-scheme", tail)


if __name__ == "__main__":
    unittest.main()
