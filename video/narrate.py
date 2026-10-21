#!/usr/bin/env python3
"""Per-scene narration with ElevenLabs (when a key exists), local Kokoro, or edge-tts (the last fallback), plus word timings.

Kokoro (2026-10-21, Ben's blind tests: Kokoro bf_emma over edge Sonia for the how-tos, am_michael / af_heart over the
US edge voices) runs on the Mac mini in its own venv through TikTokPipeline's shared_media/kokoro_local.py, once per
storyboard for all its scenes. Storyboards keep naming edge voices; KOKORO_VOICES maps them by accent and gender, and the
storyboard rate becomes Kokoro's speed ("-4%" -> 0.96). TTS_ENGINE=edge turns Kokoro off.

ElevenLabs is used when a key is in ~/.config/purplelink/elevenlabs-api-key (or ELEVENLABS_API_KEY) and
ELEVENLABS_DISABLE is not set. Any ElevenLabs failure (no key, quota, network) falls back to edge-tts for that
scene; timing.json records the engine per scene. Storyboards keep naming edge voices ("en-GB-SoniaNeural"):
ELEVEN_VOICES maps each to an ElevenLabs voice, overridable in ~/.config/purplelink/elevenlabs-voices.json.

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
import asyncio, base64, hashlib, json, os, ssl, subprocess, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_VOICE = "en-US-AndrewNeural"
DEFAULT_RATE = "+0%"

# Microsoft moved Edge's Read Aloud service on 2026-10-10: the old host (speech.platform.bing.com)
# answers every handshake with 403, and edge-tts 7.2.8 still uses it (rany2/edge-tts#490). The new
# host takes the same client token under the query name Ocp-Apim-Subscription-Key. communicate.py
# binds WSS_URL at import, so the override is set on edge_tts.communicate. EDGE_TTS_HOST=legacy
# leaves the library's own URL untouched. Same switch as TikTokPipeline/shared_media/narrate.py.
EDGE_TTS_HOST = os.environ.get("EDGE_TTS_HOST", "api.msedgeservices.com")


def apply_edge_endpoint(host: str = EDGE_TTS_HOST) -> str:
    import edge_tts.communicate as com
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN
    if host and host != "legacy":
        com.WSS_URL = (f"wss://{host}/tts/cognitiveservices/websocket/v1"
                       f"?Ocp-Apim-Subscription-Key={TRUSTED_CLIENT_TOKEN}")
    return com.WSS_URL


async def synth(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts
    apply_edge_endpoint()
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


# ---- ElevenLabs ---------------------------------------------------------------------------------------------------
ELEVEN_KEY_FILE = Path.home() / ".config" / "purplelink" / "elevenlabs-api-key"
ELEVEN_VOICE_FILE = Path.home() / ".config" / "purplelink" / "elevenlabs-voices.json"
ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
# ElevenLabs premade voices closest to the edge voices the storyboards name (calm, plain reads)
ELEVEN_VOICES = {
    "en-GB-SoniaNeural": "Xb7hH8MSUJpSbSDYk0k2",   # Alice, British female
    "en-US-AndrewNeural": "nPczCjzI2devNBz1zQrb",  # Brian, American male
    "default": "nPczCjzI2devNBz1zQrb",
}


def eleven_key() -> str | None:
    if os.environ.get("ELEVENLABS_DISABLE"):
        return None
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k and ELEVEN_KEY_FILE.exists():
        k = ELEVEN_KEY_FILE.read_text().strip()
    return k or None


def eleven_voice(edge_voice: str) -> str:
    table = dict(ELEVEN_VOICES)
    if ELEVEN_VOICE_FILE.exists():
        table.update(json.loads(ELEVEN_VOICE_FILE.read_text()))
    return table.get(edge_voice) or table["default"]


def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def synth_eleven(text: str, voice: str, rate: str, mp3: Path, key: str) -> list[dict]:
    """POST text-to-speech/<voice>/with-timestamps; turn the per-character alignment into word timings."""
    pct = float(rate.strip().rstrip("%") or 0)
    speed = max(0.7, min(1.2, 1 + pct / 100))
    body = json.dumps({"text": text, "model_id": ELEVEN_MODEL,
                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice(voice)}/with-timestamps?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120, context=_ssl()) as r:
        j = json.loads(r.read())
    audio = base64.b64decode(j["audio_base64"])
    if not audio:
        raise RuntimeError("ElevenLabs returned no audio")
    mp3.write_bytes(audio)
    al = j.get("alignment") or j.get("normalized_alignment") or {}
    chars, starts, ends = al.get("characters", []), al.get("character_start_times_seconds", []), al.get("character_end_times_seconds", [])
    words, cur, cs = [], "", None
    for ch, a, b in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": round(cs, 3), "end": round(prev_end, 3)})
            cur, cs = "", None
            continue
        if not cur:
            cs = a
        cur += ch
        prev_end = b
    if cur:
        words.append({"word": cur, "start": round(cs, 3), "end": round(prev_end, 3)})
    if not words:
        raise RuntimeError("ElevenLabs returned no alignment")
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


KOKORO_PY = Path(os.environ.get("KOKORO_PY", "/Volumes/Extreme SSD/_tools/kokoro/venv/bin/python"))
KOKORO_RUNNER = Path(os.environ.get("KOKORO_RUNNER", "/Volumes/Extreme SSD/TikTokPipeline/shared_media/kokoro_local.py"))
KOKORO_VOICES = {"GB_F": "bf_emma", "GB_M": "bm_george", "US_F": "af_heart", "US_M": "am_michael"}
KOKORO_MALE = ("andrew", "guy", "christopher", "eric", "brian", "davis", "jason", "tony", "roger", "steffan",
               "ryan", "thomas", "alfie", "oliver", "elliot", "ethan", "noah")


def kokoro_on() -> bool:
    return (os.environ.get("TTS_ENGINE") or "kokoro").strip().lower() != "edge" and KOKORO_PY.exists() and KOKORO_RUNNER.exists()


def kokoro_voice(edge_voice: str) -> str:
    v = (edge_voice or "").lower()
    accent = "GB" if v.startswith("en-gb") else "US"
    return KOKORO_VOICES[f"{accent}_{'M' if any(n in v for n in KOKORO_MALE) else 'F'}"]


def kokoro_speed(rate: str) -> float:
    try:
        return round(min(1.5, max(0.7, 1.0 + float(str(rate).strip().rstrip("%")) / 100.0)), 3)
    except ValueError:
        return 1.0


def synth_kokoro_batch(items: list[tuple[str, Path]], voice: str, rate: str) -> dict[Path, list[dict]]:
    """[(text, mp3)] -> {mp3: words} for the scenes Kokoro rendered; a missing entry means fall back for that scene.
    One model load for the whole storyboard."""
    import tempfile
    out: dict[Path, list[dict]] = {}
    if not items:
        return out
    with tempfile.TemporaryDirectory(prefix="video-kokoro-") as d:
        jobs = [{"text": t, "voice": kokoro_voice(voice), "speed": kokoro_speed(rate), "mp3": str(mp3),
                 "words": str(Path(d) / f"w{i}.json")} for i, (t, mp3) in enumerate(items)]
        (Path(d) / "jobs.json").write_text(json.dumps(jobs))
        env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.environ.get("PATH", "/usr/bin:/bin"),
                   ESPEAK_DATA_PATH="/opt/homebrew/share/espeak-ng-data",
                   PHONEMIZER_ESPEAK_LIBRARY="/opt/homebrew/lib/libespeak-ng.dylib")
        try:
            subprocess.run([str(KOKORO_PY), str(KOKORO_RUNNER), "--jobs", str(Path(d) / "jobs.json"),
                            "--results", str(Path(d) / "results.json")], env=env, capture_output=True, text=True,
                           timeout=60 + 30 * len(items), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            print("Kokoro timed out; using edge-tts", file=sys.stderr)
            return out
        for j, (text, mp3) in zip(jobs, items):
            try:
                words = json.loads(Path(j["words"]).read_text())
            except (OSError, ValueError):
                continue
            if words and len(words) >= 0.8 * len(text.split()) and Path(mp3).exists() and Path(mp3).stat().st_size:
                out[mp3] = words
    return out


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
    key = eleven_key()
    use_kokoro = not key and kokoro_on()
    # Kokoro audio is cached under its own hash (voice and speed included), so a storyboard narrated before the switch
    # is re-narrated whole instead of mixing cached edge scenes with new Kokoro ones
    kk = f"kk|{kokoro_voice(voice)}|{kokoro_speed(rate)}|" if use_kokoro else ""
    pending = []
    for i, sc in enumerate(sb["scenes"]):
        text = (sc.get("narration") or "").strip()
        h = hashlib.sha1(kk.encode() + f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        prev = old.get(i)
        mp3 = out_dir / "audio" / f"scene-{i}.mp3"
        if use_kokoro and text and (force or not (prev and prev.get("hash") == h and mp3.exists())):
            pending.append((text, mp3))
    kokoro_words = synth_kokoro_batch(pending, voice, rate) if use_kokoro else {}
    scenes = []
    for i, sc in enumerate(sb["scenes"]):
        text = (sc.get("narration") or "").strip()
        if not text:
            scenes.append({"index": i, "audio": None, "duration": 0, "words": [], "hash": ""})
            continue
        engine = "elevenlabs" if key else ("kokoro" if use_kokoro else "edge")
        # edge keeps its original hash so existing caches stay valid; ElevenLabs and Kokoro audio are cached separately
        h = hashlib.sha1((f"el|{eleven_voice(voice)}|{ELEVEN_MODEL}|" if key else kk).encode() + f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        mp3 = out_dir / "audio" / f"scene-{i}.mp3"
        prev = old.get(i)
        if not force and prev and prev.get("hash") == h and mp3.exists():
            scenes.append(prev)
            print(f"scene {i}: cached ({prev['duration']:.2f}s)")
            continue
        raw = None
        if key:
            try:
                raw = synth_eleven(text, voice, rate, mp3, key)
            except Exception as e:  # quota, network, bad key: fall back to edge-tts for this scene
                print(f"scene {i}: ElevenLabs failed ({type(e).__name__}: {str(e)[:120]}); using edge-tts", file=sys.stderr)
                engine = "edge"
                h = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        if raw is None and use_kokoro:
            raw = kokoro_words.get(mp3)
            if raw is None:
                print(f"scene {i}: Kokoro failed; using edge-tts", file=sys.stderr)
                engine = "edge"
                h = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
        if raw is None:
            raw = asyncio.run(synth(text, voice, rate, mp3))
        words = restore_punctuation(raw, text)
        dur = probe_duration(mp3)
        scenes.append({"index": i, "audio": f"audio/{sb['id']}/scene-{i}.mp3", "duration": dur,
                       "words": words, "hash": h, "engine": engine})
        print(f"scene {i}: {engine}, {len(words)} words, {dur:.2f}s")
    timing_path.write_text(json.dumps({"voice": voice, "rate": rate, "scenes": scenes}, indent=1))
    print(f"wrote {timing_path}")


if __name__ == "__main__":
    main()
