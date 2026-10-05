#!/usr/bin/env python3
"""Resolve curated player names to Wikidata QIDs and fetch team stints. Usage: resolve.py nba|nfl|mlb|nhl
Caches in scripts/sports/cache/<sport>.json. Uses curl (python urllib has SSL trouble here)."""
import json, subprocess, sys, time, urllib.parse, pathlib, re
HERE = pathlib.Path(__file__).parent
UA = "PurplelinkGames/1.0 (ben@purplelink.llc)"
SPORT_WORDS = {
  "nba": ["basketball"], "nfl": ["american football", "national football league", "nfl", "gridiron"],
  "mlb": ["baseball"], "nhl": ["ice hockey", "hockey player", "national hockey league", "nhl"],
}
def curl(args):
    for i in range(4):
        r = subprocess.run(["curl", "-s", "--max-time", "60", "-A", UA] + args, capture_output=True, text=True)
        if r.stdout.strip().startswith(("{", "[")):
            try: return json.loads(r.stdout)
            except Exception: pass
        time.sleep(2 + 3 * i)
    return None
def search(name, sport):
    q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en", "limit": 30, "format": "json", "type": "item"})
    d = curl(["https://www.wikidata.org/w/api.php?" + q])
    if not d: return None
    words = SPORT_WORDS[sport]
    for c in d.get("search", []):
        desc = (c.get("description") or "").lower()
        if desc.startswith(("college", "high school")) or "wheelchair" in desc or "women" in desc or "field hockey" in desc or "soccer" in desc or "association football" in desc: continue
        if any(w in desc for w in words):
            return {"qid": c["id"], "label": c.get("label"), "desc": c.get("description")}
    return None
def wp_fallback(name, sport):
    """No Wikidata description matched: try the English Wikipedia article of that name (and sport-qualified variants)."""
    suffix = {"nfl": "American football", "mlb": "baseball", "nhl": "ice hockey", "nba": "basketball"}[sport]
    titles = [name, "%s (%s)" % (name, suffix)]
    q = urllib.parse.urlencode({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "titles": "|".join(titles), "redirects": 1, "format": "json"})
    d = curl(["https://en.wikipedia.org/w/api.php?" + q])
    if not d: return None
    for p in d.get("query", {}).get("pages", {}).values():
        qid = p.get("pageprops", {}).get("wikibase_item")
        if qid: return {"qid": qid, "label": name, "desc": "FALLBACK " + p["title"]}
    return None
def stints(qids):
    vals = " ".join("wd:" + q for q in qids)
    sparql = """SELECT ?p ?team ?teamLabel ?s ?e WHERE { VALUES ?p { %s } ?p p:P54 ?st . ?st ps:P54 ?team . OPTIONAL{?st pq:P580 ?s} OPTIONAL{?st pq:P582 ?e} SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }""" % vals
    d = curl(["-X", "POST", "https://query.wikidata.org/sparql", "-H", "Accept: application/sparql-results+json", "--data-urlencode", "query=" + sparql])
    if not d: return None
    out = []
    for b in d["results"]["bindings"]:
        g = lambda k: b.get(k, {}).get("value")
        out.append({"p": g("p").split("/")[-1], "team": g("teamLabel"), "tq": g("team").split("/")[-1], "s": (g("s") or "")[:4], "e": (g("e") or "")[:4]})
    return out
def main():
    sport = sys.argv[1]
    src = HERE / f"{sport}-players.txt"
    cache_f = HERE / "cache" / f"{sport}.json"
    cache_f.parent.mkdir(exist_ok=True)
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {"players": {}, "stints": {}}
    rows = []
    for line in src.read_text().splitlines():
        if not line.strip() or line.startswith("#"): continue
        parts = [x.strip() for x in line.split("|")]
        rows.append(parts)
    for parts in rows:
        name = parts[0]
        qid_override = parts[4] if len(parts) > 4 and parts[4] else None
        if name in cache["players"] and cache["players"][name]: continue
        r = {"qid": qid_override, "label": name} if qid_override else (search(name, sport) or wp_fallback(name, sport))
        cache["players"][name] = r
        if not r: print("UNRESOLVED", name)
        time.sleep(0.15)
    cache_f.write_text(json.dumps(cache))
    need = [r["qid"] for r in cache["players"].values() if r and r["qid"] not in cache["stints"]]
    for i in range(0, len(need), 12):
        chunk = need[i:i+12]
        res = stints(chunk)
        if res is None: print("stint chunk failed", chunk); continue
        for q in chunk: cache["stints"][q] = []
        for x in res: cache["stints"][x["p"]].append(x)
        cache_f.write_text(json.dumps(cache))
        print("stints", i + len(chunk), "/", len(need), flush=True)
        time.sleep(1)
if __name__ == "__main__": main()
