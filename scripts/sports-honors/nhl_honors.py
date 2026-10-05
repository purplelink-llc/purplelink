#!/usr/bin/env python3
"""NHL career honors for the famous pool: individual trophies and All-Star Team selections counted from the Wikipedia list
pages, Stanley Cup seasons from the franchise and seasons in the player's own stints, Hall of Fame from the infobox.
Writes scripts/sports-honors/nhl.json in the same shape as honors.py."""
import json, pathlib, re, sys, collections
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "sports"))
import honors as H
import franchises

pool = json.loads((HERE.parent / "sports" / "out" / "nhl.json").read_text())["players"]
cache = json.loads((HERE.parent / "sports" / "cache" / "nhl.json").read_text())
qid = {p["name"]: cache["players"][p["name"]]["qid"] for p in pool}
titles = {}
for i in range(0, len(pool), 40):
    chunk = [qid[p["name"]] for p in pool[i:i + 40]]
    t = H.titles_for(chunk)
    titles.update({n: t.get(qid[n]) for n in [p["name"] for p in pool[i:i + 40]]})

PAGES = {  # page: (category, weight)
    "Hart Memorial Trophy": ("mvp", 6), "Conn Smythe Trophy": ("finalsmvp", 3), "Vezina Trophy": ("major", 3), "James Norris Memorial Trophy": ("major", 3),
    "Art Ross Trophy": ("major", 3), "Calder Memorial Trophy": ("major", 3), "Maurice \"Rocket\" Richard Trophy": ("major", 3), "Ted Lindsay Award": ("major", 3),
    "Frank J. Selke Trophy": ("major", 3), "Lady Byng Memorial Trophy": ("minor", 1.5), "NHL All-Star team": ("first", 2.5),
}
texts = {}
for page in PAGES:
    got, redir = H.wikitext([page])
    txt = next(iter(got.values()), "")
    if page == "NHL All-Star team":
        m = re.search(r"==\s*Selections\s*==(.*?)(?=^==\s*Most selections)", txt, flags=re.S | re.M); txt = m.group(1) if m else txt
    else:
        m = re.search(r"^==\s*(Winners|Recipients|Award winners|List of winners)[^=\n]*==", txt, flags=re.M | re.I)
        txt = txt[m.start():] if m else txt[txt.find("{|"):]
        txt = re.split(r"^==\s*(?:See also|Notes|References|External links)", txt, flags=re.M)[0]
    txt = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("[[File:"))
    texts[page] = txt
    print(page, len(txt))

# Stanley Cup winners by season -> franchise id
cup, _ = H.wikitext(["List of Stanley Cup champions"]); ct = next(iter(cup.values()), "")
def fid(label):
    t = label.lower()
    for f, _, pats in franchises.NHL:
        if any(p in t for p in pats): return f
winners = {}
for m in re.finditer(r"\{\{scfy\|(\d{4})\}\}\s*\|\|\s*\[\[(?:\d{4}[–-]\d{2,4} )?([^\]|]+?)(?: season)?(?:\|([^\]]*))?\]\]", ct):
    y = int(m.group(1)); f = fid(m.group(3) or m.group(2))
    if f and y not in winners: winners[y] = f
print("cup winners parsed:", len(winners), "latest", max(winners) if winners else None)

out = {}
for p in pool:
    name = p["name"]; title = titles.get(name) or name
    toks = name.split(); first, last = " ".join(toks[:-1]), toks[-1]
    pat = re.compile(r"\[\[" + re.escape(title) + r"(?:\||\]\])|sortname\|\s*" + re.escape(first) + r"\s*\|\s*" + re.escape(last) + r"\s*[|}]")
    cat = collections.Counter(); score = 0.0
    for page, (c, w) in PAGES.items():
        n = sum(1 for row in re.split(r"^\|-", texts[page], flags=re.M) if pat.search(row))
        if n: cat[c] += n; score += w * (n if n <= 6 else 6 + (n - 6) * 0.5)
    t = sum(1 for f, s, e in p["st"] for y in range(s, e) if winners.get(y + 1) == f)
    if t: cat["title"] = t; score += 1.3 * min(t, 8)
    out[name] = {"raw": {"wiki": title}, "cat": dict(cat), "score": round(score, 1)}
# Hall of Fame from the infobox
for i in range(0, len(pool), 40):
    names = [p["name"] for p in pool[i:i + 40]]
    tx, redir = H.wikitext([titles[n] for n in names if titles.get(n)])
    inv = {titles[n]: n for n in names if titles.get(n)}
    for t, txt in tx.items():
        n = inv.get(t) or inv.get(redir.get(t))
        if n and H.HOF.search(txt): out[n]["cat"]["hof"] = 1; out[n]["score"] = round(out[n]["score"] + 5, 1)
(HERE / "nhl.json").write_text(json.dumps(out, indent=0))
for n in ["Wayne Gretzky", "Connor McDavid", "Mario Lemieux", "Patrick Roy", "Mark Messier", "Sidney Crosby"]:
    if n in out: print(n, out[n]["score"], out[n]["cat"])
print("zero:", sum(1 for v in out.values() if v["score"] == 0), "of", len(out))
