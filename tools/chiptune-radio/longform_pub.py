#!/usr/bin/env python3.12
"""Everything around a rendered long-form video that is not the video: its thumbnail, its upload metadata, and a check of the finished file.

    python3.12 longform_pub.py thumb    --theme campfire --hours 2 --out campfire-2h-thumb.jpg
    python3.12 longform_pub.py meta     --theme campfire --hours 2 --slug campfire-2h --out campfire-2h.json
    python3.12 longform_pub.py verify   --video campfire-2h.mp4 --frames-dir DIR      # ffprobe, loudness, silence, four frames
    python3.12 longform_pub.py meta     --theme campfire --sound brown --hours 10 --dark 300 --slug campfire-brown-10h --out campfire-brown-10h.json

`--sound` and `--dark` are the same options as in longform.py; verify takes `--sound` too, because each sound has its own loudness target.
Titles, tags and hashtags use the ranked search phrases from keywords.py when its research file exists.

Nothing here uploads anything. The metadata file is what a person (or a later script) pastes into YouTube Studio.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageDraw

import keywords
import longform as lf
import pixfont
import px
import sounds
import themes

THUMB = (1280, 720)          # an exact 4x of the 320x180 art
THUMB_SCALE = THUMB[0] // px.W
MAX_THUMB_BYTES = 2_000_000

# per theme: where the title block sits, as fractions of the thumbnail, and which text colour goes with the art
THUMB_LAYOUT = {
    "campfire": {"x": 0.5, "y": 0.06, "align": "center"},
    "halloween": {"x": 0.5, "y": 0.05, "align": "center"},
    "winter": {"x": 0.5, "y": 0.04, "align": "center"},
    "study": {"x": 0.5, "y": 0.05, "align": "center"},
}


THUMB_SOUND = {"brown": "BROWN NOISE", "pink": "PINK NOISE", "white": "WHITE NOISE", "binaural-alpha": "10 HZ BINAURAL", "binaural-theta": "6 HZ BINAURAL",
               "binaural-delta": "2 HZ BINAURAL", "synth": "AMBIENT SYNTH", "lofi": "LOFI", "rain": "RAIN SOUNDS", "thunderstorm": "THUNDERSTORM",
               "fireplace": "FIREPLACE", "ocean": "OCEAN WAVES", "wind": "WIND SOUNDS", "fan": "FAN SOUNDS", "airplane": "AIRPLANE CABIN"}


def thumb_text(theme_name: str, sound: str, musical: bool, season: str, uhd: bool, dark: float) -> list | None:
    """Thumbnail text for a holiday or 4K video: the searched phrase on line one, the scene (with 4K when the picture stays on screen) on line two.
    None for any other video, which keeps its usual text."""
    if not (uhd or season in HOLIDAYS):
        return None
    four = " 4K" if uhd and not dark else ""
    hol = {"christmas": "CHRISTMAS", "newyear": "NEW YEAR"}.get(season, "")
    if sound == "fireplace":
        return [hol or "FIREPLACE", ("FIREPLACE" if hol else "SOUNDS") + four]
    if musical:
        music = "LOFI" if sound == "lofi" else ""
        if theme_name == "study":
            return [" ".join(x for x in (hol, music or "STUDY") if x), ("STUDY" if music else "WITH ME") + four]
        return [hol or "COZY", "CABIN" + four if theme_name == "winter" else themes.get(theme_name).thumb_lines[1] + four]
    return [THUMB_SOUND[sound], SCENE_NAME.get(theme_name, "CABIN").upper() + four]


def make_thumbnail(theme_name: str, seconds: float, seed: int, out: Path, options: dict | None = None, music: bool = True, sound: str = "chiptune",
                   uhd: bool = False, dark: float = 0.0) -> Path:
    """A 1280x720 JPEG: a clean frame of the scene, enlarged exactly 4x, with a darkened band behind big pixel-font title text. The bottom-right
    corner is left empty because YouTube puts the duration stamp there."""
    cls = themes.get(theme_name)
    tracks = lf.plan_tracks(cls, seconds, seed, lf.music_cfg(cls, sound))
    theme = cls(seed, seconds, bpm_at=lf.bpm_lookup(tracks), options=options or {})
    t = theme.progress(theme.thumb_at * seconds) * seconds
    art = px.scale_up(theme.frame(t), THUMB_SCALE).convert("RGBA")
    lay = THUMB_LAYOUT.get(theme_name, {"x": 0.5, "y": 0.05, "align": "center"})
    lines = list(cls.thumb_lines)
    if not music:
        lines = [lines[0], lines[1]]
    if sound != "chiptune":                                          # the searched phrase leads, the scene's own word second
        lines = [THUMB_SOUND[sound], lines[1]]
    holiday = thumb_text(theme_name, sound, sounds.spec(sound).musical and music, (options or {}).get("season", ""), uhd, dark)
    if holiday:
        lines = holiday
    scale = 16
    widths = [pixfont.width(s, scale) for s in lines]
    while max(widths) > THUMB[0] - 120 and scale > 8:
        scale -= 4
        widths = [pixfont.width(s, scale) for s in lines]
    line_h = pixfont.height(scale) + scale * 2
    block_h = line_h * len(lines)
    y0 = int(THUMB[1] * lay["y"])
    # a soft dark band behind the text so it reads over any part of the picture
    band = Image.new("RGBA", THUMB, (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    pad = 28
    for i in range(pad):
        bd.rectangle([0, y0 - pad + i, THUMB[0], y0 - pad + i], fill=(8, 6, 16, int(80 * i / pad)))
    bd.rectangle([0, y0, THUMB[0], y0 + block_h], fill=(8, 6, 16, 80))
    for i in range(pad):
        bd.rectangle([0, y0 + block_h + i, THUMB[0], y0 + block_h + i], fill=(8, 6, 16, int(80 * (1 - i / pad))))
    art = Image.alpha_composite(art, band)
    for i, (s, w) in enumerate(zip(lines, widths)):
        x = int((THUMB[0] - w) / 2) if lay["align"] == "center" else int(THUMB[0] * lay["x"])
        colour = (255, 255, 255) if i == 0 else cls.accent
        pixfont.draw(art, x, y0 + i * line_h + scale, s, scale, colour, shadow=(10, 6, 20))
    out = Path(out)
    rgb = art.convert("RGB")
    for q in (92, 88, 82, 76):
        rgb.save(out, "JPEG", quality=q, subsampling=0, optimize=True)
        if out.stat().st_size < MAX_THUMB_BYTES:
            break
    return out


# ------------------------------------------------------------------------------------------------------------------------ metadata
def hours_text(seconds: float) -> str:
    h = seconds / 3600
    if abs(h - round(h)) < 0.01:
        n = int(round(h))
        return f"{n} Hour" + ("s" if n != 1 else "")
    return f"{int(round(seconds / 60))} Minutes"


def clock(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


COPY = {
    "campfire": {
        "scene": "a pixel-art campfire in a night forest clearing: flickering flames, rising embers, fireflies, a tent, a moon crossing the sky, and now and then an owl or a shooting star",
        "sound_music": "soft chiptune music with the sound of a crackling fire, a little wind in the pines and distant crickets under it",
        "sound_solo": "the sound of a crackling fire, wind in the pines and distant crickets, with no music",
        "use": "reading, studying, working or winding down",
        "tags": ["campfire ambience", "campfire sounds", "crackling fire", "night forest ambience", "fireplace sounds", "pixel art", "relaxing ambience", "study ambience"],
        "tags_music": ["chiptune", "8-bit music", "study music", "chill chiptune", "lofi chiptune"],
        "title_music": "Cozy Campfire Ambience with Chiptune Music, {dur}",
        "title_solo": "Campfire Sounds, Crackling Fire and Night Wind, No Music, {dur}",
        "category": "Music", "category_solo": "Entertainment", "hashtags": "#campfire #ambience #chiptune",
    },
    "halloween": {
        "scene": "a pixel-art Halloween porch at night: jack-o'-lanterns with flickering faces, a big moon with clouds crossing it, a black cat on the railing, a lit house on the hill, drifting fog, and now and then a flock of bats or a small friendly ghost",
        "sound_music": "gentle minor-key chiptune music with a low hollow wind and a few late crickets under it",
        "sound_solo": "a low hollow wind and a few late crickets, with no music",
        "use": "studying, reading, working, or a quiet Halloween evening",
        "tags": ["halloween ambience", "halloween music", "spooky ambience", "cozy halloween", "jack o lantern", "pixel art", "halloween study music"],
        "tags_music": ["chiptune", "8-bit music", "spooky chiptune", "study music"],
        "title_music": "Halloween Ambience, Spooky Cozy Porch with Chiptune Music, {dur}",
        "title_solo": "Halloween Porch Ambience, Wind and Crickets, No Music, {dur}",
        "category": "Music", "category_solo": "Entertainment", "hashtags": "#halloween #ambience #chiptune",
    },
    "winter": {
        "scene": "a pixel-art snowed-in cabin at night: snow falling past the window, a stone fireplace with stockings, a lit tree, a cat asleep on the rug, a mug steaming on the sill, and now and then a sleigh crossing the sky",
        "sound_music": "cozy chiptune music in major keys with bells and plucks, with a soft fireplace crackle and a muffled wind outside",
        "sound_solo": "a soft fireplace crackle and a muffled wind outside, with no music",
        "use": "studying, reading, working, or a quiet winter evening",
        "tags": ["winter ambience", "cozy cabin", "fireplace sounds", "snow ambience", "winter cabin", "pixel art", "cozy winter music", "study ambience"],
        "tags_music": ["chiptune", "8-bit music", "christmas chiptune", "holiday ambience", "study music"],
        "title_music": "Cozy Winter Cabin Ambience, Fireplace and Snow with Chiptune Music, {dur}",
        "title_solo": "Cozy Winter Cabin Ambience, Fireplace and Snow, No Music, {dur}",
        "category": "Music", "category_solo": "Entertainment", "hashtags": "#winter #ambience #chiptune",
    },
    "study": {
        "scene": "a pixel-art study room: someone working at a desk in front of a window that goes through a whole day and night, with rain, a cat, a visiting dog and friend, a robin and a robot vacuum",
        "sound_music": "relaxed chiptune music that drifts between calm and a little livelier, with rain when it rains in the window",
        "sound_solo": "soft room tone and rain when it rains in the window, with no music",
        "use": "studying, reading or working",
        "tags": ["study with me", "pomodoro", "pomodoro timer", "study music", "chiptune", "8-bit music", "pixel art", "focus music", "lofi chiptune"],
        "tags_music": [],
        "title_music": "Study With Me, {dur} with Chiptune Music",
        "title_music_pomo": "Study With Me, {dur}, 25/5 Pomodoro Timer with Chiptune Music",
        "title_solo": "Study With Me, {dur}, No Music",
        "title_solo_pomo": "Study With Me, {dur}, 25/5 Pomodoro Timer, No Music",
        "category": "Education", "category_solo": "Education", "hashtags": "#studywithme #pomodoro #chiptune",
    },
}

DISCLOSURE = {
    "answer": "Yes",
    "decision": "Answer Yes to 'altered or synthetic content' in Studio. This is the cautious reading, and Ben can change it.",
    "reasoning": ("YouTube's disclosure page lists music made with generative tools as something to disclose, and says a label may appear in the player or the "
                  "expanded description. This music and ambience are composed and synthesised by a program written by us, not by a trained model, and none of it "
                  "imitates a real person or a real recording, so a strict reading says no disclosure is required. Answering Yes costs a small label and removes any "
                  "chance of a later dispute over undisclosed generated audio. The picture is plainly animated pixel art, which the page says needs no disclosure. "
                  "Source: https://support.google.com/youtube/answer/14328491, checked 2026-10-16."),
}


TITLE_THEME = {"campfire": "Crackling Campfire", "halloween": "Halloween Porch", "winter": "Winter Cabin", "study": "Study Room"}
SCENE_SHORT = {"campfire": "a pixel-art campfire at night", "halloween": "a pixel-art Halloween porch", "winter": "a pixel-art snowed-in cabin",
               "study": "a pixel-art study room"}
# title lead phrases per sound; the first is the default, the others win only if the keyword research ranks them higher
LEADS = {"brown": ["Brown Noise"], "pink": ["Pink Noise"], "white": ["White Noise"],
         "binaural-alpha": ["Alpha Binaural Beats 10 Hz", "10 Hz Binaural Beats"], "binaural-theta": ["Theta Binaural Beats 6 Hz", "6 Hz Binaural Beats"],
         "binaural-delta": ["Delta Binaural Beats 2 Hz", "2 Hz Binaural Beats"], "synth": ["Ambient Synth Music", "Ambient Drone"],
         "lofi": ["Lofi Study Music", "Lofi Chiptune"], "rain": ["Rain Sounds", "Rain Sounds for Sleeping"], "thunderstorm": ["Thunderstorm Sounds"],
         "fireplace": ["Fireplace Sounds", "Crackling Fire Sounds"], "ocean": ["Ocean Waves Sounds"], "wind": ["Wind Sounds"],
         "fan": ["Fan Sounds", "Fan Noise"], "airplane": ["Airplane Cabin Sounds", "Airplane Noise"]}
# the plain first sentence's description of the sound (kept short: the first 150 characters of a description are what search and answer engines show)
WHAT_SHORT = {"brown": "Deep, smooth brown noise", "pink": "Smooth pink noise", "white": "Steady white noise",
              "binaural-alpha": "A 10 Hz binaural beat (use headphones)", "binaural-theta": "A 6 Hz binaural beat (use headphones)",
              "binaural-delta": "A 2 Hz binaural beat (use headphones)", "synth": "Slow ambient synth pads, no beat and no melody",
              "lofi": "Slow, soft lofi chiptune music", "rain": "Steady rain with distant thunder", "thunderstorm": "Heavy rain with rolling thunder",
              "fireplace": "A crackling fireplace", "ocean": "Waves rolling onto a shore", "wind": "Wind with slow gusts", "fan": "The steady whoosh of a fan",
              "airplane": "The low roar of an airplane cabin"}
SOUND_HASH = {"brown": "#brownnoise", "pink": "#pinknoise", "white": "#whitenoise", "binaural-alpha": "#binauralbeats", "binaural-theta": "#binauralbeats",
              "binaural-delta": "#binauralbeats", "synth": "#ambientmusic", "lofi": "#lofi", "rain": "#rainsounds", "thunderstorm": "#thunderstorm",
              "fireplace": "#fireplace", "ocean": "#oceanwaves", "wind": "#windsounds", "fan": "#fansounds", "airplane": "#airplanesounds"}
THEME_HASH = {"campfire": "#campfire", "halloween": "#halloween", "winter": "#cozycabin", "study": "#studywithme"}
LAYER_WORDS = {"fire": "fire crackle", "wind": "wind", "hollow_wind": "a low hollow wind", "muffled_wind": "a muffled wind outside", "crickets": "crickets", "rain": "rain"}
SLEEP_SOUNDS = {"brown", "pink", "white", "rain", "thunderstorm", "ocean", "fan", "airplane", "wind", "fireplace", "binaural-delta"}
MAX_TAGS, MAX_TAG_CHARS = 15, 470
CHANNEL_LINE = ("This channel makes ambient videos in which every sound and every picture is generated by code. "
                "Nothing is recorded, sampled or taken from a sound or image library.")


def pick_lead(sound: str, kw: dict | None) -> str:
    """The title's lead phrase: the first candidate, unless the keyword research ranks another candidate higher."""
    cands = LEADS[sound]
    rows = {r["phrase"]: r["score"] for r in (kw or {}).get("kinds", {}).get(sound, [])}

    def score(c: str) -> float:
        low = c.lower()
        return max([v for k, v in rows.items() if k == low] + [0.0])
    return max(cands, key=lambda c: (score(c), -cands.index(c)))


