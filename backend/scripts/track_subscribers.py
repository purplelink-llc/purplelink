#!/usr/bin/env python3
"""Record the digest's current subscriber count to a tracked growth log.

Usage:
  python3 backend/scripts/track_subscribers.py

Fetches SUBSCRIBE_SECRET from the Netlify CLI (must be logged in and linked
to the site), queries the live subscribers-list endpoint, and appends a row
to analytics/subscriber-growth.csv. Skips silently if a row for today's date
already exists (idempotent — safe to run more than once a day).
"""
from __future__ import annotations

import csv
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "analytics" / "subscriber-growth.csv"
SITE_URL = "https://purplelink.llc/.netlify/functions/subscribers-list"


def get_subscribe_secret() -> str:
    result = subprocess.run(
        ["netlify", "env:get", "SUBSCRIBE_SECRET"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    secret = result.stdout.strip()
    if result.returncode != 0 or not secret:
        print(f"ERROR: could not fetch SUBSCRIBE_SECRET via netlify CLI: {result.stderr.strip()}")
        sys.exit(1)
    return secret


def fetch_subscriber_count(secret: str) -> int:
    result = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: Bearer {secret}", SITE_URL],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"ERROR: unexpected response: {result.stdout}")
        sys.exit(1)
    if "count" not in data:
        print(f"ERROR: {data}")
        sys.exit(1)
    return data["count"]


def append_row(date_str: str, count: int) -> bool:
    """Returns False if a row for this date already exists (no-op)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        with open(LOG_PATH, newline="") as f:
            existing_dates = {row["date"] for row in csv.DictReader(f)}
        if date_str in existing_dates:
            return False

    is_new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date", "subscriber_count"])
        writer.writerow([date_str, count])
    return True


def main() -> None:
    secret = get_subscribe_secret()
    count = fetch_subscriber_count(secret)
    today = datetime.date.today().isoformat()

    if append_row(today, count):
        print(f"Recorded: {today} -> {count} subscribers ({LOG_PATH.relative_to(ROOT)})")
    else:
        print(f"Already recorded for {today} — skipping.")


if __name__ == "__main__":
    main()
