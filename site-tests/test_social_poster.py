"""scripts/social poster: identity pins, limits, standing approval, caps, duplicates. Fake HTTP only, no network:
every request goes to FakeHttp, which fails the test on any URL it was not told about."""
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
import channels as chs  # noqa: E402
import core  # noqa: E402
import events  # noqa: E402
import poster  # noqa: E402
import variants as var  # noqa: E402
from core import Refused, Response, Skip  # noqa: E402

COMPANY = {
    "bluesky": {"id": "did:plc:company", "handle": "purplelink.llc"},
    "threads": {"id": "111", "handle": "purplelinkllc"},
    "x": {"id": "222", "handle": "purplelinkllc"},
    "mastodon": {"id": "333", "handle": "purplelink", "instance": "https://mastodon.example"},
    "devto": {"id": "444", "handle": "purplelink"},
    "email": {"id": "seg_1", "handle": "Purplelink release notes"},
}
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
        self.old_root, aq.ROOT = aq.ROOT, t / "queue"
        aq.ensure_root()
        self.old_pins = json.loads(json.dumps(core.PINS))
        self.http = FakeHttp()
        self.out = []

    def tearDown(self):
        aq.ROOT = self.old_root
        core.PINS.clear()
        core.PINS.update(self.old_pins)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    # -- helpers
    def enable(self, ch, **cfg):
        core.PINS[ch] = dict(COMPANY[ch])
        base = {"id": COMPANY[ch]["id"], "handle": COMPANY[ch]["handle"]}
        if ch == "mastodon":
            base["instance"] = COMPANY[ch]["instance"]
        base.update({"threads": {"access_token": "T"}, "bluesky": {"app_password": "P"},
                     "x": {"access_token": "T", "paid_posting_ok": True}, "mastodon": {"access_token": "T"},
                     "devto": {"api_key": "K"}, "email": {"api_key": "K", "from": "Purplelink <news@purplelink.llc>",
                                                          "double_opt_in": True}}.get(ch, {}))
        base.update(cfg)
        core.save_config(ch, base)

    def live_guide(self, slug="demo-guide", status=200):
        self.http.on("GET", rf"^https://purplelink\.llc/guides/{slug}/$", page(GUIDE_HTML, status))
        for p in core.LINK_PREFIX.values():
            self.http.on("GET", rf"^https://purplelink\.llc/{p}/g/{slug}$", page(GUIDE_HTML, status))

    def guide_item(self, slug="demo-guide", at=None):
        self.live_guide(slug)
        facts = events.guide_facts(self.http, slug)
        folder, probs = poster.create_item(facts, live=True, offline=True, at=at)
        self.assertEqual((folder, probs), ("pending", []))
        return [i for i in aq.all_items() if i["fm"].get("event_key") == f"guide:{slug}"][0]

    def bluesky_ok(self, handle_seq=None):
        h = COMPANY["bluesky"]
        self.http.on("POST", r"createSession$", {"did": h["id"], "handle": h["handle"], "accessJwt": "J"})
        self.http.on("GET", r"getSession$", sequence(*(handle_seq or [{"did": h["id"], "handle": h["handle"]}])))
        self.http.on("POST", r"createRecord$", {"uri": "at://did:plc:company/app.bsky.feed.post/abc", "cid": "c"})

    def run_live(self, **kw):
        return poster.run(self.http, live=True, out=self.out.append, threads={"sleep": lambda s: None}, **kw)


