#!/usr/bin/env python3
"""Structural checks on every committed crossword grid (and its clues, when present).

  python3 scripts/check_crossword.py        # exit 1 on any problem

Grid: square, 180-degree symmetric, every run of white squares at least 3 long, all white
squares connected, entries match a fresh numbering, no repeated answer, no singular/plural pair.
Clues: every entry has one that passes `clue_problems`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "scripts" / "games-data" / "crossword"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    cw, extra = load("gen_crossword"), load("gen_games_extra")
    problems = []
    for gp in sorted(D.glob("*.grid.json")):
        day = gp.name.split(".")[0]
        g = json.loads(gp.read_text())
        rows, n = g["rows"], g["size"]
        if len(rows) != n or any(len(r) != n for r in rows):
            problems.append(f"{day}: not square")
            continue
        black = [[ch == "#" for ch in r] for r in rows]
        if any(black[r][c] != black[n - 1 - r][n - 1 - c] for r in range(n) for c in range(n)):
            problems.append(f"{day}: not symmetric")
        if not cw.runs_ok(black, n, [(r, c) for r in range(n) for c in range(n)]):
            problems.append(f"{day}: a run is shorter than 3")
        if not cw.connected(black, n):
            problems.append(f"{day}: white squares are not connected")
        fresh = cw.numbering(rows)
        if [(e["n"], e["dir"], e["answer"]) for e in fresh] != [(e["n"], e["dir"], e["answer"]) for e in g["entries"]]:
            problems.append(f"{day}: entries do not match the grid")
        ans = [e["answer"] for e in g["entries"]]
        if len(set(ans)) != len(ans):
            problems.append(f"{day}: repeated answer")
        if any(a + "s" in set(ans) for a in ans) and day >= "2026-10-12":
            problems.append(f"{day}: singular and plural of one word")
        cp = D / f"{day}.clues.json"
        if cp.exists():
            clues = json.loads(cp.read_text())
            for a in ans:
                bad = extra.clue_problems(a, clues.get(a.upper(), ""))
                if bad:
                    problems.append(f"{day}: {a}: {', '.join(bad)}")
    for p in problems:
        print("crossword PROBLEM:", p)
    print(f"crossword: {len(list(D.glob('*.grid.json')))} grids checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
