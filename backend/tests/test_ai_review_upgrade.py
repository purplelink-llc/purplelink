"""Offline tests for the AI-review upgrade: request shape, prompt caching, parsing, retries, ceilings.

No test here reaches an API: every model call goes through a fake httpx-like client that records the JSON
body it was sent, so the tests pin what is sent (model, max_tokens, cache_control placement, system prompt)
and how replies are read (good, malformed, cut off).

Prompt snapshots live in tests/fixtures/prompt_snapshots/. A change to any prompt shows up as a diff there.
After an intended prompt edit, regenerate them with
    UPDATE_PROMPT_SNAPSHOTS=1 pytest tests/test_ai_review_upgrade.py -k snapshot
and review the diff in the PR.
"""
import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from latextools import papercheck as p
from latextools import paperreview_extras as pre

SNAP_DIR = Path(__file__).parent / "fixtures" / "prompt_snapshots"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else _payload("ok")
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def _payload(text, *, stop="end_turn", inp=100, out=50, cw=0, cr=0):
    return {
        "content": [{"type": "text", "text": text}] if text else [],
        "stop_reason": stop,
        "usage": {"input_tokens": inp, "output_tokens": out,
                  "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr},
    }


class _Client:
    """Records every request body; `handler(body, n)` returns a _Resp or raises."""

    def __init__(self, handler):
        self.handler = handler
        self.bodies = []

    async def post(self, url, json=None, headers=None):
        self.bodies.append(json)
        out = self.handler(json, len(self.bodies))
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    async def _fast(_):
        return None
    monkeypatch.setattr("asyncio.sleep", _fast)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")


def _structure(body="Body sentence one. We measured accuracy of 91.2 percent on the held-out set."):
    return p.PaperStructure(
        title="A Fixed Test Paper",
        abstract="We study a thing and report a number.",
        body=body,
        page_count=4,
        figures=[p.PaperFigure(label="Figure 1", caption="The thing.", page=2)],
        references=[p.PaperReference(raw="Smith 2020")],
        n_references_total=1,
    )


FINDING = {"category": "stats", "severity": "major", "claim_quoted": "accuracy of 91.2 percent on the held-out set",
           "issue": "No interval is reported.", "evidence": "Results paragraph", "what_a_referee_would_say": "Add CIs."}


# ---------------------------------------------------------------------------
# Cost accounting
# ---------------------------------------------------------------------------

def test_cost_includes_cache_writes_and_reads_at_their_own_rates():
    # Opus 5.5: $4 in, $20 out, $5 per MTok to write a 5-minute cache entry, $0.20 to read one.
    assert p._cost_usd("claude-opus-5-5", 0, 0, cache_creation_tokens=1_000_000) == pytest.approx(5.0)
    assert p._cost_usd("claude-opus-5-5", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.20)
    assert p._cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(24.0)
    # A model with no cache_read entry is assumed to read at a tenth of its input rate.
    assert p._cost_usd("claude-sonnet-4-6", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.30)
    assert p._cost_usd("claude-unknown-9", 1_000_000, 0) == 10.0


def test_current_price_table_matches_the_published_rates():
    t = p.MODEL_PRICING_PER_MTOK
    assert (t["claude-sonnet-5"]["input"], t["claude-sonnet-5"]["output"]) == (2.0, 10.0)
    assert (t["claude-opus-5"]["input"], t["claude-opus-5"]["output"]) == (5.0, 25.0)
    assert (t["claude-haiku-5-5"]["input"], t["claude-haiku-5-5"]["output"]) == (0.10, 0.50)


@pytest.mark.asyncio
async def test_usage_tracker_records_cache_tokens_and_totals_all_input():
    client = _Client(lambda b, n: _Resp(200, _payload("[]", inp=1_000, out=500, cw=20_000, cr=0)
                                        if n == 1 else _payload("[]", inp=1_000, out=500, cw=0, cr=20_000)))
    with p.UsageTracker() as usage:
        for _ in range(2):
            await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                       max_tokens=10)
    assert usage.total_cache_creation_tokens == 20_000
    assert usage.total_cache_read_tokens == 20_000
    assert usage.total_input_tokens == 2_000 + 40_000
    first = 1_000 * 4 + 20_000 * 5 + 500 * 20
    second = 1_000 * 4 + 20_000 * 0.2 + 500 * 20
    assert usage.total_cost_usd == pytest.approx((first + second) / 1e6)
    d = usage.to_dict()
    assert d["cache_read_tokens"] == 20_000 and d["calls"] == 2


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persona_request_shape_model_caps_cache_and_no_temperature():
    client = _Client(lambda b, n: _Resp(200, _payload(json.dumps([FINDING]))))
    s = _structure()
    out = await p._run_one_persona(client, "statistical_skeptic", p.PERSONA_PROMPTS["statistical_skeptic"],
                                   s, {"findings": []}, {"issues": []}, "general")
    assert out["status"] == "ok" and len(out["findings"]) == 1
    body = client.bodies[0]
    assert body["model"] == "claude-opus-5-5"
    assert body["max_tokens"] == p.PERSONA_MAX_OUTPUT_TOKENS == 12_000
    assert "temperature" not in body                      # every 5.x model rejects it
    assert body["system"] == p.PANEL_SYSTEM
    blocks = body["messages"][0]["content"]
    assert len(blocks) == 2
    # The breakpoint sits on the shared block, and only there.
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]
    # Shared block: manuscript and domain module. Persona block: the persona and the instruction.
    assert s.body in blocks[0]["text"]
    assert "Statistical Skeptic" not in blocks[0]["text"]
    assert "Statistical Skeptic" in blocks[1]["text"]
    assert blocks[1]["text"].rstrip().endswith("Now produce your JSON array of findings.")
    # The document leads and the instructions follow it.
    assert blocks[0]["text"].index("<manuscript_body>") < len(blocks[0]["text"])
    assert len(json.dumps(body)) < 12_000                 # sanity: nothing duplicated into the request


