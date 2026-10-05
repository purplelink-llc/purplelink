#!/usr/bin/env python3.12
"""Procedural study music in four sound worlds, version 3. One seed gives one track, always the same track.

Each track picks an era: 8-bit (pulse, triangle, noise at 4 bits), 16-bit (FM keys, bells, flute, organ, strings, plucks, reverb and sampled-style drums),
synth (detuned saws, filtered bass, risers, sidechain pumping) or a hybrid of the three. See voices.py for the instruments.


Voices, as on a small console: pulse channels for the melody, its echo, a harmony line, an arpeggio and a pad,
a triangle bass, and noise drums, with 4-bit amplitude steps. The music itself comes from composition rules:

  * chords move by function (a Markov walk over scale degrees), with sevenths, an occasional secondary dominant
    or borrowed chord, and 8-bar progressions that end on a half cadence or a full close
  * melodies are built from a motif that is repeated, sequenced, inverted and answered, with grace notes, trills
    and slides; strong beats land on chord tones
  * sections have different jobs: intro, A, B, a sparse bridge, a return, a final verse a step higher, an outro
  * bass and drum grooves change by section, with approach notes, ghost notes, fills and a little swing

    python3.12 chiptune.py --seed 7 --out track.wav
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

import voices as V

SR = 44100            # output rate
OS = 2                # oversampling while rendering, so square waves do not alias into hiss
RATE = SR * OS

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
}
BRIGHT = ("major", "mixolydian", "lydian")
KEYS = {"C": 0, "D": 2, "Eb": 3, "F": 5, "G": 7, "A": 9, "Bb": 10}

# Where each chord tends to go next, by scale degree: (next degree, weight).
NEXT_BRIGHT = {
    0: [(3, 3), (5, 3), (4, 2), (1, 2), (2, 1), (0, 1)],
    1: [(4, 6), (3, 2), (0, 1), (5, 1)],
    2: [(5, 5), (3, 3), (1, 2)],
    3: [(4, 3), (0, 2), (1, 2), (5, 1), (3, 1)],
    4: [(0, 5), (5, 3), (3, 1), (2, 1)],
    5: [(3, 3), (1, 3), (4, 2), (2, 2), (0, 1)],
    6: [(0, 3), (2, 3), (5, 2)],
}
NEXT_DARK = {
    0: [(5, 3), (3, 3), (6, 3), (2, 2), (4, 1)],
    1: [(4, 3), (6, 2), (0, 1)],
    2: [(5, 3), (3, 2), (6, 3), (0, 1)],
    3: [(6, 3), (0, 2), (4, 2), (2, 1), (5, 1)],
    4: [(0, 4), (5, 2), (3, 1)],
    5: [(6, 3), (3, 3), (2, 2), (4, 1), (0, 1)],
    6: [(2, 3), (0, 3), (5, 2), (3, 1)],
}

FORMS = [
    [("intro", 4), ("A", 8), ("B", 8), ("A2", 8), ("bridge", 8), ("B2", 8), ("A3", 8), ("outro", 4)],
    [("intro", 4), ("A", 8), ("A2", 8), ("B", 8), ("bridge", 8), ("B2", 8), ("A3", 8), ("outro", 4)],
    [("intro", 4), ("A", 8), ("B", 8), ("bridge", 8), ("A2", 8), ("B2", 8), ("A3", 8), ("outro", 4)],
]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


@dataclass
class Chord:
    root: int                      # semitones above the key's tonic, 0 to 11
    ivs: tuple                     # intervals above the root, e.g. (0, 4, 7, 11)

    def pcs(self, key: int):
        return {(key + self.root + i) % 12 for i in self.ivs}


@dataclass
class Section:
    name: str
    bars: int
    chords: list                   # one list of (beat, Chord, beats) per bar
    energy: float                  # 0 to 1
    lead: str                      # 'motif', 'sparse' or 'none'
    arp: str                       # arpeggio pattern name or ''
    drums: float
    hats: bool
    echo: bool
    harmony: bool
    pad: bool
    octave: int = 0                # semitones the melody moves up
    lift: int = 0                  # semitones the whole section moves up (the final verse)
    duty: float = 0.5
    fill: bool = True


@dataclass
class Track:
    seed: int
    key: str
    mode: str
    bpm: int
    swing: float
    groove: str
    sections: list = field(default_factory=list)
    sound: dict = field(default_factory=dict)

    @property
    def bar_seconds(self) -> float:
        return 4 * 60.0 / self.bpm

    @property
    def bars(self) -> int:
        return sum(s.bars for s in self.sections)

    @property
    def seconds(self) -> float:
        return self.bars * self.bar_seconds


# ---------------------------------------------------------------- harmony

def diatonic(scale: list, deg: int, seventh: bool = True, ninth: bool = False) -> Chord:
    root = scale[deg % 7]
    ivs = [0]
    for k in (2, 4) + ((6,) if seventh else ()):
        ivs.append((scale[(deg + k) % 7] - root) % 12)
    if ninth:
        ivs.append((scale[(deg + 8) % 7] - root) % 12 + 12)
    return Chord(root, tuple(ivs))


def walk(r: random.Random, table: dict, start: int, n: int, end: int | None) -> list:
    out = [start]
    while len(out) < n:
        opts = table[out[-1]]
        out.append(r.choices([o for o, _ in opts], weights=[w for _, w in opts])[0])
    if end is not None:
        out[-1] = end
        if len(out) > 1 and out[-2] == end:
            out[-2] = r.choice([d for d, _ in table[end] if d != end])
    return out


def progression(r: random.Random, scale: list, dark: bool, kind: str) -> list:
    """Eight bars of chords. `kind` is 'half' (ends on the dominant), 'full' (ends on the tonic) or 'bridge'."""
    table = NEXT_DARK if dark else NEXT_BRIGHT
    dom = 4
    if kind == "bridge":
        start = r.choice([5, 3, 1]) if not dark else r.choice([3, 5, 2])
        degs = walk(r, table, start, 4, end=dom)
        bars = [degs[i // 2] for i in range(8)]
    elif kind == "half":
        bars = walk(r, table, 0, 8, end=dom)
    else:
        first = walk(r, table, 0, 4, end=None)
        tail = walk(r, table, r.choice([3, 5]), 3, end=None)
        bars = first + tail + [0]
        bars[6] = dom
    if r.random() < 0.25 and kind != "bridge":
        bars = [bars[(i // 2) * 2] if i < 6 else bars[i] for i in range(8)]       # a slower harmonic rhythm
    out = []
    for i, d in enumerate(bars):
        ch = diatonic(scale, d, seventh=True, ninth=(d == 0 and r.random() < 0.35))
        split = None
        if i + 1 < 8 and d != bars[i + 1] and r.random() < 0.22 and bars[i + 1] != 6:
            nxt = diatonic(scale, bars[i + 1], seventh=True)
            split = Chord((nxt.root + 7) % 12, (0, 4, 7, 10))                    # a secondary dominant for the second half
        if not dark and d == 3 and r.random() < 0.15:
            ch = Chord(ch.root, (0, 3, 7, 10))                                    # the minor iv, borrowed
        if dark and d == 4 and r.random() < 0.7:
            ch = Chord(ch.root, (0, 4, 7, 10))                                    # the major V, borrowed
        out.append([(0, ch, 2), (2, split, 2)] if split else [(0, ch, 4)])
    return out


# ---------------------------------------------------------------- planning

ERAS = {
    "8bit": dict(lead=["pulse"], arp=["pulse_arp"], pad=["pulse_pad"], bass=["tri8"], kit=["8bit"], wet=0.0, cut=7500),
    "16bit": dict(lead=["fm_ep", "flute", "fm_bell", "pulse_soft", "fm_brass"], arp=["pluck", "fm_ep", "fm_bell"], pad=["strings", "organ", "warm_pad"],
                  bass=["fm_bass", "synth_bass", "sub_sine"], kit=["lofi", "808"], wet=0.24, cut=11500),
    "synth": dict(lead=["saw_lead", "fm_brass", "pulse_soft"], arp=["saw_pluck", "pluck"], pad=["warm_pad", "strings"],
                  bass=["synth_bass", "fm_bass"], kit=["electro", "808"], wet=0.18, cut=11500),
    "hybrid": dict(lead=["pulse", "pulse_soft", "fm_ep", "saw_lead"], arp=["pulse_arp", "pluck", "saw_pluck"], pad=["strings", "organ", "pulse_pad"],
                   bass=["tri8", "fm_bass", "synth_bass"], kit=["8bit", "lofi", "808"], wet=0.12, cut=9500),
}


def pick_sound(seed: int, era: str | None = None) -> dict:
    """The instruments for a track, chosen on their own random stream so the notes do not change when the sound does."""
    r = random.Random(seed * 31337 + 5)
    picked = r.choices(list(ERAS), weights=[2, 4, 3, 3])[0]          # always drawn, so pinning an era leaves the other choices unchanged
    era = era or picked
    e = ERAS[era]

    def two(pool):
        a = r.choice(pool)
        return [a, r.choice([x for x in pool if x != a] or pool)]

    return dict(era=era, lead=two(e["lead"]), arp=two(e["arp"]), pad=r.choice(e["pad"]), bass=r.choice(e["bass"]), kit=r.choice(e["kit"]),
                wet=e["wet"] * r.uniform(0.8, 1.25), rt60=r.uniform(1.1, 2.4), cut=e["cut"],
                duck=era == "synth" or (era == "hybrid" and r.random() < 0.3), risers=era in ("16bit", "synth") or r.random() < 0.4,
                spark=era != "8bit" and r.random() < 0.75, crackle=era in ("16bit", "hybrid") and r.random() < 0.5,
                chorus=era != "8bit" and r.random() < 0.8)


def plan(seed: int, era: str | None = None) -> Track:
    r = random.Random(seed * 7919 + 13)
    key = r.choice(list(KEYS))
    mode = r.choices(list(MODES), weights=[4, 4, 3, 2, 1])[0]
    bpm = r.randint(72, 94)
    swing = r.choice([0.0, 0.0, 0.12, 0.2, 0.28])
    groove = r.choice(["steady", "lofi", "broken"])
    dark = mode not in BRIGHT
    scale = MODES[mode]
    p_half = progression(r, scale, dark, "half")
    p_full = progression(r, scale, dark, "full")
    p_b = progression(r, scale, dark, "half")
    p_b2 = progression(r, scale, dark, "full")
    p_br = progression(r, scale, dark, "bridge")
    form = r.choice(FORMS)
    arp_style = r.choice(["updown", "broken", "pedal"])
    arp_b = r.choice([a for a in ("updown", "broken", "pedal", "gated") if a != arp_style])
    lift = 2 if r.random() < 0.6 else 0
    t = Track(seed, key, mode, bpm, swing, groove)
    spec = {
        "intro": dict(chords=p_half, energy=.25, lead="none", arp=arp_style, drums=0, hats=False, echo=False, harmony=False, pad=True, fill=False),
        "A": dict(chords=p_half, energy=.55, lead="motif", arp=arp_style if r.random() < .8 else "", drums=.65, hats=False, echo=False, harmony=False, pad=False),
        "A2": dict(chords=p_full, energy=.65, lead="motif", arp=arp_style, drums=.8, hats=r.random() < .5, echo=True, harmony=False, pad=False),
        "B": dict(chords=p_b, energy=.85, lead="motif", arp=arp_b, drums=1.0, hats=True, echo=False, harmony=False, pad=True, duty=.25),
        "bridge": dict(chords=p_br, energy=.3, lead="sparse", arp=arp_style, drums=.0, hats=False, echo=True, harmony=False, pad=True, fill=False),
        "B2": dict(chords=p_b2, energy=1.0, lead="motif", arp=arp_b, drums=1.0, hats=True, echo=True, harmony=True, pad=True, duty=.25, octave=5 if r.random() < .4 else 0),
        "A3": dict(chords=p_full, energy=.8, lead="motif", arp=arp_style, drums=.8, hats=True, echo=True, harmony=r.random() < .5, pad=False, lift=lift),
        "outro": dict(chords=p_full, energy=.2, lead="none", arp=arp_style, drums=0, hats=False, echo=False, harmony=False, pad=True, fill=False, lift=lift),
    }
    for name, bars in form:
        s = dict(spec[name])
        chords = s.pop("chords")
        t.sections.append(Section(name, bars, chords, **s))
    t.sound = pick_sound(seed, era)
    return t


# ---------------------------------------------------------------- composition

def scale_midis(key_midi: int, scale: list, lo: int, hi: int) -> list:
    out = []
    for o in range(-5, 8):
        for s in scale:
            m = key_midi + 12 * o + s
            if lo <= m <= hi:
                out.append(m)
    return sorted(out)


def chord_at(sec: Section, bar: int, beat: float):
    for b, ch, ln in sec.chords[bar % len(sec.chords)]:
        if b <= beat < b + ln:
            return ch
    return sec.chords[bar % len(sec.chords)][0][1]


def make_motif(r: random.Random, bars: int, density: float, bias_up: bool):
    """A rhythm on a 16th grid with a scale step for each note: [(slot, length, rest, step)]."""
    total = bars * 16
    notes, pos = [], 0
    lengths = [1, 2, 2, 3, 4, 4, 6, 8]
    weights = [3 * density, 6 * density, 5, 3, 5, 4, 2, 1]
    if r.random() < 0.4:
        notes.append((0, 2, False, 0))                 # a short first note, so the phrase opens with a little pickup figure
        pos = 2
    while pos < total:
        ln = r.choices(lengths, weights=weights)[0]
        ln = min(ln, total - pos)
        if pos >= total - 8:
            ln = max(ln, min(6, total - pos))         # slow down and breathe at the end
        rest = r.random() < 0.18 and pos % 8 != 0 and pos > 2 and pos + ln < total - 4
        notes.append((pos, ln, rest, 0))
        pos += ln
    n = len(notes)
    out, prev_leap = [], 0
    for i, (p, ln, rest, _) in enumerate(notes):
        bias = (0.5 if bias_up else -0.2) if i < n * 0.5 else (-0.5 if bias_up else 0.2)
        opts = [-3, -2, -1, 0, 1, 2, 3]
        w = [3, 10, 28, 7, 28, 10, 3]
        w = [x * math.exp(bias * o * 0.45) for x, o in zip(w, opts)]
        if prev_leap:
            w = [x * (3 if (o * prev_leap < 0) else 0.4) for x, o in zip(w, opts)]
        st = r.choices(opts, weights=w)[0]
        if r.random() < 0.1:
            st = r.choice([-5, -4, 4, 5])
        prev_leap = st if abs(st) >= 3 else 0
        out.append((p, ln, rest, st))
    return out


def develop(r: random.Random, motif, how: str):
    """Repeat, sequence, invert or vary a motif. Returns (motif, start shift in scale steps)."""
    if how == "repeat":
        return motif, 0
    if how == "seq_up":
        return motif, 1
    if how == "seq_down":
        return motif, -1
    if how == "invert":
        return [(p, ln, rest, -st) for p, ln, rest, st in motif], 0
    if how == "vary":
        k = len(motif) // 2
        tail = [(p, ln, rest, r.choice([-2, -1, 1, 2])) for p, ln, rest, _ in motif[k:]]
        return motif[:k] + tail, 0
    return motif, 0


def place(t: Track, bar_start: float, slot: float) -> float:
    s = 60.0 / t.bpm / 4
    sw = t.swing * s if int(slot) % 2 == 1 else 0.0
    return bar_start + slot * s + sw


def compose(t: Track):
    """Per-channel event lists of (start_s, dur_s, midi, volume, extra) for the whole track."""
    r = random.Random(t.seed * 104729 + 7)
    scale = MODES[t.mode]
    key = KEYS[t.key]
    beat = 60.0 / t.bpm
    s16 = beat / 4
    ev = {c: [] for c in ("lead", "echo", "harm", "arp", "pad", "bass", "kick", "snare", "hat", "tom", "spark", "fx")}
    names = ["p1", "p2", "p3", "p4"]
    bass_a = r.choice(names)
    bass_b = r.choice([p for p in names if p != bass_a])
    dark = t.mode not in BRIGHT
    motif_a = make_motif(r, 2, 1.0, True)
    motif_b = make_motif(r, 2, 1.3, False)
    clock = 0.0

    def low(m: int) -> int:
        while m < 33:
            m += 12
        while m > 46:
            m -= 12
        return m

    for sec in t.sections:
        tonic = 48 + key + sec.lift                 # MIDI of the tonic in octave 3
        sec_start = clock
        for bar in range(sec.bars):
            t0 = sec_start + bar * t.bar_seconds
            chs = sec.chords[bar % len(sec.chords)]
            nxt = sec.chords[(bar + 1) % len(sec.chords)][0][1]
            fade = 1.0
            if sec.name == "outro":
                fade = max(0.0, 1.0 - (bar + 1) / (sec.bars + 0.5))
            if sec.name == "intro":
                fade = 0.4 + 0.6 * (bar / max(1, sec.bars - 1))
            block_end = bar % 4 == 3

            # bass (triangle), chord-aware, with an approach note into the next chord
            pat = bass_b if sec.name.startswith("B") else bass_a
            for b, ch, ln in chs:
                root = low(tonic - 24 + ch.root)
                fifth = root + (ch.ivs[2] if len(ch.ivs) > 2 else 7)
                third = root + ch.ivs[1]
                nroot = low(tonic - 24 + nxt.root)
                approach = nroot + (-1 if nroot > root else 1) if abs(nroot - root) > 2 else nroot - 2
                lines = {
                    "p1": [(0, 6, root), (8, 4, root), (12, 4, fifth)],
                    "p2": [(0, 4, root), (6, 2, root + 12), (8, 4, fifth), (12, 2, root), (14, 2, approach)],
                    "p3": [(0, 4, root), (4, 4, third), (8, 4, fifth), (12, 4, approach)],
                    "p4": [(0, 3, root), (3, 3, root), (6, 2, fifth), (8, 4, root + 12), (12, 4, fifth)],
                }[pat]
                lo_slot, hi_slot = b * 4, (b + ln) * 4
                for slot, sl, m in lines:
                    if lo_slot <= slot < hi_slot:
                        ev["bass"].append((place(t, t0, slot), sl * s16 * 0.9, m, 0.9 * fade, None))

            # arpeggio on a pulse channel, chord by chord, with a short run into each new 4-bar block
            if sec.arp:
                pattern = {"updown": [0, 1, 2, 3, 2, 1], "broken": [0, 2, 1, 3], "pedal": [0, 2, 0, 3, 0, 2, 0, 1],
                           "gated": [0, -1, 1, -1, 2, -1, 1, -1]}[sec.arp]
                for b, ch, ln in chs:
                    tones = sorted(tonic + 12 + ch.root + (iv % 12) for iv in ch.ivs)
                    tones.append(tones[0] + 12)
                    for k in range(b * 4, (b + ln) * 4):
                        pi = pattern[k % len(pattern)]
                        if pi < 0:
                            continue
                        m = tones[pi % len(tones)]
                        if block_end and k >= 12 and sec.fill:
                            m = tonic + 12 + scale[(k - 12) % 7] + (12 if k - 12 > 4 else 0)
                        ev["arp"].append((place(t, t0, k), s16 * 0.7, m, 0.55 * fade * (0.6 + 0.4 * sec.energy), {"duty": 0.125 if bar % 2 == 0 else 0.25}))

            # pad: two long notes from the chord (its third and its seventh or fifth)
            if sec.pad:
                for b, ch, ln in chs:
                    for iv in (ch.ivs[1], ch.ivs[3] if len(ch.ivs) > 3 else ch.ivs[2]):
                        m = tonic + 12 + ch.root + (iv % 12)
                        m = m - 12 if m > 74 else m
                        ev["pad"].append((t0 + b * beat, ln * beat * 0.98, m, 0.5 * fade, None))

            # a bell on the first beat of every second bar in the bigger sections, and a riser into them
            if sec.name.startswith("B") and bar % 2 == 0:
                b, ch, ln = chs[0]
                ev["spark"].append((t0, 0.9, 72 + ((tonic + ch.root + ch.ivs[min(2, len(ch.ivs) - 1)]) % 12), 0.5 * fade, None))
            if bar == 0 and sec.name in ("B", "B2", "A3"):
                span = min(3.0, 2 * t.bar_seconds)
                ev["fx"].append((t0 - span, span, 0, 0.6, None))

            # drums
            if sec.drums > 0:
                d = sec.drums * fade
                grooves = {
                    "steady": ([0, 8], [4, 12], [], list(range(0, 16, 2))),
                    "lofi": ([0, 6, 10], [4, 12], [7, 15], list(range(0, 16, 2))),
                    "broken": ([0, 7, 10], [4, 12], [14], list(range(0, 16, 1)) if sec.energy > 0.9 else list(range(0, 16, 2))),
                }
                kicks, snares, ghosts, hats = grooves[t.groove]
                fill = sec.fill and block_end
                if fill:
                    snares = [4, 8, 10, 12, 13, 14, 15]
                    kicks = [0]
                for k in kicks:
                    ev["kick"].append((place(t, t0, k), 0.16, 0, 0.9 * d, None))
                for k in snares:
                    ev["snare"].append((place(t, t0, k), 0.1, 0, (0.7 if k in (4, 12) else 0.45) * d, None))
                for k in ghosts:
                    ev["snare"].append((place(t, t0, k), 0.05, 0, 0.22 * d, None))
                if fill and bar % 8 == 7:
                    for k, p in zip((12, 13, 14, 15), (0.0, 0.3, 0.6, 0.9)):
                        ev["tom"].append((place(t, t0, k), 0.1, 0, 0.55 * d, {"pitch": 110 - 25 * p}))
                if sec.hats:
                    for k in hats:
                        acc = 1.0 if k % 4 == 0 else 0.55
                        ev["hat"].append((place(t, t0, k), 0.04, 0, acc * (0.8 if k % 2 == 0 else 0.35) * d, None))

        if sec.lead != "none":
            ev["lead"] += melody(r, t, sec, sec_start, key, scale, motif_a, motif_b)
        clock += sec.bars * t.bar_seconds

    # echo and harmony are made from the lead
    for st, du, m, v, ex in list(ev["lead"]):
        sec = section_at(t, st)
        if sec.echo and du > 1.5 * s16:
            ev["echo"].append((st + 3 * s16, du * 0.8, m, v * 0.4, ex))
        if sec.harmony and du > 1.5 * s16:
            hm = scale_below(key + sec.lift, scale, m, 2)
            if hm is not None:
                ev["harm"].append((st, du, hm, v * 0.55, ex))
    ev["lead"] = mono(ev["lead"])
    ev["echo"] = mono(ev["echo"])
    ev["harm"] = mono(ev["harm"])
    return ev


def section_at(t: Track, ts: float) -> Section:
    c = 0.0
    for s in t.sections:
        if c <= ts < c + s.bars * t.bar_seconds:
            return s
        c += s.bars * t.bar_seconds
    return t.sections[-1]


def scale_below(key: int, scale: list, midi: int, steps: int):
    pcs = [(key + s) % 12 for s in scale]
    if midi % 12 not in pcs:
        return None
    pool = sorted({m for m in range(midi - 16, midi + 1) if m % 12 in pcs})
    i = pool.index(midi)
    return pool[i - steps] if i - steps >= 0 else None


def mono(notes: list) -> list:
    notes = sorted(notes, key=lambda e: e[0])
    out = []
    for i, (st, du, m, v, ex) in enumerate(notes):
        if i + 1 < len(notes):
            gap = notes[i + 1][0] - st
            if gap < 0.03:
                continue                                  # two notes almost together on one voice: keep the later one
            du = min(du, gap - 0.004)
        out.append((st, du, m, v, ex))
    return out


def melody(r, t, sec, sec_start, key, scale, motif_a, motif_b):
    beat = 60.0 / t.bpm
    s16 = beat / 4
    k = key + sec.lift
    centre = 74 + sec.octave
    lo, hi = centre - 9, min(centre + 10, 90)
    pool = scale_midis(k, scale, lo, hi)
    out = []

    def nearest(m, pcs=None):
        c = [x for x in range(lo, hi + 1) if (x in pool if pcs is None else x % 12 in pcs)]
        return min(c, key=lambda x: abs(x - m)) if c else m

    def step(m, n):
        i = min(range(len(pool)), key=lambda q: abs(pool[q] - m))
        return pool[max(0, min(len(pool) - 1, i + n))]

    if sec.lead == "sparse":
        m = nearest(centre)
        for bar in range(sec.bars):
            for b, ch, ln in sec.chords[bar % len(sec.chords)]:
                m = nearest(m + r.choice([-2, 0, 2, 3]), ch.pcs(k))
                out.append((sec_start + bar * t.bar_seconds + b * beat, ln * beat * 0.92, m, 0.8, {"vib": 0.006}))
        return out

    base = motif_a if sec.name.startswith("A") else motif_b
    plans = {
        "A": ["repeat", "seq_up", "repeat", "vary"],
        "A2": ["repeat", "vary", "seq_down", "vary"],
        "A3": ["repeat", "seq_up", "invert", "vary"],
        "B": ["repeat", "invert", "seq_up", "vary"],
        "B2": ["repeat", "seq_up", "invert", "repeat"],
    }
    order = plans.get(sec.name, ["repeat", "seq_up", "repeat", "vary"])
    cur = nearest(centre)
    blocks = sec.bars // 2
    for blk in range(blocks):
        motif, shift = develop(r, base, order[blk % len(order)])
        resolve = blk == blocks - 1
        half_cadence = blocks >= 4 and blk == blocks // 2 - 1
        m = step(cur, shift)
        notes = []
        for i, (slot, ln, rest, st) in enumerate(motif):
            bar = blk * 2 + slot // 16
            sl = slot % 16
            m = step(m, st)
            ch = chord_at(sec, bar, sl / 4)
            if sl % 4 == 0 and not rest:
                m = nearest(m, ch.pcs(k))
            if i == len(motif) - 1:
                if resolve and sec.name in ("A2", "A3", "B2"):
                    m = nearest(centre, {k % 12, (k + scale[2]) % 12, (k + scale[4]) % 12})
                elif half_cadence or resolve:
                    m = nearest(m, chord_at(sec, bar, 3).pcs(k))
                rest = False
            m = max(lo, min(hi, m))
            if rest:
                continue
            tstart = place(t, sec_start + bar * t.bar_seconds, sl)
            dur = ln * s16 * (0.92 if ln > 2 else 0.8)
            ex = {"vib": 0.005 if ln >= 4 else 0.0, "duty": sec.duty if blk % 2 == 0 else 0.5}
            notes.append([tstart, dur, m, 0.9 if sl % 4 == 0 else 0.78, ex, ln, sl])
        for i, (tstart, dur, m, vol, ex, ln, sl) in enumerate(notes):
            roll = r.random()
            if ln >= 6 and roll < 0.13 and sec.energy >= 0.55:                   # a trill on a long note
                up = step(m, 1)
                tt, q = tstart + 0.5 * dur, 0
                while tt + s16 < tstart + dur:
                    out.append((tt, s16 * 0.9, up if q % 2 == 0 else m, vol * 0.85, ex))
                    tt += s16
                    q += 1
                dur *= 0.5
            elif ln >= 3 and roll < 0.28:                                         # slide up into the note
                ex = dict(ex, slide=-2)
            elif sl % 4 == 0 and i > 0 and roll < 0.42 and ln >= 2:               # a grace note
                out.append((tstart - s16 * 0.9, s16 * 0.8, step(m, -1 if r.random() < 0.5 else 1), vol * 0.7, ex))
            out.append((tstart, dur, m, vol, ex))
        cur = m - ((m > centre) - (m < centre)) * 2
    return out


# ---------------------------------------------------------------- synthesis

def adsr(n: int, a=0.004, d=0.07, s=0.7, rel=0.05) -> np.ndarray:
    a, d, rel = int(a * RATE), int(d * RATE), min(int(rel * RATE), max(1, n // 2))
    e = np.full(n, s, dtype=np.float64)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a, endpoint=False)
    d_end = min(a + d, n)
    e[a:d_end] = np.linspace(1, s, d_end - a)
    if rel:
        e[n - rel:] *= np.linspace(1, 0, rel)
    return e


def pulse(f: float, n: int, duty: float, vib: float = 0.0, slide: float = 0.0) -> np.ndarray:
    tt = np.arange(n) / RATE
    fr = f * (1 + vib * np.sin(2 * np.pi * 5.2 * tt) * np.clip((tt - 0.12) / 0.3, 0, 1))
    if slide:
        fr = fr * 2 ** ((slide * np.clip(1 - tt / 0.05, 0, 1)) / 12)
    ph = (np.cumsum(fr) / RATE) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def tri(f: float, n: int) -> np.ndarray:
    ph = (np.cumsum(np.full(n, f)) / RATE) % 1.0
    w = 4 * np.abs(ph - 0.5) - 1
    return np.round((w + 1) * 7.5) / 7.5 - 1


def noise(rng: np.random.Generator, n: int, rate: float) -> np.ndarray:
    steps = int(n * rate / RATE) + 2
    vals = rng.choice([-1.0, 1.0], steps)
    return vals[(np.arange(n) * rate / RATE).astype(int)]


def crush(x: np.ndarray, levels: int = 15) -> np.ndarray:
    return np.round(x * levels) / levels


def pan(sig: np.ndarray, p: float):
    a = (p + 1) * math.pi / 4
    return sig * math.cos(a), sig * math.sin(a)


def render(t: Track) -> np.ndarray:
    ev = compose(t)
    snd = t.sound
    rng = np.random.default_rng(t.seed)
    total = int((t.seconds + 2.5) * SR)
    groups = {g: np.zeros((2, total), np.float32) for g in ("lead", "arp", "pad", "bass", "drums", "fx")}
    kit = snd["kit"]
    kick_times = []

    def put(group, sig88, start, p, gain):
        i = int(start * SR)
        if i >= total or i + 4 < 0:
            return
        sig = resample_poly(sig88, 1, OS)
        if i < 0:
            sig, i = sig[-i:], 0
        sig = sig[: total - i]
        l, r_ = pan(sig * gain, p)
        groups[group][0, i:i + len(sig)] += l.astype(np.float32)
        groups[group][1, i:i + len(sig)] += r_.astype(np.float32)

    def inst(names, ts):
        return names[1] if section_at(t, ts).name.startswith("B") else names[0]

    def play(group, channel, names, p, gain, pad_alt=False):
        for k, (start, dur, m, vol, ex) in enumerate(ev[channel]):
            name = names if isinstance(names, str) else inst(names, start)
            n = max(16, int(dur * RATE))
            w = V.note(name, hz(m), n, ex, rng) * vol
            if name in V.CRUSHED:
                w = crush(w)
            pp = p(k) if callable(p) else p
            put(group, w, start, pp, gain)

    play("lead", "lead", snd["lead"], -0.15, 0.24)
    play("lead", "echo", snd["lead"], 0.45, 0.24)
    play("lead", "harm", snd["lead"], 0.2, 0.24)
    play("arp", "arp", snd["arp"], lambda k: -0.45 if k % 2 == 0 else 0.45, 0.09)
    play("pad", "pad", snd["pad"], lambda k: -0.7 if k % 2 else 0.7, 0.06)
    play("bass", "bass", snd["bass"], 0.0, 0.35)
    if snd["spark"]:
        play("lead", "spark", "fm_bell", 0.55, 0.10)

    # drums: the 8-bit kit is the original noise and sine, the others are the sampled-style kits in voices.py
    def drum(channel, fn8, fn, gain, p, rate=None):
        for start, dur, _, vol, ex in ev[channel]:
            if kit == "8bit":
                w = fn8(int(dur * RATE), vol, ex)
            else:
                w = fn(dur, rng) * V.DRUM_TRIM[fn] * vol
            put("drums", w, start, p, gain)
            if channel == "kick":
                kick_times.append(start)

    def k8(n, vol, ex):
        f = np.linspace(130, 44, n)
        return crush(np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.linspace(1, 0, n) ** 1.5, 7) * vol

    def s8(n, vol, ex):
        return crush((noise(rng, n, 9000) * 0.8 + pulse(190, n, 0.5) * 0.25) * np.linspace(1, 0, n) ** 2, 7) * vol

    def h8(n, vol, ex):
        return crush(noise(rng, n, 24000) * np.linspace(1, 0, n) ** 2, 5) * vol

    def t8(n, vol, ex):
        f = np.linspace(ex["pitch"] * 1.4, ex["pitch"], n)
        return crush(np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.linspace(1, 0, n) ** 1.2, 7) * vol

    kits = V.KITS.get(kit)
    drum("kick", k8, kits["kick"] if kits else None, 0.36, 0.0)
    drum("snare", s8, kits["snare"] if kits else None, 0.20 if kit == "8bit" else 0.20, 0.15)
    drum("hat", h8, kits["hat"] if kits else None, 0.055 if kit == "8bit" else 0.07, 0.4)
    for start, dur, _, vol, ex in ev["tom"]:
        w = t8(int(dur * RATE), vol, ex) if kit == "8bit" else V.tom_16(dur, rng, ex["pitch"]) * V.DRUM_TRIM[V.tom_16] * vol
        put("drums", w, start, 0.0, 0.3)
    if snd["risers"]:
        for start, dur, _, vol, _ in ev["fx"]:
            put("fx", V.riser(dur, rng), start, 0.0, 0.05 * vol)

    # effects on the 44.1 kHz buses
    if snd["duck"] and kick_times:
        curve = V.duck_curve(total, sorted(kick_times))
        for g in ("pad", "arp"):
            groups[g] *= curve
    if snd["chorus"]:
        groups["pad"] = V.chorus(groups["pad"])
    out = sum(groups.values())
    if snd["wet"] > 0:
        send = groups["lead"] * 0.8 + groups["arp"] * 0.6 + groups["pad"] * 1.0 + groups["drums"] * 0.12
        out = out + V.reverb(send, V.make_ir(snd["rt60"], t.seed)) * snd["wet"]
        del send
    if snd["crackle"]:
        r2 = np.random.default_rng(t.seed + 99)
        n = out.shape[1]
        hits = (r2.random(n) < 14 / SR).astype(np.float32) * r2.standard_normal(n).astype(np.float32)
        bed = sosfilt(butter(1, 1200, "lowpass", fs=SR, output="sos"), r2.standard_normal(n).astype(np.float32)) * 0.002
        out = out + (sosfilt(butter(2, 3500, "lowpass", fs=SR, output="sos"), hits) * 0.012 + bed)[None, :]
    del groups
    out = sosfilt(butter(2, snd["cut"], "lowpass", fs=SR, output="sos"), out, axis=1).astype(np.float32)
    out = sosfilt(butter(2, 35, "highpass", fs=SR, output="sos"), out, axis=1).astype(np.float32)
    peak = float(np.max(np.abs(out)))
    return out * np.float32(0.89 / peak) if peak else out


def describe(t: Track) -> dict:
    return {"seed": t.seed, "era": t.sound.get("era"), "instruments": [t.sound["lead"][0], t.sound["arp"][0], t.sound["pad"], t.sound["bass"], t.sound["kit"]], "key": f"{t.key} {t.mode}", "bpm": t.bpm, "swing": t.swing, "groove": t.groove, "bars": t.bars,
            "seconds": round(t.seconds, 1), "sections": [f"{s.name}x{s.bars}" + (f"+{s.lift}" if s.lift else "") for s in t.sections]}


def write_wav(path: str, audio: np.ndarray) -> None:
    import wave
    pcm = (np.clip(audio.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="track.wav")
    a = ap.parse_args()
    tr = plan(a.seed)
    write_wav(a.out, render(tr))
    print(json.dumps(describe(tr)))
