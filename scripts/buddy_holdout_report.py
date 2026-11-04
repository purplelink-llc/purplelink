#!/usr/bin/env python3
"""Read out the Buddy chat holdout (docs/designs/buddy-chat.md, "Conversion pass", section 3).

The unit is the UTC day. For each of the 28 pairs it takes the conversion rate on the ten Mac-app pages
(appConversions / appPageviews, from the dashboard's daily archive) on the B day (chat shown) minus the A day (no
chat), then reports the mean paired difference with an sign-flip randomization test over the pairs.
Decision rule, written before the start: keep Buddy unless the B days convert worse than the A days.

  python3 scripts/buddy_holdout_report.py            # reads ~/.purplelink/traffic/history.json
  PURPLELINK_TRAFFIC_DIR=/path python3 scripts/buddy_holdout_report.py --json
"""
from __future__ import annotations

import datetime as dt
import itertools
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOADER = ROOT / "site" / "buddy-chat" / "loader.js"
TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")


def schedule() -> tuple[dt.date, str]:
    src = LOADER.read_text(encoding="utf-8")
    start = re.search(r'var START = "(\d{4}-\d{2}-\d{2})"', src).group(1)
    return dt.date.fromisoformat(start), re.search(r'var SCHEDULE = "([AB]+)"', src).group(1)


def pairs(by_day: dict, start: dt.date, sched: str) -> list[dict]:
    out = []
    for i in range(0, len(sched) - 1, 2):
        row = {}
        for j in (i, i + 1):
            day = (start + dt.timedelta(days=j)).isoformat()
            m = by_day.get(day) or {}
            views, conv = m.get("appPageviews"), m.get("appConversions")
            row[sched[j]] = {"day": day, "views": views, "conversions": conv,
                             "rate": conv / views if views else None}
        if row["A"]["rate"] is not None and row["B"]["rate"] is not None:
            row["diff"] = row["B"]["rate"] - row["A"]["rate"]
            out.append(row)
    return out


def sign_flip_p(diffs: list[float]) -> float:
    """Two-sided randomization p-value for the mean paired difference: every sign flip up to 20 pairs, a fixed-seed
    sample of 200,000 flips above that (2^28 is too many to list)."""
    if not diffs:
        return 1.0
    observed = abs(sum(diffs))
    if len(diffs) > 20:
        import random
        rng = random.Random(20261228)
        hits = sum(abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12 for _ in range(200_000))
        return hits / 200_000
    hits = sum(abs(sum(d * s for d, s in zip(diffs, signs))) >= observed - 1e-12
               for signs in itertools.product((1, -1), repeat=len(diffs)))
    return hits / 2 ** len(diffs)


def report(history: dict) -> dict:
    start, sched = schedule()
    by_day = (((history.get("sites") or {}).get("purplelink") or {}).get("byDay")) or {}
    rows = pairs(by_day, start, sched)
    diffs = [r["diff"] for r in rows]
    mean = sum(diffs) / len(diffs) if diffs else None
    p = sign_flip_p(diffs)
    if not rows:
        verdict = "no data yet"
    elif len(rows) < len(sched) // 2:
        verdict = f"running: {len(rows)} of {len(sched) // 2} pairs complete"
    elif mean < 0 and p < 0.05:
        verdict = "remove or rethink: B days (chat shown) converted worse"
    else:
        verdict = "keep Buddy: no sign that showing the chat converts worse"
    return {"pairs_complete": len(rows), "pairs_total": len(sched) // 2, "mean_diff_b_minus_a": mean,
            "p_two_sided": p, "verdict": verdict, "pairs": rows}


def main() -> int:
    history = json.loads((TRAFFIC / "history.json").read_text(encoding="utf-8"))
    out = report(history)
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
        return 0
    print(f"Buddy chat holdout: {out['pairs_complete']} of {out['pairs_total']} pairs")
    if out["mean_diff_b_minus_a"] is not None:
        print(f"mean conversion rate, B minus A: {out['mean_diff_b_minus_a']:+.4f} (p = {out['p_two_sided']:.3f})")
    print(out["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