def test_shared_prefix_is_byte_identical_across_personas_and_across_passes():
    s = _structure()
    l1, l2 = {"findings": [{"page": 1}]}, {"issues": [], "retractions": [], "audit": {"findings": []}}
    blocks = [p._build_persona_user_content(prompt, s, l1, l2, "general") for prompt in p.PERSONA_PROMPTS.values()]
    deep = p._build_persona_user_content(p.PERSONA_PROMPTS["methodology_critic"] + p._DEEP_PASS_SUFFIX, s, l1, l2,
                                         "general", tail="TAIL ")
    first = json.dumps(blocks[0][0], sort_keys=True)
    assert all(json.dumps(b[0], sort_keys=True) == first for b in blocks)
    assert json.dumps(deep[0], sort_keys=True) == first
    assert "TAIL " in deep[1]["text"] and "TAIL " not in deep[0]["text"]


@pytest.mark.asyncio
async def test_deep_pass_uses_the_same_system_prompt_and_cached_block_as_the_first_pass():
    seen = []

    def handler(body, n):
        seen.append(body)
        return _Resp(200, _payload("[]"))

    client = _Client(handler)
    s = _structure()
    await p._run_one_persona(client, "methodology_critic", p.PERSONA_PROMPTS["methodology_critic"],
                             s, {"findings": []}, {"issues": []}, "general")
    await p._run_one_persona_deep(client, "methodology_critic", p.PERSONA_PROMPTS["methodology_critic"],
                                  s, {"findings": []}, {"issues": []}, [FINDING], "general")
    first, deep = client.bodies
    assert first["system"] == deep["system"]
    assert first["messages"][0]["content"][0] == deep["messages"][0]["content"][0]
    assert "SECOND pass" in deep["messages"][0]["content"][1]["text"]
    assert "other_personas_first_pass_findings" in deep["messages"][0]["content"][1]["text"]


