#!/usr/bin/env python3
"""Replay a few public papers through the OLD and NEW Paper Review prompts and write a side-by-side report.

NOT RUN AS PART OF THE UPGRADE PR. Running it spends real money on the Anthropic API. It prints a cost
estimate first and does nothing until you type the confirmation word. The estimate for the default set of four
papers is about $9 (range $7 to $13); see ESTIMATE NOTES below. Use --dry-run to see the estimate only.

What it compares (layers whose prompts changed in the upgrade; the vision layer and CrossRef lookups are skipped,
their inputs are empty lists in both variants, so the comparison is like for like):
  * Layer 3, the seven-persona panel: old prompt layout (domain module and persona before the manuscript, a
    "four-reviewer" system prompt, no cache marker) vs the new layout (system prompt shared, manuscript block first
    with cache_control, persona instructions last, calibration rules).
  * Layer 4, the synthesis report: old system prompt and input (indent=2 JSON, every finding sent twice, model
    writes the Panel Transcript) vs the new one (compact JSON, findings once, transcript rendered in code,
    calibration rules).

How it runs: the Message Batches API at 50 percent of list price, in two batches (personas, then reports built from
the persona answers). Prompt-cache hits inside a batch are best effort, so the cost estimate assumes none and the
real bill for the NEW arm is usually lower. Both arms use the production models and settings (Opus 5.5, default
effort, no temperature). Nothing here touches Modal, Stripe or the production key: set BENCH_ANTHROPIC_KEY to a
separate key (never the production one; see memory note on benchmark keys).

Papers (all arXiv, license CC BY 4.0 as shown on each abstract page when checked on 2026-10-17):
  2201.11903  Chain-of-Thought Prompting Elicits Reasoning in Large Language Models        (machine_learning)
  2309.17453  Efficient Streaming Language Models with Attention Sinks                     (machine_learning)
  2305.18290  Direct Preference Optimization: Your Language Model is Secretly a Reward Model (machine_learning)
  2511.13860  Randomized Controlled Trials for Phishing Triage Agent                       (psychology_social)
The set is ML-heavy because CC BY papers in other fields are harder to find on arXiv. To cover the biomedicine and
chemistry modules, add your own open-access PDFs with --pdf path:domain (for example a PMC CC BY article).

Usage:
  python3 scripts/ai_review_eval.py --dry-run                  # estimate only, no key needed
  BENCH_ANTHROPIC_KEY=sk-ant-... python3 scripts/ai_review_eval.py
  python3 scripts/ai_review_eval.py --papers 2201.11903 --pdf ~/Downloads/x.pdf:biomedicine

Needs: the backend requirements (pdfplumber etc.) and `pip install anthropic`. Run from the repo root.

ESTIMATE NOTES. Per paper and arm: 7 persona calls of about 27,000 input and 6,000 output tokens, plus one report
call of about 50,000 input and 20,000 output tokens, all at Opus 5.5 list prices ($4 / $20 per MTok) halved for
batch. The script recomputes input sizes from the real extracted text before asking you to confirm.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

# Pinned to the commit the upgrade branched from, so the "old" arm stays the old prompts after the PR merges.
DEFAULT_OLD_REF = "2171ac2cb"

PAPERS = [
    ("2201.11903", "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models", "machine_learning"),
    ("2309.17453", "Efficient Streaming Language Models with Attention Sinks", "machine_learning"),
    ("2305.18290", "Direct Preference Optimization: Your Language Model is Secretly a Reward Model", "machine_learning"),
    ("2511.13860", "Randomized Controlled Trials for Phishing Triage Agent", "psychology_social"),
]

# Assumed output sizes (tokens, thinking included), measured on 2026-10-09 and 2026-10-10 runs.
PERSONA_OUT_TOKENS = 6_000
L4_OUT_TOKENS = 20_000
BATCH_DISCOUNT = 0.5
PRICE_IN, PRICE_OUT = 4.0, 20.0           # Opus 5.5 $/MTok

OLD_PANEL_SYSTEM_TAIL = (
    "You are part of a four-reviewer adversarial panel red-teaming an "
    "academic manuscript. Stay strictly in your assigned persona. Quote "
    "the paper exactly when you cite it. Output a JSON array of "
    "findings and nothing else."
)


# ---------------------------------------------------------------------------
# Loading the old and new prompt code
# ---------------------------------------------------------------------------

def load_old_module(ref: str):
    """papercheck.py as of `ref`, loaded under the name papercheck_old (read from git, nothing checked out)."""
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:backend/latextools/papercheck.py"],
                         capture_output=True, text=True, check=True).stdout
    tmp = Path(tempfile.mkdtemp(prefix="papercheck_old_")) / "papercheck_old.py"
    tmp.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("papercheck_old", tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["papercheck_old"] = mod        # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    return mod


def old_l4_user_text(old, structure, l1, l2, l3) -> str:
    """The old layer-4 user message: indent=2 JSON, merged findings plus the same findings again as `panel`."""
    s = old._safety
    return (
        s.wrap_user_content(
            f"Title: {structure.title or '(not extracted)'}\nPages: {structure.page_count}\n"
            f"References extracted: {len(structure.references)} of {structure.n_references_total}",
            "paper_metadata") + "\n\n"
        + s.wrap_user_content(structure.abstract or "(not extracted)", "abstract") + "\n\n"
        + s.wrap_user_content(json.dumps(l1, indent=2)[:30_000], "layer_1_vision") + "\n\n"
        + s.wrap_user_content(json.dumps(l2, indent=2)[:30_000], "layer_2_citations") + "\n\n"
        + s.wrap_user_content(json.dumps({"merged_findings": l3.get("merged_findings", []),
                                          "panel": l3.get("panel", [])}, indent=2)[:60_000], "layer_3_panel") + "\n"
        + "\n" + s.wrap_user_content(structure.body, "manuscript_body") + "\n\n"
        + "Produce the final Markdown report now."
    )


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

def fetch_pdf(arxiv_id: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{arxiv_id}.pdf"
    if not path.exists():
        req = urllib.request.Request(f"https://arxiv.org/pdf/{arxiv_id}",
                                     headers={"User-Agent": "purplelink-eval/1.0 (ben@purplelink.llc)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
        time.sleep(3)                       # be polite to arXiv
    return path


def load_papers(args, pc):
    out = []
    wanted = set(args.papers) if args.papers else None
    for aid, title, domain in PAPERS:
        if wanted is not None and aid not in wanted:
            continue
        pdf = fetch_pdf(aid, Path(args.cache))
        out.append({"id": aid, "title": title, "domain": domain, "structure": pc.extract_paper(pdf.read_bytes())})
    for spec in args.pdf or []:
        path, _, domain = spec.partition(":")
        domain = domain or "general"
        if domain not in pc.DOMAINS:
            sys.exit(f"unknown domain {domain!r}; choose from {pc.DOMAINS}")
        p = Path(path).expanduser()
        out.append({"id": p.stem, "title": p.stem, "domain": domain, "structure": pc.extract_paper(p.read_bytes())})
    if not out:
        sys.exit("no papers selected")
    return out


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------

def persona_requests(pc, old, papers):
    reqs = []
    empty_l1, empty_l2 = {"findings": []}, {"issues": [], "retractions": [], "audit": {"findings": []}}
    for paper in papers:
        s = paper["structure"]
        for key, prompt in pc.PERSONA_PROMPTS.items():
            old_content = old._build_persona_user_content(prompt, s, empty_l1, empty_l2, paper["domain"])
            reqs.append({"custom_id": f"{paper['id']}__old__{key}", "params": {
                "model": pc.PERSONA_MODEL, "max_tokens": pc.PERSONA_MAX_OUTPUT_TOKENS,
                "system": pc._safety.SAFETY_PREAMBLE + "\n\n" + OLD_PANEL_SYSTEM_TAIL,
                "messages": [{"role": "user", "content": old_content}]}})
            new_content = pc._build_persona_user_content(prompt, s, empty_l1, empty_l2, paper["domain"])
            reqs.append({"custom_id": f"{paper['id']}__new__{key}", "params": {
                "model": pc.PERSONA_MODEL, "max_tokens": pc.PERSONA_MAX_OUTPUT_TOKENS,
                "system": pc.PANEL_SYSTEM, "messages": [{"role": "user", "content": new_content}]}})
    return reqs


def l4_requests(pc, old, papers, persona_results):
    """Report requests from each arm's own persona answers."""
    reqs = []
    empty_l1, empty_l2 = {"findings": []}, {"issues": [], "retractions": [], "audit": {"findings": []}}
    for paper in papers:
        s = paper["structure"]
        for arm in ("old", "new"):
            panel = []
            for key in pc.PERSONA_PROMPTS:
                raw = persona_results.get(f"{paper['id']}__{arm}__{key}", {}).get("text", "")
                findings, _ = pc._parse_json_findings_checked(raw)
                pc.flag_unverified_quotes(findings, s.body)
                for f in findings:
                    f["persona"] = key
                panel.append({"persona": key, "findings": findings, "status": "ok"})
            l3 = pc._consensus_filter(panel)
            paper.setdefault("l3", {})[arm] = l3
            if arm == "old":
                system, user = old.L4_SYSTEM, old_l4_user_text(old, s, empty_l1, empty_l2, l3)
            else:
                user = (pc._safety.wrap_user_content(
                    f"Title: {s.title or '(not extracted)'}\nPages: {s.page_count}\n"
                    f"References extracted: {len(s.references)} of {s.n_references_total}", "paper_metadata") + "\n\n"
                    + pc._safety.wrap_user_content(s.abstract or "(not extracted)", "abstract") + "\n\n"
                    + pc._safety.wrap_user_content(pc._compact_json(empty_l1), "layer_1_vision") + "\n\n"
                    + pc._safety.wrap_user_content(pc._compact_json(empty_l2), "layer_2_citations") + "\n\n"
                    + pc._safety.wrap_user_content(pc._compact_json_capped(l3.get("merged_findings", []), 60_000),
                                                   "layer_3_panel") + "\n\n"
                    + pc._safety.wrap_user_content(s.body, "manuscript_body") + "\n\n"
                    + "Produce the final Markdown report now.")
                system = pc.L4_SYSTEM
            reqs.append({"custom_id": f"{paper['id']}__{arm}__l4", "params": {
                "model": pc.DEFAULT_MODEL, "max_tokens": pc.RECTIFY_MAX_OUTPUT_TOKENS, "system": system,
                "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}]}})
    return reqs


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------

def request_input_tokens(pc, req) -> int:
    p = req["params"]
    return pc.estimate_input_tokens(p["system"], p["messages"][0]["content"])


def estimate(pc, persona_reqs, papers, l4_in_tokens=None) -> dict:
    """Dollars for the whole run at batch prices, assuming no cache hits and the output sizes above."""
    p_in = sum(request_input_tokens(pc, r) for r in persona_reqs)
    p_out = len(persona_reqs) * PERSONA_OUT_TOKENS
    n_l4 = 2 * len(papers)
    l4_in = l4_in_tokens if l4_in_tokens is not None else sum(
        pc.estimate_input_tokens(pc.L4_SYSTEM, [{"type": "text", "text": p["structure"].body}]) + 12_000
        for p in papers) * 2
    l4_out = n_l4 * L4_OUT_TOKENS
    full = (p_in + l4_in) * PRICE_IN / 1e6 + (p_out + l4_out) * PRICE_OUT / 1e6
    return {"persona_calls": len(persona_reqs), "l4_calls": n_l4, "input_tokens": p_in + l4_in,
            "output_tokens_assumed": p_out + l4_out, "batch_usd": round(full * BATCH_DISCOUNT, 2),
            "list_price_usd": round(full, 2)}


def actual_cost(usage: dict) -> float:
    """Batch-priced dollars from a response's usage block (cache writes 1.25x, reads 0.05x of input on Opus 5.5)."""
    inp = usage.get("input_tokens", 0) * PRICE_IN
    cw = usage.get("cache_creation_input_tokens", 0) * PRICE_IN * 1.25
    cr = usage.get("cache_read_input_tokens", 0) * 0.20
    out = usage.get("output_tokens", 0) * PRICE_OUT
    return (inp + cw + cr + out) / 1e6 * BATCH_DISCOUNT


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------

def run_batch(client, requests, label: str) -> dict:
    batch = client.messages.batches.create(requests=requests)
    print(f"[{label}] batch {batch.id} submitted ({len(requests)} requests); polling every 60s", flush=True)
    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        time.sleep(60)
    out = {}
    for item in client.messages.batches.results(batch.id):          # any order: key by custom_id
        r = item.result
        if r.type != "succeeded":
            out[item.custom_id] = {"text": "", "stop_reason": r.type, "usage": {}}
            continue
        m = r.message
        text = "".join(blk.text for blk in m.content if getattr(blk, "type", "") == "text")
        out[item.custom_id] = {"text": text, "stop_reason": m.stop_reason,
                               "usage": m.usage.model_dump() if hasattr(m.usage, "model_dump") else dict(m.usage)}
    return out


# ---------------------------------------------------------------------------
# Metrics and report
# ---------------------------------------------------------------------------

def persona_metrics(pc, paper, arm, results) -> dict:
    n = parsed = trunc = found = quoted = 0
    cost = 0.0
    sev = {"critical": 0, "major": 0, "minor": 0}
    for key in pc.PERSONA_PROMPTS:
        r = results.get(f"{paper['id']}__{arm}__{key}", {})
        findings, ok = pc._parse_json_findings_checked(r.get("text", ""))
        parsed += 1 if ok else 0
        trunc += 1 if r.get("stop_reason") == "max_tokens" else 0
        cost += actual_cost(r.get("usage", {}))
        pc.flag_unverified_quotes(findings, paper["structure"].body)
        for f in findings:
            n += 1
            sev[str(f.get("severity", "")).lower()] = sev.get(str(f.get("severity", "")).lower(), 0) + 1
            if "quote_found" in f:
                quoted += 1
                found += 1 if f["quote_found"] else 0
    return {"findings": n, "calls_parsed": f"{parsed}/{len(pc.PERSONA_PROMPTS)}", "truncated_calls": trunc,
            "severity": sev, "quotes_checked": quoted,
            "quotes_not_found": quoted - found, "cost_usd": round(cost, 2)}


def report_metrics(pc, text: str, stop: str, usage: dict) -> dict:
    claims = re.search(r"^## Claims and Evidence\s*$(.*?)(?=^## )", text, re.M | re.S)
    rows = [l for l in (claims.group(1).splitlines() if claims else []) if l.startswith("|")][2:]
    spots = re.search(r"^## Critical Blind Spots\s*$(.*?)(?=^## )", text, re.M | re.S)
    n_spots = len(re.findall(r"^- \*\*\[Confidence", spots.group(1), re.M)) if spots else 0
    return {"chars": len(text), "truncated": stop == "max_tokens", "claim_rows": len(rows),
            "claims_supported": sum(1 for r in rows if re.search(r"\|\s*Supported\b", r)),
            "blind_spots": n_spots, "has_panel_transcript": "## Panel Transcript" in text,
            "output_tokens": usage.get("output_tokens", 0), "cost_usd": round(actual_cost(usage), 2)}


def write_report(pc, papers, persona_res, l4_res, out_dir: Path, est: dict, seed: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    lines = [f"# Paper Review prompt eval, {dt.date.today()}", "",
             f"Estimate before the run: ${est['batch_usd']} (batch). Batch prices, cache hits best effort.", "",
             "## Layer 3 panel", "", "| Paper | Arm | Findings | Parsed | Truncated | Critical/Major/Minor | "
             "Quotes not found | Cost |", "|---|---|---|---|---|---|---|---|"]
    total = 0.0
    for p in papers:
        for arm in ("old", "new"):
            m = persona_metrics(pc, p, arm, persona_res)
            total += m["cost_usd"]
            s = m["severity"]
            lines.append(f"| {p['id']} | {arm} | {m['findings']} | {m['calls_parsed']} | {m['truncated_calls']} | "
                         f"{s.get('critical', 0)}/{s.get('major', 0)}/{s.get('minor', 0)} | "
                         f"{m['quotes_not_found']}/{m['quotes_checked']} | ${m['cost_usd']} |")
    lines += ["", "## Layer 4 report", "", "| Paper | Arm | Chars | Truncated | Claim rows | Supported | Blind spots | "
              "Transcript | Out tokens | Cost |", "|---|---|---|---|---|---|---|---|---|---|"]
    blind = []
    for p in papers:
        pair = {}
        for arm in ("old", "new"):
            r = l4_res.get(f"{p['id']}__{arm}__l4", {})
            text = r.get("text", "")
            if arm == "new":
                text = pc._strip_panel_transcript(text) + "\n\n" + pc.render_panel_transcript(p["l3"]["new"])
            m = report_metrics(pc, text, r.get("stop_reason", ""), r.get("usage", {}))
            total += m["cost_usd"]
            pair[arm] = text
            lines.append(f"| {p['id']} | {arm} | {m['chars']} | {m['truncated']} | {m['claim_rows']} | "
                         f"{m['claims_supported']} | {m['blind_spots']} | {m['has_panel_transcript']} | "
                         f"{m['output_tokens']} | ${m['cost_usd']} |")
        order = ["old", "new"]
        rng.shuffle(order)
        blind.append((p, order, pair))
    lines += ["", f"Total actual cost: ${total:.2f}", "",
              "## Blind read (decide which report you would rather send; the key is at the end)", ""]
    key = []
    for p, order, pair in blind:
        lines += [f"### {p['id']}  {p['title']}", ""]
        for label, arm in zip("AB", order):
            lines += [f"#### Report {label}", "", pair[arm], ""]
        key.append(f"{p['id']}: A={order[0]}, B={order[1]}")
    lines += ["## Key", "", *[f"- {k}" for k in key], ""]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "raw.json").write_text(json.dumps({"personas": persona_res, "l4": l4_res}), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the estimate and stop")
    ap.add_argument("--papers", nargs="*", help="arXiv ids from the built-in list (default: all)")
    ap.add_argument("--pdf", nargs="*", help="extra PDFs as path:domain")
    ap.add_argument("--old-ref", default=DEFAULT_OLD_REF, help="git ref holding the old prompts")
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "ai_review_eval_pdfs"))
    ap.add_argument("--out", default=str(REPO / "docs" / "growth-briefs" / f"ai-review-eval-{dt.date.today()}"))
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()

    from latextools import papercheck as pc
    old = load_old_module(args.old_ref)
    papers = load_papers(args, pc)
    reqs = persona_requests(pc, old, papers)
    est = estimate(pc, reqs, papers)
    print(json.dumps(est, indent=2))
    print(f"\nEstimated cost: ${est['batch_usd']} at batch prices (${est['list_price_usd']} at list). "
          f"Papers: {', '.join(p['id'] for p in papers)}.")
    if args.dry_run:
        return 0
    key = os.environ.get("BENCH_ANTHROPIC_KEY")
    if not key:
        sys.exit("set BENCH_ANTHROPIC_KEY to a separate benchmark key (not the production key)")
    if input("This will spend real money. Type 'spend' to continue: ").strip().lower() != "spend":
        print("cancelled")
        return 1
    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic")
    client = anthropic.Anthropic(api_key=key)
    persona_res = run_batch(client, reqs, "personas")
    l4 = l4_requests(pc, old, papers, persona_res)
    l4_res = run_batch(client, l4, "reports")
    path = write_report(pc, papers, persona_res, l4_res, Path(args.out), est, args.seed)
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
