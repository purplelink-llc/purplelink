#!/usr/bin/env python3
"""Pull career team/year pairs from each player's English Wikipedia infobox. Usage: wiki_career.py nba
Writes cache/<sport>-career.json {name: [{team, s, e}]}. Needs cache/<sport>.json from resolve.py."""
import json, subprocess, sys, re, time, pathlib, urllib.parse
HERE = pathlib.Path(__file__).parent
UA = "PurplelinkGames/1.0 (ben@purplelink.llc)"
def curl(url, data=None):
    for i in range(4):
        args = ["curl", "-s", "--max-time", "60", "-A", UA, url] + (["--data-urlencode", data] if False else [])
        r = subprocess.run(args, capture_output=True, text=True)
        try: return json.loads(r.stdout)
        except Exception: time.sleep(2 + 3 * i)
    return None
def titles_for(qids):
    q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks", "sitefilter": "enwiki", "format": "json"})
    d = curl("https://www.wikidata.org/w/api.php?" + q) or {}
    return {k: v.get("sitelinks", {}).get("enwiki", {}).get("title") for k, v in d.get("entities", {}).items()}
def wikitext(titles):
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(titles), "format": "json", "redirects": 1})
    d = curl("https://en.wikipedia.org/w/api.php?" + q) or {}
    out = {}
    redir = {r["to"]: r["from"] for r in d.get("query", {}).get("redirects", [])}
    for p in d.get("query", {}).get("pages", {}).values():
        try: out[p["title"]] = p["revisions"][0]["slots"]["main"]["*"]
        except Exception: pass
    return out, redir
def clean(t):
    t = re.sub(r"<ref.*?(</ref>|/>)", "", t, flags=re.S)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    return re.sub(r"<[^>]+>|'{2,}", "", t).strip()
def expand_years(v):
    """Expand Wikipedia season templates ({{nbay|1956|start}}, {{abay|1972|end}}, {{nbay|1985|full=y}}, also nfl/mlb/nhl equivalents)
    into plain years. The numeric argument is always the season's starting year; 'end' yields the year that season ended."""
    def sub(m):
        y = int(m.group(1)); rest = m.group(2).lower()
        if "end" in rest and "full" not in rest: return str(y + 1)
        if "full" in rest: return "%d\u2013%d" % (y, y + 1)
        return str(y)
    return re.sub(r"\{\{\s*[a-z]{3,5}y\s*\|\s*(\d{4})([^}]*)\}\}", sub, v, flags=re.I)
def parse(text):
    pairs = {}
    for m in re.finditer(r"^\s*\|\s*(years|team)(\d+)\s*=\s*(.*)$", text, flags=re.M):
        kind, n, val = m.group(1), int(m.group(2)), m.group(3)
        pairs.setdefault(n, {})["years" if kind == "years" else "team"] = expand_years(val) if kind == "years" else clean(val)
    out = []
    for n in sorted(pairs):
        d = pairs[n]
        if "team" not in d or "years" not in d: continue
        yrs = clean(d["years"])
        ys = [int(x) for x in re.findall(r"\d{4}", yrs)]
        if not ys: continue
        s = ys[0]; e = ys[-1] if len(ys) > 1 else s + 1
        if "present" in yrs.lower() or re.search(r"[\u2013-]\s*$", yrs): e = 2027
        out.append({"team": d["team"], "s": s, "e": e})
    return out
def accolades(text):
    """All-Star selections, titles and MVPs from the infobox highlights, when listed."""
    def count(pat):
        m = re.search(r"(?:(\d+)\s*[\u00d7x]\s*)?\[\[[^\]]*?(?:%s)[^\]]*\]\]" % pat, text, flags=re.I)
        if not m: return 0
        return int(m.group(1)) if m.group(1) else 1
    return {"as": count(r"All-Stars?"), "ch": count(r"champions\b|champion\b"), "mvp": count(r"Most Valuable Player")}
def main():
    sport = sys.argv[1]
    c = json.loads((HERE / "cache" / f"{sport}.json").read_text())
    outf = HERE / "cache" / f"{sport}-career.json"
    res = json.loads(outf.read_text()) if outf.exists() else {}
    accf = HERE / "cache" / f"{sport}-acc.json"; acc = json.loads(accf.read_text()) if accf.exists() else {}
    items = [(n, r["qid"]) for n, r in c["players"].items() if r and n not in res]
    for i in range(0, len(items), 40):
        ch = items[i:i+40]
        tm = titles_for([q for _, q in ch])
        title2name = {tm.get(q): n for n, q in ch if tm.get(q)}
        for n, q in ch:
            if not tm.get(q): res[n] = []
        texts, redir = wikitext(list(title2name))
        for t, txt in texts.items():
            name = title2name.get(t) or title2name.get(redir.get(t))
            if name: res[name] = parse(txt); acc[name] = accolades(txt)
        for t, n in title2name.items():
            res.setdefault(n, [])
        outf.write_text(json.dumps(res)); accf.write_text(json.dumps(acc))
        print(i + len(ch), "/", len(items), flush=True)
        time.sleep(1)
if __name__ == "__main__": main()
