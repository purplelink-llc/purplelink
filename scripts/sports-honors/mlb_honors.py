#!/usr/bin/env python3
"""MLB career honors from the Lahman database (SABR, CC BY-SA 3.0) for the famous pool.
Writes scripts/sports-honors/mlb.json in the same shape as honors.py. Needs Lahman csv files in scripts/sports/cache/raw/mlb
(People, Appearances, Teams) and scripts/sports-honors/cache (AwardsPlayers, AllstarFull, HallOfFame)."""
import csv, json, pathlib, re, collections, sys, unicodedata
HERE = pathlib.Path(__file__).parent
RAW = HERE.parent / "sports" / "cache" / "raw" / "mlb"
CACHE = HERE / "cache"

def fold(s):
    s = unicodedata.normalize("NFD", s); s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()

def rows(p): return list(csv.DictReader(open(p, encoding="utf-8-sig")))

people = rows(RAW / "People.csv")
by_name = collections.defaultdict(list)
for r in people:
    by_name[fold(f"{r['nameFirst']} {r['nameLast']}")].append(r)
    if r.get("nameGiven"): by_name[fold(f"{r['nameGiven']} {r['nameLast']}")].append(r)

pool = json.loads((HERE.parent / "sports" / "out" / "mlb.json").read_text())["players"]

ALIAS = {"goose gossage": "rich gossage"}

def pick(p):
    nm = fold(p["name"]); nm = ALIAS.get(nm, re.sub(r" (jr|sr|ii|iii)$", "", nm))
    cands = by_name.get(nm, [])
    if not cands: return None
    first = min(s[1] for s in p["st"]); last = max(s[2] for s in p["st"]) - 1
    def gap(r):
        try: d = int(r["debut"][:4])
        except Exception: return 999
        f = int(r["finalGame"][:4]) if r["finalGame"] else 2025
        return abs(d - first) + abs(f - last)
    return min(cands, key=gap)

award = collections.defaultdict(collections.Counter)
for r in rows(CACHE / "AwardsPlayers.csv"): award[r["playerID"]][r["awardID"]] += 1
allstar = collections.defaultdict(set)
for r in rows(CACHE / "AllstarFull.csv"): allstar[r["playerID"]].add(r["yearID"])
hof = {r["playerID"] for r in rows(CACHE / "HallOfFame.csv") if r["inducted"] == "Y" and r["category"] == "Player"}
champ = {(r["yearID"], r["teamID"]) for r in rows(RAW / "Teams.csv") if r.get("WSWin") == "Y"}
titles = collections.defaultdict(set)
for r in rows(RAW / "Appearances.csv"):
    if (r["yearID"], r["teamID"]) in champ: titles[r["playerID"]].add(r["yearID"])

W = {"Most Valuable Player": ("mvp", 6), "Cy Young Award": ("major", 4), "Rookie of the Year": ("minor", 1.5), "Gold Glove": ("minor", 0.7), "Silver Slugger": ("minor", 0.7),
     "World Series MVP": ("finalsmvp", 3), "NLCS MVP": ("minor", 1.5), "ALCS MVP": ("minor", 1.5), "Triple Crown": ("major", 3), "Pitching Triple Crown": ("major", 3),
     "Hank Aaron Award": ("minor", 1.5), "All-MLB Team - First Team": ("first", 2), "All-MLB Team - Second Team": ("second", 1), "Comeback Player of the Year": ("minor", 1),
     "Reliever of the Year Award": ("minor", 1.5)}
out = {}; miss = []
for p in pool:
    r = pick(p)
    if not r: out[p["name"]] = {"raw": {}, "cat": {}, "score": 0.0}; miss.append(p["name"]); continue
    pid = r["playerID"]; cat = collections.Counter(); score = 0.0
    def add(c, n, w):
        global score
        cat[c] += n; score += w * (n if n <= 6 else 6 + (n - 6) * 0.5)
    for a, n in award[pid].items():
        if a in W: c, w = W[a]; add(c, n, w)
    if allstar[pid]: add("allstar", len(allstar[pid]), 1)
    if titles[pid]: add("title", len(titles[pid]), 1.3)
    if pid in hof: cat["hof"] = 1; score += 5
    out[p["name"]] = {"raw": {"lahman": pid}, "cat": dict(cat), "score": round(score, 1)}
(HERE / "mlb.json").write_text(json.dumps(out, indent=0))
print("matched", len(pool) - len(miss), "of", len(pool), "unmatched:", miss)
for n in ["Willie Mays", "Albert Pujols", "Mike Trout", "Shohei Ohtani", "Babe Ruth", "Derek Jeter"]:
    if n in out: print(n, out[n]["score"], out[n]["cat"])
