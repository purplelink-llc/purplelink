#!/usr/bin/env python3
"""Daily Sudoku generator: unique-solution puzzles graded by the techniques a human needs, getting harder every week.

  python3 scripts/gen_sudoku.py --days 140      # write scripts/games-data/sudoku.json (cached; only missing days are generated)
  python3 scripts/gen_sudoku.py --stats         # grade and time a sample of puzzles per week

A season is ten weeks. Each week is harder than the one before: fewer givens and a higher technique level
(1 singles, 2 locked candidates, 3 pairs and triples, 4 X-Wing, 5 needs one guess to get started).
After week ten the next season starts again at week one. Puzzle N is a pure function of N (seeded), so a
rerun never changes a published day.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "games-data" / "sudoku.json"
EPOCH_DOW_MONDAY_OFFSET = 6      # day 0 (2026-10-04) is a Sunday; weeks run Monday to Sunday

# week of the season -> (technique level the puzzle must need, give-up-digging-below clue count / dig-until clue count)
SEASON = [(1, 42), (1, 34), (2, 34), (2, 30), (3, 30), (3, 28), (4, 28), (4, 26), (5, 26), (5, 24)]
LEVEL_NAMES = {1: "Beginner", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Expert"}
WEEK_NAMES = ["Beginner", "Beginner", "Easy", "Easy", "Medium", "Medium", "Hard", "Hard", "Expert", "Expert"]
MIN_CLUES = 22

ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [[(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)] for br in range(3) for bc in range(3)]
UNITS = ROWS + COLS + BOXES
PEERS = [set() for _ in range(81)]
for u in UNITS:
    for a in u:
        for b in u:
            if a != b:
                PEERS[a].add(b)
PEERS = [sorted(p) for p in PEERS]
BIT = [0] + [1 << (d - 1) for d in range(1, 10)]
FULL = 0x1FF


def popcount(x: int) -> int:
    return bin(x).count("1")


def digits(mask: int):
    d = 1
    while mask:
        if mask & 1:
            yield d
        mask >>= 1
        d += 1


# ---------- fast solver: counts solutions (stops at `limit`) ----------

def count_solutions(grid: list[int], limit: int = 2) -> int:
    rows = [0] * 9; cols = [0] * 9; boxes = [0] * 9
    cells = []
    for i, v in enumerate(grid):
        if v:
            b = BIT[v]
            r, c = divmod(i, 9)
            if rows[r] & b or cols[c] & b or boxes[(r // 3) * 3 + c // 3] & b:
                return 0
            rows[r] |= b; cols[c] |= b; boxes[(r // 3) * 3 + c // 3] |= b
        else:
            cells.append(i)
    found = 0

    def solve(remaining: list[int]) -> None:
        nonlocal found
        if found >= limit:
            return
        if not remaining:
            found += 1
            return
        best, best_mask, best_n = -1, 0, 10
        for idx, i in enumerate(remaining):
            r, c = divmod(i, 9)
            m = FULL & ~(rows[r] | cols[c] | boxes[(r // 3) * 3 + c // 3])
            n = popcount(m)
            if n < best_n:
                best, best_mask, best_n = idx, m, n
                if n <= 1:
                    break
        if best_n == 0:
            return
        i = remaining[best]
        r, c = divmod(i, 9)
        b3 = (r // 3) * 3 + c // 3
        rest = remaining[:best] + remaining[best + 1:]
        for d in digits(best_mask):
            bit = BIT[d]
            rows[r] |= bit; cols[c] |= bit; boxes[b3] |= bit
            solve(rest)
            rows[r] &= ~bit; cols[c] &= ~bit; boxes[b3] &= ~bit
            if found >= limit:
                return

    solve(cells)
    return found


def random_solution(rng: random.Random) -> list[int]:
    grid = [0] * 81
    rows = [0] * 9; cols = [0] * 9; boxes = [0] * 9

    def fill(i: int) -> bool:
        if i == 81:
            return True
        r, c = divmod(i, 9)
        b3 = (r // 3) * 3 + c // 3
        order = list(range(1, 10))
        rng.shuffle(order)
        for d in order:
            bit = BIT[d]
            if rows[r] & bit or cols[c] & bit or boxes[b3] & bit:
                continue
            grid[i] = d
            rows[r] |= bit; cols[c] |= bit; boxes[b3] |= bit
            if fill(i + 1):
                return True
            rows[r] &= ~bit; cols[c] &= ~bit; boxes[b3] &= ~bit
            grid[i] = 0
        return False

    fill(0)
    return grid


# ---------- logical solver (the grader) ----------

class Logic:
    def __init__(self, grid: list[int]):
        self.val = [0] * 81
        self.cand = [FULL] * 81
        self.ok = True
        for i, v in enumerate(grid):
            if v:
                self.place(i, v)

    def place(self, i: int, d: int) -> None:
        if not (self.cand[i] & BIT[d]) and self.val[i] != d:
            self.ok = False
            return
        self.val[i] = d
        self.cand[i] = 0
        for p in PEERS[i]:
            if self.val[p] == d:
                self.ok = False
            self.cand[p] &= ~BIT[d]

    def solved(self) -> bool:
        return all(self.val)

    def dead(self) -> bool:
        return not self.ok or any(self.val[i] == 0 and self.cand[i] == 0 for i in range(81))

    # level 1
    def singles(self) -> bool:
        progress = False
        changed = True
        while changed and self.ok:
            changed = False
            for i in range(81):
                if not self.val[i] and popcount(self.cand[i]) == 1:
                    self.place(i, next(digits(self.cand[i])))
                    changed = progress = True
            for u in UNITS:
                for d in range(1, 10):
                    bit = BIT[d]
                    spots = [i for i in u if self.cand[i] & bit]
                    if len(spots) == 1 and not self.val[spots[0]]:
                        self.place(spots[0], d)
                        changed = progress = True
        return progress

    # level 2
    def locked(self) -> bool:
        did = False
        for d in range(1, 10):
            bit = BIT[d]
            for box in BOXES:
                spots = [i for i in box if self.cand[i] & bit]
                if len(spots) < 2:
                    continue
                for lines in (ROWS, COLS):
                    owners = {next(k for k, ln in enumerate(lines) if i in ln) for i in spots}
                    if len(owners) == 1:
                        ln = lines[owners.pop()]
                        for j in ln:
                            if j not in box and self.cand[j] & bit:
                                self.cand[j] &= ~bit; did = True
            for lines in (ROWS, COLS):
                for ln in lines:
                    spots = [i for i in ln if self.cand[i] & bit]
                    if len(spots) < 2:
                        continue
                    boxes = {next(k for k, bx in enumerate(BOXES) if i in bx) for i in spots}
                    if len(boxes) == 1:
                        bx = BOXES[boxes.pop()]
                        for j in bx:
                            if j not in ln and self.cand[j] & bit:
                                self.cand[j] &= ~bit; did = True
        return did

    # level 3: naked pairs/triples and hidden pairs
    def subsets(self) -> bool:
        did = False
        for u in UNITS:
            empty = [i for i in u if not self.val[i]]
            for n in (2, 3):
                for a in range(len(empty)):
                    if popcount(self.cand[empty[a]]) > n:
                        continue
                    for b in range(a + 1, len(empty)):
                        if n == 2:
                            grp = (empty[a], empty[b])
                            m = self.cand[grp[0]] | self.cand[grp[1]]
                            if popcount(m) == 2:
                                for j in empty:
                                    if j not in grp and self.cand[j] & m:
                                        self.cand[j] &= ~m; did = True
                        else:
                            for c in range(b + 1, len(empty)):
                                grp = (empty[a], empty[b], empty[c])
                                m = self.cand[grp[0]] | self.cand[grp[1]] | self.cand[grp[2]]
                                if popcount(m) == 3:
                                    for j in empty:
                                        if j not in grp and self.cand[j] & m:
                                            self.cand[j] &= ~m; did = True
            # hidden pairs
            where = {d: [i for i in empty if self.cand[i] & BIT[d]] for d in range(1, 10)}
            ds = [d for d in where if len(where[d]) == 2]
            for x in range(len(ds)):
                for y in range(x + 1, len(ds)):
                    if where[ds[x]] == where[ds[y]]:
                        m = BIT[ds[x]] | BIT[ds[y]]
                        for i in where[ds[x]]:
                            if self.cand[i] & ~m:
                                self.cand[i] &= m; did = True
        return did

    # level 4: X-Wing
    def xwing(self) -> bool:
        did = False
        for d in range(1, 10):
            bit = BIT[d]
            for lines, cross in ((ROWS, COLS), (COLS, ROWS)):
                pos = []
                for k, ln in enumerate(lines):
                    spots = tuple(next(c for c, cl in enumerate(cross) if i in cl) for i in ln if self.cand[i] & bit)
                    if len(spots) == 2:
                        pos.append((k, spots))
                for x in range(len(pos)):
                    for y in range(x + 1, len(pos)):
                        if pos[x][1] == pos[y][1]:
                            for c in pos[x][1]:
                                for j in cross[c]:
                                    row_or_col = next(k for k, ln in enumerate(lines) if j in ln)
                                    if row_or_col not in (pos[x][0], pos[y][0]) and self.cand[j] & bit:
                                        self.cand[j] &= ~bit; did = True
        return did

    def run(self, level: int) -> bool:
        """Solve using techniques up to `level` (1 to 4). True if the grid is completed."""
        while self.ok and not self.solved():
            if self.singles():
                continue
            if self.dead():
                return False
            if level >= 2 and self.locked():
                continue
            if level >= 3 and self.subsets():
                continue
            if level >= 4 and self.xwing():
                continue
            return False
        return self.ok and self.solved()


def copy_logic(src: Logic) -> Logic:
    n = Logic.__new__(Logic)
    n.val = src.val[:]; n.cand = src.cand[:]; n.ok = src.ok
    return n


def solves_with_one_guess(grid: list[int]) -> bool:
    """Level 5: stuck at level 4, but trying each candidate of one cell and applying only singles finishes it."""
    lg = Logic(grid)
    lg.run(4)
    if lg.solved():
        return True
    if lg.dead():
        return False
    cells = sorted((i for i in range(81) if not lg.val[i]), key=lambda i: popcount(lg.cand[i]))
    for i in cells[:12]:
        survivors = []
        for d in digits(lg.cand[i]):
            t = copy_logic(lg)
            t.place(i, d)
            t.run(1)
            if not t.dead():
                survivors.append((d, t))
        if len(survivors) == 1:
            return True      # every other candidate leads to a contradiction, so the guess is forced
    return False


def grade(grid: list[int]) -> int:
    for level in (1, 2, 3, 4):
        lg = Logic(grid)
        if lg.run(level):
            return level
    return 5 if solves_with_one_guess(grid) else 6


# ---------- digging ----------

def make_puzzle(rng: random.Random, level: int, clues_target: int) -> tuple[list[int], list[int], int]:
    sol = random_solution(rng)
    puz = sol[:]
    order = list(range(41))      # one of each 180-degree pair, plus the centre
    rng.shuffle(order)
    clues = 81
    for i in order:
        j = 80 - i
        if clues <= MIN_CLUES:
            break
        keep_i, keep_j = puz[i], puz[j]
        if i == j:
            puz[i] = 0
            removed = 1
        else:
            puz[i] = puz[j] = 0
            removed = 2
        if count_solutions(puz) != 1:
            puz[i], puz[j] = keep_i, keep_j
            continue
        clues -= removed
        if clues <= clues_target and grade(puz) >= level:
            break
    return puz, sol, grade(puz)


def season_week(day_index: int) -> int:
    """1 to 10: which week of the ten-week season this puzzle day falls in (day 0 is a Sunday; weeks run Monday to Sunday)."""
    week = (day_index + EPOCH_DOW_MONDAY_OFFSET) // 7      # 0 for the first Sunday, then 1, 2, ...
    return (max(week, 1) - 1) % 10 + 1


def generate_day(day_index: int, enc) -> dict:
    wk = season_week(day_index)
    level, target = SEASON[wk - 1]
    for attempt in range(400):
        rng = random.Random(f"sudoku:{day_index}:{attempt}")
        puz, sol, g = make_puzzle(rng, level, target)
        if g == level and sum(1 for v in puz if v) <= target + 3:
            return {"p": "".join(str(v) if v else "." for v in puz), "s": enc("".join(map(str, sol))), "l": LEVEL_NAMES[level], "w": wk,
                    "n": sum(1 for v in puz if v)}
    # could not hit the exact level: keep the last unique puzzle that is at least that hard
    return {"p": "".join(str(v) if v else "." for v in puz), "s": enc("".join(map(str, sol))), "l": LEVEL_NAMES[min(g, 5)], "w": wk, "n": sum(1 for v in puz if v)}


def main() -> int:
    import base64
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=140)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    enc = lambda s: base64.b64encode(s.encode()).decode()
    if a.stats:
        for wk in range(1, 11):
            idx = wk * 7 - 5
            t = time.time()
            d = generate_day(idx, enc)
            print(f"week {wk:2} ({d['l']:9}) clues {d['n']:2}  {time.time() - t:5.1f}s")
        return 0
    have = json.loads(OUT.read_text())["days"] if OUT.exists() else []
    days = have[:]
    t0 = time.time()
    for i in range(len(have), a.days):
        days.append(generate_day(i, enc))
        if i % 10 == 9:
            print(f"  day {i + 1}/{a.days} {time.time() - t0:.0f}s", flush=True)
    OUT.write_text(json.dumps({"epoch": "2026-10-04", "days": days}, separators=(",", ":")) + "\n")
    print(f"wrote {len(days)} puzzles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