def bed_text(cls, sound: str, bed_on: bool) -> str:
    """The theme's ambience under a sound, in words, from the layers that are actually mixed in."""
    sp = sounds.spec(sound)
    if not bed_on or sp.bed_level <= 0:
        return ""
    layers = [k for k in (cls.bed_solo or cls.bed) if k not in sp.drop and k in LAYER_WORDS]
    words = [LAYER_WORDS[k] for k in layers]
    return ", ".join(words[:-1]) + (" and " if len(words) > 1 else "") + words[-1] if words else ""


NEVER_IN_TAGS = re.compile(r"\b(no ads|ad[- ]free|no copyright)\b", re.I)         # a monetised channel cannot promise these, and the research ranks them first


def merge_tags(*groups: list, limit: int = MAX_TAGS, max_chars: int = MAX_TAG_CHARS) -> list:
    """Tags in priority order, no duplicates (case-insensitive), at most `limit` of them and `max_chars` characters in all. A phrase the channel cannot
    honestly promise (no ads, no copyright) is dropped even when the research ranks it first."""
    out, seen, used = [], set(), 0
    for g in groups:
        for t in g:
            t = t.strip()
            if not t or t.lower() in seen or len(out) >= limit or used + len(t) > max_chars or NEVER_IN_TAGS.search(t):
                continue
            seen.add(t.lower())
            out.append(t)
            used += len(t)
    return out