class Identity(Base):
    """Every channel refuses a wrong id or handle, and an identity that changes between the two checks."""

    def post(self, ch, text="Hello https://purplelink.llc/x/legroom", **extra):
        ad = chs.adapter(ch, self.http, **({"sleep": lambda s: None} if ch == "threads" else {}))
        self.assertIsNotNone(ad, ch)
        return ad.post(text, {"idempotency_key": "k", "subject": "S", "title": "T", "description": "",
                              "article": {"title": "T", "body_markdown": "b", "canonical_url": "https://purplelink.llc/guides/x/"},
                              **extra})

    def test_threads_wrong_account_refused(self):
        self.enable("threads")
        self.http.on("GET", r"/me\?", {"id": "999", "username": "benampel"})
        with self.assertRaises(Refused):
            self.post("threads")
        self.assertEqual(self.http.posted(r"threads"), [])

    def test_threads_identity_change_between_checks(self):
        self.enable("threads")
        self.http.on("GET", r"/me\?", sequence({"id": "111", "username": "purplelinkllc"}, {"id": "999", "username": "benampel"}))
        self.http.on("GET", r"threads_publishing_limit", {"data": [{"quota_usage": 0, "config": {"quota_total": 250}}]})
        self.http.on("POST", r"/111/threads$", {"id": "container1"})
        with self.assertRaises(Refused):
            self.post("threads")
        self.assertEqual(self.http.posted(r"threads_publish"), [])

    def test_threads_quota_exhausted(self):
        self.enable("threads")
        self.http.on("GET", r"/me\?", {"id": "111", "username": "purplelinkllc"})
        self.http.on("GET", r"threads_publishing_limit", {"data": [{"quota_usage": 250, "config": {"quota_total": 250}}]})
        with self.assertRaises(Skip):
            self.post("threads")
        self.assertEqual(self.http.posted(r"threads"), [])

    def test_threads_publishes_after_both_checks(self):
        self.enable("threads")
        self.http.on("GET", r"/me\?", {"id": "111", "username": "purplelinkllc"})
        self.http.on("GET", r"threads_publishing_limit", {"data": [{"quota_usage": 3, "config": {"quota_total": 250}}]})
        self.http.on("POST", r"/111/threads$", {"id": "container1"})
        self.http.on("POST", r"/111/threads_publish$", {"id": "m1"})
        self.http.on("GET", r"/m1\?", {"id": "m1", "permalink": "https://www.threads.com/@purplelinkllc/post/1", "username": "purplelinkllc"})
        self.assertEqual(self.post("threads"), "https://www.threads.com/@purplelinkllc/post/1")
        self.assertEqual(len([c for c in self.http.calls if re.search(r"/me\?", c["url"])]), 2)

    def test_bluesky_wrong_did_refused(self):
        self.enable("bluesky")
        self.http.on("POST", r"createSession$", {"did": "did:plc:ben", "handle": "ben.bsky.social", "accessJwt": "J"})
        with self.assertRaises(Refused):
            self.post("bluesky")
        self.assertEqual(self.http.posted(r"createRecord"), [])

    def test_bluesky_wrong_handle_refused(self):
        self.enable("bluesky")
        self.http.on("POST", r"createSession$", {"did": "did:plc:company", "handle": "purplelink.llc", "accessJwt": "J"})
        self.http.on("GET", r"getSession$", {"did": "did:plc:company", "handle": "someone.else"})
        with self.assertRaises(Refused):
            self.post("bluesky")

    def test_bluesky_identity_change_between_checks(self):
        self.enable("bluesky")
        self.bluesky_ok([{"did": "did:plc:company", "handle": "purplelink.llc"}, {"did": "did:plc:other", "handle": "purplelink.llc"}])
        with self.assertRaises(Refused):
            self.post("bluesky")
        self.assertEqual(self.http.posted(r"createRecord"), [])

    def test_bluesky_posts_with_link_facet_and_card(self):
        self.enable("bluesky")
        self.bluesky_ok()
        url = self.post("bluesky", text="Café note https://purplelink.llc/bs/legroom")
        self.assertEqual(url, "https://bsky.app/profile/purplelink.llc/post/abc")
        rec = self.http.posted(r"createRecord$")[0]["json_body"]["record"]
        f = rec["facets"][0]["index"]
        self.assertEqual(rec["text"].encode()[f["byteStart"]:f["byteEnd"]].decode(), "https://purplelink.llc/bs/legroom")
        self.assertEqual(rec["embed"]["external"]["uri"], "https://purplelink.llc/bs/legroom")

    def test_x_wrong_account_refused(self):
        self.enable("x")
        self.http.on("GET", r"api\.x\.com/2/users/me$", {"data": {"id": "222", "username": "BenAmpel"}})
        with self.assertRaises(Refused):
            self.post("x")
        self.assertEqual(self.http.posted(r"tweets"), [])

    def test_x_stays_off_without_paid_flag(self):
        self.enable("x", paid_posting_ok=False)
        self.http.on("GET", r"users/me$", {"data": {"id": "222", "username": "purplelinkllc"}})
        with self.assertRaises(Skip):
            self.post("x")
        self.assertEqual(self.http.posted(r"tweets"), [])

    def test_mastodon_wrong_account_refused(self):
        self.enable("mastodon")
        self.http.on("GET", r"verify_credentials$", {"id": "333", "acct": "ben"})
        with self.assertRaises(Refused):
            self.post("mastodon")
        self.assertEqual(self.http.posted(r"statuses"), [])

    def test_mastodon_config_pointing_at_another_server_refused(self):
        self.enable("mastodon", instance="https://evil.example")
        with self.assertRaises(Refused):
            self.post("mastodon")
        self.assertEqual(self.http.calls, [])

    def test_mastodon_identity_change_between_checks(self):
        self.enable("mastodon")
        self.http.on("GET", r"verify_credentials$", sequence({"id": "333", "acct": "purplelink"}, {"id": "9", "acct": "purplelink"}))
        with self.assertRaises(Refused):
            self.post("mastodon")
        self.assertEqual(self.http.posted(r"statuses"), [])

    def test_devto_wrong_account_refused(self):
        self.enable("devto")
        self.http.on("GET", r"dev\.to/api/users/me$", {"id": 444, "username": "benampel"})
        with self.assertRaises(Refused):
            self.post("devto")
        self.assertEqual(self.http.posted(r"articles"), [])

    def test_devto_posts_with_canonical_url(self):
        self.enable("devto")
        self.http.on("GET", r"users/me$", {"id": 444, "username": "purplelink"})
        self.http.on("POST", r"api/articles$", {"url": "https://dev.to/purplelink/demo"})
        self.assertEqual(self.post("devto"), "https://dev.to/purplelink/demo")
        art = self.http.posted(r"articles")[0]["json_body"]["article"]
        self.assertTrue(art["published"])
        self.assertEqual(art["canonical_url"], "https://purplelink.llc/guides/x/")

    def test_email_wrong_segment_refused(self):
        self.enable("email")
        self.http.on("GET", r"segments/seg_1$", {"id": "seg_1", "name": "Someone else's list"})
        with self.assertRaises(Refused):
            self.post("email")
        self.assertEqual(self.http.posted(r"broadcasts"), [])

    def test_email_sender_must_be_purplelink(self):
        self.enable("email", **{"from": "ben@gmail.com"})
        self.http.on("GET", r"segments/seg_1$", {"id": "seg_1", "name": "Purplelink release notes"})
        with self.assertRaises(Refused):
            self.post("email")

    def test_linkedin_refusal_from_existing_poster(self):
        core.save_config("linkedin", {"enabled": True})

        class R:
            returncode = 4
        ad = chs.adapter("linkedin", self.http, runner=lambda *a, **k: R())
        with self.assertRaises(Refused):
            ad.post("text", {})

    def test_config_must_match_pin(self):
        self.enable("devto", id="999", handle="benampel")
        self.http.on("GET", r"users/me$", {"id": 444, "username": "purplelink"})
        with self.assertRaises(Refused):
            self.post("devto")

    def test_disabled_without_pin_or_config(self):
        self.assertIsNone(chs.adapter("bluesky", self.http))  # no pin, no config
        core.PINS["bluesky"] = dict(COMPANY["bluesky"])
        self.assertIsNone(chs.adapter("bluesky", self.http))  # pin, no config
        self.assertIn("no config", chs.status("bluesky"))
        core.PINS["bluesky"] = {"id": None, "handle": None}
        core.save_config("bluesky", {"id": "did:plc:company", "handle": "purplelink.llc", "app_password": "P"})
        self.assertIsNone(chs.adapter("bluesky", self.http))  # config alone does not enable it

    def test_world_readable_config_refused(self):
        self.enable("devto")
        os.chmod(core.config_dir() / "devto.json", 0o644)
        with self.assertRaises(Refused):
            chs.adapter("devto", self.http)

    def test_shipped_pins_are_empty_except_linkedin(self):
        for ch, p in self.old_pins.items():
            if ch != "linkedin":
                self.assertIsNone(p["id"], ch)
        self.assertEqual(self.old_pins["linkedin"]["id"], "120183926")


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

    def test_variants_fit_long_facts(self):
        f = {"kind": "release_published", "event_key": "release:legroom:9.0", "app_slug": "legroom", "name": "Legroom",
             "version": "9.0.0", "price": "9.99", "price_once": True, "url": "https://purplelink.llc/legroom/",
             "title": "Legroom 9.0.0", "notes": " ".join(["This sentence describes one change in plain words."] * 40)}
        vs = var.build_all(f)
        self.assertEqual(set(vs), {"linkedin", "bluesky", "threads", "x", "mastodon", "email"})
        self.assertEqual(var.problems(vs), [])
        for ch in ("bluesky", "x"):
            self.assertIn("Legroom 9.0.0", vs[ch])
            self.assertIn("$9.99 once", vs[ch])
            self.assertIn(f"https://purplelink.llc/{core.LINK_PREFIX[ch]}/legroom", vs[ch])

    def test_devto_only_for_guides_and_email_only_for_releases(self):
        g = var.build_all({"kind": "guide_live", "event_key": "guide:a", "slug": "a", "url": "https://purplelink.llc/guides/a/",
                           "title": "A", "description": "B."})
        self.assertIn("devto", g)
        self.assertNotIn("email", g)
        self.assertEqual(g["devto"]["canonical_url"], "https://purplelink.llc/guides/a/")


