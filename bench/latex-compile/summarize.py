#!/usr/bin/env python3
"""Print CPU and wall medians per doc, engine and mode from results.csv.

CPU seconds (user+sys of the latexmk process tree) are the comparable figure.
Wall seconds depend on what else the Mac was doing; max_load1 and waited show
the conditions.
"""
import csv, statistics, sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "results.csv"
wall, cpu, load = (defaultdict(list) for _ in range(3))
waited = defaultdict(set)
for row in csv.DictReader(l for l in open(path) if not l.startswith("#")):
    k = (row["doc"], row["engine"], row["mode"])
    wall[k].append(float(row["seconds"]))
    cpu[k].append(float(row["cpu_seconds"]))
    load[k].append(float(row["load1"]))
    waited[k].add(row["waited"])
print("doc,engine,mode,runs,cpu_median,cpu_min,cpu_max,wall_median,wall_min,wall_max,max_load1,waited")
for k, v in wall.items():
    c = cpu[k]
    print(",".join(k) + f",{len(v)},{statistics.median(c):.2f},{min(c):.2f},{max(c):.2f},"
          f"{statistics.median(v):.2f},{min(v):.2f},{max(v):.2f},{max(load[k]):.1f},{'/'.join(sorted(waited[k]))}")
