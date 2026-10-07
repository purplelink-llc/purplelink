#!/usr/bin/env python3
"""Mixes a short non-narration sound bed (for example the real recorded key and click sounds bundled in an app)
from a list of timed events, ducked under the narration.

    python3 mixbed.py bed.json out.wav

bed.json:
  { "dur": 24.0,                       # seconds of output
    "duckGain": 0.4,                   # gain while a duck window is active (linear)
    "duck": [[t0, t1], ...],           # narration windows, product-local seconds
    "events": [ { "t": 1.2, "file": "assets/keyfeel/samples/tactile/press-03.wav",
                  "gain": 0.6, "pan": -0.2, "rate": 1.0 }, ... ] }   # file paths are relative to video/

Samples are mono or stereo 16-bit WAV. rate resamples (pitch). Output: 44.1 kHz stereo 16-bit WAV, peak
limited to -3 dBFS. Narration is normalised to -16 LUFS separately (audio.mjs); this bed is not normalised, its
gains come from the plan so the mix stays under the voice.
"""
import json, sys, wave
from pathlib import Path
import numpy as np

SR = 44100
HERE = Path(__file__).resolve().parent


def read_wav(path):
    w = wave.open(str(path))
    n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    assert sw == 2, f"{path}: 16-bit only"
    x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768
    x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x).astype(np.float32)
    return x


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    n = int(spec["dur"] * SR)
    mix = np.zeros((n, 2), dtype=np.float32)
    cache = {}
    for e in spec["events"]:
        f = e["file"]
        if f not in cache:
            cache[f] = read_wav(HERE / f)
        x = cache[f]
        r = float(e.get("rate", 1.0))
        if abs(r - 1) > 1e-4:
            x = np.interp(np.arange(int(len(x) / r)) * r, np.arange(len(x)), x).astype(np.float32)
        i0 = int(round(e["t"] * SR))
        if i0 >= n:
            continue
        seg = x[: n - i0] * float(e.get("gain", 1.0))
        a = (float(e.get("pan", 0.0)) + 1) * np.pi / 4  # equal-power pan
        mix[i0 : i0 + len(seg), 0] += seg * np.cos(a)
        mix[i0 : i0 + len(seg), 1] += seg * np.sin(a)
    # duck under narration: smoothed envelope, quick attack, slower release
    env = np.ones(n, dtype=np.float32)
    dg = float(spec.get("duckGain", 0.4))
    for t0, t1 in spec.get("duck", []):
        env[max(0, int(t0 * SR)) : min(n, int(t1 * SR))] = dg
    att, rel = int(0.04 * SR), int(0.25 * SR)
    sm = np.empty_like(env)
    cur = 1.0
    for i in range(n):
        tgt = env[i]
        k = 1 / att if tgt < cur else 1 / rel
        cur += (tgt - cur) * min(1.0, k * 3)
        sm[i] = cur
    mix *= sm[:, None]
    pk = float(np.abs(mix).max()) or 1.0
    lim = 10 ** (-3 / 20)
    if pk > lim:
        mix *= lim / pk
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    print(f"bed: {len(spec['events'])} events, {spec['dur']:.1f}s, peak {20*np.log10(pk):.1f} dBFS -> {out}")


if __name__ == "__main__":
    main()
