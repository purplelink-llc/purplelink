#!/usr/bin/env python3
"""All NHL players: candidates from Wikipedia's per-franchise 'List of X players' articles (CC BY-SA 4.0; each row = a player who
appeared for the club, with first/last season), exact season-by-season clubs from the NHL rows of the 'Career statistics' table on each
player's own Wikipedia article. Birth year and position from the article infobox.  (The official NHL stats API was NOT used: the NHL
terms of service prohibit unauthorised automated compilation.)
Rule: a franchise's stints come from the player's career table when it has any season for that franchise; otherwise from the list's
first-last range (gaps cannot be seen, so the range is split around seasons the player is known to have spent elsewhere).
Usage: all_nhl.py [fetch|build]   (default both)"""
import re, sys, json, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_wiki import *
import wiki_career, build
RAWD = RAW / "nhl"
PAGES = [  # (list article, franchise id)
 ("Anaheim Ducks", "ANA"), ("Boston Bruins", "BOS"), ("Buffalo Sabres", "BUF"), ("Calgary Flames", "CGY"), ("Atlanta Flames", "CGY"),
 ("Carolina Hurricanes", "CAR"), ("Hartford Whalers", "CAR"), ("Chicago Blackhawks", "CHI"), ("Colorado Avalanche", "COL"), ("Quebec Nordiques", "COL"),
 ("Columbus Blue Jackets", "CBJ"), ("Dallas Stars", "DAL"), ("Minnesota North Stars", "DAL"), ("Detroit Red Wings", "DET"), ("Edmonton Oilers", "EDM"),
 ("Florida Panthers", "FLA"), ("Los Angeles Kings", "LAK"), ("Minnesota Wild", "MIN"), ("Montreal Canadiens", "MTL"), ("Nashville Predators", "NSH"),
 ("New Jersey Devils", "NJD"), ("Colorado Rockies (NHL)", "NJD"), ("Kansas City Scouts", "NJD"), ("New York Islanders", "NYI"), ("New York Rangers", "NYR"),
 ("Ottawa Senators", "OTT"), ("Philadelphia Flyers", "PHI"), ("Pittsburgh Penguins", "PIT"), ("San Jose Sharks", "SJS"), ("Seattle Kraken", "SEA"),
 ("St. Louis Blues", "STL"), ("Tampa Bay Lightning", "TBL"), ("Toronto Maple Leafs", "TOR"), ("Utah Mammoth", "UTA"), ("Arizona Coyotes", "UTA"),
 ("Winnipeg Jets (1979–1996)", "UTA"), ("Vancouver Canucks", "VAN"), ("Vegas Golden Knights", "VGK"), ("Washington Capitals", "WSH"),
 ("Winnipeg Jets", "WPG"), ("Atlanta Thrashers", "WPG"), ("California Golden Seals", "CLB"), ("Cleveland Barons (NHL)", "CLB"),
]
POSMAP = [("goaltender", "G"), ("goalie", "G"), ("left wing", "LW"), ("right wing", "RW"), ("defence", "D"), ("defense", "D"), ("centre", "C"), ("center", "C")]
def team_fid(label, s):
    label = re.sub(r"\s+", " ", label); t = label.lower()
    if "ottawa senators" in t and s < 1935: return None          # the original Senators (1917-34) are a different franchise
    if any(x in t for x in ("detroit cougars", "detroit falcons")): return "DET"
    return build.franchise_of("nhl", label, s)

DASH = "[–—‒-]"
def unwrap(c):
    c = re.sub(r"<ref[^>]*?(?:/>|>.*?</ref>)", "", c, flags=re.S)
    c = re.sub(r"\{\{\s*sort\s*\|[^|}]*\|([^}]*)\}\}", r"\1", c, flags=re.I)
    return c
