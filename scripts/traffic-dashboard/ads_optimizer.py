#!/usr/bin/env python3
"""Daily optimization pass over Apple Search Ads keywords (GlobePin).

  python3 ads_optimizer.py            # human summary
  python3 ads_optimizer.py --json     # machine-readable

Reads ~/.purplelink/traffic/asa-keywords.json (record_asa_keywords.py) and
manual-ads.json (campaign daily budget). Advisory only: it never changes the
account. Every recommendation names its sample so small numbers are not
mistaken for signal.

What it answers each day:
  1. Delivery: how much of the daily budget was actually spent, and is the budget
     or the auction the limit? (Spend far under budget means bids or volume are
     the limit; raising the budget cannot help.)
  2. Per keyword: no impressions at its bid (not winning auctions or no volume),
     impressions but no taps (irrelevant), taps but no installs (wrong audience or
     page), or installs (scale it), each with a suggested bid step.
Daily numbers come from differences between successive snapshots of a growing
window ("Last 30 days"); the first snapshot is the baseline.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
SNAP = TRAFFIC / "asa-keywords.json"
SHARE = TRAFFIC / "asa-impression-share.json"
MANUAL = TRAFFIC / "manual-ads.json"

TARGET_CPI = 1.50      # dollars per install we are willing to pay; edit as GlobePin Pro economics firm up
DEAD_DAYS = 5          # days at a bid with zero impressions before we call it
BUMP = 1.5             # bid multiplier when a keyword is not winning auctions
MAX_BID = 2.00
MIN_BID = 0.25
NOIMP_HIGH = 300       # impressions with zero taps before a keyword is called irrelevant
TAPS_NO_INSTALL = 10   # taps with zero installs before we cut the bid
TAPS_PAUSE = 20
UNDER_BUDGET = 0.5     # utilization below this = auction/volume limited
NEAR_BUDGET = 0.9      # above this = budget limited


def money(v: float) -> str:
    return f"${v:,.2f}"


def load() -> dict:
    return json.loads(SNAP.read_text()).get("snapshots", {}) if SNAP.exists() else {}


def budget_from(snaps: dict) -> float | None:
    for d in sorted(snaps, reverse=True):
        if snaps[d].get("dailyBudget"):
            return float(snaps[d]["dailyBudget"])
    try:
        camps = json.loads(MANUAL.read_text()).get("appleSearchAds", {}).get("campaigns") or []
        return float(camps[0].get("dailyBudget")) if camps else None
    except Exception:
        return None


def by_kw(snap: dict) -> dict[str, dict]:
    return {k["keyword"]: k for k in snap.get("keywords", [])}


def daily_delta(cur: dict, prev: dict | None) -> dict:
    p = prev or {"spend": 0, "impressions": 0, "taps": 0, "installs": 0}
    return {f: max(0, cur[f] - p[f]) for f in ("spend", "impressions", "taps", "installs")}


def since_bid(dates: list[str], snaps: dict, kw: str) -> tuple[int, dict]:
    """Index of the snapshot that the current bid's run is measured from, and the keyword's
    totals in it (zeros when the keyword did not exist yet). The run covers activity after that
    snapshot, so a bid changed between two snapshots is measured from the earlier one."""
    zero = {"spend": 0.0, "impressions": 0, "taps": 0, "installs": 0}
    cur_bid = by_kw(snaps[dates[-1]])[kw]["bid"]
    start = len(dates) - 1
    while start > 0:
        row = by_kw(snaps[dates[start - 1]]).get(kw)
        if row is None or row["bid"] != cur_bid:
            break
        start -= 1
    base_idx = max(start - 1, 0) if start > 0 else 0
    row = by_kw(snaps[dates[base_idx]]).get(kw)
    return base_idx, ({f: row[f] for f in zero} if row and start > 0 else ({f: row[f] for f in zero} if row and base_idx == 0 else zero))


def analyze(snaps: dict, today: dt.date | None = None) -> dict:
    dates = sorted(snaps)
    if not dates:
        return {"error": "no snapshots yet"}
    today = today or dt.date.today()
    last = dates[-1]
    cur = by_kw(snaps[last])
    prev_snap = by_kw(snaps[dates[-2]]) if len(dates) > 1 else None
    budget = budget_from(snaps)

    # 1. delivery
    per_day = []
    for i in range(1, len(dates)):
        a, b = by_kw(snaps[dates[i - 1]]), by_kw(snaps[dates[i]])
        s = sum(max(0, b[k]["spend"] - (a.get(k) or {"spend": 0})["spend"]) for k in b)
        gap = (dt.date.fromisoformat(dates[i]) - dt.date.fromisoformat(dates[i - 1])).days or 1
        per_day.append({"date": dates[i], "spend": round(s / gap, 2)})
    recent = per_day[-5:]
    avg_spend = sum(d["spend"] for d in recent) / len(recent) if recent else None
    delivery = {"budget": budget, "yesterday": per_day[-1]["spend"] if per_day else None,
                "avg5": round(avg_spend, 2) if avg_spend is not None else None,
                "utilization": round(avg_spend / budget, 2) if (avg_spend is not None and budget) else None,
                "days": len(per_day), "baselineOnly": not per_day}
    if delivery["utilization"] is None:
        verdict = "One snapshot so far: this is the baseline. Daily numbers start with the next reading."
    elif delivery["utilization"] < UNDER_BUDGET:
        verdict = ("Auction/volume limited: spend is under half the budget, so raising the budget will not add spend. "
                   "Raise bids on keywords that get no impressions, or add higher-volume terms.")
    elif delivery["utilization"] >= NEAR_BUDGET:
        verdict = "Budget limited: nearly all of the daily budget is spent. Cut weak keywords or raise the budget."
    else:
        verdict = "Spending most of the budget; keep watching cost per install."
    delivery["verdict"] = verdict

    # 2. keywords
    rows = []
    for kw, row in cur.items():
        if row["status"] != "Running":
            continue
        base_idx, base = since_bid(dates, snaps, kw)
        days_at_bid = (dt.date.fromisoformat(last) - dt.date.fromisoformat(dates[base_idx])).days
        if days_at_bid == 0:
            days_at_bid = None  # single reading: baseline only
        run = {f: row[f] - base[f] for f in ("spend", "impressions", "taps", "installs")}
        d = daily_delta(row, prev_snap.get(kw) if prev_snap else None) if prev_snap else None
        bid = row["bid"]
        action, why, new_bid = "hold", "too early to judge", None
        cpi = run["spend"] / run["installs"] if run["installs"] else None
        if run["installs"] > 0 and cpi is not None and cpi <= TARGET_CPI:
            action, new_bid = "scale", min(MAX_BID, round(bid * 1.2, 2))
            why = f"{run['installs']} install(s) at {money(cpi)} each, under the {money(TARGET_CPI)} target"
        elif run["installs"] > 0:
            action, new_bid = "trim", max(MIN_BID, round(bid * 0.8, 2))
            why = f"{money(cpi)} per install is over the {money(TARGET_CPI)} target"
        elif run["taps"] >= TAPS_PAUSE:
            action, why = "pause", f"{run['taps']} taps and no install ({money(run['spend'])} spent)"
        elif run["taps"] >= TAPS_NO_INSTALL:
            action, new_bid = "trim", max(MIN_BID, round(bid * 0.75, 2))
            why = f"{run['taps']} taps, no installs"
        elif run["impressions"] >= NOIMP_HIGH and run["taps"] == 0:
            action, why = "pause", f"{run['impressions']} impressions and no taps: not relevant to searchers"
        elif days_at_bid is not None and days_at_bid >= DEAD_DAYS and run["impressions"] == 0:
            if bid < MAX_BID:
                action, new_bid = "raise", min(MAX_BID, round(bid * BUMP, 2))
                why = f"no impressions in {days_at_bid} days at {money(bid)}: not winning auctions or no volume"
            else:
                action, why = "pause", f"no impressions in {days_at_bid} days even at {money(bid)}: no volume"
        elif days_at_bid is not None and days_at_bid < DEAD_DAYS and run["impressions"] == 0:
            why = f"no impressions yet ({days_at_bid} day(s) at {money(bid)}); judge after {DEAD_DAYS}"
        rows.append({"keyword": kw, "bid": bid, "action": action, "newBid": new_bid, "why": why,
                     "daysAtBid": days_at_bid, "run": {k: round(v, 2) if k == "spend" else v for k, v in run.items()},
                     "yesterday": d, "sample": f"{run['impressions']} impr, {run['taps']} taps, {run['installs']} installs"})
    order = {"scale": 0, "raise": 1, "trim": 2, "pause": 3, "hold": 4}
    rows.sort(key=lambda r: (order[r["action"]], -r["run"]["impressions"]))
    totals = {f: sum(r[f] for r in cur.values()) for f in ("spend", "impressions", "taps", "installs")}
    return {"asOf": last, "snapshots": len(dates), "delivery": delivery, "totals": totals, "keywords": rows,
            "window": snaps[last].get("window")}


LOW_SHARE = 0.10       # impression share under this on a term with real volume: we rarely win it
TERM_MIN_TAPS = 5


def analyze_terms(snaps: dict, today: dt.date | None = None) -> dict:
    """Search-term impression share (Apple's report) against the keyword list. Advisory."""
    if not SHARE.exists():
        return {"terms": [], "note": "no impression-share reading yet"}
    rows = list(json.loads(SHARE.read_text()).get("rows", {}).values())
    kws = set()
    if snaps:
        for k in by_kw(snaps[sorted(snaps)[-1]]):
            kws.add(k.strip("[]").lower())
    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["term"], {"term": r["term"], "popularity": r["popularity"], "days": 0, "spend": 0.0,
                                       "impressions": 0, "taps": 0, "installs": 0, "share": [], "rank": []})
        a["days"] += 1
        for f in ("spend", "impressions", "taps", "installs"):
            a[f] += r[f]
        a["share"].append(r["share"])
        a["rank"].append(r["rank"])
    out = []
    for a in agg.values():
        share = max(a["share"]) / 100 if a["share"] else 0.0
        cpi = a["spend"] / a["installs"] if a["installs"] else None
        covered = a["term"].lower() in kws
        action, why = "watch", "little activity"
        if a["installs"] > 0 and cpi is not None and cpi <= TARGET_CPI and not covered:
            action = "add"
            why = (f"{a['installs']} install(s) at {money(cpi)} each from this search term, and it is not a keyword: "
                   f"add [{a['term']}] as an exact keyword")
        elif a["taps"] >= TERM_MIN_TAPS and a["installs"] == 0:
            action, why = "negative", f"{a['taps']} taps and no installs: add as a negative"
        elif share < LOW_SHARE and a["popularity"] >= 3 and a["impressions"] >= 10 and (covered or a["taps"] >= 1):
            action = "bid-up" if covered else "add"
            why = (f"peak impression share {share*100:.0f}% on a popularity-{a['popularity']} term: "
                   + ("raise its bid" if covered else f"add [{a['term']}] as an exact keyword"))
        elif share < LOW_SHARE and a["impressions"] >= 10:
            why = (f"low impression share ({share*100:.0f}%) but no taps yet: relevance unproven, so it is not worth a bid")
        out.append({**a, "share": round(share, 3), "cpi": round(cpi, 2) if cpi else None, "covered": covered,
                    "action": action, "why": why,
                    "sample": f"{a['impressions']} impr, {a['taps']} taps, {a['installs']} installs over {a['days']} day(s)"})
    order = {"add": 0, "bid-up": 1, "negative": 2, "watch": 3}
    out.sort(key=lambda t: (order[t["action"]], -t["installs"], -t["impressions"]))
    return {"terms": out, "note": None}


