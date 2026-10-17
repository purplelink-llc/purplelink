"""The study room from the 24/7 stream (scene.py), reused as it is: someone working at a desk, a window that goes through a whole day and night
every two hours, rain, a cat, a dog that visits, a friend, a robin, the robot vacuum. For an uploaded video the live-stream extras are left off
(world clocks, now-playing, the subscribe nudge); with `--pomodoro 25/5` a timer and a tally of finished focus blocks are drawn instead, and a soft
chime sounds at each change. The timer starts at the top of a focus block, so the person at the desk takes their break when the timer says break."""
from __future__ import annotations

import math
import random

import scene as sc
import pixfont
from themes import Theme, register

FOCUS, BREAK = sc.FOCUS, sc.BREAK


@register
class Study(Theme):
    name = "study"
    label = "Study Room"
    thumb_lines = ("STUDY", "WITH ME")
    accent = (190, 140, 255)
    thumb_at = 0.26
    is_study = True
    music = {"modes": {"major": 4, "mixolydian": 3, "dorian": 3, "lydian": 2, "minor": 2}, "eras": ["16bit", "8bit", "16bit", "synth", "hybrid", "16bit"],
             "mood": (0.0, 0.62), "sound": {}}
    bed = {"rain": 1.0, "room": 1.0}
    bed_solo = {"rain": 1.0, "room": 1.0}
    music_bed_level = 0.5

    def __init__(self, seed, seconds, bpm_at=None, options=None):
        super().__init__(seed, seconds, bpm_at, options)
        sc.ANIM_FPS = self.fps                                    # the scene steps at the video's own rate, so 10 fps frames are never uneven repeats
        self.scene = sc.Scene(seed=seed)
        self.pomodoro = self.options.get("pomodoro")              # (focus_minutes, break_minutes) or None
        if self.pomodoro and tuple(self.pomodoro) != (25, 5):
            raise ValueError("only 25/5 is supported: the person at the desk takes a 5 minute break on the half hour")
        self.base = (1_760_000_000 // 1800 + seed % 1000) * 1800.0  # a wall time on a half-hour boundary: t = 0 is the start of a focus block
        self.h0 = random.Random(seed).choice([20.5, 21.5, 22.5, 6.0, 12.0, 17.0])       # the scene hour the video starts at
        r = random.Random(seed * 3 + 1)
        span = r.uniform(0.18, 0.28) * seconds
        start = r.uniform(0.3, 0.55) * seconds
        self.rain = [(start, min(seconds - 60, start + span))] if r.random() < 0.8 else []
        self.events = []

    def rain_spans(self):
        return self.rain

    def _raining(self, t):
        return any(a <= t <= b for a, b in self.rain)

    def frame(self, t: float):
        hour = sc.hour_at(self.h0 / 24.0 * 7200.0 + t)
        return self.scene.frame(t, hour, self._raining(t), self.bpm_at(t), "", self.base + t, None, hud=False, events=True, lights_dy=10,
                                season=self.options.get("season"))

    # ---- the Pomodoro timer, drawn at full size on the enlarged frame
    def overlay(self, im, t: float) -> None:
        if not self.pomodoro:
            return
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        panel, bar, text, dim, green = sc.C["panel"], sc.C["bar"], sc.C["text"], sc.C["text_dim"], sc.C["plant"]
        sec = t % (FOCUS + BREAK)
        focus = sec < FOCUS
        left = int((FOCUS - sec) if focus else (FOCUS + BREAK - sec))
        total = FOCUS if focus else BREAK
        colour = bar if focus else green
        d.rectangle([24, 880, 24 + 560, 1054], fill=panel)
        d.rectangle([24, 880, 24 + 560, 886], fill=colour)
        pixfont.draw(im, 48, 904, "FOCUS" if focus else "BREAK", 5, colour)
        pixfont.draw(im, 48, 952, f"{left // 60:02d}:{left % 60:02d}", 9, text)
        d.rectangle([48, 1026, 48 + 512, 1038], fill=sc.C["wall3"])
        d.rectangle([48, 1026, 48 + int(512 * (1 - left / total)), 1038], fill=colour)
        done = int(t // (FOCUS + BREAK)) + (1 if sec >= FOCUS else 0)
        pw, ph = 296, 112
        px, py = 1920 - 24 - pw, 24
        d.rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], fill=sc.C["desk_dark"])
        d.rectangle([px, py, px + pw, py + ph], fill=panel)
        pixfont.draw(im, px + 14, py + 12, "POMODOROS", 3, dim)
        n_txt = f"{done}"
        pixfont.draw(im, px + pw - 14 - pixfont.width(n_txt, 5), py + 8, n_txt, 5, text)
        for i in range(min(done, 24)):
            tx, ty = px + 14 + (i % 12) * 23, py + 50 + (i // 12) * 28
            for ry, row in enumerate(sc.Scene.TOMATO):
                for rx, ch in enumerate(row):
                    if ch != ".":
                        d.rectangle([tx + rx * 3, ty + ry * 3, tx + rx * 3 + 2, ty + ry * 3 + 2], fill=sc.Scene.TOMATO_COLOURS[ch])
        if done == 0:
            pixfont.draw(im, px + 14, py + 56, "FIRST ONE SOON", 3, dim)

    def chapters(self) -> list:
        if not self.pomodoro:
            return []
        out, n, t = [], 1, 0.0
        while t < self.seconds - 60:
            out.append((t, f"Focus {n}"))
            if t + FOCUS < self.seconds - 30:
                out.append((t + FOCUS, "Break"))
            t += FOCUS + BREAK
            n += 1
        return out
