"""The rendered-video step of scripts/howto_gate.py (check_video): pass and fail paths on small synthetic videos.
The checks themselves live in TikTokPipeline/shared_media/video_qa.py, which CI does not have, so the tests that
run it are skipped when it is missing; the missing-module and missing-boxes paths always run."""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "howto_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

QA = gate.VIDEO_QA
try:
    import numpy as np
except ImportError:
    np = None
CAN_RUN = QA.is_file() and np is not None and shutil.which("ffmpeg") is not None
W, H = 320, 180


def encode(path, frames, fps=12):
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
                          "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def frame(i, fg=(0, 0, 0), bg=(235, 225, 245), box=True):
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = bg
    for k in range(8):                       # strokes standing in for a line of text
        f[70:110, 40 + k * 20:40 + k * 20 + 9] = fg
    if box:                                  # something that moves, so the video is not a still
        x = 10 + (i * 4) % 250
        f[140:160, x:x + 30] = (120, 40, 160)
    return f


def write_qa(video, rect=(30, 60, 200, 60), t=1.0):
    video.with_suffix(".qa.json").write_text(json.dumps(
        {"format": "16x9", "fps": 12, "final_hold": 0, "regions": [{"name": "scene 0 title", "t": t, "rect": list(rect)}]}))


class MissingPieces(unittest.TestCase):
    def test_missing_video_module_is_a_clear_error(self):
        old = gate.VIDEO_QA
        gate.VIDEO_QA = Path("/nonexistent/video_qa.py")
        try:
            with tempfile.TemporaryDirectory() as d:
                v = Path(d) / "a-16x9.mp4"
                v.write_bytes(b"x")
                errs = gate.check_video(v)
        finally:
            gate.VIDEO_QA = old
        self.assertEqual(len(errs), 1)
        self.assertIn("video_qa not found", errs[0])

    def test_missing_video_fails(self):
        self.assertTrue(any("not found" in e for e in gate.check_video(Path("/nonexistent/x.mp4"))))


@unittest.skipUnless(CAN_RUN, "needs TikTokPipeline/shared_media/video_qa.py, numpy and ffmpeg")
class RenderedVideo(unittest.TestCase):
    def run_check(self, frames, rect=(30, 60, 200, 60), qa_file=True):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "x-16x9.mp4"
            encode(v, frames)
            if qa_file:
                write_qa(v, rect)
            errs = gate.check_video(v)
            sheet = v.with_name("x-16x9-contact-sheet.jpg")
            return errs, sheet.is_file()

    def test_clean_video_passes_and_writes_a_contact_sheet(self):
        errs, sheet = self.run_check([frame(i) for i in range(60)])
        self.assertEqual(errs, [])
        self.assertTrue(sheet)

    def test_a_one_frame_flash_fails(self):
        fr = [frame(i) for i in range(60)]
        fr[30] = np.full((H, W, 3), 255, np.uint8)
        errs, _ = self.run_check(fr)
        self.assertTrue(any("pop" in e for e in errs), errs)

    def test_a_long_freeze_fails(self):
        fr = [frame(i) for i in range(24)] + [frame(24)] * 96 + [frame(i) for i in range(24)]
        errs, _ = self.run_check(fr)
        self.assertTrue(any("nothing changes" in e for e in errs), errs)

    def test_low_contrast_text_fails(self):
        errs, _ = self.run_check([frame(i, fg=(190, 180, 200)) for i in range(60)])
        self.assertTrue(any("contrast" in e for e in errs), errs)

    def test_missing_text_boxes_file_fails(self):
        errs, _ = self.run_check([frame(i) for i in range(30)], qa_file=False)
        self.assertTrue(any(".qa.json is missing" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