@pytest.mark.asyncio
async def test_panel_system_prompt_is_calibrated_and_not_stale():
    assert "seven-reviewer" in p.PANEL_SYSTEM and "four-reviewer" not in p.PANEL_SYSTEM
    assert "other six reviewers" in p._DEEP_PASS_SUFFIX and "other three" not in p._DEEP_PASS_SUFFIX
    for needle in ("return [] when you find nothing", "Never invent citations", "No em dashes", "claim_quoted"):
        assert needle in p.PANEL_SYSTEM


# ---------------------------------------------------------------------------
# Panel orchestration: warm the cache, then fan out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_panel_prewarms_once_then_runs_all_seven_with_the_same_prefix():
    s = _structure(body="word " * 3_000)

    def handler(body, n):
        if body["max_tokens"] == 0:
            return _Resp(200, _payload("", stop="max_tokens", out=0, cw=9_000))
        return _Resp(200, _payload("[]", cr=9_000))

    client = _Client(handler)
    l3 = await p.run_layer_3_personas(client, s, {"findings": []}, {"issues": []}, "general")
    assert [b["max_tokens"] for b in client.bodies].count(0) == 1
    assert client.bodies[0]["max_tokens"] == 0                       # the warm-up goes first
    assert len(client.bodies) == 1 + p.N_PERSONAS
    warm = client.bodies[0]
    assert warm["system"] == p.PANEL_SYSTEM and warm["model"] == p.PERSONA_MODEL
    warm_blocks = warm["messages"][0]["content"]
    assert len(warm_blocks) == 1 and warm_blocks[0]["cache_control"] == {"type": "ephemeral"}
    for b in client.bodies[1:]:
        assert b["messages"][0]["content"][0] == warm_blocks[0]       # same bytes, so the entry is read
    assert len(l3["panel"]) == 7


@pytest.mark.asyncio
async def test_panel_falls_back_to_one_persona_first_when_the_prewarm_is_refused():
    s = _structure(body="word " * 3_000)
    order = []

    def handler(body, n):
        if body["max_tokens"] == 0:
            return _Resp(400, {"error": {"type": "invalid_request_error", "message": "max_tokens must be >= 1"}})
        order.append(body["messages"][0]["content"][1]["text"][:40])
        return _Resp(200, _payload("[]", cw=9_000 if len(order) == 1 else 0, cr=0 if len(order) == 1 else 9_000))

    client = _Client(handler)
    l3 = await p.run_layer_3_personas(client, s, {"findings": []}, {"issues": []}, "general")
    assert len(order) == 7 and len(l3["panel"]) == 7
    assert "Methodology Critic" in order[0]            # the first persona ran alone before the rest


@pytest.mark.asyncio
async def test_tiny_manuscripts_skip_the_prewarm():
    client = _Client(lambda b, n: _Resp(200, _payload("[]")))
    await p.run_layer_3_personas(client, _structure(body="short"), {"findings": []}, {"issues": []}, "general")
    assert all(b["max_tokens"] > 0 for b in client.bodies)
    assert len(client.bodies) == p.N_PERSONAS


# ---------------------------------------------------------------------------
# Retries and ceilings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 502, 503, 504, 529, 429])
async def test_transient_server_errors_are_retried(status):
    client = _Client(lambda b, n: _Resp(status) if n == 1 else _Resp(200))
    out = await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert out == "ok" and len(client.bodies) == 2


@pytest.mark.asyncio
async def test_a_bad_request_is_not_retried():
    client = _Client(lambda b, n: _Resp(400, {"error": {"type": "invalid_request_error", "message": "bad field"}}))
    with pytest.raises(httpx.HTTPStatusError):
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert len(client.bodies) == 1


@pytest.mark.asyncio
async def test_retries_stop_after_three_attempts():
    client = _Client(lambda b, n: _Resp(503))
    with pytest.raises(httpx.HTTPStatusError):
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    assert len(client.bodies) == 3


@pytest.mark.asyncio
async def test_cost_ceiling_stops_the_next_call_before_it_is_sent():
    client = _Client(lambda b, n: _Resp(200, _payload("ok", inp=1_000_000, out=0)))     # $4.00 on Opus 5.5
    with p.UsageTracker(max_cost_usd=3.0) as usage:
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
        assert usage.over_ceiling()
        with pytest.raises(p.CostCeilingExceeded):
            await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                       max_tokens=10)
    assert len(client.bodies) == 1                      # the second request never left


