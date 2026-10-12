#!/usr/bin/env python3
"""Fallback narration with the macOS `say` voices, for when edge-tts is unavailable (Microsoft's service answers 403).

    python3 narrate_say.py storyboards/<id>.json [--voice "Flo (English (UK))"] [--rate 180]

Writes the same .cache/<id>/audio/scene-N.mp3 and .cache/<id>/timing.json that narrate.py writes. `say` gives no word
boundaries, so each word is placed by its share of the spoken time (pauses found with ffmpeg silencedetect are not counted);
cues land within a few tenths of a second. Delete .cache/<id> and run narrate.py when edge-tts works again.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def duration(f):
    return round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(f)], text=True)), 3)


def silences(f, dur):
    out = subprocess.run(["ffmpeg", "-i", str(f), "-af", "silencedetect=noise=-38dB:d=0.07", "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", out)]
    sil = []
    for i, s in enumerate(starts):
        sil.append((max(0.0, s), ends[i] if i < len(ends) else dur))
    return sil


def speech_intervals(sil, dur):
    iv, cur = [], 0.0
    for s, e in sorted(sil):
        if s > cur + 0.02:
            iv.append((cur, s))
        cur = max(cur, e)
    if dur > cur + 0.02:
        iv.append((cur, dur))
    return iv


def place(words_text, iv):
    total = sum(e - s for s, e in iv)
    weights = [len(re.sub(r"[^A-Za-z0-9]", "", w)) + 1.5 for w in words_text]
    wsum = sum(weights)

    def real(x):  # position in concatenated speech time -> real time
        for s, e in iv:
            if x <= e - s + 1e-9:
                return s + x
            x -= e - s
        return iv[-1][1]

    out, acc = [], 0.0
    for w, wt in zip(words_text, weights):
        a, b = acc / wsum * total, (acc + wt) / wsum * total
        out.append({"word": re.sub(r"[^\w'-]", "", w) or w, "start": round(real(a), 3), "end": round(real(b), 3), "display": w})
        acc += wt
    return out


def main():
    sb = json.loads(Path(sys.argv[1]).read_text())
    voice, rate = opt("--voice", "Flo (English (UK))"), opt("--rate", "180")
    out_dir = HERE / ".cache" / sb["id"]
    (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    scenes = []
    for i, sc in enumerate(sb["scenes"]):
        text = (sc.get("narration") or "").strip()
        if not text:
            scenes.append({"index": i, "audio": None, "duration": 0, "words": [], "hash": ""})
            continue
        aiff, mp3 = out_dir / "audio" / f"scene-{i}.aiff", out_dir / "audio" / f"scene-{i}.mp3"
        subprocess.check_call(["say", "-v", voice, "-r", rate, "-o", str(aiff), text])
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "2", str(mp3)])
        aiff.unlink()
        dur = duration(mp3)
        words = place(text.split(), speech_intervals(silences(mp3, dur), dur))
        h = hashlib.sha1(f"say|{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        scenes.append({"index": i, "audio": f"audio/{sb['id']}/scene-{i}.mp3", "duration": dur, "words": words, "hash": h})
        print(f"scene {i}: {len(words)} words, {dur:.2f}s")
    (out_dir / "timing.json").write_text(json.dumps({"voice": f"say:{voice}", "rate": rate, "scenes": scenes}, indent=1))
    print("wrote", out_dir / "timing.json")


if __name__ == "__main__":
    main()
