#!/usr/bin/env python3.12
"""Keyword research for the ambient channel, from YouTube's public search autocomplete.

    python3.12 keywords.py --refresh            # ask the suggest endpoint for every seed x modifier (about 400 requests, 2 a second), cache, rank
    python3.12 keywords.py --show brown         # the ranked phrases for one sound (or theme: campfire, halloween, winter, study)
    python3.12 keywords.py --show brown --theme campfire --top 10

Autocomplete is what people actually type into the search box, in order of how often. It is a demand signal, not a view count. The endpoint is
`https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=...` (no key, no login). We ask politely: two requests a second at most,
every answer cached with its date for 7 days, and the whole run is meant to happen once a week.

Files, in `$AMBIENT_KEYWORDS_DIR` (default /Volumes/Extreme SSD/PurplelinkVideos/ambient/keywords/):
    cache.json            {query: {"date": "2026-10-17", "suggestions": [...]}}
    ranked-YYYY-MM-DD.json and latest.json
                          {"date", "kinds": {name: [{"phrase", "score", "seeds", "best_pos"}]}, "modifiers": {phrase: score}}

Ranking: a suggestion earns (10 - position) / 10 for every query that returns it (position 0 is the first suggestion), so a phrase that comes up first
for several seeds beats one that comes up once at position 8. A seed asked on its own counts three times a seed with a modifier added ("brown noise" against
"brown noise black screen"), because a modifier we typed ourselves is echoed back and says little about demand. For the same reason the modifier table
("black screen", "10 hours", "no ads"...) counts only what autocomplete volunteers for the bare seeds. A phrase only counts for a sound or theme if it contains one of that kind's key words
(so "brown noise adhd" counts for brown and "rain sounds" for rain, but a stray "lofi girl" does not count for campfire).

Nothing here posts, uploads or signs in anywhere.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q="
CACHE_DAYS = 7
PLAIN_WEIGHT = 3.0                  # a bare seed counts this many times a seed with a modifier added
MIN_GAP = 0.5                       # seconds between requests: two a second at most
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

# kind -> (seed phrases, words a suggestion must contain to count for this kind)
SOUND_SEEDS = {
    "brown": (["brown noise"], ["brown noise"]),
    "pink": (["pink noise"], ["pink noise"]),
    "white": (["white noise"], ["white noise"]),
    "binaural-alpha": (["alpha binaural beats", "10 hz binaural beats", "binaural beats"], ["binaural", "alpha"]),
    "binaural-theta": (["theta binaural beats", "6 hz binaural beats"], ["theta", "binaural"]),
    "binaural-delta": (["delta binaural beats", "2 hz binaural beats"], ["delta", "binaural"]),
    "synth": (["ambient synth music", "ambient drone", "synth pad ambient", "ambient music"], ["ambient", "synth", "drone"]),
    "lofi": (["lofi study music", "lofi chiptune", "lofi music"], ["lofi", "lo-fi"]),
    "chiptune": (["chiptune study music", "8 bit study music", "chiptune music"], ["chiptune", "8 bit", "8-bit"]),
    "rain": (["rain sounds", "rain sounds for sleeping"], ["rain"]),
    "thunderstorm": (["thunderstorm sounds", "rain and thunder sounds"], ["thunder"]),
    "fireplace": (["fireplace sounds", "crackling fire sounds"], ["fireplace", "fire sounds", "crackling fire", "crackling"]),
    "ocean": (["ocean waves sounds"], ["ocean", "waves"]),
    "wind": (["wind sounds"], ["wind"]),
    "fan": (["fan sounds", "fan noise for sleeping"], ["fan"]),
    "airplane": (["airplane cabin sounds", "airplane white noise", "airplane noise"], ["airplane", "plane", "flight", "jet"]),
}
THEME_SEEDS = {
    "campfire": (["campfire sounds", "campfire ambience", "crackling campfire"], ["campfire", "camp fire"]),
    "halloween": (["halloween ambience", "spooky ambience", "halloween music"], ["halloween", "spooky"]),
    "winter": (["cozy winter cabin ambience", "winter cabin ambience", "snowy cabin sounds"], ["winter", "snow", "cabin"]),
    "study": (["study with me", "study with me pomodoro", "study ambience"], ["study"]),
}
MODIFIERS_SOUND = ["", "10 hours", "8 hours", "for sleep", "for studying", "black screen", "dark screen", "no ads", "1 hour", "3 hours"]
MODIFIERS_THEME = ["", "10 hours", "for sleep", "for studying", "black screen"]
# phrases whose frequency across all suggestions tells which title modifiers people use
MODIFIER_PHRASES = ["10 hours", "8 hours", "12 hours", "3 hours", "2 hours", "1 hour", "black screen", "dark screen", "no ads", "no music", "for sleep",
                    "for studying", "for focus", "for work", "for reading", "pomodoro", "no loop", "loop"]


def kw_dir() -> Path:
    return Path(os.environ.get("AMBIENT_KEYWORDS_DIR", "/Volumes/Extreme SSD/PurplelinkVideos/ambient/keywords"))


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def queries() -> list[tuple[str, str, str]]:
    """Every (kind, name, query) to ask: each seed with each modifier."""
    out, seen = [], set()
    for kind, table, mods in (("sound", SOUND_SEEDS, MODIFIERS_SOUND), ("theme", THEME_SEEDS, MODIFIERS_THEME)):
        for name, (seeds, _) in table.items():
            for s in seeds:
                for m in mods:
                    q = f"{s} {m}".strip()
                    if (name, q) not in seen:
                        seen.add((name, q))
                        out.append((kind, name, q))
    return out


def fetch(q: str, timeout: float = 15.0) -> list[str]:
    req = urllib.request.Request(ENDPOINT + urllib.parse.quote(q), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return [str(x) for x in data[1]]


def refresh(today: dt.date | None = None, fetcher=fetch, sleep=time.sleep, log=print) -> dict:
    """Asks for every query not cached within CACHE_DAYS, writes the cache, ranks, and writes ranked-<date>.json and latest.json."""
    today = today or dt.date.today()
    d = kw_dir()
    d.mkdir(parents=True, exist_ok=True)
    cache = _load_json(d / "cache.json", {})
    asked = failed = 0
    for _, _, q in queries():
        hit = cache.get(q)
        if hit and (today - dt.date.fromisoformat(hit["date"])).days < CACHE_DAYS:
            continue
        try:
            cache[q] = {"date": today.isoformat(), "suggestions": fetcher(q)}
            asked += 1
        except Exception as e:                                       # one failed request must not lose the run; the old cache entry (if any) stays
            failed += 1
            log(f"keywords: {q!r} failed: {e}")
        sleep(MIN_GAP)
        if asked % 50 == 0 and asked:
            (d / "cache.json").write_text(json.dumps(cache, indent=1, sort_keys=True))
    (d / "cache.json").write_text(json.dumps(cache, indent=1, sort_keys=True))
    ranked = rank(cache, today)
    (d / f"ranked-{today.isoformat()}.json").write_text(json.dumps(ranked, indent=1))
    (d / "latest.json").write_text(json.dumps(ranked, indent=1))
    log(f"keywords: {asked} asked, {failed} failed, {len(cache)} cached")
    return ranked


def rank(cache: dict, today: dt.date | None = None) -> dict:
    """Ranked phrases per sound and per theme, plus how often each title modifier shows up."""
    kinds: dict = {}
    mods: dict = {}
    for _, name_table in (("sound", SOUND_SEEDS), ("theme", THEME_SEEDS)):
        for name, (seeds, must) in name_table.items():
            agg: dict = {}
            for _, n, q in queries():
                if n != name or q not in cache:
                    continue
                plain = q in seeds
                for pos, s in enumerate(cache[q]["suggestions"]):
                    low = s.lower().strip()
                    if not any(m in low for m in must):
                        continue
                    a = agg.setdefault(low, {"phrase": low, "score": 0.0, "seeds": set(), "best_pos": pos})
                    a["score"] += (10 - pos) / 10 * (PLAIN_WEIGHT if plain else 1.0)
                    a["seeds"].add(q)
                    a["best_pos"] = min(a["best_pos"], pos)
                    if plain:
                        for m in MODIFIER_PHRASES:
                            if m in low:
                                mods[m] = mods.get(m, 0.0) + (10 - pos) / 10
            kinds[name] = sorted(({"phrase": v["phrase"], "score": round(v["score"], 2), "seeds": len(v["seeds"]), "best_pos": v["best_pos"]} for v in agg.values()),
                                 key=lambda r: (-r["score"], r["best_pos"], r["phrase"]))
    return {"date": (today or dt.date.today()).isoformat(), "kinds": kinds, "modifiers": {k: round(v, 2) for k, v in sorted(mods.items(), key=lambda kv: -kv[1])}}


def load(path: Path | None = None) -> dict | None:
    """The latest ranked keywords, or None if the research has not been run (callers then fall back to the built-in copy)."""
    data = _load_json(path or kw_dir() / "latest.json", None)
    return data if isinstance(data, dict) and "kinds" in data else None


def top(kw: dict | None, name: str, n: int = 10, contains: str | None = None) -> list[str]:
    """The top n phrases for a sound or theme name, optionally only those containing a word."""
    rows = (kw or {}).get("kinds", {}).get(name, [])
    out = [r["phrase"] for r in rows if not contains or contains in r["phrase"]]
    return out[:n]


def modifier_score(kw: dict | None, phrase: str) -> float:
    return float((kw or {}).get("modifiers", {}).get(phrase, 0.0))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--show", metavar="NAME", help="a sound or theme name")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--theme", help="with --show: also list the theme's phrases")
    a = ap.parse_args(argv)
    if a.refresh:
        refresh()
    kw = load()
    if a.show:
        if kw is None:
            print("no keyword research yet: run with --refresh")
            return 1
        for name in [a.show] + ([a.theme] if a.theme else []):
            print(f"{name}:")
            for r in kw["kinds"].get(name, [])[: a.top]:
                print(f"  {r['score']:6.2f}  seeds={r['seeds']:<3} {r['phrase']}")
    elif not a.refresh:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
