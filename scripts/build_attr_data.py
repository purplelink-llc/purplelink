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


# ---------------- scientists (curated here) ----------------
# name, field, born, died (None if living), country of birth as named today, gender
SCI = [
    ("Albert Einstein", "Physics", 1879, 1955, "Germany", "Male"), ("Isaac Newton", "Physics", 1643, 1727, "United Kingdom", "Male"), ("Marie Curie", "Physics", 1867, 1934, "Poland", "Female"),
    ("Niels Bohr", "Physics", 1885, 1962, "Denmark", "Male"), ("Max Planck", "Physics", 1858, 1947, "Germany", "Male"), ("Richard Feynman", "Physics", 1918, 1988, "United States", "Male"),
    ("Stephen Hawking", "Physics", 1942, 2018, "United Kingdom", "Male"), ("Galileo Galilei", "Physics", 1564, 1642, "Italy", "Male"), ("Michael Faraday", "Physics", 1791, 1867, "United Kingdom", "Male"),
    ("James Clerk Maxwell", "Physics", 1831, 1879, "United Kingdom", "Male"), ("Erwin Schr\u00f6dinger", "Physics", 1887, 1961, "Austria", "Male"), ("Werner Heisenberg", "Physics", 1901, 1976, "Germany", "Male"),
    ("Enrico Fermi", "Physics", 1901, 1954, "Italy", "Male"), ("J. Robert Oppenheimer", "Physics", 1904, 1967, "United States", "Male"), ("Paul Dirac", "Physics", 1902, 1984, "United Kingdom", "Male"),
    ("Ernest Rutherford", "Physics", 1871, 1937, "New Zealand", "Male"), ("Lise Meitner", "Physics", 1878, 1968, "Austria", "Female"), ("Nikola Tesla", "Physics", 1856, 1943, "Croatia", "Male"),
    ("Heinrich Hertz", "Physics", 1857, 1894, "Germany", "Male"), ("Lord Kelvin", "Physics", 1824, 1907, "United Kingdom", "Male"), ("Blaise Pascal", "Physics", 1623, 1662, "France", "Male"),
    ("Christiaan Huygens", "Physics", 1629, 1695, "Netherlands", "Male"), ("Alessandro Volta", "Physics", 1745, 1827, "Italy", "Male"), ("Andr\u00e9-Marie Amp\u00e8re", "Physics", 1775, 1836, "France", "Male"),
    ("Georg Ohm", "Physics", 1789, 1854, "Germany", "Male"), ("Wilhelm R\u00f6ntgen", "Physics", 1845, 1923, "Germany", "Male"), ("Max Born", "Physics", 1882, 1970, "Poland", "Male"),
    ("Wolfgang Pauli", "Physics", 1900, 1958, "Austria", "Male"), ("Murray Gell-Mann", "Physics", 1929, 2019, "United States", "Male"), ("Peter Higgs", "Physics", 1929, 2024, "United Kingdom", "Male"),
    ("Kip Thorne", "Physics", 1940, None, "United States", "Male"), ("Roger Penrose", "Physics", 1931, None, "United Kingdom", "Male"), ("Chien-Shiung Wu", "Physics", 1912, 1997, "China", "Female"),
    ("Antoine Lavoisier", "Chemistry", 1743, 1794, "France", "Male"), ("Dmitri Mendeleev", "Chemistry", 1834, 1907, "Russia", "Male"), ("Linus Pauling", "Chemistry", 1901, 1994, "United States", "Male"),
    ("Rosalind Franklin", "Chemistry", 1920, 1958, "United Kingdom", "Female"), ("Robert Boyle", "Chemistry", 1627, 1691, "Ireland", "Male"), ("John Dalton", "Chemistry", 1766, 1844, "United Kingdom", "Male"),
    ("Joseph Priestley", "Chemistry", 1733, 1804, "United Kingdom", "Male"), ("Humphry Davy", "Chemistry", 1778, 1829, "United Kingdom", "Male"), ("Svante Arrhenius", "Chemistry", 1859, 1927, "Sweden", "Male"),
    ("Fritz Haber", "Chemistry", 1868, 1934, "Poland", "Male"), ("Dorothy Hodgkin", "Chemistry", 1910, 1994, "Egypt", "Female"), ("J\u00f6ns Jacob Berzelius", "Chemistry", 1779, 1848, "Sweden", "Male"),
    ("Frederick Sanger", "Chemistry", 1918, 2013, "United Kingdom", "Male"), ("Jennifer Doudna", "Chemistry", 1964, None, "United States", "Female"), ("Ahmed Zewail", "Chemistry", 1946, 2016, "Egypt", "Male"),
    ("Charles Darwin", "Biology", 1809, 1882, "United Kingdom", "Male"), ("Gregor Mendel", "Biology", 1822, 1884, "Czechia", "Male"), ("Louis Pasteur", "Biology", 1822, 1895, "France", "Male"),
    ("Carl Linnaeus", "Biology", 1707, 1778, "Sweden", "Male"), ("Jane Goodall", "Biology", 1934, 2025, "United Kingdom", "Female"), ("Rachel Carson", "Biology", 1907, 1964, "United States", "Female"),
    ("Alexander Fleming", "Biology", 1881, 1955, "United Kingdom", "Male"), ("Francis Crick", "Biology", 1916, 2004, "United Kingdom", "Male"), ("James Watson", "Biology", 1928, 2025, "United States", "Male"),
    ("Barbara McClintock", "Biology", 1902, 1992, "United States", "Female"), ("E. O. Wilson", "Biology", 1929, 2021, "United States", "Male"), ("Richard Dawkins", "Biology", 1941, None, "Kenya", "Male"),
    ("Alfred Russel Wallace", "Biology", 1823, 1913, "United Kingdom", "Male"), ("Jean-Baptiste Lamarck", "Biology", 1744, 1829, "France", "Male"), ("Alexander von Humboldt", "Biology", 1769, 1859, "Germany", "Male"),
    ("Robert Hooke", "Biology", 1635, 1703, "United Kingdom", "Male"), ("Antonie van Leeuwenhoek", "Biology", 1632, 1723, "Netherlands", "Male"), ("Ivan Pavlov", "Biology", 1849, 1936, "Russia", "Male"),
    ("Edward Jenner", "Medicine", 1749, 1823, "United Kingdom", "Male"), ("Joseph Lister", "Medicine", 1827, 1912, "United Kingdom", "Male"), ("Robert Koch", "Medicine", 1843, 1910, "Germany", "Male"),
    ("Jonas Salk", "Medicine", 1914, 1995, "United States", "Male"), ("William Harvey", "Medicine", 1578, 1657, "United Kingdom", "Male"), ("Andreas Vesalius", "Medicine", 1514, 1564, "Belgium", "Male"),
    ("Paul Ehrlich", "Medicine", 1854, 1915, "Poland", "Male"), ("Santiago Ram\u00f3n y Cajal", "Medicine", 1852, 1934, "Spain", "Male"), ("Elizabeth Blackwell", "Medicine", 1821, 1910, "United Kingdom", "Female"),
    ("Carl Friedrich Gauss", "Mathematics", 1777, 1855, "Germany", "Male"), ("Leonhard Euler", "Mathematics", 1707, 1783, "Switzerland", "Male"), ("Pierre de Fermat", "Mathematics", 1607, 1665, "France", "Male"),
    ("Ren\u00e9 Descartes", "Mathematics", 1596, 1650, "France", "Male"), ("Bernhard Riemann", "Mathematics", 1826, 1866, "Germany", "Male"), ("Srinivasa Ramanujan", "Mathematics", 1887, 1920, "India", "Male"),
    ("Emmy Noether", "Mathematics", 1882, 1935, "Germany", "Female"), ("Kurt G\u00f6del", "Mathematics", 1906, 1978, "Czechia", "Male"), ("David Hilbert", "Mathematics", 1862, 1943, "Russia", "Male"),
    ("\u00c9variste Galois", "Mathematics", 1811, 1832, "France", "Male"), ("Georg Cantor", "Mathematics", 1845, 1918, "Russia", "Male"), ("Henri Poincar\u00e9", "Mathematics", 1854, 1912, "France", "Male"),
    ("John von Neumann", "Mathematics", 1903, 1957, "Hungary", "Male"), ("Andrew Wiles", "Mathematics", 1953, None, "United Kingdom", "Male"), ("Terence Tao", "Mathematics", 1975, None, "Australia", "Male"),
    ("Maryam Mirzakhani", "Mathematics", 1977, 2017, "Iran", "Female"), ("Joseph-Louis Lagrange", "Mathematics", 1736, 1813, "Italy", "Male"), ("Pierre-Simon Laplace", "Mathematics", 1749, 1827, "France", "Male"),
    ("Sophie Germain", "Mathematics", 1776, 1831, "France", "Female"), ("Katherine Johnson", "Mathematics", 1918, 2020, "United States", "Female"), ("Paul Erd\u0151s", "Mathematics", 1913, 1996, "Hungary", "Male"),
    ("Nicolaus Copernicus", "Astronomy", 1473, 1543, "Poland", "Male"), ("Johannes Kepler", "Astronomy", 1571, 1630, "Germany", "Male"), ("Tycho Brahe", "Astronomy", 1546, 1601, "Sweden", "Male"),
    ("Edwin Hubble", "Astronomy", 1889, 1953, "United States", "Male"), ("Carl Sagan", "Astronomy", 1934, 1996, "United States", "Male"), ("Edmond Halley", "Astronomy", 1656, 1742, "United Kingdom", "Male"),
    ("William Herschel", "Astronomy", 1738, 1822, "Germany", "Male"), ("Caroline Herschel", "Astronomy", 1750, 1848, "Germany", "Female"), ("Henrietta Swan Leavitt", "Astronomy", 1868, 1921, "United States", "Female"),
    ("Vera Rubin", "Astronomy", 1928, 2016, "United States", "Female"), ("Subrahmanyan Chandrasekhar", "Astronomy", 1910, 1995, "Pakistan", "Male"), ("Neil deGrasse Tyson", "Astronomy", 1958, None, "United States", "Male"),
    ("Annie Jump Cannon", "Astronomy", 1863, 1941, "United States", "Female"), ("Cecilia Payne-Gaposchkin", "Astronomy", 1900, 1979, "United Kingdom", "Female"), ("Georges Lema\u00eetre", "Astronomy", 1894, 1966, "Belgium", "Male"),
    ("Giovanni Cassini", "Astronomy", 1625, 1712, "Italy", "Male"),
    ("Alan Turing", "Computer science", 1912, 1954, "United Kingdom", "Male"), ("Grace Hopper", "Computer science", 1906, 1992, "United States", "Female"), ("Ada Lovelace", "Computer science", 1815, 1852, "United Kingdom", "Female"),
    ("Charles Babbage", "Computer science", 1791, 1871, "United Kingdom", "Male"), ("Claude Shannon", "Computer science", 1916, 2001, "United States", "Male"), ("Tim Berners-Lee", "Computer science", 1955, None, "United Kingdom", "Male"),
    ("Linus Torvalds", "Computer science", 1969, None, "Finland", "Male"), ("Donald Knuth", "Computer science", 1938, None, "United States", "Male"), ("Dennis Ritchie", "Computer science", 1941, 2011, "United States", "Male"),
    ("John McCarthy", "Computer science", 1927, 2011, "United States", "Male"), ("Margaret Hamilton", "Computer science", 1936, None, "United States", "Female"), ("Vint Cerf", "Computer science", 1943, None, "United States", "Male"),
    ("Edsger Dijkstra", "Computer science", 1930, 2002, "Netherlands", "Male"), ("Barbara Liskov", "Computer science", 1939, None, "United States", "Female"), ("Geoffrey Hinton", "Computer science", 1947, None, "United Kingdom", "Male"),
    ("Alfred Wegener", "Earth science", 1880, 1930, "Germany", "Male"), ("Mary Anning", "Earth science", 1799, 1847, "United Kingdom", "Female"), ("Charles Lyell", "Earth science", 1797, 1875, "United Kingdom", "Male"),
    ("Inge Lehmann", "Earth science", 1888, 1993, "Denmark", "Female"),
]


