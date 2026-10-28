"""Scheduler: due, stale, pause, window, approval, idempotency, retries, refusals, write-back, logs."""
import datetime as dt

import pytest

from social_helpers import env, make_png  # noqa: F401
from socialpost import config as cfgmod
from socialpost import engine, items, paths
from socialpost.adapters.base import Adapter, Result
from socialpost.errors import Ambiguous, Refused, SocialError

NOON = dt.datetime(2026, 10, 20, 16, 0, tzinfo=dt.timezone.utc)  # Tuesday 12:00 Eastern


@pytest.fixture(autouse=True)
def _pin_item_clock(monkeypatch):
    """The engine runs on the clock each test passes, but items.approve() checks staleness against items.now().
    Pin it to NOON, or every approval of a NOON-relative item fails once the real date is 48 hours past it."""
    monkeypatch.setattr(items, "now", lambda: NOON)


class Fake(Adapter):
    """Scripted adapter. Behaviour is chosen by class attribute `plan` (name -> list of outcomes)."""
    plan: dict = {}
    posted: list = []
    name = "fake"

    def whoami(self):
        return {}

    def check_identity(self):
        return {}

    def post(self, item, dry_run=False):
        outcome = Fake.plan.get(self.name, ["ok"])
        o = outcome.pop(0) if len(outcome) > 1 else outcome[0]
        if isinstance(o, Exception):
            raise o
        Fake.posted.append((item.id, self.name))
        return Result(url=f"https://example.test/{self.name}/{len(Fake.posted)}", id=f"id{len(Fake.posted)}")

    def verify(self, url):
        return True


def fakes():
    out = {}
    for p in ("linkedin", "bluesky", "threads", "mastodon", "x"):
        out[p] = type(p.title(), (Fake,), {"name": p})
    return out


@pytest.fixture(autouse=True)
def reset():
    Fake.plan, Fake.posted = {}, []


def cfg_all_on():
    cfg = cfgmod.load()
    for p in cfg["platforms"].values():
        p["enabled"] = True
    cfg["windows"] = {"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59"}
    return cfg



@pytest.fixture(autouse=True)
def _approval_clock_at_noon(monkeypatch):
    """items.approve() checks scheduled_at against items.now(); pin it to the test day so a fixed NOON does not turn
    every approval stale once the real clock is 48 hours past it (these tests broke on 2026-10-22)."""
    monkeypatch.setattr(items, "now", lambda: NOON)

def approved(env, platforms=("linkedin", "bluesky"), at=None, cfg=None):
    it = items.create("t", list(platforms), "https://purplelink.llc/vitae/", "vitae-140")
    it.sections["default"] = "Post text {link}"
    it.meta["scheduled_at"] = (at or (NOON - dt.timedelta(minutes=5))).isoformat()
    it.meta["experiment_note"] = "compare with quiet days"
    it.save()
    items.approve(it, cfg or cfg_all_on())
    return items.Item.load(it.path)


def run(env, cfg=None, when=NOON):
    return engine.run_due(cfg or cfg_all_on(), factory=fakes(), when=when)


def reload(it):
    return items.Item.load(it.path)


def test_posts_an_approved_due_item_and_writes_results_back(env):
    it = approved(env)
    run(env)
    done = reload(it)
    assert done.status == "posted" and sorted(Fake.posted) == [(it.id, "bluesky"), (it.id, "linkedin")]
    for p in ("linkedin", "bluesky"):
        r = done.results[p]
        assert r["status"] == "posted" and r["url"].startswith("https://example.test/") and r["id"] and r["posted_at"] and r["error"] is None


def test_drafts_never_post(env):
    it = items.create("t", ["bluesky"], "https://purplelink.llc/", "c", (NOON - dt.timedelta(minutes=5)).isoformat())
    it.sections["default"] = "x {link}"
    it.save()
    run(env)
    assert Fake.posted == [] and reload(it).status == "draft"


