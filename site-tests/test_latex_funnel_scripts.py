"""The LaTeX video funnel tooling: YouTube description tagging, the error-demand ranking and the stop rule."""
import datetime as dt
import importlib.util
import sys
import tempfile
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import latex_error_demand as D  # noqa: E402
import latex_funnel_report as R  # noqa: E402

_spec = importlib.util.spec_from_file_location("yt_utm", ROOT / "scripts" / "yt-utm.py")
U = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(U)


class YoutubeTagging(unittest.TestCase):
    SHORT = ("How to read the log for LaTeX's File not found error and fix it in under 30 seconds. "
             "More causes and fixes: https://purplelink.llc/latex-errors/file-not-found/")

    def test_short_gets_a_tagged_error_link_and_a_tagged_moderntex_line(self):
        out = U.plan(self.SHORT)
        self.assertIn("https://purplelink.llc/latex-errors/file-not-found/?utm_source=youtube-latex&utm_medium=short&utm_campaign=latex-errors", out)
        self.assertIn("https://purplelink.llc/moderntex/?utm_source=youtube-latex&utm_medium=short&utm_campaign=latex-errors", out)
        self.assertTrue(out.startswith(self.SHORT.split("https://")[0]))

    def test_promo_link_is_tagged_in_place_without_a_new_line(self):
        d = "A tour of ModernTex. $19.99, one purchase. https://purplelink.llc/moderntex/"
        out = U.plan(d)
        self.assertEqual(out, d + "?utm_source=youtube-latex&utm_medium=video&utm_campaign=moderntex-promo")

    def test_rerun_changes_nothing(self):
        once = U.plan(self.SHORT)
        self.assertIsNone(U.plan(once))
        self.assertIsNone(U.plan("Live stream https://purplelink.llc/?utm_source=youtube&utm_medium=stream"))

    def test_no_purplelink_link_means_nothing_to_do(self):
        self.assertIsNone(U.plan("Just a description"))

    def test_existing_moderntex_mention_is_not_duplicated(self):
        d = self.SHORT + "\nModernTex: https://purplelink.llc/moderntex/?x=1"
        self.assertEqual(U.plan(d).count("/moderntex/"), 1)

    def test_every_listed_video_id_is_a_youtube_id(self):
        import json
        ids = json.loads((ROOT / "scripts" / "yt-utm-videos.json").read_text())
        self.assertGreaterEqual(len(ids), 14)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9_-]{11}", i) for i in ids))


class DemandRanking(unittest.TestCase):
    def fake(self, views_by_words):
        def fetch(url):
            from urllib.parse import parse_qs, urlparse
            w = parse_qs(urlparse(url).query)["intitle"][0]
            v = views_by_words.get(w)
            if v is None:
                raise OSError("boom")
            return {"items": [{"view_count": x} for x in v], "quota_remaining": 200}
        return fetch

    def test_sorted_by_views_with_ranks_and_coverage(self):
        cands = [("file-not-found", "a", "A"), ("not-a-page", "b", "B"), ("overfull-hbox", "c", "C")]
        rows = D.rank(self.fake({"a": [10, 20], "b": [500], "c": [5]}), lambda s: None, ROOT, cands)
        self.assertEqual([r["slug"] for r in rows], ["not-a-page", "file-not-found", "overfull-hbox"])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3])
        self.assertEqual([r["covered"] for r in rows], [False, True, True])
        self.assertEqual((rows[1]["views"], rows[1]["questions"], rows[1]["top_views"]), (30, 2, 20))

    def test_one_failed_lookup_does_not_lose_the_rest_and_is_marked(self):
        cands = [("x", "a", "A"), ("y", "zzz", "B")]
        rows = D.rank(self.fake({"a": [7]}), lambda s: None, ROOT, cands)
        bad = [r for r in rows if r["slug"] == "y"][0]
        self.assertIn("error_lookup", bad)
        self.assertEqual([r for r in rows if r["slug"] == "x"][0]["views"], 7)

    def test_every_covered_page_is_a_real_candidate_and_slugs_are_unique(self):
        slugs = [c[0] for c in D.CANDIDATES]
        self.assertEqual(len(slugs), len(set(slugs)))
        pages = {p.parent.name for p in (ROOT / "site" / "latex-errors").glob("*/index.html")}
        self.assertTrue(pages <= set(slugs), pages - set(slugs))

    def test_table_flags_rows_with_no_title_match(self):
        t = D.table([{"rank": 1, "views": 0, "questions": 0, "covered": False, "error": "X"}])
        self.assertIn("no title matched", t)