@pytest.mark.asyncio
async def test_no_ceiling_means_no_limit_and_a_ceiling_does_not_leak_out_of_its_block():
    client = _Client(lambda b, n: _Resp(200, _payload("ok", inp=1_000_000, out=0)))
    with p.UsageTracker(max_cost_usd=1.0):
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    for _ in range(2):                                   # outside the block: unlimited
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}], max_tokens=10)
    with p.UsageTracker():                               # no ceiling given
        for _ in range(2):
            await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                       max_tokens=10)


@pytest.mark.asyncio
async def test_an_oversized_request_is_refused_before_it_is_sent(monkeypatch):
    monkeypatch.setattr(p, "MAX_REQUEST_INPUT_TOKENS", 1_000)
    client = _Client(lambda b, n: _Resp(200))
    with pytest.raises(p.InputTooLargeError):
        await p._anthropic_message(client, system="s", user_content=[{"type": "text", "text": "x" * 10_000}],
                                   max_tokens=10)
    assert client.bodies == []


def test_input_estimate_counts_text_and_images():
    assert p.estimate_input_tokens("a" * 320, [{"type": "text", "text": "b" * 320}]) == 200
    assert p.estimate_input_tokens("", [{"type": "image", "source": {}}]) == 1_700


def test_order_cost_ceiling_is_the_unit_price(monkeypatch):
    import app
    assert app._order_cost_ceiling("paper-review-standard") == pytest.approx(9.0)
    assert app._order_cost_ceiling("paper-review-deep") == pytest.approx(15.0)
    assert app._order_cost_ceiling("paper-review-pack-5") == pytest.approx(7.6)
    assert app._order_cost_ceiling("paper-review-pack-20") == pytest.approx(7.5)
    assert app._order_cost_ceiling("cover-letter") == pytest.approx(2.0)
    assert app._order_cost_ceiling("not-a-product") is None
    monkeypatch.setenv("ORDER_COST_CEILING_FACTOR", "0.5")
    assert app._order_cost_ceiling("paper-review-standard") == pytest.approx(4.5)
    monkeypatch.setenv("ORDER_COST_CEILING_FACTOR", "junk")
    assert app._order_cost_ceiling("paper-review-standard") == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# JSON parsing: good, malformed, partial
# ---------------------------------------------------------------------------

def test_parse_checked_distinguishes_empty_from_unreadable():
    assert p._parse_json_findings_checked("[]") == ([], True)
    assert p._parse_json_findings_checked("```json\n[{\"a\": 1}]\n```") == ([{"a": 1}], True)
    assert p._parse_json_findings_checked('Sure! Here you go: [{"a": 1}] Hope that helps.') == ([{"a": 1}], True)
    assert p._parse_json_findings_checked("I could not find any issues.") == ([], False)
    assert p._parse_json_findings_checked('[{"a": 1}, {"b": ') == ([], False)         # cut off
    assert p._parse_json_findings_checked('{"findings": [{"a": 1}]}') == ([{"a": 1}], True)   # array inside an object
    assert p._parse_json_findings_checked("") == ([], False)
    # Non-dict entries are dropped but the array still counts as read.
    assert p._parse_json_findings_checked('[1, {"a": 1}, "x"]') == ([{"a": 1}], True)


def test_parse_never_logs_the_response_text(caplog):
    secret = "UNPUBLISHED RESULT: the compound melts at 412 K"
    with caplog.at_level("DEBUG"):
        p._parse_json_findings_checked("[{\"a\": \"" + secret + "\"")
        p._parse_json_findings_checked("[{\"a\": \"" + secret + "\"}, ")
    assert secret not in caplog.text


