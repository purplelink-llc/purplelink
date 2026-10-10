#!/usr/bin/env python3
# backend/benchmark/persona_models.py
"""Can Opus 5.5 or Sonnet 5.5 run Paper Review's persona calls instead of Fable 5?

COSTS REAL MONEY (about $2.5 at the defaults; a hard cap stops it). Use a SEPARATE key with
spare credit: on 2026-10-09 benchmark runs on the production key used up its prepaid credit.

    cd backend && BENCH_ANTHROPIC_KEY=... python3 benchmark/persona_models.py

Method. There is no ground truth for "a good review", so the test plants known defects.
Two real published papers (CAIS, found on the SSD) are trimmed to a short body and five
defects are inserted at seeded positions:

  D1 a t statistic that cannot give the reported p        D4 a percentage that does not match its count
  D2 two contradictory sample sizes                        D5 a claim attributed to a source that does not exist
  D3 an overclaim ("prove ... causes ... every organization")

Four personas (the production persona calls, same prompts, same call path) read each paper on
each model. For every (model, paper) the script reports how many of the five planted defects
the combined findings caught, how many findings quote text that is NOT in the paper (invented
quotes), findings per call, failures, which model really served the call (a refusal falls
back to Opus), tokens, cost and latency.

Limits. Five planted defects in two papers is a small, easy test: it catches a model that cannot
find obvious problems, not one that is subtly worse at deep review. The papers are published and
may contain real flaws the planted ones do not account for.
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("BENCH_ANTHROPIC_KEY", "")
if not os.environ["ANTHROPIC_API_KEY"]:
    raise SystemExit("Set BENCH_ANTHROPIC_KEY to a key with spare credit (not the production key).")

import httpx  # noqa: E402

from latextools import papercheck as pc  # noqa: E402

CORPUS = "/Volumes/Extreme SSD/Attention Check Survey/fulltext_pdfs/staging_cais_aisel/Vol_42/*.pdf"
MODELS = [m for m in os.environ.get("BENCH_MODELS", "claude-fable-5,claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5").split(",") if m]
PERSONAS = ["methodology_critic", "statistical_skeptic", "literature_auditor", "numerical_realist"]
N_PAPERS = int(os.environ.get("N_PAPERS", "2"))
# Production caps persona output at 4,000 tokens; 5.x models spend 5,000 to 6,000 on a persona review, so most
# calls truncate and parse to nothing. Test with PERSONA_CAP=12000 to see the models without that failure.
pc.PERSONA_MAX_OUTPUT_TOKENS = int(os.environ.get("PERSONA_CAP", pc.PERSONA_MAX_OUTPUT_TOKENS))
BODY_CHARS = 18_000
BUDGET_USD = float(os.environ.get("BENCH_BUDGET_USD", "3.2"))

DEFECTS = {
    "D1_stat": ("A paired comparison showed a significant difference between the two conditions, t(48) = 1.20, p < .001.",
                lambda t: bool(re.search(r"1\.20|t\(48\)|p\s*<\s*\.?001", t))),
    "D2_n": [("A total of 120 respondents completed the survey and all 120 were retained for the analysis.", 0.35),
             ("The analysis of the 87 respondents who completed the survey showed consistent results across groups.", 0.7)],
    "D3_overclaim": ("These results prove that the intervention causes higher performance in every organization.",
                     lambda t: bool(re.search(r"\bprove|causes? higher|every organi[sz]ation", t, re.I))),
    "D4_percent": ("Of the 40 participants, 52 percent (n = 31) agreed with the statement.",
                   lambda t: bool(re.search(r"52 ?(percent|%)|n ?= ?31", t))),
    "D5_fake_cite": ("As Hartwell and Okonkwo (2019) showed, 95 percent of firms adopt such tools within one year.",
                     lambda t: bool(re.search(r"Hartwell|Okonkwo", t))),
}
DETECT = {
    "D1_stat": DEFECTS["D1_stat"][1], "D3_overclaim": DEFECTS["D3_overclaim"][1],
    "D4_percent": DEFECTS["D4_percent"][1], "D5_fake_cite": DEFECTS["D5_fake_cite"][1],
    "D2_n": lambda t: "120" in t and "87" in t,
}


def norm(s: str) -> str:
    s = re.sub(r"-\s*\n\s*", "", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zÀ-￿]+", " ", s)).strip()


def build_papers():
    files = sorted(glob.glob(CORPUS))
    picked = []
    for f in files:
        if len(picked) == N_PAPERS:
            break
        try:
            s = pc.extract_paper(open(f, "rb").read())
        except Exception:
            continue
        if len(s.body) < BODY_CHARS or s.n_references_total < 8:
            continue
        lines = s.body[:BODY_CHARS].split("\n")
        rng = random.Random(len(picked) + 11)
        inserts = {}
        for key in ("D1_stat", "D3_overclaim", "D4_percent", "D5_fake_cite"):
            inserts[key] = (rng.uniform(0.25, 0.85), DEFECTS[key][0])
        for i, (text, pos) in enumerate(DEFECTS["D2_n"]):
            inserts[f"D2_{i}"] = (pos, text)
        for _, (pos, text) in sorted(inserts.items(), key=lambda kv: -kv[1][0]):
            lines.insert(max(1, int(len(lines) * pos)), text)
        s.body = "\n".join(lines)
        picked.append((os.path.basename(f)[:48], s))
    return picked


async def one(client, sem, spend, model, paper_name, structure, persona):
    prompt = pc.PERSONA_PROMPTS[persona]
    user_content = pc._build_persona_user_content(prompt, structure, {"findings": []},
                                                  {"checked": 0, "verified": 0, "issues": [], "retractions": [], "audit": {}}, "general")
    system = (pc._safety.SAFETY_PREAMBLE + "\n\nYou are part of a four-reviewer adversarial panel red-teaming an academic "
              "manuscript. Stay strictly in your assigned persona. Quote the paper exactly when you cite it. "
              "Output a JSON array of findings and nothing else.")
    async with sem:
        if spend["usd"] > BUDGET_USD:
            return {"model": model, "paper": paper_name, "persona": persona, "skipped": "budget"}
        t = time.time()
        try:
            with pc.UsageTracker() as u:
                raw = await pc._anthropic_message(client, system=system, user_content=user_content,
                                                  max_tokens=pc.PERSONA_MAX_OUTPUT_TOKENS, model=model)
            spend["usd"] += u.total_cost_usd
            findings = [f for f in pc._parse_json_findings(raw) if isinstance(f, dict)]
            return {"model": model, "paper": paper_name, "persona": persona, "findings": findings, "served": u.models_used(),
                    "usd": u.total_cost_usd, "in": u.total_input_tokens, "out": u.total_output_tokens, "secs": time.time() - t}
        except Exception as e:
            return {"model": model, "paper": paper_name, "persona": persona, "error": f"{type(e).__name__}: {str(e)[:160]}"}


async def main():
    papers = build_papers()
    if len(papers) < N_PAPERS:
        raise SystemExit(f"only found {len(papers)} usable papers")
    spend = {"usd": 0.0}
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)) as client:
        results = await asyncio.gather(*[one(client, sem, spend, m, name, s, p)
                                         for m in MODELS for name, s in papers for p in PERSONAS])
    bodies = {name: norm(s.body) for name, s in papers}
    report = {"papers": [n for n, _ in papers], "total_usd": round(spend["usd"], 2), "models": {}}
    for m in MODELS:
        rs = [r for r in results if r["model"] == m]
        per_paper = {}
        for name, _ in papers:
            mine = [r for r in rs if r["paper"] == name and "findings" in r]
            text = " ".join(json.dumps(f) for r in mine for f in r["findings"])
            caught = sorted(k for k, fn in DETECT.items() if fn(text))
            per_paper[name] = {"caught": caught, "n_caught": len(caught)}
        allf = [f for r in rs if "findings" in r for f in r["findings"]]
        invented = 0; checked_q = 0
        for r in rs:
            if "findings" not in r:
                continue
            for f in r["findings"]:
                q = norm(str(f.get("claim_quoted", "")))
                if len(q.split()) >= 4:
                    checked_q += 1
                    invented += q not in bodies[r["paper"]]
        report["models"][m] = {
            "defects_caught_per_paper": per_paper,
            "defects_caught_total": sum(v["n_caught"] for v in per_paper.values()), "of": 5 * len(papers),
            "calls_ok": sum(1 for r in rs if "findings" in r), "calls_empty": sum(1 for r in rs if "findings" in r and not r["findings"]),
            "calls_failed": [r.get("error") or r.get("skipped") for r in rs if "findings" not in r],
            "findings_per_call": round(len(allf) / max(1, sum(1 for r in rs if "findings" in r)), 1),
            "severity": {s: sum(1 for f in allf if f.get("severity") == s) for s in ("critical", "major", "minor")},
            "quotes_checked": checked_q, "quotes_not_in_paper": invented,
            "served_by": sorted({x for r in rs for x in r.get("served", [])}),
            "tokens_in": sum(r.get("in", 0) for r in rs), "tokens_out": sum(r.get("out", 0) for r in rs),
            "usd": round(sum(r.get("usd", 0) for r in rs), 3),
            "median_secs": round(sorted(r["secs"] for r in rs if "secs" in r)[len([1 for r in rs if "secs" in r]) // 2], 1)
            if any("secs" in r for r in rs) else None,
        }
    report["sample_findings"] = {m: [{"persona": r["persona"], "severity": f.get("severity"), "quote": str(f.get("claim_quoted"))[:100],
                                     "issue": str(f.get("issue"))[:140]} for r in results if r["model"] == m and "findings" in r
                                    for f in r["findings"][:1]][:3] for m in ("claude-opus-5-5", "claude-sonnet-5-5")}
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
