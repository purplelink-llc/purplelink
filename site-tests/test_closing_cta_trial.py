"""The closing ModernTex band on content pages leads with the free trial and both buttons are counted.

Until 2026-11-18 the band's two buttons both went to /moderntex/ with no tracking, so a reader who reached
the end of a guide had no direct way to the trial and the click was invisible. The trial button uses the
guide door (src=guide) so it counts as guide_mtx_trial, and mtx-trial-door.js sends visitors who are not on a
Mac to /moderntex/ with a "-not-mac" meta, since a disk image is no use on a phone or a PC.
"""
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
ACTIONS = re.compile(r'<div class="waitlist-actions">(.*?)</div>', re.S)
TRIAL = "/.netlify/functions/moderntex-download?src=guide&amp;trial=1"


def bands():
    for p in sorted(SITE.rglob("*.html")):
        for m in ACTIONS.finditer(p.read_text(encoding="utf-8")):
            yield p, m.group(1)


class ClosingCtaTrial(unittest.TestCase):
    def test_no_band_sends_both_buttons_to_the_same_page(self):
        for p, band in bands():
            hrefs = re.findall(r'href="([^"]+)"', band)
            if len(hrefs) == 2 and hrefs[0].startswith("/moderntex/"):
                self.assertNotEqual(hrefs[0], hrefs[1], p)

    def test_trial_bands_are_tracked_through_the_guide_door(self):
        n = 0
        for p, band in bands():
            if "moderntex-download" not in band:
                continue
            n += 1
            self.assertIn(f'href="{TRIAL}" data-track="guide_mtx_trial" data-track-meta="', band, p)
            self.assertIn('data-track="guide_mtx_click" data-track-meta="', band, p)
            # never the bare trial door: that would count as trial_download in the experiment metrics
            self.assertNotIn("moderntex-download?trial=1", band, p)
            if ':end">' in band:  # the closing bands from 2026-11-18 send non-Mac visitors to /moderntex/
                self.assertIn('<script src="/mtx-trial-door.js" defer></script>', p.read_text(encoding="utf-8"), p)
        self.assertGreaterEqual(n, 53)

    def test_trial_door_not_mac_matches_send_to_mac(self):
        def body(name):
            s = (SITE / name).read_text(encoding="utf-8")
            m = re.search(r"function notMac\(nav\) \{.*?\n  \}\n", s, re.S)
            self.assertIsNotNone(m, name)
            return re.sub(r"\s+", " ", m.group(0))
        self.assertEqual(body("mtx-trial-door.js"), body("send-to-mac.js"))

    def test_track_meta_is_unique_per_page(self):
        seen = {}
        for p, band in bands():
            for meta in re.findall(r'data-track-meta="([^"]+:end)"', band):
                self.assertNotIn(meta, seen, (p, seen.get(meta)))
                seen[meta] = p


if __name__ == "__main__":
    unittest.main()
