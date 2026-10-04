"""Build the data files for the attribute-guess games from the snapshots in scripts/games-data/attr/.

Each game is a table: one row per thing (a country, an element, a laureate) and a few comparable columns.
The page picks the day's answer from `seq` and compares each guess with it column by column.
Column types: enum (same or not), num (equal, close, higher or lower), set (same, overlapping or not).
"""
from __future__ import annotations

import json
import random
from pathlib import Path


def _enum_state(s):
    s = s or "Unknown"
    return {"Expected to be a Gas": "Gas", "Expected to be a Solid": "Solid", "Expected to be a Liquid": "Liquid"}.get(s, s)


def _income(s):
    return "High income" if s.startswith("High income") else s


def _countries(rows):
    cols = [
        {"k": "continent", "l": "Continent", "t": "enum"},
        {"k": "subregion", "l": "Region", "t": "enum"},
        {"k": "pop", "l": "Population", "t": "num", "f": "pop", "rel": 0.5},
        {"k": "area", "l": "Area", "t": "num", "f": "area", "rel": 0.5},
        {"k": "coast", "l": "Coast", "t": "enum"},
        {"k": "side", "l": "Drives on", "t": "enum"},
        {"k": "income", "l": "Income", "t": "enum"},
    ]
    out = []
    for r in rows:
        out.append({"n": r["name"], "a": r["alt"], "v": [r["continent"], r["subregion"], r["pop"], r["area"], r["coast"], r["side"] or "Right", _income(r["income"])]})
    return cols, out, list(range(len(out)))


def _elements(rows):
    cols = [
        {"k": "z", "l": "Atomic number", "t": "num", "f": "int", "abs": 5},
        {"k": "period", "l": "Period", "t": "num", "f": "int", "abs": 1},
        {"k": "cat", "l": "Category", "t": "enum"},
        {"k": "state", "l": "State", "t": "enum"},
        {"k": "mass", "l": "Atomic mass", "t": "num", "f": "mass", "rel": 0.1},
        {"k": "year", "l": "Discovered", "t": "num", "f": "ayear", "abs": 15},
    ]
    out = [{"n": r["name"], "a": [r["sym"]], "v": [r["z"], r["period"], r["cat"], _enum_state(r["state"]), r["mass"], r["year"]]} for r in rows]
    return cols, out, [i for i, r in enumerate(rows) if r["z"] <= 103]


def _laureates(rows):
    cols = [
        {"k": "field", "l": "Prize", "t": "enum"},
        {"k": "year", "l": "Year", "t": "num", "f": "plain", "abs": 8},
        {"k": "born", "l": "Born", "t": "num", "f": "plain", "abs": 8},
        {"k": "age", "l": "Age at prize", "t": "num", "f": "int", "abs": 5},
        {"k": "continent", "l": "Born in", "t": "enum"},
        {"k": "country", "l": "Country", "t": "enum"},
        {"k": "gender", "l": "Gender", "t": "enum"},
    ]
    out = [{"n": r["name"], "a": [], "v": [r["field"], r["year"], r["born"], r["age"], r["continent"], r["country"], r["gender"]]} for r in rows]
    ranked = sorted(range(len(rows)), key=lambda i: -rows[i]["fame"])[:250]
    return cols, out, ranked


def _cities(rows):
    cols = [
        {"k": "continent", "l": "Continent", "t": "enum"},
        {"k": "country", "l": "Country", "t": "enum"},
        {"k": "pop", "l": "Population", "t": "num", "f": "pop", "rel": 0.4},
        {"k": "lat", "l": "Latitude", "t": "num", "f": "lat", "abs": 8},
        {"k": "lon", "l": "Longitude", "t": "num", "f": "lon", "abs": 15},
        {"k": "cap", "l": "Capital", "t": "enum"},
    ]
    out = [{"n": r["name"], "a": r["alt"], "v": [r["continent"], r["country"], r["pop"], r["lat"], r["lon"], "Capital" if r["capital"] else "Not a capital"]} for r in rows]
    ranked = sorted(range(len(rows)), key=lambda i: -rows[i]["pop"])[:250]
    return cols, out, ranked


NOT_ANSWERS = {"Mount Rushmore", "Mount Bazardüzü", "Mount Athos", "Mount Sinai", "Mount Kailash", "Table Mountain"}


def _peaks(rows):
    cols = [
        {"k": "continent", "l": "Continent", "t": "enum"},
        {"k": "countries", "l": "Country", "t": "set"},
        {"k": "elev", "l": "Height", "t": "num", "f": "m", "rel": 0.2},
        {"k": "lat", "l": "Latitude", "t": "num", "f": "lat", "abs": 8},
        {"k": "lon", "l": "Longitude", "t": "num", "f": "lon", "abs": 15},
        {"k": "volcano", "l": "Volcano", "t": "enum"},
    ]
    out = [{"n": r["name"], "a": [], "v": [r["continent"], r["countries"], r["elev"], r["lat"], r["lon"], "Yes" if r["volcano"] else "No"]} for r in rows]
    ranked = [i for i in sorted(range(len(rows)), key=lambda i: -rows[i]["fame"]) if rows[i]["name"] not in NOT_ANSWERS][:120]
    return cols, out, ranked


def _languages(rows):
    cols = [
        {"k": "year", "l": "First appeared", "t": "num", "f": "plain", "abs": 6},
        {"k": "typing", "l": "Typing", "t": "enum"},
        {"k": "runs", "l": "Runs as", "t": "enum"},
        {"k": "memory", "l": "Memory", "t": "enum"},
        {"k": "domain", "l": "Used for", "t": "enum"},
        {"k": "paradigms", "l": "Style", "t": "set"},
    ]
    out = [{"n": r["name"], "a": [], "v": [r["year"], r["typing"], r["runs"], r["memory"], r["domain"], r["paradigms"]]} for r in rows]
    return cols, out, [i for i, r in enumerate(rows) if r["well"]]


GAMES = {"citylink": ("cities", _cities), "peaklink": ("peaks", _peaks), "codelink": ("languages", _languages), "landlink": ("countries", _countries), "atomlink": ("elements", _elements), "prizelink": ("laureates", _laureates)}


def build(src: Path, epoch: str, days: int, enc_text) -> dict[str, str]:
    files = {}
    for gid, (fname, fn) in GAMES.items():
        p = src / "attr" / f"{fname}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))
        cols, out, pool = fn(rows)
        # the guess list is alphabetical; `pool` holds indexes into the original order, so remap after sorting
        order = sorted(range(len(out)), key=lambda i: out[i]["n"].lower())
        pos = {old: new for new, old in enumerate(order)}
        out = [out[i] for i in order]
        pool = [pos[i] for i in pool]
        seq, cycle = [], 0
        while len(seq) < days:
            rng = random.Random(f"attr:{gid}:{cycle}")
            lap = pool[:]
            rng.shuffle(lap)
            if seq and lap and lap[0] == seq[-1]:
                lap.append(lap.pop(0))
            seq.extend(lap)
            cycle += 1
        data = {"id": gid, "epoch": epoch, "cols": cols, "rows": out, "seq": enc_text(",".join(map(str, seq[:days])))}
        files[f"{gid}.json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    return files
