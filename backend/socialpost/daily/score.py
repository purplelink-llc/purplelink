"""Scoring: importance by kind x freshness decay x learned multipliers (kind and format) minus a fatigue penalty.

Hard rules before scoring: the same item is not posted again within `dup_days`, the same kind is not picked more
than `max_same_kind_streak` days in a row, and a kind or format that the weekly learning step dropped is out until
it re-enters. All weights come from the private config, so they can be tuned without a code change.
"""
from __future__ import annotations

import datetime as dt

from .candidates import Candidate


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def posted_history(history: list[dict]) -> list[dict]:
    """History rows that count as 'posted' for repeat and fatigue rules (the pipeline marks `counts`)."""
    return [h for h in history if h.get("counts", True)]


def blocked_platforms(c: Candidate, history: list[dict], today: dt.date, dup_days: int,
                      all_platforms: list[str]) -> set[str]:
    """Platforms where this item (or, for outside posts, anything that names it) went out within `dup_days`."""
    from .external import names_candidate
    out: set[str] = set()
    for h in posted_history(history):
        if not 0 <= (today - _date(h["date"])).days < dup_days:
            continue
        if h.get("external"):
            hit = names_candidate(c, h.get("text", ""))
        else:
            hit = h.get("candidate") == c.id
        if hit:
            out |= set(h.get("platforms") or all_platforms)
    return out


def recent_dup(c: Candidate, history: list[dict], today: dt.date, dup_days: int, platforms=None) -> bool:
    """True when the item is blocked on every one of `platforms` (all four by default)."""
    plats = list(platforms or ["linkedin", "bluesky", "threads", "mastodon"])
    return set(plats) <= blocked_platforms(c, history, today, dup_days, plats)


def pipeline_rows(history: list[dict]) -> list[dict]:
    """The daily pipeline's own picks (not outside posts), one per day: the day's main pick."""
    return [h for h in posted_history(history) if not h.get("external") and h.get("primary", True)]


def kind_streak_blocked(kind: str, history: list[dict], today: dt.date, limit: int) -> bool:
    """True when the last `limit` picks (one per day, most recent first) were all this kind."""
    rows = sorted(pipeline_rows(history), key=lambda h: h["date"], reverse=True)
    rows = [h for h in rows if _date(h["date"]) < today]
    last = rows[:limit]
    return len(last) >= limit and all(h.get("kind") == kind for h in last)


def freshness(c: Candidate, today: dt.date, cfg: dict) -> float:
    if c.kind == "evergreen":
        return 1.0
    hl = float(cfg["half_life_days"].get(c.kind, 3.0))
    return 0.5 ** (c.age_days(today) / hl)


def evergreen_weight(c: Candidate, max_traffic: int) -> float:
    """0.5 for an unranked page, up to 1.0 for the most visited."""
    if max_traffic <= 0:
        return 0.5
    return 0.5 + 0.5 * min(1.0, c.traffic / max_traffic)


def fatigue(kind: str, history: list[dict], today: dt.date, cfg: dict) -> float:
    n = sum(1 for h in pipeline_rows(history)
            if h.get("kind") == kind and 0 < (today - _date(h["date"])).days <= cfg["recent_days"])
    return n * cfg["fatigue_penalty"]


def multiplier(learned: dict, group: str, name: str) -> float:
    return float(learned.get(group, {}).get(name, 1.0))


def is_dropped(learned: dict, group: str, name: str) -> bool:
    return f"{group}:{name}" in learned.get("dropped", {})


def score(c: Candidate, fmt: str, today: dt.date, cfg: dict, learned: dict, history: list[dict],
          max_traffic: int = 0) -> float:
    base = float(cfg["importance"][c.kind]) * freshness(c, today, cfg)
    if c.kind == "evergreen":
        base *= evergreen_weight(c, max_traffic)
    base *= multiplier(learned, "kind", c.kind) * multiplier(learned, "format", fmt)
    return base - fatigue(c.kind, history, today, cfg)


def rank(cands: list[Candidate], fmt: str, today: dt.date, cfg: dict, learned: dict, history: list[dict],
         log=None, platforms=None) -> list[tuple[float, Candidate]]:
    """Eligible candidates, best first. `log(msg)` receives the reason each excluded candidate was left out."""
    log = log or (lambda m: None)
    mx = max((c.traffic for c in cands if c.kind == "evergreen"), default=0)
    out = []
    for c in cands:
        if is_dropped(learned, "kind", c.kind):
            log(f"{c.id}: kind {c.kind} is dropped until it re-enters")
            continue
        if recent_dup(c, history, today, cfg["dup_days"], platforms):
            log(f"{c.id}: already posted on every platform within the last {cfg['dup_days']} days")
            continue
        if kind_streak_blocked(c.kind, history, today, cfg["max_same_kind_streak"]):
            log(f"{c.id}: {cfg['max_same_kind_streak']} {c.kind} picks in a row already")
            continue
        out.append((score(c, fmt, today, cfg, learned, history, mx), c))
    out.sort(key=lambda t: (-t[0], t[1].id))
    return out


# ---------------------------------------------------------------- format rotation
def pick_format(history: list[dict], cfg: dict, learned: dict, has_image: bool = True, skip: set | None = None) -> str:
    """Rotate the format by day so each one gets a fair run: the least-used live format, ties broken by the cycle
    order. A dropped format is skipped; `card` needs an image. Returns the format name."""
    formats = [f for f in cfg["formats"] if not is_dropped(learned, "format", f)]
    if not has_image:
        formats = [f for f in formats if f != "card"] or list(cfg["formats"])
    formats = [f for f in formats if f not in (skip or set())] or [f for f in cfg["formats"] if f != "card"]
    counts = {f: sum(1 for h in pipeline_rows(history) if h.get("format") == f) for f in formats}
    order = {f: i for i, f in enumerate(cfg["formats"])}
    last = max(pipeline_rows(history), key=lambda h: h["date"], default=None)
    last_idx = order.get(last.get("format"), -1) if last else -1
    n = len(cfg["formats"])
    return sorted(formats, key=lambda f: (counts[f], (order[f] - last_idx - 1) % n))[0]
