#!/usr/bin/env python3
"""All NBA players (BAA 1946-49 players only through surviving franchises; ABA stints for the franchises that joined the NBA and for the
ABA clubs that have an id in franchises.py) built from Wikipedia (en.wikipedia.org, CC BY-SA 4.0). Sources, in order of trust:
  1. the per-franchise 'all-time roster' lists: one row per player with tenure seasons ({{nbay}}/{{abay}} templates = start year of the season)
     and a Basketball-Reference citation whose id we keep as the stable source id and cross-franchise join key;
  2. the player's own article infobox (years/team pairs) - used for birth year, position, and to ADD a franchise the lists miss;
  3. Wikipedia player categories ('<Team> players', NBA and ABA) - only to find players the lists omit; their stints come from the infobox.
Writes all/nba.json.  Usage: all_nba.py [--no-info]"""
import re, sys, json, collections, pathlib, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_wiki import *
import build
RAWD = RAW / "nba"
PAGES = [  # (page title, franchise id); season rules in assign()
 ("Atlanta Hawks all-time roster", "ATL"), ("Boston Celtics all-time roster", "BOS"), ("Brooklyn Nets all-time roster", "BKN"),
 ("Charlotte Hornets all-time roster", "CHA"), ("Chicago Bulls all-time roster", "CHI"), ("Cleveland Cavaliers all-time roster", "CLE"),
 ("Dallas Mavericks all-time roster and statistics leaders", "DAL"), ("Denver Nuggets all-time roster", "DEN"), ("Detroit Pistons all-time roster", "DET"),
 ("Golden State Warriors all-time roster", "GSW"), ("Houston Rockets all-time roster", "HOU"), ("Indiana Pacers all-time roster", "IND"),
 ("Los Angeles Clippers all-time roster", "LAC"), ("Los Angeles Lakers all-time roster", "LAL"), ("Memphis Grizzlies all-time roster", "MEM"),
 ("Miami Heat all-time roster", "MIA"), ("Milwaukee Bucks all-time roster", "MIL"), ("Minnesota Timberwolves all-time roster", "MIN"),
 ("New Orleans Pelicans all-time roster", "NOP"), ("New York Knicks all-time roster", "NYK"), ("Oklahoma City Thunder all-time roster", "OKC"),
 ("Seattle SuperSonics all-time roster", "OKC"), ("Orlando Magic all-time roster", "ORL"), ("Philadelphia 76ers all-time roster", "PHI"),
 ("Phoenix Suns all-time roster", "PHX"), ("Portland Trail Blazers all-time roster", "POR"), ("Sacramento Kings all-time roster", "SAC"),
 ("San Antonio Spurs all-time roster", "SAS"), ("Toronto Raptors all-time roster", "TOR"), ("Utah Jazz all-time roster", "UTA"),
 ("Washington Wizards all-time roster", "WAS"),
]
CAT_ROOTS = ["Category:%s players" % n for n in [
 "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
 "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers", "Los Angeles Clippers", "Los Angeles Lakers", "Memphis Grizzlies",
 "Miami Heat", "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
 "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards",
 "Charlotte Bobcats", "Seattle SuperSonics", "New Jersey Nets", "New York Nets", "New Orleans Hornets", "Washington Bullets", "Capital Bullets",
 "Baltimore Bullets (1963–1973)", "Chicago Zephyrs", "Chicago Packers", "Buffalo Braves", "San Diego Clippers", "Vancouver Grizzlies", "Kansas City Kings",
 "Kansas City-Omaha Kings", "Cincinnati Royals", "Rochester Royals", "Syracuse Nationals", "Philadelphia Warriors", "San Francisco Warriors",
 "St. Louis Hawks", "Milwaukee Hawks", "Tri-Cities Blackhawks", "Minneapolis Lakers", "Fort Wayne Pistons", "San Diego Rockets", "New Orleans Jazz",
 "Virginia Squires", "Utah Stars", "Kentucky Colonels", "Spirits of St. Louis", "San Diego Conquistadors", "Carolina Cougars", "Oakland Oaks", "Washington Caps",
 "Los Angeles Stars", "Anaheim Amigos", "Denver Rockets", "Dallas Chaparrals", "Texas Chaparrals", "Houston Mavericks", "New Jersey Americans"]]