def sound_metadata(theme_name: str, seconds: float, slug: str, pomodoro: bool, seed: int, loop_min: float, sound: str, dark: float, no_bed: bool, kw: dict | None) -> dict:
    """Title, description and tags for a video whose sound is not the default chiptune: lead with the searched phrase, say plainly what it is in the
    first 150 characters, then a short factual block that answer engines can quote."""
    cls = themes.get(theme_name)
    cp = COPY[theme_name]
    sp = sounds.spec(sound)
    dur = hours_text(seconds)
    lead = pick_lead(sound, kw)
    screen = "Black Screen" if keywords.modifier_score(kw, "black screen") > keywords.modifier_score(kw, "dark screen") else "Dark Screen"
    title = f"{lead} with {TITLE_THEME[theme_name]}, {dur}" + (f", {screen}" if dark else "")
    if len(title) > 100:
        title = f"{lead}, {dur}" + (f", {screen}" if dark else "")
    bed = bed_text(cls, sound, not no_bed)
    scene = SCENE_SHORT[theme_name]
    first = f"{lead}, {dur}. {WHAT_SHORT[sound]}{' with quiet ' + bed if bed and not sp.musical else ''}, over {scene}."
    if len(first) > 150:                                             # the first 150 characters are what search and answer engines show: drop the extras, not the facts
        first = f"{lead}, {dur}. {WHAT_SHORT[sound]}, over {scene}."
    if len(first) > 150:
        first = f"{lead}, {dur}. {WHAT_SHORT[sound]}, over a pixel-art scene."
    dim = f"The screen dims to near black after {dark / 60:g} minutes and the sound carries on." if dark else ""
    lines = [first, ""]
    if dim:
        lines += [dim, ""]
    lines += ["About this video", f"What it is: {sp.what[0].upper() + sp.what[1:]}.",
              f"Length: {dur}" + (f", one {loop_min:g} minute loop joined so it repeats without a gap" if loop_min else "") + "."]
    if bed and not sp.musical:
        lines.append(f"Also in the mix: quiet {bed}.")
    lines.append(f"Picture: {cp['scene']}.")
    if sp.how:
        lines.append(f"How it was made: {sp.how}.")
    else:
        lines.append("How it was made: a program composes every track from a random seed (melody, chords, bass and drums).")
    if sp.note:
        lines.append(sp.note)
    if sp.lufs < -16:
        lines.append(f"Level: mastered at about {sp.lufs:g} LUFS, quieter than most music, so it sits comfortably at a low volume. Turn it up if you need to.")
    lines += ["", CHANNEL_LINE, ""]
    for ln in ("A steady background sound for reading, studying, working or going to sleep." if sound in SLEEP_SOUNDS else
               "Background sound for reading, studying, working or winding down.",):
        lines += [ln, ""]
    hashtags = [SOUND_HASH[sound], THEME_HASH[theme_name], "#sleepsounds" if sound in SLEEP_SOUNDS else "#ambience"]
    lines.append(" ".join(hashtags))
    ranked = keywords.top(kw, sound, 10) + keywords.top(kw, theme_name, 4)
    tags = merge_tags([lead.lower()], ranked, [sp.label.lower()], [t for t in cp["tags"] if pomodoro or "pomodoro" not in t], ["pixel art", "ambient sounds"])
    chapters = []
    if pomodoro:
        th = cls(seed, seconds, options={"pomodoro": (25, 5)})
        chapters = [{"time": lf_clock(t), "seconds": int(t), "title": name} for t, name in th.chapters()]
        lines += ["", "Chapters:"] + [f"{c['time']} {c['title']}" for c in chapters]
    return {
        "slug": slug, "title": title, "description": "\n".join(l for i, l in enumerate(lines) if l != "" or (i and lines[i - 1] != "")).strip(),
        "optional_footer": "More free tools and apps: https://purplelink.llc/?utm_source=youtube&utm_medium=ambient&utm_campaign=" + slug,
        "tags": tags, "chapters": chapters, "category": "Music", "made_for_kids": False, "altered_or_synthetic_content": DISCLOSURE, "language": "en",
        "visibility_on_upload": "private, until Ben has watched it and chosen a publish time", "video_file": slug + ".mp4", "thumbnail_file": slug + "-thumb.jpg",
        "render": {"theme": theme_name, "seed": seed, "seconds": seconds, "sound": sound, "dark_after_seconds": dark or None, "loudness_target_lufs": sp.lufs,
                   "loop_minutes": loop_min or None, "keywords_date": (kw or {}).get("date")},
    }