class Standing(Base):
    def test_full_guide_flow_posts_once(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        self.assertEqual(self.run_live(), 0)
        cur = [i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]
        # Other channels are disabled, so the item waits in approved/ in case one is enabled before it expires.
        self.assertEqual(cur["folder"], "approved")
        self.assertEqual(len(self.http.posted(r"createRecord")), 1)
        text = self.http.posted(r"createRecord")[0]["json_body"]["record"]["text"]
        self.assertIn("https://purplelink.llc/bs/g/demo-guide", text)
        self.assertIn('"actor": "standing-approval"', (aq.ROOT / "log.jsonl").read_text())
        self.assertEqual(self.run_live(), 0)
        self.assertEqual(len(self.http.posted(r"createRecord")), 1)  # the same item never posts twice
        aq.move(cur, "approved", {"expires": "2020-01-01"})
        self.run_live()
        cur = [i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]
        self.assertEqual(cur["folder"], "done")
        self.assertIn("bluesky: https://bsky.app/profile/purplelink.llc/post/abc", cur["body"])

    def test_404_target_stays_pending(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        self.live_guide(status=404)
        self.run_live()
        now = [i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]
        self.assertEqual(now["folder"], "pending")
        self.assertEqual(self.http.posted(r"createRecord"), [])
        self.assertTrue(any("not live" in o for o in self.out))

    def test_short_link_404_is_not_posted(self):
        self.enable("bluesky")
        self.bluesky_ok()
        self.guide_item()
        self.http.on("GET", r"/bs/g/demo-guide$", page("", 404))
        self.run_live()
        self.assertEqual(self.http.posted(r"createRecord"), [])

    def test_expired_item_is_not_posted(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item(at=core.now() - dt.timedelta(days=30))
        self.run_live()
        now = [i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]
        self.assertEqual(now["folder"], "pending")
        self.assertEqual(self.http.posted(r"createRecord"), [])

    def test_fact_drift_waits(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        self.http.on("GET", r"/guides/demo-guide/$", page(GUIDE_HTML.replace("Demo guide for Mac", "Renamed guide")))
        self.run_live()
        self.assertEqual([i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]["folder"], "pending")

    def test_edited_item_needs_ben(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        aq.move(it, "pending", {"status": "edited"})
        self.run_live()
        self.assertEqual(self.http.posted(r"createRecord"), [])
        self.assertTrue(any("needs Ben" in o for o in self.out))

    def test_non_standing_kind_needs_approval(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        aq.move(it, "pending", {"event_kind": "manual_post"})
        self.run_live()
        self.assertEqual([i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]["folder"], "pending")
        self.assertEqual(self.http.posted(r"createRecord"), [])
        self.assertTrue(any("Ben approves" in o for o in self.out))

    def test_ben_approved_item_posts(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        aq.move(it, "pending", {"status": "edited", "event_kind": "manual_post"})
        it = [i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]
        aq.decide(it, "approved", "approved")
        self.run_live()
        self.assertEqual(len(self.http.posted(r"createRecord")), 1)

    def test_duplicate_within_30_days(self):
        self.enable("bluesky")
        self.bluesky_ok()
        st = core.load_state()
        st["posts"].append({"channel": "bluesky", "item": "q-old", "event_key": "guide:demo-guide", "hash": "x",
                            "date": (core.now() - dt.timedelta(days=10)).date().isoformat(), "url": "https://bsky.app/x"})
        core.save_state(st)
        self.guide_item()
        self.run_live()
        self.assertEqual(self.http.posted(r"createRecord"), [])
        self.assertTrue(any("same event" in o for o in self.out))

    def test_lint_blocks_a_second_item_for_the_same_event(self):
        self.guide_item()
        facts = events.guide_facts(self.http, "demo-guide")
        folder, probs = poster.create_item(facts, live=True, offline=True)
        self.assertEqual(folder, "needs-work")
        self.assertTrue(any("30 days" in p for p in probs))

    def test_caps_one_a_day_three_a_week(self):
        self.enable("bluesky")
        self.bluesky_ok()
        today = core.now().date()
        st = core.load_state()
        st["posts"].append({"channel": "bluesky", "item": "q-a", "event_key": "a", "hash": "a", "date": today.isoformat(), "url": "u"})
        core.save_state(st)
        self.guide_item()
        self.run_live()
        self.assertEqual(self.http.posted(r"createRecord"), [])
        st = core.load_state()
        st["posts"] = [{"channel": "bluesky", "item": f"q-{i}", "event_key": str(i), "hash": str(i),
                        "date": (today - dt.timedelta(days=i)).isoformat(), "url": "u"} for i in (1, 2, 3)]
        core.save_state(st)
        self.run_live()
        self.assertEqual(self.http.posted(r"createRecord"), [])
        self.assertTrue(any("7 days" in o for o in self.out))

    def test_refusal_exits_4_and_is_not_retried_that_day(self):
        self.enable("bluesky")
        self.http.on("POST", r"createSession$", {"did": "did:plc:ben", "handle": "ben.bsky.social", "accessJwt": "J"})
        self.guide_item()
        self.assertEqual(self.run_live(), 4)
        self.assertEqual(core.load_state()["refused"]["bluesky"], core.now().date().isoformat())
        sessions = len(self.http.posted(r"createSession"))
        self.assertEqual(self.run_live(), 0)
        self.assertEqual(len(self.http.posted(r"createSession")), sessions)  # not tried again today
        self.assertIn("REFUSED", (core.home() / "log.jsonl").read_text())

    def test_dry_run_changes_nothing(self):
        self.enable("bluesky")
        self.bluesky_ok()
        it = self.guide_item()
        poster.run(self.http, live=False, out=self.out.append)
        self.assertEqual([i for i in aq.all_items() if i["fm"]["id"] == it["fm"]["id"]][0]["folder"], "pending")
        self.assertEqual(self.http.posted(r"."), [])
        self.assertTrue(any("would post" in o for o in self.out))


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

    def test_devto_markdown(self):
        self.live_guide()
        md = events.devto_markdown(self.http, {"url": "https://purplelink.llc/guides/demo-guide/"}, poster.dev_tagger())
        self.assertIn("## Part", md)
        self.assertIn("- One", md)
        self.assertIn("| A | B |", md)
        self.assertIn("(https://purplelink.llc/legroom/?utm_source=devto&utm_medium=social&utm_campaign=dev-guide)", md)


class QueueLint(unittest.TestCase):
    def test_poster_executor_only_for_poster_items(self):
        fm = {"executor": "poster", "job": "weekly-growth-scan", "kind": "post"}
        _, probs = aq.lint(fm, "", offline=True)
        self.assertTrue(any("executor poster" in p for p in probs))


if __name__ == "__main__":
    unittest.main()