# ---------------------------------------------------------------------------------------------- list-page parsing
NBAY = re.compile(r"\{\{\s*[na]bay\s*\|\s*(\d{4})\s*(?:\|([^}]*))?\}\}|\{\{\s*sort\s*\|\s*9999\s*\|\s*present\s*\}\}|\bpresent\b", re.I)
def strip_sort(c):
    """{{sort|key|text}} -> text (nested templates allowed); {{dts|...}} -> ''."""
    out, i = [], 0
    low = c.lower()
    while i < len(c):
        m = re.match(r"\{\{\s*(sort|dts)\s*\|", c[i:], flags=re.I)
        if not m: out.append(c[i]); i += 1; continue
        depth, j = 1, i + m.end()
        start = j
        while j < len(c) and depth:
            if c.startswith("{{", j): depth += 1; j += 2
            elif c.startswith("}}", j): depth -= 1; j += 2
            else: j += 1
        body = c[start:j - 2]
        if m.group(1).lower() == "sort":
            parts = body.split("|", 1); out.append(strip_sort(parts[1] if len(parts) > 1 else ""))
        i = j
    return "".join(out)
def toks(part):
    out = []
    for m in NBAY.finditer(part):
        out.append((int(m.group(1)), (m.group(2) or "").lower()) if m.group(1) else (LAST_SEASON, "present"))
    return out
def is_bare(c):
    """A From/To cell: nothing but season templates, dts() sort helpers, 'present' and <br>."""
    t = re.sub(r"\{\{\s*dts[^}]*\}\}|<br\s*/?>|\s", "", NBAY.sub("", c), flags=re.I)
    return bool(NBAY.search(c)) and not t
def single_cell(cell):
    """One 'Seasons' cell: parts separated by <br>; within a part 1 token = one season, 2+ tokens pair up as first..last season."""
    out = []
    for part in re.split(r"<br\s*/?>", cell, flags=re.I):
        t = toks(part)
        if not t:
            ys = [int(y) for y in re.findall(r"\b(19[4-9]\d|20[0-3]\d)\b", part)]
            if len(ys) == 1: out.append([ys[0], ys[0] + 1])
            elif len(ys) >= 2: out.append([ys[0], ys[-1]])
            continue
        i = 0
        while i < len(t):
            if i + 1 < len(t): out.append([t[i][0], t[i + 1][0] + 1]); i += 2
            else: out.append([t[i][0], t[i][0] + 1]); i += 1
    return out
def from_to(c1, c2):
    a = [toks(p) for p in re.split(r"<br\s*/?>", c1, flags=re.I)]
    b = [toks(p) for p in re.split(r"<br\s*/?>", c2, flags=re.I)]
    a = [x[0][0] for x in a if x]; b = [x[0][0] for x in b if x]
    return [[a[i], b[i] + 1] for i in range(min(len(a), len(b)))]
STOP = {"men", "s", "basketball", "university", "college", "of", "the", "state", "high", "school", "hs"}
def link_tokens(links):
    return {w for l in links for w in re.findall(r"[a-z]+", norm_name(l)) if w not in STOP and len(w) > 2}
def assign(fid, s, e):
    """Charlotte's pre-Bobcats seasons belong to the Hornets/Pelicans line (NOP), as in build.franchise_of."""
    if fid == "CHA":
        parts = []
        if s <= 2003: parts.append(("NOP", s, min(e, 2004)))
        if e > 2004: parts.append(("CHA", max(s, 2004), e))
        return [p for p in parts if p[2] > p[1]]
    return [(fid, s, e)]
