#!/usr/bin/env python3
"""Fetch and snapshot the open data behind the attribute-guess games (Landlink, Atomlink, Prizelink).

  python3 scripts/build_attr_data.py            # needs curl and network; writes scripts/games-data/attr/*.json

Sources (all open):
  Natural Earth admin-0 countries (public domain) + Wikidata (CC0) for area, capital and driving side  -> countries.json
  PubChem periodic table (US government, public domain)                                                -> elements.json
  Nobel Prize API v2.1 (CC0) + Wikidata sitelink counts as a "how well known" measure                  -> laureates.json
  Natural Earth populated places (public domain)                                                       -> cities.json
  Wikidata mountains (CC0)                                                                              -> peaks.json
  Programming languages: a hand-written table in this file (our own facts)                             -> languages.json
The snapshots are committed; gen_games.py builds the site data from them and never touches the network.
"""
import csv, io, json, subprocess, sys, urllib.parse
from pathlib import Path

OUT = Path(__file__).resolve().parent / "games-data" / "attr"
UA = "PurplelinkGames/1.0 (ben@purplelink.llc)"


def curl(url, *extra):
    return subprocess.run(["curl", "-sL", "-m", "120", "-H", f"User-Agent: {UA}", *extra, url], capture_output=True, text=True, check=True).stdout


def sparql(q):
    return json.loads(subprocess.run(["curl", "-s", "-m", "120", "-X", "POST", "https://query.wikidata.org/sparql", "-H", f"User-Agent: {UA}", "-H", "Accept: application/sparql-results+json",
                                      "--data-urlencode", "format=json", "--data-urlencode", "query=" + q], capture_output=True, text=True, check=True).stdout)["results"]["bindings"]


# ---------------- countries ----------------
RENAME = {"Dem. Rep. Congo": "DR Congo", "Congo": "Republic of the Congo", "Central African Rep.": "Central African Republic", "Bosnia and Herz.": "Bosnia and Herzegovina",
          "Dominican Rep.": "Dominican Republic", "Eq. Guinea": "Equatorial Guinea", "S. Sudan": "South Sudan", "Solomon Is.": "Solomon Islands", "eSwatini": "Eswatini",
          "Czechia": "Czechia", "United States of America": "United States", "Timor-Leste": "Timor-Leste", "Côte d'Ivoire": "Ivory Coast", "N. Macedonia": "North Macedonia",
          "Myanmar": "Myanmar", "Palestine": "Palestine", "Taiwan": "Taiwan"}
LANDLOCKED = set("AFG AND ARM AUT AZE BLR BTN BOL BWA BFA BDI CAF TCD CZE SWZ ETH HUN KAZ KGZ LAO LSO LIE LUX MWI MLI MDA MNG NPL NER MKD PRY RWA SMR SRB SVK SDS CHE TJK TKM UGA UZB VAT ZMB ZWE".split())
DROP = {"W. Sahara", "Falkland Is.", "Fr. S. Antarctic Lands", "Puerto Rico", "New Caledonia", "Antarctica", "N. Cyprus", "Somaliland", "Greenland", "Kosovo"}


