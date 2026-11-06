"""Buddy chat usage export: counts per day, tests set apart, no message text, safe when Modal is down."""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import buddy_export as be

T = dt.datetime(2026, 11, 3, 15, tzinfo=dt.timezone.utc).timestamp()
TODAY = dt.date(2026, 11, 6)


def convo(cid, start, n=2):
    return (f"convo:{cid}", {"n": n, "replies": ["SECRET REPLY TEXT"], "expires": start + be.CONVO_TTL_SECONDS})


def test_convo_day_comes_from_expiry_and_live_test_is_set_apart():
    d = be.summarize([convo("abc", T, 3), convo("live-test-1", T, 5)])
    assert d["2026-11-03"]["convos"] == 1 and d["2026-11-03"]["turns"] == 3
    assert d["2026-11-03"]["test_convos"] == 1 and d["2026-11-03"]["test_turns"] == 5


def test_burst_of_convos_in_an_hour_is_a_test():
    burst = [convo(f"r{i}", T + i * 60) for i in range(12)]
    later = convo("real", T + 5 * 3600)
    d = be.summarize(burst + [later])
    assert d["2026-11-03"]["test_convos"] == 12 and d["2026-11-03"]["convos"] == 1


def test_claims_coupons_strikes_spend():
    items = [("claim:aaa", {"at": T, "state": "sent"}),
             ("claim:bbb", {"at": T, "state": "redeemed", "redeemed_at": T + 86400}),
             ("claim:coupon:ccc", {"at": T, "state": "sent"}),
             ("coupon:s:sid", {"code": "X", "expires_at": T + be.COUPON_ASK_SECONDS}),
             ("strikelog:2026-11-03:injection:ab12", 1), ("strikelog:2026-11-03:injection:cd34", 1),
             ("strikelog:2026-11-03:rate:ef56", 1),
             ("spend:day:2026-11-03", 0.031), ("spend:month:2026-11", 0.05), ("junk", 1)]
    d = be.summarize(items)
    r = d["2026-11-03"]
    assert (r["free_sent"], r["coupons"], r["spend"]) == (2, 2, 0.031)
    assert r["strikes"] == {"injection": 2, "rate": 1}
    assert d["2026-11-04"]["free_redeemed"] == 1


def test_odd_records_are_skipped():
    assert be.summarize([("convo:x", {"n": "many", "expires": "soon"}), ("claim:y", {"at": "never"})]) == {}


def test_merge_keeps_days_the_dict_forgot_and_never_lowers():
    old = {"2026-11-02": {**be._blank(), "convos": 4}, "2026-11-03": {**be._blank(), "convos": 5, "strikes": {"a": 3}}}
    new = {"2026-11-03": {**be._blank(), "convos": 2, "strikes": {"a": 1, "b": 1}}}
    m = be.merge_history(old, new)
    assert m["2026-11-02"]["convos"] == 4 and m["2026-11-03"]["convos"] == 5
    assert m["2026-11-03"]["strikes"] == {"a": 3, "b": 1}


def test_build_window_and_totals():
    hist = be.merge_history({}, be.summarize([convo("a", T, 4), ("spend:day:2026-11-03", 0.02)]))
    out = be.build(hist, TODAY, None, "now")
    assert len(out["days"]) == 28 and out["days"][-1]["day"] == "2026-11-06"
    assert out["totals"]["convos"] == 1 and out["totals"]["turns"] == 4 and out["month_spend"] == 0.02


def test_run_writes_counts_only_and_skips_when_modal_down(tmp_path, monkeypatch):
    monkeypatch.setattr(be, "holdout_status", lambda t: {"verdict": "running"})
    now = dt.datetime(2026, 11, 6, 12, tzinfo=dt.timezone.utc)
    assert be.run(tmp_path / "out", tmp_path, items=[convo("a", T)], now=now) is True
    text = (tmp_path / "out" / "buddy_daily.json").read_text() + (tmp_path / "out" / "buddy_summary.json").read_text()
    assert "SECRET" not in text
    assert json.loads((tmp_path / "out" / "buddy_summary.json").read_text())[0]["convos"] == 1
    assert len(json.loads((tmp_path / "out" / "buddy_daily.json").read_text())) == 28
    monkeypatch.setattr(be, "fetch_items", lambda: None)
    (tmp_path / "out" / "buddy_daily.json").unlink()
    assert be.run(tmp_path / "out", tmp_path, now=now) is False
    assert not (tmp_path / "out" / "buddy_daily.json").exists()


def test_fetch_items_none_when_modal_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "modal", None)
    assert be.fetch_items() is None


def test_main_exits_zero_when_unreachable(monkeypatch, tmp_path):
    monkeypatch.setattr(be, "fetch_items", lambda: None)
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path)])
    assert be.main() == 0
