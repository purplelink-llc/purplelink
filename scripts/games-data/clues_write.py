#!/usr/bin/env python3
"""Turn a text block of `ANSWER: clue` lines into scripts/games-data/crossword/<date>.clues.json
and report anything the validator rejects or any grid entry that has no clue.

  python3 scripts/games-data/clues_write.py 2026-10-05 < clues.txt
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import importlib.util
spec = importlib.util.spec_from_file_location("extra", HERE.parent / "gen_games_extra.py")
extra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extra)

day = sys.argv[1]
clues = {}
for line in sys.stdin.read().splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    ans, clue = line.split(":", 1)
    clues[ans.strip().upper()] = clue.strip()
grid = json.loads((HERE / "crossword" / f"{day}.grid.json").read_text())
need = {e["answer"].upper() for e in grid["entries"]}
missing = sorted(need - set(clues))
extra_keys = sorted(set(clues) - need)
bad = [f"{a}: {', '.join(extra.clue_problems(a, c))}" for a, c in clues.items() if a in need and extra.clue_problems(a, c)]
print(day, grid["weekday"], f"{len(clues)} clues for {len(need)} answers")
if missing: print("  MISSING:", " ".join(missing))
if extra_keys: print("  NOT IN GRID:", " ".join(extra_keys))
for b in bad: print("  PROBLEM", b)
if not (missing or bad):
    (HERE / "crossword" / f"{day}.clues.json").write_text(json.dumps({a: clues[a] for a in sorted(need)}, ensure_ascii=False, indent=0) + "\n")
    print("  written")
