#!/usr/bin/env python3
"""Record one day's keyword-level Apple Search Ads reading for ads_optimizer.py.

The daily update extracts the ad group's Keywords grid from Ben's signed-in Chrome
(see the daily-update skill, step 2e) and pipes it in here:

    {"window": "Last 30 days", "date": "2026-09-30",      # date optional, default today
     "adGroup": "GlobePin - Broad Travel Terms",           # optional
     "dailyBudget": 10.0,                                  # optional
     "rows": "keyword|Running|$0.75|$0.72|$0.00|$0.72|132|1|0\\n..."}

Row fields, pipe separated: keyword, status, max CPT bid, spend, avg CPA, avg CPT,
impressions, taps, installs. ("keywords": [{...}] with the same names also works.)

Snapshots are kept per date in ~/.purplelink/traffic/asa-keywords.json (last 120 days).
Use a window that only grows for a campaign this young ("Last 30 days"): day-over-day
differences of cumulative figures are then exact daily numbers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
PATH = TRAFFIC / "asa-keywords.json"
FIELDS = ("keyword", "status", "bid", "spend", "cpa", "cpt", "impressions", "taps", "installs")


def num(v) -> float:
    s = str(v if v is not None else "0").replace("$", "").replace(",", "").replace("%", "").strip()
    return float(s) if s else 0.0


def parse_rows(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9 or not parts[0]:
            continue
        out.append(dict(zip(FIELDS, parts[:9])))
    return out


def normalize(k: dict) -> dict:
    return {"keyword": str(k["keyword"]).strip(), "status": str(k.get("status", "")).strip(),
            "bid": num(k.get("bid")), "spend": num(k.get("spend")), "impressions": int(num(k.get("impressions"))),
            "taps": int(num(k.get("taps"))), "installs": int(num(k.get("installs")))}


def main() -> int:
    read = json.load(sys.stdin)
    rows = read.get("keywords") or parse_rows(read.get("rows", ""))
    kws = [normalize(k) for k in rows if k.get("keyword")]
    if not kws:
        print("record_asa_keywords: no keyword rows in the reading; nothing written", file=sys.stderr)
        return 1
    if not any(k["status"] for k in kws):
        print("record_asa_keywords: rows have no status; the grid probably did not render", file=sys.stderr)
        return 1
    data = {"snapshots": {}}
    if PATH.exists():
        try:
            data = json.loads(PATH.read_text())
        except json.JSONDecodeError:
            pass
    date = read.get("date") or dt.date.today().isoformat()
    snap = {"window": read.get("window", "Last 30 days"), "keywords": kws}
    for key in ("adGroup", "dailyBudget"):
        if read.get(key) is not None:
            snap[key] = read[key]
    data.setdefault("snapshots", {})[date] = snap
    keep = sorted(data["snapshots"])[-120:]
    data["snapshots"] = {d: data["snapshots"][d] for d in keep}
    TRAFFIC.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n")
    tmp.replace(PATH)
    spend = sum(k["spend"] for k in kws)
    print(f"{date}: {len(kws)} keywords, ${spend:.2f} spend, {sum(k['impressions'] for k in kws)} impressions, "
          f"{sum(k['taps'] for k in kws)} taps, {sum(k['installs'] for k in kws)} installs ({snap['window']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
