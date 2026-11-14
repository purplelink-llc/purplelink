import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmark"))

import tier_margin  # noqa: E402


def test_stripe_fee_matches_observed_live_charges():
    # Live Managed Payments charges on 2026-11-14: gross -> Stripe processing fee.
    for gross, fee in ((4.99, 0.44), (11.99, 0.83), (24.59, 1.38)):
        assert abs(tier_margin.stripe_fee(gross) - fee) <= 0.06


def test_bundle_cost_is_the_sum_of_its_parts_per_paper():
    costs = {"deep": [5.0, 7.0], "revision": [0.5, 0.6], "draft": [1.0, 2.0], "standard": [2.0]}
    rows = {r["product"]: r for r in tier_margin.margin_rows(costs)}
    pack = rows["publication-pack"]
    assert pack["n"] == 2 and pack["cost_max"] == 9.6 and pack["cost_median"] == 8.05
    assert pack["fee"] == 3.15 and pack["margin_worst_cost"] == round(59 - 3.15 - 9.6, 2)
    assert "journal" not in rows  # a product with no observed cost is left out, not shown as free


def test_ledger_and_tier_cost_report_the_same_cost_by_model():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from latextools import papercheck

    u = papercheck.UsageTracker()
    u.records += [{"model": "a", "cost_usd": 0.1}, {"model": "b", "cost_usd": 0.25}, {"model": "a", "cost_usd": 0.2}]
    assert u.cost_by_model() == {"a": 0.3, "b": 0.25}