# ------------------------------------------------------------------------------------------------------------------------ holiday and 4K (the TV app)
HOLIDAYS = {"christmas": "Christmas", "newyear": "New Year"}
# keyword-research kinds (keywords.HOLIDAY_SEEDS) that rank the title leads, per holiday
HOLIDAY_KINDS = {"christmas": {"fireplace": "christmas-fireplace", "ambience": "christmas-ambience", "cabin": "snowy-cabin"},
                 "newyear": {"fireplace": "newyear", "ambience": "newyear", "cabin": "newyear"}}
HOLIDAY_SCENE = {
    ("winter", "fireplace"): "a pixel-art fireplace close up: a crackling fire on logs, stockings hung from the mantel and a snowy window beside it",
    ("winter", ""): "a pixel-art snowed-in cabin at night: snow falling past the window, a stone fireplace with stockings, a lit Christmas tree, a cat asleep on the rug and a mug steaming on the sill",
    ("study", ""): "a pixel-art study room decorated for Christmas: a lit tree with presents, string lights, snow falling past the window and someone working at a desk",
}
HOLIDAY_SCENE_SHORT = {("winter", "fireplace"): "a pixel-art Christmas fireplace", ("winter", ""): "a pixel-art Christmas cabin",
                       ("study", ""): "a pixel-art Christmas study room"}
