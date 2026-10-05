#!/usr/bin/env python3
"""Turn scripts/sports/out/<sport>.json into the data files the sports games read, and pick the daily puzzles.
Writes site/games/data/sports-<sport>.json and site/games/data/sports-index.json.

Daily puzzles are pinned: scripts/sports-pinned/<sport>.json keeps every puzzle ever issued and this script only
appends, so a day that is already live never changes when the player pool grows."""
import collections, hashlib, json, math, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "sports" / "out"
PIN = ROOT / "scripts" / "sports-pinned"
DATA = ROOT / "site" / "games" / "data"
EPOCH_DOW = 0                       # the games epoch (2026-10-04) is a Sunday; JS getDay() = 0
DAYS = 420                          # daily puzzles per sport kept ahead of today
ORDER = ["nba", "nfl", "mlb", "nhl"]
DAYS_LIB = {}
WANT = {s: {1: 2, 2: 3, 3: 3, 4: 4, 5: 4, 6: 5, 0: 6} for s in ORDER}     # target chain length (par) by weekday, JS getDay()
SHORT = {"nhl": {"UTA": "Coyotes", "CLB": "Seals/Barons"}}
FULL = {"nhl": {"UTA": "Winnipeg Jets / Arizona Coyotes / Utah Mammoth"}}