def render(res: dict) -> str:
    if res.get("error"):
        return f"Ads optimizer: {res['error']}"
    d, t = res["delivery"], res["totals"]
    out = [f"Ads optimizer (Apple Search Ads, {res['asOf']}, {res['snapshots']} snapshot(s), window {res['window']}):"]
    if d["budget"]:
        y = "n/a" if d["yesterday"] is None else money(d["yesterday"])
        a = "n/a" if d["avg5"] is None else money(d["avg5"])
        u = "" if d["utilization"] is None else f" ({d['utilization']*100:.0f}% of budget)"
        out.append(f"  Delivery: budget {money(d['budget'])}/day, last day {y}, 5-day average {a}{u}.")
    out.append(f"  {d['verdict']}")
    out.append(f"  Totals in window: {money(t['spend'])}, {t['impressions']} impressions, {t['taps']} taps, {t['installs']} installs"
               + (f" ({money(t['spend']/t['installs'])} per install)." if t["installs"] else "."))
    terms = res.get("searchTerms") or {}
    if terms.get("terms"):
        out.append("  Search-term impression share (Apple report; advisory):")
        for t in terms["terms"][:8]:
            out.append(f"   {t['action'].upper():<8} {t['term']:<24} share {t['share']*100:.0f}% pop {t['popularity']}  {t['why']} [{t['sample']}]")
    acts = [r for r in res["keywords"] if r["action"] != "hold"]
    holds = [r for r in res["keywords"] if r["action"] == "hold"]
    if acts:
        out.append("  Actions (advisory; changing bids or pausing needs Ben's yes):")
        for r in acts:
            nb = f" -> {money(r['newBid'])}" if r["newBid"] else ""
            out.append(f"   {r['action'].upper():<6} {r['keyword']:<32} {money(r['bid'])}{nb}  {r['why']} [{r['sample']}]")
    if holds:
        sample = ", ".join(r["keyword"] for r in holds[:6]) + (f" and {len(holds) - 6} more" if len(holds) > 6 else "")
        out.append(f"  Holding ({len(holds)}, too early or steady): {sample}.")
    return "\n".join(out)


def main() -> int:
    snaps = load()
    res = analyze(snaps)
    res["searchTerms"] = analyze_terms(snaps)
    if "--json" in sys.argv[1:]:
        print(json.dumps(res, indent=1))
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