SCENE_NAME = {"winter": "Snowy Cabin", "study": "Study Room", "campfire": "Crackling Campfire", "halloween": "Halloween Porch"}


def holiday_lead(cands: list, kind: str, kw: dict | None) -> str:
    """The highest-ranked of the candidate lead phrases in a keyword kind (a candidate scores the best suggestion that is it or starts with it); the first
    candidate if the research has not run or ranks none of them."""
    rows = [(r["phrase"], r["score"]) for r in (kw or {}).get("kinds", {}).get(kind, [])]

    def score(c: str) -> float:
        low = c.lower()
        return max([v for k, v in rows if k == low or k.startswith(low + " ")] + [0.0])
    return max(cands, key=lambda c: (score(c), -cands.index(c)))


UNTRUE_FOR_US = re.compile(r"\b(carols?|classics?|songs?|jazz|piano|live|cortisol|adhd|anxiety|healing|meditation)\b", re.I)    # searched, but not what we make or not claimable


def honest_phrase(phrase: str, hours: float, uhd: bool, musical: bool, sound: str = "") -> bool:
    """Can this searched phrase be used as a tag for this video? Not if it names another length (christmas fireplace 2 hours on a 10 hour video), 4K for a 1080p
    file, music for a video with none, carols or songs (our music is original), or a health word."""
    low = phrase.lower()
    if UNTRUE_FOR_US.search(low) or NEVER_IN_TAGS.search(low):
        return False
    for n, unit in re.findall(r"\b(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b", low):
        if abs(float(n) * (1.0 if unit.startswith("h") else 1 / 60) - hours) > 0.01:
            return False
    if "4k" in low and not uhd:
        return False
    if re.search(r"\b(rain|thunder|thunderstorm|storm)\b", low) and sound not in ("rain", "thunderstorm"):
        return False
    if not musical and re.search(r"music|chiptune|lofi|8 bit", low) and "no music" not in low:
        return False
    return not (musical and "no music" in low)


def tv_ranked(kw: dict | None, kind: str) -> bool:
    """True when people's searches in this kind include 'for tv' (fireplace for tv, fireplace for tv screen): then the fireplace titles say it."""
    return any("for tv" in r["phrase"] and r["score"] >= 3 for r in (kw or {}).get("kinds", {}).get(kind, []))


def holiday_title(theme_name: str, season: str, sound: str, musical: bool, uhd: bool, dark: float, dur: str, kw: dict | None) -> tuple:
    """(title, lead). The searched phrase first, then the honest attributes in the order TV viewers scan them: 4K, what it is, length, no music, screen.
    The first 50 characters carry the lead and 4K, because a TV list cuts titles short. `4K` is left out of a dark video's title: the file is 2160p, but
    its picture is only there for the first minutes, so the title would promise more than the screen shows."""
    hol = HOLIDAYS.get(season, "")
    kinds = HOLIDAY_KINDS.get(season, {})
    four = " 4K" if uhd and not dark else ""
    screen = ""
    if dark:
        screen = ", " + ("Black Screen" if keywords.modifier_score(kw, "black screen") > keywords.modifier_score(kw, "dark screen") else "Dark Screen")
    no_music = "" if musical else ", No Music"
    scene_name = SCENE_NAME.get(theme_name, TITLE_THEME.get(theme_name, "Cabin"))
    if sound == "fireplace":
        if season == "christmas":
            lead = holiday_lead(["Christmas Fireplace", "Yule Log"], kinds["fireplace"], kw)
            flavor = "Crackling Fireplace" if lead == "Yule Log" else "Crackling Yule Log"
        else:
            lead, flavor = (f"{hol} Fireplace" if hol else "Fireplace Sounds"), "Crackling Fire"
        tv = " for TV" if tv_ranked(kw, kinds.get("fireplace", "")) else ""
        title = f"{lead}{four}{tv}, {flavor}, {dur}{no_music}{screen}"
    elif musical:
        music_name = "Lofi" if sound == "lofi" else "Chiptune"
        if theme_name == "study" and hol:
            lead = f"{hol} {music_name} Study Music"
            title = f"{lead}, Cozy Study Room{four}, {dur}"
        elif hol:
            lead = holiday_lead([f"{hol} Cabin Ambience", f"Cozy {hol} Cabin"], kinds.get("ambience", ""), kw)
            title = f"{lead}{four} with {hol} {music_name} Music, {dur}"
        else:
            lead = f"Cozy {scene_name}"
            title = f"{lead}{four} with {music_name} Music, {dur}"
    else:
        lead = pick_lead(sound, kw)
        title = f"{lead} with {scene_name}{four}, {dur}{screen}"
    if len(title) > 100:
        title = f"{lead}{four}, {dur}{no_music}{screen}"
    return title, lead