def test_salvage_keeps_complete_objects_from_a_cut_off_array():
    raw = ('[{"issue": "one", "q": "has } brace and \\" quote"}, {"issue": "two", "n": {"deep": [1, 2]}}, '
           '{"issue": "three", "evidence": "cut off in the mid')
    got = p._salvage_json_objects(raw)
    assert [g["issue"] for g in got] == ["one", "two"]
    assert got[0]["q"] == 'has } brace and " quote'
    assert got[1]["n"] == {"deep": [1, 2]}
    assert p._salvage_json_objects("no array here") == []
    assert p._salvage_json_objects('[{"issue": "half') == []
    assert p._salvage_json_objects('```json\n[{"issue": "a"}, {"issue": "b') == [{"issue": "a"}]


# ---------------------------------------------------------------------------
# One retry on malformed output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_reply_is_retried_once_with_the_same_prefix_plus_a_reminder():
    replies = ["Here are my thoughts in prose.", json.dumps([FINDING])]
    client = _Client(lambda b, n: _Resp(200, _payload(replies[n - 1])))
    content = [{"type": "text", "text": "shared", "cache_control": {"type": "ephemeral"}},
               {"type": "text", "text": "persona"}]
    findings, status = await p._call_json_findings(client, system="sys", user_content=content, max_tokens=100)
    assert status == "ok" and findings == [FINDING]
    first, second = (b["messages"][0]["content"] for b in client.bodies)
    assert second[:2] == first[:2]                      # cached prefix untouched
    assert len(second) == 3 and second[2]["text"] == p._RETRY_JSON_NOTE


@pytest.mark.asyncio
async def test_two_malformed_replies_report_unparsed_not_an_empty_success():
    client = _Client(lambda b, n: _Resp(200, _payload("still prose")))
    findings, status = await p._call_json_findings(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                                   max_tokens=100)
    assert (findings, status) == ([], "unparsed") and len(client.bodies) == 2


@pytest.mark.asyncio
async def test_a_valid_empty_array_is_not_retried():
    client = _Client(lambda b, n: _Resp(200, _payload("[]")))
    findings, status = await p._call_json_findings(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                                   max_tokens=100)
    assert (findings, status) == ([], "ok") and len(client.bodies) == 1


@pytest.mark.asyncio
async def test_a_cut_off_reply_keeps_its_complete_findings_without_a_second_call():
    cut = json.dumps([FINDING, FINDING])[:-40]
    client = _Client(lambda b, n: _Resp(200, _payload(cut, stop="max_tokens")))
    findings, status = await p._call_json_findings(client, system="s", user_content=[{"type": "text", "text": "x"}],
                                                   max_tokens=100)
    assert status == "salvaged" and findings == [FINDING] and len(client.bodies) == 1


@pytest.mark.asyncio
async def test_a_persona_with_unreadable_output_is_marked_error_so_the_transcript_says_so():
    client = _Client(lambda b, n: _Resp(200, _payload("no json at all")))
    out = await p._run_one_persona(client, "methodology_critic", p.PERSONA_PROMPTS["methodology_critic"],
                                   _structure(), {"findings": []}, {"issues": []}, "general")
    assert out["status"] == "error" and out["findings"] == []
    text = p.render_panel_transcript({"panel": [out]})
    assert "(this reviewer's pass did not complete)" in text.split("### Statistical Skeptic")[0]


# ---------------------------------------------------------------------------
# Grounding: quotes found in the text
# ---------------------------------------------------------------------------

def test_flag_unverified_quotes_marks_invented_quotes_only():
    body = "We measured accuracy of 91.2 percent on the held-out set. Generaliza-\ntion was not tested."
    findings = [
        {"claim_quoted": "accuracy of 91.2 percent on the held-out set"},         # verbatim
        {"claim_quoted": "generalization was not tested"},                         # PDF hyphenation
        {"claim_quoted": "the model achieves state of the art everywhere"},        # invented
        {"claim_quoted": "Overall publication recommendation"},                    # editorial verdict, no quote
        {"claim_quoted": "two words"},                                             # too short to judge
        {"issue": "no quote at all"},
    ]
    n = p.flag_unverified_quotes(findings, body)
    assert n == 1
    assert findings[0]["quote_found"] is True and findings[1]["quote_found"] is True
    assert findings[2]["quote_found"] is False
    assert all("quote_found" not in f for f in findings[3:])


