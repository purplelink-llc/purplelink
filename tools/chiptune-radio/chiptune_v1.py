#!/usr/bin/env python3.12
"""Procedural 8-bit study music. One seed gives one track, always the same track.

A track is built the way a small console would: two pulse channels (melody and arpeggio), a triangle bass and a
noise channel for drums, with 4-bit amplitude steps. Everything else is composition rules: a key and mode, a chord
progression for each section, a short melodic motif that is repeated and varied, and a calm tempo.

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

SR = 44100            # output rate
OS = 2                # oversampling while rendering, so square waves do not alias into hiss
RATE = SR * OS

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}
BRIGHT = ("major", "mixolydian")
# Chord roots by scale degree (0 = tonic). One chord per bar, four bars, repeated.
PROGS_BRIGHT = [[0, 5, 3, 4], [0, 3, 5, 4], [5, 3, 0, 4], [0, 4, 5, 3], [3, 4, 0, 0], [1, 4, 0, 5], [0, 2, 3, 4]]
PROGS_DARK = [[0, 5, 2, 6], [0, 3, 6, 2], [0, 5, 3, 6], [5, 6, 0, 0], [0, 2, 5, 6], [0, 6, 5, 6], [3, 6, 0, 0]]
KEYS = {"C": 0, "D": 2, "Eb": 3, "F": 5, "G": 7, "A": 9, "Bb": 10}

BASS_PATTERNS = [
    [(0, 3, 0), (4, 2, 0), (6, 2, 7)],
    [(0, 2, 0), (2, 2, 0), (4, 2, 7), (6, 2, 12)],
    [(0, 6, 0), (6, 2, 7)],
    [(0, 3, 0), (3, 1, 0), (4, 3, 7), (7, 1, 5)],
]
ARP_PATTERNS = [[0, 1, 2, 3], [0, 2, 1, 3], [0, 1, 2, 1], [3, 2, 1, 2]]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


@dataclass
class Section:
    name: str
    bars: int
    prog: list[int]
    lead: bool
    arp: bool
    drums: float          # 0 = none, 1 = full
    hats: bool
    lead_octave: int = 0  # semitones added to the melody register
    duty: float = 0.5


@dataclass
class Track:
    seed: int
    key: str
    mode: str
    bpm: int
    sections: list[Section] = field(default_factory=list)

    @property
    def bar_seconds(self) -> float:
        return 4 * 60.0 / self.bpm

    @property
    def bars(self) -> int:
        return sum(s.bars for s in self.sections)

    @property
    def seconds(self) -> float:
        return self.bars * self.bar_seconds


# ---------------------------------------------------------------- composition

def plan(seed: int) -> Track:
    r = random.Random(seed * 7919 + 13)
    key = r.choice(list(KEYS))
    mode = r.choices(list(MODES), weights=[4, 4, 3, 2])[0]
    bpm = r.randint(74, 92)
    progs = PROGS_BRIGHT if mode in BRIGHT else PROGS_DARK
    p1, p2 = r.sample(progs, 2)
    t = Track(seed, key, mode, bpm)
    arp_on = r.random() < 0.85
    t.sections = [
        Section("intro", 4, p1, lead=False, arp=True, drums=0.0, hats=False),
        Section("A", 8, p1, lead=True, arp=arp_on, drums=0.7, hats=False),
        Section("B", 8, p2, lead=True, arp=True, drums=1.0, hats=True, lead_octave=0, duty=0.25),
        Section("A2", 8, p1, lead=True, arp=arp_on, drums=0.8, hats=r.random() < 0.5),
        Section("B2", 8, p2, lead=True, arp=True, drums=1.0, hats=True, lead_octave=12 if r.random() < 0.4 else 0, duty=0.25),
        Section("A3", 8, p1, lead=True, arp=arp_on, drums=0.6, hats=False),
        Section("outro", 4, p1, lead=False, arp=True, drums=0.0, hats=False),
    ]
    return t


def scale_note(root_midi: int, scale: list[int], idx: int) -> int:
    return root_midi + scale[idx % 7] + 12 * (idx // 7)


def scale_interval(scale: list[int], deg: int, steps: int) -> int:
    """Semitones from scale degree `deg` up `steps` scale steps, staying in the scale."""
    return scale_note(0, scale, deg + steps) - scale_note(0, scale, deg)


def compose(t: Track):
    """Return per-channel event lists: (start_seconds, dur_seconds, midi, volume, extra)."""
    r = random.Random(t.seed * 104729 + 7)
    scale = MODES[t.mode]
    tonic = 60 + KEYS[t.key] - 12          # tonic in octave 3; individual channels move it up as needed
    beat = 60.0 / t.bpm
    eighth, sixteenth = beat / 2, beat / 4
    ev = {"lead": [], "arp": [], "bass": [], "kick": [], "snare": [], "hat": []}
    bass_pat = r.choice(BASS_PATTERNS)
    bass_alt = r.choice(BASS_PATTERNS)
    arp_pat = r.choice(ARP_PATTERNS)
    swing_snare = r.random() < 0.35

    def chord_tones(deg: int, seventh: bool):
        idx = [deg, deg + 2, deg + 4] + ([deg + 6] if seventh else [])
        return idx

    clock = 0.0
    motifs: dict[str, list] = {}
    for sec in t.sections:
        for bar in range(sec.bars):
            deg = sec.prog[bar % 4]
            seventh = (sec.name.startswith("B") and r.random() < 0.5) or r.random() < 0.15
            tones = chord_tones(deg, seventh)
            t0 = clock + bar * t.bar_seconds
            last_bar = bar == sec.bars - 1
            fade = 1.0
            if sec.name == "outro":
                fade = max(0.0, 1.0 - (bar + 1) / (sec.bars + 0.5))
            if sec.name == "intro":
                fade = 0.4 + 0.6 * (bar / max(1, sec.bars - 1))

            # bass: triangle, low octave
            pat = bass_alt if sec.name.startswith("B") else bass_pat
            root = scale_note(tonic - 24, scale, deg)
            while root < 33:
                root += 12
            while root > 45:
                root -= 12
            for slot, ln, iv in pat:
                m = root
                if iv:                                       # intervals are chord-relative, taken from the scale: 7 = fifth, 5 = fourth, 12 = octave
                    m = root + scale_interval(scale, deg, {7: 4, 5: 3, 12: 7}[iv])
                ev["bass"].append((t0 + slot * eighth, ln * eighth * 0.92, m, 0.9 * fade, None))

            # arpeggio: sixteenths over the chord tones
            if sec.arp:
                notes = [scale_note(tonic + 12, scale, i % 7) for i in tones]
                notes.sort()
                notes.append(notes[0] + 12)
                for k in range(16):
                    nm = notes[arp_pat[k % 4] % len(notes)]
                    ev["arp"].append((t0 + k * sixteenth, sixteenth * 0.75, nm, 0.55 * fade, None))

            # drums
            if sec.drums > 0:
                d = sec.drums
                for b in (0, 2):
                    ev["kick"].append((t0 + b * beat, 0.16, 0, 0.9 * d * fade, None))
                if sec.name.startswith("B") and r.random() < 0.5:
                    ev["kick"].append((t0 + 2.5 * beat, 0.14, 0, 0.7 * d, None))
                for b in (1, 3):
                    off = (sixteenth * 0.4) if swing_snare else 0.0
                    ev["snare"].append((t0 + b * beat + off, 0.1, 0, 0.7 * d * fade, None))
            if sec.hats:
                for k in range(8):
                    ev["hat"].append((t0 + k * eighth, 0.04, 0, (0.5 if k % 2 else 0.8) * fade, None))

        # melody for the whole section, two bars at a time
        if sec.lead:
            ev["lead"] += melody(r, t, sec, clock, tonic, scale, motifs)
        clock += sec.bars * t.bar_seconds
    return ev


def melody(r: random.Random, t: Track, sec: Section, clock: float, tonic: int, scale: list[int], motifs: dict):
    beat = 60.0 / t.bpm
    eighth = beat / 2
    out = []
    base = round((74 - tonic) * 7 / 12)                    # scale index of the melody's centre, about MIDI 74 whatever the key
    if sec.lead_octave and scale_note(tonic, scale, base + 7) <= 80:
        base += 7                                          # the bright second B section sits an octave higher, when there is room
    lo, hi = base - 5, base + 6

    def snap(idx: int, deg: int, seventh: bool) -> int:
        cand = []
        for off in (-14, -7, 0, 7, 14):
            for c in (deg, deg + 2, deg + 4):
                cand.append(c + off)
        cand = [c for c in cand if lo <= c <= hi]
        return min(cand, key=lambda c: abs(c - idx)) if cand else idx

    key = "A" if not sec.name.startswith("B") else "B"
    if key not in motifs:
        # a motif is two bars: 16 eighth slots split into notes and rests
        rhythm, pos = [], 0
        while pos < 16:
            ln = r.choices([1, 2, 3, 4], weights=[3, 5, 2, 2])[0]
            ln = min(ln, 16 - pos)
            rest = r.random() < 0.22 and pos % 4 != 0
            rhythm.append((pos, ln, rest))
            pos += ln
        steps = [r.choices([-2, -1, 0, 1, 2, 3, -3], weights=[12, 30, 8, 30, 12, 5, 3])[0] for _ in rhythm]
        motifs[key] = (rhythm, steps)
    rhythm, steps = motifs[key]

    deg_at = lambda bar: sec.prog[bar % 4]
    idx = base
    for blk in range(sec.bars // 2):
        shift = [0, 1, 0, -1][blk % 4] if sec.name != "B" else [0, 2, 1, 0][blk % 4]
        resolve = blk == sec.bars // 2 - 1
        cur = idx
        for n, (pos, ln, rest) in enumerate(rhythm):
            bar = blk * 2 + pos // 8
            slot = pos % 8
            cur = max(lo, min(hi, cur + steps[n] + (shift if n == 0 else 0)))
            if slot % 4 == 0:
                cur = snap(cur, deg_at(bar), False)
            if resolve and n == len(rhythm) - 1:
                cur = snap(base, 0, False)
                rest = False
            if rest:
                continue
            start = clock + bar * t.bar_seconds + slot * eighth
            dur = ln * eighth * (0.9 if ln > 1 else 0.8)
            out.append((start, dur, scale_note(tonic, scale, cur), 0.85, None))
        idx = max(lo, min(hi, cur))
        idx -= (idx > base) - (idx < base)                   # drift back toward the centre so the line breathes instead of climbing
        idx -= (idx > base + 2) - (idx < base - 2)
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


def pulse(f: float, n: int, duty: float, vib: float = 0.0) -> np.ndarray:
    tt = np.arange(n) / RATE
    fr = f * (1 + vib * np.sin(2 * np.pi * 5.2 * tt) * np.clip((tt - 0.12) / 0.3, 0, 1))
    ph = (np.cumsum(fr) / RATE) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def tri(f: float, n: int) -> np.ndarray:
    ph = (np.cumsum(np.full(n, f)) / RATE) % 1.0
    w = 4 * np.abs(ph - 0.5) - 1
    return np.round((w + 1) * 7.5) / 7.5 - 1          # the console's triangle has 16 steps


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
    rng = np.random.default_rng(t.seed)
    total = int((t.seconds + 1.5) * RATE)
    left, right = np.zeros(total), np.zeros(total)

    def put(sig: np.ndarray, start: float, p: float, gain: float):
        i = int(start * RATE)
        if i >= total:
            return
        sig = sig[: total - i]
        l, r_ = pan(sig * gain, p)
        left[i:i + len(sig)] += l
        right[i:i + len(sig)] += r_

    duty_for = {s.name: s.duty for s in t.sections}
    sec_at = []
    c = 0.0
    for s in t.sections:
        sec_at.append((c, c + s.bars * t.bar_seconds, s))
        c += s.bars * t.bar_seconds

    def section_of(ts: float) -> Section:
        for a, b, s in sec_at:
            if a <= ts < b:
                return s
        return sec_at[-1][2]

    for start, dur, m, vol, _ in ev["lead"]:
        n = max(8, int(dur * RATE))
        s = section_of(start)
        w = pulse(hz(m), n, s.duty, vib=0.004) * adsr(n, 0.006, 0.09, 0.75, 0.05)
        put(crush(w * vol), start, 0.0, 0.17)
    for start, dur, m, vol, _ in ev["arp"]:
        n = max(8, int(dur * RATE))
        w = pulse(hz(m), n, 0.125, 0.0) * adsr(n, 0.002, 0.05, 0.5, 0.02)
        k = int(round(start / (60.0 / t.bpm / 4)))
        put(crush(w * vol), start, -0.45 if k % 2 == 0 else 0.45, 0.075)
    for start, dur, m, vol, _ in ev["bass"]:
        n = max(8, int(dur * RATE))
        w = tri(hz(m), n) * adsr(n, 0.004, 0.0, 1.0, 0.04)
        put(w * vol, start, 0.0, 0.30)
    for start, dur, _, vol, _ in ev["kick"]:
        n = int(dur * RATE)
        f = np.linspace(130, 44, n)
        w = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.linspace(1, 0, n) ** 1.5
        put(crush(w, 7) * vol, start, 0.0, 0.36)
    for start, dur, _, vol, _ in ev["snare"]:
        n = int(dur * RATE)
        w = (noise(rng, n, 9000) * 0.8 + pulse(190, n, 0.5) * 0.25) * np.linspace(1, 0, n) ** 2
        put(crush(w, 7) * vol, start, 0.15, 0.17)
    for start, dur, _, vol, _ in ev["hat"]:
        n = int(dur * RATE)
        w = noise(rng, n, 24000) * np.linspace(1, 0, n) ** 2
        put(crush(w, 5) * vol, start, 0.4, 0.055)

    stereo = np.stack([left, right])
    # soften the top end a little (study music, not a fire alarm) and remove rumble
    stereo = sosfilt(butter(2, 7500, "lowpass", fs=RATE, output="sos"), stereo, axis=1)
    stereo = sosfilt(butter(2, 35, "highpass", fs=RATE, output="sos"), stereo, axis=1)
    out = resample_poly(stereo, 1, OS, axis=1)
    peak = np.max(np.abs(out))
    return (out / peak * 0.89).astype(np.float32) if peak else out.astype(np.float32)


def describe(t: Track) -> dict:
    return {"seed": t.seed, "key": f"{t.key} {t.mode}", "bpm": t.bpm, "bars": t.bars,
            "seconds": round(t.seconds, 1), "sections": [f"{s.name}x{s.bars}" for s in t.sections]}


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