def test_forged_approval_without_the_hash_never_posts(env):
    it = items.create("t", ["bluesky"], "https://purplelink.llc/", "c", (NOON - dt.timedelta(minutes=5)).isoformat())
    it.sections["default"] = "x {link}"
    it.meta.update(status="approved", approved_by="ben", approved_at="2026-10-20T00:00:00+00:00")
    it.save()
    run(env)
    assert Fake.posted == [] and reload(it).status == "draft"
    assert any("approval void" in l for l in open(env.tmp / "social.log").read().splitlines())


def test_editing_after_approval_voids_it(env):
    it = approved(env)
    it.sections["default"] = "Sneaky edit {link}"
    it.save()
    run(env)
    assert Fake.posted == [] and reload(it).status == "draft"


def test_pause_file_posts_nothing(env):
    approved(env)
    env.home.mkdir(parents=True, exist_ok=True)
    paths.pause_file().touch()
    lines = run(env)
    assert Fake.posted == [] and "PAUSE" in lines[0]


def test_not_yet_due_waits(env):
    it = approved(env, at=NOON + dt.timedelta(hours=1))
    run(env)
    assert Fake.posted == [] and reload(it).status == "approved"


def test_more_than_48_hours_late_is_stale_not_posted(env):
    it = approved(env, at=NOON - dt.timedelta(hours=1))
    it.meta["scheduled_at"] = (NOON - dt.timedelta(hours=49)).isoformat()
    # re-approve is blocked for stale times, so forge by approving then moving the clock instead
    run(env, when=NOON + dt.timedelta(hours=48))
    assert Fake.posted == [] and reload(it).status == "stale"
    assert any("stale" in n for n in env.notes)


def test_stale_item_can_be_rescheduled_and_reapproved(env):
    cfg = cfg_all_on()
    it = approved(env, at=NOON - dt.timedelta(hours=1))
    run(env, when=NOON + dt.timedelta(hours=60))
    it = reload(it)
    assert it.status == "stale"
    it.meta["scheduled_at"] = (NOON + dt.timedelta(hours=61)).isoformat()
    it.save()
    items.approve(it, cfg)
    run(env, when=NOON + dt.timedelta(hours=62))
    assert reload(it).status == "posted"


def test_outside_the_posting_window_waits(env):
    cfg = cfg_all_on()
    cfg["windows"] = {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "09:00"}
    it = approved(env)
    run(env, cfg)
    assert Fake.posted == [] and reload(it).status == "approved"


def test_second_run_never_double_posts(env):
    it = approved(env)
    run(env)
    n = len(Fake.posted)
    run(env)
    run(env, when=NOON + dt.timedelta(hours=3))
    assert len(Fake.posted) == n == 2 and reload(it).status == "posted"


def test_a_platform_that_succeeded_is_not_retried_when_the_other_fails(env):
    Fake.plan = {"bluesky": [SocialError("flaky"), SocialError("flaky"), "ok"]}
    it = approved(env)
    cfg = cfg_all_on()
    run(env, cfg)
    r = reload(it)
    assert r.results["linkedin"]["status"] == "posted" and r.results["bluesky"]["status"] == "pending"
    assert r.results["bluesky"]["attempts"] == 1 and r.results["bluesky"]["next_attempt_at"]
    run(env, cfg, NOON + dt.timedelta(minutes=5))   # backoff not over: untouched
    assert reload(it).results["bluesky"]["attempts"] == 1
    run(env, cfg, NOON + dt.timedelta(minutes=15))
    run(env, cfg, NOON + dt.timedelta(hours=2))
    done = reload(it)
    assert done.status == "posted" and done.results["bluesky"]["attempts"] == 3
    assert [p for _, p in Fake.posted].count("linkedin") == 1


def test_three_failures_mark_failed_and_notify(env):
    Fake.plan = {"bluesky": [SocialError("down")]}
    it = approved(env, ("bluesky",))
    cfg = cfg_all_on()
    for minutes in (0, 20, 120, 300, 600):
        run(env, cfg, NOON + dt.timedelta(minutes=minutes))
    done = reload(it)
    assert done.status == "failed" and done.results["bluesky"]["status"] == "failed" and done.results["bluesky"]["attempts"] == 3
    assert len([n for n in env.notes if "failed" in n.lower()]) == 1  # one summary, not one per retry


