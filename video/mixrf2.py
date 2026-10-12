#!/usr/bin/env python3
"""Sound mix for the RubbleFront v2 trailer: the game's own battle music in sections, the game's own effects recorded with the
footage, and a few synthesised hits and risers (generated here from sine waves and noise, nothing sampled).

    python3 mixrf2.py mix.json out.wav

mix.json: {"dur": 72, "music": [{"file","in","t","dur","gain_db","fade_in","fade_out"}], "music_env": [{"t","db"}],
           "game": [{"file","in","dur","t","gain_db"}], "synth": [{"t","kind","dur","gain_db"}], "peak_db": -1.5}
kinds: boom, hit, slam, riser, whoosh, tick, drop
"""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, lfilter, sosfilt

SR = 48000
rng = np.random.default_rng(7)


def load(path, ss=0.0, t=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(ss)]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2).copy()


def db(x):
    return 10 ** (x / 20)


def place(mix, x, t0, gain=1.0):
    i0 = int(round(t0 * SR))
    if i0 < 0:
        x = x[-i0:]
        i0 = 0
    n = min(len(x), len(mix) - i0)
    if n > 0:
        mix[i0:i0 + n] += x[:n] * gain


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, btype="low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, btype="high", fs=SR, output="sos"), x)


def st(x):
    return np.stack([x, x], axis=1).astype(np.float32)


def boom(dur=2.2):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 34 + 70 * np.exp(-t * 7)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    noise = lp(rng.standard_normal(n), 900) * np.exp(-t * 5.5) * 0.9
    click = hp(rng.standard_normal(n), 2500) * np.exp(-t * 90) * 0.35
    tail = lp(rng.standard_normal(n), 220) * np.exp(-t * 1.6) * 0.5
    return st(np.tanh(1.7 * (body * 1.1 + noise + click + tail)) * 0.95)


def hit(dur=0.7):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 52 + 120 * np.exp(-t * 22)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    noise = lp(rng.standard_normal(n), 3500) * np.exp(-t * 20) * 0.7
    return st(np.tanh(1.5 * (body + noise)) * 0.9)


def slam(dur=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 46 + 70 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    tick = hp(rng.standard_normal(n), 3000) * np.exp(-t * 140) * 0.4
    return st(np.tanh(1.3 * (body + tick)) * 0.8)


def riser(dur):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    blk = 1024
    zi = None
    for i in range(0, n, blk):
        fc = 250 * (30 ** (p[min(i, n - 1)]))
        fc = min(fc, 14000)
        b, a = butter(2, fc / (SR / 2), btype="low")
        seg = noise[i:i + blk]
        if zi is None:
            zi = np.zeros(max(len(a), len(b)) - 1)
        y, zi = lfilter(b, a, seg, zi=zi)
        out[i:i + blk] = y
    env = p ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * p ** 2) / SR) * 0.18
    x = (out * 0.9 + tone) * env
    x[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
    return st(x * 0.9)


def whoosh(dur=0.6):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    zi = None
    for i in range(0, n, 512):
        fc = 400 + 5000 * np.sin(np.pi * p[min(i, n - 1)])
        b, a = butter(2, [max(200, fc * 0.5) / (SR / 2), min(fc * 1.3, 20000) / (SR / 2)], btype="band")
        seg = noise[i:i + 512]
        if zi is None:
            zi = np.zeros(max(len(a), len(b)) - 1)
        y, zi = lfilter(b, a, seg, zi=zi)
        out[i:i + 512] = y
    env = np.sin(np.pi * p) ** 1.5
    return st(out * env * 1.2)


def tick(dur=0.25):
    n = int(dur * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 70 * t) * np.exp(-t * 26)
    return st(body * 0.9)


def drop(dur=1.2):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 120 * np.exp(-t * 3.2) + 28
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.3)
    return st(np.tanh(1.4 * body) * 0.9)


KINDS = {"boom": boom, "hit": hit, "slam": slam, "whoosh": whoosh, "tick": tick, "drop": drop}


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    n = int(spec["dur"] * SR)
    mus = np.zeros((n, 2), np.float32)
    fx = np.zeros((n, 2), np.float32)
    syn = np.zeros((n, 2), np.float32)
    for m in spec.get("music", []):
        x = load(m["file"], m.get("in", 0.0), m.get("dur"))
        g = np.ones(len(x), np.float32)
        fi, fo = int(m.get("fade_in", 0.0) * SR), int(m.get("fade_out", 0.0) * SR)
        if fi:
            g[:fi] = np.linspace(0, 1, fi) ** 2
        if fo and fo < len(g):
            g[-fo:] *= np.linspace(1, 0, fo) ** 2
        place(mus, x * g[:, None], m["t"], db(m.get("gain_db", 0)))
    env = spec.get("music_env")
    if env:
        ts = np.array([e["t"] for e in env]); ds = np.array([e["db"] for e in env])
        tt = np.arange(n) / SR
        mus *= (10 ** (np.interp(tt, ts, ds) / 20))[:, None].astype(np.float32)
    for e in spec.get("game", []):
        x = load(e["file"], e.get("in", 0.0), e["dur"])
        f = int(0.012 * SR)
        if len(x) > 2 * f:
            x[:f] *= np.linspace(0, 1, f)[:, None]
            x[-f:] *= np.linspace(1, 0, f)[:, None]
        place(fx, x, e["t"], db(e.get("gain_db", -6)))
    for e in spec.get("synth", []):
        k = e["kind"]
        if k == "riser":
            x = riser(e["dur"])
        elif k in ("whoosh", "boom", "drop") and e.get("dur"):
            x = KINDS[k](e["dur"])
        else:
            x = KINDS[k]()
        # risers and whooshes end on their time; hits start on it
        t0 = e["t"] - (e["dur"] if k == "riser" else (0.25 * e["dur"] if k == "whoosh" and e.get("dur") else 0.0))
        place(syn, x, t0, db(e.get("gain_db", 0)))
    mix = mus + fx + syn * db(spec.get("synth_db", -3))
    pk = float(np.abs(mix).max()) or 1.0
    lim = db(spec.get("peak_db", -1.5))
    if pk > lim:
        mix *= lim / pk
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"mix: {spec['dur']:.1f}s, {len(spec.get('music', []))} music, {len(spec.get('game', []))} game sfx, {len(spec.get('synth', []))} synth, peak {20*np.log10(pk):.1f} dBFS -> {out}")


if __name__ == "__main__":
    main()