class StopRule(unittest.TestCase):
    def rows(self, start, weeks, per_28d):
        d0 = dt.date.fromisoformat(start)
        return [{"date": (d0 + dt.timedelta(days=7 * i)).isoformat(), "human_views_est_28d": str(per_28d)} for i in range(weeks + 1)]

    def test_before_the_checkpoint_it_waits(self):
        s, _ = R.verdict(self.rows("2026-10-14", 2, 5), 12, dt.date(2026, 10, 28))
        self.assertEqual(s, "WAIT")

    def test_zero_visits_four_weeks_in_is_a_warning_not_a_stop(self):
        s, why = R.verdict(self.rows("2026-10-14", 4, 0), 14, dt.date(2026, 11, 11))
        self.assertEqual(s, "WARN")
        self.assertIn("yt-utm.py", why)

    def test_checkpoint_by_date_continues_at_ten_a_week_and_stops_below(self):
        ok = R.verdict(self.rows("2026-10-14", 8, 40), 20, dt.date(2026, 12, 9))
        self.assertEqual(ok[0], "CONTINUE")
        low = R.verdict(self.rows("2026-10-14", 8, 39), 20, dt.date(2026, 12, 9))
        self.assertEqual(low[0], "STOP")

    def test_checkpoint_by_video_count_applies_early(self):
        s, _ = R.verdict(self.rows("2026-10-14", 5, 12), 45, dt.date(2026, 11, 18))
        self.assertEqual(s, "STOP")

    def test_too_little_history_at_the_checkpoint_waits(self):
        s, why = R.verdict(self.rows("2026-12-01", 1, 100), 50, dt.date(2026, 12, 9))
        self.assertEqual(s, "WAIT")
        self.assertIn("4 weeks", why)

    def test_history_is_one_row_per_date_and_survives_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "h.csv"
            R.append_history({"date": "2026-10-14", "videos": 12, "site_views_28d": 1}, p)
            R.append_history({"date": "2026-10-14", "videos": 12, "site_views_28d": 5}, p)
            R.append_history({"date": "2026-10-21", "videos": 13, "site_views_28d": 6}, p)
            rows = R.read_history(p)
            self.assertEqual([(r["date"], r["site_views_28d"]) for r in rows], [("2026-10-14", "5"), ("2026-10-21", "6")])
            self.assertEqual(list(rows[0].keys()), R.FIELDS)

    def test_the_2026_10_14_link_check_burst_reads_as_zero_human_views(self):
        """28 page views on 14 brand-new tagged URLs (exactly 2 each) were all link checks, not viewers."""
        allowance = R.bot_allowance([], dt.date(2026, 10, 14), 14)
        self.assertEqual(allowance, 28)
        self.assertEqual(R.human_estimate(28, allowance), 0)

    def test_real_visits_on_top_of_the_checks_survive_the_subtraction(self):
        allowance = R.bot_allowance([], dt.date(2026, 10, 14), 14)
        self.assertEqual(R.human_estimate(40, allowance), 12)

    def test_only_urls_published_inside_the_window_are_allowed_for(self):
        old = [{"date": "2026-10-14", "tagged_urls": "14"}]
        # 29 days later, 3 more URLs: only those 3 are new in the window
        self.assertEqual(R.bot_allowance(old, dt.date(2026, 11, 12), 17), 6)
        # a row that is not yet 28 days old does not count as the base
        self.assertEqual(R.bot_allowance(old, dt.date(2026, 10, 30), 17), 34)

    def test_a_daily_upload_alone_cannot_clear_the_bar(self):
        """30 daily uploads, each adding 2 link-check views and no person: human estimate stays 0."""
        urls = 14 + 30
        views = R.BOT_VIEWS_PER_URL * urls
        self.assertEqual(R.human_estimate(views, R.bot_allowance([], dt.date(2026, 11, 13), urls)), 0)

    def test_site_numbers_reads_only_the_series_channel(self):
        stats = {"funnelByChannel": {"youtube": {"pageviews": 99},
                                     "youtube-latex": {"pageviews": 6, "pageviewsByPath": {"/moderntex/": 4, "/latex-errors/x/": 2},
                                                      "trial": {"moderntex": 2}, "checkout": {}}}}
        n = R.site_numbers(stats)
        self.assertEqual((n["site_views_28d"], n["moderntex_views_28d"], n["trials_28d"], n["checkouts_28d"]), (6, 4, 2, 0))
        self.assertEqual(R.site_numbers({})["site_views_28d"], 0)


if __name__ == "__main__":
    unittest.main()
