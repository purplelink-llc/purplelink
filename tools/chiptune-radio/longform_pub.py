#!/usr/bin/env python3.12
"""Everything around a rendered long-form video that is not the video: its thumbnail, its upload metadata, and a check of the finished file.

    python3.12 longform_pub.py thumb    --theme campfire --hours 2 --out campfire-2h-thumb.jpg
    python3.12 longform_pub.py meta     --theme campfire --hours 2 --slug campfire-2h --out campfire-2h.json
    python3.12 longform_pub.py verify   --video campfire-2h.mp4 --frames-dir DIR      # ffprobe, loudness, silence, four frames

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

import longform as lf
import pixfont
import px
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


def make_thumbnail(theme_name: str, seconds: float, seed: int, out: Path, options: dict | None = None, music: bool = True) -> Path:
    """A 1280x720 JPEG: a clean frame of the scene, enlarged exactly 4x, with a darkened band behind big pixel-font title text. The bottom-right
    corner is left empty because YouTube puts the duration stamp there."""
    cls = themes.get(theme_name)
    tracks = lf.plan_tracks(cls, seconds, seed)
    theme = cls(seed, seconds, bpm_at=lf.bpm_lookup(tracks), options=options or {})
    t = theme.progress(theme.thumb_at * seconds) * seconds
    art = px.scale_up(theme.frame(t), THUMB_SCALE).convert("RGBA")
    lay = THUMB_LAYOUT.get(theme_name, {"x": 0.5, "y": 0.05, "align": "center"})
    lines = list(cls.thumb_lines)
    if not music:
        lines = [lines[0], lines[1]]
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


def build_metadata(theme_name: str, seconds: float, slug: str, music: bool, pomodoro: bool, seed: int, tracks: list | None = None,
                   loop_min: float = 0.0) -> dict:
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
    tags = cp["tags"] + (cp["tags_music"] if music else ["no music ambience", "ambient sounds"])
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


def verify(video: Path, frames_dir: Path | None, slug: str, fade_allowance: float = 12.0, quick: bool = False) -> dict:
    info = probe(video)
    if quick:
        report = {"file": video.name, **info, "quick": True,
                  "checks": {"1080p": (info["width"], info["height"]) == (1920, 1080), "h264": info["video_codec"] == "h264", "aac": info["audio_codec"] == "aac"}}
        if frames_dir is not None:
            report["frames"] = extract_frames(video, frames_dir, slug, info["duration"])
        return report
    loud = loudness_and_silence(video)
    bad = [s for s in loud["silences"] if s["duration"] is None or s["start"] < info["duration"] - fade_allowance]
    report = {"file": video.name, **info, **{k: loud[k] for k in ("integrated_lufs", "lra", "true_peak_dbtp")},
              "silences_over_3s_outside_the_final_fade": bad,
              "checks": {"1080p": (info["width"], info["height"]) == (1920, 1080), "h264": info["video_codec"] == "h264", "aac": info["audio_codec"] == "aac",
                         "loudness_within_0.7_of_-14": loud["integrated_lufs"] is not None and abs(loud["integrated_lufs"] + 14.0) <= 0.7,
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
    v.add_argument("--quick", action="store_true", help="format, length and frames only; skip the loudness and silence pass (for a long file made of a verified loop)")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        video = Path(a.video)
        rep = verify(video, Path(a.frames_dir) if a.frames_dir else None, video.stem, quick=a.quick)
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
    if a.cmd == "thumb":
        p = make_thumbnail(a.theme, seconds, seed, Path(a.out), options, music=not a.no_music)
        print(p, p.stat().st_size)
    else:
        loop_min = a.loop_min if 0 < a.loop_min * 60 < seconds else 0.0
        music_s = loop_min * 60 + lf.LOOP_XF if loop_min else seconds   # a loop render composes only the loop's tracks
        tracks = lf.plan_tracks(themes.get(a.theme), music_s, seed) if not a.no_music else []
        meta = build_metadata(a.theme, seconds, a.slug, not a.no_music, bool(a.pomodoro), seed, tracks, loop_min)
        Path(a.out).write_text(json.dumps(meta, indent=2) + "\n")
        print(meta["title"])


if __name__ == "__main__":
    main()
