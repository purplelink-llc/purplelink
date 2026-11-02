"""Tests for the cost console parser, on synthetic transcripts only (tmp_path); nothing reads ~/.claude."""
import json
import os

import pytest

import build_page
import parse as P

NOW = "2026-11-02T20:00:00Z"  # 15:00 Eastern
PRICING = P.load_pricing()


def ts(day, hh="15:00"):
    return f"2026-{day}T{hh}:00.000Z"


def assistant(mid, when, model="claude-opus-5-5", out=100, inp=0, cr=0, cw5=0, cw1h=0, tools=(), speed="standard",
              stop="tool_use", split=True):
    usage = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
             "cache_creation_input_tokens": cw5 + cw1h, "speed": speed}
    if split:
        usage["cache_creation"] = {"ephemeral_5m_input_tokens": cw5, "ephemeral_1h_input_tokens": cw1h}
    content = [{"type": "tool_use", "id": f"{mid}-t{i}", "name": n, "input": {"command": c}} for i, (n, c) in enumerate(tools)]
    return {"type": "assistant", "timestamp": when, "cwd": "/Volumes/Extreme SSD/Purplelink LLC",
            "message": {"id": mid, "model": model, "usage": usage, "stop_reason": stop, "content": content or [{"type": "text", "text": "ok"}]}}


def user(when, origin, text="hi", entrypoint="claude-desktop"):
    return {"type": "user", "timestamp": when, "turnOrigin": origin, "entrypoint": entrypoint,
            "message": {"role": "user", "content": text}}


def write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for x in lines:
            fh.write((x if isinstance(x, str) else json.dumps(x, separators=(",", ":"))) + "\n")


def app_record(app_dir, local, cli, title, parent=None, prior=(), scheduled=None):
    d = {"sessionId": local, "cliSessionId": cli, "title": title, "priorCliSessionIds": list(prior),
         "cwd": "/Volumes/Extreme SSD/Purplelink LLC", "scheduledTaskId": scheduled}
    if parent:
        d["spawnedFrom"] = {"sessionId": parent}
    write(os.path.join(app_dir, "acct", "org", local + ".json"), [d])


@pytest.fixture
def dirs(tmp_path):
    projects, app = tmp_path / "projects", tmp_path / "app"
    projects.mkdir()
    app.mkdir()
    return str(projects), str(app)


def run(dirs, days=14, pricing=PRICING):
    return P.build(dirs[0], dirs[1], days, P.parse_ts(NOW), pricing)


def proj(dirs, name="-proj"):
    return os.path.join(dirs[0], name)


def session(data, title):
    return next(s for s in data["sessions"] if s["title"] == title)


# ---------- pricing ----------

def test_longest_prefix_wins():
    assert P.rate_for("claude-fable-5-1", PRICING)[0]["cache_read"] == 0.25
    assert P.rate_for("claude-fable-5", PRICING)[0]["cache_read"] == 1.00
    assert P.rate_for("claude-opus-5-5", PRICING)[0]["input"] == 4.00
    assert P.rate_for("claude-opus-5", PRICING)[0]["input"] == 5.00
    assert P.rate_for("claude-sonnet-4-6[1m]", PRICING)[0]["input"] == 3.00


def test_unknown_model_priced_at_top_rate():
    row, known = P.rate_for("claude-newthing-9", PRICING)
    assert not known and row["output"] == max(r["output"] for r in PRICING["models"].values())


def test_cache_write_ttls_priced_separately():
    row = PRICING["models"]["claude-opus-5-5"]
    c = P.turn_cost({"cache_creation_input_tokens": 2_000_000,
                     "cache_creation": {"ephemeral_5m_input_tokens": 1_000_000, "ephemeral_1h_input_tokens": 1_000_000}}, row, 2)
    assert c["cache_write"] == pytest.approx(5.00 + 8.00)


def test_missing_ttl_split_falls_back_to_5m():
    row = PRICING["models"]["claude-opus-5-5"]
    c = P.turn_cost({"cache_creation_input_tokens": 1_000_000}, row, 2)
    assert c["cache_write"] == pytest.approx(5.00)


def test_fast_mode_doubles():
    row = PRICING["models"]["claude-opus-5-5"]
    slow = P.turn_cost({"output_tokens": 1_000_000}, row, 2)["total"]
    fast = P.turn_cost({"output_tokens": 1_000_000, "speed": "fast"}, row, 2)["total"]
    assert slow == pytest.approx(20.0) and fast == pytest.approx(40.0)


