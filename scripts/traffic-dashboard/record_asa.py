#!/usr/bin/env python3
"""Record Apple Search Ads figures read from the app-ads.apple.com campaign page.

Apple Search Ads has no API integration here (Apple ID sign-in, 2FA), so the daily
update reads the campaign report in Ben's signed-in Chrome and pipes what it read
into this script, which writes ~/.purplelink/traffic/manual-ads.json for the
dashboard's Apple Search Ads card.

Input on stdin, as the page extraction produces it:
    {"metrics": [{"metric": "spend", "value": "$5.95"}, ...],
     "window": "Last 7 days", "dailyBudget": 5.0, "status": "Running"}
Every metric cell on the report is a link carrying ?metric=<name>, so values are
matched by name, never by column position. When a metric appears more than once
(ad-group rows plus TOTALS), the last occurrence (the TOTALS row) wins.

    python3 record_asa.py < read.json      # writes manual-ads.json, prints a summary
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

PATH = Path.home() / ".purplelink" / "traffic" / "manual-ads.json"
CAMPAIGN = "GlobePin - Search Results - US"


def num(v: str) -> float:
    return float(str(v).replace("$", "").replace(",", "").replace("%", "").strip() or 0)


def main() -> int:
    read = json.load(sys.stdin)
    m: dict[str, str] = {}
    for item in read.get("metrics", []):
        m[item["metric"]] = item["value"]
    missing = [k for k in ("spend", "impressions", "taps", "totalInstalls") if k not in m]
    if missing:
        print(f"record_asa: page read is missing {missing}; nothing written", file=sys.stderr)
        return 1

    prev = {}
    if PATH.exists():
        try:
            prev = (json.loads(PATH.read_text()).get("appleSearchAds") or {})
        except json.JSONDecodeError:
            prev = {}
    prev_c = (prev.get("campaigns") or [{}])[0]

    spend, installs = num(m["spend"]), int(num(m["totalInstalls"]))
    impressions, taps = int(num(m["impressions"])), int(num(m["taps"]))
    c = {
        "key": CAMPAIGN,
        "status": read.get("status") or prev_c.get("status", "Running"),
        "dailyBudget": read.get("dailyBudget") or prev_c.get("dailyBudget"),
        "maxCPT": read.get("maxCPT") or prev_c.get("maxCPT"),
        "spend": spend,
        "impressions": impressions,
        "taps": taps,
        "installs": installs,
        "avgCPT": num(m.get("avg_cpt", "0")),
        "avgCPA": num(m.get("totalAvgCPI", "0")),
        "ttr": m.get("ttr", ""),
        "conversionRate": m.get("totalInstallRate", ""),
    }

    window = read.get("window", "Last 7 days")
    if impressions == 0:
        note = f"No delivery in the {window.lower()} window."
    else:
        per = f", ${spend / installs:.2f} per install" if installs else ", no installs yet"
        note = (f"{window}: {impressions:,} impressions, {taps} taps and {installs} installs "
                f"for ${spend:.2f}{per}.")
    today = dt.date.today().isoformat()
    # Compare with the last reading from an earlier day only: a same-day re-read is not news.
    if (prev.get("asOf") and prev["asOf"] != today and prev_c.get("installs") is not None
            and prev.get("window") == window):
        d = installs - int(prev_c["installs"])
        trend = "up" if d > 0 else "down" if d < 0 else "unchanged"
        note += f" Installs {trend} from {prev_c['installs']} in the reading of {prev['asOf']}."

    out = {"appleSearchAds": {"asOf": today, "window": window,
                              "campaigns": [c], "note": note}}
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
