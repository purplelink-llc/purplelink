#!/usr/bin/env python3
"""Download a snapshot of Open Trivia DB (https://opentdb.com, CC BY-SA 4.0) into
scripts/games-data/otdb.json. Run by hand when the pool needs refreshing; the snapshot is
committed so builds never depend on the network and the daily picks stay stable.

The API allows one request per 5 seconds per IP and hands out each question once per
session token, so this walks the categories we use until each one runs dry.

  python3 scripts/fetch_trivia.py
"""
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

OUT = Path(__file__).resolve().parent / "games-data" / "otdb.json"
CATEGORIES = [9, 10, 11, 12, 14, 15, 17, 18, 19, 20, 21, 22, 23, 25, 27]
BASE = "https://opentdb.com"


def get(url):
    # curl, not urllib: this Mac's python.org build has no CA bundle.
    time.sleep(5.2)
    r = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True, text=True)
    return json.loads(r.stdout)


def main():
    token = get(f"{BASE}/api_token.php?command=request")["token"]
    out, seen = [], set()
    for cat in CATEGORIES:
        while True:
            q = urllib.parse.urlencode({"amount": 50, "category": cat, "type": "multiple", "token": token, "encode": "url3986"})
            d = get(f"{BASE}/api.php?{q}")
            code = d.get("response_code")
            if code == 5:
                time.sleep(6)
                continue
            if code != 0:
                break
            for it in d["results"]:
                item = {k: urllib.parse.unquote(v) if isinstance(v, str) else [urllib.parse.unquote(x) for x in v]
                        for k, v in it.items()}
                key = item["question"]
                if key in seen:
                    continue
                seen.add(key)
                out.append({"c": item["category"], "d": item["difficulty"], "q": item["question"],
                            "a": item["correct_answer"], "w": item["incorrect_answers"]})
            print(f"category {cat}: {len(out)} questions so far", flush=True)
            if len(d["results"]) < 50:
                break
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("wrote", OUT, len(out))


if __name__ == "__main__":
    sys.exit(main())