def holiday_metadata(theme_name: str, seconds: float, slug: str, music: bool, pomodoro: bool, seed: int, loop_min: float, sound: str, dark: float,
                     no_bed: bool, kw: dict | None, uhd: bool, season: str, view: str) -> dict:
    """Title, description and tags for a 4K and/or holiday video, written for the YouTube TV app: the ranked holiday phrase leads the title, the first
    sentence says plainly what the video is (what search and answer engines quote), then a block of short true facts. Only what is in the file is claimed:
    4K only for a 2160p file, No Music only when there is none, the length only for the real length. Any music is original: no carol or existing tune."""
    cls = themes.get(theme_name)
    cp = COPY[theme_name]
    sp = sounds.spec(sound)
    musical = bool(sp.musical and music)
    dur = hours_text(seconds)
    title, lead = holiday_title(theme_name, season, sound, musical, uhd, dark, dur, kw)
    hol = HOLIDAYS.get(season, "")
    key = (theme_name, view if (theme_name, view) in HOLIDAY_SCENE else "")
    scene = (HOLIDAY_SCENE.get(key) if season == "christmas" else None) or cp["scene"]
    scene_short = (HOLIDAY_SCENE_SHORT.get(key) if season == "christmas" else None) or SCENE_SHORT[theme_name]
    scene_cap = scene_short[0].upper() + scene_short[1:]
    music_name = "lofi" if sound == "lofi" else "chiptune"
    bed = "" if musical else bed_text(cls, sound, not no_bed)
    four_in_title = uhd and not dark
    lead_name = lead + (" 4K" if four_in_title and "4k" not in lead.lower() else "")
    if musical:
        says = f"original {music_name} music, not carols or existing songs" if hol else f"original {music_name} music"
    elif sound == "fireplace":
        says = "a crackling fire and no music"
    else:
        says = WHAT_SHORT[sound][0].lower() + WHAT_SHORT[sound][1:] + " and no music"
    first = f"{lead_name}, {dur}. {scene_cap} with {says}."
    if len(first) > 150:
        first = f"{lead_name}, {dur}. {scene_cap}."
    what = f"original {music_name} music" if musical else sp.what
    if sound == "fireplace" and no_bed:
        what = "a crackling fire on its own, with no wind or room sound under it"
    lines = [first, ""]
    if dark:
        lines += [f"The screen dims to near black after {dark / 60:g} minutes and the sound carries on.", ""]
    lines += ["About this video", f"What it is: {what[0].upper() + what[1:]}.",
              f"Length: {dur}" + (f", one {loop_min:g} minute loop joined so it repeats without a gap" if loop_min else "") + ".",
              ("Resolution: 3840x2160 (4K). The picture is pixel art drawn at 1920x1080 and enlarged exactly 2x, so every pixel keeps a hard edge."
               if uhd else "Resolution: 1920x1080."),
              f"Picture: {scene}."]
    if bed:
        lines.append(f"Also in the mix, quietly: {bed}.")
    if musical:
        lines.append("Music: composed by a program from a random seed (melody, chords, bass and drums). No carol, existing song or recording is used.")
        lines.append(f"Sound: {sp.what if sound == 'lofi' else cp['sound_music']}" + (", with the room's own ambience quietly under it." if sound == "lofi" and not no_bed else "."))
    elif sp.how:
        lines.append(f"How it was made: {sp.how}.")
    if not musical:
        lines.append("There is no music in this video.")
    if sp.lufs < -16:
        lines.append(f"Level: mastered at about {sp.lufs:g} LUFS, quieter than most music, so it sits comfortably at a low volume. Turn it up if you need to.")
    lines += ["", CHANNEL_LINE, ""]
    third = "#4k" if four_in_title else ("#sleepsounds" if sound in SLEEP_SOUNDS else "#ambience")
    scene_tag = "#yulelog" if "yule" in title.lower() else THEME_HASH[theme_name]
    first_tag = f"#{season}" if season else SOUND_HASH.get(sound, "#ambience")
    tags3 = list(dict.fromkeys([first_tag, scene_tag, third, "#ambience"]))[:3]
    lines.append(" ".join(tags3))
    kinds = HOLIDAY_KINDS.get(season, {})
    ok = lambda ph: honest_phrase(ph, seconds / 3600, uhd, musical, sound) and (theme_name == "winter" or not re.search(r"cabin|snow", ph.lower()))
    ranked = []
    if sound == "fireplace":
        ranked += [x for x in keywords.top(kw, kinds.get("fireplace", ""), 30) if ok(x)][:6]
    elif season:
        ranked += [x for x in keywords.top(kw, kinds.get("ambience", ""), 20) if ok(x)][:4] + [x for x in keywords.top(kw, kinds.get("cabin", ""), 20) if ok(x)][:3]
    if sound not in ("chiptune", "lofi"):
        ranked += [x for x in keywords.top(kw, sound, 20) if ok(x)][:4]
    base = [lead.lower()] + ([f"{lead.lower()} 4k"] if four_in_title and "4k" not in lead.lower() else [])
    fixed = []
    if sound == "fireplace":
        fixed += ["christmas fireplace", "yule log", "fireplace for tv", "fireplace sounds", "crackling fire"] if season == "christmas" else ["fireplace for tv", "fireplace sounds"]
    if season == "christmas":
        fixed += ["christmas ambience", "cozy christmas"] + (["christmas study music", "study with me"] if theme_name == "study" else [])
    if theme_name == "winter":
        fixed += ["snowy cabin", "snowy cabin ambience"]
    if dark:
        fixed.append(f"{lead.lower()} black screen")
    if uhd:
        fixed += ["4k", "4k ambience"]
    if not musical:
        fixed.append("no music")
    tags = merge_tags(base, ranked, fixed, [t for t in cp["tags"] if "pomodoro" not in t], ["pixel art", "ambient sounds"])
    return {
        "slug": slug, "title": title, "description": "\n".join(l for i, l in enumerate(lines) if l != "" or (i and lines[i - 1] != "")).strip(),
        "optional_footer": "More free tools and apps: https://purplelink.llc/?utm_source=youtube&utm_medium=ambient&utm_campaign=" + slug,
        "tags": tags, "chapters": [], "category": "Music", "made_for_kids": False, "altered_or_synthetic_content": DISCLOSURE, "language": "en",
        "visibility_on_upload": "private, until Ben has watched it and chosen a publish time", "video_file": slug + ".mp4", "thumbnail_file": slug + "-thumb.jpg",
        "render": {"theme": theme_name, "seed": seed, "seconds": seconds, "sound": sound, "season": season or None, "view": view or None, "uhd": uhd,
                   "dark_after_seconds": dark or None, "loudness_target_lufs": sp.lufs, "loop_minutes": loop_min or None, "keywords_date": (kw or {}).get("date")},
    }


