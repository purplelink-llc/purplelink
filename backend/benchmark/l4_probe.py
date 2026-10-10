#!/usr/bin/env python3
# backend/benchmark/l4_probe.py
"""Tune the report-writing call (layer 4) without paying for a whole review each time.

COSTS REAL MONEY: one `capture` is a full review (about $3.50); each `trial` is one layer-4 call (about $0.50 to $1).

    python3 -m modal run benchmark/l4_probe.py::capture --pdf /path/paper.pdf --key RV08
    python3 -m modal run benchmark/l4_probe.py::trial --key RV08 --cap 20000 --effort medium

`capture` runs the real pipeline once and stores layer 4's inputs in a Modal Dict. `trial` replays layer 4 with a
chosen token cap and effort, and prints output tokens, thinking tokens, whether the reply was cut off, and which
sections the report reached. Added 2026-10-10 after every one of 29 study reports stopped mid-word.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import modal  # noqa: E402

# Same image as retracted_validation.py, repeated because the container cannot import a sibling script.
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

stub = modal.App("l4-probe")
STORE = modal.Dict.from_name("l4-probe-inputs", create_if_missing=True)


@stub.function(image=IMAGE, secrets=SECRETS, timeout=1500, cpu=2.0, memory=4096)
def capture_remote(pdf: bytes, key: str) -> str:
    import asyncio
    import pickle

    from latextools import papercheck as p

    real = p.run_layer_4_rectify

    async def spy(client, structure, l1, l2, l3, **kw):
        STORE[key] = pickle.dumps((structure, l1, l2, l3, kw))
        return {"status": "ok", "markdown": ""}

    p.run_layer_4_rectify = spy
    try:
        asyncio.run(p.run_review_pipeline(pdf, domain="general", tier="standard"))
    except Exception as e:                                   # whatever runs after layer 4 does not matter here
        return f"pipeline ended after layer 4: {type(e).__name__}"
    return "captured"


@stub.function(image=IMAGE, secrets=SECRETS, timeout=1500)
def trial_remote(key: str, cap: int, effort: str, model: str) -> dict:
    import asyncio
    import pickle
    import re
    import time

    import httpx

    from latextools import papercheck as p

    structure, l1, l2, l3, kw = pickle.loads(STORE[key])
    p.RECTIFY_MAX_OUTPUT_TOKENS = cap
    if effort:
        os.environ["RECTIFY_EFFORT"] = effort
    p.DEFAULT_MODEL = model or p.DEFAULT_MODEL
    seen = []
    orig = p._anthropic_message_once

    async def spy(*a, **k):
        text, usage = await orig(*a, **k)
        seen.append({**usage, "model": k.get("model"), "chars": len(text)})
        return text, usage

    p._anthropic_message_once = spy
    # layer 4 passes no model, so the default argument bound at definition time is used; rebind it
    if model:
        p._anthropic_message.__kwdefaults__["model"] = model

    async def go():
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=900, write=30, pool=10)) as c:
            return await p.run_layer_4_rectify(c, structure, l1, l2, l3, **kw)

    t = time.time()
    with p.UsageTracker() as u:
        res = asyncio.run(go())
    md = res.get("markdown", "")
    return {"cap": cap, "effort": effort or "(default)", "model": model or p.DEFAULT_MODEL, "secs": round(time.time() - t),
            "usd": round(u.total_cost_usd, 3), "calls": seen, "chars": len(md),
            "cut_off": "cut off by the model" in md, "sections": re.findall(r"^## (.+)$", md, re.M)}


@stub.local_entrypoint()
def capture(pdf: str, key: str):
    print(capture_remote.remote(open(pdf, "rb").read(), key))


@stub.local_entrypoint()
def trial(key: str, cap: int = 20000, effort: str = "", model: str = ""):
    r = trial_remote.remote(key, cap, effort, model)
    print({k: v for k, v in r.items() if k != "sections"})
    print("sections:", r["sections"])
