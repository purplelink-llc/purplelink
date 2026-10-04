#!/usr/bin/env python3
"""Build the pool behind Chess Puzzles (rated, unlimited) from the Lichess puzzle database (CC0).

  pip install zstandard
  python3 scripts/fetch_chess_pool.py path/to/lichess_db_puzzle.csv.zst

Keeps up to PER_BUCKET well-rated puzzles in every 100-point rating bucket and writes
  site/games/data/chess-pool/<bucket>.json    the puzzles themselves, loaded one bucket at a time
  netlify/lib/chess-index.json                {id: [rating, number of moves]} so the rating service can check a report
The snapshot is committed; nothing at runtime touches the network.
"""
import base64, csv, io, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "site" / "games" / "data" / "chess-pool"
INDEX = ROOT / "netlify" / "lib" / "chess-index.json"
LO, HI, STEP, PER_BUCKET = 500, 2900, 100, 300
MIN_POP, MIN_PLAYS, MAX_RD = 88, 2500, 90


def main() -> int:
    import zstandard
    src = Path(sys.argv[1])
    buckets: dict[int, list] = {b: [] for b in range(LO, HI + STEP, STEP)}
    with open(src, "rb") as fh:
        reader = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8")
        for row in csv.DictReader(reader):
            try:
                rating, pop, plays, rd = int(row["Rating"]), int(row["Popularity"]), int(row["NbPlays"]), int(row["RatingDeviation"])
            except ValueError:
                continue
            if pop < MIN_POP or plays < MIN_PLAYS or rd > MAX_RD:
                continue
            moves = row["Moves"].split()
            if not 4 <= len(moves) <= 10:
                continue
            b = min(HI, max(LO, rating // STEP * STEP))
            buckets[b].append({"i": row["PuzzleId"], "f": row["FEN"], "m": row["Moves"], "r": rating, "t": row["Themes"].split()[:4], "pop": pop, "plays": plays})
    POOL.mkdir(parents=True, exist_ok=True)
    index = {}
    for b, pool in buckets.items():
        pool.sort(key=lambda p: (-p["pop"], -p["plays"], p["i"]))
        top = pool[: PER_BUCKET * 3]
        random.Random(f"chess-pool-{b}").shuffle(top)
        chosen = sorted(top[:PER_BUCKET], key=lambda p: p["i"])
        out = []
        for p in chosen:
            out.append({"i": p["i"], "f": p["f"], "m": base64.b64encode(p["m"].encode()).decode(), "r": p["r"], "t": p["t"]})
            index[p["i"]] = [p["r"], len(p["m"].split())]
        (POOL / f"{b}.json").write_text(json.dumps({"b": b, "p": out}, separators=(",", ":")) + "\n")
        print(f"bucket {b}: {len(pool)} candidates, kept {len(out)}")
    INDEX.write_text(json.dumps(index, separators=(",", ":")) + "\n")
    print("puzzles:", len(index), "index bytes:", INDEX.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