def lf_clock(sec: float) -> str:
    return clock(sec)


def build_metadata(theme_name: str, seconds: float, slug: str, music: bool, pomodoro: bool, seed: int, tracks: list | None = None,
                   loop_min: float = 0.0, sound: str = "chiptune", dark: float = 0.0, no_bed: bool = False, kw: dict | None = None,
                   uhd: bool = False, season: str = "", view: str = "") -> dict:
    if uhd or season in HOLIDAYS:                                    # 4K and holiday videos are titled for the TV app (see holiday_metadata)
        return holiday_metadata(theme_name, seconds, slug, music, pomodoro, seed, loop_min, sound, dark, no_bed, kw, uhd, season, view)
    if sound != "chiptune":
        return sound_metadata(theme_name, seconds, slug, pomodoro, seed, loop_min, sound, dark, no_bed, kw)
    cls = themes.get(theme_name)
    cp = COPY[theme_name]
    dur = hours_text(seconds)
    key = "title_music" if music else "title_solo"
    if pomodoro and key + "_pomo" in cp:
        key += "_pomo"
    title = cp[key].format(dur=dur)
    snd = cp["sound_music"] if music else cp["sound_solo"]
    lines = [f"{dur} of {cp['scene']}.", "", f"Sound: {snd}.", ""]
    if music:
        lines += ["The music is original. A program composes every track from a random seed (melody, chords, bass and drums), and the same program draws the picture "
                  "and synthesises the fire, wind and rain. Nothing in this video is sampled, recorded, or taken from a music, sound or image library.", ""]
    else:
        lines += ["There is no music. A program synthesises every sound (fire, wind, crickets) from noise and sine waves and draws the picture. "
                  "Nothing in this video is sampled, recorded, or taken from a sound or image library.", ""]
    if loop_min:
        lines += [f"The picture and sound are one {loop_min:g} minute loop, joined so it repeats without a gap, and played for the full {dur.lower()}.", ""]
    lines += [f"Good for {cp['use']}. It is a fixed-length video that ends with a fade.", ""]
    chapters = []
    if pomodoro:
        theme = cls(seed, seconds, options={"pomodoro": (25, 5)})
        chapters = [{"time": clock(t), "seconds": int(t), "title": name} for t, name in theme.chapters()]
        lines += ["The timer follows the classic Pomodoro pattern: 25 minutes of focus, then a 5 minute break, with a soft chime at each change. "
                  "The person at the desk takes their break when the timer says so.", "", "Chapters:"]
        lines += [f"{c['time']} {c['title']}" for c in chapters] + [""]
    lines += [cp["hashtags"]]
    tags = merge_tags(keywords.top(kw, "chiptune", 4) + keywords.top(kw, theme_name, 4), cp["tags"], cp["tags_music"] if music else ["no music ambience", "ambient sounds"])
    return {
        "slug": slug,
        "title": title,
        "description": "\n".join(lines).strip(),
        "optional_footer": "More free tools and apps: https://purplelink.llc/?utm_source=youtube&utm_medium=ambient&utm_campaign=" + slug,
        "tags": tags,
        "chapters": chapters,
        "category": cp["category"] if music else cp["category_solo"],
        "made_for_kids": False,
        "altered_or_synthetic_content": DISCLOSURE,
        "language": "en",
        "visibility_on_upload": "private, until Ben has watched it and chosen a publish time",
        "video_file": slug + ".mp4",
        "thumbnail_file": slug + "-thumb.jpg",
        "render": {"theme": theme_name, "seed": seed, "seconds": seconds, "music": music, "pomodoro": "25/5" if pomodoro else None,
                   "tracks": len(tracks) if tracks else 0},
    }