def scientists():
    by_a3, by_name = country_lookup()
    alias = {"united states": "united states of america", "united kingdom": "united kingdom", "czechia": "czechia"}
    rows = []
    for n, f, b, d, c, g in SCI:
        info = by_name.get(alias.get(c.lower(), c.lower()))
        if not info:
            print("  no continent for", c, file=sys.stderr)
            continue
        rows.append({"name": n.encode().decode("unicode_escape") if "\\u" in n else n, "field": f, "born": b, "life": (d - b) if d else None, "country": info["name"], "continent": info["continent"], "gender": g, "fame": 0})
    return rows


# ---------------- rivers (Wikidata, CC0) ----------------
def rivers():
    by_a3, by_name = country_lookup()
    alias = {"people's republic of china": "china", "united states": "united states of america", "russian federation": "russia", "czech republic": "czechia",
             "democratic republic of the congo": "dem. rep. congo", "republic of the congo": "congo"}
    data = sparql("""SELECT ?r ?rLabel ?n ?len ?cLabel ?mouthLabel ?lat ?lon WHERE {
      ?r wdt:P31 wd:Q4022 ; wikibase:sitelinks ?n . FILTER(?n > 45) ?r wdt:P2043 ?len .
      OPTIONAL { ?r wdt:P17 ?c } OPTIONAL { ?r wdt:P403 ?mouth } OPTIONAL { ?r wdt:P625 ?co . BIND(geof:latitude(?co) AS ?lat) BIND(geof:longitude(?co) AS ?lon) }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 4000""")
    rv = {}
    for r in data:
        name = r["rLabel"]["value"]
        if name.startswith("Q") and name[1:].isdigit():
            continue
        o = rv.setdefault(name, {"name": name, "n": int(r["n"]["value"]), "len": float(r["len"]["value"]), "countries": set(), "mouth": None, "lat": None, "lon": None})
        if "cLabel" in r:
            c = r["cLabel"]["value"]
            o["countries"].add((by_name.get(alias.get(c.lower(), c.lower())) or {}).get("name") or c)
        if "mouthLabel" in r and not o["mouth"]:
            o["mouth"] = r["mouthLabel"]["value"]
        if "lat" in r and o["lat"] is None:
            o["lat"], o["lon"] = float(r["lat"]["value"]), float(r["lon"]["value"])
    rows = []
    for o in sorted(rv.values(), key=lambda o: -o["n"]):
        cs = sorted(o["countries"])
        conts = sorted({(by_name.get(c.lower()) or {}).get("continent") for c in cs} - {None})
        if not cs or not conts or o["lat"] is None or not o["mouth"]:
            continue
        rows.append({"name": o["name"], "continent": conts[0], "countries": cs, "len": round(o["len"]), "mouth": o["mouth"], "lat": round(o["lat"], 2), "lon": round(o["lon"], 2), "fame": o["n"]})
    return rows[:400]


