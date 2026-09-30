#!/usr/bin/env python3
"""Per-scene narration with edge-tts (free Microsoft neural voices) plus word timings.

    python3 narrate.py storyboards/<id>.json [--force]

Writes .cache/<id>/audio/scene-N.mp3 and .cache/<id>/timing.json:
  {"voice", "scenes": [{"index", "audio", "duration", "words": [{"word","start","end","display"}]}]}
Scenes without narration get duration 0 and no audio. Results are cached by a hash of
(voice, rate, text); unchanged scenes are not re-synthesised.

Voice choice (documented, not auditioned): en-US-AndrewNeural is tagged Warm, Confident,
Authentic, Honest, conversation category. en-US-AriaNeural is tagged News/Novel, Positive,
Confident, which tends toward an announcer read. Calm and plain is the brand, so Andrew is
the default. Override per storyboard with "voice" and "rate".

Word boundaries follow the approach in TikTokPipeline/MuscleOnGLPPipeline/narrate.py:
WordBoundary events arrive with the audio, ticks of 100 ns. Punctuation is restored from the
source text so captions can break at phrase ends.
"""
from __future__ import annotations
import asyncio, hashlib, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_VOICE = "en-US-AndrewNeural"
DEFAULT_RATE = "+0%"


async def synth(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append({"word": chunk["text"], "start": round(s, 3),
                              "end": round(s + chunk["duration"] / 1e7, 3)})
    if not words or mp3.stat().st_size == 0:
        raise RuntimeError("edge-tts returned no audio or word events")
    return words


def restore_punctuation(words: list[dict], text: str) -> list[dict]:
    tokens = text.split()
    if len(tokens) == len(words):
        for w, t in zip(words, tokens):
            w["display"] = t
    else:
        for w in words:
            w["display"] = w["word"]
    return words


def probe_duration(mp3: Path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nk=1:nw=1", str(mp3)], text=True)
    return round(float(out.strip()), 3)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        sys.exit(__doc__)
    sb_path = Path(args[0]).resolve()
    sb = json.loads(sb_path.read_text())
    voice = sb.get("voice") or DEFAULT_VOICE
    rate = sb.get("rate") or DEFAULT_RATE
    out_dir = HERE / ".cache" / sb["id"]
    (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    timing_path = out_dir / "timing.json"
    old = {}
    if timing_path.exists():
        old = {s["index"]: s for s in json.loads(timing_path.read_text()).get("scenes", [])}
    scenes = []
    for i, sc in enumerate(sb["scenes"]):
        text = (sc.get("narration") or "").strip()
        if not text:
            scenes.append({"index": i, "audio": None, "duration": 0, "words": [], "hash": ""})
            continue
        h = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        mp3 = out_dir / "audio" / f"scene-{i}.mp3"
        prev = old.get(i)
        if not force and prev and prev.get("hash") == h and mp3.exists():
            scenes.append(prev)
            print(f"scene {i}: cached ({prev['duration']:.2f}s)")
            continue
        words = restore_punctuation(asyncio.run(synth(text, voice, rate, mp3)), text)
        dur = probe_duration(mp3)
        scenes.append({"index": i, "audio": f"audio/{sb['id']}/scene-{i}.mp3", "duration": dur,
                       "words": words, "hash": h})
        print(f"scene {i}: {len(words)} words, {dur:.2f}s")
    timing_path.write_text(json.dumps({"voice": voice, "rate": rate, "scenes": scenes}, indent=1))
    print(f"wrote {timing_path}")


if __name__ == "__main__":
    main()
