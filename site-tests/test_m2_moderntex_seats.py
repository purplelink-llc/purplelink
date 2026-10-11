import re
import unittest
from common import SITE, read_site


class ModernTexSeats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read_site("moderntex/index.html")

    def test_departments_section_and_form(self):
        self.assertRegex(self.page, r'\bid="departments"')
        self.assertRegex(self.page, r'<form\b[^>]*\bid="seat-form"')

    def test_radio_options(self):
        values = re.findall(r'<input\b[^>]*type="radio"[^>]*value="([^"]*)"', self.page)
        for v in ("5", "10", "15", "20", "bulk"):
            self.assertIn(v, values)

    def test_quantity_input(self):
        m = re.search(r'<input\b[^>]*\bid="seat-qty"[^>]*>', self.page)
        self.assertIsNotNone(m)
        tag = m.group(0)
        self.assertIn('type="number"', tag)
        self.assertIn('min="25"', tag)
        self.assertIn('max="500"', tag)

    def test_assets_referenced_and_present(self):
        for name in ("seats.js", "seats.css"):
            self.assertRegex(self.page, r"/moderntex/%s" % re.escape(name))
            self.assertTrue((SITE / "moderntex" / name).is_file(), name)

    def test_seats_js_pricing_table(self):
        self.assertIn("SEAT_PRICING", read_site("moderntex/seats.js"))

    def test_license_keys_copy_all_and_csv(self):
        js = read_site("license-keys.js")
        self.assertIn("Copy all", js)
        self.assertRegex(js, r"text/csv")
        self.assertIn(".csv", js)
