#!/usr/bin/env python3
"""Record Apple Ads "Daily Search Term Impression Share" report rows for ads_optimizer.py.

The report is saved in Ben's Apple Ads account (Insights > View reports > "Daily search term
impression share", last 30 days, all ad positions). The daily update opens it in Ben's Chrome, and
pipes the page text in:

    {"text": "<get_page_text output of the report page>"}

Each row is 17 lines: Day, App Name, App ID, Country, Search Term, Search Popularity (1-5),
Impression Share, Rank, Spend, Impressions, Taps, Installs, TTR, Avg CPT, CR, Avg CPA, Campaign Group ID.
Apple lists only terms where it can compute a share, so most days show few rows; that is normal.
Rows are keyed by (day, term) in ~/.purplelink/traffic/asa-impression-share.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
PATH = TRAFFIC / "asa-impression-share.json"
DAY = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")
ROW_LEN = 17


def num(v: str) -> float:
    s = str(v).replace("$", "").replace(",", "").replace("%", "").strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else 0.0


def parse(text: str) -> list[dict]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    rows = []
    for i, l in enumerate(lines):
        if not DAY.match(l) or i + ROW_LEN > len(lines):
            continue
        f = lines[i:i + ROW_LEN]
        day = dt.datetime.strptime(f[0], "%b %d, %Y").date().isoformat()
        rank = f[7]
        rows.append({"day": day, "term": f[4], "popularity": int(num(f[5])), "share": num(f[6]),
                     "rank": rank, "spend": num(f[8]), "impressions": int(num(f[9])),
                     "taps": int(num(f[10])), "installs": int(num(f[11]))})
    return rows


def main() -> int:
    read = json.load(sys.stdin)
    text = read.get("text", "")
    if "Impression Share" not in text:
        print("record_asa_impression_share: this is not the impression-share report; nothing written", file=sys.stderr)
        return 1
    rows = parse(text)
    empty = "No results" in text or "Showing 0 rows" in text
    if not rows and not empty:
        print("record_asa_impression_share: report did not render rows; nothing written", file=sys.stderr)
        return 1
    data = {"rows": {}}
    if PATH.exists():
        try:
            data = json.loads(PATH.read_text())
        except json.JSONDecodeError:
            pass
    for r in rows:
        data.setdefault("rows", {})[f"{r['day']}|{r['term']}"] = r
    data["asOf"] = dt.date.today().isoformat()
    TRAFFIC.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n")
    tmp.replace(PATH)
    print(f"{len(rows)} search-term row(s) read; {len(data['rows'])} on file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
