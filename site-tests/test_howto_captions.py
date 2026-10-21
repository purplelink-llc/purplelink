"""How-to caption tracks (Ben, 2026-10-21): video/src/howto/srt.js builds SubRip on the video's own timeline, and
scripts/yt-captions.py uploads it only to our own channel's own video. Fake YouTube service, no network; the SRT part
needs node and is skipped without it."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import yt_guard as g  # noqa: E402

spec = importlib.util.spec_from_file_location("yt_captions", ROOT / "scripts" / "yt-captions.py")
yc = importlib.util.module_from_spec(spec); spec.loader.exec_module(yc)

PL = "UCUv28P5SUzT4RLQOmi3EK8w"
REG = {"purplelink": {"id": PL, "title": "Purplelink", "token": "~/nope.json", "kinds": ["howto"], "confirmed": True}}
TS = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})")


def secs(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def words(text, start=0.25, step=0.4):
    return [{"word": w.strip(".:,"), "display": w, "start": round(start + i * step, 3), "end": round(start + i * step + 0.3, 3)}
            for i, w in enumerate(text.split())]


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SrtTimeline(unittest.TestCase):
    def run_srt(self, fmt):
        sb = {"id": "t", "scenes": [{"type": "hook", "short": True, "narration": "x"}, {"type": "cause", "narration": "x"},
                                    {"type": "steps", "short": True, "narration": "x"}]}
        tm = {"scenes": [{"words": words("Your Mac says the disk is full. Here is the fix.")},
                         {"words": words("Caches grow over time.")},
                         {"words": words("Open Settings, then General, then Storage, then wait for the bars to load.")}]}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sb.json").write_text(json.dumps(sb)); (Path(d) / "tm.json").write_text(json.dumps(tm))
            r = subprocess.run(["node", "write-srt.mjs", str(Path(d) / "sb.json"), str(Path(d) / "tm.json"), fmt],
                               cwd=ROOT / "video", capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        blocks = [b for b in r.stdout.strip().split("\n\n") if b]
        cues = []
        for b in blocks:
            lines = b.split("\n")
            m = TS.match(lines[1]); self.assertTrue(m, b)
            cues.append((secs(*m.groups()[:4]), secs(*m.groups()[4:]), " ".join(lines[2:])))
        return cues

    def test_first_word_lands_after_bumper_and_lead(self):
        c = self.run_srt("16x9")
        self.assertAlmostEqual(c[0][0], 2.2 - 0.4 + 0.3 + 0.25, places=2)      # open - xf + LEAD + first word
        self.assertEqual(c[0][2], "Your Mac says the disk is full.")         # breaks after a sentence end

    def test_cues_ordered_and_never_overlap(self):
        for fmt in ("16x9", "9x16"):
            c = self.run_srt(fmt)
            for a, b in zip(c, c[1:]):
                self.assertLess(a[0], a[1]); self.assertLessEqual(a[1], b[0])
            self.assertTrue(all(len(x[2].split()) <= 7 for x in c))

    def test_short_drops_unmarked_scenes(self):
        long_text = " ".join(x[2] for x in self.run_srt("16x9"))
        short_text = " ".join(x[2] for x in self.run_srt("9x16"))
        self.assertIn("Caches grow over time.", long_text)
        self.assertNotIn("Caches", short_text)
        self.assertIn("Storage,", short_text)


class FakeExec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class FakeService:
    def __init__(self, me=PL, owner=PL, existing=None):
        self.me, self.owner, self.existing, self.inserted = me, owner, existing or [], []
    def channels(self):
        s = self
        class C:
            def list(self, **k): return FakeExec({"items": [{"id": s.me, "snippet": {"title": "X"}}]})
        return C()
    def videos(self):
        s = self
        class V:
            def list(self, **k): return FakeExec({"items": [{"id": k["id"], "snippet": {"channelId": s.owner}}]})
        return V()
    def captions(self):
        s = self
        class Cap:
            def list(self, **k): return FakeExec({"items": s.existing})
            def insert(self, part, body, media_body):
                s.inserted.append(body); return FakeExec({"id": "CAP1"})
        return Cap()


class CaptionUpload(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.srt = Path(self.d.name) / "v.srt"
        self.srt.write_text("1\n00:00:02,350 --> 00:00:03,780\nIf your LaTeX build\n")
        self.orig_media = g._media; g._media = lambda *a, **k: "MEDIA"
    def tearDown(self):
        g._media = self.orig_media; self.d.cleanup()

    def test_uploads_to_own_video(self):
        svc = FakeService()
        r = yc.attach("vid1", self.srt, service=svc, registry=REG)
        self.assertEqual(r, {"video_id": "vid1", "caption_id": "CAP1"})
        self.assertEqual(svc.inserted, [{"snippet": {"videoId": "vid1", "language": "en", "name": "English", "isDraft": False}}])

    def test_refuses_wrong_token_or_foreign_video(self):
        for svc in (FakeService(me="UCsomeoneelse"), FakeService(owner="UCsomeoneelse")):
            self.assertEqual(yc.main(["vid1", str(self.srt)], service=svc, registry=REG), 3)
            self.assertEqual(svc.inserted, [])

    def test_existing_track_is_left_alone_but_auto_captions_are_not_counted(self):
        svc = FakeService(existing=[{"id": "OLD", "snippet": {"language": "en", "trackKind": "standard"}}])
        self.assertIn("skipped", yc.attach("vid1", self.srt, service=svc, registry=REG)); self.assertEqual(svc.inserted, [])
        svc = FakeService(existing=[{"id": "AUTO", "snippet": {"language": "en", "trackKind": "asr"}}])
        self.assertEqual(yc.attach("vid1", self.srt, service=svc, registry=REG)["caption_id"], "CAP1")

    def test_bad_file_and_dry_run(self):
        bad = Path(self.d.name) / "bad.srt"; bad.write_text("not subtitles")
        self.assertEqual(yc.main(["vid1", str(bad)], service=FakeService(), registry=REG), 2)
        svc = FakeService()
        self.assertEqual(yc.attach("vid1", self.srt, dry_run=True, service=svc, registry=REG)["skipped"], "dry run")
        self.assertEqual(svc.inserted, [])


if __name__ == "__main__":
    unittest.main()
