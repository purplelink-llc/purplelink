#!/usr/bin/env python3
"""Coverage / identity / distance report for all/<sport>.json.  Usage: all_report.py nba|nfl|mlb|nhl [spotcheck-seed]
Prints: counts and first-season decade histogram, famous-pool agreement stats + 15 spot checks, 10 non-famous role players,
and shortest-path lengths between famous pairs using ONLY the all-players database (vs the famous-pool-only path)."""
import json, sys, random, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_common import *
import build
ROLE = {
 "nba": ["Robert Horry", "Derek Fisher", "Steve Kerr", "Udonis Haslem", "Brian Scalabrine", "Luc Longley", "John Salley", "Danny Green", "Shane Battier", "Boris Diaw"],
 "nfl": ["Troy Brown", "Jeff Saturday", "Brad Meester", "Mike Alstott", "Kevin Mawae", "Jason Sehorn", "Matt Hasselbeck", "Ken Norton Jr.", "Olindo Mare", "Heath Miller"],
 "mlb": ["Mike Lowell", "Jason Varitek", "Tim Wakefield", "Kevin Millar", "Jeff Conine", "Brad Ausmus", "Dave Roberts", "Doug Mirabelli", "Bill Mueller", "Mark Loretta"],
 "nhl": ["Kirk Maltby", "Darren McCarty", "Bob Probert", "Dave Andreychuk", "Jere Lehtinen", "Kris Draper", "Brian Rolston", "Mike Sillinger", "Todd Marchant", "Sergei Gonchar"],
}
PAIRS = {  # famous pairs for the distance demo (names as in the famous pool)
 "nba": [("Bill Russell", "Jaylen Brown"), ("LeBron James", "Cooper Flagg"), ("Bill Russell", "Cooper Flagg"), ("George Mikan", "Victor Wembanyama"), ("Michael Jordan", "Luka Doncic")],
 "nfl": [("Johnny Unitas", "Patrick Mahomes"), ("Jim Brown", "Josh Allen"), ("Joe Namath", "Justin Jefferson"), ("Otto Graham", "Caleb Williams"), ("Tom Brady", "Joe Montana")],
 "mlb": [("Willie Mays", "Shohei Ohtani"), ("Hank Aaron", "Aaron Judge"), ("Sandy Koufax", "Paul Skenes"), ("Babe Ruth", "Mike Trout"), ("Ted Williams", "Juan Soto")],
 "nhl": [("Gordie Howe", "Connor McDavid"), ("Bobby Orr", "Auston Matthews"), ("Wayne Gretzky", "Nathan MacKinnon"), ("Maurice Richard", "Macklin Celebrini"), ("Mario Lemieux", "Connor Bedard")],
}
def buckets(players):
    B = collections.defaultdict(list)
    for i, p in enumerate(players):
        for f, s, e in p["st"]:
            for y in range(s, e): B[(f, y)].append(i)
    return B
def bfs(players, B, src, dst):
    """Shortest number of links (shared franchise + overlapping season) between two player indices; path via bucket labels."""
    if src == dst: return 0, [players[src]["name"]]
    dist = {src: 0}; prev = {src: None}; seen_b = set(); q = collections.deque([src])
    while q:
        u = q.popleft()
        for f, s, e in players[u]["st"]:
            for y in range(s, e):
                if (f, y) in seen_b: continue
                seen_b.add((f, y))
                for v in B[(f, y)]:
                    if v not in dist:
                        dist[v] = dist[u] + 1; prev[v] = (u, "%s %d" % (f, y)); q.append(v)
                        if v == dst:
                            path = []; x = v
                            while prev[x]: path.append((players[x]["name"], prev[x][1])); x = prev[x][0]
                            return dist[v], [players[src]["name"]] + [("%s [%s]" % (n, lab)) for n, lab in path[::-1]]
    return None, []
