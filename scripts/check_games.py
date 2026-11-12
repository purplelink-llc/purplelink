#!/usr/bin/env python3
"""Health check for /games/ data: how many days of content are left ahead of today?

  python3 scripts/check_games.py            # report; always exit 0 (used by the Netlify build)
  python3 scripts/check_games.py --strict   # exit 1 if anything is short (used by the content routine)

A short buffer must never block a deploy of unrelated pages, so the build only reports.
Word games are generated a long way ahead (730 days); the crossword buffer is the one that
runs out, because its clues are written by a routine. Games retired in the 2026-11-12 freeze
(trivia, photo, daily chess, Sudoku, horoscope, the attribute games except Peaklink) are not checked.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "site" / "games" / "data"
LONG_MIN = 60      # days ahead for generated games
CW_MIN = 4         # days of clued crosswords ahead


def day_index(epoch: str, today: date) -> int:
    y, m, d = map(int, epoch.split("-"))
    return (today - date(y, m, d)).days


def main() -> int:
    strict = "--strict" in sys.argv
    today = date.today()
    problems: list[str] = []
    notes: list[str] = []

    for name, key in (("linkle.json", "answers"), ("quadlink.json", "days")):
        p = DATA / name
        if not p.exists():
            problems.append(f"{name}: missing")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        left = len(d[key]) - day_index(d["epoch"], today)
        notes.append(f"{name}: {left} days ahead")
        if left < LONG_MIN:
            problems.append(f"{name}: only {left} days of puzzles ahead (need {LONG_MIN})")
        if name == "quadlink.json":
            for i, day in enumerate(d[key]):
                if len(set(day)) != 4:
                    problems.append(f"{name}: day {i} repeats a word")
                    break

    # unlimited rated chess pool (Chess Puzzles)
    pool = DATA / "chess-pool"
    if not (pool / "1000.json").exists():
        problems.append("chess-pool: missing")
    else:
        n = sum(len(json.loads(f.read_text(encoding="utf-8"))["p"]) for f in pool.glob("*.json"))
        notes.append(f"chess-pool: {n} puzzles")
        if n < 3000:
            problems.append(f"chess-pool: only {n} puzzles")

    for gid in ("peaklink",):
        f = DATA / f"{gid}.json"
        if not f.exists():
            problems.append(f"{gid}.json: missing")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        n = len(d["rows"])
        bad = [r["n"] for r in d["rows"] if len(r["v"]) != len(d["cols"])]
        notes.append(f"{gid}.json: {n} rows")
        if bad:
            problems.append(f"{gid}.json: rows with the wrong number of values: {bad[:3]}")


    # Lockerlink: every sport in the rotation has a data file, enough days of puzzles, and a connected teammate graph
    sx = DATA / "sports-index.json"
    if not sx.exists():
        problems.append("sports-index.json: missing (run scripts/gen_sports.py)")
    else:
        for sport in json.loads(sx.read_text(encoding="utf-8"))["rotation"]:
            f = DATA / f"sports-{sport}.json"
            if not f.exists():
                problems.append(f"sports-{sport}.json: missing")
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            names = {p[0] for p in d["p"]}
            bad = [n for pr in d["tl"] for n in pr if n not in names]
            notes.append(f"sports-{sport}.json: {len(d['p'])} players, {len(d['tl'])} link days, {len(d['gr'])} grids")
            if bad:
                problems.append(f"sports-{sport}.json: link puzzles name players not in the pool: {sorted(set(bad))[:3]}")
            if len(d["tl"]) < 200:
                problems.append(f"sports-{sport}.json: fewer than 200 days of puzzles")

    # crossword: days with a published puzzle ahead (grid and valid clues), and grids still waiting for clues
    cp = DATA / "crossword.json"
    if cp.exists():
        cw = json.loads(cp.read_text(encoding="utf-8"))["days"]
        ahead = [k for k in cw if date.fromisoformat(k) >= today]
        last = max((date.fromisoformat(k) for k in cw), default=None)
        left = (last - today).days if last else -1
        notes.append(f"crossword.json: puzzles through {last} ({left} days ahead)")
        if left < CW_MIN:
            problems.append(f"crossword.json: only {left} days of crosswords ahead (need {CW_MIN}); the clue routine may have stalled")
        gdir = Path(__file__).resolve().parent / "games-data" / "crossword"
        waiting = sorted(g.name.split(".")[0] for g in gdir.glob("*.grid.json")
                         if g.name.split(".")[0] not in cw and date.fromisoformat(g.name.split(".")[0]) >= today)
        if waiting:
            notes.append(f"crossword grids without usable clues: {', '.join(waiting[:5])}{' ...' if len(waiting) > 5 else ''}")
    else:
        problems.append("crossword.json: missing")

    for n in notes:
        print("games:", n)
    for p in problems:
        print("games PROBLEM:", p)
    return 1 if (strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
