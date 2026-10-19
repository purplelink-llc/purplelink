"""scripts/social detection library (PR 219) after consolidation: limits, voice, event scan, and proof that the
module no longer posts. Fake HTTP only, no network: every request goes to FakeHttp, which fails the test on any
URL it was not told about."""
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from common import ROOT

sys.path.insert(0, str(ROOT / "scripts" / "social"))
sys.path.insert(0, str(ROOT / "scripts" / "queue"))
import approval_queue as aq  # noqa: E402
import core  # noqa: E402
import events  # noqa: E402
import poster  # noqa: E402
from core import Refused, Response, Skip  # noqa: E402

GUIDE_HTML = """<html><head><meta property="og:title" content="Demo guide for Mac">
<meta name="description" content="A plain demo guide. It has two sentences."></head><body><main><h1>Demo guide for Mac</h1>
<article class="post-body"><p>First paragraph with <a href="/legroom/">Legroom</a>.</p><h2>Part</h2><ul><li>One</li></ul>
<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></article></main></body></html>"""
SITEMAP = "<urlset><url><loc>https://purplelink.llc/guides/old-guide/</loc></url>{extra}</urlset>"


class FakeHttp:
    def __init__(self):
        self.routes, self.calls = [], []

    def on(self, method, pattern, reply):
        """reply: Response, dict (JSON 200), or a function(call) -> Response. Later routes win."""
        self.routes.insert(0, (method, re.compile(pattern), reply))
        return self

    def request(self, method, url, **kw):
        call = {"method": method, "url": url, **kw}
        self.calls.append(call)
        for m, pat, reply in self.routes:
            if m == method and pat.search(url):
                if callable(reply):
                    return reply(call)
                if isinstance(reply, dict):
                    return Response(200, json.dumps(reply).encode())
                return reply
        raise AssertionError(f"unexpected request {method} {url} (tests never touch the network)")

    def posted(self, pattern):
        return [c for c in self.calls if c["method"] == "POST" and re.search(pattern, c["url"])]


def page(html, status=200):
    return Response(status, html.encode())


def sequence(*replies):
    """A reply that answers with each item in turn (the last one repeats)."""
    state = {"i": 0}

    def reply(call):
        r = replies[min(state["i"], len(replies) - 1)]
        state["i"] += 1
        return Response(200, json.dumps(r).encode()) if isinstance(r, dict) else r
    return reply


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.env = {k: os.environ.get(k) for k in ("PURPLELINK_SOCIAL_HOME", "PURPLELINK_SOCIAL_CONFIG", "PURPLELINK_SOCIAL_NO_NOTIFY")}
        os.environ["PURPLELINK_SOCIAL_HOME"] = str(t / "social")
        os.environ["PURPLELINK_SOCIAL_CONFIG"] = str(t / "config")
        os.environ["PURPLELINK_SOCIAL_NO_NOTIFY"] = "1"
        self.http = FakeHttp()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def live_guide(self, slug="demo-guide", status=200):
        self.http.on("GET", rf"^https://purplelink\.llc/guides/{slug}/$", page(GUIDE_HTML, status))


class Limits(unittest.TestCase):
    def test_each_channel_limit(self):
        cases = {"bluesky": 300, "threads": 500, "x": 280, "mastodon": 500, "linkedin": 3000}
        for ch, n in cases.items():
            self.assertEqual(core.limit_problems(ch, "a" * n), [], ch)
            self.assertTrue(core.limit_problems(ch, "a" * (n + 1)), ch)

    def test_x_and_mastodon_count_a_url_as_23(self):
        url = "https://purplelink.llc/x/g/" + "a" * 80
        self.assertEqual(core.x_weighted(f"hi {url}"), 3 + 23)
        self.assertEqual(core.mastodon_len(f"hi {url}"), 3 + 23)
        self.assertEqual(core.length_of("bluesky", f"hi {url}")[0], 3 + len(url))

    def test_bluesky_counts_graphemes(self):
        self.assertEqual(core.graphemes("é" * 300), 300)
        self.assertEqual(core.limit_problems("bluesky", "é" * 300), [])

    def test_threads_more_than_five_links(self):
        five = " ".join(f"https://purplelink.llc/{i}" for i in range(5))
        self.assertEqual(core.limit_problems("threads", five), [])
        self.assertIn("more than 5", " ".join(core.limit_problems("threads", five + " https://purplelink.llc/6")))

    def test_voice(self):
        self.assertIn("em dash", core.voice_problems("A — B"))
        self.assertIn("emoji", core.voice_problems("Ship it \U0001F680"))
        self.assertTrue(core.voice_problems("A game-changer for you"))
        self.assertEqual(core.plain("A — B"), "A, B")


