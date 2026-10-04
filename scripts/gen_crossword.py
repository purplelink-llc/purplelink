#!/usr/bin/env python3
"""Generate the daily themeless crossword grids (answers only; clues are written separately).

  python3 scripts/gen_crossword.py --ahead 21        # create any missing grid up to 21 days from today
  python3 scripts/gen_crossword.py --date 2026-10-05 # one date
  python3 scripts/gen_crossword.py --stats           # fill time per weekday, for tuning

A grid is a pure function of its date: seeded symmetric black-square patterns, then a
backtracking fill from scripts/games-data/cw-words.txt. The result is written to
scripts/games-data/crossword/<date>.grid.json and committed, so a later change to this file
never changes a puzzle that has already been published.

Difficulty by weekday (Monday easiest, Sunday hardest): grid size, how rare the words may be,
and how long the longest entries are. Clues carry the other half of the difficulty (see
docs/games.md for the clue rules the weekly routine follows).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "games-data"
OUT = SRC / "crossword"

# weekday (Monday=0): size, black squares (min, max), minimum Zipf for ordinary words, for long words
PLAN = {
    0: dict(size=9, blacks=(14, 18), zipf=3.8, zipf_long=3.4),
    1: dict(size=9, blacks=(14, 18), zipf=3.6, zipf_long=3.3),
    2: dict(size=11, blacks=(22, 28), zipf=3.4, zipf_long=3.1),
    3: dict(size=11, blacks=(22, 28), zipf=3.2, zipf_long=2.9),
    4: dict(size=13, blacks=(30, 38), zipf=3.0, zipf_long=2.7, hard=True),
    5: dict(size=13, blacks=(30, 38), zipf=2.8, zipf_long=2.5, hard=True),
    6: dict(size=15, blacks=(42, 50), zipf=3.1, zipf_long=2.7, hard=True),
}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LONG = 7   # lengths from here use zipf_long
# Short words are where the junk lives (abbreviations, interjections, names): hold them to a higher bar.
LEN_FLOOR = {3: 3.7, 4: 3.4}
# Friday to Sunday get a lower bar for short words: their grids are bigger or their words rarer anyway.
LEN_FLOOR_HARD = {3: 3.3, 4: 3.1}
MAX_SHORT_SHARE = 0.5
_popcount = getattr(int, "bit_count", None) or (lambda x: bin(x).count("1"))
NODE_LIMIT = {9: 3000, 11: 4000, 13: 8000, 15: 20000}   # short, many randomized restarts beat one long search
TIME_LIMIT = 8.0
RELAX_EVERY = 30      # after this many failed patterns, allow slightly rarer words
RELAX_STEP = 0.1
RELAX_MAX = 1.0


def load_words() -> dict[int, list[tuple[str, float]]]:
    by_len: dict[int, list[tuple[str, float]]] = {}
    blocked = set()
    for line in (SRC / "cw-blocked.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            blocked.update(line.split())
    for line in (SRC / "cw-words.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        w, z = line.split()
        if w in blocked:
            continue
        by_len.setdefault(len(w), []).append((w, float(z)))
    return by_len


# ---------- black-square patterns ----------

def runs_ok(grid: list[list[bool]], n: int, cells: list[tuple[int, int]]) -> bool:
    """True if every white run through the given cells (both directions) is at least 3 long."""
    for r, c in cells:
        if grid[r][c]:
            continue
        for dr, dc in ((0, 1), (1, 0)):
            a = 0
            rr, cc = r, c
            while rr - dr >= 0 and cc - dc >= 0 and not grid[rr - dr][cc - dc]:
                rr -= dr; cc -= dc; a += 1
            rr, cc = r, c
            b = 0
            while rr + dr < n and cc + dc < n and not grid[rr + dr][cc + dc]:
                rr += dr; cc += dc; b += 1
            if a + b + 1 < 3:
                return False
    return True


def connected(grid: list[list[bool]], n: int) -> bool:
    whites = [(r, c) for r in range(n) for c in range(n) if not grid[r][c]]
    if not whites:
        return False
    seen = {whites[0]}
    stack = [whites[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < n and 0 <= cc < n and not grid[rr][cc] and (rr, cc) not in seen:
                seen.add((rr, cc))
                stack.append((rr, cc))
    return len(seen) == len(whites)


def make_pattern(n: int, blacks: tuple[int, int], rng: random.Random) -> list[list[bool]] | None:
    """True = black. 180-degree rotational symmetry, runs of at least 3, no 2x2 black block,
    all white cells connected."""
    grid = [[False] * n for _ in range(n)]
    target = rng.randint(*blacks)
    positions = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(positions)
    count = 0
    for r, c in positions:
        if count >= target:
            break
        mr, mc = n - 1 - r, n - 1 - c
        if grid[r][c] or (r, c) == (mr, mc) and count + 1 > target + 1:
            continue
        add = [(r, c)] if (r, c) == (mr, mc) else [(r, c), (mr, mc)]
        for a, b in add:
            grid[a][b] = True
        # no 2x2 black block around either new cell
        bad = False
        for a, b in add:
            for da in (0, -1):
                for db in (0, -1):
                    ra, rb = a + da, b + db
                    if 0 <= ra < n - 1 and 0 <= rb < n - 1 and grid[ra][rb] and grid[ra + 1][rb] and grid[ra][rb + 1] and grid[ra + 1][rb + 1]:
                        bad = True
        near = set()
        for a, b in add:
            for dd in range(-2, 3):
                for coords in ((a + dd, b), (a, b + dd)):
                    if 0 <= coords[0] < n and 0 <= coords[1] < n:
                        near.add(coords)
        if bad or not runs_ok(grid, n, list(near)) or not connected(grid, n):
            for a, b in add:
                grid[a][b] = False
            continue
        count += len(add)
    return grid if count >= blacks[0] else None


# ---------- slots ----------

def find_slots(grid: list[list[bool]], n: int):
    slots = []   # (direction, row, col, cells)
    for r in range(n):
        c = 0
        while c < n:
            if grid[r][c]:
                c += 1
                continue
            s = c
            while c < n and not grid[r][c]:
                c += 1
            if c - s >= 3:
                slots.append(("across", r, s, [(r, k) for k in range(s, c)]))
    for c in range(n):
        r = 0
        while r < n:
            if grid[r][c]:
                r += 1
                continue
            s = r
            while r < n and not grid[r][c]:
                r += 1
            if r - s >= 3:
                slots.append(("down", s, c, [(k, c) for k in range(s, r)]))
    return slots


# ---------- fill ----------

class Filler:
    def __init__(self, words: dict[int, list[tuple[str, float]]], plan: dict, rng: random.Random):
        self.rng = rng
        self.lists: dict[int, list[str]] = {}
        self.index: dict[int, dict[tuple[int, str], int]] = {}
        self.full: dict[int, int] = {}
        for L, items in words.items():
            lf = LEN_FLOOR_HARD if plan.get("hard") else LEN_FLOOR
            floor = max(plan["zipf_long"] if L >= LONG else plan["zipf"], lf.get(L, 0))
            scored = [(z + rng.uniform(0, 0.9), w) for w, z in items if z >= floor]
            scored.sort(reverse=True)
            lst = [w for _, w in scored]
            self.lists[L] = lst
            idx: dict[tuple[int, str], int] = {}
            for i, w in enumerate(lst):
                bit = 1 << i
                for p, ch in enumerate(w):
                    idx[(p, ch)] = idx.get((p, ch), 0) | bit
            self.index[L] = idx
            self.full[L] = (1 << len(lst)) - 1
        self.used: set[str] = set()
        self.size = plan["size"]
        self.nodes = 0
        self.deadline = 0.0

    def fill(self, grid: list[list[bool]], n: int) -> list[list[str]] | None:
        slots = find_slots(grid, n)
        for _d, _r, _c, cells in slots:
            if len(cells) not in self.lists or not self.lists[len(cells)]:
                return None
        letters: dict[tuple[int, int], str] = {}
        cross: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for si, (_d, _r, _c, cells) in enumerate(slots):
            for p, cell in enumerate(cells):
                cross.setdefault(cell, []).append((si, p))
        cand = [self.full[len(s[3])] for s in slots]
        self.nodes = 0
        self.deadline = time.time() + TIME_LIMIT
        ok = self._dfs(slots, cross, cand, letters, [False] * len(slots))
        if not ok:
            return None
        return [["#" if grid[r][c] else letters[(r, c)] for c in range(n)] for r in range(n)]

    def _dfs(self, slots, cross, cand, letters, done) -> bool:
        if all(done):
            return True
        self.nodes += 1
        if self.nodes > NODE_LIMIT[self.size] or time.time() > self.deadline:
            return False
        # most constrained slot first
        best, best_n = -1, 1 << 60
        for i, bits in enumerate(cand):
            if done[i]:
                continue
            k = _popcount(bits)
            if k < best_n:
                best, best_n = i, k
                if k == 0:
                    return False
        si = best
        _d, _r, _c, cells = slots[si]
        L = len(cells)
        bits = cand[si]
        lst = self.lists[L]
        tried = 0
        while bits and tried < 40:
            low = bits & -bits
            wi = low.bit_length() - 1
            bits ^= low
            w = lst[wi]
            if w in self.used:
                continue
            tried += 1
            # place
            changed = []
            for p, cell in enumerate(cells):
                if cell not in letters:
                    letters[cell] = w[p]
                    changed.append(cell)
            self.used.add(w)
            done[si] = True
            saved = {}
            ok = True
            for cell in changed:
                for (sj, pj) in cross[cell]:
                    if sj == si or done[sj]:
                        continue
                    if sj not in saved:
                        saved[sj] = cand[sj]
                    cand[sj] &= self.index[len(slots[sj][3])].get((pj, letters[cell]), 0)
                    if cand[sj] == 0:
                        ok = False
                        break
                if not ok:
                    break
            # a fully-lettered crossing slot must itself be a unique word: it is handled when
            # its candidate set narrows to the single matching word; mark it done if so.
            if ok and self._dfs(slots, cross, cand, letters, done):
                return True
            for sj, v in saved.items():
                cand[sj] = v
            done[si] = False
            self.used.discard(w)
            for cell in changed:
                del letters[cell]
        return False


def numbering(rows: list[str]):
    n = len(rows)
    white = lambda r, c: 0 <= r < n and 0 <= c < n and rows[r][c] != "#"
    entries, num = [], 0
    for r in range(n):
        for c in range(n):
            if not white(r, c):
                continue
            a = not white(r, c - 1) and white(r, c + 1) and white(r, c + 2)
            d = not white(r - 1, c) and white(r + 1, c) and white(r + 2, c)
            if a or d:
                num += 1
            if a:
                w = ""
                k = c
                while white(r, k):
                    w += rows[r][k]; k += 1
                entries.append({"n": num, "dir": "across", "row": r, "col": c, "answer": w})
            if d:
                w = ""
                k = r
                while white(k, c):
                    w += rows[k][c]; k += 1
                entries.append({"n": num, "dir": "down", "row": r, "col": c, "answer": w})
    return entries


def generate(day: date, words, verbose=False) -> dict:
    base = PLAN[day.weekday()]
    n = base["size"]
    attempt = 0
    t0 = time.time()
    while True:
        attempt += 1
        relax = min(RELAX_MAX, RELAX_STEP * (attempt // RELAX_EVERY))
        plan = dict(base, zipf=base["zipf"] - relax, zipf_long=base["zipf_long"] - relax)
        rng = random.Random(f"cw:{day.isoformat()}:{attempt}")
        pat = make_pattern(n, plan["blacks"], rng)
        if pat is None:
            continue
        slots = find_slots(pat, n)
        if not slots:
            continue
        # too many three-letter slots makes a puzzle of abbreviations; keep them to a minority
        if sum(1 for sl in slots if len(sl[3]) == 3) > MAX_SHORT_SHARE * len(slots):
            continue
        filler = Filler(words, plan, rng)
        rows = filler.fill(pat, n)
        if rows:
            strs = ["".join(r) for r in rows]
            entries = numbering(strs)
            answers = [e["answer"] for e in entries]
            if len(set(answers)) != len(answers):
                continue
            # no singular and plural of the same word in one grid (AREA and AREAS)
            if any(a + "s" in set(answers) for a in answers):
                continue
            if verbose:
                print(f"  {day} {DAY_NAMES[day.weekday()]:9} {n}x{n}: {len(entries)} entries, attempt {attempt}, zipf floor -{relax:.1f}, {time.time() - t0:.1f}s", flush=True)
            return {"date": day.isoformat(), "weekday": DAY_NAMES[day.weekday()], "size": n,
                    "rows": strs, "entries": entries}


def grid_path(day: date) -> Path:
    return OUT / f"{day.isoformat()}.grid.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ahead", type=int, default=0)
    ap.add_argument("--date")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    words = load_words()
    OUT.mkdir(parents=True, exist_ok=True)
    days = []
    if a.date:
        days = [date.fromisoformat(a.date)]
    elif a.stats:
        d0 = date(2030, 1, 7)   # a Monday, outside any real puzzle date
        days = [d0 + timedelta(days=i) for i in range(7)]
    else:
        days = [date.today() + timedelta(days=i) for i in range(a.ahead + 1)]
    for day in days:
        p = grid_path(day)
        if p.exists() and not a.stats:
            continue
        g = generate(day, words, verbose=True)
        if not a.stats:
            p.write_text(json.dumps(g, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
