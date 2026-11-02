#!/usr/bin/env python3
"""Cost console: API-equivalent cost of every Claude Code session, from the transcripts already on disk.
See docs/designs/cost-console.md.

Read-only over ~/.claude/projects and the desktop app's session records; it never writes, moves or deletes
anything there. Writes one JSON file (default ~/.purplelink/cost-console/data.json, folder mode 0700). Stdlib only.

  parse.py [--days 14] [--out PATH] [--projects DIR] [--app-sessions DIR] [--ecc-costs FILE] [--now ISO]
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
EASTERN = ZoneInfo("America/New_York")
HOME = os.path.expanduser("~")
DEFAULT_PROJECTS = os.path.join(HOME, ".claude", "projects")
DEFAULT_APP = os.path.join(HOME, "Library", "Application Support", "Claude", "claude-code-sessions")
DEFAULT_ECC = os.path.join(HOME, ".claude", "metrics", "costs.jsonl")
DEFAULT_OUT = os.path.join(HOME, ".purplelink", "cost-console", "data.json")

# Turns another session or the app started, not Ben and not the session's own background work finishing.
IDLE_ORIGINS = {"peer", "side_session_event", "ci_event", "system"}
SDK_PREFIXES = (  # Claude Code tags everything the desktop app injects as turnOrigin "sdk"; the text says what it was
    ("<side-sessions-event>", "side_session_event"),
    ("<cross-session-message", "peer"),
    ("<ci-monitor-event>", "ci_event"),
    ("The app was quit while you were working", "app_resume"),
    ("Task (from the session that started this one)", "side_session_task"),
    ("Background (from the session that started this one)", "side_session_task"),
)
COMPACTION_PREFIXES = ("Below is a conversation log", "Your task is to create a detailed summary")
CONTINUED_PREFIX = "This session is being continued from a previous conversation"
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
REPLAY_TOP = 25
REPLAY_HEAD, REPLAY_TAIL = 60, 140
REPLAY_TOOLS, REPLAY_CLIP = 4, 120
CLIP = 160
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]+-----|Bearer\s+[A-Za-z0-9._\-]{16,}"
    r"|(?i:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+"
    r"|\b(?=[A-Za-z_\-]*\d)(?=[0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{40,})")  # long mixed letter-digit runs: likely keys


# ---------- pricing ----------

def load_pricing(path=None):
    with open(path or os.path.join(HERE, "pricing.json")) as fh:
        return json.load(fh)


def rate_for(model, pricing):
    """Longest-prefix match on the model id. Unknown models get the most expensive row, so a gap over-reports."""
    models = pricing["models"]
    best = None
    for prefix in models:
        if model.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    if best:
        return models[best], True
    return max(models.values(), key=lambda r: r["output"]), False


def turn_cost(u, row, fast_mult):
    """Dollar cost of one API response, split by token kind."""
    cc = u.get("cache_creation") or {}
    cw_total = u.get("cache_creation_input_tokens", 0) or 0
    cw1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    cw5m = cc.get("ephemeral_5m_input_tokens", 0) or 0
    if cw1h + cw5m != cw_total:  # split missing or partial: the remainder is priced as 5-minute writes
        cw5m = max(cw_total - cw1h, 0)
    mult = fast_mult if u.get("speed") == "fast" else 1.0
    m = 1e-6 * mult
    parts = {
        "input": (u.get("input_tokens", 0) or 0) * row["input"] * m,
        "output": (u.get("output_tokens", 0) or 0) * row["output"] * m,
        "cache_read": (u.get("cache_read_input_tokens", 0) or 0) * row["cache_read"] * m,
        "cache_write": (cw5m * row["cache_write_5m"] + cw1h * row["cache_write_1h"]) * m,
    }
    parts["total"] = sum(parts.values())
    return parts


# ---------- text helpers ----------

def redact(s):
    return SECRET_RE.sub("[redacted]", s)


def clip(s, n=CLIP):
    """Redact first, then truncate, so a secret cut in half cannot escape the pattern."""
    s = redact(" ".join(str(s).split()))
    return s if len(s) <= n else s[: n - 1] + "…"


def tool_input_text(name, inp):
    if not isinstance(inp, dict):
        return str(inp)
    for key in ("command", "file_path", "pattern", "url", "query", "description", "prompt", "skill"):
        if key in inp and isinstance(inp[key], str):
            return inp[key]
    return json.dumps(inp, sort_keys=True)


def prompt_text(content):
    """The words of a user message, without system reminders."""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return ""
    return REMINDER_RE.sub(" ", content).strip()


def classify_origin(turn_origin, text, entrypoint=None):
    """turnOrigin as written by Claude Code, with its catch-all "sdk" split into what actually happened."""
    if turn_origin != "sdk":
        return turn_origin
    if text.startswith(COMPACTION_PREFIXES):
        return "compaction"
    if text.startswith(CONTINUED_PREFIX):
        return "after_compaction"
    for prefix, origin in SDK_PREFIXES:
        if text.startswith(prefix):
            return origin
    return "headless" if entrypoint == "sdk-cli" else "app_other"


def parse_ts(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def eastern_date(ts):
    return dt.datetime.fromtimestamp(ts, EASTERN).date()


def short_project(cwd):
    if not cwd:
        return "?"
    if "/_worktrees/" in cwd:
        return cwd.split("/_worktrees/", 1)[1].split("/")[0] + " (wt)"
    if "/.claude/worktrees/" in cwd:
        return os.path.basename(cwd.split("/.claude/worktrees/", 1)[0]) + " (wt)"
    return os.path.basename(cwd.rstrip("/")) or cwd


# ---------- sources ----------

def load_app_sessions(app_dir):
    """cli session id -> app record. One app session can own several transcripts (resumes, context resets)."""
    by_cli = {}
    records = {}
    for f in glob.glob(os.path.join(app_dir, "*", "*", "local_*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        sid = d.get("sessionId")
        if not sid:
            continue
        rec = {
            "key": sid,
            "title": d.get("title"),
            "parent": (d.get("spawnedFrom") or {}).get("sessionId"),
            "scheduled": d.get("scheduledTaskId"),
            "archived": bool(d.get("isArchived")),
            "cwd": d.get("cwd") or d.get("originCwd"),
        }
        records[sid] = rec
        for cli in [d.get("cliSessionId")] + list(d.get("priorCliSessionIds") or []):
            if cli:
                by_cli[cli] = rec
    return by_cli, records


def list_transcripts(projects_dir, since_ts):
    """(path, cli_session_id, subagent_id) for every transcript modified since since_ts."""
    out = []
    for path in glob.glob(os.path.join(projects_dir, "*", "*.jsonl")):
        if os.path.getmtime(path) >= since_ts:
            out.append((path, os.path.basename(path)[:-6], None))
    for path in glob.glob(os.path.join(projects_dir, "*", "*", "subagents", "agent-*.jsonl")):
        if os.path.getmtime(path) >= since_ts:
            parent = os.path.basename(os.path.dirname(os.path.dirname(path)))
            out.append((path, parent, os.path.basename(path)[6:-6]))
    return out


def first_timestamp(path):
    with open(path, "rb") as fh:
        for i, line in enumerate(fh):
            if i > 200:
                break
            m = re.search(rb'"timestamp":"([^"]+)"', line)
            if m:
                ts = parse_ts(m.group(1).decode())
                if ts:
                    return ts
    return float("inf")


def subagent_meta(path):
    try:
        with open(path[:-6] + ".meta.json") as fh:
            m = json.load(fh)
        return clip(m.get("description") or m.get("agentType") or "subagent", 60)
    except (OSError, ValueError):
        return "subagent"


def scan_file(path, is_subagent):
    """One dict per API response in this file, in file order, plus file-level facts.

    Lines of one response share message.id; usage is taken as the per-field maximum across them.
    """
    turns = {}
    order = []
    by_tool_use = {}
    origin = "subagent" if is_subagent else "unknown"
    facts = {"titles": [], "cwd": None, "agent_name": None, "first_prompt": None}
    with open(path, "rb") as fh:
        for raw in fh:
            if b'"type":"assistant"' in raw:
                pass
            elif b'"type":"user"' in raw:
                if b'"turnOrigin"' not in raw and b'"is_error":true' not in raw:
                    continue
            elif b'"type":"custom-title"' not in raw and b'"type":"agent-name"' not in raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue  # a partial last line while the session is still writing, or a damaged line
            t = d.get("type")
            if t == "custom-title" and d.get("customTitle"):
                facts["titles"].append(d["customTitle"])
                continue
            if t == "agent-name" and d.get("agentName"):
                facts["agent_name"] = d["agentName"]
                continue
            if facts["cwd"] is None and d.get("cwd"):
                facts["cwd"] = d["cwd"]
            msg = d.get("message") or {}
            if t == "user":
                content = msg.get("content")
                if d.get("turnOrigin") and not is_subagent:
                    text = prompt_text(content)
                    origin = classify_origin(d["turnOrigin"], text, d.get("entrypoint"))
                    if facts["first_prompt"] is None and text and origin in ("human", "headless", "scheduled", "side_session_task"):
                        facts["first_prompt"] = text
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                            mid = by_tool_use.get(block.get("tool_use_id"))
                            if mid in turns:
                                turns[mid]["errors"] += 1
                continue
            if t != "assistant":
                continue
            model = msg.get("model") or ""
            mid = msg.get("id")
            if not mid or model == "<synthetic>":
                continue
            ts = parse_ts(d.get("timestamp", ""))
            if ts is None:
                continue
            turn = turns.get(mid)
            if turn is None:
                turn = turns[mid] = {"id": mid, "ts": ts, "model": model, "usage": {}, "origin": origin,
                                     "tools": [], "sigs": [], "errors": 0, "stop": None}
                order.append(mid)
            for k, v in (msg.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    turn["usage"][k] = max(turn["usage"].get(k, 0), v)
                elif k == "cache_creation" and isinstance(v, dict):
                    cc = turn["usage"].setdefault("cache_creation", {})
                    for kk, vv in v.items():
                        if isinstance(vv, (int, float)):
                            cc[kk] = max(cc.get(kk, 0), vv)
                elif k == "speed":
                    turn["usage"]["speed"] = v
            if msg.get("stop_reason"):
                turn["stop"] = msg["stop_reason"]
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    text = tool_input_text(name, block.get("input"))
                    turn["tools"].append([name, clip(text)])
                    turn["sigs"].append(name + ":" + hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12])
                    by_tool_use[block.get("id")] = mid
    return [turns[m] for m in order], facts


# ---------- flags ----------

def loop_episodes(turns, th):
    """Runs of tiny-output turns: at least loop_min_turns consecutive turns, each under loop_max_output_tokens,
    with the first and last of some such stretch within loop_window_minutes. Returns (episodes, their cost)."""
    n, max_out, window = th["loop_min_turns"], th["loop_max_output_tokens"], th["loop_window_minutes"] * 60
    episodes, cost = 0, 0.0
    run = []

    def close(run):
        nonlocal episodes, cost
        if len(run) < n:
            return
        hit = set()
        j = 0
        for i in range(len(run)):
            while run[i]["ts"] - run[j]["ts"] > window:
                j += 1
            if i - j + 1 >= n:
                hit.update(range(j, i + 1))
        if hit:
            episodes += 1
            cost += sum(run[k]["cost"]["total"] for k in hit)

    for t in turns:
        if (t["usage"].get("output_tokens", 0) or 0) < max_out:
            run.append(t)
        else:
            close(run)
            run = []
    close(run)
    return episodes, cost


def repeat_runs(turns, th):
    """Longest run of consecutive turns making the identical, non-empty set of tool calls (compared on the
    full input, before truncation), if it reaches repeat_tool_calls; else 0."""
    best, cur, prev = 0, 0, None
    for t in turns:
        sig = tuple(t["sigs"])
        if sig and sig == prev:
            cur += 1
        else:
            cur = 1 if sig else 0
        prev = sig
        best = max(best, cur)
    return best if best >= th["repeat_tool_calls"] else 0


# ---------- main ----------

def window_bounds(now_ts, days):
    """The window is `days` whole US Eastern calendar days ending today (today partial), by turn timestamp."""
    today = eastern_date(now_ts)
    start_day = today - dt.timedelta(days=days - 1)
    start = dt.datetime.combine(start_day, dt.time(0), EASTERN).timestamp()
    return start, today


def session_row(s, pricing, th):
    turns = s["sorted"]
    cost = sum(t["cost"]["total"] for t in turns)
    by_model, by_origin, per_day = {}, {}, {}
    tok = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    kinds = dict.fromkeys(tok, 0.0)
    ctx = []
    for t in turns:
        c = t["cost"]["total"]
        for k in kinds:
            kinds[k] += t["cost"][k]
        short = t["model"].replace("claude-", "")
        by_model[short] = by_model.get(short, 0) + c
        by_origin[t["origin"]] = by_origin.get(t["origin"], 0) + c
        day = eastern_date(t["ts"]).isoformat()
        per_day[day] = per_day.get(day, 0) + c
        u = t["usage"]
        tok["input"] += u.get("input_tokens", 0) or 0
        tok["output"] += u.get("output_tokens", 0) or 0
        tok["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        tok["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
        if t["sub"] is None:
            ctx.append((u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0)
                       + (u.get("cache_creation_input_tokens", 0) or 0))
    ctx.sort()

    flags = {}
    over = {d: round(c, 2) for d, c in per_day.items() if c > th["session_day_usd"]}
    if over:
        flags["over_day"] = over
    ep_cost, episodes, repeat = 0.0, 0, 0
    for f in sorted({t["file"] for t in turns}):
        ft = [t for t in turns if t["file"] == f]
        e, c = loop_episodes(ft, th)
        episodes += e
        ep_cost += c
        repeat = max(repeat, repeat_runs(ft, th))
    if episodes:
        flags["loop"] = {"episodes": episodes, "cost": round(ep_cost, 2)}
    if repeat:
        flags["repeat"] = repeat
    fable = [t for t in turns if t["model"].startswith(("claude-fable", "claude-mythos"))]
    if fable:
        flags["fable"] = {"turns": len(fable), "cost": round(sum(t["cost"]["total"] for t in fable), 2)}
    idle = sum(c for o, c in by_origin.items() if o in IDLE_ORIGINS)
    if cost > 0 and idle / cost > th["pinged_share"] and idle >= th["pinged_min_usd"]:
        flags["pinged"] = {"cost": round(idle, 2), "share": round(idle / cost, 2)}
    unknown = sorted({t["model"] for t in turns if not rate_for(t["model"], pricing)[1]})
    if unknown:
        flags["unknown_model"] = unknown

    title = s["title"] or (s["titles"][-1] if s["titles"] else None) or s["agent_name"] \
        or (s["first_prompt"] and "\u201c" + clip(s["first_prompt"], 70) + "\u201d") \
        or "untitled " + s["key"].replace("cli:", "").replace("local_", "")[:8]
    return {
        "key": s["key"], "title": clip(title, 90), "project": short_project(s["cwd"]),
        "parent": s["parent"], "scheduled": s["scheduled"], "archived": s["archived"],
        "cost": round(cost, 4), "sub_cost": round(sum(t["cost"]["total"] for t in turns if t["sub"]), 4),
        "turns": len(turns), "sub_turns": sum(1 for t in turns if t["sub"]),
        "tokens": tok, "by_kind": {k: round(v, 4) for k, v in kinds.items()},
        "ctx_median": ctx[len(ctx) // 2] if ctx else 0, "ctx_p90": ctx[int(len(ctx) * 0.9)] if ctx else 0,
        "by_model": {k: round(v, 4) for k, v in by_model.items()},
        "by_origin": {k: round(v, 4) for k, v in by_origin.items()},
        "per_day": {k: round(v, 4) for k, v in per_day.items()},
        "first": turns[0]["ts"], "last": turns[-1]["ts"], "transcripts": len(s["transcripts"]),
        "errors": sum(t["errors"] for t in turns), "flags": flags,
    }


def replay(turns):
    omitted = 0
    if len(turns) > REPLAY_HEAD + REPLAY_TAIL:
        omitted = len(turns) - REPLAY_HEAD - REPLAY_TAIL
        turns = turns[:REPLAY_HEAD] + turns[-REPLAY_TAIL:]
    return {"omitted": omitted, "head": REPLAY_HEAD if omitted else len(turns), "turns": [{
        "t": round(t["ts"]), "o": t["origin"], "m": t["model"].replace("claude-", ""),
        "in": t["usage"].get("input_tokens", 0), "out": t["usage"].get("output_tokens", 0),
        "cr": t["usage"].get("cache_read_input_tokens", 0), "cw": t["usage"].get("cache_creation_input_tokens", 0),
        "c": round(t["cost"]["total"], 5), "tools": [[n, clip(x, REPLAY_CLIP)] for n, x in t["tools"][:REPLAY_TOOLS]],
        "more": max(len(t["tools"]) - REPLAY_TOOLS, 0), "err": t["errors"],
        "stop": t["stop"] if t["stop"] in ("max_tokens", "refusal", "pause_turn") else None, "sub": t["sub"],
    } for t in turns]}


def build(projects_dir, app_dir, days, now_ts, pricing, ecc_path=None):
    th = pricing["thresholds"]
    fast = pricing.get("fast_multiplier", 2.0)
    start_ts, today = window_bounds(now_ts, days)
    by_cli, app_records = load_app_sessions(app_dir)
    files = list_transcripts(projects_dir, start_ts - 86400)
    # Earliest file first: a fork or resume copies earlier responses, and the file that had them first owns them.
    # Copied lines keep their timestamps, so a fork can start at the same instant; the file created first wins then.
    def order(f):
        st = os.stat(f[0])
        return first_timestamp(f[0]), getattr(st, "st_birthtime", st.st_mtime), f[0]
    files.sort(key=order)

    seen = set()
    file_local = {}  # main transcript -> (first turn ts, cost of all its turns before cross-file dedupe)
    sessions = {}
    unknown_models = set()
    scanned_bytes = 0
    t0 = time.time()
    for path, cli, sub in files:
        scanned_bytes += os.path.getsize(path)
        turns, facts = scan_file(path, sub is not None)
        rec = by_cli.get(cli)
        key = rec["key"] if rec else "cli:" + cli
        s = sessions.get(key)
        if s is None:
            s = sessions[key] = {
                "key": key, "title": rec["title"] if rec else None, "titles": [], "agent_name": None,
                "cwd": rec["cwd"] if rec else None, "parent": rec["parent"] if rec else None,
                "scheduled": rec["scheduled"] if rec else None, "archived": rec["archived"] if rec else False,
                "transcripts": set(), "turns": [], "first_prompt": None,
            }
        s["transcripts"].add(cli)
        if sub is None:
            s["first_prompt"] = s["first_prompt"] or facts["first_prompt"]
            s["titles"] += facts["titles"]
            s["agent_name"] = s["agent_name"] or facts["agent_name"]
            s["cwd"] = s["cwd"] or facts["cwd"]
        label = subagent_meta(path) if sub else None
        if sub is None and turns:
            local = 0.0
            for t in turns:
                if start_ts <= t["ts"] <= now_ts:
                    local += turn_cost(t["usage"], rate_for(t["model"], pricing)[0], fast)["total"]
            file_local[cli] = (turns[0]["ts"], local)
        for t in turns:
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            if not start_ts <= t["ts"] <= now_ts:
                continue
            row, known = rate_for(t["model"], pricing)
            if not known:
                unknown_models.add(t["model"])
            t["cost"] = turn_cost(t["usage"], row, fast)
            t["sub"] = label
            t["file"] = path
            s["turns"].append(t)

    sessions = {k: s for k, s in sessions.items() if s["turns"]}
    daily = {}
    totals = {"by_model": {}, "by_origin": {}, "by_kind": dict.fromkeys(("input", "output", "cache_read", "cache_write"), 0.0),
              "tokens_by_model": {}}
    rows = []
    for s in sessions.values():
        s["sorted"] = sorted(s["turns"], key=lambda t: t["ts"])
        rows.append(session_row(s, pricing, th))
        for t in s["sorted"]:
            c = t["cost"]["total"]
            short = t["model"].replace("claude-", "")
            day = daily.setdefault(eastern_date(t["ts"]).isoformat(), {})
            day[short] = day.get(short, 0) + c
            totals["by_model"][short] = totals["by_model"].get(short, 0) + c
            totals["by_origin"][t["origin"]] = totals["by_origin"].get(t["origin"], 0) + c
            for k in totals["by_kind"]:
                totals["by_kind"][k] += t["cost"][k]
            tm = totals["tokens_by_model"].setdefault(short, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "turns": 0})
            u = t["usage"]
            tm["input"] += u.get("input_tokens", 0) or 0
            tm["output"] += u.get("output_tokens", 0) or 0
            tm["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            tm["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
            tm["turns"] += 1
    rows.sort(key=lambda r: -r["cost"])

    # Replays: the top sessions by cost, plus every flagged one (loops and Fable calls are often cheap).
    keys = [r["key"] for r in rows[:REPLAY_TOP]]
    keys += [r["key"] for r in rows[REPLAY_TOP:] if r["flags"]]
    replays = {k: replay(sessions[k]["sorted"]) for k in keys}

    # Spawn tree: parents with no turns in the window still appear, as zero-cost stubs. Cycles are cut by `seen`.
    tree = {r["key"]: {"key": r["key"], "title": r["title"], "cost": r["cost"], "parent": r["parent"]} for r in rows}
    for node in list(tree.values()):
        p, guard = node["parent"], set()
        while p and p not in tree and p in app_records and p not in guard:
            guard.add(p)
            rec = app_records[p]
            tree[p] = {"key": p, "title": clip(rec["title"] or p, 90), "cost": 0.0, "parent": rec["parent"]}
            p = rec["parent"]
    for node in tree.values():
        if node["parent"] not in tree:
            node["parent"] = None

    scheduled = {}
    for r in rows:
        if r["scheduled"]:
            g = scheduled.setdefault(r["scheduled"], {"task": r["scheduled"], "runs": 0, "cost": 0.0})
            g["runs"] += 1
            g["cost"] = round(g["cost"] + r["cost"], 4)

    def day_total(d):
        return sum(daily.get(d.isoformat(), {}).values())

    week = [day_total(today - dt.timedelta(days=i)) for i in range(1, 8)]
    age = (today - dt.date.fromisoformat(pricing["_checked"])).days
    data = {
        "generated": now_ts, "window_start": start_ts, "days": days, "today": today.isoformat(),
        "pricing": {"source": pricing["_source"], "checked": pricing["_checked"],
                    "stale": age > pricing.get("stale_after_days", 45), "note": pricing["_note"],
                    "models": pricing["models"], "thresholds": th},
        "summary": {
            "total": round(sum(r["cost"] for r in rows), 2), "today": round(day_total(today), 2),
            "yesterday": round(day_total(today - dt.timedelta(days=1)), 2), "avg7": round(sum(week) / 7, 2),
            "by_model": {k: round(v, 2) for k, v in sorted(totals["by_model"].items(), key=lambda kv: -kv[1])},
            "by_origin": {k: round(v, 2) for k, v in sorted(totals["by_origin"].items(), key=lambda kv: -kv[1])},
            "by_kind": {k: round(v, 2) for k, v in totals["by_kind"].items()},
            "tokens_by_model": totals["tokens_by_model"],
            "sessions": len(rows), "unknown_models": sorted(unknown_models),
        },
        "daily": {d: {m: round(c, 4) for m, c in v.items()} for d, v in sorted(daily.items())},
        "sessions": rows, "tree": list(tree.values()),
        "scheduled": sorted(scheduled.values(), key=lambda g: -g["cost"]),
        "replays": replays,
        "scan": {"files": len(files), "bytes": scanned_bytes, "seconds": round(time.time() - t0, 1)},
    }
    if ecc_path:
        data["crosscheck"] = crosscheck(ecc_path, file_local, start_ts)
    data["summary"]["copied_history_usd"] = round(sum(c for _, c in file_local.values()) + sum(
        r["sub_cost"] for r in rows) - data["summary"]["total"], 2)
    return data


def crosscheck(ecc_path, file_local, start_ts):
    """Compare with ECC's stop:cost-tracker estimate, transcript by transcript, before cross-file dedupe (ECC
    counts history a fork copied in again). Only transcripts whose first turn is a full day inside the window
    count, since ECC's figure covers the whole transcript. ECC prices 1-hour cache writes at the 5-minute rate,
    so a ratio a little above 1 is expected; one far from that means a side is miscounting."""
    if not os.path.exists(ecc_path):
        return None
    latest = {}
    with open(ecc_path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            sid = r.get("session_id")
            if sid and str(r.get("timestamp", "")) >= str(latest.get(sid, {}).get("timestamp", "")):
                latest[sid] = r
    ours = theirs = 0.0
    n = 0
    for cli, (first, cost) in file_local.items():
        if cli in latest and first >= start_ts + 86400:
            ours += cost
            theirs += float(latest[cli].get("estimated_cost_usd") or 0)
            n += 1
    return {"transcripts": n, "ours": round(ours, 2), "ecc": round(theirs, 2),
            "ratio": round(ours / theirs, 3) if theirs else None}


def write_private(data, out):
    folder = os.path.dirname(out)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    tmp = out + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    os.replace(tmp, out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--projects", default=DEFAULT_PROJECTS)
    ap.add_argument("--app-sessions", default=DEFAULT_APP)
    ap.add_argument("--ecc-costs", default=DEFAULT_ECC)
    ap.add_argument("--pricing", default=None)
    ap.add_argument("--now", default=None, help="ISO time to treat as now (tests)")
    a = ap.parse_args(argv)
    now_ts = parse_ts(a.now) if a.now else time.time()
    data = build(a.projects, a.app_sessions, a.days, now_ts, load_pricing(a.pricing), a.ecc_costs)
    write_private(data, a.out)
    s, sc, cc = data["summary"], data["scan"], data.get("crosscheck")
    print(f"cost console: {s['sessions']} sessions, ${s['total']:,.2f} API-equivalent over {a.days} days "
          f"(today ${s['today']:,.2f}); scanned {sc['files']} files, {sc['bytes'] / 1e9:.1f} GB in {sc['seconds']} s")
    if cc and cc["ratio"]:
        print(f"cross-check vs ECC cost tracker: ours ${cc['ours']:,.2f} vs ECC ${cc['ecc']:,.2f} over "
              f"{cc['transcripts']} transcripts (ratio {cc['ratio']})")
    if s["unknown_models"]:
        print("unknown models priced at the top rate: " + ", ".join(s["unknown_models"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