# ---------------------------------------------------------------------------
# Layer 4: input, transcript, truncation
# ---------------------------------------------------------------------------

def _l3():
    panel = [{"persona": k, "status": "ok", "findings": []} for k in p.PERSONA_PROMPTS]
    f = {"persona": "methodology_critic", "severity": "critical", "issue": "UNIQUE-MARKER-123 never ablated.",
         "claim_quoted": "we show", "quote_found": False, "_consensus": ["methodology_critic"]}
    panel[0]["findings"] = [f]
    return {"panel": panel, "merged_findings": [f], "n_findings": 1, "n_high_consensus": 0}


@pytest.mark.asyncio
async def test_layer4_sends_each_finding_once_and_appends_the_transcript_in_code():
    captured = {}

    def handler(body, n):
        captured["body"] = body
        return _Resp(200, _payload("# Manuscript Review\n\n## What's Working\n- fine\n\n## Panel Transcript\n"
                                   "### Methodology Critic\n- model wrote this itself\n", out=300))

    client = _Client(handler)
    out = await p.run_layer_4_rectify(client, _structure(), {"findings": []}, {"issues": []}, _l3())
    user = captured["body"]["messages"][0]["content"][0]["text"]
    assert user.count("UNIQUE-MARKER-123") == 1                      # was twice: merged list and per-persona panel
    assert captured["body"]["system"] == p.L4_SYSTEM
    assert "## Panel Transcript" not in p.L4_SYSTEM
    md = out["markdown"]
    assert md.count("## Panel Transcript") == 1
    assert "model wrote this itself" not in md                       # a transcript the model wrote anyway is dropped
    assert "- [critical] UNIQUE-MARKER-123 never ablated. (quote not found in the extracted text)" in md
    assert md.index("## What's Working") < md.index("## Panel Transcript")
    for title in p._PERSONA_TITLES.values():
        assert f"### {title}" in md


@pytest.mark.asyncio
async def test_layer4_json_blocks_are_compact():
    captured = {}
    client = _Client(lambda b, n: captured.setdefault("b", b) and _Resp(200, _payload("# R")))
    await p.run_layer_4_rectify(client, _structure(), {"findings": [{"page": 1, "type": "x"}]}, {"issues": []}, _l3())
    user = captured["b"]["messages"][0]["content"][0]["text"]
    assert '{"findings":[{"page":1,"type":"x"}]}' in user
    assert '  "' not in user.split("<manuscript_body>")[0]            # no indent=2 whitespace before the manuscript


@pytest.mark.asyncio
async def test_layer4_truncated_report_gets_the_note_and_still_carries_its_transcript():
    client = _Client(lambda b, n: _Resp(200, _payload("# Manuscript Review\n\n## What's Working\n- cut o", stop="max_tokens")))
    out = await p.run_layer_4_rectify(client, _structure(), {"findings": []}, {"issues": []}, _l3())
    md = out["markdown"]
    assert p._TRUNCATION_NOTE.strip() in md
    assert md.index(p._TRUNCATION_NOTE.strip()) < md.index("## Panel Transcript")
    assert "### Numerical Realist" in md


def test_capped_json_drops_whole_trailing_items():
    items = [{"i": i, "pad": "x" * 100} for i in range(100)]
    text = p._compact_json_capped(items, 2_000)
    kept = json.loads(text)                                          # still valid JSON, never cut mid-object
    assert 0 < len(kept) < 100 and len(text) <= 2_000
    assert kept == items[: len(kept)]
    assert p._compact_json_capped([], 10) == "[]"
    assert json.loads(p._compact_json_capped([{"big": "y" * 5_000}], 100)) == []