# ---------- counting ----------

def test_multi_line_response_counted_once(dirs):
    a = assistant("m1", ts("11-02"), out=1_000_000)
    b = dict(a, message=dict(a["message"], content=[{"type": "text", "text": "second block"}]))
    write(os.path.join(proj(dirs), "s1.jsonl"), [user(ts("11-02", "14:59"), "human"), a, b, b])
    data = run(dirs)
    assert data["summary"]["total"] == pytest.approx(20.0)
    assert data["sessions"][0]["turns"] == 1


def test_usage_takes_per_field_max_across_lines(dirs):
    a = assistant("m1", ts("11-02"), out=10)
    b = assistant("m1", ts("11-02"), out=1_000_000)
    write(os.path.join(proj(dirs), "s1.jsonl"), [a, b])
    assert run(dirs)["summary"]["total"] == pytest.approx(20.0)


def test_fork_copy_counted_once_in_earliest_file(dirs):
    shared = assistant("m-shared", ts("11-01", "10:00"), out=1_000_000)
    write(os.path.join(proj(dirs), "orig.jsonl"), [shared])
    write(os.path.join(proj(dirs), "fork.jsonl"), [shared, assistant("m-new", ts("11-02"), out=1_000_000)])
    app_record(dirs[1], "local_a", "orig", "Original")
    app_record(dirs[1], "local_b", "fork", "Fork")
    data = run(dirs)
    assert data["summary"]["total"] == pytest.approx(40.0)
    assert session(data, "Original")["cost"] == pytest.approx(20.0)
    assert session(data, "Fork")["cost"] == pytest.approx(20.0)
    assert data["summary"]["copied_history_usd"] == pytest.approx(20.0)


def test_synthetic_and_malformed_lines_skipped(dirs):
    write(os.path.join(proj(dirs), "s1.jsonl"), [
        assistant("m0", ts("11-02"), model="<synthetic>", out=999),
        '{"type":"assistant","message": {broken',
        assistant("m1", ts("11-02"), out=1_000_000),
    ])
    assert run(dirs)["summary"]["total"] == pytest.approx(20.0)


def test_window_is_eastern_calendar_days(dirs):
    # 2026-10-20 03:30Z is 23:30 on 10-19 Eastern: outside a 14-day window ending 11-02
    write(os.path.join(proj(dirs), "s1.jsonl"), [
        assistant("old", "2026-10-20T03:30:00.000Z", out=1_000_000),
        assistant("in", "2026-10-20T04:30:00.000Z", out=1_000_000),
    ])
    data = run(dirs)
    assert data["summary"]["total"] == pytest.approx(20.0)
    assert list(data["daily"]) == ["2026-10-20"]


def test_day_bucket_uses_eastern_time(dirs):
    write(os.path.join(proj(dirs), "s1.jsonl"), [assistant("m1", "2026-11-02T03:00:00.000Z", out=1_000_000)])
    data = run(dirs)
    assert list(data["daily"]) == ["2026-11-01"]
    assert data["summary"]["yesterday"] == pytest.approx(20.0) and data["summary"]["today"] == 0


# ---------- sessions, titles, tree ----------

def test_subagents_and_prior_transcripts_roll_up(dirs):
    app_record(dirs[1], "local_p", "cur", "Parent work", prior=["older"])
    write(os.path.join(proj(dirs), "older.jsonl"), [assistant("a", ts("11-01"), out=1_000_000)])
    write(os.path.join(proj(dirs), "cur.jsonl"), [assistant("b", ts("11-02"), out=1_000_000)])
    sub = os.path.join(proj(dirs), "cur", "subagents", "agent-x1.jsonl")
    write(sub, [assistant("c", ts("11-02"), model="claude-sonnet-5-5", out=1_000_000)])
    write(sub[:-6] + ".meta.json", [{"description": "Research ad credits", "model": "sonnet"}])
    data = run(dirs)
    s = session(data, "Parent work")
    assert s["cost"] == pytest.approx(50.0) and s["sub_cost"] == pytest.approx(10.0)
    assert s["transcripts"] == 2
    assert {t["sub"] for t in data["replays"]["local_p"]["turns"]} == {None, "Research ad credits"}
    assert s["by_origin"]["subagent"] == pytest.approx(10.0)