def parse_page(title, fid):
    wt = page_wikitext(title, RAWD)
    if wt is None: raise SystemExit("cannot fetch " + title)
    m = re.search(r"^==\s*[^=\n]*(?:coach|leader|international|notes|references|see also|external)[^=\n]*==\s*$", wt, flags=re.M | re.I)
    if m: wt = wt[:m.start()]           # player tables only: coaches, statistics leaders and international-player tables follow
    rows = []
    for row in re.split(r"\n\|-[^\n]*", wt):
        low = row.lower()
        if "sortname" not in low and "bay|" not in low and "present" not in low: continue
        cells = [strip_sort(c) if "sortname" not in c.lower() else c for c in row_cells(row)]
        ni = next((i for i, c in enumerate(cells) if "sortname" in c.lower()), None)
        tg = None
        if ni is not None:
            m = re.search(r"\{\{\s*sortname\s*\|([^}]*)\}\}", cells[ni], flags=re.I)
            a = [x.strip() for x in m.group(1).split("|")]
            pos_a = [x for x in a if "=" not in x]
            kw = {x.split("=", 1)[0].strip().lower(): x.split("=", 1)[1].strip() for x in a if "=" in x}
            first, last = (pos_a + ["", ""])[:2]
            link = pos_a[2] if len(pos_a) > 2 else None
            name = (first + " " + last).strip()
            tg = link or (name + (" (%s)" % kw["dab"] if kw.get("dab") else ""))
            if kw.get("nolink"): tg = None
        else:   # plain wikilink in the first cell
            ni = next((i for i, c in enumerate(cells[:2]) if re.search(r"\[\[(?!File:|Image:)", c)), None)
            if ni is None: continue
            m = re.search(r"\[\[(?!File:|Image:)([^\]|]+)(?:\|([^\]]+))?\]\]", cells[ni])
            tg = m.group(1).strip(); name = re.sub(r"\s*\(.*$", "", (m.group(2) or m.group(1))).strip()
        k = next((i for i in range(ni + 1, len(cells)) if toks(cells[i])), None)
        if k is None: continue
        if k + 1 < len(cells) and is_bare(cells[k]) and is_bare(cells[k + 1]): ten = from_to(cells[k], cells[k + 1])
        else: ten = single_cell(cells[k])
        bb = re.search(r"basketball-reference\.com/players/\w/([a-z]+\d\d)\.html", row)
        pos = re.sub(r"<[^>]+>|\[\[|\]\]|align=\S+|style=\S+", "", cells[ni + 1] if ni + 1 < len(cells) else "").strip(' "|')
        pos = re.sub(r"^.*\|", "", pos)
        links = {x.split("|")[0].strip() for c in cells[ni + 1:] for x in re.findall(r"\[\[([^\]]+)\]\]", c)
                 if "basketball" in x.lower() or "|" in x} - {tg}          # college / pre-draft team links, used to tell namesakes apart
        rows.append({"name": clean_name(name), "title": tg, "bb": bb.group(1) if bb else None, "pos": pos, "ten": ten, "fid": fid, "page": title, "links": links})
    return rows

