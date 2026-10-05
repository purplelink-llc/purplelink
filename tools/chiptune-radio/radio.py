#!/usr/bin/env python3.12
"""Chain seeded tracks into a continuous 'radio' mix with crossfades, a playlist for the now-playing overlay, and an MP3.

    python3.12 radio.py --minutes 10 --start-seed 1 --out-dir out/

The same arguments always give the same mix. A 24/7 stream just keeps asking for the next seed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

import chiptune as c

XFADE = 3.0


def pick_tracks(start_seed: int, seconds: float):
    """Seeds in order, skipping any whose key or tempo is too close to the previous track so the mix does not sit in one place."""
    out, total, seed, prev = [], 0.0, start_seed, None
    while total < seconds + XFADE:
        t = c.plan(seed)
        if prev is None or (t.key != prev.key and abs(t.bpm - prev.bpm) >= 4):
            out.append(t)
            total += t.seconds - (XFADE if prev else 0)
            prev = t
        seed += 1
    return out


def mix(tracks, seconds: float):
    xf = int(XFADE * c.SR)
    fade_in = np.sin(np.linspace(0, np.pi / 2, xf)) ** 1.0
    fade_out = np.cos(np.linspace(0, np.pi / 2, xf))
    audio, plist, cursor = None, [], 0.0
    for i, t in enumerate(tracks):
        a = c.render(t)
        if audio is None:
            audio = a
            start = 0.0
        else:
            start = len(audio[0]) / c.SR - XFADE
            audio[:, -xf:] = audio[:, -xf:] * fade_out + a[:, :xf] * fade_in
            audio = np.concatenate([audio, a[:, xf:]], axis=1)
        plist.append({"n": i + 1, "start": round(start, 1), "seed": t.seed, "title": f"{t.key} {t.mode}, {t.bpm} BPM"})
    n = int(seconds * c.SR)
    audio = audio[:, :n]
    tail = int(4 * c.SR)
    audio[:, -tail:] *= np.linspace(1, 0, tail)
    return audio, plist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--start-seed", type=int, default=1)
    ap.add_argument("--out-dir", default="out")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seconds = a.minutes * 60
    audio, plist = mix(pick_tracks(a.start_seed, seconds), seconds)
    wav = out / "mix.wav"
    c.write_wav(str(wav), audio)
    (out / "playlist.json").write_text(json.dumps(plist, indent=2))
    mp3 = out / f"chiptune-study-{int(a.minutes)}min.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
                    "-c:a", "libmp3lame", "-b:a", "160k", "-ar", "44100", str(mp3)], check=True)
    print(json.dumps({"mp3": str(mp3), "tracks": plist}, indent=2))


if __name__ == "__main__":
    main()
