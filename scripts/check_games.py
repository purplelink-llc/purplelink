#!/usr/bin/env python3
"""Health check for /games/ data: how many days of content are left ahead of today?

  python3 scripts/check_games.py            # report; always exit 0 (used by the Netlify build)
  python3 scripts/check_games.py --strict   # exit 1 if anything is short (used by the content routine)

A short buffer must never block a deploy of unrelated pages, so the build only reports.
Word games and trivia are generated a long way ahead (730 days); the horoscope buffer is
the one that runs out, because it is written by the weekly routine.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "site" / "games" / "data"
LONG_MIN = 60      # days ahead for generated games
STARS_MIN = 5      # days ahead for the horoscope buffer
STARS_FAIL = 0     # strict mode fails at or below this
SUDOKU_MIN = 21    # days of Sudoku ahead (generation takes minutes, so the buffer is shorter)
CW_MIN = 4         # days of clued crosswords ahead


def day_index(epoch: str, today: date) -> int:
    y, m, d = map(int, epoch.split("-"))
    return (today - date(y, m, d)).days


def main() -> int:
    strict = "--strict" in sys.argv
    today = date.today()
    problems: list[str] = []
    notes: list[str] = []

    for name, key in (("linkle.json", "answers"), ("quadlink.json", "days"), ("trivia.json", "days"), ("photo.json", "days"), ("chess.json", "days"), ("sudoku.json", "days")):
        p = DATA / name
        if not p.exists():
            problems.append(f"{name}: missing")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        left = len(d[key]) - day_index(d["epoch"], today)
        notes.append(f"{name}: {left} days ahead")
        if name == "photo.json":
            continue   # wraps around after 150 days by design
        if name == "sudoku.json":
            if left < SUDOKU_MIN:
                problems.append(f"sudoku.json: only {left} days of puzzles ahead (need {SUDOKU_MIN}); run scripts/gen_sudoku.py --days N")
            continue
        if name == "chess.json":
            for i, day in enumerate(d[key]):
                if not day.get("f") or not day.get("m"):
                    problems.append(f"chess.json: day {i} is malformed")
                    break
        if left < LONG_MIN:
            problems.append(f"{name}: only {left} days of puzzles ahead (need {LONG_MIN})")
        if name == "quadlink.json":
            for i, day in enumerate(d[key]):
                if len(set(day)) != 4:
                    problems.append(f"{name}: day {i} repeats a word")
                    break
        if name == "trivia.json":
            for i, day in enumerate(d[key]):
                if len(day) != 5 or any(len(q[2]) != 4 for q in day):
                    problems.append(f"{name}: day {i} is malformed")
                    break

    # unlimited rated pools: every chess bucket from 500 up to the top that has puzzles, and some Sudoku at every level
    pool = DATA / "chess-pool"
    if not (pool / "1000.json").exists():
        problems.append("chess-pool: missing")
    else:
        n = sum(len(json.loads(f.read_text(encoding="utf-8"))["p"]) for f in pool.glob("*.json"))
        notes.append(f"chess-pool: {n} puzzles")
        if n < 3000:
            problems.append(f"chess-pool: only {n} puzzles")
    for lv in range(1, 6):
        f = DATA / "sudoku-pool" / f"level-{lv}.json"
        have = len(json.loads(f.read_text(encoding="utf-8"))["p"]) if f.exists() else 0
        if have < 40:
            problems.append(f"sudoku-pool level {lv}: only {have} puzzles (run scripts/gen_sudoku_pool.py)")
    notes.append("sudoku-pool: ok")

    sp = DATA / "stars.json"
    if not sp.exists():
        problems.append("stars.json: missing")
    else:
        stars = json.loads(sp.read_text(encoding="utf-8"))["days"]
        last = max(date.fromisoformat(k) for k in stars)
        left = (last - today).days
        notes.append(f"stars.json: readings through {last} ({left} days ahead)")
        if left < STARS_MIN:
            problems.append(f"stars.json: only {left} days of horoscopes ahead (need {STARS_MIN}); the weekly routine may have stalled")
        if left < STARS_FAIL + 1 and strict:
            pass
        for k, v in stars.items():
            if len(v["signs"]) != 12:
                problems.append(f"stars.json: {k} has {len(v['signs'])} signs, need 12")

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