def test_title_fallbacks(dirs):
    write(os.path.join(proj(dirs), "t1.jsonl"), [{"type": "custom-title", "customTitle": "Old"},
                                                 {"type": "custom-title", "customTitle": "Renamed"},
                                                 assistant("a", ts("11-02"))])
    write(os.path.join(proj(dirs), "t2.jsonl"), [user(ts("11-02", "14:00"), "sdk", "<system-reminder>x</system-reminder>Run the nightly sim", "sdk-cli"),
                                                 assistant("b", ts("11-02"))])
    write(os.path.join(proj(dirs), "t3abcdef99.jsonl"), [assistant("c", ts("11-02"))])
    titles = {s["title"] for s in run(dirs)["sessions"]}
    assert titles == {"Renamed", "“Run the nightly sim”", "untitled t3abcdef"}


def test_spawn_tree_keeps_idle_parent_as_stub(dirs):
    app_record(dirs[1], "local_root", "root-cli", "Orchestrator")
    app_record(dirs[1], "local_kid", "kid-cli", "Side task", parent="local_root")
    write(os.path.join(proj(dirs), "kid-cli.jsonl"), [assistant("a", ts("11-02"), out=1_000_000)])
    tree = {n["key"]: n for n in run(dirs)["tree"]}
    assert tree["local_kid"]["parent"] == "local_root"
    assert tree["local_root"]["cost"] == 0.0 and tree["local_root"]["title"] == "Orchestrator"


def test_spawn_cycle_does_not_hang(dirs):
    app_record(dirs[1], "local_a", "a-cli", "A", parent="local_b")
    app_record(dirs[1], "local_b", "b-cli", "B", parent="local_a")
    write(os.path.join(proj(dirs), "a-cli.jsonl"), [assistant("a", ts("11-02"))])
    assert {n["key"] for n in run(dirs)["tree"]} == {"local_a", "local_b"}


def test_scheduled_tasks_grouped(dirs):
    for i in range(3):
        app_record(dirs[1], f"local_r{i}", f"r{i}", "Daily update", scheduled="daily-update")
        write(os.path.join(proj(dirs), f"r{i}.jsonl"), [assistant(f"m{i}", ts("11-02"), out=1_000_000)])
    assert run(dirs)["scheduled"] == [{"task": "daily-update", "runs": 3, "cost": pytest.approx(60.0)}]


# ---------- origins ----------

@pytest.mark.parametrize("origin,text,entry,expected", [
    ("human", "fix the bug", "claude-desktop", "human"),
    ("peer", "Another Claude session sent a message", "claude-desktop", "peer"),
    ("sdk", "<cross-session-message from=\"local_x\">do it", "claude-desktop", "peer"),
    ("sdk", "<side-sessions-event>None of the sessions", "claude-desktop", "side_session_event"),
    ("sdk", "<ci-monitor-event>checks passed", "claude-desktop", "ci_event"),
    ("sdk", "Below is a conversation log from a Claude Code coding session.", "sdk-cli", "compaction"),
    ("sdk", "This session is being continued from a previous conversation that ran out", "claude-desktop", "after_compaction"),
    ("sdk", "Your complete instructions are in the file", "sdk-cli", "headless"),
    ("sdk", "something new", "claude-desktop", "app_other"),
])
def test_origin_classification(dirs, origin, text, entry, expected):
    write(os.path.join(proj(dirs), "o.jsonl"), [user(ts("11-02", "14:00"), origin, text, entry), assistant("a", ts("11-02"))])
    assert set(run(dirs)["sessions"][0]["by_origin"]) == {expected}


def test_origin_carries_over_tool_result_lines(dirs):
    write(os.path.join(proj(dirs), "o.jsonl"), [
        user(ts("11-02", "14:00"), "scheduled", "<scheduled-task name=x>"),
        assistant("a", ts("11-02", "14:01"), tools=[("Bash", "ls")]),
        {"type": "user", "timestamp": ts("11-02", "14:02"), "message": {"content": [{"type": "tool_result", "tool_use_id": "a-t0", "is_error": True, "content": "boom"}]}},
        assistant("b", ts("11-02", "14:03")),
    ])
    s = run(dirs)["sessions"][0]
    assert set(s["by_origin"]) == {"scheduled"} and s["errors"] == 1


# ---------- flags ----------

def tiny_run(n, out=50, tools=()):
    return [assistant(f"t{i}", f"2026-11-02T14:{i:02d}:00.000Z", out=out, tools=tools) for i in range(n)]


