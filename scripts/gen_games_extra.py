"""Trivia and horoscope data for scripts/gen_games.py (loaded by it; not run on its own)."""
from __future__ import annotations

import base64
import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

PER_DAY_ACADEMIC = 2
PER_DAY_OTDB = 3
BAD_OPTION = re.compile(r"\b(all|none|both|neither)\b.*\b(above|these|the answers)\b|^(all|none) of", re.I)


def _academic(src: Path) -> list[dict]:
    out = []
    p = src / "academic.txt"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c, q, a, *w = line.split("|")
        assert len(w) == 3, line
        out.append({"c": c, "q": q, "a": a, "w": w})
    return out


def _otdb(src: Path) -> list[dict]:
    p = src / "otdb.json"
    if not p.exists():
        return []
    seen, out = set(), []
    for it in json.loads(p.read_text(encoding="utf-8")):
        q, a, w = it["q"].strip(), it["a"].strip(), [x.strip() for x in it["w"]]
        opts = [a] + w
        if len(q) > 190 or any(len(o) > 70 for o in opts) or len(set(opts)) != 4:
            continue
        if any(BAD_OPTION.search(o) for o in opts):
            continue
        if re.search(r"[<>&]|%[0-9A-F]{2}", q + "".join(opts)):
            continue
        if re.search(r"\b(which of these|which of the following)\b.*\b(is not|isn't)\b", q, re.I) and False:
            continue
        if it.get("d") == "hard" or q in seen:
            continue
        seen.add(q)
        cat = it["c"].split(": ", 1)[-1]
        out.append({"c": cat, "q": q, "a": a, "w": w})
    out.sort(key=lambda x: x["q"])   # stable base order before the seeded shuffle
    # Keep the mix broad: the raw pool is a third video-game questions.
    caps = {"Video Games": 70, "Music": 150, "Film": 150, "Television": 100, "General Knowledge": 300}
    kept, count = [], {}
    order = out[:]
    random.Random("otdb-cap").shuffle(order)
    for it in order:
        n = count.get(it["c"], 0)
        if n >= caps.get(it["c"], 10**9):
            continue
        count[it["c"]] = n + 1
        kept.append(it)
    kept.sort(key=lambda x: x["q"])
    return kept


def enc_text(s: str) -> str:
    """UTF-8 safe light obfuscation for quiz answers (the word games reverse ASCII instead)."""
    return base64.b64encode(s.encode("utf-8")).decode()


def _shape(item: dict, enc, rng_seed: str) -> list:
    opts = [item["a"]] + item["w"]
    random.Random(rng_seed + item["q"]).shuffle(opts)
    return [item["c"], item["q"], opts, enc(item["a"])]


def _stream(pool: list[dict], seed: str, need: int) -> list[dict]:
    out: list[dict] = []
    n = 0
    while len(out) < need:
        order = pool[:]
        random.Random(f"{seed}:{n}").shuffle(order)
        out.extend(order)
        n += 1
    return out[:need]


def trivia(src: Path, epoch: str, days: int, enc) -> dict:
    ac, ot = _academic(src), _otdb(src)
    if not ac or not ot:
        return {}
    a_stream = _stream(ac, "trivia-academic", days * PER_DAY_ACADEMIC)
    o_stream = _stream(ot, "trivia-otdb", days * PER_DAY_OTDB + 400)
    out_days = []
    used = 0
    for d in range(days):
        picked = a_stream[d * PER_DAY_ACADEMIC:(d + 1) * PER_DAY_ACADEMIC]
        extra: list[dict] = []
        cats = {x["c"] for x in picked}
        i = used
        while len(extra) < PER_DAY_OTDB and i < len(o_stream):
            cand = o_stream[i]
            if cand["c"] not in cats or i - used > 25:
                extra.append(cand)
                cats.add(cand["c"])
                o_stream.pop(i)
            else:
                i += 1
        qs = picked + extra
        random.Random(f"trivia-day:{d}").shuffle(qs)
        out_days.append([_shape(x, enc, f"opt{d}") for x in qs])
    return {"epoch": epoch, "days": out_days}


# ---- Daily Stars ----
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SYNODIC = 29.530588853
NEW_MOON_REF = 2451550.1  # Julian date of the new moon on 2000-01-06


def moon_phase(d: date) -> str:
    """Approximate phase name from the mean synodic month (good to about half a day).
    The four main phases get a one-day window; the rest of the cycle is crescent or gibbous."""
    jd = d.toordinal() + 1721424.5 + 0.5   # local noon, close enough for a phase name
    age = (jd - NEW_MOON_REF) % SYNODIC
    q = SYNODIC / 4
    for i, name in enumerate(["new moon", "first quarter", "full moon", "last quarter"]):
        centre = i * q
        if min(abs(age - centre), abs(age - centre - SYNODIC)) < 0.9:
            return name
    if age < q:
        return "waxing crescent"
    if age < 2 * q:
        return "waxing gibbous"
    if age < 3 * q:
        return "waning gibbous"
    return "waning crescent"


def stars(src: Path, epoch: str) -> dict:
    p = src / "stars-source.txt"
    if not p.exists():
        return {}
    days: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        day, sign, text = [x.strip() for x in line.split("|", 2)]
        assert sign in SIGNS, line
        days.setdefault(day, {})[sign] = text
    out = {}
    for day in sorted(days):
        y, m, dd = map(int, day.split("-"))
        out[day] = {"moon": moon_phase(date(y, m, dd)), "signs": days[day]}
    return {"days": out}


def build(src: Path, epoch: str, days: int, enc) -> dict[str, str]:
    files: dict[str, str] = {}
    t = trivia(src, epoch, days, enc_text)
    if t:
        files["trivia.json"] = json.dumps(t, ensure_ascii=False, separators=(",", ":")) + "\n"
    s = stars(src, epoch)
    if s:
        files["stars.json"] = json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n"
    return files
