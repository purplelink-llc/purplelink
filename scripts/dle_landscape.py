#!/usr/bin/env python3
"""Sort the 768 games listed at https://dles.aukspot.com/ into build tiers.

  python3 scripts/dle_landscape.py [path/to/dle_cats.json]

The input is the list scraped from that page (category, name, URL). The output is a spreadsheet and a CSV in
docs/games-landscape/. This is keyword sorting on names only, so treat every row as a first guess to be checked,
and none of it is legal advice. Tier 1 = our own code and open or self-made data; Tier 2 = needs licensed or
third-party data, credit, or embeds; Tier 3 = the game is someone else's IP, brand or proprietary content.
"""
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "games-landscape"
LABELS = ["Card/Board Games", "Colors", "Estimation", "Food", "Geography", "History", "Math/Logic", "Movies/TV", "Music", "Science/Nature",
          "Shapes/Patterns", "Novelty", "Sports", "Trivia", "Vehicles", "Video Games", "Miscellaneous", "Words"]

IP = r"pok[eé]|pokle|pokedle|zelda|zeldle|yu-?gi-?oh|ygo|disney|pixar|marvel|star ?wars|swdle|harry ?potter|hogwarts|simpsons?|futurama|seinfeld|breaking ?bad|game of thrones|lord of the rings|tolkien|anime|naruto|one ?piece|dragon ?ball|jojo|genshin|honkai|league of legends|dota|valorant|overwatch|fortnite|minecraft|mario|smash|sonic|kirby|elden|dark ?souls|final ?fantasy|persona|fire ?emblem|hollow ?knight|terraria|stardew|apex legends|halo|destiny|warcraft|diablo|hearthstone|magic: the gathering|mtg|lego|brickdle|costco|taylor swift|beyonc|k-?pop|bts|nba|nfl|mlb|nhl|premier league|formula ?1|wwe|ufc|wordle archive|scrokk|enchant|prince chazz|chessguessr"
PROPRIETARY = r"puzzmo|sporcle|new york times|nyt|boston globe|washington post|guardian|wsj|wall street|edhrec|chess\.com|geoguessr|jeopardy|nytimes|the athletic|npr|seven little words|7 little words|crossword club"
LICENSED = {"Movies/TV": "Titles and facts are fine. Posters, stills and clips need a licensed source (TMDB terms, credit) or none.",
            "Music": "Song facts are fine. Audio only through the provider's embed or preview terms; never host clips.",
            "Sports": "Names and stats are facts. Logos, photos and league marks are not free to use.",
            "Video Games": "Names and facts are fine. Screenshots, art and sprites belong to the publishers; use only openly licensed wiki text.",
            "Vehicles": "Specs are facts. Photos need an open licence (Wikimedia Commons) with credit.",
            "Food": "Recipes' facts are fine. Photos and brand marks need open licences."}

