#!/usr/bin/env python3
"""Notable teammate chains between the biggest stars of different eras, for the static 'how are they connected' pages.
Writes scripts/sports-degrees/<sport>.json. Needs scripts/sports/out and scripts/sports/all (see gen_sports.py)."""
import json, pathlib, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_sports as G

OUT = pathlib.Path(__file__).resolve().parent / "sports-degrees"


def build(sport):
    F, P = G.load(sport); extra, _ = G.load_extra(sport, P)
    stints = G.combined(P, extra); bk = G.make_buckets(stints)
    stars = sorted([i for i, p in enumerate(P) if p["t"] >= 4], key=lambda i: -P[i]["o"])[:45]
    first = lambda i: min(x[1] for x in P[i]["s"])
    dist = {i: G.full_bfs(stints, bk, i) for i in stars}
    pairs = []
    for a in stars:
        for b in stars:
            if a < b and b in dist[a]:
                gap = abs(first(a) - first(b))
                pairs.append((a, b, dist[a][b], gap))
    allD = [d for _, _, d, _ in pairs]
    # the pairs worth showing: far apart in time and iconic; each star appears at most twice
    ranked = sorted(pairs, key=lambda x: -(x[3] * 1.0 + P[x[0]]["o"] + P[x[1]]["o"] + 3 * x[2]))
    use = collections.Counter(); chosen = []
    for a, b, d, gap in ranked:
        if gap < 20 or use[a] >= 2 or use[b] >= 2: continue
        use[a] += 1; use[b] += 1; chosen.append((a, b, d, gap))
        if len(chosen) == 24: break
    names = [(P[a]["n"], P[b]["n"]) for a, b, _, _ in chosen]
    chains = G.chains_for(P, extra, [list(x) for x in names])
    rows = []
    for (a, b, d, gap), ch in zip(chosen, chains):
        rows.append({"a": P[a]["n"], "b": P[b]["n"], "links": d, "gap": gap, "c": ch["c"], "h": ch["h"]})
    return {"sport": sport, "name": G.CFG[sport]["name"], "players": len(P) + len(extra), "stars": len(stars),
            "avg": round(sum(allD) / len(allD), 2), "max": max(allD), "dist": sorted(collections.Counter(allD).items()),
            "first": min(first(i) for i in range(len(P))), "fr": F, "fs": G.SHORT.get(sport, {}), "split": bool(G.CFG[sport].get("split")), "rows": rows}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for sport in (sys.argv[1:] or G.ORDER):
        d = build(sport); (OUT / f"{sport}.json").write_text(json.dumps(d, ensure_ascii=False, indent=0))
        print(sport, d["players"], "players;", len(d["rows"]), "chains; avg", d["avg"], "max", d["max"], d["rows"][0]["a"], "to", d["rows"][0]["b"], d["rows"][0]["links"])