# ------------------------------------------------------------------------------------------------------------------------ verification
def probe(video: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    return {"duration": float(j["format"]["duration"]), "size_bytes": int(j["format"]["size"]), "width": v["width"], "height": v["height"],
            "video_codec": v["codec_name"], "profile": v.get("profile"), "fps": v["r_frame_rate"], "audio_codec": a["codec_name"],
            "audio_rate": a["sample_rate"], "audio_kbps": round(int(a.get("bit_rate", 0)) / 1000)}


def loudness_and_silence(video: Path, floor_db: float = -55.0, min_len: float = 3.0) -> dict:
    """One pass over the audio: integrated loudness, loudness range, true peak, and every stretch quieter than `floor_db` for `min_len` seconds or more."""
    af = f"ebur128=peak=true,silencedetect=n={floor_db}dB:d={min_len}"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af", af, "-f", "null", "-"], capture_output=True, text=True)
    text = r.stderr
    summary = text[text.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", text)]
    ends = re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", text)
    spans = [{"start": s, "duration": float(d)} for s, (_, d) in zip(starts, ends)]
    if len(starts) > len(ends):                                   # still silent at the end of the file
        spans.append({"start": starts[-1], "duration": None})
    return {"integrated_lufs": float(i.group(1)) if i else None, "lra": float(lra.group(1)) if lra else None,
            "true_peak_dbtp": float(tp.group(1)) if tp else None, "silences": spans}


def extract_frames(video: Path, out_dir: Path, slug: str, duration: float, fractions=(0.10, 0.40, 0.70, 0.95)) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in fractions:
        p = out_dir / f"{slug}-frame-{int(round(f * 100)):02d}.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{duration * f:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(p)], check=True)
        paths.append(str(p))
    return paths


SIZES_OK = ((1920, 1080), (3840, 2160))          # 1080p, or 2160p (--uhd): YouTube labels a file 4K from its height


def size_checks(info: dict) -> dict:
    wh = (info["width"], info["height"])
    return {"1080p_or_2160p": wh in SIZES_OK, **({"2160p": True} if wh == (3840, 2160) else {"1080p": wh == (1920, 1080)})}


def verify(video: Path, frames_dir: Path | None, slug: str, fade_allowance: float = 12.0, quick: bool = False, sound: str = "chiptune") -> dict:
    target = sounds.target_lufs(sound)
    info = probe(video)
    if quick:
        report = {"file": video.name, **info, "quick": True,
                  "checks": {**size_checks(info), "h264": info["video_codec"] == "h264", "aac": info["audio_codec"] == "aac"}}
        if frames_dir is not None:
            report["frames"] = extract_frames(video, frames_dir, slug, info["duration"])
        return report
    loud = loudness_and_silence(video)
    bad = [s for s in loud["silences"] if s["duration"] is None or s["start"] < info["duration"] - fade_allowance]
    report = {"file": video.name, "sound": sound, "target_lufs": target, **info, **{k: loud[k] for k in ("integrated_lufs", "lra", "true_peak_dbtp")},
              "silences_over_3s_outside_the_final_fade": bad,
              "checks": {**size_checks(info), "h264": info["video_codec"] == "h264", "aac": info["audio_codec"] == "aac",
                         f"loudness_within_0.7_of_{target:g}": loud["integrated_lufs"] is not None and abs(loud["integrated_lufs"] - target) <= 0.7,
                         "true_peak_at_most_-1": loud["true_peak_dbtp"] is not None and loud["true_peak_dbtp"] <= -1.0, "no_unexpected_silence": not bad}}
    if frames_dir is not None:
        report["frames"] = extract_frames(video, frames_dir, slug, info["duration"])
    return report


# ------------------------------------------------------------------------------------------------------------------------ command line
def _common(ap):
    ap.add_argument("--theme", required=True)
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--pomodoro", default="")
    ap.add_argument("--season", default="")
    ap.add_argument("--loop-min", type=float, default=0.0)
    ap.add_argument("--sound", default="chiptune", choices=sounds.NAMES)
    ap.add_argument("--dark", type=float, default=0.0)
    ap.add_argument("--no-bed", action="store_true")
    ap.add_argument("--uhd", action="store_true", help="the video is 3840x2160 (the title then says 4K)")
    ap.add_argument("--view", default="", choices=["", "fireplace"])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("thumb")
    _common(t)
    t.add_argument("--out", required=True)
    m = sub.add_parser("meta")
    _common(m)
    m.add_argument("--slug", required=True)
    m.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--video", required=True)
    v.add_argument("--frames-dir")
    v.add_argument("--out")
    v.add_argument("--sound", default="chiptune", choices=sounds.NAMES, help="the sound the video was rendered with: sets the loudness target it is checked against")
    v.add_argument("--quick", action="store_true", help="format, length and frames only; skip the loudness and silence pass (for a long file made of a verified loop)")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        video = Path(a.video)
        rep = verify(video, Path(a.frames_dir) if a.frames_dir else None, video.stem, quick=a.quick, sound=a.sound)
        text = json.dumps(rep, indent=2)
        if a.out:
            Path(a.out).write_text(text)
        print(text)
        return
    seed = a.seed if a.seed is not None else zlib.crc32(a.theme.encode()) % 900 + 1
    seconds = a.seconds if a.seconds else a.hours * 3600.0
    options = {"pomodoro": (25, 5)} if a.pomodoro else {}
    if a.season:
        options["season"] = a.season
    if a.view:
        options["view"] = a.view
    if a.cmd == "thumb":
        p = make_thumbnail(a.theme, seconds, seed, Path(a.out), options, music=not a.no_music, sound=a.sound, uhd=a.uhd, dark=a.dark)
        print(p, p.stat().st_size)
    else:
        loop_min = a.loop_min if 0 < a.loop_min * 60 < seconds else 0.0
        music_s = loop_min * 60 + lf.LOOP_XF if loop_min else seconds   # a loop render composes only the loop's tracks
        cls = themes.get(a.theme)
        musical = sounds.spec(a.sound).musical and not a.no_music
        tracks = lf.plan_tracks(cls, music_s, seed, lf.music_cfg(cls, a.sound)) if musical else []
        meta = build_metadata(a.theme, seconds, a.slug, musical, bool(a.pomodoro), seed, tracks, loop_min, sound=a.sound, dark=a.dark, no_bed=a.no_bed,
                              kw=keywords.load(), uhd=a.uhd, season=a.season, view=a.view)
        Path(a.out).write_text(json.dumps(meta, indent=2) + "\n")
        print(meta["title"])


if __name__ == "__main__":
    main()
