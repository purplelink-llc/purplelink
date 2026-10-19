"""Daily pipeline end to end with fakes: pick, vet, queue under standing approval, time-of-day rules, caps, the
Mastodon inclusion, and that the existing engine is the only thing that posts."""
import datetime as dt
import json

import pytest

from social_daily_helpers import FakeHttp, denv, env, site  # noqa: F401
from social_helpers import make_png  # noqa: F401
from socialpost import engine, items, paths
from socialpost.adapters.base import Adapter, Result
from socialpost.daily import pipeline, settings as st
from socialpost.daily.pipeline import run_daily

UTC = dt.timezone.utc
# Tuesday 2026-10-20: 09:00 Eastern is before the pick time, 14:00 UTC = 10:00 Eastern.
TEN = dt.datetime(2026, 10, 20, 14, 0, tzinfo=UTC)
ADDED = {"/guides/new-guide/": dt.date(2026, 10, 18), "/guides/old-guide/": dt.date(2026, 5, 1),
         "/tools/word-counter/": dt.date(2026, 4, 1)}
STATS = {"topPaths": [{"key": "/tools/word-counter/", "count": 90}, {"key": "/guides/old-guide/", "count": 30},
                      {"key": "/blog/digest/", "count": 500}]}


def go(denv, http=None, when=TEN, **kw):
    http = http or site()
    kw.setdefault("stats", STATS)
    kw.setdefault("added", ADDED)
    kw.setdefault("ledger", [])
    kw.setdefault("notify", lambda m: denv.notes.append(m))
    kw.setdefault("say", lambda m: None)
    return run_daily(http, st.load(), denv.cfg, when, **kw), http


def test_queues_the_top_candidate_with_standing_approval_for_all_four_platforms(denv):
    res, http = go(denv)
    assert res["status"] == "queued" and res["candidate"] == "release:panely:1.1.0"
    it = items.find(res["item"])
    assert it.platforms == ["linkedin", "bluesky", "threads", "mastodon"]
    assert it.meta["approved_by"] == items.STANDING_BY and it.meta["source"] == "social-daily"
    assert it.approval_valid() == (True, "")
    assert it.campaign == "daily-release" and it.link == "https://purplelink.llc/panely/"
    for p in it.platforms:
        assert f"utm_source={p}&utm_medium=social&utm_campaign=daily-release" in it.render(p)
    assert http.posted() == []  # the pipeline itself never posts


def test_stats_token_goes_in_a_header_never_in_the_url(denv):
    h = site()
    h.on("GET", r"/\.netlify/functions/stats", STATS)
    run_daily(h, st.load(), denv.cfg, TEN, dry_run=True, added=ADDED, ledger=[], say=lambda m: None)
    c = [c for c in h.calls if "functions/stats" in c["url"]][0]
    assert c["headers"].get("x-stats-token") == "test-token-123" and "test-token" not in c["url"]


def test_time_of_day_rules(denv):
    early = dt.datetime(2026, 10, 20, 12, 0, tzinfo=UTC)   # 08:00 Eastern
    assert go(denv, when=early)[0]["status"] == "too-early"
    late = dt.datetime(2026, 10, 21, 1, 0, tzinfo=UTC)     # 21:00 Eastern: past the last pick
    assert go(denv, when=late)[0]["status"] == "missed"
    assert go(denv, when=late)[0]["status"] == "done-already"


def test_a_late_pick_is_scheduled_for_now_not_the_past_slot(denv):
    afternoon = dt.datetime(2026, 10, 20, 19, 40, tzinfo=UTC)  # 15:40 Eastern, slot was 10:30
    res, _ = go(denv, when=afternoon)
    t = items.parse_time(res["scheduled_at"])
    assert dt.timedelta(minutes=1) <= t - afternoon <= dt.timedelta(minutes=5)


def test_morning_pick_is_scheduled_for_the_slot(denv):
    res, _ = go(denv)
    assert items.parse_time(res["scheduled_at"]) == dt.datetime(2026, 10, 20, 14, 30, tzinfo=UTC)  # 10:30 Eastern


def test_once_a_day_and_history_recorded(denv):
    res, _ = go(denv)
    assert go(denv)[0]["status"] == "done-already"
    h = st.load_history()
    assert len(h) == 1 and h[0]["candidate"] == res["candidate"] and h[0]["format"] == res["format"]


def test_dry_run_writes_nothing(denv):
    res, _ = go(denv, dry_run=True)
    assert res["status"] == "dry-run" and res["texts"]
    assert items.list_items() == [] and st.load_history() == []


def test_pause_stops_the_pick(denv):
    paths.home().mkdir(parents=True, exist_ok=True)
    paths.pause_file().touch()
    assert go(denv)[0]["status"] == "paused" and items.list_items() == []