# ---------------- animals (curated here) ----------------
# name, class, diet, home, continents, typical adult mass (kg), typical lifespan (years)
ANIMALS = [
    ("African elephant", "Mammal", "Herbivore", "Grassland", "Africa", 6000, 65), ("Asian elephant", "Mammal", "Herbivore", "Forest", "Asia", 4000, 60),
    ("Lion", "Mammal", "Carnivore", "Grassland", "Africa,Asia", 190, 14), ("Tiger", "Mammal", "Carnivore", "Forest", "Asia", 220, 15),
    ("Leopard", "Mammal", "Carnivore", "Forest", "Africa,Asia", 60, 14), ("Cheetah", "Mammal", "Carnivore", "Grassland", "Africa,Asia", 50, 12),
    ("Jaguar", "Mammal", "Carnivore", "Forest", "North America,South America", 90, 12), ("Polar bear", "Mammal", "Carnivore", "Polar", "North America,Europe,Asia", 450, 25),
    ("Brown bear", "Mammal", "Omnivore", "Forest", "North America,Europe,Asia", 270, 25), ("Giant panda", "Mammal", "Herbivore", "Mountains", "Asia", 100, 20),
    ("Grey wolf", "Mammal", "Carnivore", "Forest", "North America,Europe,Asia", 40, 8), ("Red fox", "Mammal", "Omnivore", "Forest", "North America,Europe,Asia,Africa", 6, 5),
    ("Hippopotamus", "Mammal", "Herbivore", "Freshwater", "Africa", 1500, 40), ("Giraffe", "Mammal", "Herbivore", "Grassland", "Africa", 1200, 25),
    ("Plains zebra", "Mammal", "Herbivore", "Grassland", "Africa", 350, 25), ("Rhinoceros", "Mammal", "Herbivore", "Grassland", "Africa,Asia", 2000, 40),
    ("Gorilla", "Mammal", "Herbivore", "Forest", "Africa", 160, 35), ("Chimpanzee", "Mammal", "Omnivore", "Forest", "Africa", 50, 40),
    ("Orangutan", "Mammal", "Omnivore", "Forest", "Asia", 75, 35), ("Kangaroo", "Mammal", "Herbivore", "Grassland", "Oceania", 55, 15),
    ("Koala", "Mammal", "Herbivore", "Forest", "Oceania", 9, 13), ("Camel", "Mammal", "Herbivore", "Desert", "Africa,Asia", 600, 40),
    ("Moose", "Mammal", "Herbivore", "Forest", "North America,Europe,Asia", 450, 15), ("Bison", "Mammal", "Herbivore", "Grassland", "North America,Europe", 700, 18),
    ("Reindeer", "Mammal", "Herbivore", "Polar", "North America,Europe,Asia", 120, 15), ("Capybara", "Mammal", "Herbivore", "Wetlands", "South America", 50, 8),
    ("Sloth", "Mammal", "Herbivore", "Forest", "South America,North America", 6, 20), ("Beaver", "Mammal", "Herbivore", "Freshwater", "North America,Europe", 20, 12),
    ("Gray squirrel", "Mammal", "Herbivore", "Forest", "North America,Europe", 0.6, 6), ("Hedgehog", "Mammal", "Omnivore", "Forest", "Europe,Africa,Asia", 1, 5),
    ("Platypus", "Mammal", "Carnivore", "Freshwater", "Oceania", 1.4, 12), ("Bat", "Mammal", "Omnivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 0.02, 20),
    ("Domestic cat", "Mammal", "Carnivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 4.5, 15), ("Domestic dog", "Mammal", "Omnivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 20, 12),
    ("Horse", "Mammal", "Herbivore", "Grassland", "Africa,Asia,Europe,North America,South America,Oceania", 500, 28), ("Cow", "Mammal", "Herbivore", "Grassland", "Africa,Asia,Europe,North America,South America,Oceania", 650, 20),
    ("Pig", "Mammal", "Omnivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 200, 15), ("Sheep", "Mammal", "Herbivore", "Grassland", "Africa,Asia,Europe,North America,South America,Oceania", 70, 12),
    ("Blue whale", "Mammal", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 150000, 80), ("Humpback whale", "Mammal", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 30000, 50),
    ("Killer whale", "Mammal", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 4500, 40), ("Bottlenose dolphin", "Mammal", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 250, 40),
    ("Walrus", "Mammal", "Carnivore", "Polar", "North America,Europe,Asia", 1200, 40), ("Manatee", "Mammal", "Herbivore", "Wetlands", "North America,South America,Africa", 500, 50),
    ("Emperor penguin", "Bird", "Carnivore", "Polar", "Antarctica", 30, 20), ("Bald eagle", "Bird", "Carnivore", "Forest", "North America", 5, 20),
    ("Ostrich", "Bird", "Omnivore", "Grassland", "Africa", 110, 40), ("Peregrine falcon", "Bird", "Carnivore", "Mountains", "Africa,Asia,Europe,North America,South America,Oceania", 1, 15),
    ("Barn owl", "Bird", "Carnivore", "Grassland", "Africa,Asia,Europe,North America,South America,Oceania", 0.5, 4), ("Flamingo", "Bird", "Omnivore", "Wetlands", "Africa,Europe,South America,North America,Asia", 3, 30),
    ("Hummingbird", "Bird", "Omnivore", "Forest", "North America,South America", 0.005, 5), ("Albatross", "Bird", "Carnivore", "Ocean", "Antarctica,Oceania,South America,North America", 9, 50),
    ("Pelican", "Bird", "Carnivore", "Wetlands", "Africa,Asia,Europe,North America,South America,Oceania", 8, 25), ("Toucan", "Bird", "Omnivore", "Forest", "South America,North America", 0.6, 20),
    ("Kiwi", "Bird", "Omnivore", "Forest", "Oceania", 2.5, 25), ("Emu", "Bird", "Omnivore", "Grassland", "Oceania", 35, 12),
    ("Parrot", "Bird", "Herbivore", "Forest", "South America,Africa,Asia,Oceania", 0.5, 40), ("Mallard duck", "Bird", "Omnivore", "Freshwater", "North America,Europe,Asia", 1.1, 8),
    ("Chicken", "Bird", "Omnivore", "Grassland", "Africa,Asia,Europe,North America,South America,Oceania", 2.5, 8), ("Crow", "Bird", "Omnivore", "Forest", "North America,Europe,Asia,Africa", 0.5, 10),
    ("Saltwater crocodile", "Reptile", "Carnivore", "Wetlands", "Asia,Oceania", 450, 70), ("Nile crocodile", "Reptile", "Carnivore", "Freshwater", "Africa", 500, 60),
    ("Komodo dragon", "Reptile", "Carnivore", "Grassland", "Asia", 70, 30), ("Green sea turtle", "Reptile", "Herbivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 150, 70),
    ("Galapagos tortoise", "Reptile", "Herbivore", "Grassland", "South America", 250, 100), ("King cobra", "Reptile", "Carnivore", "Forest", "Asia", 6, 20),
    ("Green iguana", "Reptile", "Herbivore", "Forest", "South America,North America", 5, 15), ("Chameleon", "Reptile", "Carnivore", "Forest", "Africa,Asia,Europe", 0.1, 5),
    ("Anaconda", "Reptile", "Carnivore", "Wetlands", "South America", 100, 10), ("American alligator", "Reptile", "Carnivore", "Wetlands", "North America", 360, 50),
    ("Bullfrog", "Amphibian", "Carnivore", "Freshwater", "North America", 0.5, 8), ("Axolotl", "Amphibian", "Carnivore", "Freshwater", "North America", 0.2, 12),
    ("Poison dart frog", "Amphibian", "Carnivore", "Forest", "South America,North America", 0.003, 5), ("Giant salamander", "Amphibian", "Carnivore", "Freshwater", "Asia", 25, 50),
    ("Great white shark", "Fish", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 1100, 70), ("Whale shark", "Fish", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 20000, 70),
    ("Clownfish", "Fish", "Omnivore", "Ocean", "Asia,Oceania,Africa", 0.25, 8), ("Goldfish", "Fish", "Omnivore", "Freshwater", "Asia,Europe,North America", 0.3, 15),
    ("Atlantic salmon", "Fish", "Carnivore", "Freshwater", "Europe,North America", 5, 6), ("Piranha", "Fish", "Omnivore", "Freshwater", "South America", 1, 10),
    ("Seahorse", "Fish", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 0.02, 3), ("Manta ray", "Fish", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 1400, 40),
    ("Tuna", "Fish", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 250, 15), ("Electric eel", "Fish", "Carnivore", "Freshwater", "South America", 20, 15),
    ("Honey bee", "Invertebrate", "Herbivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 0.0001, 1), ("Monarch butterfly", "Invertebrate", "Herbivore", "Grassland", "North America,South America", 0.0005, 1),
    ("Giant squid", "Invertebrate", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 275, 5), ("Octopus", "Invertebrate", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 10, 3),
    ("Tarantula", "Invertebrate", "Carnivore", "Forest", "South America,North America,Africa,Asia", 0.09, 20), ("Ant", "Invertebrate", "Omnivore", "Forest", "Africa,Asia,Europe,North America,South America,Oceania", 0.00001, 2),
    ("Jellyfish", "Invertebrate", "Carnivore", "Ocean", "Africa,Asia,Europe,North America,South America,Oceania", 3, 1), ("Lobster", "Invertebrate", "Omnivore", "Ocean", "North America,Europe", 4, 50),
]


def animals():
    return [{"name": n, "cls": c, "diet": d, "home": h, "continents": ct.split(","), "mass": m, "life": l} for n, c, d, h, ct, m, l in ANIMALS]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("countries", countries), ("elements", elements), ("laureates", laureates), ("cities", cities), ("peaks", peaks), ("languages", languages), ("scientists", scientists), ("rivers", rivers), ("animals", animals)):
        rows = fn()
        (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        print(name, len(rows))


if __name__ == "__main__":
    main()
