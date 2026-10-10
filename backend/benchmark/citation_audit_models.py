#!/usr/bin/env python3
# backend/benchmark/citation_audit_models.py
"""Which Claude model should judge citation support in Paper Review?

THIS COSTS REAL MONEY WHEN RUN (about $6 at 60 abstracts, mostly the production
default model). Give it a SEPARATE key with spare credit: on 2026-10-09 two runs on the
production key used up its prepaid credit and stopped the daily digest cron. The key is
read from BENCH_ANTHROPIC_KEY and sent to Modal as an inline secret:

    cd backend && BENCH_ANTHROPIC_KEY=... N_ABSTRACTS=30 python3 -m modal run benchmark/citation_audit_models.py

What it does
  1. Samples real, public abstracts from OpenAlex (a seeded random sample).
  2. For each abstract, a strong model writes four one-sentence claims, one per
     production verdict: Supported, Partially supported, Contradicted, Not
     supported by abstract. The label is the instruction the writer was given.
  3. Each candidate model judges every (claim, abstract) pair with the PRODUCTION
     prompt and batching (latextools.citation_audit: same system prompt, same
     fences, batches of 8, same output schema).
  4. Reports accuracy, per-class recall, confusion, false alarms on Supported
     claims, parse failures, tokens, cost and latency per model.

Limits, stated plainly. The labels are constructed, not human-judged: the
Partially supported / Not supported boundary is the least reliable, and a Claude
model wrote the claims, which may favour Claude judges. Real citations are subtler
than these. Treat the result as a way to rank models and spot gross failures, not
as an accuracy figure to quote. Abstracts are public and no manuscript text is used.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import modal  # noqa: E402

# A lean image (the benchmark needs HTTP and the audit prompt, not TeX Live) and the
# production secret. Both are defined unconditionally so the container sees the same objects.
IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx==0.27.2", "pdfplumber>=0.11,<1", "pdf2image>=1.17,<2", "pillow>=10,<12", "pypdf>=4.3,<6")
    .add_local_python_source("latextools")
)
# The key is passed at launch (BENCH_ANTHROPIC_KEY) and travels as an inline secret: nothing is stored in Modal
# and the production `anthropic-secret` is never touched. The object is defined unconditionally so the
# container sees the same one (its contents only matter locally).
if modal.is_local() and not os.environ.get("BENCH_ANTHROPIC_KEY"):
    raise SystemExit("Set BENCH_ANTHROPIC_KEY to a key with spare credit (not the production key).")
SECRETS = [modal.Secret.from_dict({"ANTHROPIC_API_KEY": os.environ.get("BENCH_ANTHROPIC_KEY", "")})]

stub = modal.App("citation-audit-model-benchmark")

# $ per million tokens (input, output), from OpenRouter's catalogue on 2026-10-09.
PRICES = {
    "claude-fable-5": (10.0, 50.0),
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
GENERATOR = "claude-opus-5-5"
CANDIDATES = ["claude-fable-5", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
LABELS = {
    "supported": "Supported",
    "partial": "Partially supported",
    "contradicted": "Contradicted",
    "unsupported": "Not supported by abstract",
}
N_ABSTRACTS = 40
JUDGE_MAX_TOKENS = 4000   # production uses 1500
BATCH = 8
BUDGET_USD = 5.0

GEN_SYSTEM = (
    "You write test items for evaluating a citation checker. You are given the abstract of a real paper. "
    "Write four different one-sentence claims (each under 35 words) that a manuscript might make while citing "
    "this paper. Write them as an author would in a literature review: in your own words, never copying a "
    "sentence from the abstract, and with no citation marker.\n"
    "- supported: faithfully states a finding or fact that the abstract reports.\n"
    "- partial: relates to a real finding but overstates it (generalises beyond the sample, turns correlation into "
    "causation, adds a detail or magnitude the abstract does not give), so only part of it is supported.\n"
    "- contradicted: asserts the opposite of something the abstract reports (reverses the direction or the "
    "presence of an effect).\n"
    "- unsupported: plausible and on the same topic, but about something the abstract reports neither way.\n"
    'Reply ONLY with JSON: {"supported": "...", "partial": "...", "contradicted": "...", "unsupported": "..."}'
)


EFFORT = None   # set per run; "low" | "medium" | "high" | None (the API default)


async def _call(client, model, system, user, max_tokens, spend):
    """One Anthropic messages call with transient-error retries. Returns
    (text, usage, seconds, echoed_model) or raises RuntimeError with the API's message."""
    import asyncio
    import time

    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}]}
    if EFFORT:
        body["output_config"] = {"effort": EFFORT}
    # No temperature: every 5.x model rejects the field, so all candidates run at their default
    # (production sends 0.1 only to models that still accept it).
    headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    for attempt in range(6):
        t = time.time()
        resp = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers, timeout=180)
        if resp.status_code in (429, 529, 500, 502, 503):
            await asyncio.sleep(min(30, 2 ** attempt))
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"{resp.status_code}: {resp.text[:300]}")
        d = resp.json()
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        pin, pout = PRICES.get(model, (10.0, 50.0))
        spend["usd"] += (u.get("input_tokens", 0) * pin + u.get("output_tokens", 0) * pout) / 1e6
        if spend["usd"] > BUDGET_USD:
            raise RuntimeError(f"budget guard: spent ${spend['usd']:.2f} > ${BUDGET_USD}")
        return text, u, time.time() - t, d.get("model", model), (d.get("stop_reason"), d.get("stop_details"))
    raise RuntimeError("too many transient errors")