FAMILIES = [
    ("Chess/board puzzle", r"chess|poker|bridge|mahjong|checkers|go |backgammon|cards?\b|solitaire", "Lichess (CC0) for chess; self-made for the rest"),
    ("Crossword / mini", r"cross|mini|fill-?ins|grid ?fill", "Own clues and grids (we have a generator)"),
    ("Grouping / connections", r"connect|categor|group|conexo|couples|link|chain|odd one|sort|set\b", "Own word lists and themes"),
    ("Letter-set / boggle", r"boggle|blossom|hive|spell|anagram|scrabble|word ?search|letter|lexi|honeycomb|bee\b", "Open word list (ENABLE)"),
    ("Semantic similarity", r"contexto|cemantle|semantic|similar", "Open embeddings"),
    ("Cipher / decode", r"crypt|cipher|decod|decipher|cyph|code\b", "Own quotes (public domain)"),
    ("Higher / lower / estimate", r"higher|lower|estimate|guess the (number|price|amount)|price|cost|amount|how (many|much|old|far)|angle|centroid|distance|tradle", "Open statistics (Wikidata, World Bank)"),
    ("Map / flag / place guess", r"where|map|geo|border|flag|country|capital|city|states?\b|worldle|globe|atlas|street|place|spot|landmark", "Natural Earth, Wikidata, Wikimedia Commons"),
    ("Logic grid / number logic", r"sudoku|kakuro|nonogram|mine|bridges|hitori|futoshiki|zebra|logic|hashi|slither|kenken|nurikabe|binary|grid\b|puzzle", "Self-generated (we have a Sudoku generator)"),
    ("Arithmetic target", r"math|equation|nerdle|number|calc|arith|\b24\b|sum|digit", "Self-generated"),
    ("Color match", r"colo|hex|shade|hue|crayon|chroma|dialed", "Self-generated"),
    ("Audio / lyric", r"song|heardle|music|tune|lyric|album|artist|band|sound|audio|melod|chord|note", "Provider embeds only"),
    ("Picture reveal / zoom", r"zoom|blur|pixel|reveal|frame|still|image|photo|poster|logo|emoji", "Openly licensed images only"),
    ("Timeline / ordering", r"year|date|chrono|timeline|order|rank|before|after|era|history", "Wikidata (CC0), open events"),
    ("Trivia / multiple choice", r"trivia|quiz|question|fact|know", "Open Trivia DB, own sets"),
    ("Attribute guess (-dle)", r"dle\b|le\b|guess|who|which|what", "Open dataset with comparable attributes"),
]
ENGINE = {"Attribute guess (-dle)": "Attribute-guess engine (building now)", "Higher / lower / estimate": "Higher-lower engine", "Map / flag / place guess": "Map and flag engine",
          "Grouping / connections": "Grouping engine", "Crossword / mini": "Crossword (live)", "Logic grid / number logic": "Sudoku family (live) + more logic types",
          "Trivia / multiple choice": "Daily Five (live)", "Chess/board puzzle": "Chess (live)", "Picture reveal / zoom": "Zoom-reveal engine", "Timeline / ordering": "Timeline engine",
          "Color match": "Color engine", "Arithmetic target": "Arithmetic engine", "Cipher / decode": "Cipher engine", "Letter-set / boggle": "Letter-set engine",
          "Semantic similarity": "Semantic engine (needs embeddings)", "Audio / lyric": "Skip: audio rights", }


def family(cat, name, url):
    s = (name + " " + url).lower()
    if cat == "Colors":
        return "Color match"
    if cat == "Estimation":
        return "Higher / lower / estimate"
    if cat == "Geography" and not re.search(r"quiz|trivia", s):
        return "Map / flag / place guess"
    if cat == "Music":
        return "Audio / lyric"
    for fam, rx, _ in FAMILIES:
        if fam.startswith("Attribute") and cat in ("Words", "Math/Logic", "Shapes/Patterns", "Miscellaneous", "Novelty"):
            continue
        if re.search(rx, s):
            return fam
    if cat in ("Movies/TV", "Video Games", "Sports", "Vehicles", "Food", "Science/Nature"):
        return "Attribute guess (-dle)"
    if cat == "Words":
        return "Grid guess (Wordle-like)" if re.search(r"dle\b|le\b|word", s) else "Word puzzle (other)"
    return "Other"


def data_note(fam):
    for f, _, note in FAMILIES:
        if f == fam:
            return note
    return "Self-generated" if fam.startswith(("Grid guess", "Word puzzle")) else "Check case by case"


