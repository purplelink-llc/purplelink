"""Long-form themes: a scene (drawn in code at 320x180) plus an audio palette (which modes and instruments the music uses and which
synthesised ambience sits under it). A new theme is one small file in this folder that subclasses `Theme` and is decorated with
`@register`; `longform.py --theme NAME` finds it by name, and `names()` lists what exists.

What a theme provides:
    name, label, thumb_lines, accent       the id, the short title for thumbnails, the thumbnail text and its colour
    music                                  {"modes": {mode: weight}, "eras": [...], "mood": (lo, hi), "sound": {instrument overrides}}
    bed / bed_solo                         ambience layers (see ambience.LAYERS) under music / when there is no music
    frame(t) -> 320x180 RGB image          the picture t seconds in; must be a pure function of t (any frame can be asked for in any order)
    events                                 [(seconds, kind, duration, ...)] the picture and the sound both read, so a hoot is heard when the owl is seen
    overlay(im, t)                         optional text drawn on the enlarged 1920x1080 frame (the study theme's Pomodoro timer)
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

REGISTRY: dict = {}


def register(cls):
    REGISTRY[cls.name] = cls
    return cls


def names() -> list[str]:
    """Every theme module in this folder, without importing them."""
    return sorted(m.name for m in pkgutil.iter_modules([str(Path(__file__).parent)]) if not m.name.startswith("_"))


def get(name: str):
    if name not in REGISTRY:
        if name not in names():
            raise KeyError(f"unknown theme {name!r}; choose one of {', '.join(names())}")
        importlib.import_module(f"themes.{name}")
    return REGISTRY[name]


class Theme:
    name = "base"
    label = "Ambience"
    thumb_lines = ("COZY", "AMBIENCE")
    accent = (255, 190, 100)
    fps = 10
    music: dict = {"modes": {"major": 4, "mixolydian": 2, "dorian": 2, "minor": 1}, "eras": ["16bit"], "mood": (0.0, 0.45), "sound": {}}
    bed: dict = {"room": 1.0}
    bed_solo: dict | None = None
    music_bed_level = 0.4          # how loud the ambience is under music, against music at 1.0
    thumb_at = 0.3                 # fraction of the video to take the thumbnail frame from
    is_study = False

    def __init__(self, seed: int, seconds: float, bpm_at=None, options: dict | None = None):
        self.seed, self.seconds, self.options = seed, float(seconds), dict(options or {})
        self.bpm_at = bpm_at or (lambda t: 72)
        self.events: list = []

    def progress(self, t: float) -> float:
        return min(1.0, max(0.0, t / self.seconds))

    def audio_events(self) -> list:
        """What the sound needs from the event list: [(seconds, kind, duration)] with kinds owl, settle, gust, sleigh."""
        return [(e[0], e[1], e[2]) for e in self.events if e[1] in ("owl", "settle", "gust", "sleigh")]

    def rain_spans(self) -> list:
        return []

    def frame(self, t: float):
        raise NotImplementedError

    def overlay(self, im, t: float) -> None:
        return None

    def chapters(self) -> list:
        return []


def schedule(seed: int, seconds: float, spec: dict, free: tuple = ("star",), margin: float = 45.0, min_gap: float = 40.0) -> list:
    """Seeded events spread over the video: spec maps a kind to (average seconds between them, how long each lasts). Kinds listed in `free`
    (a shooting star) may overlap anything; the others keep at least `min_gap` seconds apart so the scene never gets busy."""
    import random
    rng = random.Random(seed * 911 + 7)
    raw = []
    for kind, (gap, dur) in sorted(spec.items()):
        t = rng.uniform(0.25, 0.8) * gap
        while t < seconds - margin - dur:
            raw.append((round(t, 2), kind, dur))
            t += gap * rng.uniform(0.6, 1.4) + dur
    raw.sort()
    out, last_end = [], -1e9
    for e in raw:
        if e[1] in free:
            out.append(e)
        elif e[0] >= last_end + min_gap:
            out.append(e)
            last_end = e[0] + e[2]
    return out
