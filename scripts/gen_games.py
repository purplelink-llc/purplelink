#!/usr/bin/env python3
"""Build the data files the /games/ pages read.

Everything is a pure function of the committed source lists in scripts/games-data/, so a
rerun gives byte-identical output and a longer horizon only appends days (the shuffle is
seeded and the first N entries never change). That matters: a player who has already seen
"puzzle 12" must never see a different puzzle 12.

  python3 scripts/gen_games.py            # write site/games/data/*
  python3 scripts/gen_games.py --check    # exit 1 if the files on disk are stale

Outputs
  linkle.json    one five-letter answer per day
  quadlink.json  four five-letter answers per day, no repeats within a day
  valid5.txt     every accepted guess, one word per line
  trivia.json    five questions per day (added in the trivia step)
  stars.json     twelve readings per day (added in the horoscope step)
"""
from __future__ import annotations

import base64
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "games-data"
OUT = ROOT / "site" / "games" / "data"

EPOCH = "2026-10-05"   # puzzle 1; never change after launch
DAYS = 730


def words(name: str) -> list[str]:
    out = []
    for line in (SRC / name).read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            out.extend(line.split())
    return out


def enc(word: str) -> str:
    """Light obfuscation so the answer is not sitting in view-source as plain text."""
    return base64.b64encode(word[::-1].encode()).decode()


def answer_pool() -> list[str]:
    valid = set(words("valid5.txt"))
    blocked = set(words("blocked.txt"))
    pool = [w for w in words("answers5.txt") if w in valid and w not in blocked]
    return sorted(set(pool))


def cycle_stream(pool: list[str], seed: str, need: int) -> list[str]:
    """Concatenated seeded shuffles of the pool; the prefix never changes when `need` grows."""
    out: list[str] = []
    n = 0
    while len(out) < need:
        order = pool[:]
        random.Random(f"{seed}:{n}").shuffle(order)
        out.extend(order)
        n += 1
    return out[:need]


def linkle(pool: list[str]) -> dict:
    return {"epoch": EPOCH, "answers": [enc(w) for w in cycle_stream(pool, "linkle", DAYS)]}


def quadlink(pool: list[str]) -> dict:
    stream = cycle_stream(pool, "quadlink", DAYS * 4)
    days = []
    for d in range(DAYS):
        chunk = stream[d * 4:(d + 1) * 4]
        # A cycle boundary can put one word twice in a day; swap in the next unused word.
        seen: list[str] = []
        spare = iter(stream[DAYS * 4:] + pool)
        for w in chunk:
            while w in seen:
                w = next(spare)
            seen.append(w)
        days.append([enc(w) for w in seen])
    return {"epoch": EPOCH, "days": days}


def build() -> dict[str, str]:
    pool = answer_pool()
    files = {
        "linkle.json": json.dumps(linkle(pool), separators=(",", ":")) + "\n",
        "quadlink.json": json.dumps(quadlink(pool), separators=(",", ":")) + "\n",
        "valid5.txt": "\n".join(words("valid5.txt")) + "\n",
    }
    extra = ROOT / "scripts" / "gen_games_extra.py"
    if extra.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_games_extra", extra)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        files.update(mod.build(SRC, EPOCH, DAYS, enc))
    return files


def main() -> int:
    files = build()
    if "--check" in sys.argv:
        stale = [n for n, t in files.items() if not (OUT / n).exists() or (OUT / n).read_text() != t]
        if stale:
            print("stale games data:", ", ".join(stale))
            return 1
        print("games data up to date")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in files.items():
        (OUT / n).write_text(t)
    print(f"answer pool {len(answer_pool())} words; wrote {', '.join(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
