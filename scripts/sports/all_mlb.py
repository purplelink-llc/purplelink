#!/usr/bin/env python3
"""All MLB players from the SABR Lahman Baseball Database (1871-2025), CC BY-SA 3.0.
Downloaded from a GitHub CSV mirror of the 2025 release (cbwinslow/lahman-database-csv; official page: sabr.org/lahman-database).
Writes all/mlb.json. A player-season is one Appearances row with G_all >= 1; (yearID, lgID, teamID) -> Teams.franchID -> our id."""
import csv, collections, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_common import *
BASE = "https://raw.githubusercontent.com/cbwinslow/lahman-database-csv/HEAD/data/"
FILES = ["People.csv", "Appearances.csv", "Teams.csv", "TeamsFranchises.csv", "readme2025.txt"]
# Lahman franchID -> franchises.py id. Everything else (Negro Leagues, 19th-century defunct clubs, Federal League...) is dropped.
# Lahman's own 'ATH' franchise is the 1876 NL Philadelphia Athletics (defunct), the modern Athletics are 'OAK'.
FR = {"ANA": "LAA", "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BOS": "BOS", "CHC": "CHC", "CHW": "CWS", "CIN": "CIN", "CLE": "CLE",
      "COL": "COL", "DET": "DET", "FLA": "MIA", "HOU": "HOU", "KCR": "KC", "LAD": "LAD", "MIL": "MIL", "MIN": "MIN", "NYM": "NYM",
      "NYY": "NYY", "OAK": "ATH", "PHI": "PHI", "PIT": "PIT", "SDP": "SD", "SEA": "SEA", "SFG": "SF", "STL": "STL", "TBD": "TB",
      "TEX": "TEX", "TOR": "TOR", "WSN": "WSH"}
def rows(name):
    return list(csv.DictReader(open(RAW / "mlb" / name, encoding="utf-8-sig")))
def main():
    for f in FILES:
        if not (RAW / "mlb" / f).exists(): curl(BASE + f, out=RAW / "mlb" / f)
    teams = {(t["yearID"], t["lgID"], t["teamID"]): t["franchID"] for t in rows("Teams.csv")}
    people = {p["playerID"]: p for p in rows("People.csv")}
    st = collections.defaultdict(list); pos = {}
    miss = collections.Counter()
    for a in rows("Appearances.csv"):
        y = int(a["yearID"])
        if y > LAST_SEASON or int(a["G_all"] or 0) < 1: continue
        fid = FR.get(teams.get((a["yearID"], a["lgID"], a["teamID"])))
        pid = a["playerID"]
        # position tally counts all games, including unmapped (minor-ish) clubs
        t = pos.setdefault(pid, collections.Counter())
        for k, c in (("C", "G_c"), ("1B", "G_1b"), ("2B", "G_2b"), ("3B", "G_3b"), ("SS", "G_ss"), ("LF", "G_lf"), ("CF", "G_cf"), ("RF", "G_rf")):
            t[k] += int(a[c] or 0)
        gp, gs = int(a["G_p"] or 0), int(a["GS"] or 0)
        t["P"] += gp; t["_gs"] += min(gs, gp)
        if fid: st[pid].append([fid, y, y + 1])
        else: miss[(a["lgID"])] += 1
    out = []
    for pid, L in st.items():
        p = people.get(pid)
        if not p: continue
        t = pos[pid]; ps = None
        field = {k: v for k, v in t.items() if k in ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "P") and v > 0}
        if field:
            top = max(field, key=field.get)
            ps = ("SP" if t["_gs"] * 2 >= t["P"] else "RP") if top == "P" else top
        by = p["birthYear"].strip()
        out.append({"id": pid, "name": ((p["nameFirst"] or "") + " " + (p["nameLast"] or "")).strip(), "born": int(by) if by.isdigit() else None,
                    "pos": ps, "st": L})
    print("dropped appearance rows by league (not in franchise map):", dict(miss.most_common(8)))
    unm, amb, mt = match_famous("mlb", out, name_alias={"Goose Gossage": "Rich Gossage"})
    print("famous matched", len(mt), "unmatched", unm, "ambiguous", amb)
    print("fuzzy matches:", [(n, out[i]["name"]) for n, i, h, sc in mt if h == "fuzzy"])
    write_all("mlb", "SABR Lahman Baseball Database 1871-2025 (Sean Lahman / SABR; CSV mirror cbwinslow/lahman-database-csv). Franchise and position mapping by Purplelink.",
              "CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/): attribution required, share-alike", out)
if __name__ == "__main__": main()