def parse_list(title, fid):
    wt = page_wikitext("List of %s players" % title, RAWD)
    if wt is None: print("MISSING list", title); return []
    rows = []
    for row in re.split(r"\n\|-[^\n]*", wt):
        cells = [unwrap(c) for c in row_cells(row)]
        ni = next((i for i, c in enumerate(cells[:3]) if "sortname" in c.lower() or re.search(r"\[\[(?!File:|Image:|Category:)", c)), None)
        if ni is None: continue
        ym = None
        for c in cells[ni + 1:ni + 6]:
            ym = re.search(r"\b((?:19|20)\d\d)\s*%s\s*((?:19|20)\d\d|present)\b" % DASH, c, flags=re.I)
            if ym: break
        if ym is None: continue
        c0 = cells[ni]
        m = re.search(r"\{\{\s*sortname\s*\|([^}]*)\}\}", c0, flags=re.I)
        if m:
            a = [x.strip() for x in m.group(1).split("|") if "=" not in x]
            first, last = (a + ["", ""])[:2]
            ttl = a[2] if len(a) > 2 and a[2] else (first + " " + last).strip()
            disp = (first + " " + last).strip()
        else:
            m = re.search(r"\[\[(?!File:|Image:|Category:)([^\]|]+)(?:\|([^\]]+))?\]\]", c0)
            ttl = m.group(1).strip(); disp = re.sub(r"\s+", " ", (m.group(2) or m.group(1))).strip()
            mm = re.match(r"^(.*?),\s*(.*)$", disp)
            if mm: disp = mm.group(2) + " " + mm.group(1)
        s_ = int(ym.group(1)); e_ = LAST_SEASON + 1 if ym.group(2).lower() == "present" else int(ym.group(2))
        if e_ < s_: continue
        if e_ == s_: e_ = s_ + 1
        pos = None
        for c in cells[ni + 1:ni + 4]:
            cc = re.sub(r"\{\{[^}]*\}\}|\[\[|\]\]|'''|<[^>]+>", "", c).strip()
            if re.fullmatch(r"(C|LW|RW|L|R|D|W|F|G)(\s*[/,]\s*(C|LW|RW|L|R|D|W|F))*", cc): pos = cc.split("/")[0].split(",")[0].strip(); break
        pos = {"L": "LW", "R": "RW"}.get(pos, pos)
        rows.append({"title": ttl, "disp": disp, "s": s_, "e": e_, "fid": fid, "pos": pos if pos in ("C", "LW", "RW", "D", "G") else None})
    return rows

