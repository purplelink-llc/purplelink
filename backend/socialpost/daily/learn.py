"""Weekly learning: results by kind and format, shrunk multipliers, and the drop rule.

Multiplier = shrunk group mean / overall mean, clamped. Shrinkage adds `prior_strength` average posts to every group,
so a group with a handful of posts stays near 1.0 and one lucky week moves nothing.

Drop rule (kind or format): at least `drop_min_posts` posts (counted since its last re-entry) AND clearly the worst:
its mean is the lowest of all groups, under `drop_ratio` of everyone else's mean, and its upper confidence bound
(mean + z x standard error) is below the others' lower bound. One bad week cannot satisfy that with 10 posts. A drop
is logged with its numbers, lasts `reentry_days`, then the group re-enters and must earn a new 10 posts. Protected
kinds are never dropped, and at least `min_formats` formats always stay in.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from . import settings as st


def by_item(outcomes: list[dict]) -> list[dict]:
    """Sum platforms into one row per post (one pick = one observation)."""
    rows: dict[str, dict] = {}
    for o in outcomes:
        r = rows.setdefault(o["item"], {"item": o["item"], "kind": o["kind"], "format": o["format"],
                                        "posted": o["posted"], "outcome": 0, "clicks": 0, "engagement": 0})
        r["outcome"] += o["outcome"]
        r["clicks"] += o["clicks"]
        r["engagement"] += o["engagement"]
        r["posted"] = min(r["posted"], o["posted"])
    return list(rows.values())


def _stats(xs: list[float]) -> tuple[int, float, float]:
    n = len(xs)
    if n == 0:
        return 0, 0.0, 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    return n, m, sd


def group(rows: list[dict], field: str, since: dict | None = None) -> dict[str, list[float]]:
    g: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        cut = (since or {}).get(r[field])
        if cut and r["posted"] <= cut:
            continue
        g[r[field]].append(float(r["outcome"]))
    return g


def multipliers(groups: dict[str, list[float]], cfg: dict) -> dict[str, float]:
    allx = [x for xs in groups.values() for x in xs]
    n_all, m_all, _ = _stats(allx)
    lo, hi = cfg["multiplier_range"]
    if n_all == 0 or m_all <= 0:
        return {k: 1.0 for k in groups}
    k0 = cfg["prior_strength"]
    out = {}
    for name, xs in groups.items():
        shrunk = (sum(xs) + k0 * m_all) / (len(xs) + k0)
        out[name] = round(min(hi, max(lo, shrunk / m_all)), 4)
    return out


def drop_candidate(name: str, groups: dict[str, list[float]], cfg: dict) -> dict | None:
    """Numbers for `name` if it meets the drop rule, else None."""
    xs = groups.get(name, [])
    n, m, sd = _stats(xs)
    if n < cfg["drop_min_posts"]:
        return None
    others = [x for k, v in groups.items() if k != name for x in v]
    no, mo, sdo = _stats(others)
    if no < cfg["drop_min_posts"] or mo <= 0:
        return None
    other_means = [sum(v) / len(v) for k, v in groups.items() if k != name and len(v) >= 3]
    if other_means and m > min(other_means):
        return None          # not the bottom group
    se, seo = sd / math.sqrt(n), sdo / math.sqrt(no)
    z = cfg["drop_z"]
    if not (m < cfg["drop_ratio"] * mo and m + z * se < mo - z * seo):
        return None
    return {"posts": n, "mean": round(m, 3), "others_posts": no, "others_mean": round(mo, 3),
            "se": round(se, 3), "others_se": round(seo, 3)}


def update(rows: list[dict], learned: dict, cfg: dict, today: dt.date) -> dict:
    """New learned state from this week's rows. Mutates and returns `learned`; appends to its log."""
    # re-entry first
    for key, rec in list(learned["dropped"].items()):
        if (today - dt.date.fromisoformat(rec["since"])).days >= cfg["reentry_days"]:
            del learned["dropped"][key]
            learned["reentered"][key] = today.isoformat()
            learned["log"].append({"date": today.isoformat(), "event": "re-entered", "group": key})
    for field, gname in (("kind", "kind"), ("format", "format")):
        since = {k.split(":", 1)[1]: v for k, v in learned["reentered"].items() if k.startswith(f"{gname}:")}
        groups = group(rows, field, since)
        learned[gname] = multipliers(group(rows, field), cfg)
        for name in list(groups):
            key = f"{gname}:{name}"
            if key in learned["dropped"]:
                continue
            if gname == "kind" and name in cfg["protected_kinds"]:
                continue
            if gname == "format":
                live = [f for f in cfg["formats"] if f"format:{f}" not in learned["dropped"]]
                if len(live) - 1 < cfg["min_formats"]:
                    continue
            nums = drop_candidate(name, groups, cfg)
            if nums:
                learned["dropped"][key] = {"since": today.isoformat(), "numbers": nums}
                learned["log"].append({"date": today.isoformat(), "event": "dropped", "group": key, **nums})
    return learned


def report(rows: list[dict], outcomes: list[dict], learned: dict, cfg: dict, today: dt.date, notes: list[str]) -> str:
    def table(field: str) -> list[str]:
        g = group(rows, field)
        lines = [f"| {field} | posts | mean outcome | multiplier | status |", "|---|---|---|---|---|"]
        for name, xs in sorted(g.items()):
            n, m, _ = _stats(xs)
            drop = learned["dropped"].get(f"{field}:{name}")
            status = f"dropped since {drop['since']}" if drop else ("needs 10 posts to be droppable" if n < cfg["drop_min_posts"] else "in")
            lines.append(f"| {name} | {n} | {m:.2f} | {learned[field].get(name, 1.0):.2f} | {status} |")
        return lines

    unknown_views = sum(1 for o in outcomes if o.get("views") is None)
    out = [f"# Social weekly report, {today.isoformat()}", "",
           f"Posts with results so far: {len(rows)} (platform results: {len(outcomes)}). "
           "Outcome per post = first-touch clicks to its page from that platform + likes + 2 x reposts + 2 x replies, "
           "summed over platforms. Views are not counted (unknown on most platforms).", "",
           "## By kind", *table("kind"), "", "## By format", *table("format"), ""]
    log = [e for e in learned["log"] if e["date"] >= (today - dt.timedelta(days=7)).isoformat()]
    out += ["## Drops and re-entries this week"]
    out += [f"- {e['date']}: {e['event']} {e['group']}" + (f" ({e['posts']} posts, mean {e['mean']} vs others {e['others_mean']} over {e['others_posts']})" if e["event"] == "dropped" else "") for e in log] or ["- none"]
    out += ["", "## Data gaps"]
    out += [f"- {n}" for n in notes[-5:]] or ["- none"]
    if unknown_views:
        out.append(f"- {unknown_views} platform results have unknown views (LinkedIn has no public counts; Threads "
                   "needs `threads_manage_insights`).")
    out += ["", "Small samples barely move a multiplier (shrinkage toward 1.0). Nothing is dropped under 10 posts.", ""]
    return "\n".join(out)


def run_weekly(metrics: dict, today: dt.date, cfg: dict | None = None):
    """Returns (report text, learned). Saves learned state; the caller writes the report file and notifies."""
    from . import metrics as mm
    cfg = cfg or st.load()
    outcomes = mm.post_outcomes(metrics, today)
    rows = by_item(outcomes)
    learned = update(rows, st.load_learned(), cfg, today)
    from .. import paths
    st.write_json(paths.learned_file(), learned)
    return report(rows, outcomes, learned, cfg, today, metrics.get("notes", [])), learned
