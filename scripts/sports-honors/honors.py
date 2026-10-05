#!/usr/bin/env python3
"""Career honors for the famous pools, read from the 'highlights' list in each player's English Wikipedia infobox.
Usage: honors.py nba|nfl|mlb|nhl   -> scripts/sports-honors/<sport>.json  {name: {"raw": {award: count}, "cat": {category: count}, "score": H}}
Every infobox bullet reads like '4x [[NBA Most Valuable Player]] (2008, ...)'; the leading number is the count (1 when absent)."""
import json, pathlib, re, subprocess, sys, time, urllib.parse
HERE = pathlib.Path(__file__).parent
SPORTS = HERE.parent / "sports"
sys.path.insert(0, str(SPORTS))
UA = "PurplelinkGames/1.0 (ben@purplelink.llc)"

def curl_json(url):
    for i in range(4):
        r = subprocess.run(["curl", "-s", "--max-time", "60", "-A", UA, url], capture_output=True, text=True)
        try: return json.loads(r.stdout)
        except Exception: time.sleep(2 + 3 * i)
    return None

def titles_for(qids):
    q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks", "sitefilter": "enwiki", "format": "json"})
    d = curl_json("https://www.wikidata.org/w/api.php?" + q) or {}
    return {k: v.get("sitelinks", {}).get("enwiki", {}).get("title") for k, v in d.get("entities", {}).items()}

def wikitext(titles):
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titles), "format": "json", "redirects": 1})
    d = curl_json("https://en.wikipedia.org/w/api.php?" + q) or {}
    redir = {r["to"]: r["from"] for r in d.get("query", {}).get("redirects", [])}
    out = {}
    for p in d.get("query", {}).get("pages", {}).values():
        try: out[redir.get(p["title"], p["title"])] = p["revisions"][0]["slots"]["main"]["*"]
        except Exception: pass
    return out, redir

def highlights(text):
    m = re.search(r"^\s*\|\s*(?:highlights|honors|honours)\s*=\s*(.*?)(?=^\s*\|\s*[a-z_0-9]+\s*=|^\}\})", text, flags=re.S | re.M)
    return m.group(1) if m else ""

def clean(s):
    s = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    for _ in range(3): s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"'{2,}|<[^>]+>", "", s).strip()

def parse(text):
    h = highlights(text)
    raw = {}
    for line in h.splitlines():
        line = line.strip()
        if not line.startswith("*") or line.startswith("**"): continue
        body = line.lstrip("* ").strip()
        m = re.match(r"(\d+)\s*[×x]\s*(.*)", body)
        n, rest = (int(m.group(1)), m.group(2)) if m else (1, body)
        name = clean(re.split(r"\s*[\(\{]", rest, 1)[0] if not rest.startswith("[[") else rest)
        name = re.sub(r"\s*\(.*$", "", name).strip(" :;,.")
        if not name or len(name) > 70: continue
        raw[name] = raw.get(name, 0) + n
    return raw

# Honors that count, per league. (pattern on the cleaned award name, category, points per selection). First match wins.
# College, high school, team halls of fame and off-field awards are not listed, so they never count.
COMMON = [(r"^(consensus )?first[- ]team all-pro|^all-(nba|aba|nhl|mlb) first|^nhl first all-star|^all-mlb first", "first", 3),
          (r"^(consensus )?second[- ]team all-pro|^all-(nba|aba|nhl|mlb) second|^nhl second all-star|^all-mlb second", "second", 2),
          (r"^all-(nba|aba) third", "third", 1)]
