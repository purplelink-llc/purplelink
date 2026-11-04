"""Paper Review funnel (docs/designs/paper-review-growth.md, Part A): joins orders, jobs and free-check counters."""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))
sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td

DAY = 86400
TODAY = dt.date(2026, 11, 4)
T0 = dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc).timestamp()


def order(p, ts=T0, cust="c1", product="paper-review", net=1900, **kw):
    return {"id": "cs_" + p, "product": product, "kind": "purchase", "gross": net, "net": net, "ts": ts,
            "cust": cust, "purchase": p, **kw}


def job(p, ts=T0 + 60, status="done", cost=0.5, viewed=None, **kw):
    j = {"ts": ts, "status": status, "cost_usd": cost, "purchase": p}
    if viewed is not None:
        j["viewed_at"] = viewed
    return j | kw


def run(orders=(), comps=(), jobs=(), preview=None, **kw):
    return td.paper_review_funnel(list(orders), list(comps), [dict(j) for j in jobs], preview or {}, today=TODAY, **kw)


def test_sum_preview_counts_across_containers():
    out = td.sum_preview_counts([("preview:2026-11-03:ok:aa", 3), ("preview:2026-11-03:ok:bb", 2),
                                 ("preview:2026-11-03:limited:aa", 1), ("junk", 9), ("preview:2026-11-03:odd:aa", 4)])
    assert out == {"2026-11-03": {"ok": 5, "error": 0, "limited": 1}}


def test_activation_counts_beside_rate_and_flags_small_denominator():
    f = run([order("a"), order("b", cust="c2"), order("c", cust="c3")],
            jobs=[job("a", viewed=T0 + 100), job("b", viewed=T0 + 9 * DAY), job("c")])
    assert f["activated"]["text"] == "1 of 3" and f["activated"]["small"] is True
    assert f["signups"] == {"total": 3, "paid": 3, "comps": 0}


def test_refunded_orders_are_not_signups():
    f = run([order("a", refunded=1900), order("b", cust="c2")])
    assert f["signups"]["total"] == 1


def test_before_tracking_jobs_are_separate_and_excluded_from_margin():
    f = run([order("a")], jobs=[job("a", viewed=T0 + 10), {"ts": T0, "status": "done", "cost_usd": 2.0}])
    assert f["before_tracking"] == {"jobs": 1, "ok": 1, "model_cost_usd": 2.0}
    assert f["margin"]["paid_jobs_ok"] == 1 and f["margin"]["cost_usd"] == 0.5
    assert f["cost_per_evaluation"]["jobs_all"] == 2


def test_margin_divides_pack_revenue_by_quantity():
    f = run([order("a", product="paper-review-pack-5", net=10000)], jobs=[job("a", cost=1.0)])
    assert f["margin"]["revenue_per_eval_usd"] == 20.0
    assert f["margin"]["gross_margin"]["pct"] == 95.0


def test_comp_jobs_are_promotion_cost_not_margin():
    f = run([], comps=[{"id": "x", "purchase": "k", "ts": T0, "cust": "z", "product": "paper-review"}],
            jobs=[job("k", cost=0.7)])
    assert f["margin"] is None and f["promotion_cost_usd"] == 0.7 and f["signups"]["comps"] == 1


def test_repeat_and_comp_to_paid():
    comp = {"id": "x", "purchase": "k", "ts": T0, "cust": "z", "product": "paper-review"}
    f = run([order("p", ts=T0 + 5 * DAY, cust="z")], comps=[comp],
            jobs=[job("k", viewed=T0 + 100), job("p", ts=T0 + 5 * DAY, viewed=T0 + 6 * DAY)])
    assert f["comp_to_paid"]["text"] == "1 of 1"
    assert f["repeat"]["30d"]["text"] == "1 of 1"


def test_free_check_to_paid_is_an_upper_bound_proxy():
    f = run([order("a", pr_preview=True, ts=T0), order("b", cust="c2", ts=T0)],
            preview={"2026-11-01": {"ok": 8, "error": 1, "limited": 2}, "2026-08-01": {"ok": 99}})
    assert f["free_checks"]["ok"] == 8
    assert f["free_check_to_paid"]["text"] == "1 of 8" and "upper bound" in f["free_check_to_paid"]["note"]


def test_cac_by_channel_includes_spend_and_hours():
    f = run([order("a", attr={"first": {"s": "reddit", "r": "reddit.com"}})],
            jobs=[job("a")], spend_by_channel={"Reddit": 20}, hours_by_channel={"Reddit": 1})
    row = f["cac_by_channel"][0]
    assert row["channel"] == "Reddit" and row["cac_usd"] == 70.0 and row["small"] is True


def test_ledger_orders_of_other_products_are_ignored():
    f = run([order("a", product="moderntex")])
    assert f["signups"]["total"] == 0


def test_write_is_best_effort_and_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(td, "PR_FUNNEL_PATH", tmp_path / "paper_review_funnel.json")
    h = {"ledger": {"cs_a": order("a")}, "apiUsage": [job("a", viewed=T0 + 5)],
         "previewDaily": {}, "prComps": {}}
    out = td.write_paper_review_funnel(h, today=TODAY)
    assert out["signups"]["total"] == 1
    assert json.loads((tmp_path / "paper_review_funnel.json").read_text())["activated"]["n"] == 1
    assert td.write_paper_review_funnel({"ledger": 5}, today=TODAY) is None
