import re
import unittest
from common import read, read_site


def money(cents):
    return f"${cents / 100:,.2f}"


def parse_seats_mjs():
    src = read("netlify/lib/seats.mjs")
    packs = [(int(a), int(b)) for a, b in re.findall(r"\{\s*seats:\s*(\d+),\s*unitCents:\s*(\d+)\s*\}", src)]
    bulk = re.search(r"SEAT_BULK\s*=\s*\{\s*minSeats:\s*(\d+),\s*unitCents:\s*(\d+)", src)
    mx = re.search(r"MAX_SEATS\s*=\s*(\d+)", src)
    return packs, int(bulk.group(1)), int(bulk.group(2)), int(mx.group(1))


class SeatPrices(unittest.TestCase):
    def test_parse(self):
        packs, bmin, bunit, mx = parse_seats_mjs()
        self.assertEqual([p[0] for p in packs], [5, 10, 15, 20])
        self.assertEqual((bmin, mx), (25, 500))

    def test_moderntex_page_matches_server(self):
        packs, bmin, bunit, mx = parse_seats_mjs()
        page = read_site("moderntex/index.html")
        for seats, unit in packs:
            m = re.search(r'<input[^>]*value="%d"[^>]*>.*?<span class="seat-unit">([^<]*)</span><span class="seat-total">([^<]*)</span>' % seats, page, re.S)
            self.assertIsNotNone(m, f"{seats} seats row")
            self.assertEqual(m.group(1), f"{money(unit)} each")
            self.assertEqual(m.group(2), money(unit * seats))
        m = re.search(r'value="bulk".*?<span class="seat-unit">([^<]*)</span>', page, re.S)
        self.assertEqual(m.group(1), f"{money(bunit)} each")
        self.assertIn(f'min="{bmin}"', page)
        self.assertIn(f'max="{mx}"', page)

    def test_llms_txt_line_matches_server(self):
        packs, bmin, bunit, mx = parse_seats_mjs()
        line = next((l for l in read_site("llms.txt").splitlines() if "Seats for labs and departments" in l), None)
        self.assertIsNotNone(line)
        for seats, unit in packs:
            self.assertIn(f"{seats} seats {money(unit * seats)} ({money(unit)}", line)
        self.assertIn(f"{bmin} to {mx} seats {money(bunit)} each", line)
