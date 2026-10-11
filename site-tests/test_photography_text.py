import html
import json
import unittest
from common import ROOT, SITE, read


def esc(t):
    return html.escape(t, quote=True)


def variants(t):
    return {html.escape(t, quote=True), html.escape(t, quote=False), t}


class PhotographyText(unittest.TestCase):
    def test_more_paragraphs_rendered_once(self):
        data = json.loads(read("scripts/data/photo-places.json"))
        checked = 0
        for c in data["countries"]:
            targets = [(SITE / "photography" / c["slug"] / "index.html", c)]
            targets += [(SITE / "photography" / c["slug"] / p["slug"] / "index.html", p) for p in c["places"]]
            for path, entry in targets:
                if not entry.get("more"):
                    continue
                self.assertTrue(path.is_file(), str(path.relative_to(SITE)))
                text = path.read_text(encoding="utf-8")
                for para in entry["more"]:
                    n = max(text.count(v) for v in variants(para))
                    self.assertEqual(n, 1, f"{path.relative_to(SITE)}: paragraph appears {n} times: {para[:50]}")
                    checked += 1
        self.assertGreater(checked, 30)

    def test_generator_renders_more(self):
        src = read("scripts/gen_photo_hubs.py")
        self.assertIn("more_paras", src)
        self.assertIn('.get("more"', src)