RULES = {
 "nba": COMMON + [(r"^(nba|aba) most valuable player", "mvp", 6), (r"^nba finals mvp", "finalsmvp", 3), (r"^nba defensive player of the year", "major", 3),
                  (r"^nba (rookie of the year|most improved|sixth man)", "minor", 1.5), (r"^(nba|aba) all-star$", "allstar", 1), (r"^(nba|aba) champion", "title", 1.3),
                  (r"^nba (scoring|rebounding|assists|steals|blocks) (champion|leader)", "leader", 1), (r"^nba all-defensive first", "minor", 1),
                  (r"^nba (75th )?anniversary team|^aba all-time team|^nba 50th", "legend", 4), (r"^nba all-star game mvp", "minor", 1)],
 "nfl": COMMON + [(r"^nfl most valuable player|^afl most valuable|^afl player of the year", "mvp", 6), (r"^super bowl mvp", "finalsmvp", 3),
                  (r"^nfl (offensive|defensive) player of the year", "major", 3), (r"^nfl (offensive|defensive) rookie of the year|^nfl comeback", "minor", 1.2),
                  (r"^(pro bowl|afl all-star)$", "allstar", 1), (r"^(super bowl|nfl|afl) champion", "title", 1.3),
                  (r"^nfl .* leader$", "leader", 1), (r"^nfl .* all-decade team", "decade", 1.5), (r"^nfl (100th|75th|50th) anniversary", "legend", 4)],
 "mlb": COMMON + [(r"^(al|nl|mlb)? ?(most valuable player|mvp)$", "mvp", 6), (r"^world series mvp", "finalsmvp", 3), (r"^(alcs|nlcs) mvp", "minor", 1.5),
                  (r"cy young", "major", 4), (r"^(al |nl )?rookie of the year", "minor", 1.5), (r"^gold glove|^silver slugger", "minor", 0.7),
                  (r"^all-star$|^mlb all-star", "allstar", 1), (r"^world series champion", "title", 1.3), (r"triple crown", "major", 3),
                  (r"(batting champion|home run leader|rbi leader|wins leader|strikeout leader|era leader|stolen base leader|saves leader)", "leader", 1),
                  (r"all-century team|all-time team", "legend", 4), (r"hank aaron award|rolaids|comeback player", "minor", 1.2)],
 "nhl": COMMON + [(r"hart (memorial )?trophy", "mvp", 6), (r"conn smythe", "finalsmvp", 3), (r"stanley cup", "title", 1.3),
                  (r"vezina|norris|art ross|rocket richard|ted lindsay|selke|calder|lester pearson|william m\. jennings", "major", 3),
                  (r"nhl all-star( game)?$|^nhl all-star", "allstar", 1), (r"lady byng|king clancy|masterton", "minor", 1.5), (r"100 greatest|centennial|all-decade", "legend", 4)],
}
HOF = re.compile(r"\|\s*(?:hof|hof_player|hall ?of ?fame|hofdate|hofyear|hoflink|hof_year|halloffame|hall_of_fame|pfhof|hhof)\s*=\s*[^\s|}]", re.I)

def classify(sport, raw, text=""):
    cat = {}; score = 0.0
    for name, n in raw.items():
        low = name.lower().strip()
        for pat, c, w in RULES[sport]:
            if re.search(pat, low):
                cat[c] = cat.get(c, 0) + n
                score += w * (n if n <= 6 else 6 + (n - 6) * 0.5)    # long careers count a little less each time past six
                break
    if HOF.search(text):
        cat["hof"] = 1; score += 5
    return cat, round(score, 1)

def section_awards(text):
    """Fallback when the infobox lists no highlights (many MLB and all NHL pages): count years on award lines under an awards heading."""
    m = re.search(r"^==+\s*(awards?|honou?rs|achievements|accomplishments|awards and (honou?rs|achievements)|career awards.*)\s*==+\s*$(.*?)(?=^==[^=]|\Z)", text, flags=re.S | re.M | re.I)
    if not m: return {}
    raw = {}
    for line in m.group(0).splitlines():
        l = clean(line)
        years = set(re.findall(r"\b(?:18|19|20)\d{2}\b", l))
        mm = re.match(r"^[\*\|!\s]*(.*?)(?:\s*[\(\|:,–-]\s*(?:18|19|20)\d{2}.*)?$", l)
        name = re.sub(r"^[\*\|!\s]+", "", (mm.group(1) if mm else l)).strip(" :;,.|")
        if name and years and len(name) < 80:
            raw[name] = raw.get(name, 0) + len(years)
    return raw

def main():
    sport = sys.argv[1]
    cache = json.loads((SPORTS / "cache" / f"{sport}.json").read_text())
    out_f = HERE / f"{sport}.json"
    out = json.loads(out_f.read_text()) if out_f.exists() else {}
    items = [(n, r["qid"]) for n, r in cache["players"].items() if r and n not in out]
    for i in range(0, len(items), 40):
        ch = items[i:i + 40]
        tm = titles_for([q for _, q in ch])
        t2n = {tm.get(q): n for n, q in ch if tm.get(q)}
        texts, redir = wikitext(list(t2n))
        for t, txt in texts.items():
            n = t2n.get(t)
            if not n: continue
            raw = parse(txt)
            if not raw: raw = section_awards(txt)
            cat, score = classify(sport, raw, txt)
            out[n] = {"raw": raw, "cat": cat, "score": score}
        for n, q in ch: out.setdefault(n, {"raw": {}, "cat": {}, "score": 0.0})
        out_f.write_text(json.dumps(out, indent=0)); print(i + len(ch), "/", len(items), flush=True); time.sleep(1)

if __name__ == "__main__": main()
