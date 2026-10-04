#!/usr/bin/env python3
"""Pick the daily chess puzzles from the Lichess puzzle database (CC0, https://database.lichess.org/#puzzles).

  pip install zstandard
  python3 scripts/fetch_chess_puzzles.py [path/to/lichess_db_puzzle.csv.zst]   # downloads it (about 300 MB) if no path is given

Keeps well-rated, widely played puzzles of 2 to 4 of your own moves, grouped into seven rating bands, one band
per weekday (Monday easiest, Sunday hardest), and writes scripts/games-data/chess-puzzles.json. The snapshot is
committed; the daily page and gen_games.py never touch the network.
"""
import csv
import io
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent / "games-data" / "chess-puzzles.json"
URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
# weekday (Monday = 0) -> rating band
BANDS = [(800, 1250), (1150, 1500), (1400, 1700), (1600, 1900), (1800, 2100), (2000, 2300), (2150, 2600)]
PER_BAND = 130
MIN_POP, MIN_PLAYS, MAX_RD = 92, 4000, 90
THEMES_OK = {"mate", "mateIn1", "mateIn2", "mateIn3", "fork", "pin", "skewer", "discoveredAttack", "hangingPiece", "trappedPiece", "backRankMate",
             "smotheredMate", "deflection", "attraction", "sacrifice", "advancedPawn", "promotion", "quietMove", "intermezzo", "doubleCheck",
             "exposedKing", "kingsideAttack", "queensideAttack", "capturingDefender", "clearance", "interference", "zugzwang", "endgame",
             "middlegame", "opening", "crushing", "advantage", "short", "oneMove", "long"}


def main() -> int:
    import zstandard
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if src is None:
        src = Path(tempfile.gettempdir()) / "lichess_db_puzzle.csv.zst"
        if not src.exists():
            subprocess.run(["curl", "-L", "-o", str(src), URL], check=True)
    pools: list[list[dict]] = [[] for _ in BANDS]
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
            if not 4 <= len(moves) <= 8:      # opponent's move, then 2 to 4 of the player's
                continue
            for b, (lo, hi) in enumerate(BANDS):
                if lo <= rating < hi:
                    themes = row["Themes"].split()
                    pools[b].append({"id": row["PuzzleId"], "f": row["FEN"], "m": row["Moves"], "r": rating, "t": themes[:4],
                                     "g": row["GameUrl"].split("lichess.org/")[-1], "pop": pop, "plays": plays})
                    break
    picked = []
    for b, pool in enumerate(pools):
        pool.sort(key=lambda p: (-p["pop"], -p["plays"], p["id"]))
        top = pool[: PER_BAND * 4]
        random.Random(f"chess-band-{b}").shuffle(top)
        chosen = sorted(top[:PER_BAND], key=lambda p: p["id"])
        picked.append([{k: v for k, v in p.items() if k not in ("pop", "plays")} for p in chosen])
        print(f"band {b} {BANDS[b]}: {len(pool)} candidates, kept {len(chosen)}")
    OUT.write_text(json.dumps({"source": "Lichess puzzle database, CC0", "bands": picked}, separators=(",", ":")) + "\n")
    print("wrote", OUT, OUT.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