class Scan(Base):
    def site(self, extra_guides=(), version="1.4.0", changelog=True):
        locs = "".join(f"<url><loc>https://purplelink.llc/guides/{g}/</loc></url>" for g in extra_guides)
        self.http.on("GET", r"sitemap\.xml$", page(SITEMAP.format(extra=locs)))
        self.http.on("GET", r"/guides/old-guide/$", page(GUIDE_HTML))
        for g in extra_guides:
            self.live_guide(g)
        for app, path in events.PRODUCTS.items():
            name = app.replace("-", " ").title()
            ld = json.dumps({"@type": "SoftwareApplication", "name": name, "softwareVersion": version if app == "legroom" else "1.0.0",
                             "offers": {"@type": "Offer", "price": "9.99"}})
            self.http.on("GET", rf"^https://purplelink\.llc{re.escape(path)}$",
                         page(f'<script type="application/ld+json">{ld}</script><p>a single $9.99 payment</p>'))
        entries = "" if not changelog else f"<h2>Legroom {version}</h2>\n<p>New: a thing. Second.</p>"
        entries += "".join(f"<h2>{a.replace('-', ' ').title()} 1.0.0</h2><p>Old.</p>" for a in events.PRODUCTS if a != "legroom")
        self.http.on("GET", r"/changelog/$", page(entries))
        self.http.on("GET", r"feeds/videos\.xml", page("<feed><entry><yt:videoId>OLDVIDEO01</yt:videoId><title>Old</title></entry></feed>"))

    def test_first_scan_seeds_and_announces_nothing(self):
        self.site()
        st = core.load_state()
        found, _ = events.scan(self.http, st)
        self.assertEqual(found, [])
        self.assertTrue(st["seeded"])
        self.assertIn("old-guide", st["seen"]["guides"])
        self.assertEqual(st["seen"]["releases"]["legroom"], "1.4.0")

    def test_new_guide_release_and_video_are_found(self):
        self.site()
        st = core.load_state()
        events.scan(self.http, st)
        self.site(extra_guides=["demo-guide"], version="1.5.0")
        self.http.on("GET", r"feeds/videos\.xml", page(
            "<feed><entry><yt:videoId>OLDVIDEO01</yt:videoId><title>Old</title></entry>"
            "<entry><yt:videoId>NEWVIDEO01</yt:videoId><title>New &amp; long</title>"
            "<media:description>What it shows.\n\nhttps://purplelink.llc/x?utm_source=youtube #mac</media:description></entry>"
            "<entry><yt:videoId>SHORTVID01</yt:videoId><title>A Short</title></entry></feed>"))
        self.http.on("HEAD", r"shorts/NEWVIDEO01$", Response(303))
        self.http.on("HEAD", r"shorts/SHORTVID01$", Response(200))
        self.http.on("GET", r"oembed.*NEWVIDEO01", {"title": "New & long"})
        found, notes = events.scan(self.http, st)
        keys = sorted(f["event_key"] for f in found)
        self.assertEqual(keys, ["guide:demo-guide", "release:legroom:1.5.0", "video:NEWVIDEO01"])
        rel = next(f for f in found if f["kind"] == "release_published")
        self.assertEqual((rel["version"], rel["price"], rel["price_once"]), ("1.5.0", "9.99", True))
        self.assertEqual(rel["notes"], "New: a thing. Second.")
        vid = next(f for f in found if f["kind"] == "video_published")
        self.assertEqual(vid["description"], "What it shows.")
        self.assertIn("SHORTVID01", st["seen"]["videos"])

    def test_release_without_live_changelog_entry_waits(self):
        self.site()
        st = core.load_state()
        events.scan(self.http, st)
        self.site(version="1.5.0", changelog=False)
        found, notes = events.scan(self.http, st)
        self.assertEqual(found, [])
        self.assertEqual(st["seen"]["releases"]["legroom"], "1.4.0")  # found on the next scan once it is live
        self.assertTrue(any("changelog" in n for n in notes))


class QueueLint(unittest.TestCase):
    def test_poster_executor_only_for_poster_items(self):
        fm = {"executor": "poster", "job": "weekly-growth-scan", "kind": "post"}
        _, probs = aq.lint(fm, "", offline=True)
        self.assertTrue(any("executor poster" in p for p in probs))


class SinglePostingPath(unittest.TestCase):
    """PR 219's poster must not post on its own: the one posting path is backend/scripts/social.py."""

    def test_poster_has_no_posting_code(self):
        self.assertFalse((ROOT / "scripts" / "social" / "channels.py").exists())
        self.assertFalse((ROOT / "scripts" / "social" / "variants.py").exists())
        for name in ("run", "create_item", "standing_problems", "channel_problems", "dev_tagger"):
            self.assertFalse(hasattr(poster, name), name)

    def test_retired_commands_exit_2_and_touch_no_network(self):
        for cmd in poster.RETIRED:
            self.assertEqual(poster.main([cmd], http=FakeHttp()), 2, cmd)  # FakeHttp fails on any request

    def test_no_launchd_job_or_wrapper_runs_it(self):
        for f in (ROOT / "backend" / "scripts").glob("*.sh"):
            self.assertNotIn("social/poster.py", f.read_text(), f.name)
        self.assertNotIn("run --live", (ROOT / "scripts" / "social" / "poster.py").read_text().split('"""')[1].split("Every other")[0])

    def test_scan_writes_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        t = Path(tmp.name) / "social"
        old = os.environ.get("PURPLELINK_SOCIAL_HOME")
        os.environ["PURPLELINK_SOCIAL_HOME"] = str(t)
        self.addCleanup(lambda: os.environ.pop("PURPLELINK_SOCIAL_HOME") if old is None else os.environ.update(PURPLELINK_SOCIAL_HOME=old))
        http = FakeHttp()
        http.on("GET", r"sitemap\.xml$", page(SITEMAP.format(extra="")))
        http.on("GET", r"/guides/old-guide/$", page(GUIDE_HTML))
        for app, path in events.PRODUCTS.items():
            http.on("GET", rf"^https://purplelink\.llc{re.escape(path)}$", page("<p>x</p>"))
        http.on("GET", r"feeds/videos\.xml", page("<feed></feed>"))
        self.assertEqual(poster.main(["scan"], http=http), 0)
        self.assertFalse(t.exists() and any(t.iterdir()))
        self.assertEqual([c for c in http.calls if c["method"] != "GET"], [])


if __name__ == "__main__":
    unittest.main()