def countries():
    ne = json.loads(curl("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"))
    wd = {}
    for r in sparql("""SELECT ?iso ?area ?side ?capLabel WHERE { ?c wdt:P298 ?iso . { ?c wdt:P31 wd:Q3624078 } UNION { ?c wdt:P31 wd:Q6256 }
      OPTIONAL { ?c wdt:P2046 ?area } OPTIONAL { ?c wdt:P1622 ?s . ?s rdfs:label ?side FILTER(LANG(?side)="en") } OPTIONAL { ?c wdt:P36 ?cap }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""):
        o = wd.setdefault(r["iso"]["value"], {})
        if "area" in r: o["area"] = float(r["area"]["value"])
        if "side" in r: o["side"] = r["side"]["value"]
        if "capLabel" in r: o["cap"] = r["capLabel"]["value"]
    rows = []
    for f in ne["features"]:
        p = f["properties"]
        if p["NAME"] in DROP:
            continue
        iso = p["ISO_A3"] if p["ISO_A3"] != "-99" else p["ADM0_A3"]
        w = wd.get(iso, {}) or wd.get(p["ADM0_A3"], {})
        name = RENAME.get(p["NAME"], p["NAME"])
        if not w.get("area") or not w.get("side"):
            print("  missing wikidata for", name, iso, file=sys.stderr)
        income = p["INCOME_GRP"].split(". ", 1)[-1]
        rows.append({"name": name, "alt": sorted({p["NAME_LONG"], p["ABBREV"], p["NAME"], p["FORMAL_EN"] or ""} - {"", name}),
                     "continent": p["CONTINENT"], "subregion": p["SUBREGION"], "pop": int(p["POP_EST"]), "area": round(w.get("area", 0)) or None,
                     "coast": "Landlocked" if (iso in LANDLOCKED or p["ADM0_A3"] in LANDLOCKED) else "Coastal", "side": (w.get("side") or "").capitalize() or None,
                     "income": income, "gdp": p["GDP_MD"]})
    rows.sort(key=lambda r: r["name"])
    return rows


# ---------------- elements ----------------
PERIOD_END = [2, 10, 18, 36, 54, 86, 118]


def elements():
    text = curl("https://pubchem.ncbi.nlm.nih.gov/rest/pug/periodictable/CSV")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        z = int(r["AtomicNumber"])
        period = next(i + 1 for i, e in enumerate(PERIOD_END) if z <= e)
        year = r["YearDiscovered"]
        rows.append({"name": r["Name"], "sym": r["Symbol"], "z": z, "period": period, "cat": r["GroupBlock"], "state": r["StandardState"] or "Unknown",
                     "mass": round(float(r["AtomicMass"]), 3), "year": -1500 if year == "Ancient" else int(year) if year.isdigit() else None,
                     "ancient": year == "Ancient"})
    return rows


# ---------------- Nobel laureates ----------------
def laureates():
    data = json.loads(curl("https://api.nobelprize.org/2.1/laureates?limit=1200&offset=0"))["laureates"]
    people = [l for l in data if l.get("gender") and "knownName" in l and l.get("nobelPrizes") and l.get("birth", {}).get("year", "").isdigit()]
    ids = [l["wikidata"]["id"] for l in people if l.get("wikidata")]
    links = {}
    for i in range(0, len(ids), 250):
        chunk = " ".join("wd:" + x for x in ids[i:i + 250])
        for r in sparql("SELECT ?p ?n WHERE { VALUES ?p { %s } ?p wikibase:sitelinks ?n }" % chunk):
            links[r["p"]["value"].rsplit("/", 1)[-1]] = int(r["n"]["value"])
    rows = []
    for l in people:
        pz = l["nobelPrizes"][0]
        place = l["birth"].get("place", {})
        by = int(l["birth"]["year"]); ay = int(pz["awardYear"])
        country = (place.get("countryNow") or place.get("country") or {}).get("en")
        cont = (place.get("continent") or {}).get("en")
        if not country or not cont:
            continue
        rows.append({"name": l["knownName"]["en"], "field": pz["category"]["en"], "year": ay, "born": by, "age": ay - by, "continent": cont, "country": country,
                     "gender": l["gender"].capitalize(), "shared": pz.get("portion", "1") != "1", "fame": links.get(l.get("wikidata", {}).get("id", ""), 0),
                     "prizes": len(l["nobelPrizes"])})
    rows.sort(key=lambda r: (-r["fame"], r["name"]))
    return rows



# ---------------- cities (Natural Earth populated places, public domain) ----------------
def country_lookup():
    ne = json.loads(curl("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"))
    by_a3, by_name = {}, {}
    for f in ne["features"]:
        p = f["properties"]
        info = {"continent": p["CONTINENT"], "name": RENAME.get(p["NAME"], p["NAME"])}
        for k in ("ADM0_A3", "ISO_A3", "SOV_A3", "GU_A3"):
            if p.get(k) and p[k] != "-99":
                by_a3[p[k]] = info
        for k in ("NAME", "NAME_LONG", "FORMAL_EN", "ABBREV", "NAME_SORT", "ADMIN"):
            if p.get(k):
                by_name[p[k].lower()] = info
    return by_a3, by_name


def cities():
    pp = json.loads(curl("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson"))["features"]
    by_a3, by_name = country_lookup()
    rows, seen = [], {}
    for f in sorted(pp, key=lambda f: -(f["properties"].get("pop_max") or 0)):
        p = f["properties"]
        if len(rows) >= 700:
            break
        c = by_a3.get(p["adm0_a3"]) or by_a3.get(p["sov_a3"]) or by_name.get((p["adm0name"] or "").lower())
        if not c or not p.get("pop_max"):
            continue
        name = p["nameascii"] if p["nameascii"] else p["name"]
        key = name.lower()
        if key in seen:                        # two places with one name: keep the bigger, label the other with its country
            name = f"{name}, {c['name']}"
            if name.lower() in seen:
                continue
        seen[name.lower()] = 1
        rows.append({"name": name, "alt": [p["name"]] if p["name"] != name else [], "continent": c["continent"], "country": c["name"], "pop": int(p["pop_max"]),
                     "lat": round(p["latitude"], 2), "lon": round(p["longitude"], 2), "capital": p["adm0cap"] == 1})
    return rows


# ---------------- mountains (Wikidata, CC0) ----------------
def peaks():
    by_a3, by_name = country_lookup()
    alias = {"people's republic of china": "china", "russian federation": "russia", "united states": "united states of america", "kingdom of the netherlands": "netherlands",
             "democratic republic of the congo": "dem. rep. congo", "czech republic": "czechia", "republic of china": "taiwan", "myanmar": "myanmar"}
    data = sparql("""SELECT ?m ?mLabel ?n ?elev ?countryLabel ?lat ?lon ?vol WHERE {
      ?m wdt:P31 wd:Q8502 . ?m wikibase:sitelinks ?n . FILTER(?n > 40) ?m wdt:P2044 ?elev . ?m wdt:P625 ?co .
      OPTIONAL { ?m wdt:P17 ?country } OPTIONAL { ?m wdt:P31 ?vt FILTER(?vt = wd:Q8072) BIND(true AS ?vol) }
      BIND(geof:latitude(?co) AS ?lat) BIND(geof:longitude(?co) AS ?lon)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 3000""")
    peaks = {}
    for r in data:
        name = r["mLabel"]["value"]
        if name.startswith("Q") and name[1:].isdigit():
            continue
        o = peaks.setdefault(name, {"name": name, "n": int(r["n"]["value"]), "elev": float(r["elev"]["value"]), "countries": set(), "lat": float(r["lat"]["value"]),
                                    "lon": float(r["lon"]["value"]), "volcano": False})
        if "countryLabel" in r:
            c = r["countryLabel"]["value"]
            o["countries"].add(by_name.get(alias.get(c.lower(), c.lower()), {}).get("name") or c)
        if "vol" in r:
            o["volcano"] = True
    rows = []
    for o in sorted(peaks.values(), key=lambda o: -o["n"]):
        cs = sorted(o["countries"])
        info = [by_name.get(c.lower()) for c in cs]
        conts = sorted({i["continent"] for i in info if i})
        if not cs or not conts:
            continue
        rows.append({"name": o["name"], "continent": conts[0], "countries": cs, "elev": round(o["elev"]), "lat": round(o["lat"], 2), "lon": round(o["lon"], 2),
                     "volcano": o["volcano"], "fame": o["n"]})
    return rows


# ---------------- programming languages (curated here) ----------------
# name, first appeared, typing, how it runs, memory, domain, paradigms
LANGS = [
    ("Ada", 1983, "Static", "Compiled", "Manual", "Embedded and safety", "Procedural,Object-oriented"),
    ("ALGOL", 1958, "Static", "Compiled", "Manual", "Academic", "Procedural"),
    ("APL", 1966, "Dynamic", "Interpreted", "Garbage collected", "Data and science", "Functional,Procedural"),
    ("Assembly", 1949, "None", "Compiled", "Manual", "Systems", "Procedural"),
    ("Awk", 1977, "Dynamic", "Interpreted", "Garbage collected", "Scripting", "Procedural,Declarative"),
    ("Bash", 1989, "Dynamic", "Interpreted", "Garbage collected", "Scripting", "Procedural"),
    ("BASIC", 1964, "Dynamic", "Interpreted", "Garbage collected", "Education", "Procedural"),
    ("C", 1972, "Static", "Compiled", "Manual", "Systems", "Procedural"),
    ("C++", 1985, "Static", "Compiled", "Manual", "Systems", "Procedural,Object-oriented,Functional"),
    ("C#", 2000, "Static", "Virtual machine", "Garbage collected", "Enterprise and apps", "Object-oriented,Functional,Procedural"),
    ("Clojure", 2007, "Dynamic", "Virtual machine", "Garbage collected", "General purpose", "Functional"),
    ("COBOL", 1959, "Static", "Compiled", "Manual", "Enterprise and apps", "Procedural,Object-oriented"),
    ("CoffeeScript", 2009, "Dynamic", "Interpreted", "Garbage collected", "Web", "Object-oriented,Functional"),
    ("Crystal", 2014, "Static", "Compiled", "Garbage collected", "General purpose", "Object-oriented"),
    ("D", 2001, "Static", "Compiled", "Garbage collected", "Systems", "Procedural,Object-oriented,Functional"),
    ("Dart", 2011, "Static", "Virtual machine", "Garbage collected", "Mobile and web", "Object-oriented"),
    ("Delphi", 1995, "Static", "Compiled", "Manual", "Enterprise and apps", "Procedural,Object-oriented"),
    ("Eiffel", 1986, "Static", "Compiled", "Garbage collected", "Academic", "Object-oriented"),
    ("Elixir", 2011, "Dynamic", "Virtual machine", "Garbage collected", "Web", "Functional"),
    ("Elm", 2012, "Static", "Interpreted", "Garbage collected", "Web", "Functional"),
    ("Erlang", 1986, "Dynamic", "Virtual machine", "Garbage collected", "Telecom and servers", "Functional"),
    ("F#", 2005, "Static", "Virtual machine", "Garbage collected", "General purpose", "Functional,Object-oriented"),
    ("Forth", 1970, "None", "Interpreted", "Manual", "Embedded and safety", "Procedural"),
    ("Fortran", 1957, "Static", "Compiled", "Manual", "Data and science", "Procedural,Object-oriented"),
    ("Go", 2009, "Static", "Compiled", "Garbage collected", "Servers and cloud", "Procedural"),
    ("Groovy", 2003, "Dynamic", "Virtual machine", "Garbage collected", "Scripting", "Object-oriented,Functional"),
    ("Hack", 2014, "Static", "Virtual machine", "Garbage collected", "Web", "Object-oriented"),
    ("Haskell", 1990, "Static", "Compiled", "Garbage collected", "Academic", "Functional"),
    ("Haxe", 2005, "Static", "Compiled", "Garbage collected", "Mobile and web", "Object-oriented"),
    ("Java", 1995, "Static", "Virtual machine", "Garbage collected", "Enterprise and apps", "Object-oriented"),
    ("JavaScript", 1995, "Dynamic", "Interpreted", "Garbage collected", "Web", "Object-oriented,Functional,Procedural"),
    ("Julia", 2012, "Dynamic", "Compiled", "Garbage collected", "Data and science", "Functional,Procedural"),
    ("Kotlin", 2011, "Static", "Virtual machine", "Garbage collected", "Mobile and web", "Object-oriented,Functional"),
    ("Lisp", 1958, "Dynamic", "Interpreted", "Garbage collected", "Academic", "Functional,Procedural"),
    ("Logo", 1967, "Dynamic", "Interpreted", "Garbage collected", "Education", "Functional,Procedural"),
    ("Lua", 1993, "Dynamic", "Interpreted", "Garbage collected", "Scripting", "Procedural,Object-oriented,Functional"),
    ("MATLAB", 1984, "Dynamic", "Interpreted", "Garbage collected", "Data and science", "Procedural,Object-oriented"),
    ("Mojo", 2023, "Static", "Compiled", "Manual", "Data and science", "Procedural,Object-oriented"),
    ("Nim", 2008, "Static", "Compiled", "Garbage collected", "Systems", "Procedural,Object-oriented,Functional"),
    ("Objective-C", 1984, "Static", "Compiled", "Reference counted", "Mobile and web", "Object-oriented"),
    ("OCaml", 1996, "Static", "Compiled", "Garbage collected", "Academic", "Functional,Object-oriented"),
    ("Pascal", 1970, "Static", "Compiled", "Manual", "Education", "Procedural"),
    ("Perl", 1987, "Dynamic", "Interpreted", "Reference counted", "Scripting", "Procedural,Object-oriented,Functional"),
    ("PHP", 1995, "Dynamic", "Interpreted", "Reference counted", "Web", "Procedural,Object-oriented"),
    ("PowerShell", 2006, "Dynamic", "Interpreted", "Garbage collected", "Scripting", "Procedural,Object-oriented"),
    ("Prolog", 1972, "Dynamic", "Interpreted", "Garbage collected", "Academic", "Declarative"),
    ("Python", 1991, "Dynamic", "Interpreted", "Reference counted", "Data and science", "Procedural,Object-oriented,Functional"),
    ("R", 1993, "Dynamic", "Interpreted", "Garbage collected", "Data and science", "Functional,Procedural"),
    ("Racket", 1995, "Dynamic", "Virtual machine", "Garbage collected", "Academic", "Functional"),
    ("Ruby", 1995, "Dynamic", "Interpreted", "Garbage collected", "Web", "Object-oriented,Functional"),
    ("Rust", 2010, "Static", "Compiled", "Ownership", "Systems", "Procedural,Functional"),
    ("Scala", 2004, "Static", "Virtual machine", "Garbage collected", "General purpose", "Functional,Object-oriented"),
    ("Scheme", 1975, "Dynamic", "Interpreted", "Garbage collected", "Academic", "Functional"),
    ("Simula", 1962, "Static", "Compiled", "Garbage collected", "Academic", "Object-oriented,Procedural"),
    ("Smalltalk", 1972, "Dynamic", "Virtual machine", "Garbage collected", "Education", "Object-oriented"),
    ("Solidity", 2014, "Static", "Virtual machine", "Manual", "Blockchain", "Object-oriented"),
    ("SQL", 1974, "Static", "Interpreted", "Garbage collected", "Data and science", "Declarative"),
    ("Swift", 2014, "Static", "Compiled", "Reference counted", "Mobile and web", "Object-oriented,Functional,Procedural"),
    ("Tcl", 1988, "Dynamic", "Interpreted", "Reference counted", "Scripting", "Procedural"),
    ("TypeScript", 2012, "Static", "Interpreted", "Garbage collected", "Web", "Object-oriented,Functional"),
    ("Verilog", 1984, "Static", "Interpreted", "Manual", "Embedded and safety", "Declarative"),
    ("Visual Basic", 1991, "Static", "Virtual machine", "Reference counted", "Enterprise and apps", "Procedural,Object-oriented"),
    ("Zig", 2016, "Static", "Compiled", "Manual", "Systems", "Procedural"),
]


def languages():
    return [{"name": n, "year": y, "typing": t, "runs": r, "memory": m, "domain": d, "paradigms": p.split(","), "well": n in WELL_KNOWN_LANGS} for n, y, t, r, m, d, p in LANGS]


WELL_KNOWN_LANGS = {"Assembly", "Bash", "BASIC", "C", "C++", "C#", "COBOL", "Dart", "Elixir", "Erlang", "Fortran", "Go", "Haskell", "Java", "JavaScript", "Julia", "Kotlin", "Lisp",
                    "Lua", "MATLAB", "Objective-C", "OCaml", "Pascal", "Perl", "PHP", "PowerShell", "Prolog", "Python", "R", "Ruby", "Rust", "Scala", "Scheme", "Smalltalk", "SQL",
                    "Swift", "TypeScript", "Visual Basic", "Zig", "Clojure", "Ada", "Delphi", "Racket", "F#", "Groovy", "Nim", "Solidity"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("countries", countries), ("elements", elements), ("laureates", laureates), ("cities", cities), ("peaks", peaks), ("languages", languages)):
        rows = fn()
        (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        print(name, len(rows))


if __name__ == "__main__":
    main()
