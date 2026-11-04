"""Studio voices: plays composer channels on Apple's sampled instruments instead of the numpy chip voices.

Melodic channels go through `aurender` (a small Swift host, `aurender/aurender.swift`) that plays one Logic/GarageBand `.exs` instrument dry
with sample-accurate MIDI. Drum channels are one-shot hits from GarageBand's Drum Machine Designer kits, mixed here in numpy. Either way the
result is a dry stereo stem that `chiptune.render()` puts on its usual group bus, so ducking, reverb, the lowpass and the levelling still apply.

There is no fallback: a missing instrument, a failed host or a silent stem raises, so a video never ships with the wrong sound.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
HERE = Path(__file__).resolve().parent
SRC = HERE / "aurender" / "aurender.swift"
BIN = HERE / ".aurender-bin"
LOGIC = Path("/Library/Application Support/Logic/Sampler Instruments")
KITS = Path("/Library/Application Support/Logic/Ultrabeat Samples/Drum Machine Designer")
TIMEOUT = 900                                   # seconds for one stem; a 2-hour bass stem takes about 2 minutes


def ensure_binary() -> Path:
    """Builds aurender with swiftc when it is missing or older than its source. A lock keeps parallel workers from building it at once."""
    with open(HERE / ".aurender-build.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not BIN.exists() or BIN.stat().st_mtime < SRC.stat().st_mtime:
            tmp = BIN.with_suffix(".tmp")
            subprocess.run(["swiftc", "-O", str(SRC), "-o", str(tmp)], check=True, capture_output=True, timeout=600)
            os.replace(tmp, BIN)
    return BIN


def midi_events(notes, latency: int, transpose: int = 0) -> list[list[int]]:
    """Composer notes `(start_s, dur_s, midi, vol, extra)` to `[frame, status, note, velocity]` rows, sorted.

    Volumes are scaled to this channel's loudest note, then to velocity 30..127, so the sampler's velocity layers follow the composer's
    accents. Notes start `latency` frames early, which cancels the instrument's measured attack delay. A note that starts while the same pitch
    still sounds ends that earlier note first (a sampler voice cannot overlap itself cleanly). At one frame, note-offs come before note-ons."""
    if not notes:
        return []
    top = max(n[3] for n in notes) or 1.0
    ons = sorted((max(0, int(round(s * SR)) - latency), max(1, int(round(d * SR))), int(m) + transpose, v) for s, d, m, v, _ in notes)
    off_row: dict[int, list] = {}                 # pitch -> its pending note-off row
    rows = []
    for f, n, m, v in ons:
        if not 0 <= m <= 127:
            continue
        prev = off_row.get(m)
        if prev is not None and prev[0] > f:      # same pitch still sounding: release it here
            prev[0] = f
        vel = int(round(30 + 97 * min(1.0, max(0.0, v / top))))
        off = [f + n, 0x80, m, 0]
        rows += [[f, 0x90, m, vel], off]
        off_row[m] = off
    return sorted(rows, key=lambda r: (r[0], 0 if r[1] == 0x80 else 1, r[2]))


def sampled_stem(exs: str, notes, total: int, latency: int = 0, transpose: int = 0) -> np.ndarray:
    """Renders `notes` on the `.exs` instrument (path relative to the Logic library) into a dry (2, total) float32 stem."""
    path = LOGIC / exs
    if not path.is_file():
        raise FileNotFoundError(f"studio instrument missing: {path}")
    rows = midi_events(notes, latency, transpose)
    with tempfile.TemporaryDirectory(prefix="aurender-") as d:
        job, out = Path(d) / "job.json", Path(d) / "out.f32"
        job.write_text(json.dumps({"sr": SR, "frames": total, "exs": str(path), "events": rows}))
        p = subprocess.run([str(ensure_binary()), str(job), str(out)], capture_output=True, text=True, timeout=TIMEOUT)
        if p.returncode:
            raise RuntimeError(f"aurender failed on {exs}: {p.stderr.strip()[:300]}")
        x = np.fromfile(out, np.float32)
    if x.size != 2 * total:
        raise RuntimeError(f"aurender wrote {x.size} samples for {exs}, expected {2 * total}")
    x = x.reshape(2, total)
    if rows and not np.any(x):
        raise RuntimeError(f"aurender rendered silence for {exs}")
    return x


_HITS: dict[Path, np.ndarray] = {}


def hit(kit: str, name: str) -> np.ndarray:
    """One drum hit of a Drum Machine Designer kit, e.g. hit("Silverlake GB", "Kick_1") as a (2, n) float32 array."""
    tag = kit.replace(" GB", "").replace(" ", "")
    path = KITS / kit / f"{name}_{tag}_GB.aif"
    if path not in _HITS:
        if not path.is_file():
            raise FileNotFoundError(f"studio drum hit missing: {path}")
        x, sr = sf.read(str(path), dtype="float32", always_2d=True)
        if sr != SR:
            raise RuntimeError(f"{path} is {sr} Hz, expected {SR}")
        _HITS[path] = np.ascontiguousarray(x.T if x.shape[1] == 2 else np.repeat(x.T, 2, axis=0))
    return _HITS[path]


# composer drum channel -> hit chooser (dur, vol, extra) -> sample name
DRUM_MAP = {
    "kick": lambda d, v, ex: "Kick_1",
    "snare": lambda d, v, ex: "Snare_1" if v >= 0.5 else "Snare_3",         # quiet snare notes are ghost notes
    "hat": lambda d, v, ex: "Hi-Hat_Open" if d >= 0.18 else "Hi-Hat_1",
    "tom": lambda d, v, ex: "Tom_High" if ex.get("pitch", 80) >= 95 else ("Tom_Mid" if ex.get("pitch", 80) >= 75 else "Tom_Low"),
}


def drum_stem(kit: str, channel: str, notes, total: int) -> np.ndarray:
    """Places one-shot hits for a composer drum channel. A closed hat chokes a ringing open hat, as on a real kit."""
    out = np.zeros((2, total), np.float32)
    top = max((n[3] for n in notes), default=1.0) or 1.0
    choose = DRUM_MAP[channel]
    open_end = -1
    for s, d, _, v, ex in sorted(notes, key=lambda n: n[0]):
        i = int(round(s * SR))
        if i >= total:
            break
        name = choose(d, v / top, ex or {})
        if channel == "hat" and name != "Hi-Hat_Open" and open_end > i:
            fade = min(220, open_end - i)
            out[:, i:i + fade] *= np.linspace(1, 0, fade, dtype=np.float32)
            out[:, i + fade:open_end] = 0
        x = hit(kit, name)
        n = min(x.shape[1], total - i)
        out[:, i:i + n] += x[:, :n] * np.float32(0.35 + 0.65 * v / top)
        if name == "Hi-Hat_Open":
            open_end = i + n
    return out


def level(x: np.ndarray, rms: float) -> np.ndarray:
    """Scales a stem so its loud passages (the RMS of 50 ms windows above 10% of the loudest) sit at `rms`; returns it unchanged when silent."""
    w = 2205
    n = x.shape[1] // w * w
    r = np.sqrt((x[:, :n].reshape(2, -1, w) ** 2).mean(axis=(0, 2)))
    if not r.size or r.max() == 0:
        return x
    loud = r[r > 0.1 * r.max()]
    return x * np.float32(rms / float(np.sqrt((loud ** 2).mean())))
