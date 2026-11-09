"""YouTube ids that start with "-" (-7GnRgjBu8s, 2026-11-09) and Studio's slow-check wording.

howto-publish.py's argv for yt-captions.py and social.py instagram reel-add must parse with the real parsers when an
id starts with "-", and yt-upload.py must keep waiting on "Checks are taking longer than usual ... still running"."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# yt-upload.py imports cdp_tab, which needs websocket-client; CI has no browser, so stand in for it when missing.
try:
    import websocket  # noqa: F401
except ImportError:
    sys.modules["websocket"] = types.ModuleType("websocket")

hp = load("howto_publish", "scripts/howto-publish.py")
yc = load("yt_captions", "scripts/yt-captions.py")
yu = load("yt_upload", "scripts/yt-upload.py")

DASH = "-7GnRgjBu8s"
LONG = "-AbCdEfGhIj"


class DashIds(unittest.TestCase):
    def test_captions_args_parse(self):
        seen = {}

        def fake_attach(video_id, srt, channel, lang, name, dry_run, **kw):
            seen.update(video_id=video_id, srt=srt, channel=channel)
            return {"ok": True}

        real = yc.attach
        yc.attach = fake_attach
        try:
            rc = yc.main(hp.captions_args(DASH, Path("/x/y.srt")))
        finally:
            yc.attach = real
        self.assertEqual(rc, 0)
        self.assertEqual(seen, {"video_id": DASH, "srt": Path("/x/y.srt"), "channel": "purplelink"})

    def test_reel_args_parse(self):
        from socialpost import cli
        a = cli.build_parser().parse_args(
            hp.reel_args(Path("/v/s.mp4"), DASH, "Title", "/tmp/d.txt", "https://purplelink.llc/x/", LONG, "-tag"))
        self.assertEqual((a.what, a.youtube_id, a.also, a.utm_content), ("reel-add", DASH, LONG, "-tag"))
        a = cli.build_parser().parse_args(
            hp.reel_args(Path("/v/s.mp4"), DASH, "Title", "/tmp/d.txt", "https://purplelink.llc/x/", LONG))
        self.assertEqual(a.utm_content, "")


class CheckState(unittest.TestCase):
    def test_wordings(self):
        cs = yu.check_state
        self.assertEqual(cs("Checks are taking longer than usual to complete but are still running"), "checking")
        self.assertEqual(cs("Checking 40% ... 3 minutes left"), "checking")
        self.assertEqual(cs(""), "checking")
        self.assertEqual(cs("Checks complete. No issues found."), "done")
        self.assertEqual(cs("Copyright issues found"), "issue")

    def test_slow_check_waits_until_complete(self):
        texts = iter(["Checks are taking longer than usual to complete but are still running"] * 2
                     + ["Checks complete. No issues found."])

        class Tab:
            def eval(self, js):
                return next(texts)

        real = yu.time.sleep
        yu.time.sleep = lambda s: None
        try:
            yu.wait_for_checks(Tab(), timeout=60)
        finally:
            yu.time.sleep = real

    def test_slow_check_times_out_without_publishing(self):
        class Tab:
            def eval(self, js):
                return "Checks are taking longer than usual to complete but are still running"

        real_sleep, real_time = yu.time.sleep, yu.time.time
        clock = iter(range(0, 10_000, 20))
        yu.time.sleep = lambda s: None
        yu.time.time = lambda: next(clock)
        try:
            with self.assertRaises(TimeoutError):
                yu.wait_for_checks(Tab(), timeout=100)
        finally:
            yu.time.sleep, yu.time.time = real_sleep, real_time


if __name__ == "__main__":
    unittest.main()
