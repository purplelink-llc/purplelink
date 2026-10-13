import html
import json
import re
import unittest
from pathlib import Path

from common import ORIGIN, EMOJI, page_of, canonical, jsonld_blocks, walk

URL = "/guides/check-mac-battery-health-voltage-and-cycle-count/"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mac_battery"

# An all-caps letters-and-digits run of 10+ characters, with at least one letter and one digit,
# is how Apple serial numbers and adapter serial strings look.
SERIAL_LIKE = re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,}\b")
LABELLED = re.compile(r"^\s*(Serial Number|Device Name|Name|Family):\s*(.*)$", re.M)
KEYED = re.compile(r'"(Serial|SerialString|DeviceName|Name|FamilyCode)"\s*=\s*"?([^",}\s]*)"?')


def unredacted(text):
    """Identifying fields whose value is not XXXX."""
    bad = [m.group(0) for m in LABELLED.finditer(text) if m.group(2).strip() != "XXXX"]
    bad += [m.group(0) for m in KEYED.finditer(text) if m.group(2) != "XXXX"]
    return bad


def strip_tags(text):
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


class MacBatteryGuide(unittest.TestCase):
    def setUp(self):
        self.text = page_of(URL).read_text(encoding="utf-8")

    def test_exists_with_canonical(self):
        self.assertTrue(page_of(URL).is_file())
        self.assertEqual(canonical(self.text), ORIGIN + URL)

    def test_title_under_60_with_year(self):
        title = re.search(r"<title>(.*?)</title>", self.text).group(1)
        self.assertLess(len(title), 60)
        self.assertIn("2026", title)

    def test_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.text)), 1)

    def test_no_inline_style(self):
        self.assertNotRegex(self.text, r'\sstyle="')
        self.assertNotRegex(self.text, r"<style\b")

    def test_no_em_dash_or_emoji(self):
        self.assertNotIn("—", self.text)
        self.assertIsNone(EMOJI.search(self.text))

    def test_json_ld_valid(self):
        blocks = jsonld_blocks(self.text)
        types = {d.get("@type") for b in blocks for d in walk(b)}
        self.assertIn("Article", types)
        self.assertIn("BreadcrumbList", types)
        self.assertIn("FAQPage", types)

    def test_internal_links_resolve(self):
        hrefs = set(re.findall(r'href="(/[^"#?]*)', self.text))
        bad = [h for h in hrefs if h.endswith("/") and h != "/" and not page_of(h).is_file()]
        self.assertEqual(bad, [])

    def test_faq_jsonld_matches_visible_text(self):
        faq = None
        for b in jsonld_blocks(self.text):
            for d in walk(b):
                if d.get("@type") == "FAQPage":
                    faq = d
        self.assertIsNotNone(faq)
        entities = faq["mainEntity"]
        self.assertGreaterEqual(len(entities), 3)
        self.assertLessEqual(len(entities), 4)
        for q in entities:
            name = q["name"]
            m = re.search(r"<h3>%s</h3>\s*<p>(.*?)</p>" % re.escape(html.escape(name, quote=True)), self.text, re.S)
            self.assertIsNotNone(m, "no visible FAQ heading for: " + name)
            visible = " ".join(strip_tags(m.group(1)).split())
            self.assertEqual(visible, " ".join(q["acceptedAnswer"]["text"].split()))

    def test_no_affiliate_markup(self):
        self.assertNotIn("sponsored", self.text)
        self.assertNotRegex(self.text, r"[?&](aff|tag)=")

    def test_page_has_no_serial_like_strings(self):
        visible = strip_tags(self.text)
        self.assertEqual(SERIAL_LIKE.findall(visible), [])
        self.assertEqual(unredacted(visible), [])

    def test_fixtures_are_redacted(self):
        files = sorted(FIXTURES.glob("*.txt"))
        self.assertGreaterEqual(len(files), 10)
        for f in files:
            body = f.read_text(encoding="utf-8")
            self.assertEqual(SERIAL_LIKE.findall(body), [], f.name)
            self.assertEqual(unredacted(body), [], f.name)
        # the redaction markers are present where the raw output has identifying fields
        self.assertRegex((FIXTURES / "system_profiler_battery.txt").read_text(), r"Serial Number: XXXX")
        self.assertRegex((FIXTURES / "system_profiler_battery.txt").read_text(), r"Device Name: XXXX")
        self.assertRegex((FIXTURES / "later_system_profiler_charger.txt").read_text(), r"Serial Number: XXXX")
        self.assertRegex((FIXTURES / "later_system_profiler_charger.txt").read_text(), r"Name: XXXX")
        self.assertIn('"SerialString"="XXXX"', (FIXTURES / "later_ioreg_filtered.txt").read_text())
        self.assertIn("(id=XXXX)", (FIXTURES / "pmset.txt").read_text())

    def test_quoted_outputs_match_fixtures(self):
        for f in sorted(FIXTURES.glob("*.txt")):
            body = f.read_text(encoding="utf-8").rstrip("\n")
            self.assertIn(html.escape(body, quote=False), self.text, "page does not quote fixture " + f.name)

    def test_fixture_arithmetic_matches_page(self):
        ioreg = (FIXTURES / "ioreg_filtered.txt").read_text()
        design = int(re.search(r'"DesignCapacity"=(\d+)', ioreg).group(1))
        raw_max = int(re.search(r'"AppleRawMaxCapacity"=(\d+)', ioreg).group(1))
        remaining = int(re.search(r'"RemainingCapacity"=(\d+)', ioreg).group(1))
        voltage = int(re.search(r'"Voltage" = (\d+)', ioreg).group(1))
        amp = int(re.search(r'"Amperage" = (\d+)', ioreg).group(1))
        signed = amp - 2 ** 64
        self.assertEqual(signed, int((FIXTURES / "bash_signed.txt").read_text()))
        self.assertEqual("%.1f%%" % (raw_max / design * 100), (FIXTURES / "calc_health.txt").read_text().strip())
        self.assertEqual("%.2f W" % (voltage / 1000 * -signed / 1000), (FIXTURES / "calc_watts.txt").read_text().strip())
        self.assertEqual("%.0f minutes" % (remaining / -signed * 60), (FIXTURES / "calc_minutes.txt").read_text().strip())
        power = int(re.search(r'"BatteryPower"=(\d+)', ioreg).group(1)) - 2 ** 64
        self.assertEqual(power, int((FIXTURES / "bash_signed_power.txt").read_text()))
        later = (FIXTURES / "later_ioreg_filtered.txt").read_text()
        later_amp = int(re.search(r'"Amperage" = (-?\d+)', later).group(1))
        self.assertGreater(later_amp, 0)
        later_max = int(re.search(r'"AppleRawMaxCapacity"=(\d+)', later).group(1))
        self.assertEqual("%.1f%%" % (later_max / design * 100), (FIXTURES / "health_two_readings.txt").read_text().split()[1])


if __name__ == "__main__":
    unittest.main()
