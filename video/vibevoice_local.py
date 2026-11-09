#!/usr/bin/env python3
"""Local VibeVoice-1.5B narration (MLX) cloned from one stored reference voice, with word timings, for the how-tos.

Run with the VibeVoice venv's python (/Volumes/Extreme SSD/_tools/vibevoice/venv, built from requirements.lock.txt there:
mlx-audio 0.6.4; models in ../models: vibevoice-1.5b with lm_head_tied.safetensors, the Qwen2.5 tokenizer, Whisper):

    <vibevoice venv>/bin/python vibevoice_local.py --jobs jobs.json --results results.json

jobs.json:    [{"text": "<caption text>", "speak": "<spoken form>", "ref": "<reference.wav>", "mp3": "<out.mp3>",
                "words": "<out.words.json>"}, ...]
results.json: [{"mp3", "ok", "audio_s", "gen_s", "match", "error"}, ...]
words file:   [{"word", "start", "end"}, ...] one entry per whitespace token of "text", so narrate.py's
              restore_punctuation keeps the script's own spelling in the captions.

Why this shape (TTS bake-off 2026-11-09, Ben's pick): VibeVoice keeps a cloned voice closest to its reference, but one
long pass speeds up (212 wpm on a 90 s script), so text is read three sentences at a time and joined with a short
pause. The model gives no timings, so Whisper large-v3-turbo transcribes the result with word timestamps and the
script's tokens are matched to Whisper's words (difflib); unmatched tokens get times interpolated from neighbours.
A take whose transcript matches under MIN_MATCH of the script fails, and narrate.py falls back to the current voice.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time

TOOLS = os.environ.get("VIBEVOICE_HOME", "/Volumes/Extreme SSD/_tools/vibevoice")
MODEL = os.path.join(TOOLS, "models", "vibevoice-1.5b")
WHISPER = os.path.join(TOOLS, "models", "whisper-large-v3-turbo")
SENTENCES_PER_CHUNK = 3
GAP_S = 0.25
MIN_MATCH = 0.85
NORM = re.compile(r"[^a-z0-9]+")


def norm(w):
    return NORM.sub("", w.lower())


def chunks(text, n=SENTENCES_PER_CHUNK):
    s = [x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x]
    return [" ".join(s[i:i + n]) for i in range(0, len(s), n)]


def align(tokens, heard):
    """tokens: script words; heard: [{"word","start","end"}] from Whisper -> one timing per token, plus match ratio."""
    a = [norm(t) for t in tokens]
    b = [norm(h["word"]) for h in heard]
    times = [None] * len(tokens)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    matched = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
            matched += i2 - i1
        elif tag == "replace" and j2 > j1:
            # same span said differently ("P01" heard as "P-O-1"): spread the heard span over the script tokens
            s, e = heard[j1]["start"], heard[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = (s + (e - s) * k / n, s + (e - s) * (k + 1) / n)
    # tokens Whisper did not hear at all: interpolate between the neighbours
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev)
            times[i] = (prev, max(prev, nxt))
    words = [{"word": re.sub(r"^[^\w]+|[^\w]+$", "", t) or t, "start": round(s, 3), "end": round(e, 3)}
             for t, (s, e) in zip(tokens, times)]
    return words, matched / max(1, len(tokens))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--results", required=True)
    o = ap.parse_args()
    jobs = json.load(open(o.jobs))
    import numpy as np
    import soundfile as sf
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    from mlx_audio.stt.utils import load_model as load_stt

    t0 = time.time()
    tts = load_model(model_path=MODEL)
    sr = tts.sample_rate
    stt = None
    results = []
    for j in jobs:
        r = {"mp3": j["mp3"], "ok": False, "audio_s": 0, "gen_s": 0, "match": 0, "error": ""}
        try:
            g0 = time.time()
            parts = []
            for c in chunks(j.get("speak") or j["text"]):
                for seg in tts.generate("Speaker 1: " + c, ref_audio=j["ref"]):
                    parts.append(np.array(seg.audio.astype(mx.float32)).reshape(-1))
                parts.append(np.zeros(int(GAP_S * sr), dtype=np.float32))
            audio = np.concatenate(parts[:-1]) if len(parts) > 1 else np.zeros(1, np.float32)
            r["gen_s"] = round(time.time() - g0, 2)
            r["audio_s"] = round(len(audio) / sr, 2)
            wav = j["mp3"] + ".wav"
            sf.write(wav, audio, sr)
            if stt is None:
                stt = load_stt(WHISPER)
            heard = []
            res = stt.generate(wav, language="en", word_timestamps=True)
            for seg in res.segments:
                for w in seg.get("words", []):
                    heard.append({"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])})
            words, match = align(j["text"].split(), heard)
            r["match"] = round(match, 3)
            if match < MIN_MATCH:
                raise RuntimeError(f"transcript matched {match:.0%} of the script (need {MIN_MATCH:.0%})")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k",
                            j["mp3"]], check=True, stdin=subprocess.DEVNULL)
            os.remove(wav)
            tmp = j["words"] + ".tmp"
            json.dump(words, open(tmp, "w"))
            os.replace(tmp, j["words"])
            r["ok"] = True
        except Exception as e:  # one failed take fails the job; narrate.py decides the fallback
            r["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        results.append(r)
        print(json.dumps(r), file=sys.stderr)
    tmp = o.results + ".tmp"
    json.dump({"load_s": round(time.time() - t0, 1), "jobs": results}, open(tmp, "w"), indent=1)
    os.replace(tmp, o.results)


if __name__ == "__main__":
    main()
