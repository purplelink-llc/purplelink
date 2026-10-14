"""YouTube thumbnail spec (video/thumbs/youtube.json, rendered by video/build-thumbs.mjs with src/Thumb.jsx)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "video" / "thumbs" / "youtube.json").read_text())


class ThumbSpec(unittest.TestCase):
    def test_one_entry_per_video_with_a_known_template(self):
        ids = [s["id"] for s in SPEC]
        self.assertEqual(len(ids), len(set(ids)))
        for s in SPEC:
            self.assertRegex(s["id"], r"^[A-Za-z0-9_-]{11}$")
            self.assertIn(s["kind"], {"error", "long", "product"})

    def test_every_image_source_exists(self):
        for s in SPEC:
            for src in [s.get("img"), s.get("icon"), *s.get("icons", [])]:
                if src is None:
                    continue
                path = src["video"] if isinstance(src, dict) else src
                self.assertTrue((ROOT / path).is_file(), f"{s['id']}: missing {path}")

    def test_text_is_short_and_carries_no_price(self):
        # research 2026-10-14: 1-5 display words; prices go stale in images nobody re-renders
        for s in SPEC:
            text = s.get("line") or s.get("msg") or ""
            self.assertTrue(text, s["id"])
            self.assertNotRegex(text, r"\$\d", s["id"])
            if s["kind"] == "product":
                self.assertLessEqual(len(text.split()), 6, s["id"])

    def test_no_emoji(self):
        blob = json.dumps(SPEC, ensure_ascii=False)
        self.assertIsNone(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", blob))


class AbVariants(unittest.TestCase):
    """Every long video ships three thumbnails for YouTube Test & Compare (video/thumbs/ab/<video>.json)."""

    def test_each_file_holds_three_distinct_honest_variants(self):
        files = sorted((ROOT / "video" / "thumbs" / "ab").glob("*.json"))
        self.assertTrue(files)
        for f in files:
            v = json.loads(f.read_text())
            self.assertEqual([x["variant"] for x in v], ["A", "B", "C"], f.name)
            self.assertEqual(len({x["id"] for x in v}), 3, f.name)
            # variants that differ only in colour teach nothing: at least two different templates
            self.assertGreaterEqual(len({x["kind"] for x in v}), 2, f.name)
            for x in v:
                self.assertNotRegex(x.get("line") or x.get("msg") or x.get("after") or "", r"\$\d", f.name)
                src = x.get("img")
                if src:
                    self.assertTrue((ROOT / (src["video"] if isinstance(src, dict) else src)).is_file(), f"{f.name}: {src}")


if __name__ == "__main__":
    unittest.main()
