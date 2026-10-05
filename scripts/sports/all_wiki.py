"""Wikipedia helpers shared by the NBA / NHL / NFL all-players scripts (MediaWiki API through curl, polite delay, raw cache)."""
import json, pathlib, re, sys, urllib.parse, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from all_common import *
API = "https://en.wikipedia.org/w/api.php"

def page_wikitext(title, cache_dir):
    """Full wikitext of one page (redirects followed), cached as a file named after the title."""
    f = pathlib.Path(cache_dir) / (re.sub(r"[^A-Za-z0-9._-]+", "_", title) + ".wt")
    if f.exists(): return f.read_text()
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": title, "format": "json", "redirects": 1, "formatversion": 2})
    txt = curl(API + "?" + q, delay=0.4)
    if not txt: return None
    d = json.loads(txt)
    try: wt = d["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    except Exception: return None
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(wt)
    return wt

def batch_wikitext(titles, section0=False):
    """{requested title -> wikitext or None} for up to 50 titles. Follows redirects/normalisation; returns the resolved title too."""
    q = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titles), "format": "json", "redirects": 1, "formatversion": 2}
    if section0: q["rvsection"] = 0
    txt = curl(API + "?" + urllib.parse.urlencode(q), delay=0.35)
    if not txt: return None
    d = json.loads(txt).get("query", {})
    back = {}
    for n in d.get("normalized", []): back[n["to"]] = n["from"]
    redir = {r["to"]: r["from"] for r in d.get("redirects", [])}
    out = {}
    for p in d.get("pages", []):
        t = p["title"]
        wt = None
        try: wt = p["revisions"][0]["slots"]["main"]["content"]
        except Exception: pass
        src = redir.get(t, t); src = back.get(src, src)
        out[src] = (t, wt)
    return out

def infobox_field(wt, *names):
    for n in names:
        m = re.search(r"^\s*\|\s*%s\s*=\s*(.*?)\s*(?=^\s*\||\Z|^\}\})" % n, wt, flags=re.M | re.S | re.I)
        if m: return m.group(1)
    return None

def birth_year(wt):
    v = infobox_field(wt, "birth_date", "birthdate")
    if not v: return None
    v = re.sub(r"<!--.*?-->", "", v, flags=re.S)
    m = re.search(r"\{\{\s*(?:birth[ _]date(?:[ _]and[ _]age)?|bda|birth[ _]year[ _]and[ _]age|birth-date(?:[ _]and[ _]age)?)\s*\|\s*(?:df=\w+\|)?(?:mf=\w+\|)?(\d{4})", v, flags=re.I)
    if m: return int(m.group(1))
    m = re.search(r"\b(1[6-9]\d\d|20[0-2]\d)\b", v)
    return int(m.group(1)) if m else None

def row_cells(row):
    """Split a wikitext table row into cells at '||', '!!' and at line starts '|' / '!', but not inside {{...}} or [[...]]."""
    cells, cur, depth, i, n = [], [], 0, 0, len(row)
    while i < n:
        two = row[i:i + 2]
        if two in ("{{", "[["): depth += 1; cur.append(two); i += 2; continue
        if two in ("}}", "]]"): depth = max(0, depth - 1); cur.append(two); i += 2; continue
        if depth == 0:
            if two in ("||", "!!"): cells.append("".join(cur)); cur = []; i += 2; continue
            if row[i] == "\n" and i + 1 < n and row[i + 1] in "|!" and row[i + 1:i + 3] not in ("|-", "|}", "|+"):
                cells.append("".join(cur)); cur = []; i += 2; continue
        cur.append(row[i]); i += 1
    cells.append("".join(cur))
    return cells