def test_transcript_lines_are_plain_text_and_bounded():
    l3 = {"panel": [{"persona": "methodology_critic", "status": "ok", "findings": [
        {"severity": "major", "issue": "See [x](http://evil.example) <script>alert(1)</script> ![img](u) " + "word " * 200}]}]}
    t = p.render_panel_transcript(l3)
    line = [l for l in t.splitlines() if l.startswith("- [major]")][0]
    assert "<" not in line and ">" not in line and "](" not in line and "![" not in line
    assert len(line) < p._TRANSCRIPT_LINE_MAX + 40 and line.endswith("...")
    assert "(this reviewer's pass did not complete)" in t             # personas absent from the panel


# ---------------------------------------------------------------------------
# Other paid tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anonymity_check_is_an_error_not_a_clean_bill_when_replies_are_unreadable(monkeypatch):
    async def fake(*a, **k):
        return "I found nothing worth reporting."
    monkeypatch.setattr(pre, "_anthropic_message", fake)
    out = await pre.run_anonymity_check(None, _structure())
    assert out["status"] == "error"

    async def clean(*a, **k):
        return "[]"
    monkeypatch.setattr(pre, "_anthropic_message", clean)
    out = await pre.run_anonymity_check(None, _structure())
    assert out["status"] == "ok" and out["n_total"] == 0


@pytest.mark.asyncio
async def test_cover_letter_caps_model_and_truncation(monkeypatch):
    seen = {}

    async def fake(client, *, system, user_content, max_tokens, **kw):
        seen.update(max_tokens=max_tokens, **kw)
        return "Dear Editor,\n\nWe submit..."
    monkeypatch.setattr(pre, "_anthropic_message", fake)
    out = await pre.run_cover_letter(None, _structure(), "Journal of Tests")
    assert out["status"] == "ok"
    assert seen["max_tokens"] == pre.COVER_LETTER_MAX_OUTPUT_TOKENS >= 4_000
    assert seen["model"] == p.DEFAULT_MODEL

    async def cut(client, *, system, user_content, max_tokens, on_truncated=None, **kw):
        on_truncated("m")
        return "Dear Editor, we sub"
    monkeypatch.setattr(pre, "_anthropic_message", cut)
    out = await pre.run_cover_letter(None, _structure(), "Journal of Tests")
    assert out["status"] == "error"                                  # never deliver a letter cut off mid-sentence


@pytest.mark.asyncio
async def test_revision_review_cap_and_truncation_note(monkeypatch):
    review = "## Rectification Checklist\n- **[A1]** Add a baseline."

    async def cut(client, *, system, user_content, max_tokens, on_truncated=None, **kw):
        assert max_tokens == pre.REVISION_REVIEW_MAX_OUTPUT_TOKENS >= 8_000
        on_truncated("m")
        return "# Revision Review\n\n## Summary\n- partway"
    monkeypatch.setattr(pre, "_anthropic_message", cut)
    out = await pre.run_revision_review(None, _structure(), review)
    assert out["status"] == "ok" and p._TRUNCATION_NOTE.strip() in out["markdown"]


def test_secondary_tool_models_default_to_the_main_model_and_are_overridable():
    for name in ("COVER_LETTER_MODEL", "ANONYMITY_MODEL", "CITATION_GAP_MODEL", "REVISION_REVIEW_MODEL"):
        assert getattr(pre, name) == p.DEFAULT_MODEL == "claude-opus-5-5"