# ---------------------------------------------------------------------------------------------- infobox / category fetch
POSMAP = [("point guard", "PG"), ("shooting guard", "SG"), ("small forward", "SF"), ("power forward", "PF"), ("center", "C")]
def fetch_info(titles):
    """{requested title -> {rt, born, pos, teams:[[team link/label, years text], ...]} } from infobox section 0; cached in raw/nba/info2.json."""
    f = RAWD / "info2.json"; cache = json.loads(f.read_text()) if f.exists() else {}
    todo = sorted({t for t in titles if t not in cache})
    print("fetching infoboxes for", len(todo), "titles", flush=True)
    for i in range(0, len(todo), 50):
        ch = todo[i:i + 50]
        res = batch_wikitext(ch, section0=True)
        if res is None: print("batch failed", i); continue
        for t in ch:
            if t not in res: cache[t] = {}; continue
            rt, wt = res[t]
            if not wt or "infobox basketball biography" not in wt.lower(): cache[t] = {"rt": rt}; continue
            wt = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
            posv = (infobox_field(wt, "career_position", "position") or "").lower()
            posv = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", posv)
            hits = sorted((posv.find(k), c) for k, c in POSMAP if k in posv)
            teams = []
            for n in range(1, 40):
                yv = infobox_field(wt, "years%d" % n); tv = infobox_field(wt, "team%d" % n)
                if yv is None and tv is None:
                    if n > 3: break
                    continue
                teams.append([tv or "", yv or ""])
            cache[t] = {"rt": rt, "born": birth_year(wt), "pos": hits[0][1] if hits else None, "teams": teams}
        if (i // 50) % 10 == 0: f.write_text(json.dumps(cache)); print(" ", i + len(ch), "/", len(todo), flush=True)
    f.write_text(json.dumps(cache))
    return cache
def fetch_cats():
    """All article titles in the roots (and their '... players' subcategories, depth 2), cached."""
    f = RAWD / "cats.json"; cache = json.loads(f.read_text()) if f.exists() else {}
    def members(cat, typ):
        out, cont = [], None
        while True:
            q = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": 500, "cmtype": typ, "format": "json", "formatversion": 2}
            if cont: q["cmcontinue"] = cont
            txt = curl(API + "?" + urllib.parse.urlencode(q), delay=0.3)
            d = json.loads(txt) if txt else {}
            out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
            cont = d.get("continue", {}).get("cmcontinue")
            if not cont: return out
    seen_cat = set()
    def walk(cat, depth):
        if cat in seen_cat: return
        seen_cat.add(cat)
        if cat not in cache: cache[cat] = {"pages": members(cat, "page"), "sub": members(cat, "subcat")}
        if depth > 0:
            for sc in cache[cat]["sub"]:
                if sc.endswith(" players") and "women" not in sc.lower() and "draft" not in sc.lower(): walk(sc, depth - 1)
    for c in CAT_ROOTS: walk(c, 2)
    f.write_text(json.dumps(cache))
    titles = set()
    for c in seen_cat: titles |= set(cache[c]["pages"])
    return {t for t in titles if "all-time roster" not in t and not t.lower().startswith(("list of", "category:"))}

def nba_fid(label, s):
    """build.franchise_of with the 'hornets' trap removed: franchises.NBA lists BKN's pattern 'nets', which is a substring of 'hornets'."""
    t = label.lower()
    if "hornets" in t:
        if "new orleans" in t or "oklahoma city" in t: return "NOP"
        if "charlotte" in t: return "NOP" if s < 2003 else "CHA"
        return None
    return build.franchise_of("nba", label, s)
def info_stints(teams):
    """Infobox rows -> [(franchise, s, e)] counting only NBA/ABA season templates (so G League / overseas clubs are never mistaken for NBA clubs)."""
    out = []
    for tv, yv in teams:
        if not re.search(r"[na]bay\s*\|", yv, flags=re.I) and "present" not in yv.lower(): continue
        if not re.search(r"[na]bay\s*\|", yv, flags=re.I): continue
        m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", tv)
        label = (m.group(2) or m.group(1)) if m else re.sub(r"[\[\]]", "", tv)
        label2 = m.group(1) if m else label
        for s, e in single_cell(yv):
            f = nba_fid(label, s) or nba_fid(label2, s)
            if f == "WAS" and s < 1961: continue          # original Baltimore Bullets (1944-54) are a different, defunct club
            if f == "DEN" and s < 1967: continue          # Denver Nuggets (1948-50) likewise
            if f: out.append((f, s, e))
    return out

# ---------------------------------------------------------------------------------------------- main
def main():
    rows = []
    for title, fid in PAGES:
        r = parse_page(title, fid); rows += r
        print(title, len(r), "rows,", sum(1 for x in r if x["bb"]), "with bbref id", flush=True)
    # a bbref id cited on a row whose name disagrees with the id's majority name is a Wikipedia typo: drop that id from the row
    names_by_bb = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["bb"]: names_by_bb[r["bb"]][norm_name(r["name"])] += 1
    bad = 0
    for r in rows:
        if r["bb"] and norm_name(r["name"]) != names_by_bb[r["bb"]].most_common(1)[0][0]:
            if len(names_by_bb[r["bb"]]) > 1 and names_by_bb[r["bb"]][norm_name(r["name"])] == 1: r["bb"] = None; bad += 1
    print("rows whose cited bbref id disagreed with the id's other rows (ignored):", bad)
    G = collections.OrderedDict()
    for r in rows:
        k = r["bb"] or ("T:" + r["title"] if r["title"] else "N:" + norm_name(r["name"]))
        g = G.setdefault(k, {"id": r["bb"] or k, "name": r["name"], "title": r["title"], "posl": set(), "st": [], "bbref": bool(r["bb"]), "links": set()})
        g["posl"].add(r["pos"]); g["title"] = g["title"] or r["title"]; g["links"] |= r["links"]
        for s, e in r["ten"]:
            for f, s2, e2 in assign(r["fid"], s, e): g["st"].append([f, s2, e2])
    info = {}; cattitles = set()
    if "--no-info" not in sys.argv:
        cattitles = fetch_cats(); print("category titles", len(cattitles))
        info = fetch_info(sorted({g["title"] for g in G.values() if g["title"]} | cattitles))
    # id-less groups (Sonics page, a few rows elsewhere) join a bbref group of the same article title when the college / pre-draft links agree,
    # or, failing that, when the article's infobox lists the id-less group's franchise (so a namesake such as the other Bill Russell is refused)
    bytitle = collections.defaultdict(list)
    for k, g in G.items():
        if g["bbref"] and g["title"]: bytitle[g["title"]].append(k)
    joined = refused = 0
    for k in [k for k, g in G.items() if not g["bbref"]]:
        g = G[k]; cand = bytitle.get(g["title"], [])
        ok = [c for c in cand if link_tokens(g["links"]) & link_tokens(G[c]["links"]) or (not g["links"] and not G[c]["links"])]
        if len(ok) != 1 and cand:
            gf = {f for f, _, _ in g["st"]}
            ok = [c for c in cand if gf <= {f for f, _, _ in info_stints(info.get(G[c]["title"] or "", {}).get("teams", []))}]
        if len(ok) == 1 and ok[0] != k:
            t_ = ok[0]; G[t_]["st"] += g["st"]; G[t_]["posl"] |= g["posl"]; G[t_]["links"] |= g["links"]; del G[k]; joined += 1
        elif cand: refused += 1; print("  refused join:", g["name"], sorted(g["links"])[:2], [G[c]["id"] for c in cand])
    print("players from lists", len(G), "| id-less rows joined to a bbref player:", joined, "| refused (namesake):", refused)
    out = []; used_rt = set(); stat = collections.Counter()
    for g in G.values():
        i = info.get(g["title"] or "", {})
        ist = info_stints(i.get("teams", [])) if i.get("teams") else []
        lf = {f for f, _, _ in g["st"]}
        if ist and lf and not ({f for f, _, _ in ist} & lf):   # the article is another person with the same name
            stat["infobox rejected (no shared franchise)"] += 1; i = {}; ist = []
        if i.get("rt"): used_rt.add(i["rt"])
        st = list(g["st"])
        for f in {f for f, _, _ in ist} - lf:                  # franchises the lists miss for this player
            st += [[x, s, e] for x, s, e in ist if x == f]; stat["franchise added from infobox"] += 1
        pos = i.get("pos")
        if pos is None and g["posl"] == {"C"}: pos = "C"
        out.append({"id": g["id"], "name": g["name"], "born": i.get("born"), "pos": pos, "st": st})
    # players found only through categories
    for t in sorted(cattitles):
        i = info.get(t, {})
        if not i.get("teams") or i.get("rt") in used_rt: continue
        used_rt.add(i["rt"])
        st = [list(x) for x in info_stints(i["teams"])]
        if st:
            out.append({"id": "wp:" + i["rt"], "name": clean_name(re.sub(r"\s*\([^)]*\)$", "", i["rt"])), "born": i.get("born"), "pos": i.get("pos"), "st": st})
            stat["players from categories only"] += 1
    print(dict(stat))
    unm, amb, mt = match_famous("nba", out, ALIASES)
    print("famous matched", len(mt), "unmatched", unm, "ambiguous", amb)
    write_all("nba", "Wikipedia franchise all-time roster lists, player infoboxes and player categories (en.wikipedia.org, CC BY-SA 4.0; list rows cite Basketball-Reference ids). Franchise mapping by Purplelink.",
              "CC BY-SA 4.0 (Wikipedia text); facts compiled by Purplelink; attribution to Wikipedia contributors required", out)
ALIASES = {}
if __name__ == "__main__": main()
