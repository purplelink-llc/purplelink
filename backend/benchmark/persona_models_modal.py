#!/usr/bin/env python3
# backend/benchmark/persona_models_modal.py
"""Run the planted-defect persona check (persona_models.py) on Modal, with the key from the anthropic-secret, for
one effort level and a list of models. Effort is read when papercheck is imported, so each effort level is its own
run. COSTS REAL MONEY: about $1-4 per run; BENCH_BUDGET_USD inside persona_models.py stops it.
    cd backend && python3 -m modal run benchmark/persona_models_modal.py --models claude-opus-5-5,claude-fable-5-2 \
        --effort high --out /path/result.json
It is a floor test (five obvious defects in two papers): it shows whether a model misses obvious problems or
invents quotes, not which model reviews best.
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import modal  # noqa: E402

# The production Python packages, without TeX (the persona calls only read the PDF).
IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("poppler-utils", "ghostscript")
    .pip_install("fastapi[standard]==0.115.2", "python-docx==1.1.2", "lxml==5.3.0", "bibtexparser>=1.3,<2",
                 "httpx==0.27.2", "markitdown[pdf,docx,pptx,xlsx]==0.1.6", "pdfplumber>=0.11,<1",
                 "pdf2image>=1.17,<2", "pillow>=10,<12", "pypdf>=4.3,<6")
    .add_local_python_source("latextools")
)

CORPUS = "/Volumes/Extreme SSD/Attention Check Survey/fulltext_pdfs/staging_cais_aisel/Vol_42/*.pdf"
stub = modal.App("persona-models")


@stub.function(image=IMAGE.add_local_file(os.path.join(HERE, "persona_models.py"), "/root/bench/persona_models.py"),
               secrets=[modal.Secret.from_name("anthropic-secret")], timeout=1800)
def run(pdfs: dict, models: str, effort: str, budget: float) -> dict:
    import asyncio
    import contextlib
    import io

    os.makedirs("/tmp/corpus", exist_ok=True)
    for name, data in pdfs.items():
        with open(os.path.join("/tmp/corpus", name), "wb") as f:
            f.write(data)
    # Set before import: persona_models reads these at import time. The key never leaves the container.
    os.environ["BENCH_ANTHROPIC_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
    os.environ["BENCH_MODELS"] = models
    os.environ["BENCH_BUDGET_USD"] = str(budget)
    if effort:
        os.environ["REVIEW_EFFORT"] = effort
    sys.path.insert(0, "/root/bench")
    import persona_models as pm

    pm.CORPUS = "/tmp/corpus/*.pdf"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        asyncio.run(pm.main())
    report = json.loads(buf.getvalue())
    report["effort"] = pm.pc.DEFAULT_EFFORT
    report["persona_cap"] = pm.pc.PERSONA_MAX_OUTPUT_TOKENS
    return report


@stub.local_entrypoint()
def main(models: str, out: str, effort: str = "", budget: float = 6.0):
    pdfs = {os.path.basename(p): open(p, "rb").read() for p in sorted(glob.glob(CORPUS))}
    res = run.remote(pdfs, models, effort, budget)
    with open(out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
