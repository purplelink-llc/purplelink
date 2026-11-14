#!/usr/bin/env python3
# backend/benchmark/tier_margin.py
"""Cost and margin per Paper Review product, from tier_cost.py results and/or the live usage ledger.
    python3 benchmark/tier_margin.py result1.json result2.json ...   # benchmark runs (one per paper)
    python3 benchmark/tier_margin.py --ledger                        # live jobs (needs Modal credentials)

Margin is the list price, less Stripe's fee, less the model cost. Fee: 5% + $0.20 of the gross, fitted to this
account's live Managed Payments charges on 2026-11-14 ($4.99 -> $0.44, $11.99 -> $0.83, $24.59 -> $1.38). Prices are
tax-inclusive, so sales tax or VAT (0% to about 20% by buyer location) also comes out of the price; the table shows
margin before that tax and the worst case at 20%.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

FEE_PCT, FEE_FIXED = 0.05, 0.20
WORST_TAX = 0.20
# Prices from PAID_PRODUCTS in app.py. A bundle's cost is the sum of its parts' costs.
PRODUCTS = {
    "standard": ("Paper Review Standard", 14.0, ("standard",)),
    "journal": ("Paper Review Journal", 24.0, ("journal",)),
    "deep": ("Paper Review Deep", 39.0, ("deep",)),
    "revision": ("Revision Review", 5.0, ("revision",)),
    "response": ("Response Review", 12.0, ("response",)),
    "draft": ("Response draft", 24.0, ("draft",)),
    "publication-pack": ("Publication Pack", 59.0, ("deep", "revision", "draft")),
}
# Ledger product keys -> the names above (the ledger keys a pack token as paper-review-standard).
LEDGER_KEYS = {"paper-review-standard": "standard", "paper-review-journal": "journal", "paper-review-deep": "deep",
               "revision-review": "revision", "response-review": "response", "response-draft": "draft"}


def stripe_fee(price: float) -> float:
    return round(price * FEE_PCT + FEE_FIXED, 2)


def margin_rows(costs: dict[str, list[float]]) -> list[dict]:
    """costs maps a part name to its observed costs (one per paper or job, in the same paper order for bundles).
    Returns one row per product with every part observed."""
    rows = []
    for key, (label, price, parts) in PRODUCTS.items():
        if not all(costs.get(p) for p in parts):
            continue
        n = min(len(costs[p]) for p in parts)
        totals = [sum(costs[p][i] for p in parts) for i in range(n)]
        fee = stripe_fee(price)
        mx = max(totals)
        net = price - fee
        rows.append({"product": key, "label": label, "price": price, "n": n, "fee": fee,
                     "cost_median": round(statistics.median(totals), 2), "cost_max": round(mx, 2),
                     "margin_worst_cost": round(net - mx, 2), "margin_pct": round((net - mx) / price * 100),
                     "margin_worst_cost_and_tax": round(price / (1 + WORST_TAX) - fee - mx, 2)})
    return rows


def costs_from_benchmarks(paths: list[str]) -> dict[str, list[float]]:
    costs: dict[str, list[float]] = {}
    for p in paths:
        with open(p) as f:
            res = json.load(f)
        for name, use in res.get("products", {}).items():
            costs.setdefault(name, []).append(float(use["usd"]))
    return costs


def costs_from_ledger() -> dict[str, list[float]]:
    import modal
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from latextools.durable_dict import DurableDict

    d = DurableDict(modal.Dict.from_name("paper-review-usage-ledger"),
                    modal.Volume.from_name("paper-review-durable"), "usage-ledger")
    costs: dict[str, list[float]] = {}
    for _k, r in d.items():
        name = LEDGER_KEYS.get(r.get("product_key") or "")
        if name and r.get("models") and r.get("status") in ("done", "ok"):
            costs.setdefault(name, []).append(float(r.get("cost_usd") or 0))
    return costs


def render(rows: list[dict]) -> str:
    head = "| Product | Price | Stripe fee | Cost median | Cost max | Margin (max cost) | Same, 20% tax | n |\n"
    head += "|---|---:|---:|---:|---:|---:|---:|---:|\n"
    return head + "".join(
        f"| {r['label']} | ${r['price']:.2f} | ${r['fee']:.2f} | ${r['cost_median']:.2f} | ${r['cost_max']:.2f} | "
        f"${r['margin_worst_cost']:.2f} ({r['margin_pct']}%) | ${r['margin_worst_cost_and_tax']:.2f} | {r['n']} |\n"
        for r in rows)


if __name__ == "__main__":
    args = sys.argv[1:]
    data = costs_from_ledger() if args == ["--ledger"] else costs_from_benchmarks(args)
    print(render(margin_rows(data)))
