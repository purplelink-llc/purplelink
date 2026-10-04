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


# ---- Daily crossword ----
MAX_CLUE = 110


def clue_problems(answer: str, clue: str) -> list[str]:
    """Rules every clue must follow; also used by check_games.py and the weekly routine."""
    out = []
    c = (clue or "").strip()
    if not c:
        return ["missing"]
    if len(c) > MAX_CLUE:
        out.append(f"longer than {MAX_CLUE} characters")
    low = c.lower()
    a = answer.lower()
    words = re.findall(r"[a-z']+", low)
    if a in words:
        out.append("contains its own answer")
    elif len(a) >= 5 and any(w.startswith(a[: max(4, len(a) - 2)]) for w in words):
        out.append("contains most of its answer")
    if "\u2014" in c or "\u2013" in c:
        out.append("uses a dash character")
    if any(ord(ch) > 0x2000 and ch not in "\u2019\u201c\u201d" for ch in c):
        out.append("uses a symbol or emoji")
    if "!" in c:
        out.append("uses an exclamation mark")
    return out


def crossword(src: Path) -> dict:
    gdir = src / "crossword"
    if not gdir.exists():
        return {}
    days = {}
    for gp in sorted(gdir.glob("*.grid.json")):
        day = gp.name.split(".")[0]
        cp = gdir / f"{day}.clues.json"
        if not cp.exists():
            continue
        grid = json.loads(gp.read_text(encoding="utf-8"))
        clues = json.loads(cp.read_text(encoding="utf-8"))
        entries, bad = [], []
        for e in grid["entries"]:
            clue = clues.get(e["answer"].upper()) or clues.get(e["answer"])
            probs = clue_problems(e["answer"], clue)
            if probs:
                bad.append(f'{e["answer"]}: {", ".join(probs)}')
            entries.append({"n": e["n"], "dir": e["dir"], "row": e["row"], "col": e["col"],
                            "len": len(e["answer"]), "clue": (clue or "").strip()})
        if bad:
            print(f"crossword {day}: left out ({len(bad)} clue problem(s)): " + "; ".join(bad[:5]))
            continue
        days[day] = {"weekday": grid["weekday"], "size": grid["size"],
                     "solution": enc_text("/".join(grid["rows"])), "entries": entries}
    return {"days": days}


# ---- Daily Photo ("where in the world was this taken") ----
PHOTOS_PER_DAY = 5
SKIP_WORDS = ("close-up", "close up", "closeup", "macro", "texture", "detail", "pattern", "petal", "bokeh", "abstract", "sign ", "plaque", "stalk", "menu")


def photo_pool(root: Path) -> dict[str, list[dict]]:
    """Photographs from the published photography hubs that are recognisable as a place, grouped by country."""
    hub = root / "site" / "photography" / "hub-data.json"
    img_dir = root / "site" / "assets" / "photography" / "hub"
    if not hub.exists():
        return {}
    data = json.loads(hub.read_text(encoding="utf-8"))
    pool: dict[str, list[dict]] = {}
    for c in data["countries"]:
        items = []
        for pl in c["places"]:
            for im in pl["images"]:
                items.append((im, pl["name"] + ", " + c["name"], pl["url"]))
        for im in c["extra"]:
            items.append((im, c["name"], c["url"]))
        for im, label, url in items:
            stem = im["stem"].lower().replace("_", "-")
            title = im["title"]
            if any(w in title.lower() for w in SKIP_WORDS):
                continue
            if not (img_dir / f"{stem}-1200.webp").exists():
                continue
            pool.setdefault(c["name"], []).append({"i": stem, "t": title, "p": label, "c": im["caption"], "u": url})
    for lst in pool.values():
        lst.sort(key=lambda x: x["i"])
    return pool


def photo_days(root: Path, epoch: str, days: int) -> dict:
    pool = photo_pool(root)
    countries = sorted(c for c, v in pool.items() if len(v) >= 3)
    if len(countries) < 4:
        return {}
    cycles = {c: [] for c in countries}
    counters = {c: 0 for c in countries}

    def next_photo(c: str) -> dict:
        if not cycles[c]:
            order = pool[c][:]
            random.Random(f"photo-{c}-{counters[c]}").shuffle(order)
            counters[c] += 1
            cycles[c] = order
        return cycles[c].pop()

    weights = [len(pool[c]) ** 0.5 for c in countries]
    out = []
    for d in range(days):
        rng = random.Random(f"photo-day:{d}")
        chosen: list[str] = []
        while len(chosen) < PHOTOS_PER_DAY:
            c = rng.choices(countries, weights=weights)[0]
            if c not in chosen:
                chosen.append(c)
        rounds = []
        for c in chosen:
            ph = next_photo(c)
            others = [x for x in countries if x != c]
            rng.shuffle(others)
            opts = [c] + others[:3]
            rng.shuffle(opts)
            rounds.append({"i": ph["i"], "o": opts, "a": enc_text(c), "t": ph["t"], "p": ph["p"], "c": ph["c"], "u": ph["u"]})
        out.append(rounds)
    return {"epoch": epoch, "days": out}


# ---- Daily Chess (Lichess puzzle database, CC0) ----
def chess_days(src: Path, epoch: str, days: int) -> dict:
    p = src / "chess-puzzles.json"
    if not p.exists():
        return {}
    bands = json.loads(p.read_text(encoding="utf-8"))["bands"]
    y, m, d = map(int, epoch.split("-"))
    start = date(y, m, d)
    nxt = [0] * 7
    out = []
    for i in range(days):
        wd = (start + timedelta(days=i)).weekday()      # Monday easiest ... Sunday hardest
        band = bands[wd]
        pz = band[nxt[wd] % len(band)]
        nxt[wd] += 1
        out.append({"i": pz["id"], "f": pz["f"], "m": enc_text(pz["m"]), "r": pz["r"], "t": pz["t"], "g": pz["g"]})
    return {"epoch": epoch, "days": out}


def build(src: Path, epoch: str, days: int, enc) -> dict[str, str]:
    files: dict[str, str] = {}
    t = trivia(src, epoch, days, enc_text)
    if t:
        files["trivia.json"] = json.dumps(t, ensure_ascii=False, separators=(",", ":")) + "\n"
    ch = chess_days(src, epoch, days)
    if ch:
        files["chess.json"] = json.dumps(ch, ensure_ascii=False, separators=(",", ":")) + "\n"
    sd = src / "sudoku.json"
    if sd.exists():
        files["sudoku.json"] = sd.read_text(encoding="utf-8")
    ph = photo_days(src.parent.parent, epoch, 150)   # 150 days is ~280 KB; the page wraps around after that
    if ph:
        files["photo.json"] = json.dumps(ph, ensure_ascii=False, separators=(",", ":")) + "\n"
    cw = crossword(src)
    if cw:
        files["crossword.json"] = json.dumps(cw, ensure_ascii=False, separators=(",", ":")) + "\n"
    s = stars(src, epoch)
    if s:
        files["stars.json"] = json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        from gen_attr import build as attr_build
    except ImportError:
        from scripts.gen_attr import build as attr_build
    files.update(attr_build(src, epoch, days, enc_text))
    return files
