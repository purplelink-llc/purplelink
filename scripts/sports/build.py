#!/usr/bin/env python3
"""Build the sports data file for one sport from the curated list + cached Wikipedia careers.
Usage: build.py nba   -> writes scripts/sports/out/<sport>.json and prints a QA report.
Seasons are integers (the year a season began). A stint [s, e) covers seasons s .. e-1."""
import json, pathlib, re, sys, collections
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import franchises
LAST_SEASON = 2025          # data is capped at the 2025-26 season; later moves are not trusted yet
EXCLUDE = ["quad city", "borås", "great danes", "austin spurs", "texas legends", "→", "g league", "raptors 905"]

def franchise_of(sport, label, s):
    t = label.lower().strip()
    if any(x in t for x in EXCLUDE): return None
    if sport == "nba" and "charlotte hornets" in t and "bobcats" not in t: return "NOP" if s < 2003 else "CHA"
    for fid, _, pats in getattr(franchises, sport.upper()):
        if any(p in t for p in pats): return fid
    return None

def load(sport):
    players = []
    cache = json.loads((HERE / "cache" / f"{sport}.json").read_text())
    career = json.loads((HERE / "cache" / f"{sport}-career.json").read_text())
    patches = json.loads((HERE / "patches" / f"{sport}.json").read_text()) if (HERE / "patches" / f"{sport}.json").exists() else {}
    for line in (HERE / f"{sport}-players.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"): continue
        name, pos, tier = [x.strip() for x in line.split("|")[:3]]
        raw = patches.get(name) or career.get(name) or []
        st = []
        for x in raw:
            f = franchise_of(sport, x["team"], x["s"]) if "f" not in x else x["f"]
            if not f: continue
            e = min(x["e"], LAST_SEASON + 1)
            if e <= x["s"]: continue
            st.append([f, x["s"], e])
        # merge touching stints on the same franchise
        st.sort(key=lambda a: (a[1], a[2]))
        merged = []
        for f, s, e in st:
            if merged and merged[-1][0] == f and s <= merged[-1][2]: merged[-1][2] = max(merged[-1][2], e)
            else: merged.append([f, s, e])
        players.append({"name": name, "pos": pos, "tier": int(tier), "qid": cache["players"][name]["qid"], "st": merged})
    return players

def graph(players):
    adj = collections.defaultdict(dict)
    for i, a in enumerate(players):
        for j in range(i + 1, len(players)):
            b = players[j]
            for fa, sa, ea in a["st"]:
                for fb, sb, eb in b["st"]:
                    if fa == fb and sa < eb and sb < ea:
                        adj[i].setdefault(j, (fa, max(sa, sb))); adj[j].setdefault(i, (fa, max(sa, sb)))
    return adj

def bfs(adj, src, n):
    d = {src: 0}; q = collections.deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in d: d[v] = d[u] + 1; q.append(v)
    return d

def main():
    sport = sys.argv[1]
    P = load(sport); adj = graph(P)
    idx = {p["name"]: i for i, p in enumerate(P)}
    print(len(P), "players")
    # QA
    for p in P:
        if not p["st"]: print("NO STINTS:", p["name"])
    iso = [P[i]["name"] for i in range(len(P)) if not adj[i]]
    print("isolated:", iso)
    dist_hist = collections.Counter(); far = []
    for i in range(len(P)):
        d = bfs(adj, i, len(P))
        for j, v in d.items():
            if j > i: dist_hist[v] += 1
        if len(d) < len(P) and len(d) > 1: print("UNREACHABLE from", P[i]["name"], len(P) - len(d))
        far.append(max(d.values()))
    print("distance histogram", sorted(dist_hist.items()), "max", max(far))
    def path(a, b):
        src, dst = idx[a], idx[b]; prev = {src: None}; q = collections.deque([src])
        while q:
            u = q.popleft()
            if u == dst: break
            for v in adj[u]:
                if v not in prev: prev[v] = u; q.append(v)
        if dst not in prev: return []
        out = []; u = dst
        while u is not None: out.append(P[u]["name"]); u = prev[u]
        return out[::-1]
    for a, b in [("Bill Russell", "Jaylen Brown"), ("LeBron James", "Cooper Flagg"), ("Bill Russell", "Cooper Flagg"), ("George Mikan", "Victor Wembanyama")]:
        if a in idx and b in idx: print(a, "->", b, path(a, b))
    out = HERE / "out"; out.mkdir(exist_ok=True)
    used = {f for p in P for f, _, _ in p["st"]}
    fr = {fid: name for fid, name, _ in getattr(franchises, sport.upper()) if fid in used}
    (out / f"{sport}.json").write_text(json.dumps({"sport": sport, "franchises": fr, "players": P}, separators=(",", ":")))
if __name__ == "__main__": main()