def main():
    sport = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    D = json.loads((ALL / f"{sport}.json").read_text()); P = D["players"]
    print("=" * 78); print(sport.upper(), "| source:", D["source"][:110]); print("licence:", D["license"][:110])
    print("players:", len(P), "| with birth year:", sum(1 for p in P if p["born"]), "| with position:", sum(1 for p in P if p["pos"]),
          "| stints/player: %.2f" % (sum(len(p["st"]) for p in P) / len(P)), "| player-seasons:", sum(season_cells(p["st"]) for p in P))
    dec = collections.Counter((p["st"][0][1] // 10) * 10 for p in P)
    print("by decade of first season:", " ".join("%ds:%d" % (d, dec[d]) for d in sorted(dec)))
    ids = collections.Counter(p["id"] for p in P); print("duplicate ids:", sum(1 for v in ids.values() if v > 1))
    # coverage per season: players per season overall
    ps = collections.Counter(); 
    for p in P:
        for f, s, e in p["st"]:
            for y in range(s, e): ps[y] += 1
    yrs = sorted(ps); print("distinct player-rows per season (every 10th):", " ".join("%d:%d" % (y, ps[y]) for y in yrs[::10]), "last %d:%d" % (yrs[-1], ps[yrs[-1]]))
    # famous agreement
    F = {p["name"]: p for p in famous_pool(sport)}
    A = {p["famous"]: p for p in P if p.get("famous")}
    miss = [n for n in F if n not in A]; print("famous pool: %d, matched %d, unmatched %s" % (len(F), len(A), miss))
    same_fr = 0; jacc = []; sub = 0; bad = []
    for n, fp in F.items():
        ap = A.get(n)
        if not ap: continue
        ff = {f for f, _, _ in fp["st"]}; af = {f for f, _, _ in ap["st"]}
        a_cells = {(f, y) for f, s, e in ap["st"] for y in range(s, e)}; f_cells = {(f, y) for f, s, e in fp["st"] for y in range(s, e)}
        j = len(a_cells & f_cells) / max(1, len(a_cells | f_cells)); jacc.append(j)
        if ff == af: same_fr += 1
        if f_cells <= a_cells: sub += 1
        if j < 0.8: bad.append((j, n))
    print("famous vs all-db: identical franchise sets %d/%d; every famous (franchise,season) present in all-db %d/%d; mean season-cell Jaccard %.3f; Jaccard<0.8: %d"
          % (same_fr, len(A), sub, len(A), sum(jacc) / len(jacc), len(bad)))
    print("  lowest agreement:", [(n, round(j, 2)) for j, n in sorted(bad)[:12]])
    rnd = random.Random(seed); names = sorted(A)
    print("\n-- 15 famous spot checks (famous | all-db), seasons inclusive --")
    for n in rnd.sample(names, min(15, len(names))):
        print(" %-22s F: %s\n %-22s A: %s  [%s, b.%s, id %s]" % (n, fmt_st(F[n]["st"]), "", fmt_st(A[n]["st"]), A[n]["pos"], A[n]["born"], A[n]["id"]))
    print("\n-- 10 non-famous role players --")
    byname = collections.defaultdict(list)
    for p in P: byname[norm_name(p["name"])].append(p)
    for n in ROLE[sport]:
        c = byname.get(norm_name(n), [])
        if not c: print(" %-18s NOT FOUND" % n); continue
        for p in c: print(" %-18s %s  [%s, b.%s, famous=%s]" % (n, fmt_st(p["st"]), p["pos"], p["born"], p.get("famous")))
    print("\n-- shortest paths (links = shared franchise + overlapping season) --")
    B = buckets(P); idx = {p["famous"]: i for i, p in enumerate(P) if p.get("famous")}
    Fp = list(F.values()); Fadj = build.graph(Fp); fidx = {p["name"]: i for i, p in enumerate(Fp)}
    for a, b in PAIRS[sport]:
        if a not in idx or b not in idx: print(" skip", a, b, "(not in pool/db)"); continue
        d, path = bfs(P, B, idx[a], idx[b])
        fd = build.bfs(Fadj, fidx[a], len(Fp)).get(fidx[b])
        print(" %s -> %s: all-db %s links | famous-pool-only %s links" % (a, b, d, fd))
        print("     ", " -> ".join(path))
if __name__ == "__main__": main()
