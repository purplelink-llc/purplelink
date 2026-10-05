#!/usr/bin/env python3
"""All NFL (and AFL 1960-69) players from the nflverse season rosters (github.com/nflverse/nflverse-data, release 'rosters',
roster_YYYY.csv for 1920-2025; repository licence CC-BY-4.0). One roster row = player x team x season.
Rows counted as 'played for the club that season': status ACT, RES, INA and the in-season transfer codes TRD/TRC/TRT/TRL; practice squad (DEV),
cut (CUT), PUP/NWT/SUS/exempt/retired/blank rows are ignored. Team codes are mapped to franchise ids season by season (relocations, AFL names,
Boston/Baltimore/Houston/St. Louis code reuse); defunct clubs (1920s teams, AAFC-only clubs, Steagles) are dropped.
Player identity: gsis_id when present, else (normalised name, birth date).  Writes all/nfl.json."""
import csv, sys, collections, pathlib, difflib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_common import *
RAWD = RAW / "nfl"
KEEP = {"ACT", "RES", "INA", "TRD", "TRC", "TRT", "TRL"}
BASE = "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_%d.csv"
def fid(code, y):
    """franchises.py NFL id for roster team code `code` in season y, or None for clubs outside the 32 franchises."""
    c = code
    if c in ("ARI", "ARZ", "PHO", "CHC"): return "ARI"
    if c == "STL": return "ARI" if y <= 1987 else ("LAR" if y >= 1995 else None)
    if c in ("SL", "RAM"): return "LAR" if (c == "SL" or y >= 1946) else None
    if c == "LA": return "LAR" if y >= 1950 else None
    if c == "CLE": return "LAR" if y <= 1945 and y >= 1937 else ("CLE" if y >= 1946 else None)
    if c == "CLV": return "CLE"
    if c in ("ATL", "CAR", "CIN", "DEN", "GB", "JAX", "MIA", "MIN", "NO", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "WAS", "DAL", "KC", "DET"):
        lo = {"ATL": 1966, "CAR": 1995, "CIN": 1968, "DEN": 1960, "GB": 1921, "JAX": 1995, "MIA": 1966, "MIN": 1961, "NO": 1967, "NYJ": 1963, "PHI": 1933,
              "PIT": 1933, "SEA": 1976, "SF": 1946, "TB": 1976, "WAS": 1937, "DAL": 1963, "KC": 1963, "DET": 1934}[c]
        if c == "DAL" and y == 1952: return "IND"        # the 1952 Dallas Texans: build.py maps them to the Colts franchise
        return c if y >= lo else None
    if c == "BUF": return "BUF" if y >= 1960 else None   # 1920s Bisons/All-Americans and the AAFC Bills are other franchises
    if c == "CHI": return "CHI"
    if c in ("CHB", "CHS", "DEC"): return "CHI"
    if c == "BAL": return "IND" if 1953 <= y <= 1983 else ("BAL" if y >= 1996 else None)
    if c == "BLT": return "BAL"
    if c == "IND": return "IND"
    if c == "HOU": return "TEN" if y <= 1996 else "HOU"
    if c == "HST": return "HOU"
    if c == "TEN": return "TEN"
    if c in ("OAK", "RAI", "LV"): return "LV"
    if c in ("SD", "LAC"): return "LAC"
    if c in ("NE",): return "NE"
    if c == "BOS": return "NE" if 1960 <= y <= 1970 else ("WAS" if 1932 <= y <= 1936 else None)
    if c == "NY": return "NYG" if y >= 1925 else None
    if c == "NYG": return "NYG"
    if c == "NYT": return "NYJ"
    if c in ("TEX",): return "KC"
    if c == "COW": return "DAL"
    if c == "POR": return "DET"
    return None
POSM = {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE", "OL": "OL", "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL",
        "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL", "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB", "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB"}
def load():
    RAWD.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(1920, LAST_SEASON + 1):
        f = RAWD / ("roster_%d.csv" % y)
        if not f.exists() or f.stat().st_size < 100: curl(BASE % y, out=f, delay=0.3)
        rows += [r for r in csv.DictReader(open(f, encoding="utf-8")) if r["status"] in KEEP]
    return rows
def main():
    rows = load(); print("kept roster rows", len(rows))
    # pass 1: (name, birth) -> gsis_id so id-less historical rows join the player's later id-bearing rows
    nb2g = {}
    for r in rows:
        if r["gsis_id"] and r["birth_date"]: nb2g.setdefault((norm_name(r["full_name"]), r["birth_date"]), r["gsis_id"])
    P = {}; dropped = collections.Counter()
    for r in rows:
        y = int(r["season"]); f = fid(r["team"], y)
        nm = norm_name(r["full_name"]); b = r["birth_date"]
        key = r["gsis_id"] or nb2g.get((nm, b)) or (("nb:" + nm + "|" + b) if b else ("n:" + nm + "|" + r["position"]))
        p = P.setdefault(key, {"id": key, "name": clean_name(r["full_name"]), "born": int(b[:4]) if b[:4].isdigit() else None, "st": [], "pos": collections.Counter()})
        if f: p["st"].append([f, y, y + 1])
        else: dropped[r["team"]] += 1
        pp = POSM.get(r["position"]) or POSM.get(r["depth_chart_position"])
        if pp: p["pos"][pp] += 1
        if r["pfr_id"] and "pfr" not in p: p["pfr"] = r["pfr_id"]
    print("dropped rows by unmapped team code:", dropped.most_common(15))
    # merge id-less duplicates: same birth date, near-identical names (spelling changes across rosters)
    byb = collections.defaultdict(list)
    for k, p in P.items():
        if k.startswith("nb:") or k.startswith("00-"): byb[k.split("|")[-1] if k.startswith("nb:") else None].append(k)
    merged = 0
    bdate = {}
    for k, p in P.items():
        if k.startswith("nb:"): bdate[k] = k.split("|")[-1]
    gs_by_birth = collections.defaultdict(list)
    for r in rows:
        if r["gsis_id"] and r["birth_date"]: gs_by_birth[r["birth_date"]].append((r["gsis_id"], norm_name(r["full_name"])))
    for k in [k for k in P if k.startswith("nb:")]:
        b = bdate[k]; nm = k[3:].split("|")[0]
        cands = {g for g, n in gs_by_birth.get(b, []) if difflib.SequenceMatcher(None, nm, n).ratio() >= 0.8}
        if len(cands) == 1:
            g = next(iter(cands))
            if g in P: P[g]["st"] += P[k]["st"]; P[g]["pos"].update(P[k]["pos"]); del P[k]; merged += 1
    print("merged spelling-variant duplicates:", merged)
    out = []
    for p in P.values():
        pos = p["pos"].most_common(1)[0][0] if p["pos"] else None
        out.append({"id": p["id"], "name": p["name"], "born": p["born"], "pos": pos, "st": p["st"]})
    unm, amb, mt = match_famous("nfl", out, ALIASES)
    print("famous matched", len(mt), "unmatched", unm, "ambiguous", amb)
    write_all("nfl", "nflverse season rosters 1920-2025 (github.com/nflverse/nflverse-data, release 'rosters'). Franchise and position mapping by Purplelink.",
              "CC BY 4.0 (nflverse-data repository licence; https://creativecommons.org/licenses/by/4.0/): attribution required", out)
ALIASES = {"Michael Vick": "Mike Vick", "Sauce Gardner": "Ahmad Gardner"}
if __name__ == "__main__": main()
