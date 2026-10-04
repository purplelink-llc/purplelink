#!/usr/bin/env python3
"""Fetch and snapshot the open data behind the attribute-guess games (Landlink, Atomlink, Prizelink).

  python3 scripts/build_attr_data.py            # needs curl and network; writes scripts/games-data/attr/*.json

Sources (all open):
  Natural Earth admin-0 countries (public domain) + Wikidata (CC0) for area, capital and driving side  -> countries.json
  PubChem periodic table (US government, public domain)                                                -> elements.json
  Nobel Prize API v2.1 (CC0) + Wikidata sitelink counts as a "how well known" measure                  -> laureates.json
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("countries", countries), ("elements", elements), ("laureates", laureates)):
        rows = fn()
        (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        print(name, len(rows))


if __name__ == "__main__":
    main()
