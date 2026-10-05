#!/usr/bin/env python3
"""Shared helpers for the all-players pipelines (all_mlb.py, all_nhl.py, all_nba.py, all_nfl.py).
Season convention (same as out/<sport>.json): a stint [s, e) covers seasons s..e-1; a season is identified by the calendar
year it STARTED. Franchise ids come from franchises.py."""
import json, pathlib, re, subprocess, sys, time, unicodedata, collections
HERE = pathlib.Path(__file__).parent
RAW = HERE / "cache" / "raw"
ALL = HERE / "all"
UA = "PurplelinkGames/1.0 (ben@purplelink.llc)"
LAST_SEASON = 2025
POS = {"nba": {"PG", "SG", "SF", "PF", "C"}, "nfl": {"QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"},
       "mlb": {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "SP", "RP"}, "nhl": {"C", "LW", "RW", "D", "G"}}

def curl(url, out=None, post=None, headers=(), retries=4, delay=0.0):
    """Fetch with curl. Returns text (or writes to `out` and returns path). Polite delay applied before each call."""
    if delay: time.sleep(delay)
    for i in range(retries):
        args = ["curl", "-sL", "--max-time", "120", "-A", UA, "-w", "\n%{http_code}"] + [x for h in headers for x in ("-H", h)]
        if post: args += ["--data-urlencode", post]
        r = subprocess.run(args + [url], capture_output=True)
        body, _, code = r.stdout.rpartition(b"\n")
        if code.strip() == b"200":
            if out:
                pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(out).write_bytes(body); return str(out)
            return body.decode("utf-8", "replace")
        if code.strip() in (b"404", b"400"): return None
        time.sleep(2 + 3 * i)
    return None

def cached_json(path, url, delay=0.35, **kw):
    """GET url as JSON, caching the raw response at `path` (a pathlib.Path). Returns parsed JSON or None."""
    path = pathlib.Path(path)
    if path.exists() and path.stat().st_size > 2:
        return json.loads(path.read_text())
    txt = curl(url, delay=delay, **kw)
    if txt is None: return None
    try: d = json.loads(txt)
    except Exception: return None
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(txt)
    return d

SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace("'", "").replace("’", ""))
    toks = [t for t in s.split() if t]
    while len(toks) > 2 and toks[-1] in SUFFIX: toks.pop()
    return " ".join(toks)

def clean_name(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r"\s*\((?:[^)]*)\)\s*$", "", s)          # trailing (note)
    s = re.sub(r"\s*[\*†‡#]+$", "", s)
    return s.strip()

def merge_stints(st):
    """Merge overlapping / touching stints on the same franchise; drop empties."""
    by = collections.defaultdict(list)
    for f, s, e in st:
        e = min(e, LAST_SEASON + 1)
        if e > s: by[f].append([s, e])
    out = []
    for f, L in by.items():
        L.sort()
        cur = L[0][:]
        for s, e in L[1:]:
            if s <= cur[1]: cur[1] = max(cur[1], e)
            else: out.append([f, cur[0], cur[1]]); cur = [s, e]
        out.append([f, cur[0], cur[1]])
    out.sort(key=lambda x: (x[1], x[2], x[0]))
    return out

def franchise_ids(sport):
    import franchises
    return {fid for fid, _, _ in getattr(franchises, sport.upper())}

def famous_pool(sport):
    d = json.loads((HERE / "out" / f"{sport}.json").read_text())
    return d["players"]

def write_all(sport, source, license_, players, extra=None):
    """players: list of dict(id,name,born,pos,st,[famous]). Sorts, drops stint-less, validates, writes all/<sport>.json."""
    ALL.mkdir(exist_ok=True)
    fids = franchise_ids(sport); ok = []
    for p in players:
        p["st"] = merge_stints(p["st"])
        if not p["st"]: continue
        assert all(f in fids for f, _, _ in p["st"]), (p["name"], p["st"])
        if p.get("pos") is not None: assert p["pos"] in POS[sport], (p["name"], p["pos"])
        p.setdefault("famous", None); ok.append(p)
    ok.sort(key=lambda p: (p["st"][0][1], norm_name(p["name"]), str(p["id"])))
    d = {"source": source, "license": license_, "players": ok}
    if extra: d.update(extra)
    (ALL / f"{sport}.json").write_text(json.dumps(d, separators=(",", ":"), ensure_ascii=False))
    print(sport, "wrote", len(ok), "players ->", ALL / f"{sport}.json")
    return ok

def overlap_score(a, b):
    """Number of (franchise, season) cells shared by two stint lists."""
    n = 0
    for fa, sa, ea in a:
        for fb, sb, eb in b:
            if fa == fb: n += max(0, min(ea, eb) - max(sa, sb))
    return n

def season_cells(st):
    return sum(e - s for _, s, e in st)

def match_famous(sport, players, name_alias=None):
    """Set players[i]['famous'] for each famous-pool player. Returns (unmatched, ambiguous, matches).
    Candidate set = same normalised name (or, failing that, same last name + same first initial / fuzzy ratio >= .85).
    Best = highest shared (franchise,season) cells; ties broken by birth year absent -> keep first and flag ambiguous
    when a second candidate has a positive score within 30% of the best."""
    import difflib
    name_alias = name_alias or {}
    fam = famous_pool(sport)
    byname = collections.defaultdict(list)
    bylast = collections.defaultdict(list)
    for i, p in enumerate(players):
        n = norm_name(p["name"]); byname[n].append(i); bylast[n.split()[-1]].append(i)
        p["famous"] = None
    claimed = {}
    unmatched, ambiguous, matches = [], [], []
    for fp in fam:
        key = norm_name(name_alias.get(fp["name"], fp["name"]))
        cand = list(byname.get(key, []))
        how = "exact"
        if not cand:
            last = key.split()[-1]
            pool = bylast.get(last, [])
            sc = [(difflib.SequenceMatcher(None, key, norm_name(players[i]["name"])).ratio(), i) for i in pool]
            cand = [i for r, i in sc if r >= 0.8]; how = "fuzzy"
        scored = sorted(((overlap_score(fp["st"], players[i]["st"]), i) for i in cand), reverse=True)
        scored = [x for x in scored if x[0] > 0]
        if not scored:
            unmatched.append((fp["name"], how, [players[i]["name"] for i in cand][:5])); continue
        best = scored[0]
        if len(scored) > 1 and scored[1][0] >= 0.7 * best[0]:
            ambiguous.append((fp["name"], [(players[i]["name"], players[i]["id"], s) for s, i in scored[:3]]))
        if best[1] in claimed:
            ambiguous.append((fp["name"], "ALSO CLAIMED BY " + claimed[best[1]])); continue
        claimed[best[1]] = fp["name"]
        players[best[1]]["famous"] = fp["name"]
        matches.append((fp["name"], best[1], how, best[0]))
    return unmatched, ambiguous, matches

def fmt_st(st): return " ".join("%s:%d-%d" % (f, s, e - 1) for f, s, e in st)
