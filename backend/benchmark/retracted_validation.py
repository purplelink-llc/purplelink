#!/usr/bin/env python3
# backend/benchmark/retracted_validation.py
"""Does Paper Review notice what later got a paper retracted?

COSTS REAL MONEY (about $2.50 per paper on a typical manuscript; 25 papers plus 6 controls is about $75).
Run it with a spare budget in mind; the per-paper cost is printed, and --limit bounds a trial run.

    cd backend && python3 -m modal run benchmark/retracted_validation.py \\
        --candidates /path/validation-candidates.json --pdf-dir /path/pdfs --out /path/results --limit 3

Inputs
  * candidates.json from the selection step: {"candidates": [{id, title, doi, field, retracted, notice_doi,
    reason_category, reason_summary, detectable_from_manuscript, ...}], "controls": [{id or doi, ...}]}
  * one PDF per paper in --pdf-dir, named <id>.pdf (controls: control-<n>.pdf or <id>.pdf)

What it does
  1. Runs the real review pipeline (standard tier, general domain) on each PDF on Modal, with the production
     prompts and models, recording cost and the report.
  2. For each retracted paper, a judge model reads ONLY the retraction reason and the report's findings (not the
     paper) and answers: did the report identify that problem? yes / partly / no, with the finding it relied on.
  3. For controls (non-retracted papers) it counts critical findings and Contradicted claims as a false-alarm
     proxy.
  4. Writes results.json and results.md under --out, with every number traceable to a report file.

Limits, stated plainly. The reasons come from retraction notices and may not describe everything wrong. A paper
retracted for an error may carry that error in data the manuscript does not show. The judge is a model; the
script keeps every report so a person can check its calls, and the write-up should say how many were checked by
hand. Selection is of retractions with documented honest errors, which are easier to find than subtle flaws.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import modal  # noqa: E402

# Same packages as the production image, defined here so the container does not need the app module.
IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("texlive-latex-recommended", "texlive-latex-extra", "texlive-fonts-recommended", "texlive-xetex",
                 "latexmk", "latexdiff", "biber", "pandoc")
    .apt_install("poppler-utils")
    .apt_install("ghostscript")
    .pip_install("fastapi[standard]==0.115.2", "python-docx==1.1.2", "lxml==5.3.0", "bibtexparser>=1.3,<2",
                 "httpx==0.27.2", "markitdown[pdf,docx,pptx,xlsx]==0.1.6", "pdfplumber>=0.11,<1",
                 "pdf2image>=1.17,<2", "pillow>=10,<12", "pypdf>=4.3,<6")
    .add_local_file(os.path.join(os.path.dirname(HERE), "texmf.cnf"), "/etc/texmf/texmf.d/99-hardening.cnf", copy=True)
    .run_commands("update-texmf")
    .add_local_python_source("latextools")
)
SECRETS = [modal.Secret.from_name("anthropic-secret")]
stub = modal.App("retracted-validation")

JUDGE_MODEL = "claude-opus-5-5"
JUDGE_SYSTEM = (
    "You compare an AI manuscript review with the documented reason a paper was later retracted. You see only the "
    "retraction reason and the review's findings, not the paper. Decide whether the review identified the problem "
    "the retraction describes, even if it named it differently. 'yes' means a finding clearly points at the same "
    "error. 'partly' means a finding points at the same area or a symptom of it without naming the error. 'no' "
    "means nothing in the review points at it. Be strict: generic advice that would apply to any paper is 'no'. "
    'Reply with ONLY JSON: {"verdict": "yes"|"partly"|"no", "finding": "<the finding you relied on, under 40 words, or empty>"}'
)


@stub.function(image=IMAGE, secrets=SECRETS, timeout=1200, cpu=2.0, memory=4096, max_containers=6)
def review(pdf: bytes, env: dict | None = None) -> dict:
    import asyncio
    import time

    os.environ.update(env or {})      # experiment switches such as RECTIFY_EFFORT, set before papercheck reads them

    from latextools import papercheck

    t0 = time.time()

    async def go():
        with papercheck.UsageTracker() as u:
            final = await papercheck.run_review_pipeline(pdf, domain="general", tier="standard")
        return final, u

    try:
        final, u = asyncio.run(go())
    except Exception as e:                                   # a PDF that cannot be read is a result, not a crash
        return {"error": f"{type(e).__name__}: {str(e)[:200]}", "seconds": round(time.time() - t0)}
    return {"seconds": round(time.time() - t0), "status": final.get("status"), "usd": round(u.total_cost_usd, 3),
            "tokens_in": u.total_input_tokens, "tokens_out": u.total_output_tokens,
            "report_md": final.get("result_md") or "", "layers": final.get("layer_status"),
            "deterministic": [d.get("summary", "")[:160] for d in (final.get("deterministic_findings") or [])]}


@stub.function(image=IMAGE, secrets=SECRETS, timeout=300)
def judge(reason: str, findings_text: str) -> dict:
    import asyncio

    import httpx

    from latextools import papercheck

    async def go():
        async with httpx.AsyncClient(timeout=120) as c:
            raw = await papercheck._anthropic_message(
                c, system=JUDGE_SYSTEM,
                user_content=[{"type": "text", "text": f"RETRACTION REASON:\n{reason}\n\nREVIEW FINDINGS:\n{findings_text[:24000]}"}],
                max_tokens=1500, model=JUDGE_MODEL)
        return raw

    raw = asyncio.run(go())
    try:
        o = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        v = str(o.get("verdict", "")).lower()
        return {"verdict": v if v in ("yes", "partly", "no") else "unparsed", "finding": str(o.get("finding", ""))[:300]}
    except Exception:
        return {"verdict": "unparsed", "finding": raw[:200]}


def findings_section(md: str) -> str:
    """The parts of a report that state problems, without the praise and the transcript."""
    import re
    keep = []
    for name in ("Verified Checks", "Claims and Evidence", "Critical Blind Spots", "Data-to-Claim Contradictions",
                 "Equation Audit", "Literature & Citation Usage", "Number Realism", "Rectification Checklist"):
        m = re.search(rf"^## {re.escape(name)}.*?(?=^## |\Z)", md, re.M | re.S)
        if m:
            keep.append(m.group(0))
    return "\n\n".join(keep) or md


def false_alarm_counts(md: str) -> dict:
    import re
    crit = len(re.findall(r"\*\*\[Confidence: high\]\*\*", md))
    contradicted = len(re.findall(r"\|\s*Contradicted\b", md))
    return {"high_confidence_blind_spots": crit, "contradicted_claims": contradicted}


@stub.local_entrypoint()
def main(candidates: str, pdf_dir: str, out: str, limit: int = 0, include_controls: bool = True, only: str = "", env: str = ""):
    os.makedirs(out, exist_ok=True)
    data = json.load(open(candidates))
    papers = [(c["id"], c, "retracted") for c in data.get("candidates", [])]
    if include_controls:
        papers += [(c.get("id") or f"control-{i + 1}", c, "control") for i, c in enumerate(data.get("controls", []))]
    if only:                       # a fixed, outcome-blind selection, for example every other control
        wanted = {i.strip() for i in only.split(",") if i.strip()}
        papers = [p for p in papers if p[0] in wanted]
    todo = []
    for pid, meta, kind in papers:
        path = os.path.join(pdf_dir, f"{pid}.pdf")
        if os.path.exists(path):
            todo.append((pid, meta, kind, path))
        else:
            print(f"skip {pid}: no PDF at {path}")
    # Resume: papers already reviewed without error in a previous run of this --out are kept, not paid for again.
    prior = {}
    prior_path = os.path.join(out, "results.json")
    if os.path.exists(prior_path):
        prior = {r["id"]: r for r in json.load(open(prior_path)).get("rows", []) if "error" not in r}
        todo = [t for t in todo if t[0] not in prior]
    if limit:
        todo = todo[:limit]
    print(f"Reviewing {len(todo)} papers on Modal (about $2.50 each); {len(prior)} already done.")
    extra = dict(kv.split("=", 1) for kv in env.split(",") if "=" in kv)
    results = list(review.starmap([(open(p, "rb").read(), extra) for _, _, _, p in todo], return_exceptions=True))
    rows, total = list(prior.values()), sum(r.get("usd", 0) for r in prior.values())
    for (pid, meta, kind, _), res in zip(todo, results):
        if isinstance(res, Exception) or "error" in res:
            rows.append({"id": pid, "kind": kind, "error": str(res)[:200] if isinstance(res, Exception) else res["error"]})
            continue
        md = res["report_md"]
        open(os.path.join(out, f"{pid}.report.md"), "w").write(md)
        total += res["usd"]
        row = {"id": pid, "kind": kind, "title": meta.get("title", "")[:100], "field": meta.get("field"), "usd": res["usd"],
               "report_chars": len(md), "status": res["status"], **false_alarm_counts(md)}
        if kind == "retracted":
            j = judge.remote(meta.get("reason_summary", ""), findings_section(md))
            row.update(reason=meta.get("reason_summary"), category=meta.get("reason_category"),
                       detectable=meta.get("detectable_from_manuscript"), verdict=j["verdict"], finding=j["finding"])
        rows.append(row)
    json.dump({"rows": rows, "total_usd": round(total, 2)}, open(os.path.join(out, "results.json"), "w"), indent=1)
    ret = [r for r in rows if r.get("kind") == "retracted" and "verdict" in r]
    ctl = [r for r in rows if r.get("kind") == "control" and "error" not in r]
    lines = [f"# Retracted-paper validation", "", f"Papers reviewed: {len(rows)}. Total model cost: ${total:.2f}.", ""]
    if ret:
        n = len(ret)
        c = {k: sum(1 for r in ret if r["verdict"] == k) for k in ("yes", "partly", "no", "unparsed")}
        lines += [f"Retracted papers: {n}. Problem identified: {c['yes']}. Partly: {c['partly']}. Not identified: {c['no']}. "
                  f"Judge unparsed: {c['unparsed']}.", ""]
    if ctl:
        lines += [f"Controls (not retracted): {len(ctl)}. Mean high-confidence blind spots "
                  f"{sum(r['high_confidence_blind_spots'] for r in ctl) / len(ctl):.1f}; mean contradicted claims "
                  f"{sum(r['contradicted_claims'] for r in ctl) / len(ctl):.1f}.", ""]
    lines += ["| id | verdict | reason (short) | finding relied on |", "|---|---|---|---|"]
    for r in ret:
        lines.append(f"| {r['id']} | {r['verdict']} | {str(r.get('reason', ''))[:70]} | {str(r.get('finding', ''))[:90]} |")
    open(os.path.join(out, "results.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


@stub.local_entrypoint()
def baseline(candidates: str, out: str, per_reason: int = 2):
    """Chance baseline: judge each retraction reason against the findings of NON-retracted papers' reports.

    If the judge says 'yes' often on a mismatched report, the matched-pair hit rate is mostly chance. Pairing is
    fixed (reason i against controls i, i+1, ... in id order) so it cannot be chosen by outcome."""
    data = json.load(open(candidates))
    rows = json.load(open(os.path.join(out, "results.json")))["rows"]
    reasons = {c["id"]: c for c in data["candidates"]}
    done = sorted(r["id"] for r in rows if r.get("kind") == "retracted" and "verdict" in r)
    ctl = sorted(r["id"] for r in rows if r.get("kind") == "control" and "error" not in r)
    pairs = [(rid, ctl[(i + k) % len(ctl)]) for i, rid in enumerate(done) for k in range(per_reason)]
    texts = {cid: findings_section(open(os.path.join(out, f"{cid}.report.md")).read()) for cid in ctl}
    res = list(judge.starmap([(reasons[rid].get("reason_summary", ""), texts[cid]) for rid, cid in pairs], return_exceptions=True))
    matched = {r["id"]: r["verdict"] for r in rows if r.get("kind") == "retracted" and "verdict" in r}
    out_rows = [{"reason_of": rid, "control": cid, "verdict": (r["verdict"] if isinstance(r, dict) else "error"),
                 "finding": (r.get("finding", "") if isinstance(r, dict) else str(r)[:100])} for (rid, cid), r in zip(pairs, res)]
    json.dump(out_rows, open(os.path.join(out, "baseline.json"), "w"), indent=1)
    cnt = lambda vs: {k: sum(1 for v in vs if v == k) for k in ("yes", "partly", "no", "unparsed", "error")}
    print("matched   ", cnt(matched.values()), "of", len(matched))
    print("mismatched", cnt([r["verdict"] for r in out_rows]), "of", len(out_rows))
