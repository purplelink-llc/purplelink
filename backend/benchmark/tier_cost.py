#!/usr/bin/env python3
# backend/benchmark/tier_cost.py
"""What does one order of each Paper Review product cost in model calls?
COSTS REAL MONEY: about $10-20 per paper (all six products run on it). Run one paper first and read the total.
    cd backend && python3 -m modal run benchmark/tier_cost.py --pdf /path/paper.pdf --out /path/result.json

Runs the production code paths on Modal with the production secrets (anthropic-secret, and coherence-flags so
COHERENCE_IN_REVIEW matches the live pipeline), each product under its own UsageTracker with the same per-order
ceiling the live job uses (_order_cost_ceiling: the price paid). Nothing is written to the live job, token or
usage-ledger Dicts, so the dashboard and funnel never see these runs.

The products are chained so each gets realistic input from the same paper:
  standard  run_review_pipeline(tier="standard", anonymity_check=True)              Paper Review $14
  journal   same, plus a journal pack (default neurips)                              Paper Review $24
  deep      run_review_pipeline(tier="deep", journal pack, anonymity)                Paper Review $39
  (each of the three plus the coherence section when COHERENCE_IN_REVIEW=1, as app.py does)
  revision  run_revision_review on the same PDF against the standard report          Revision Review $5
  draft     run_response_draft with reviewer comments taken from the standard report Response draft $24
  response  run_response_review on that drafted letter                               Response Review $12
The Publication Pack ($59) is deep + revision + draft (its response check is inside the draft), so its cost is
the sum of those three rows. Use public papers only (arXiv), never a customer's file.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import modal  # noqa: E402

# Same packages as the production image (see retracted_validation.py).
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
SECRETS = [modal.Secret.from_name("anthropic-secret"), modal.Secret.from_name("coherence-flags")]
stub = modal.App("tier-cost")

# Prices paid, in USD, matching PAID_PRODUCTS in app.py; each product's model spend is capped at its price.
PRICES = {"standard": 14.0, "journal": 24.0, "deep": 39.0, "revision": 5.0, "draft": 24.0, "response": 12.0}
MAX_COMMENTS = 20


def comments_from_report(report_md: str, limit: int = MAX_COMMENTS) -> str:
    """Reviewer comments for the draft and response products, built from a review's bullet findings: the
    Rectification Checklist when present, else every top-level bullet. Formatted as one reviewer's numbered list."""
    m = re.search(r"^##+ .*Rectification Checklist.*$", report_md, re.M | re.I)
    body = report_md[m.end():] if m else report_md
    if m:
        nxt = re.search(r"^## ", body, re.M)
        body = body[:nxt.start()] if nxt else body
    items = []
    for line in body.splitlines():
        s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+(?:\[[ x]\]\s*)?", "", line)
        if s != line and len(s.strip()) > 40:
            items.append(re.sub(r"\*\*", "", s.strip()))
        if len(items) >= limit:
            break
    return "Reviewer 1\n\n" + "\n\n".join(f"Comment {i}. {t}" for i, t in enumerate(items, 1))


def _usage_dict(u, seconds: float, status) -> dict:
    return {"status": status, "seconds": round(seconds), "usd": round(u.total_cost_usd, 4), "calls": len(u.records),
            "input_tokens": u.total_input_tokens, "cache_read_tokens": u.total_cache_read_tokens,
            "cache_creation_tokens": u.total_cache_creation_tokens, "output_tokens": u.total_output_tokens,
            "usd_by_model": u.cost_by_model(), "hit_ceiling": u.over_ceiling()}


@stub.function(image=IMAGE, secrets=SECRETS, timeout=3600, cpu=2.0, memory=4096)
def run_chain(pdf: bytes, journal_key: str = "neurips", only: str = "") -> dict:
    import asyncio
    import time

    import httpx

    from latextools import coherence, journals, papercheck, paperreview_extras, response_draft, response_review

    want = set(filter(None, only.split(","))) or set(PRICES)
    out: dict = {"coherence_in_review": coherence.in_review_enabled(), "products": {}}

    async def paper(tier: str, jkey: str | None, ceiling: float):
        with papercheck.UsageTracker(max_cost_usd=ceiling) as u:
            t0 = time.time()
            final = await papercheck.run_review_pipeline(
                pdf, domain="general", tier=tier,
                journal_pack=journals.JOURNAL_SPECS.get(jkey) if jkey else None, anonymity_check=True)
            if coherence.in_review_enabled() and final.get("result_md"):
                ms = coherence.load_manuscript(pdf, "manuscript.pdf")
                await coherence.run_coherence_check(ms)
        return final.get("result_md") or "", _usage_dict(u, time.time() - t0, final.get("status"))

    async def go():
        std_md = ""
        for name, tier, jkey in (("standard", "standard", None), ("journal", "standard", journal_key),
                                 ("deep", "deep", journal_key)):
            if name in want or (name == "standard" and want & {"revision", "draft", "response"}):
                md, use = await paper(tier, jkey, PRICES[name])
                out["products"][name] = use
                if name == "standard":
                    std_md = md
        if "revision" in want and std_md:
            with papercheck.UsageTracker(max_cost_usd=PRICES["revision"]) as u:
                t0 = time.time()
                struct = papercheck.extract_paper(pdf)
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)) as c:
                    res = await paperreview_extras.run_revision_review(c, struct, std_md)
            out["products"]["revision"] = _usage_dict(u, time.time() - t0, res.get("status"))
        letter = ""
        comments = comments_from_report(std_md) if std_md else ""
        out["n_comments"] = comments.count("\nComment ") + comments.startswith("Comment ")
        if want & {"draft", "response"} and comments:
            with papercheck.UsageTracker(max_cost_usd=PRICES["draft"]) as u:
                t0 = time.time()
                final = await response_draft.run_response_draft(pdf, comments, "")
            letter = final.get("result_md") or ""
            out["products"]["draft"] = _usage_dict(u, time.time() - t0, final.get("status"))
        if "response" in want and letter:
            with papercheck.UsageTracker(max_cost_usd=PRICES["response"]) as u:
                t0 = time.time()
                final = await response_review.run_response_review(pdf, comments, letter)
            out["products"]["response"] = _usage_dict(u, time.time() - t0, final.get("status"))

    asyncio.run(go())
    out["total_usd"] = round(sum(p["usd"] for p in out["products"].values()), 4)
    return out


@stub.local_entrypoint()
def main(pdf: str, out: str, journal: str = "neurips", only: str = ""):
    from pypdf import PdfReader

    r = PdfReader(pdf)
    meta = {"pdf": os.path.basename(pdf), "pages": len(r.pages),
            "chars": sum(len(p.extract_text() or "") for p in r.pages)}
    res = run_chain.remote(open(pdf, "rb").read(), journal, only)
    res = {**meta, **res}
    with open(out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
