#!/usr/bin/env python3
"""Turn scripts/sports/out/<sport>.json into the data files the sports games read, and pick the daily puzzles.
Writes site/games/data/sports-<sport>.json and site/games/data/sports-index.json.

Daily puzzles are pinned: scripts/sports-pinned/<sport>.json keeps every puzzle ever issued and this script only
appends, so a day that is already live never changes when the player pool grows."""
import collections, hashlib, json, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "sports" / "out"
PIN = ROOT / "scripts" / "sports-pinned"
DATA = ROOT / "site" / "games" / "data"
EPOCH_DOW = 0                       # the games epoch (2026-10-04) is a Sunday; JS getDay() = 0
DAYS = 420                          # daily puzzles per sport kept ahead of today
ORDER = ["nba", "nfl", "mlb", "nhl"]

CFG = {
    "nba": dict(name="NBA", plural="basketball players", slots=["G", "G", "F", "F", "C"], bench=3, cap=32, games=82, scale=4.0, base=80, teams=30, rounds=[7, 7, 7, 7], era=1990, split=True,
                groups={"PG": "G", "SG": "G", "SF": "F", "PF": "F", "C": "C"}, gname={"G": "Guard", "F": "Forward", "C": "Center"}),
    "nfl": dict(name="NFL", plural="football players", slots=["QB", "RB", "WR", "WR", "TE", "OL", "DL", "DL", "LB", "DB", "DB"], bench=2, cap=36, games=17, scale=5.0, base=80, teams=32, rounds=[1, 1, 1], era=1990,
                groups={k: k for k in ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"]}, gname={"QB": "Quarterback", "RB": "Running back", "WR": "Receiver", "TE": "Tight end", "OL": "Lineman", "DL": "Defensive line", "LB": "Linebacker", "DB": "Defensive back"}),
    "mlb": dict(name="MLB", plural="baseball players", slots=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "SP", "SP", "SP", "RP"], bench=2, cap=42, games=162, scale=9.0, base=80, teams=30, rounds=[5, 7, 7], era=1980,
                groups={"C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS", "LF": "OF", "CF": "OF", "RF": "OF", "SP": "SP", "RP": "RP"}, gname={"C": "Catcher", "1B": "First baseman", "2B": "Second baseman", "3B": "Third baseman", "SS": "Shortstop", "OF": "Outfielder", "SP": "Starting pitcher", "RP": "Reliever"}),
    "nhl": dict(name="NHL", plural="hockey players", slots=["C", "C", "W", "W", "D", "D", "G"], bench=3, cap=34, games=82, scale=6.0, base=80, teams=32, rounds=[7, 7, 7, 7], era=1990, split=True,
                groups={"C": "C", "LW": "W", "RW": "W", "D": "D", "G": "G"}, gname={"C": "Center", "W": "Winger", "D": "Defenseman", "G": "Goalie"}),
}
BASE_OVR = {5: 96, 4: 89, 3: 82, 2: 75, 1: 68}


def ovr(name, tier):
    h = int(hashlib.md5(name.encode()).hexdigest()[:4], 16)
    return BASE_OVR[tier] + (h % 5) - 2


def load(sport):
    d = json.loads((OUT / f"{sport}.json").read_text())
    cfg = CFG[sport]
    P = []
    for p in sorted(d["players"], key=lambda x: x["name"]):
        if not p["st"]: continue
        P.append({"n": p["name"], "p": p["pos"], "g": cfg["groups"].get(p["pos"], p["pos"]), "t": p["tier"], "o": ovr(p["name"], p["tier"]), "s": p["st"]})
    return d["franchises"], P


def adjacency(P):
    adj = collections.defaultdict(set)
    for i, a in enumerate(P):
        for j in range(i + 1, len(P)):
            b = P[j]
            if any(fa == fb and sa < eb and sb < ea for fa, sa, ea in a["s"] for fb, sb, eb in b["s"]):
                adj[i].add(j); adj[j].add(i)
    return adj


def bfs(adj, src):
    d = {src: 0}; q = collections.deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in d: d[v] = d[u] + 1; q.append(v)
    return d


# ---- criteria (mirrors criteria() in site/games/sports.js) ----
def crit_ok(c, p):
    k, v = c.split(":")
    if k == "t": return any(f == v for f, _, _ in p["s"])
    if k == "p": return p["g"] == v
    if k == "d":
        y = int(v); return any(s < y + 10 and e > y for _, s, e in p["s"])
    if k == "n": return len({f for f, _, _ in p["s"]}) >= int(v)
    if k == "y": return sum(e - s for _, s, e in p["s"]) >= int(v)
    if k == "o": return len({f for f, _, _ in p["s"]}) == 1
    return False


def pick_pairs(P, adj, sport, existing):
    famous = [i for i, p in enumerate(P) if p["t"] >= 3]
    dist = {i: bfs(adj, i) for i in famous}
    pairs_by = collections.defaultdict(list)
    for a in famous:
        for b in famous:
            if a < b and b in dist[a]: pairs_by[dist[a][b]].append((a, b))
    want = {1: 2, 2: 3, 3: 3, 4: 4, 5: 4, 6: 5, 0: 6}        # JS getDay(): Mon..Sun
    out = list(existing)
    rng = random.Random(f"tl-{sport}")
    for _ in range(len(existing)): rng.random()
    idx = {p["n"]: i for i, p in enumerate(P)}
    recent = collections.deque([], 40)
    for n in out[-40:]:
        recent.extend(n)
    order = ORDERS = [s for s in ORDER if (OUT / f"{s}.json").exists()]
    k = order.index(sport)
    for day in range(len(existing), DAYS):
        dd = day * len(order) + k
        par = want[(EPOCH_DOW + dd) % 7]
        pool = pairs_by.get(par) or pairs_by.get(par - 1) or pairs_by.get(par + 1) or []
        for _ in range(400):
            a, b = rng.choice(pool)
            if rng.random() < .5: a, b = b, a
            if P[a]["n"] not in recent and P[b]["n"] not in recent: break
        recent.extend([P[a]["n"], P[b]["n"]])
        out.append([P[a]["n"], P[b]["n"]])
    return out


def pick_grids(P, F, sport, existing):
    cfg = CFG[sport]
    teams = [f for f in F if sum(1 for p in P if any(x[0] == f for x in p["s"])) >= 7]
    groups = sorted(set(cfg["groups"].values()))
    decades = [d for d in range(1950, 2030, 10) if sum(1 for p in P if crit_ok(f"d:{d}", p)) >= 12]
    extra = [f"n:4", "y:15", "o:1"] + [f"p:{g}" for g in groups] + [f"d:{d}" for d in decades]
    rng = random.Random(f"gr-{sport}")
    for _ in range(len(existing)): rng.random()
    out = list(existing)
    def ok_cell(a, b, mn):
        return sum(1 for p in P if crit_ok(a, p) and crit_ok(b, p)) >= mn
    tries = 0
    while len(out) < DAYS and tries < 400000:
        tries += 1
        rows = [f"t:{t}" for t in rng.sample(teams, 3)]
        mix = rng.random()
        if mix < .45: cols = [f"t:{t}" for t in rng.sample([t for t in teams if f"t:{t}" not in rows], 3)]
        elif mix < .8: cols = rng.sample(extra, 3)
        else: cols = [f"t:{rng.choice([t for t in teams if f't:{t}' not in rows])}"] + rng.sample(extra, 2)
        if len(set(cols)) < 3: continue
        # no two columns of the same kind unless they are teams or decades (keeps cells meaningful)
        kinds = [c[0] for c in cols]
        if kinds.count("p") > 1 or kinds.count("n") + kinds.count("y") + kinds.count("o") > 1: continue
        if not all(ok_cell(r, c, 2) for r in rows for c in cols): continue
        key = rows + cols
        if any(key == g["r"] + g["c"] for g in out): continue
        out.append({"r": rows, "c": cols})
    return out


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    present = [s for s in ORDER if (OUT / f"{s}.json").exists()]
    for sport in present:
        F, P = load(sport)
        adj = adjacency(P)
        pin_f = PIN / f"{sport}.json"
        pin = json.loads(pin_f.read_text()) if pin_f.exists() else {"tl": [], "gr": []}
        names = {p["n"] for p in P}
        lost = [n for pr in pin["tl"] for n in pr if n not in names]
        if lost: print(sport, "WARNING pinned players missing from pool:", sorted(set(lost)))
        pin["tl"] = pick_pairs(P, adj, sport, pin["tl"])
        pin["gr"] = pick_grids(P, F, sport, pin["gr"])
        pin_f.write_text(json.dumps(pin, separators=(",", ":")))
        cfg = CFG[sport]
        data = {"sport": sport, "name": cfg["name"], "fr": F, "cfg": {k: cfg[k] for k in ("slots", "bench", "cap", "games", "scale", "base", "gname", "plural", "teams", "rounds", "era") if k in cfg} | {"split": bool(cfg.get("split"))},
                "p": [[p["n"], p["p"], p["t"], p["o"], p["s"]] for p in P], "tl": pin["tl"], "gr": pin["gr"]}
        (DATA / f"sports-{sport}.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        print(sport, len(P), "players", len(pin["tl"]), "link days", len(pin["gr"]), "grids", (DATA / f"sports-{sport}.json").stat().st_size // 1024, "KB")
    (DATA / "sports-index.json").write_text(json.dumps({"rotation": present}, separators=(",", ":")))


if __name__ == "__main__":
    main()