def test_loop_flag_fires_at_threshold(dirs):
    write(os.path.join(proj(dirs), "l.jsonl"), tiny_run(30))
    assert run(dirs)["sessions"][0]["flags"]["loop"]["episodes"] == 1


def test_loop_flag_quiet_below_threshold_or_with_real_output(dirs):
    write(os.path.join(proj(dirs), "l1.jsonl"), tiny_run(29))
    lines = tiny_run(30)
    lines[15] = assistant("big", "2026-11-02T14:15:00.000Z", out=5000)
    write(os.path.join(proj(dirs), "l2.jsonl"), lines)
    assert all("loop" not in s["flags"] for s in run(dirs)["sessions"])


def test_repeat_flag(dirs):
    write(os.path.join(proj(dirs), "r1.jsonl"), tiny_run(5, out=500, tools=[("Bash", "sleep 60; gh pr checks 5")]))
    write(os.path.join(proj(dirs), "r2.jsonl"), [assistant(f"x{i}", f"2026-11-02T14:{i:02d}:00.000Z", out=500, tools=[("Bash", "sleep 60")]) for i in range(4)])
    flags = {s["key"]: s["flags"] for s in run(dirs)["sessions"]}
    assert flags["cli:r1"]["repeat"] == 5 and "repeat" not in flags["cli:r2"]


def test_fable_flag(dirs):
    write(os.path.join(proj(dirs), "f.jsonl"), [assistant("a", ts("11-02"), model="claude-fable-5-1", out=1_000_000)])
    assert run(dirs)["sessions"][0]["flags"]["fable"] == {"turns": 1, "cost": 50.0}


def test_over_day_flag_is_strictly_greater(dirs):
    write(os.path.join(proj(dirs), "a.jsonl"), [assistant("a", ts("11-02"), out=2_500_000)])  # exactly $50
    write(os.path.join(proj(dirs), "b.jsonl"), [assistant("b", ts("11-02"), out=2_600_000)])
    flags = {s["key"]: s["flags"] for s in run(dirs)["sessions"]}
    assert "over_day" not in flags["cli:a"] and flags["cli:b"]["over_day"] == {"2026-11-02": 52.0}


def test_pinged_flag(dirs):
    write(os.path.join(proj(dirs), "p.jsonl"), [
        user(ts("11-02", "10:00"), "human"), assistant("a", ts("11-02", "10:01"), out=50_000),
        user(ts("11-02", "11:00"), "sdk", "<side-sessions-event>idle"), assistant("b", ts("11-02", "11:01"), out=100_000),
    ])
    assert run(dirs)["sessions"][0]["flags"]["pinged"] == {"cost": 2.0, "share": 0.67}


# ---------- privacy and output ----------

def test_secrets_redacted_before_truncation():
    secret = "sk-ant-" + "A1b2C3d4" * 6
    assert "A1b2" not in P.clip("curl -H 'x-api-key: " + secret + "' https://api", 40)
    assert "ghp_" not in P.clip("export GITHUB_TOKEN=ghp_" + "x1" * 18)
    assert P.clip("cat scripts/cost_console/parse.py") == "cat scripts/cost_console/parse.py"


def test_replay_cap(dirs):
    write(os.path.join(proj(dirs), "big.jsonl"), [assistant(f"m{i}", f"2026-11-02T{10 + i // 60:02d}:{i % 60:02d}:00.000Z", out=500) for i in range(250)])
    r = run(dirs)["replays"]["cli:big"]
    assert r["omitted"] == 250 - P.REPLAY_HEAD - P.REPLAY_TAIL and len(r["turns"]) == P.REPLAY_HEAD + P.REPLAY_TAIL


def test_page_escapes_script_close(dirs):
    write(os.path.join(proj(dirs), "x.jsonl"), [{"type": "custom-title", "customTitle": "</script><b>hi"}, assistant("a", ts("11-02"))])
    html = build_page.render(run(dirs))
    assert html.count("</script>") == 2 and "<\\/script><b>hi" in html


def test_write_private_sets_modes(tmp_path):
    out = tmp_path / "cc" / "data.json"
    P.write_private({"a": 1}, str(out))
    assert oct(os.stat(out).st_mode & 0o777) == "0o600" and oct(os.stat(out.parent).st_mode & 0o777) == "0o700"
