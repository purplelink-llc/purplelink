#!/usr/bin/env python3
"""Cuts GlobePin Simulator takes into shot clips and synthesises the music bed for the
App Store preview and the 16:9 film (storyboard: storyboards/globepin-preview.md).

    python3 globepin/cut.py <takes-dir> [music-seconds]

Takes are `xcrun simctl io recordVideo` files (1320x2868, variable frame rate). Each shot is cut,
retimed to constant 30 fps, sped up where the plan says so and scaled to 744 px wide, then written
to .cache/globepin-preview/public/clips/<id>.mp4 with shots.json beside it. The music is synthesised
here (no samples, no licence questions) to .cache/globepin-preview/public/music.wav at -16 LUFS.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, butter, sosfilt

HERE = Path(__file__).resolve().parent
PUB = HERE.parent / ".cache" / "globepin-preview" / "public"
FPS = 30

# id, take, in (s), out (s), speed. Durations after retiming are what the edit gets.
SHOTS = [
    ("globe", "02-globe-spin", 6.4, 10.4, 1.0),
    ("empty", "01-onboard-rebuild", 2.8, 4.6, 1.0),
    ("scan", "01-onboard-rebuild", 8.4, 9.8, 1.0),
    ("list", "01-onboard-rebuild", 16.0, 28.0, 3.0),
    ("done", "01-onboard-rebuild", 71.7, 73.3, 1.0),
    ("pins", "01-onboard-rebuild", 91.0, 93.0, 1.0),
    ("timeline", "03-timeline", 16.8, 22.8, 1.5),
    ("stats", "04-stats", 1.3, 8.3, 1.75),
    ("place", "07b-place-zermatt", 7.4, 10.3, 1.0),
    ("goals", "06-goals", 20.6, 23.6, 1.0),
    ("reel", "05-cards-reel", 19.0, 23.0, 1.25),
    ("end", "02-globe-spin", 0.2, 4.2, 1.0),
]


def cut(takes: Path):
    out = PUB / "clips"
    out.mkdir(parents=True, exist_ok=True)
    meta = []
    for sid, take, t0, t1, speed in SHOTS:
        dst = out / f"{sid}.mp4"
        # Simulator recordings only write a frame when the screen changes, so the last frame of a
        # still stretch can outlast the cut; trim to the exact frame count after retiming.
        n = round((t1 - t0) / speed * FPS)
        vf = f"setpts=(PTS-STARTPTS)/{speed},fps={FPS},trim=end_frame={n},scale=744:-2:flags=lanczos,format=yuv420p"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0}", "-to", f"{t1}", "-i", str(takes / f"{take}.mp4"),
                        "-vf", vf, "-an", "-c:v", "libx264", "-crf", "14", "-preset", "slow", str(dst)], check=True)
        frames = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                     "stream=nb_read_frames", "-of", "csv=p=0", str(dst)],
                                    capture_output=True, text=True, check=True).stdout.strip())
        meta.append({"id": sid, "src": f"clips/{sid}.mp4", "frames": frames})
        print(f"{sid:9s} {frames:4d} frames ({frames / FPS:.2f} s)")
    (PUB / "shots.json").write_text(json.dumps(meta, indent=1))


# ---- music --------------------------------------------------------------------------------------

SR = 48000
BPM = 100.0
BEAT = 60.0 / BPM


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def pad(freqs, dur, amp=0.08):
    """Warm pad: three detuned saws per note, low-passed, slow attack and release."""
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for f in freqs:
        for d in (-0.07, 0.0, 0.06):
            ph = 2 * np.pi * f * (1 + d / 100) * t + np.random.uniform(0, 6.28)
            x += sum(np.sin(k * ph) / k for k in range(1, 9))
    sos = butter(2, 1400, "low", fs=SR, output="sos")
    x = sosfilt(sos, x)
    env = np.minimum(1, t / 0.9) * np.minimum(1, (dur - t) / 0.9)
    return amp * x * env / len(freqs)


def pluck(f, dur=1.6, amp=0.22):
    """Soft mallet: sine with a few decaying partials."""
    t = np.arange(int(dur * SR)) / SR
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 6)
         + 0.12 * np.sin(6 * np.pi * f * t) * np.exp(-t * 9))
    return amp * x * np.exp(-t * 2.6) * np.minimum(1, t / 0.004)


def shaker(dur=0.09, amp=0.035):
    n = int(dur * SR)
    x = np.random.normal(size=n)
    sos = butter(2, 6000, "high", fs=SR, output="sos")
    return amp * sosfilt(sos, x) * np.exp(-np.arange(n) / SR * 45)


def add(buf, start, sig):
    i = int(start * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def music(total: float, out: Path):
    np.random.seed(20261031)
    n = int(total * SR)
    L, R = np.zeros(n), np.zeros(n)
    # Fmaj9 - Am7 - Dm9 - Bbmaj7, one chord per bar (4 beats), looping.
    chords = [[53, 57, 60, 64, 67], [57, 60, 64, 67], [50, 57, 60, 64, 65], [46, 53, 57, 62, 64]]
    arps = [[65, 69, 72, 76, 79, 76, 72, 69], [64, 67, 72, 76, 74, 72, 67, 64],
            [62, 65, 69, 72, 74, 72, 69, 65], [62, 65, 69, 70, 74, 70, 69, 65]]
    bar = 4 * BEAT
    nbars = int(np.ceil(total / bar))
    for b in range(nbars):
        t0 = b * bar
        c = chords[b % 4]
        p = pad([midi(m) for m in c], bar + 1.2)
        add(L, t0, p); add(R, t0, p * 0.92)
        bass = pluck(midi(c[0] - 12), dur=bar, amp=0.20)
        add(L, t0, bass); add(R, t0, bass)
        # arpeggio enters on bar 2 and drops out for the last bar so the end card can breathe
        if 1 <= b < nbars - 1:
            for k, m in enumerate(arps[b % 4]):
                s = pluck(midi(m), amp=0.10 + 0.03 * (k == 0))
                pan = 0.5 + 0.35 * np.sin(k * 0.9)
                add(L, t0 + k * BEAT / 2, s * (1 - pan) * 1.4); add(R, t0 + k * BEAT / 2, s * pan * 1.4)
        if 2 <= b < nbars - 1:
            for k in range(8):
                h = shaker(amp=0.03 if k % 2 else 0.018)
                add(L, t0 + k * BEAT / 2 + 0.01, h * 0.8); add(R, t0 + k * BEAT / 2, h)
    # final chord rings out
    ring = pad([midi(m) for m in chords[0]], 3.5, amp=0.09)
    add(L, total - 3.4, ring); add(R, total - 3.4, ring)
    add(L, total - 3.4, pluck(midi(77), dur=3, amp=0.12)); add(R, total - 3.4, pluck(midi(77), dur=3, amp=0.12))
    # room: exponential-decay noise impulse, 2.2 s
    ir_t = np.arange(int(2.2 * SR)) / SR
    irL = np.random.normal(size=ir_t.size) * np.exp(-ir_t * 3.2)
    irR = np.random.normal(size=ir_t.size) * np.exp(-ir_t * 3.2)
    wetL = fftconvolve(L, irL)[:n]; wetR = fftconvolve(R, irR)[:n]
    wetL /= np.max(np.abs(wetL)) + 1e-9; wetR /= np.max(np.abs(wetR)) + 1e-9
    mix = np.stack([L / (np.max(np.abs(L)) + 1e-9) + 0.45 * wetL, R / (np.max(np.abs(R)) + 1e-9) + 0.45 * wetR], 1)
    t = np.arange(n) / SR
    fade = np.minimum(1, t / 0.35) * np.minimum(1, (total - t) / 1.2)
    mix *= fade[:, None]
    mix /= np.max(np.abs(mix)) + 1e-9
    raw = out.with_suffix(".raw.wav")
    wavfile.write(raw, SR, (mix * 0.9 * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", str(SR), "-ac", "2", str(out)], check=True)
    raw.unlink()
    print(f"music {total:.2f} s -> {out}")


if __name__ == "__main__":
    takes = Path(sys.argv[1])
    cut(takes)
    music(float(sys.argv[2]) if len(sys.argv) > 2 else 30.0, PUB / "music.wav")