def test_ambiguous_publish_is_never_retried(env):
    Fake.plan = {"bluesky": [Ambiguous("may be live")]}
    it = approved(env, ("bluesky",))
    cfg = cfg_all_on()
    run(env, cfg)
    run(env, cfg, NOON + dt.timedelta(hours=3))
    done = reload(it)
    assert done.results["bluesky"]["status"] == "failed" and done.results["bluesky"].get("ambiguous")
    assert done.results["bluesky"]["attempts"] == 1


def test_identity_refusal_posts_nothing_notifies_and_does_not_retry(env):
    Fake.plan = {"bluesky": [Refused("signed in as 'ben'")]}
    it = approved(env)
    cfg = cfg_all_on()
    run(env, cfg)
    run(env, cfg, NOON + dt.timedelta(hours=3))
    done = reload(it)
    assert done.results["bluesky"]["status"] == "refused" and done.results["linkedin"]["status"] == "posted"
    assert [p for _, p in Fake.posted] == ["linkedin"]
    assert any("REFUSED" in n for n in env.notes)


def test_a_run_that_died_mid_post_is_not_retried(env):
    it = approved(env, ("bluesky",))
    it.results["bluesky"] = {"status": "posting", "attempts": 1}
    it.save()
    run(env)
    assert Fake.posted == [] and "may be live" in reload(it).results["bluesky"]["error"]


def test_disabled_platforms_are_skipped_not_posted(env):
    cfg = cfg_all_on()
    cfg["platforms"]["threads"]["enabled"] = False
    it = approved(env, ("bluesky", "threads"), cfg=cfg)
    run(env, cfg)
    done = reload(it)
    assert done.results["threads"]["status"] == "skipped" and done.results["bluesky"]["status"] == "posted"
    assert done.status == "posted" and [p for _, p in Fake.posted] == ["bluesky"]


def test_finishing_writes_outreach_log_and_change_log_and_notifies_once(env):
    it = approved(env)
    run(env)
    log = env.outreach.read_text()
    assert log.count("| posted |") == 2 and it.id in log and "utm_campaign=vitae-140" in log
    chg = env.changes.read_text()
    assert "--area outreach" in chg and "vitae-140" in chg and "compare with quiet days" in chg
    assert len([n for n in env.notes if it.id in n]) == 1


def test_item_that_no_longer_validates_goes_back_to_draft(env):
    cfg = cfg_all_on()
    it = approved(env, ("bluesky",), cfg=cfg)
    p = env.tmp / "gone.png"
    make_png(p)
    it.meta["images"] = [{"path": str(p), "alt": "x"}]
    it.meta["approved_hash"] = it.content_hash()   # an image was added and approved ...
    it.save()
    p.unlink()                                      # ... then vanished
    run(env, cfg)
    assert Fake.posted == [] and reload(it).status == "draft"


def test_overlapping_runs_are_blocked_by_the_lock(env):
    approved(env)
    with engine.single_instance() as first:
        assert first
        lines = run(env)
        assert any("another run-due" in l for l in lines)
    assert Fake.posted == []


def test_nothing_due_logs_it(env):
    assert run(env) == ["nothing due"]


def test_threads_token_is_refreshed_after_30_days(env, monkeypatch):
    from socialpost import setup
    seen = []

    class T(Fake):
        name = "threads"

        def refresh(self):
            seen.append("refreshed")

    cfg = cfg_all_on()
    setup.note_token_time("threads", NOON - dt.timedelta(days=31))
    engine.run_due(cfg, factory={**fakes(), "threads": T}, when=NOON)
    assert seen == ["refreshed"] and setup.token_age_days("threads", NOON) < 1
    seen.clear()
    engine.run_due(cfg, factory={**fakes(), "threads": T}, when=NOON + dt.timedelta(days=1))
    assert seen == []