def fetch_pages(titles):
    """Per title: infobox head + career-statistics tail, cached as JSON lines."""
    f = RAWD / "pages.json"; cache = json.loads(f.read_text()) if f.exists() else {}
    todo = sorted({t for t in titles if t not in cache})
    print("fetching", len(todo), "player articles", flush=True)
    for i in range(0, len(todo), 40):
        ch = todo[i:i + 40]
        res = batch_wikitext(ch)
        if res is None:
            print("batch failed, retry later", i); continue
        for t in ch:
            if t not in res: cache[t] = {"missing": True}; continue
            rt, wt = res[t]
            if wt is None: cache[t] = {"missing": True}; continue
            j = wt.find("areer statistics")
            cache[t] = {"title": rt, "head": wt[:7000], "tail": wt[j:j + 40000] if j >= 0 else "", "len": len(wt)}
        if (i // 40) % 5 == 0: f.write_text(json.dumps(cache)); print(" ", i + len(ch), "/", len(todo), flush=True)
    f.write_text(json.dumps(cache))
    return cache

def infobox_info(head):
    low = head.lower()
    if "infobox ice hockey" not in low: return None
    posv = (infobox_field(head, "position") or "").lower()
    posv = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", posv)
    pos = None
    hits = sorted((posv.find(k), c) for k, c in POSMAP if k in posv)
    if hits: pos = hits[0][1]
    return {"born": birth_year(head), "pos": pos}

def career(tail, head):
    if not tail: return []
    try: return wiki_career.parse_nhl(re.sub(r"<!--.*?-->", "", head + "\n" + tail, flags=re.S))
    except Exception: return []

def split_around(rng, others):
    """Remove from season range rng=[s,e) the seasons wholly covered by other franchises' ranges lying strictly inside it."""
    s, e = rng; pieces = [[s, e]]
    for os_, oe in others:
        if os_ > s and oe < e:       # strictly inside: player left and came back
            new = []
            for a, b in pieces:
                if a < os_ and oe < b: new += [[a, os_], [oe, b]]
                else: new.append([a, b])
            pieces = new
    return pieces

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    rows = []
    for t, fid in PAGES: 
        r = parse_list(t, fid); rows += r; print(t, len(r), "rows", flush=True)
    titles = sorted({r["title"] for r in rows})
    print("unique linked titles", len(titles))
    cache = fetch_pages(titles)
    if mode == "fetch": return
    # resolve each list title to an article (redirects); key players by resolved title
    byp = collections.OrderedDict()
    for r in rows:
        c = cache.get(r["title"], {})
        info = infobox_info(c["head"]) if c.get("head") else None
        key = ("W:" + c["title"]) if info is not None else ("R:" + norm_name(r["disp"]) + "|" + r["title"])
        p = byp.setdefault(key, {"title": c.get("title") if info is not None else None, "disp": r["disp"], "info": info, "lst": [], "c": c, "pos": set()})
        p["lst"].append((r["fid"], r["s"], r["e"])); 
        if r["pos"]: p["pos"].add(r["pos"])
    print("players", len(byp), "of which with article+infobox", sum(1 for p in byp.values() if p["info"] is not None))
    out = []; stat = collections.Counter(); unmapped = collections.Counter()
    for key, p in byp.items():
        tab = []
        if p["info"] is not None:
            for x in career(p["c"].get("tail", ""), p["c"].get("head", "")):
                f = team_fid(x["team"], x["s"])
                if f: tab.append([f, x["s"], min(x["e"], LAST_SEASON + 1)])
                else: unmapped[x["team"]] += 1
        tab = [x for x in tab if x[2] > x[1]]
        tabf = collections.defaultdict(list)
        for f, s, e in tab: tabf[f].append([s, e])
        st = list(tab)
        # franchises the list says the player was on but the career table lacks (or the table failed): use the list range, minus seasons known elsewhere
        lf = collections.defaultdict(list)
        for f, s, e in p["lst"]: lf[f].append([s, e])
        for f, rngs in lf.items():
            if f in tabf: stat["from table"] += 1; continue
            stat["from list" if tab else "from list (no table)"] += 1
            for s, e in rngs:
                others = [(os_, oe) for g, L in tabf.items() if g != f for os_, oe in L] + [(os_, oe) for g, L in lf.items() if g != f for os_, oe in L]
                for a, b in split_around([s, e], others): st.append([f, a, min(b, LAST_SEASON + 1)])
        if p["info"] is not None and p["title"]:
            name = clean_name(re.sub(r"\s*\((?:ice hockey|hockey|[^)]*born[^)]*|[^)]*hockey[^)]*)\)\s*$", "", p["title"]))
            pid = "wp:" + p["title"]
        else:
            name = clean_name(p["disp"]); pid = "wp?:" + key[2:]
        pos = (p["info"] or {}).get("pos")
        if pos is None and len(p["pos"]) == 1:
            pp = next(iter(p["pos"])); pos = pp if pp in ("C", "LW", "RW", "D", "G") else None
        out.append({"id": pid, "name": name, "born": (p["info"] or {}).get("born"), "pos": pos, "st": st})
    print(dict(stat)); print("unmapped table labels (dropped):", unmapped.most_common(25))
    unm, amb, mt = match_famous("nhl", out, ALIASES)
    print("famous matched", len(mt), "unmatched", unm, "ambiguous", amb)
    write_all("nhl", "Wikipedia 'List of <franchise> players' articles and player career-statistics tables (en.wikipedia.org, CC BY-SA 4.0); birth year and position from article infoboxes. Franchise mapping by Purplelink.",
              "CC BY-SA 4.0 (Wikipedia text); facts compiled by Purplelink; attribution to Wikipedia contributors required", out)
ALIASES = {}
if __name__ == "__main__": main()
