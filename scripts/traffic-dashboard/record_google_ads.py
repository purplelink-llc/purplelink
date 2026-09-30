#!/usr/bin/env python3
"""Record ModernTex Google Ads figures read from ads.google.com.

Google Ads does have a reporting API, but it needs a developer-token
application (real approval time, not just an OAuth consent flow), so this
reads the campaign page in Ben's signed-in Chrome instead, the same way
Apple Search Ads is read for GlobePin -- see record_asa.py.

Input on stdin, as the page extraction produces it:
    {"metrics": {"Cost": "$10.13", "Impr.": "1,259", "Clicks": "39",
                 "Avg. CPC": "$0.26"}, "window": "Last 7 days"}

    python3 record_google_ads.py < read.json   # writes manual-ads.json, prints a summary
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

PATH = Path.home() / ".purplelink" / "traffic" / "manual-ads.json"
CAMPAIGN = "ModernTex - Search Results - US"


def num(v: str) -> float:
    return float(str(v).replace("$", "").replace(",", "").replace("%", "").strip() or 0)


def main() -> int:
    read = json.load(sys.stdin)
    m: dict[str, str] = read.get("metrics", {})
    missing = [k for k in ("Cost", "Impr.", "Clicks") if k not in m]
    if missing:
        print(f"record_google_ads: page read is missing {missing}; nothing written", file=sys.stderr)
        return 1

    data = {}
    if PATH.exists():
        try:
            data = json.loads(PATH.read_text())
        except json.JSONDecodeError:
            data = {}
    prev = data.get("googleAdsModerntex") or {}

    spend, impressions, clicks = num(m["Cost"]), int(num(m["Impr."])), int(num(m["Clicks"]))
    avg_cpc = num(m.get("Avg. CPC", "0"))
    window = read.get("window", "Last 7 days")

    if window.strip().lower() in ("all time", "lifetime"):
        # Lifetime reading: stored beside the 7-day reading, never in place of it.
        prev["allTime"] = {"asOf": dt.date.today().isoformat(), "spend": spend,
                           "impressions": impressions, "clicks": clicks, "avgCPC": avg_cpc}
        data["googleAdsModerntex"] = prev
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(data, indent=2) + "\n")
        print(f"All time: {impressions:,} impressions, {clicks} clicks for ${spend:.2f}.")
        return 0

    if impressions == 0:
        note = f"No delivery in the {window.lower()} window."
    else:
        note = f"{window}: {impressions:,} impressions, {clicks} clicks for ${spend:.2f}."
    today = dt.date.today().isoformat()
    # Compare with the last reading from an earlier day only: a same-day re-read is not news.
    if (prev.get("asOf") and prev["asOf"] != today and prev.get("spend") is not None
            and prev.get("window") == window):
        d = spend - prev["spend"]
        trend = "up" if d > 0.01 else "down" if d < -0.01 else "unchanged"
        note += f" Spend {trend} from ${prev['spend']:.2f} in the reading of {prev['asOf']}."

    data["googleAdsModerntex"] = {
        "asOf": today, "window": window, "campaign": CAMPAIGN,
        "spend": spend, "impressions": impressions, "clicks": clicks,
        "avgCPC": avg_cpc, "note": note,
    }
    if prev.get("allTime"):
        data["googleAdsModerntex"]["allTime"] = prev["allTime"]
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
