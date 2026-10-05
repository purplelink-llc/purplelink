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

YEAR_TPL = re.compile(r"\{\{\s*(?:nfl year|nfly|mlby|baseball year|nhly|npby|kboy|cfl year|afly|aafcy)\s*\|([^{}]*)\}\}", re.I)
def tpl_years(v):
    """{{NFL Year|1956|1972}} -> 1956-1972 ; {{mlby|1951}} -> 1951 ; other templates are dropped."""
    def sub(m):
        ys = re.findall(r"\d{4}", m.group(1))
        return "%s–%s" % (ys[0], ys[-1]) if len(ys) > 1 else (ys[0] if ys else "")
    return YEAR_TPL.sub(sub, v)
def param_block(text, names):
    """Text of an infobox parameter (first of names found), through its following bullet lines."""
    for nm in names:
        m = re.search(r"^\s*\|\s*%s\s*=(.*)$" % nm, text, flags=re.M | re.I)
        if not m: continue
        start = m.end(); rest = text[start:]
        lines = [m.group(1)]
        for ln in rest.split("\n")[1:]:
            if re.match(r"^\s*\|\s*[A-Za-z_0-9 ]+\s*=", ln) or ln.strip().startswith(("}}", "{{")): break
            lines.append(ln)
        return "\n".join(lines)
    return None
def parse_bullets(text, sport):
    """NFL / MLB: bullet list '* [[Team]] ({{NFL Year|2000|2019}})' inside pastteams/currentteams/teams."""
    names = ["pastteams", "currentteams", "teams"]
    out = []
    final = None
    fy = [int(x) for x in re.findall(r"^\s*\|\s*final\d*year\s*=\s*(\d{4})", text, flags=re.M | re.I)]
    if fy: final = max(fy)
    for nm in names:
        blk = param_block(text, [nm])
        if blk is None: continue
        started = False
        for ln in blk.split("\n"):
            ln = ln.strip()
            if nm.endswith("teams") and not ln.strip("*").strip() and not started: continue
            ln0 = ln
            if "×" in ln or "x [[" in ln or re.search(r"\b(champion|all-star|pro bowl|mvp|award|hall of fame|retired|record|leader)\b", ln, re.I) and not re.search(r"\{\{(?:nfl year|mlby|nfly)", ln, re.I):
                if started: break
                continue
            ln = tpl_years(ln)
            ln = re.sub(r"<ref.*?(</ref>|/>)", "", ln, flags=re.S)
            ln = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", ln)
            mm = re.match(r"^\*?\s*(.*?)\s*\(([^()]*\d{4}[^()]*)\)(\s*\*)?", ln)
            if mm and mm.group(3): continue          # trailing * = offseason / practice squad only, never played
            if not mm:
                if started and ln.startswith("*"): continue
                continue
            label = clean(mm.group(1))
            yrs = mm.group(2)
            if not label or re.search(r"champion|all-star|bowl|mvp", label, re.I): continue
            started = True
            # split multiple stints: '1951–1952, 1954–1972'
            for part in re.split(r"[,;]|\band\b", yrs):
                ys = [int(x) for x in re.findall(r"\d{4}", part)]
                if not ys: continue
                s = ys[0]; e = ys[-1] + 1 if len(ys) > 1 else s + 1
                if "present" in part.lower() or (len(ys) == 1 and re.search(r"[–-]\s*$", part.strip())): e = 2027
                out.append({"team": label, "s": s, "e": e})
    if final:
        out = [dict(x, e=min(x["e"], final + 1)) for x in out if x["s"] <= final]
    return out
def parse_nhl(text):
    """NHL: infobox has no years, so read the career statistics table: rows whose league cell is NHL."""
    i = text.find("areer statistics")
    body = text[i:] if i >= 0 else text
    rows = []
    for chunk in re.split(r"\n\|-[^\n]*", body):
        cells = []
        for ln in chunk.split("\n"):
            ln = ln.strip()
            if not ln.startswith("|") or ln.startswith(("|}", "|+")): continue
            ln = ln[1:]
            for c in ln.split("||"): cells.append(c.strip())
        if len(cells) < 3: continue
        def cl(c):
            c = re.sub(r"^[^|\[\]{}]*\|(?!\|)", "", c) if re.match(r"^\s*(style|colspan|rowspan|align|width)\b", c) else c
            return clean(re.sub(r"<ref.*?(</ref>|/>)", "", c, flags=re.S))
        season, team, league = cl(cells[0]), cl(cells[1]), cl(cells[2])
        ms = re.search(r"(\d{4})\s*[–\-—/]\s*(\d{2,4})", season)
        if not ms: continue
        if league.strip().upper() != "NHL": continue
        rows.append((int(ms.group(1)), team))
    out = []
    by = {}
    for yr, team in sorted(set(rows)): by.setdefault(team, []).append(yr)
    for team, yrs in by.items():
        run = [yrs[0]]
        for y in yrs[1:]:
            if y == run[-1] + 1: run.append(y)
            elif y == run[-1] + 2 and run[-1] == 2003 : run.append(y)   # 2004-05 lockout
            else: out.append({"team": team, "s": run[0], "e": run[-1] + 1}); run = [y]
        out.append({"team": team, "s": run[0], "e": run[-1] + 1})
    # active player whose article table lags a season: extend the current club
    cur = param_block(text, ["team"])
    if out and cur and not re.search(r"^\s*\|\s*career_end\s*=\s*\d", text, flags=re.M):
        cur = clean(cur).lower()
        last = max(out, key=lambda x: x["e"])
        if last["e"] == 2025 and last["team"].lower() in cur: last["e"] = 2026
    return out
def parse_sport(sport, text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    if sport == "nhl": return parse_nhl(text)
    if sport in ("nfl", "mlb"): return parse_bullets(text, sport)
    return parse(text)

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
            if name: res[name] = parse_sport(sport, txt); acc[name] = accolades(txt)
        for t, n in title2name.items():
            res.setdefault(n, [])
        outf.write_text(json.dumps(res)); accf.write_text(json.dumps(acc))
        print(i + len(ch), "/", len(items), flush=True)
        time.sleep(1)
if __name__ == "__main__": main()
