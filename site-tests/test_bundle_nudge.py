"""The bundle line on the product pages (scripts/apply_bundle_nudge.py) stays current and honest."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "apply_bundle_nudge.py"

spec = importlib.util.spec_from_file_location("apply_bundle_nudge", SCRIPT)
nudge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nudge)

LINE = re.compile(re.escape(nudge.START) + r'<p class="buy-bundle">(.*?)</p>' + re.escape(nudge.END), re.S)
PRESSURE = re.compile(r"\b(today|now|hurry|limited|only \d|ends|expires|last chance|left)\b", re.I)


class BundleNudge(unittest.TestCase):
    def page(self, slug):
        return (ROOT / "site" / slug / "index.html").read_text(encoding="utf-8")

    def test_pages_are_current(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_app_page_has_the_line_with_the_real_percents(self):
        tiers = nudge.percents()
        self.assertEqual(tiers, {"2": 25, "3": 40})
        self.assertIn("lenses", nudge.PAGES)
        for slug in nudge.PAGES:
            m = LINE.search(self.page(slug))
            self.assertIsNotNone(m, slug)
            text = m.group(1)
            self.assertIn(f"save {tiers['2']}% on both", text, slug)
            self.assertIn(f"{tiers['3']}% off all three", text, slug)
            self.assertNotRegex(text, r"\$\d", slug)

    def test_no_pressure_words(self):
        for slug in nudge.PAGES:
            m = LINE.search(self.page(slug))
            if m:
                self.assertIsNone(PRESSURE.search(m.group(1)), slug)

    def test_links_are_unique_and_tagged(self):
        seen = set()
        for slug in nudge.PAGES:
            m = LINE.search(self.page(slug))
            if not m:
                continue
            href = re.search(r'href="([^"]+)"', m.group(1)).group(1)
            self.assertIn("utm_source=purplelink", href)
            self.assertTrue(href.endswith("#bundle"))
            content = re.search(r"utm_content=([^&#]+)", href).group(1)
            self.assertNotIn(content, seen)
            seen.add(content)

    def test_style_is_external(self):
        css = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".buy-bundle {", css)
        for slug in nudge.PAGES:
            m = LINE.search(self.page(slug))
            if m:
                self.assertNotIn("style=", m.group(1))


if __name__ == "__main__":
    unittest.main()