def tier(cat, name, url, fam):
    s = (name + " " + url).lower()
    if re.search(PROPRIETARY, s):
        return 3, "Proprietary publisher content or brand. Rebuild the idea under our own name if at all; never copy their puzzles."
    if re.search(IP, s):
        return 3, "Built around someone's characters, brand or league. The mechanic is free; the content is not."
    if fam == "Audio / lyric":
        return 2, LICENSED["Music"]
    if cat in LICENSED:
        return 2, LICENSED[cat]
    return 1, "Mechanic is free to rebuild. Use our own code, art, wording and an open or self-made data set."


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "games-data" / "dle-list.json"
    cats = json.loads(src.read_text())
    rows = []
    for label, (_, items) in zip(LABELS, cats):
        for url, name in items:
            fam = family(label, name, url)
            t, note = tier(label, name, url, fam)
            eng = ENGINE.get(fam, "Grid-guess family (Linkle/Quadlink live)" if fam.startswith(("Grid guess", "Word puzzle")) else "Case by case")
            rows.append({"Game": name, "URL": url, "Category": label, "Tier": t, "Mechanic family": fam, "Data we would use": data_note(fam), "Engine / what we have": eng, "Note": note})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "dle-landscape.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); ws = wb.active; ws.title = "Games"
    ws.append(list(rows[0]))
    for r in rows:
        ws.append(list(r.values()))
    fills = {1: "D8F0D2", 2: "FFF1C2", 3: "F6D3D3"}
    for c in ws[1]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="E4DDF5")
    for row in ws.iter_rows(min_row=2):
        row[3].fill = PatternFill("solid", fgColor=fills[row[3].value])
        row[1].hyperlink = row[1].value
    for col, width in zip("ABCDEFGH", (34, 44, 17, 6, 26, 40, 38, 80)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    # summary
    sm = wb.create_sheet("Summary", 0)
    sm.append(["Category", "Games", "Tier 1", "Tier 2", "Tier 3"])
    for lab in LABELS:
        sub = [r for r in rows if r["Category"] == lab]
        sm.append([lab, len(sub)] + [sum(1 for r in sub if r["Tier"] == t) for t in (1, 2, 3)])
    sm.append(["Total", len(rows)] + [sum(1 for r in rows if r["Tier"] == t) for t in (1, 2, 3)])
    sm.append([]); sm.append(["Mechanic family", "Games", "Tier 1"])
    fams = sorted({r["Mechanic family"] for r in rows}, key=lambda f: -sum(1 for r in rows if r["Mechanic family"] == f))
    for f in fams:
        sub = [r for r in rows if r["Mechanic family"] == f]
        sm.append([f, len(sub), sum(1 for r in sub if r["Tier"] == 1)])
    for c in sm[1]:
        c.font = Font(bold=True)
    sm.column_dimensions["A"].width = 34
    # rules
    ru = wb.create_sheet("Read me")
    for line in [
        "Source list: https://dles.aukspot.com/ (768 games, scraped 2026-10-04). It is a directory of other people's sites.",
        "Tiers come from keyword rules on names and categories only. Every row is a first guess. This is not legal advice.",
        "Tier 1: rebuild with our own code, art, wording and an open or self-made data set. Game rules and mechanics are not copyrightable.",
        "Tier 2: the mechanic is free, the data or media needs a licence, credit or an embed.",
        "Tier 3: the game is someone's IP, brand or proprietary content. Skip, or rebuild only the bare idea under our own name.",
        "Always: our own names (no 'Wordle', 'Connections', 'Strands'), our own code and look, no copied datasets, credit CC BY-SA sources.",
        "Many games are variants of a few dozen mechanics, so build engines, not 768 games. See the Mechanic family table on Summary.",
        "Quality matters for ad approval: many near-identical thin pages are a risk. Fewer, richer games are better.",
    ]:
        ru.append([line])
    ru.column_dimensions["A"].width = 140
    wb.save(OUT / "dle-landscape.xlsx")
    print(len(rows), "games;", {t: sum(1 for r in rows if r["Tier"] == t) for t in (1, 2, 3)})
    for f in fams[:14]:
        print(f"  {f:34} {sum(1 for r in rows if r['Mechanic family'] == f)}")


if __name__ == "__main__":
    main()