@pytest.mark.asyncio
async def test_response_review_shares_one_cached_manuscript_and_keeps_it_from_the_tone_editor(monkeypatch):
    from latextools import response_review as rr
    s = _structure(body="manuscript " * 2_000)
    monkeypatch.setattr(rr, "extract_paper", lambda pdf: s)

    def handler(body, n):
        if body["max_tokens"] == 0:
            return _Resp(200, _payload("", stop="max_tokens", out=0, cw=5_000))
        text = body["messages"][0]["content"][-1]["text"]
        if "Editor-in-Chief" in text or "Skeptical Reviewer" in text or "Tone Editor" in text:
            return _Resp(200, _payload("[]"))
        return _Resp(200, _payload("# Response Letter Review\n\n## Overall Verdict\nok"))

    client = _Client(handler)

    class _CM:
        async def __aenter__(self_):
            return client

        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _CM())
    out = await rr.run_response_review(b"pdf", "Reviewer 1:\n1. Please add a baseline.", "We added a baseline.")
    assert out["status"] == "done"
    bodies = client.bodies
    warm = [b for b in bodies if b["max_tokens"] == 0]
    assert len(warm) == 1 and warm[0]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    by_persona = {}
    for b in bodies:
        blocks = b["messages"][0]["content"]
        for key in ("Skeptical Reviewer", "Tone Editor", "Editor-in-Chief"):
            if blocks[-1]["text"].startswith("<persona name=\"%s\"" % key):
                by_persona[key] = b
    assert set(by_persona) == {"Skeptical Reviewer", "Tone Editor", "Editor-in-Chief"}
    tone_text = json.dumps(by_persona["Tone Editor"]["messages"])
    assert "manuscript manuscript" not in tone_text                  # no 20,000 tokens of manuscript for a tone check
    for k in ("Skeptical Reviewer", "Editor-in-Chief"):
        assert by_persona[k]["system"] == rr.RR_PANEL_SYSTEM == by_persona["Tone Editor"]["system"]
        assert by_persona[k]["messages"][0]["content"][0] == warm[0]["messages"][0]["content"][0]
        assert "manuscript manuscript" in by_persona[k]["messages"][0]["content"][0]["text"]
    synth = [b for b in bodies if b["max_tokens"] == rr.RR_SYNTHESIS_MAX_OUTPUT_TOKENS][0]
    assert synth["max_tokens"] >= 10_000


# ---------------------------------------------------------------------------
# Prompt snapshots (review prompt changes as diffs)
# ---------------------------------------------------------------------------

def _snapshot_texts() -> dict:
    s = _structure()
    l1 = {"findings": [{"page": 2, "type": "presentation", "severity": "minor", "where": "Figure 1",
                        "observation": "Axis labels are small.", "recommendation": "Enlarge them."}]}
    l2 = {"issues": [], "retractions": [], "audit": {"findings": []}}
    content = p._build_persona_user_content(p.PERSONA_PROMPTS["methodology_critic"], s, l1, l2, "general")
    deep = p._build_persona_user_content(
        p.PERSONA_PROMPTS["methodology_critic"] + p._DEEP_PASS_SUFFIX, s, l1, l2, "general",
        tail="<other findings go here>\n\nNow produce your SECOND-PASS JSON array of findings.\n\n")
    from latextools import response_review as rr

    def render(blocks):
        return "\n".join(
            f"--- block {i}{' [cache_control: ephemeral]' if b.get('cache_control') else ''} ---\n{b['text']}"
            for i, b in enumerate(blocks))

    return {
        "panel_system.txt": p.PANEL_SYSTEM,
        "persona_user_content.txt": render(content),
        "persona_deep_user_content.txt": render(deep),
        "l4_system.txt": p.L4_SYSTEM,
        "l1_system.txt": p.L1_SYSTEM,
        "response_review_panel_system.txt": rr.RR_PANEL_SYSTEM,
        "retry_note.txt": p._RETRY_JSON_NOTE,
        "cover_letter_system.txt": pre._COVER_LETTER_SYSTEM,
        "anonymity_system.txt": pre._ANONYMITY_SYSTEM,
        "citation_gap_system.txt": pre._CITATION_GAP_SYSTEM,
        "revision_system.txt": pre._REVISION_SYSTEM,
        "transcript_example.txt": p.render_panel_transcript(_l3()),
    }


@pytest.mark.parametrize("name", sorted(_snapshot_texts()))
def test_prompt_snapshot(name):
    text = _snapshot_texts()[name]
    path = SNAP_DIR / name
    if os.environ.get("UPDATE_PROMPT_SNAPSHOTS") == "1":
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"missing snapshot {name}; run with UPDATE_PROMPT_SNAPSHOTS=1"
    assert text == path.read_text(encoding="utf-8"), (
        f"{name} changed. If the edit is intended, regenerate with UPDATE_PROMPT_SNAPSHOTS=1 and review the diff."
    )
