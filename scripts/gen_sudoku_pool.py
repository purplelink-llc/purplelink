#!/usr/bin/env python3
"""Pre-generate the pool behind Sudoku Unlimited: unique-solution puzzles graded 1 (Beginner) to 5 (Expert).

  python3 scripts/gen_sudoku_pool.py --per-level 250     # about 2.5 s per puzzle, three worker processes

Writes site/games/data/sudoku-pool/level-N.json (one file per level, loaded on demand). The page also relabels
digits and flips or rotates each puzzle, so a pool of 250 per level plays as many more. Seeded: re-running with
the same numbers gives the same puzzles; raise --per-level to append new ones.
"""
import argparse, base64, json, random, sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_sudoku as S

OUT = Path(__file__).resolve().parent.parent / "site" / "games" / "data" / "sudoku-pool"
TARGET = {1: 40, 2: 33, 3: 30, 4: 27, 5: 25}   # clue counts to aim for at each level


def one(job):
    level, i = job
    for attempt in range(400):
        rng = random.Random(f"pool:{level}:{i}:{attempt}")
        puz, sol, g = S.make_puzzle(rng, level, TARGET[level])
        if g == level and sum(1 for v in puz if v) <= TARGET[level] + 3:
            return level, i, "".join(str(v) if v else "." for v in puz), base64.b64encode("".join(map(str, sol)).encode()).decode()
    return level, i, None, None


def sample(k):
    """One random unique puzzle, filed under whatever level it turns out to be. Much cheaper than aiming at a level."""
    rng = random.Random(f"bin:{k}")
    target = 22 + k % 12
    puz, sol, g = S.make_puzzle(rng, 1, target)
    return min(5, g), "".join(str(v) if v else "." for v in puz), base64.b64encode("".join(map(str, sol)).encode()).decode()


def fill_by_binning(have, per_level, workers, start=0):
    """Top up every level that is short by making puzzles of mixed clue counts and keeping each at its true level."""
    k, seen = start, {lv: {p for p, _ in have[lv]} for lv in have}
    with Pool(workers) as pool:
        while any(len(have[lv]) < per_level for lv in have):
            for lv, p, s in pool.imap_unordered(sample, range(k, k + 96), chunksize=4):
                if len(have[lv]) < per_level and p not in seen[lv]:
                    have[lv].append([p, s]); seen[lv].add(p)
            k += 96
            print("  ", k, {lv: len(have[lv]) for lv in sorted(have)}, flush=True)
            for lv in have:
                (OUT / f"level-{lv}.json").write_text(json.dumps({"level": lv, "p": have[lv]}, separators=(",", ":")) + "\n")
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=250)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--bin", action="store_true", help="fast mode: fill short levels by sorting mixed puzzles into their levels")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    have = {}
    for lv in range(1, 6):
        f = OUT / f"level-{lv}.json"
        have[lv] = json.loads(f.read_text())["p"] if f.exists() else []
    if a.bin:
        fill_by_binning(have, a.per_level, a.workers, start=sum(len(v) for v in have.values()) * 7)
        print({k: len(v) for k, v in have.items()})
        return
    jobs = [(lv, i) for lv in range(1, 6) for i in range(len(have[lv]), a.per_level)]
    print(f"{len(jobs)} puzzles to make", flush=True)
    done = 0
    with Pool(a.workers) as pool:
        for lv, i, p, s in pool.imap(one, jobs, chunksize=1):
            if p:
                have[lv].append([p, s])
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
                for k in have:
                    (OUT / f"level-{k}.json").write_text(json.dumps({"level": k, "p": have[k]}, separators=(",", ":")) + "\n")
    for k in have:
        (OUT / f"level-{k}.json").write_text(json.dumps({"level": k, "p": have[k]}, separators=(",", ":")) + "\n")
    print({k: len(v) for k, v in have.items()})


if __name__ == "__main__":
    main()
