#!/usr/bin/env python3
"""Offline tests for the Search Console operator/natural split and the card (run: python3 scripts/traffic-dashboard/test_gsc_split.py)."""
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("td", Path(__file__).with_name("traffic_dashboard.py"))
td = importlib.util.module_from_spec(spec); spec.loader.exec_module(td)


def check(cond, msg):
    if not cond:
        print("FAIL:", msg); sys.exit(1)


row = lambda q, imp, clk=0, pos=10.0: {"keys": [q], "impressions": imp, "clicks": clk, "position": pos}

for q in ['"pmc12965823" "repetitions in reserve"', '%"pmc12965823" x', '+site.pubmed.ncbi.nlm.nih.gov y',
          'site.pmc.ncbi.nlm.nih.gov/articles/pmc12965823', 'yogurt fdcid', 'intitle:glp-1']:
    check(td.is_operator_query(q), f"operator: {q}")
for q in ['glp-1 calorie calculator', 'can ozempic cause muscle loss', 'whey vs plant protein', '30% protein diet']:
    check(not td.is_operator_query(q), f"natural: {q}")

rows = [row('"pmc12965823" "reserve"', 100), row("glp-1 calorie calculator", 30, 1, 8.0),
        row("creatine and glp-1", 10, 0, 70.0)]
sp = td.split_queries(rows, 400)
check(sp["operator"] == {"queries": 1, "impressions": 100, "clicks": 0}, "operator totals")
check(sp["natural"]["impressions"] == 40 and sp["natural"]["clicks"] == 1, "natural totals")
check(sp["natural"]["top10_impressions"] == 30, "top10 impressions")
check(sp["natural"]["position"] == 23.5, f"weighted position {sp['natural']['position']}")
check(sp["visible_impressions"] == 140 and sp["anonymized_impressions"] == 260, "visible/anonymized")
check([r["key"] for r in sp["natural_top"]] == ["glp-1 calorie calculator", "creatine and glp-1"], "natural_top order")
check(td.split_queries([], 0)["natural"]["position"] == 0.0, "empty input")

g = {"clicks": 2, "impressions": 400, "ctr": 0.5, "position": 13.8, "start": "2026-07-03", "end": "2026-09-30",
     "queries": sp["natural_top"], "split": sp,
     "devices": {"desktop": {"impressions": 380, "clicks": 0, "position": 13.6},
                 "mobile": {"impressions": 20, "clicks": 2, "position": 16.2}}}
h = td.gsc_card(g)
check("mobile impr." in h and "desktop impr." in h and "operator-style" in h, "card shows device row and split note")
legacy = td.gsc_card({k: g[k] for k in ("clicks", "impressions", "ctr", "position", "start", "end")})
check("operator-style" not in legacy and "Google Search" in legacy, "legacy archive entry still renders")
print("ok")
