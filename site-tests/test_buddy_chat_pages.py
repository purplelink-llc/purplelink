"""Where Buddy, the site chat, appears (docs/designs/buddy-chat.md, Boundaries; Ben, 2026-11-03: "Everywhere except
checkout"): on every public page, never on an account or payment flow page, and never as a render-blocking stylesheet."""
import re
import unittest

from common import SITE

LOADER = re.compile(r'<script src="/buddy-chat/loader\.js[^"]*" defer></script>')
FLOW_DIRS = {"checkout", "success", "upload", "manage", "recover", "account", "stats", "digest"}


def pages():
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith("assets/") or rel.startswith("google"):
            continue
        yield rel, f.read_text(encoding="utf-8")


class BuddyChatPages(unittest.TestCase):
    def test_never_on_flow_pages(self):
        on_flow = [rel for rel, text in pages() if set(rel.split("/")[:-1]) & FLOW_DIRS and LOADER.search(text)]
        self.assertEqual(on_flow, [])

    def test_on_the_public_pages(self):
        for rel in ("index.html", "nee/index.html", "globepin/index.html", "guides/index.html", "blog/index.html",
                    "tools/png-to-jpg/index.html", "tools/heic-to-jpg/index.html", "tools/citation-gap/index.html",
                    "moderntex/index.html", "games/index.html"):
            with self.subTest(rel=rel):
                self.assertRegex((SITE / rel).read_text(encoding="utf-8"), LOADER)

    def test_stylesheet_is_added_by_the_loader_not_the_page(self):
        # A <link> to chat.css in <head> would hold up rendering on every page; loader.js adds it itself.
        with_css = [rel for rel, text in pages() if "/buddy-chat/chat.css" in text]
        self.assertEqual(with_css, [])
        loader = (SITE / "buddy-chat" / "loader.js").read_text(encoding="utf-8")
        self.assertIn('BASE + "chat.css"', loader)
        self.assertIn("css.onload = draw", loader)

    def test_pre_sale_buttons_name_real_app_pages(self):
        # chat.js shows price, trial and Mac buttons on these pages (design doc, "Conversion pass", section 2).
        chat = (SITE / "buddy-chat" / "chat.js").read_text(encoding="utf-8")
        table = re.search(r"var APPS = \{(.*?)\};", chat, re.S).group(1)
        keys = re.findall(r'"([a-z-]+)":', table)
        self.assertEqual(len(keys), 10)
        for key in keys:
            with self.subTest(app=key):
                self.assertRegex((SITE / key / "index.html").read_text(encoding="utf-8"), LOADER)
        for text in ("Which Macs does it run on?", "How does the free trial work?",
                     "AI answers from what's on this site. It can be wrong. "):
            self.assertIn(text, chat)

    def test_holdout_schedule_is_the_reproducible_draw(self):
        # The holdout in loader.js must be the schedule scripts/draw_buddy_schedule.py draws, or all "B" once stopped.
        import subprocess, sys
        loader = (SITE / "buddy-chat" / "loader.js").read_text(encoding="utf-8")
        schedule = re.search(r'var SCHEDULE = "([AB]+)"', loader).group(1)
        if set(schedule) == {"B"}:
            return
        script = SITE.parent / "scripts" / "draw_buddy_schedule.py"
        done = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_holdout_report_reads_pairs_and_applies_the_rule(self):
        import importlib.util, datetime as dt
        spec = importlib.util.spec_from_file_location("bhr", SITE.parent / "scripts" / "buddy_holdout_report.py")
        bhr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bhr)
        start, sched = bhr.schedule()

        def history(b_rate, a_rate, days=len(sched)):
            by_day = {}
            for i in range(days):
                rate = b_rate if sched[i] == "B" else a_rate
                by_day[(start + dt.timedelta(days=i)).isoformat()] = {"appPageviews": 100, "appConversions": rate}
            return {"sites": {"purplelink": {"byDay": by_day}}}

        self.assertEqual(bhr.report({})["verdict"], "no data yet")
        self.assertTrue(bhr.report(history(3, 3, days=10))["verdict"].startswith("running: 5 of 28"))
        worse = bhr.report(history(1, 4))
        self.assertLess(worse["mean_diff_b_minus_a"], 0)
        self.assertTrue(worse["verdict"].startswith("remove or rethink"))
        self.assertTrue(bhr.report(history(4, 1))["verdict"].startswith("keep Buddy"))
        self.assertTrue(bhr.report(history(2, 2))["verdict"].startswith("keep Buddy"))


if __name__ == "__main__":
    unittest.main()
