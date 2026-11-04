#!/usr/bin/env python3
"""Draw the Buddy chat holdout schedule (docs/designs/buddy-chat.md, "Conversion pass", section 3).

A paired-day switchback: days 1+2, 3+4, ... are pairs, and one seeded fair coin per pair picks the B day (the day the
chat launcher shows); random.Random(seed), and rng.random() < 0.5 puts B on the first day of the pair. Seeds count up
from FIRST_SEED and the first draw in which every UTC weekday has 3 to 5 B days out of 8 is used. Both other
switchbacks (exp-trial-link.js, exp-moderntex-hero.js) end before START, so no cross-test balance rule is needed.

  python3 scripts/draw_buddy_schedule.py           # print seed, schedule and the weekday counts
  python3 scripts/draw_buddy_schedule.py --check   # exit 1 unless site/buddy-chat/loader.js holds this draw
"""
from __future__ import annotations

import datetime as dt
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOADER = ROOT / "site" / "buddy-chat" / "loader.js"
START = dt.date(2026, 12, 28)
DAYS = 56
FIRST_SEED = 20261228


def schedule_for(seed: int) -> str:
    rng = random.Random(seed)
    return "".join("BA" if rng.random() < 0.5 else "AB" for _ in range(DAYS // 2))


def weekday_b(schedule: str) -> list[int]:
    counts = [0] * 7
    for i, arm in enumerate(schedule):
        if arm == "B":
            counts[(START + dt.timedelta(days=i)).weekday()] += 1
    return counts


def draw() -> tuple[int, str, list[int]]:
    for seed in range(FIRST_SEED, FIRST_SEED + 10_000):
        s = schedule_for(seed)
        counts = weekday_b(s)
        if all(3 <= c <= 5 for c in counts):
            return seed, s, counts
    raise SystemExit("no seed in 10,000 met the weekday rule")


def main() -> int:
    seed, s, counts = draw()
    if "--check" in sys.argv:
        src = LOADER.read_text(encoding="utf-8")
        got = re.search(r'var SCHEDULE = "([AB]*)"', src)
        start = re.search(r'var START = "(\d{4}-\d{2}-\d{2})"', src)
        ok = got and start and got.group(1) == s and start.group(1) == START.isoformat()
        if not ok:
            print("loader.js does not hold the drawn schedule; run python3 scripts/draw_buddy_schedule.py")
            return 1
        return 0
    print("seed", seed)
    print("schedule", s)
    print("B days per weekday (Mon..Sun)", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