@stub.function(image=IMAGE, secrets=SECRETS, timeout=3000, cpu=2.0, memory=2048)
def run(n_abstracts: int = N_ABSTRACTS, models: list | None = None, judge_cap: int = JUDGE_MAX_TOKENS,
        budget_usd: float = BUDGET_USD, effort: str | None = None) -> dict:
    global BUDGET_USD, JUDGE_MAX_TOKENS, CANDIDATES, EFFORT
    BUDGET_USD, JUDGE_MAX_TOKENS, EFFORT = budget_usd, judge_cap, effort
    CANDIDATES = models or CANDIDATES
    import asyncio
    import json
    import random
    import statistics
    from collections import Counter, defaultdict

    import httpx

    from latextools import citation_audit as ca
    from latextools.papercheck import _parse_json_findings

    spend = {"usd": 0.0}

    async def main():
        async with httpx.AsyncClient() as client:
            # 1. Real abstracts ------------------------------------------------------------------
            r = await client.get(
                "https://api.openalex.org/works",
                params={"filter": "has_abstract:true,type:article,from_publication_date:2016-01-01,cited_by_count:>30",
                        "sample": "140", "seed": "7", "per-page": "140",
                        "select": "id,title,abstract_inverted_index,primary_topic",
                        "mailto": "ben@purplelink.llc"},
                timeout=60)
            r.raise_for_status()
            abstracts = []
            for w in r.json().get("results", []):
                text = ca.reconstruct_abstract(w.get("abstract_inverted_index"))
                if text and 500 <= len(text) <= 1800 and text.isascii():
                    topic = ((w.get("primary_topic") or {}).get("field") or {}).get("display_name", "")
                    abstracts.append({"id": w["id"], "text": text, "field": topic})
            abstracts = abstracts[:n_abstracts]

            # 2. Labelled claims -----------------------------------------------------------------
            sem = asyncio.Semaphore(6)

            async def gen(a):
                async with sem:
                    try:
                        text, _, _, _, _ = await _call(client, GENERATOR, GEN_SYSTEM, "ABSTRACT:\n" + a["text"], 900, spend)
                        o = json.loads(text[text.index("{"): text.rindex("}") + 1])
                        return [{"abstract": a, "claim": o[k].strip(), "label": LABELS[k]} for k in LABELS if o.get(k)]
                    except Exception as e:
                        gen_errors.append(f"{type(e).__name__}: {str(e)[:240]}")
                        return []

            gen_errors: list = []
            # Which of the model ids we want does this API key accept? (A wrong id is the usual failure.)
            id_check = {}
            for m in dict.fromkeys([GENERATOR] + CANDIDATES):
                try:
                    await _call(client, m, "Reply with the word ok.", "ok?", 8, spend)
                    id_check[m] = "ok"
                except Exception as e:
                    id_check[m] = str(e)[:200]
            try:
                lm = await client.get("https://api.anthropic.com/v1/models", params={"limit": 100},
                                      headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}, timeout=30)
                listed = [x.get("id") for x in lm.json().get("data", [])] if lm.status_code == 200 else [f"HTTP {lm.status_code}"]
            except Exception as e:
                listed = [f"error {type(e).__name__}"]
            if id_check.get(GENERATOR) != "ok":
                return {"id_check": id_check, "models_listed": listed, "note": "generator model rejected; fix ids and rerun"}

            generated = await asyncio.gather(*[gen(a) for a in abstracts])
            items = [it for grp in generated for it in grp]
            random.Random(1).shuffle(items)
            gen_usd = spend["usd"]

            # 3. Judge with the production prompt and batching -----------------------------------
            results = {}

            async def judge(model):
                preds = [None] * len(items)
                nonlocal_unparsed = []
                toks_in = toks_out = 0
                lats, errors, seen_models = [], [], set()
                stops = Counter()
                refusals = []
                unparsed_calls = 0
                bsem = asyncio.Semaphore(4)

                async def one(start):
                    nonlocal toks_in, toks_out
                    batch = items[start:start + BATCH]
                    pairs = [(ca.ClaimCitation(claim_sentence=it["claim"], ref_keys=["1"]),
                              ca.SourceAbstract(ref_key="1", status="ok", text=it["abstract"]["text"])) for it in batch]
                    async with bsem:
                        try:
                            raw, u, secs, echoed, stop = await _call(client, model, ca._ASSESS_SYSTEM,
                                                                     ca._build_assess_prompt(pairs), JUDGE_MAX_TOKENS, spend)
                        except Exception as e:
                            errors.append(str(e)[:200])
                            return
                    toks_in += u.get("input_tokens", 0); toks_out += u.get("output_tokens", 0)
                    lats.append(secs); seen_models.add(echoed); stops[stop[0]] += 1
                    if stop[0] == "refusal":
                        refusals.append({"details": stop[1], "fields": [it["abstract"]["field"] for it in batch],
                                         "labels": [it["label"] for it in batch], "out_tokens": u.get("output_tokens")})
                    parsed = _parse_json_findings(raw)
                    if not parsed:
                        nonlocal_unparsed.append(1)
                    by_index = {int(o.get("index", -1)): o for o in parsed if isinstance(o, dict) and str(o.get("index", "")).lstrip("-").isdigit()}
                    for i in range(len(batch)):
                        o = by_index.get(i)
                        if o is not None:
                            preds[start + i] = ca._clamp_verdict(o.get("verdict"))

                await asyncio.gather(*[one(s) for s in range(0, len(items), BATCH)])
                return model, preds, toks_in, toks_out, lats, errors, seen_models, stops, len(nonlocal_unparsed), refusals

            outs = await asyncio.gather(*[judge(m) for m in CANDIDATES])

            # 3b. What happens at the PRODUCTION output cap (1500 tokens)? First three batches per model.
            async def cap_check(model):
                res = {"batches": 0, "stop_reasons": Counter(), "parsed_items": 0, "out_tokens": []}
                for start in range(0, min(len(items), 3 * BATCH), BATCH):
                    batch = items[start:start + BATCH]
                    pairs = [(ca.ClaimCitation(claim_sentence=it["claim"], ref_keys=["1"]),
                              ca.SourceAbstract(ref_key="1", status="ok", text=it["abstract"]["text"])) for it in batch]
                    try:
                        raw, u, _, _, stop = await _call(client, model, ca._ASSESS_SYSTEM, ca._build_assess_prompt(pairs), 1500, spend)
                    except Exception as e:
                        res["error"] = str(e)[:160]; break
                    res["batches"] += 1; res["stop_reasons"][stop[0]] += 1; res["out_tokens"].append(u.get("output_tokens"))
                    res["parsed_items"] += len([o for o in _parse_json_findings(raw) if isinstance(o, dict)])
                res["stop_reasons"] = dict(res["stop_reasons"])
                return model, res

            cap_results = dict(await asyncio.gather(*[cap_check(m) for m in CANDIDATES]))

            # 4. Report --------------------------------------------------------------------------
            truth = [it["label"] for it in items]
            classes = list(LABELS.values())
            report = {"id_check": id_check, "models_listed": listed, "gen_errors": gen_errors[:3], "n_abstracts": len(abstracts), "n_items": len(items), "generation_usd": round(gen_usd, 3),
                      "fields": dict(Counter(a["field"] for a in abstracts).most_common(8)), "models": {}}
            for model, preds, ti, to, lats, errors, seen, stops, n_unparsed, refusals in outs:
                answered = [(t, p) for t, p in zip(truth, preds) if p is not None]
                acc = sum(t == p for t, p in answered) / max(1, len(answered))
                recall = {c: round(sum(1 for t, p in answered if t == c and p == c) / max(1, sum(1 for t, _ in answered if t == c)), 3) for c in classes}
                conf = defaultdict(Counter)
                for t, p in answered:
                    conf[t][p] += 1
                supported = [p for t, p in answered if t == "Supported"]
                false_flag = sum(1 for p in supported if p != "Supported") / max(1, len(supported))
                bad = [(t, p) for t, p in answered if t != "Supported"]
                caught = sum(1 for t, p in bad if p != "Supported") / max(1, len(bad))
                pin, pout = PRICES[model]
                report["models"][model] = {
                    "echoed_model": sorted(seen), "stop_reasons": dict(stops), "refusals": refusals[:6], "calls_with_no_parseable_json": n_unparsed, "judge_max_tokens": JUDGE_MAX_TOKENS, "effort": EFFORT, "answered": len(answered), "unparsed_or_failed": len(items) - len(answered),
                    "errors": errors[:2], "accuracy": round(acc, 3), "recall": recall,
                    "false_flag_rate_on_supported": round(false_flag, 3), "problem_detection_recall": round(caught, 3),
                    "contradicted_recall": recall["Contradicted"],
                    "confusion": {t: dict(c) for t, c in conf.items()},
                    "tokens_in": ti, "tokens_out": to,
                    "usd_for_run": round((ti * pin + to * pout) / 1e6, 4),
                    "usd_per_100_pairs": round(((ti * pin + to * pout) / 1e6) / max(1, len(answered)) * 100, 4),
                    "median_batch_seconds": round(statistics.median(lats), 1) if lats else None,
                }
            # agreement between models on the pairs both answered
            ids = [o[0] for o in outs]
            pm = {o[0]: o[1] for o in outs}
            report["agreement_with_fable"] = {
                m: round(sum(1 for a, b in zip(pm["claude-fable-5"], pm[m]) if a is not None and a == b) / max(1, sum(1 for a in pm["claude-fable-5"] if a is not None)), 3)
                for m in ids if m != "claude-fable-5"}
            report["production_cap_check_1500_tokens"] = cap_results
            report["total_usd"] = round(spend["usd"], 2)
            report["samples"] = [{"label": it["label"], "claim": it["claim"], "abstract_start": it["abstract"]["text"][:160]}
                                 for it in items[:6]]
            return report

    return asyncio.run(main())


@stub.local_entrypoint()
def entry():
    import json
    models = [m for m in os.environ.get("BENCH_MODELS", "").split(",") if m] or None
    print(json.dumps(run.remote(n_abstracts=int(os.environ.get("N_ABSTRACTS", N_ABSTRACTS)), models=models,
                                judge_cap=int(os.environ.get("JUDGE_MAX_TOKENS", JUDGE_MAX_TOKENS)),
                                budget_usd=float(os.environ.get("BENCH_BUDGET_USD", BUDGET_USD)),
                                effort=os.environ.get("BENCH_EFFORT") or None), indent=1))