CFG = {
    "nba": dict(name="NBA", plural="basketball players", slots=["G", "G", "F", "F", "C"], bench=3, cap=28, games=82, scale=4.0, base=80, teams=30, rounds=[7, 7, 7, 7], era=1990, split=True,
                groups={"PG": "G", "SG": "G", "SF": "F", "PF": "F", "C": "C"}, gname={"G": "Guard", "F": "Forward", "C": "Center"}),
    "nfl": dict(name="NFL", plural="football players", slots=["QB", "RB", "WR", "WR", "TE", "OL", "DL", "DL", "LB", "DB", "DB"], bench=2, cap=36, games=17, scale=5.0, base=80, teams=32, rounds=[1, 1, 1], era=1990,
                groups={k: k for k in ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"]}, gname={"QB": "Quarterback", "RB": "Running back", "WR": "Receiver", "TE": "Tight end", "OL": "Lineman", "DL": "Defensive line", "LB": "Linebacker", "DB": "Defensive back"}),
    "mlb": dict(name="MLB", plural="baseball players", slots=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "SP", "SP", "SP", "RP"], bench=2, cap=42, games=162, scale=7.0, base=80, teams=30, rounds=[5, 7, 7], era=1980,
                groups={"C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS", "LF": "OF", "CF": "OF", "RF": "OF", "SP": "SP", "RP": "RP"}, gname={"C": "Catcher", "1B": "First baseman", "2B": "Second baseman", "3B": "Third baseman", "SS": "Shortstop", "OF": "Outfielder", "SP": "Starting pitcher", "RP": "Reliever"}),
    "nhl": dict(name="NHL", plural="hockey players", slots=["C", "C", "W", "W", "D", "D", "G"], bench=3, cap=34, games=82, scale=5.0, base=80, teams=32, rounds=[7, 7, 7, 7], era=1990, split=True,
                groups={"C": "C", "LW": "W", "RW": "W", "D": "D", "G": "G"}, gname={"C": "Center", "W": "Winger", "D": "Defenseman", "G": "Goalie"}),
}
BASE_OVR = {5: 96, 4: 89, 3: 82, 2: 75, 1: 68}


HONORS = ROOT / "scripts" / "sports-honors"
HK = {"nba": 40, "nfl": 30, "mlb": 25, "nhl": 32}     # honors points at which the honors rating reaches about two thirds of its range
SELNAME = {"nba": "All-Star", "nfl": "Pro Bowl", "mlb": "All-Star", "nhl": "All-NHL team"}
WEIGHT = 0.6                                           # share of the rating that comes from career honors, the rest from our tier


def rating(sport, name, tier, hon):
    """Half-and-more from career honors (counted from Lahman, Wikipedia and its award lists), the rest from our tier of
    how good the player was at his best. With no honors on record the tier alone decides."""
    base = BASE_OVR[tier]
    if not hon or (hon["score"] == 0 and not hon["cat"]): return base
    honors = 62 + 36 * (1 - math.exp(-hon["score"] / HK[sport]))
    return round(WEIGHT * honors + (1 - WEIGHT) * base)


def summary(sport, hon):
    """[selections, MVPs, titles, hall of fame] shown beside each player in Unbeaten."""
    if not hon: return [0, 0, 0, 0]
    c = hon["cat"]
    return [c.get("allstar") or c.get("first", 0), c.get("mvp", 0), c.get("title", 0), 1 if c.get("hof") else 0]


def load(sport):
    d = json.loads((OUT / f"{sport}.json").read_text())
    cfg = CFG[sport]
    hf = HONORS / f"{sport}.json"
    honors = json.loads(hf.read_text()) if hf.exists() else {}
    P = []
    for p in sorted(d["players"], key=lambda x: x["name"]):
        if not p["st"]: continue
        hon = honors.get(p["name"])
        P.append({"n": p["name"], "p": p["pos"], "g": cfg["groups"].get(p["pos"], p["pos"]), "t": p["tier"], "o": rating(sport, p["name"], p["tier"], hon), "s": p["st"], "h": summary(sport, hon)})
    return d["franchises"], P


ALL = ROOT / "scripts" / "sports" / "all"


def load_extra(sport, P):
    if not os.environ.get("SPORTS_EXTRAS"): return [], ""
    """Players outside the famous pool, from scripts/sports/all/<sport>.json. Returns rows [name, pos, born, stints]
    with names made unique, plus the credit text."""
    f = ALL / f"{sport}.json"
    if not f.exists(): return [], ""
    d = json.loads(f.read_text())
    taken = {p["n"] for p in P}
    famous = {p["famous"] for p in d["players"] if p.get("famous")}
    rows = []
    for p in sorted(d["players"], key=lambda x: (x["name"], x.get("born") or 0, x["id"])):
        if p.get("famous") in taken or not p["st"]: continue
        name = p["name"]
        if name in taken:
            tag = p.get("born") or p["st"][0][1]
            name = f"{name} ({tag})"
            n = 2
            while name in taken: name = f"{p['name']} ({tag}-{n})"; n += 1
        taken.add(name)
        st = sorted([[a, b, c] for a, b, c in p["st"] if c > b])
        rows.append([name, p.get("pos") or "", p.get("born") or 0, st])
    return rows, d.get("source", "")


def combined(P, extra):
    """Everyone as stint lists, for distances over the whole database."""
    return [p["s"] for p in P] + [r[3] for r in extra]


def full_bfs(stints, buckets, src):
    dist = {src: 0}; q = collections.deque([src])
    while q:
        u = q.popleft()
        for f, s, e in stints[u]:
            for y in range(s, e):
                for v in buckets.get((f, y), ()):
                    if v not in dist: dist[v] = dist[u] + 1; q.append(v)
    return dist


def make_buckets(stints):
    bk = collections.defaultdict(list)
    for i, st in enumerate(stints):
        for f, s, e in st:
            for y in range(s, e): bk[(f, y)].append(i)
    return bk


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
    if k == "a":
        h = p["h"]
        return {"mvp": h[1] >= 1, "title": h[2] >= 1, "sel5": h[0] >= 5, "hof": h[3] >= 1}[v]
    if k == "m": return p["n"] in MATES.get(v, ())
    return False


MATES = {}                 # star name -> names of everyone who shared a franchise and season with him


def teammates_of(P, star):
    out = set()
    for p in P:
        if p["n"] != star["n"] and any(fa == fb and sa < eb and sb < ea for fa, sa, ea in p["s"] for fb, sb, eb in star["s"]): out.add(p["n"])
    return out


def pars_for(P, extra, pairs):
    """Shortest chain length for each daily pair over everyone in the database."""
    stints = combined(P, extra); bk = make_buckets(stints); idx = {p["n"]: i for i, p in enumerate(P)}
    out = []
    for a, b in pairs:
        out.append(full_bfs(stints, bk, idx[a]).get(idx[b], 0))
    return out


def pick_pairs(P, extra, sport, existing):
    famous = [i for i, p in enumerate(P) if p["t"] >= 3]
    stints = combined(P, extra); bk = make_buckets(stints)
    dist = {i: full_bfs(stints, bk, i) for i in famous}
    pairs_by = collections.defaultdict(list)
    for a in famous:
        for b in famous:
            if a < b and b in dist[a]: pairs_by[dist[a][b]].append((a, b))
    want = WANT[sport]            # JS getDay(): Mon..Sun
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


def kinds_m(cols): return len([c for c in cols if c[0] == 'm'])


def pick_grids(P, F, sport, existing):
    cfg = CFG[sport]
    teams = [f for f in F if sum(1 for p in P if any(x[0] == f for x in p["s"])) >= 7]
    groups = sorted(set(cfg["groups"].values()))
    decades = [d for d in range(1950, 2030, 10) if sum(1 for p in P if crit_ok(f"d:{d}", p)) >= 12]
    stars = sorted([p for p in P if p["t"] == 5], key=lambda p: -p["o"])[:14]
    for st_ in stars: MATES[st_["n"]] = teammates_of(P, st_)
    awards = [f"a:{a}" for a in ("mvp", "title", "sel5", "hof") if sum(1 for p in P if crit_ok(f"a:{a}", p)) >= 12]
    extra = [f"n:4", "y:15", "o:1"] + [f"p:{g}" for g in groups] + [f"d:{d}" for d in decades] + awards * 2 + [f"m:{p['n']}" for p in stars if len(MATES[p['n']]) >= 12] * 3
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
        if len({c for c in cols if c[0] == 'm'}) != kinds_m(cols): continue
        # no two columns of the same kind unless they are teams or decades (keeps cells meaningful)
        kinds = [c[0] for c in cols]
        if kinds.count("p") > 1 or kinds.count("n") + kinds.count("y") + kinds.count("o") > 1 or kinds.count("a") > 2 or kinds.count("m") > 1: continue
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
        extra, credit = load_extra(sport, P)
        pin_f = PIN / f"{sport}.json"
        pin = json.loads(pin_f.read_text()) if pin_f.exists() else {"tl": [], "gr": []}
        names = {p["n"] for p in P}
        lost = [n for pr in pin["tl"] for n in pr if n not in names]
        if lost: print(sport, "WARNING pinned players missing from pool:", sorted(set(lost)))
        pin["tl"] = pick_pairs(P, extra, sport, pin["tl"])
        pin["gr"] = pick_grids(P, F, sport, pin["gr"])
        pin_f.write_text(json.dumps(pin, separators=(",", ":")))
        cfg = CFG[sport]
        F = {k: FULL.get(sport, {}).get(k, v) for k, v in F.items()}
        pars = pars_for(P, extra, pin["tl"])
        DAYS_LIB[sport] = {"par": pars, "games": cfg["games"]}
        data = {"sport": sport, "name": cfg["name"], "fr": F, "fs": SHORT.get(sport, {}), "cfg": {k: cfg[k] for k in ("slots", "bench", "cap", "games", "scale", "base", "gname", "plural", "teams", "rounds", "era") if k in cfg} | {"split": bool(cfg.get("split")), "selname": SELNAME[sport]},
                "p": [[p["n"], p["p"], p["t"], p["o"], p["s"], p["h"]] for p in P], "tl": pin["tl"], "tp": pars, "gr": pin["gr"]}
        (DATA / f"sports-{sport}.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        if extra:
            (DATA / f"sports-{sport}-all.json").write_text(json.dumps({"credit": credit, "p": extra}, separators=(",", ":"), ensure_ascii=False))
        print(sport, len(P), "famous +", len(extra), "others,", len(pin["tl"]), "link days", len(pin["gr"]), "grids", (DATA / f"sports-{sport}.json").stat().st_size // 1024, "KB")
    (DATA / "sports-index.json").write_text(json.dumps({"rotation": present}, separators=(",", ":")))
    # the rating service needs the day's expected chain length and season length; it never sees the puzzles themselves
    lib = ROOT / "netlify" / "lib" / "sports-days.json"
    lib.write_text(json.dumps({"rotation": present, **DAYS_LIB}, separators=(",", ":")))


if __name__ == "__main__":
    main()