def test_failing_the_gate_moves_to_the_next_candidate_and_logs_why(denv):
    h = site()
    from social_daily_helpers import product
    seen = {"n": 0}

    def flaky(call):  # live while the facts are read, gone when the gate re-checks the link
        seen["n"] += 1
        return product("panely", "Panely", "1.1.0") if seen["n"] == 1 else Response404()
    h.on("GET", r"^https://purplelink\.llc/panely/$", flaky)
    res, _ = go(denv, http=h)
    assert res["status"] == "queued" and res["candidate"] != "release:panely:1.1.0"
    assert any("release:panely:1.1.0" in e and "link answered 404" in e for e in res["excluded"])


class Response404:
    def __new__(cls):
        from socialpost.daily.lib219 import Response
        return Response(404, b"nope")


def test_all_candidates_failing_posts_nothing_and_notifies_once(denv):
    h = site()
    h.on("GET", r"purplelink\.llc/(panely|guides|tools)/", Response404())
    res, _ = go(denv, http=h)
    assert res["status"] == "nothing-passed" and items.list_items() == []
    assert len([n for n in denv.notes if "no candidate passed" in n]) == 1


def test_one_post_per_platform_per_day(denv):
    first, _ = go(denv)
    it = items.find(first["item"])
    # an earlier item already holds linkedin and bluesky today: a second run (force) only uses the others
    it.meta["platforms"] = ["linkedin", "bluesky"]
    it.meta["status"] = "posted"
    it.save()
    paths_state = pipeline.state_file()
    paths_state.unlink()
    res, _ = go(denv, force=True)
    assert res["status"] == "queued" and res["platforms"] == ["threads", "mastodon"]


def test_mastodon_is_in_the_daily_run_in_ben_voice(denv):
    res, _ = go(denv)
    t = res["texts"]["mastodon"]
    assert t.startswith("Panely 1.1.0\n\nI shipped this release this week")
    assert "utm_source=mastodon" in t and len(t) <= 500
    assert "—" not in t and "Moreover" not in t


def test_x_is_never_covered_by_standing_approval(denv):
    it = items.create("t", ["x"], "https://purplelink.llc/", "daily-guide")
    it.sections["default"] = "Hello. {link}"
    it.meta["source"] = items.STANDING_SOURCE
    it.save()
    with pytest.raises(ValueError):
        items.approve_standing(it, denv.cfg)


def test_standing_approval_needs_the_daily_source(denv):
    it = items.create("t", ["bluesky"], "https://purplelink.llc/", "daily-guide")
    it.sections["default"] = "Hello. {link}"
    it.save()
    with pytest.raises(ValueError):
        items.approve_standing(it, denv.cfg)
    items.approve(it, denv.cfg, items.STANDING_BY)   # forged route: the hash is right but the source is wrong
    ok, why = items.Item.load(it.path).approval_valid()
    assert not ok and "daily pipeline" in why


def test_hand_edit_after_standing_approval_voids_it(denv):
    res, _ = go(denv)
    it = items.find(res["item"])
    it.sections["bluesky"] = "Edited by hand. {link}"
    it.save()
    assert items.Item.load(it.path).approval_valid()[0] is False


def test_card_format_attaches_a_hosted_image_and_alt_text(denv):
    res, _ = go(denv)
    assert res["format"] == "card"
    it = items.find(res["item"])
    im = it.meta["images"][0]
    assert im["alt"].strip() and set(im["platforms"]) == {"bluesky", "threads", "mastodon"}
    assert "linkedin" in it.meta["text_only"]


def test_threads_image_waits_for_the_image_function(denv):
    h = site()
    h.on("GET", r"/social-media/0{40}\.png$", Response404())  # HTML 404: the function is not deployed
    res, _ = go(denv, http=h)
    assert "threads" not in res["images"][0]["platforms"]


# ---- single posting path: the existing engine posts the daily item, with the standing approval string
class Fake(Adapter):
    posted: list = []
    name = "fake"

    def whoami(self):
        return {}

    def check_identity(self):
        return {}

    def post(self, item, dry_run=False):
        Fake.posted.append((item.id, self.name))
        return Result(url=f"https://example.test/{self.name}", id="1")

    def verify(self, url):
        return True


def test_engine_posts_the_daily_item_and_nothing_else_does(denv):
    Fake.posted = []
    res, _ = go(denv)
    cfg = denv.cfg
    cfg["windows"] = {"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59"}
    fakes = {p: type(p, (Fake,), {"name": p}) for p in ("linkedin", "bluesky", "threads", "mastodon", "x")}
    when = dt.datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # after the 10:30 Eastern slot
    engine.run_due(cfg, factory=fakes, when=when)
    assert sorted(p for _, p in Fake.posted) == ["bluesky", "linkedin", "mastodon", "threads"]
    done = items.find(res["item"])
    assert done.status == "posted"
    assert "approved by ben (standing, 2026-10-18)" in open(denv.outreach).read()
    engine.run_due(cfg, factory=fakes, when=when)
    assert len(Fake.posted) == 4  # nothing twice
