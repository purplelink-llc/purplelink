#!/usr/bin/env python3.12
"""Checks the rules the generator promises, over many seeds. Run: python3.12 qa.py"""
import collections
import numpy as np
import chiptune as c


def qa(seeds):
    bad = collections.Counter()
    stats = collections.defaultdict(list)
    for seed in seeds:
        t = c.plan(seed)
        ev = c.compose(t)
        key = c.KEYS[t.key]
        scale = c.MODES[t.mode]
        s16 = 60.0 / t.bpm / 4
        for name in ("lead", "echo", "harm"):
            L = ev[name]
            if any(L[i][0] + L[i][1] > L[i + 1][0] + 1e-6 for i in range(len(L) - 1)):
                bad[f"{name} overlaps"] += 1
            if any(e[1] <= 0 or e[0] < 0 for e in L):
                bad[f"{name} bad time"] += 1
        # every lead note in the section's scale or in the chord under it
        clock, off, total = 0.0, 0, 0
        for sec in t.sections:
            end = clock + sec.bars * t.bar_seconds
            kk = key + sec.lift
            pcs = {(kk + s) % 12 for s in scale}
            for st, du, m, v, ex in ev["lead"]:
                if clock <= st < end:
                    bar = int((st - clock) / t.bar_seconds)
                    beat = ((st - clock) % t.bar_seconds) / (60.0 / t.bpm)
                    ch = c.chord_at(sec, bar, min(3.99, beat))
                    total += 1
                    if m % 12 not in pcs and m % 12 not in ch.pcs(kk):
                        off += 1
            clock = end
        if total and off / total > 0.03:
            bad["lead out of key"] += 1
        lead = [e[2] for e in ev["lead"]]
        if min(lead) < 60 or max(lead) > 92:
            bad["lead range"] += 1
        # variety
        chords = {(ch.root, ch.ivs) for s in t.sections for bar in s.chords for _, ch, _ in bar}
        stats["distinct chords"].append(len(chords))
        stats["lead notes"].append(len(lead))
        stats["trills/graces"].append(sum(1 for e in ev["lead"] if e[1] < s16 * 1.1))
        stats["seconds"].append(t.seconds)
        stats["has harmony"].append(len(ev["harm"]) > 0)
        stats["has fill"].append(len(ev["tom"]) > 0)
    return bad, stats


if __name__ == "__main__":
    bad, stats = qa(range(1, 61))
    print("problems:", dict(bad) or "none")
    for k, v in stats.items():
        v = np.array(v, dtype=float)
        print(f"{k:>16}: mean {v.mean():7.1f}  min {v.min():6.1f}  max {v.max():6.1f}")
