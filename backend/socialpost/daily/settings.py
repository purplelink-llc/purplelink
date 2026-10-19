"""Private tuning: weights, slot, platforms. ~/.config/purplelink/social-daily.json (no secrets). Defaults live here;
the file overrides them key by key, so a missing file or key is fine."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .. import paths

DEFAULT = {
    # When the post goes out (US Eastern) and when the daily job may start picking (it picks, vets and queues; the
    # scheduler posts at `slot`, or at once when the pick happens after it, as long as it is inside the posting window).
    "timezone": "America/New_York",
    "slot": "10:30",
    "pick_after": "09:30",
    "last_pick": "20:30",
    # Unattended platforms (a subset of items.STANDING_PLATFORMS). Mastodon text is written in Ben's voice.
    "platforms": ["linkedin", "bluesky", "threads", "mastodon"],
    "recent_days": 7,
    "dup_days": 21,
    "max_same_kind_streak": 3,
    "evergreen_top_n": 30,
    "stats_days": 90,
    "exclude_paths": ["/blog/digest/", "/guides/", "/tools/", "/blog/"],
    # importance by kind: release > guide > blog > video > tool > evergreen
    "importance": {"release": 1.0, "guide": 0.8, "video": 0.65, "blog": 0.6, "tool": 0.5, "evergreen": 0.3},
    # freshness = 0.5 ** (age_days / half_life); evergreen does not decay
    "half_life_days": {"release": 3.0, "guide": 3.0, "video": 3.0, "blog": 3.0, "tool": 3.0},
    "fatigue_penalty": 0.15,          # subtracted per post of the same kind in the last recent_days
    "formats": ["card", "link", "question", "statement"],
    # learning
    "prior_strength": 8,              # shrinkage: a group counts as this many average posts before its own data
    "multiplier_range": [0.5, 1.5],
    "drop_min_posts": 10,
    "drop_z": 1.28,                   # the group's upper bound must sit below everyone else's lower bound
    "drop_ratio": 0.5,                # and its mean must be under this fraction of the others' mean
    "reentry_days": 30,
    "protected_kinds": ["evergreen"],
    "min_formats": 2,
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load() -> dict:
    p = paths.daily_config_file()
    if not p.exists():
        return json.loads(json.dumps(DEFAULT))
    return _merge(DEFAULT, json.loads(p.read_text(encoding="utf-8")))


def write_default() -> bool:
    p = paths.daily_config_file()
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(DEFAULT, indent=2) + "\n", encoding="utf-8")
    p.chmod(0o600)
    return True


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def load_learned() -> dict:
    d = read_json(paths.learned_file(), {})
    d.setdefault("kind", {})
    d.setdefault("format", {})
    d.setdefault("dropped", {})        # {"kind:guide": {"since": date, "numbers": {...}}}
    d.setdefault("reentered", {})      # {"kind:guide": date}
    d.setdefault("log", [])
    return d


def load_history() -> list[dict]:
    d = read_json(paths.daily_history_file(), [])
    return d if isinstance(d, list) else []


def save_history(h: list[dict]) -> None:
    write_json(paths.daily_history_file(), h)
