"""Modal app for the purplelink LaTeX tools backend."""
import datetime
import logging
import os

import modal

logger = logging.getLogger(__name__)

from latextools import core

app = modal.App("purplelink-latextools")

# Pinned TeX Live + toolchain image.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "texlive-latex-recommended",
        "texlive-latex-extra",
        "texlive-fonts-recommended",
        "texlive-xetex",
        "latexmk",
        "latexdiff",
        "biber",
        "pandoc",
    )
    .apt_install("poppler-utils")
    .apt_install("ghostscript")
    .pip_install(
        "fastapi[standard]==0.115.2",
        "python-docx==1.1.2",
        "lxml==5.3.0",
        "bibtexparser>=1.3,<2",
        "httpx==0.27.2",
        "markitdown[pdf,docx,pptx,xlsx]==0.1.6",
        # Paper Review (paid) tool deps
        "pdfplumber>=0.11,<1",
        "pdf2image>=1.17,<2",
        "pillow>=10,<12",
        "pypdf>=4.3,<6",   # PDF annotation rendering
    )
    # Append paranoid hardening to the texmf config via the Debian texmf.d
    # mechanism, then verify it took effect at build time (fail the build if not).
    .add_local_file("texmf.cnf", "/etc/texmf/texmf.d/99-hardening.cnf", copy=True)
    .run_commands(
        "update-texmf",
        "test \"$(kpsewhich -var-value=openin_any)\" = p",
        "test \"$(kpsewhich -var-value=shell_escape)\" = f",
    )
    .add_local_python_source("latextools")
)

# Isolated JVM image for the free PDF-structure tool. The opendataloader-pdf
# PyPI package bundles the CLI JAR (Apache-2.0 v2.x) + LICENSE/NOTICE/
# THIRD_PARTY; we add only a JRE for it to shell out to. Kept separate from
# `image` above so the other free tools' cold starts stay unaffected. Pinned
# >= 2.0 so the core stays Apache-2.0 (pre-2.0 was MPL).
opendataloader_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("openjdk-17-jre-headless")
    .pip_install("opendataloader-pdf>=2.4,<3")
    .run_commands(
        "java -version",
        # Fail the build loudly if the bundled JAR is missing.
        "python -c \"import opendataloader_pdf, glob, os; "
        "p=os.path.dirname(opendataloader_pdf.__file__); "
        "assert glob.glob(os.path.join(p,'jar','*.jar')), 'bundled JAR missing'\"",
    )
    .add_local_python_source("latextools")
)

# Persistent, low-volume counter store for rate limiting.
rate_dict = modal.Dict.from_name("latextools-rate", create_if_missing=True)

# ---- Paid-tool persistent storage ----------------------------------------
# Single shared token store across all paid products (Paper Review, Cover
# Letter, Anonymity Check, Citation Gap, Revision, Response Review, Volume
# Packs). Each token carries its `product` field so the submit endpoint can
# dispatch correctly. Keys are session_id from Stripe.
#   paper_tokens_dict[session_id]       = { tokens: [token, ...], product, redeemed: bool, ... }
#   paper_jobs_dict[token]              = pipeline progress / result dict
#   paper_token_claims_dict[token]      = True (written once, atomically, to
#                                          gate concurrent /submit races)
#   paper_token_index_dict[token]       = session_id (reverse index so token
#                                          lookups are O(1) instead of a full
#                                          scan of paper_tokens_dict)
paper_tokens_dict = modal.Dict.from_name("paper-review-tokens", create_if_missing=True)
paper_jobs_dict = modal.Dict.from_name("paper-review-jobs", create_if_missing=True)
paper_token_claims_dict = modal.Dict.from_name("paper-review-token-claims", create_if_missing=True)
paper_token_index_dict = modal.Dict.from_name("paper-review-token-index", create_if_missing=True)

# Permanent per-job cost ledger — unlike paper_jobs_dict (deleted on first
# status read, by design, for data minimization), this never expires. Keyed
# uniquely per job so concurrent writes never race on a shared list. Written
# once, right after a job finishes (success or failure), by both pipeline
# functions below. Used to calibrate pricing against real Anthropic usage —
# see docs/paper-review-runbook.md "Cost & margin tracking".
#   usage_ledger_dict["<token[:16]>_<finished_at>"] = {
#       ts, product, tier, status, price_charged_usd,
#       input_tokens, output_tokens, cost_usd, models,
#   }
usage_ledger_dict = modal.Dict.from_name("paper-review-usage-ledger", create_if_missing=True)

# Lifecycle email automation — post-purchase tips/review-request/win-back
# sequence, driven entirely by lifecycle_email_sweep() below.
#   customer_lifecycle_dict[session_id] = {
#       email, manuscript_title, purchased_at, last_stage_sent, last_sent_at,
#   }
#   lifecycle_optout_dict[email] = True   # written by /lifecycle/unsubscribe
customer_lifecycle_dict = modal.Dict.from_name("paper-review-lifecycle", create_if_missing=True)
lifecycle_optout_dict = modal.Dict.from_name("paper-review-lifecycle-optout", create_if_missing=True)

# Co-author exposure referral loop — a Paper Review buyer's completed
# report carries a personal referral code in its footer (see
# _referral_footer_md below). If a co-author they shared it with buys a
# review using that code AND a .edu email, both sides get a one-time $2
# credit (see _credit_referral). referral_dict maps code -> the original
# purchaser's email; codes only become live once that purchaser's own
# review completes (see paper_review_pipeline._run), since you can't share
# a code from a report you don't have yet.
referral_dict = modal.Dict.from_name("paper-review-referral", create_if_missing=True)

# Module-level (not just a local inside web()) so the scheduled sweep below
# can reference the same constant instead of hardcoding a second copy of
# the TTL.
PAPER_JOB_TTL_SECONDS = 24 * 3600          # 24h before stale jobs expire

# How long a completed review stays retrievable *after* it has first been
# successfully delivered. Protects against a refresh, a second tab, or a
# dropped response (backgrounded mobile tab, laptop sleep, flaky wifi)
# losing the only copy of a paid result. Short enough that we're not
# meaningfully "storing" reviews, long enough to cover a re-poll or a user
# noticing a blank tab and reloading it.
PAPER_RESULT_GRACE_SECONDS = 30 * 60       # 30 minutes after first delivery

# Secrets — create via:
#   modal secret create anthropic-secret      ANTHROPIC_API_KEY="sk-ant-..."
#   modal secret create paper-review-shared   BACKEND_WEBHOOK_SECRET="<random>"
#   modal secret create stripe-secret         STRIPE_SECRET_KEY="sk_live_..."
#   modal secret create resend-secret         RESEND_API_KEY="re_..."
anthropic_secret = modal.Secret.from_name("anthropic-secret")
paper_review_shared_secret = modal.Secret.from_name("paper-review-shared")
stripe_secret = modal.Secret.from_name("stripe-secret")
subscribe_secret = modal.Secret.from_name("subscribe-secret")
resend_secret = modal.Secret.from_name("resend-secret")

# Product catalog — single source of truth shared between the webhook
# (which maps Stripe price_id → product), the register-token endpoint
# (which mints the right number of tokens per pack), and the submit
# endpoints (which dispatch to the right pipeline). Each entry can be
# overridden by env vars at deploy time but the keys themselves are
# stable.
#
# MAX_PACK_QTY is a defensive upper bound on "qty" for any catalog entry.
# Today qty is only ever 1, 5, or 20 (static, not attacker-controlled), but
# register-token mints `qty` tokens synchronously and emails them all in one
# HTML message, so if qty is ever sourced from an env var override or a
# future admin-configurable pack size, an unbounded value could blow up the
# webhook (timeout, oversized email, Resend rejection). Enforced where qty
# is consumed in paper_review_register_token below.
MAX_PACK_QTY = 100
PAID_PRODUCTS: dict[str, dict] = {
    # Repriced 2026-07-03 for the Sonnet 4.5 -> Fable 5 model upgrade (see
    # DEFAULT_MODEL in latextools/papercheck.py). Fable 5 is ~$10/$50 per
    # MTok vs. Sonnet 4.5's $3/$15, and its newer tokenizer produces ~30%
    # more tokens for the same text — roughly 4.3x the COGS per review.
    # Prices below are sized off comment-estimated token counts (no real
    # usage data existed yet at repricing time) to leave a modest ~15-30%
    # margin after Anthropic + Stripe fees. Once backend/app.py's
    # usage_ledger_dict has real per-job cost data (see _write_usage_ledger),
    # revisit these against actual COGS — see docs/paper-review-runbook.md
    # "Cost & margin tracking".
    "paper-review-standard":    {"category": "paper-review", "tier": "standard", "qty": 1, "amount": 900, "bundled_anonymity": True},
    "paper-review-journal":     {"category": "paper-review", "tier": "standard", "qty": 1, "amount": 1100, "bundled_anonymity": True, "bundled_journal": True},
    "paper-review-deep":        {"category": "paper-review", "tier": "deep",     "qty": 1, "amount": 1500, "bundled_anonymity": True, "bundled_journal": True},
    # Volume packs (mint N tokens of standard Paper Review). ~15-17% off vs.
    # buying à la carte at $9 each.
    "paper-review-pack-5":      {"category": "paper-review", "tier": "standard", "qty": 5,  "amount": 3800},
    "paper-review-pack-20":     {"category": "paper-review", "tier": "standard", "qty": 20, "amount": 15000},
    # Auxiliary paid tools — single/few-call pipelines, cheap even at Fable
    # rates, so these carry a wide margin rather than a thin one.
    "cover-letter":             {"category": "cover-letter", "qty": 1, "amount": 200},
    "anonymity-check":          {"category": "anonymity-check", "qty": 1, "amount": 200},
    "citation-gap":             {"category": "citation-gap", "qty": 1, "amount": 300},
    "revision-review":          {"category": "revision-review", "qty": 1, "amount": 200},
    "response-review":          {"category": "response-review", "qty": 1, "amount": 600},
}

ALLOWED_ORIGINS = [
    "https://purplelink.llc",
    "https://www.purplelink.llc",
]
# Allow the local dev origin only when explicitly opted in, so production does
# not advertise a cross-origin surface it never needs.
if os.environ.get("ALLOW_LOCAL_CORS") == "1":
    ALLOWED_ORIGINS.append("http://localhost:4200")


def _write_usage_ledger(token: str, product_key: str, status: str, usage) -> None:
    """Persist a permanent per-job cost record. `usage` is a
    papercheck.UsageTracker collected around the job's LLM calls (may have
    zero records if the job errored before any call). Never raises — a
    logging failure must not take down the pipeline."""
    import time as _time

    entry = PAID_PRODUCTS.get(product_key, {})
    record = {
        "ts": _time.time(),
        "product_key": product_key,
        "status": status,
        "price_charged_usd": entry.get("amount", 0) / 100.0,
        "input_tokens": usage.total_input_tokens,
        "output_tokens": usage.total_output_tokens,
        "cost_usd": round(usage.total_cost_usd, 4),
        "models": usage.models_used(),
    }
    try:
        usage_ledger_dict[f"{token[:16]}_{record['ts']}"] = record
        logger.info("usage_ledger %s", record)
    except Exception:
        logger.exception("usage_ledger write failed for token=%s", token[:12])


def _reissue_token_on_failure(token: str) -> str | None:
    """Mint and register a replacement token for a job that failed *after*
    the original token was consumed (spawn succeeded, but the pipeline body
    itself later raised — LLM/API outage, PDF parse crash, timeout, etc.).

    Spawn-before-consume (see `_consume_token` callers in the /submit
    handlers) already protects the "spawn never happened" case by leaving
    the token redeemable. This covers the remaining charged-without-result
    gap: once spawned, a mid-pipeline crash left the customer with a spent
    token and only a manual-support-email path. Since `paper_tokens_dict`
    is a module-level Modal Dict, it's reachable from inside these
    `@app.function`-decorated pipelines, not just the web() route handlers.

    Returns the new token string on success, or None if the token's owning
    session couldn't be found or the write failed (never raises — this must
    not affect the error status already being persisted for the job).
    """
    import secrets as _secrets
    import time as _time

    try:
        session_id = paper_token_index_dict.get(token)
        if not session_id:
            for _sid, _entry in list(paper_tokens_dict.items()):
                if isinstance(_entry, dict) and token in (_entry.get("tokens") or []):
                    session_id = _sid
                    break
        if not session_id:
            return None

        entry = paper_tokens_dict.get(session_id)
        if not isinstance(entry, dict):
            return None

        new_token = _secrets.token_urlsafe(32)
        tokens = list(entry.get("tokens") or [])
        tokens.append(new_token)
        entry["tokens"] = tokens
        # Explicitly NOT added to consumed_tokens — it's redeemable.
        entry["last_reissued_at"] = _time.time()
        paper_tokens_dict[session_id] = entry
        paper_token_index_dict[new_token] = session_id
        return new_token
    except Exception:
        logger.exception("token reissue failed for token=%s", token[:12])
        return None


def _paper_referral_code(email: str) -> str:
    """Deterministic per-email referral code, namespaced separately from
    the lifecycle-unsubscribe token (see _lifecycle_unsubscribe_token in
    web()) and the digest's own referral code — same SUBSCRIBE_SECRET
    reuse pattern, different namespace prefix, so none of these can be
    used to derive each other."""
    import hashlib as _hashlib
    import hmac as _hmac_local
    secret = os.environ.get("SUBSCRIBE_SECRET", "")
    return _hmac_local.new(
        secret.encode(), f"paper-referral:{email}".encode(), _hashlib.sha256
    ).hexdigest()[:10]


def _referral_footer_md(email: str) -> str:
    """Quiet, one-line footer appended to a completed Paper Review report
    (see paper_review_pipeline._run below). Deliberately not a banner or
    a repeated pitch — the report itself is the value; this is one line at
    the very end for a co-author reading a shared copy to notice."""
    code = _paper_referral_code(email)
    link = f"https://purplelink.llc/tools/paper-review/?ref={code}"
    return (
        f"\n\n---\n\n*Reviewed with [Purplelink Paper Review]({link}). "
        f".edu referrals earn both of you a $2 credit.*\n"
    )


async def _mint_referral_promo_code(client, email: str) -> str | None:
    """Create a single-use Stripe promotion code against the shared
    'purplelink-referral-2usd' coupon (see backend/setup_referral_coupon.py)
    for one recipient. Returns the code string, or None on failure — a
    failed mint should log and skip that recipient's email, not crash the
    whole crediting flow for both sides."""
    import secrets as _secrets

    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        logger.warning("_mint_referral_promo_code: STRIPE_SECRET_KEY not set")
        return None
    code = "REFER-" + _secrets.token_hex(4).upper()
    try:
        resp = await client.post(
            "https://api.stripe.com/v1/promotion_codes",
            auth=(stripe_key, ""),
            data={
                # This account's Stripe API version (2026-06-24.dahlia)
                # nests the coupon reference under promotion[...] rather
                # than a flat "coupon" field — verified live against a
                # 400 parameter_unknown error before landing this.
                "promotion[type]": "coupon",
                "promotion[coupon]": "purplelink-referral-2usd",
                "code": code,
                "max_redemptions": "1",
                "metadata[recipient_email]": email[:200],
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json().get("code", code)
    except Exception:
        logger.exception("_mint_referral_promo_code failed for %s", email[:40])
        return None


async def _credit_referral(referrer_email: str, referee_email: str) -> None:
    """Best-effort: mint a promo code for each side and email it. Called
    from paper_review_register_token after a new purchase's payload names
    a valid, live referral_code and a .edu buyer email — see the call site
    for the eligibility checks. Never raises; a failure here must not
    affect the purchase that's already been charged and registered."""
    import httpx

    from latextools import delivery

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            referrer_code = await _mint_referral_promo_code(client, referrer_email)
            referee_code = await _mint_referral_promo_code(client, referee_email)

            if referrer_code:
                await delivery.send_email(
                    client, to=referrer_email,
                    subject="You've got a referral credit",
                    html=delivery.html_referral_credit(
                        promo_code=referrer_code,
                        reason="A colleague you referred bought a Paper Review with a .edu email.",
                    ),
                    tags=[{"name": "referral", "value": "referrer"}],
                )
            if referee_code:
                await delivery.send_email(
                    client, to=referee_email,
                    subject="You've got a referral credit",
                    html=delivery.html_referral_credit(
                        promo_code=referee_code,
                        reason="Thanks for using a referral link with your .edu email.",
                    ),
                    tags=[{"name": "referral", "value": "referee"}],
                )
    except Exception:
        logger.exception("_credit_referral failed for %s -> %s", referrer_email[:40], referee_email[:40])


# ---------------------------------------------------------------------------
# Paper Review pipeline (paid tool) — heavy multi-Sonnet orchestration.
#
# Lives in its own Modal function so it gets a fatter resource envelope
# (longer timeout, more memory) than the free-tool ASGI app needs. The web()
# function uses .spawn() to fire-and-forget this function; the pipeline
# itself writes progress + final result into paper_jobs_dict, and the
# polling endpoint just reads from that dict.
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    timeout=900,         # 15 min cap — deep tier can take 10+ min
    cpu=2.0,
    memory=4096,
    max_containers=4,
    secrets=[anthropic_secret, resend_secret],
)
def paper_review_pipeline(
    token: str,
    pdf_bytes: bytes,
    domain: str,
    *,
    tier: str = "standard",
    journal_key: str = "",
    anonymity_check: bool = False,
    deliver_email: str = "",
) -> None:
    """Run the full Paper Review pipeline (any tier) and persist to dict."""
    import asyncio as _asyncio
    import time as _time
    import httpx

    from latextools import papercheck, journals, delivery

    journal_pack = journals.JOURNAL_SPECS.get(journal_key) if journal_key else None
    product_key = "paper-review-deep" if tier == "deep" else ("paper-review-journal" if journal_key else "paper-review-standard")

    def _persist(progress) -> None:
        d = progress.to_dict()
        if progress.status != "done":
            d["result_md"] = None
            d["result_pdf_b64"] = None
            d["annotated_pdf_b64"] = None
        paper_jobs_dict[token] = d

    async def _run():
        with papercheck.UsageTracker() as usage:
            try:
                final = await papercheck.run_review_pipeline(
                    pdf_bytes, domain=domain, on_progress=_persist,
                    tier=tier,
                    journal_pack=journal_pack,
                    anonymity_check=anonymity_check,
                )
                job_status = "done" if final.get("result_md") else "error"
                replacement_token = None
                if job_status == "error":
                    # run_review_pipeline (and its AI-SCoRe delegate) can land on
                    # status="error" via a normal return — extraction_failed,
                    # empty_manuscript, L4-synthesis-failure — without raising.
                    # The token was still spawned/consumed, so treat this the
                    # same as the except-Exception crash path below.
                    replacement_token = _reissue_token_on_failure(token)
                elif deliver_email and final.get("result_md"):
                    # Register this buyer's referral code and append the
                    # quiet footer now that they actually have a report to
                    # share — see referral_dict's docstring above.
                    try:
                        referral_dict[_paper_referral_code(deliver_email)] = deliver_email
                        final["result_md"] += _referral_footer_md(deliver_email)
                    except Exception:
                        logger.exception("referral footer/registration failed for token=%s", token[:12])
                paper_jobs_dict[token] = {
                    **final,
                    "product": "paper-review",
                    "status": job_status,
                    **({"replacement_token": replacement_token} if job_status == "error" else {}),
                }
                _write_usage_ledger(token, product_key, job_status, usage)
                if deliver_email and final.get("result_md"):
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as ec:
                            _email_result = await delivery.send_email(
                                ec,
                                to=deliver_email,
                                subject="Your Paper Review is ready",
                                html=delivery.html_review_ready(
                                    status_url=f"https://purplelink.llc/tools/paper-review/status/?token={token}",
                                    manuscript_title=(final.get("structure_summary") or {}).get("title", ""),
                                    amount_cents=PAID_PRODUCTS.get(product_key, {}).get("amount", 900),
                                ),
                                tags=[{"name": "product", "value": "paper-review"}],
                            )
                        if _email_result.get("status") != "ok":
                            logger.warning(
                                "paper_review_pipeline delivery email not sent for token=%s: %s",
                                token[:12], _email_result,
                            )
                    except Exception:
                        logger.exception("paper_review_pipeline delivery email failed for token=%s", token[:12])
            except Exception:
                logger.exception("paper_review_pipeline failed for token=%s", token[:12])
                replacement_token = _reissue_token_on_failure(token)
                paper_jobs_dict[token] = {
                    "status": "error",
                    "error": "pipeline_failed",
                    "finished_at": _time.time(),
                    "replacement_token": replacement_token,
                }
                _write_usage_ledger(token, product_key, "error", usage)

    _asyncio.run(_run())


@app.function(
    image=image,
    timeout=600,
    cpu=1.0,
    memory=3072,
    max_containers=4,
    secrets=[anthropic_secret, resend_secret],
)
def adjacent_tool_pipeline(
    token: str,
    product: str,
    pdf_bytes: bytes = b"",
    *,
    journal_name: str = "",
    custom_note: str = "",
    original_review_md: str = "",
    reviewer_comments: str = "",
    author_response: str = "",
    abstract_only: str = "",
    title_only: str = "",
    deliver_email: str = "",
) -> None:
    """Single dispatcher for cover-letter, anonymity-check, citation-gap,
    revision-review, response-review jobs. The product field decides which
    pipeline runs; all of them write progress + result into paper_jobs_dict
    keyed by token."""
    import asyncio as _asyncio
    import base64 as _base64
    import time as _time
    import httpx

    from latextools import papercheck, paperreview_extras, response_review, delivery

    def _persist(progress_dict: dict) -> None:
        paper_jobs_dict[token] = progress_dict

    async def _run():
      with papercheck.UsageTracker() as usage:
        try:
            if product == "cover-letter":
                # Cover letter uses pasted abstract + journal only — privacy-
                # preserving design (no full PDF retained).
                struct = papercheck.PaperStructure(
                    title=title_only or "",
                    abstract=abstract_only or "",
                )
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 30,
                    "stage": "drafting", "product": product,
                    "started_at": _time.time(),
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
                ) as client:
                    res = await paperreview_extras.run_cover_letter(
                        client, struct, journal_name or "the target journal",
                        custom_note=custom_note,
                    )
                paper_jobs_dict[token] = {
                    "status": "done" if res.get("status") == "ok" else "error",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": res.get("text", ""),
                    "finished_at": _time.time(),
                }

            elif product in ("anonymity-check", "citation-gap"):
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 15,
                    "stage": "extracting", "product": product,
                    "started_at": _time.time(),
                }
                struct = papercheck.extract_paper(pdf_bytes)
                paper_jobs_dict[token] = {
                    **paper_jobs_dict[token],
                    "progress_pct": 50, "stage": "analysing",
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
                ) as client:
                    if product == "anonymity-check":
                        res = await paperreview_extras.run_anonymity_check(
                            client, struct,
                        )
                        md = _format_anonymity_md(res)
                    else:
                        res = await paperreview_extras.run_citation_gap(client, struct)
                        md = _format_citation_gap_md(res)
                paper_jobs_dict[token] = {
                    "status": "done" if res.get("status") == "ok" else "error",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": md,
                    "error": "" if res.get("status") == "ok" else "analysis_failed",
                    "raw": res,
                    "finished_at": _time.time(),
                }

            elif product == "revision-review":
                paper_jobs_dict[token] = {
                    "status": "running", "progress_pct": 15,
                    "stage": "extracting", "product": product,
                    "started_at": _time.time(),
                }
                struct = papercheck.extract_paper(pdf_bytes)
                paper_jobs_dict[token] = {
                    **paper_jobs_dict[token],
                    "progress_pct": 50, "stage": "comparing",
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
                ) as client:
                    res = await paperreview_extras.run_revision_review(
                        client, struct, original_review_md or "",
                    )
                # run_revision_review distinguishes "mismatch" (pasted review
                # has no Rectification Checklist, or doesn't match this
                # manuscript) from a hard "error". Both collapse to job
                # status "error" here, but mismatch carries a specific,
                # already customer-safe message — prefix it so the frontend
                # (status.js friendlyError) can surface it verbatim instead
                # of falling back to a generic message.
                res_error = res.get("error", "")
                if res.get("status") == "mismatch" and res_error:
                    res_error = "revision_mismatch:" + res_error
                paper_jobs_dict[token] = {
                    "status": "done" if res.get("status") == "ok" else "error",
                    "progress_pct": 100,
                    "stage": "done",
                    "product": product,
                    "result_md": res.get("markdown", ""),
                    "error": res_error,
                    "finished_at": _time.time(),
                }

            elif product == "response-review":
                def _emit(progress) -> None:
                    paper_jobs_dict[token] = {
                        "status": progress.status,
                        "progress_pct": progress.progress_pct,
                        "stage": progress.stage,
                        "product": product,
                        "started_at": progress.started_at,
                        "result_md": progress.result_md if progress.status == "done" else None,
                    }
                final = await response_review.run_response_review(
                    pdf_bytes, reviewer_comments or "", author_response or "",
                    on_progress=_emit,
                )
                paper_jobs_dict[token] = {
                    **final, "product": product,
                }
            else:
                paper_jobs_dict[token] = {
                    "status": "error",
                    "error": f"unknown_product:{product}",
                    "finished_at": _time.time(),
                }
                return

            if paper_jobs_dict[token].get("status") == "error":
                # Every branch above can land on status="error" via a normal
                # return (analysis_failed, extraction exceptions caught deeper
                # in paperreview_extras/response_review, etc.) without this
                # try block itself raising. The token was already consumed,
                # so reissue here too — mirrors the except-Exception path below.
                paper_jobs_dict[token] = {
                    **paper_jobs_dict[token],
                    "replacement_token": _reissue_token_on_failure(token),
                }

            _write_usage_ledger(token, product, paper_jobs_dict[token].get("status", "unknown"), usage)

            if deliver_email:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as ec:
                        _email_result = await delivery.send_email(
                            ec, to=deliver_email,
                            subject=f"Your {product.replace('-', ' ').title()} is ready",
                            html=delivery.html_review_ready(
                                status_url=f"https://purplelink.llc/tools/paper-review/status/?token={token}&product={product}",
                                amount_cents=PAID_PRODUCTS.get(product, {}).get("amount", 900),
                            ),
                            tags=[{"name": "product", "value": product}],
                        )
                    if _email_result.get("status") != "ok":
                        logger.warning(
                            "adjacent_tool_pipeline delivery email not sent for token=%s product=%s: %s",
                            token[:12], product, _email_result,
                        )
                except Exception:
                    logger.exception("adjacent_tool_pipeline delivery email failed for token=%s product=%s", token[:12], product)
        except Exception:
            logger.exception("adjacent_tool_pipeline failed for token=%s product=%s", token[:12], product)
            replacement_token = _reissue_token_on_failure(token)
            paper_jobs_dict[token] = {
                "status": "error",
                "error": "pipeline_failed",
                "finished_at": _time.time(),
                "product": product,
                "replacement_token": replacement_token,
            }
            _write_usage_ledger(token, product, "error", usage)

    _asyncio.run(_run())


def _format_anonymity_md(res: dict) -> str:
    """Render the anonymity-check JSON result as a user-facing Markdown
    report. Lives here rather than in paperreview_extras so the module
    stays a pure async helper."""
    leaks = res.get("leaks", []) or []
    if not leaks:
        return (
            "# Anonymity Check\n\n"
            "**Result: no concrete leaks detected.**\n\n"
            "We scanned the manuscript body and abstract for author "
            "names, institution names, funding/grant numbers, IRB or "
            "ethics-board protocol numbers, named software or datasets, "
            "and author-owned URLs. No identifying information was "
            "flagged.\n\n"
            "This does not guarantee a fully blinded submission — please "
            "still review your acknowledgements, figures, and supplementary "
            "materials manually.\n"
        )
    parts = [
        "# Anonymity Check\n",
        f"**Result: {len(leaks)} potential leak"
        f"{'s' if len(leaks) != 1 else ''} detected.**\n",
        "Each item below should be removed or generalised before "
        "double-blind submission.\n",
    ]
    by_cat: dict[str, list] = {}
    for l in leaks:
        cat = l.get("category", "other")
        by_cat.setdefault(cat, []).append(l)
    for cat, items in by_cat.items():
        parts.append(f"\n## {cat.replace('_', ' ').title()}\n")
        for l in items:
            severity = (l.get("severity") or "minor").upper()
            quote = (l.get("quote") or "").replace("\n", " ").strip()[:300]
            where = l.get("where", "")
            fix = l.get("fix", "")
            parts.append(
                f"- **[{severity}]** {where}: \"{quote}\"\n"
                f"  - Fix: {fix}\n"
            )
    return "".join(parts)


def _format_citation_gap_md(res: dict) -> str:
    """Render the citation-gap JSON as user-facing Markdown."""
    gaps = res.get("gaps", []) or []
    truncation_note = ""
    if res.get("references_truncated"):
        truncation_note = (
            f"\n**Note:** only the first {res.get('n_references_reviewed', 0)} of "
            f"{res.get('n_references_total', 0)} references in the manuscript's "
            "bibliography were reviewed. Gaps flagged below may already be "
            "cited in the remainder of the reference list — verify before "
            "acting.\n"
        )
    if not gaps:
        if res.get("no_references_extracted"):
            return (
                "# Citation Gap Analysis\n\n"
                "**Result: no reference list was found in this manuscript.**\n\n"
                "We could not extract any references to check the manuscript "
                "against — this usually means the bibliography uses a "
                "non-standard heading, is formatted in a way our extractor "
                "doesn't recognise, or is a scanned/image-only section. This "
                "is NOT a confirmation that the manuscript is well cited; it "
                "means the check had nothing to verify. Please confirm your "
                "manuscript includes a machine-readable reference list and "
                "re-run this check.\n"
                + truncation_note
            )
        return (
            "# Citation Gap Analysis\n\n"
            "**Result: no obvious citation gaps detected.**\n\n"
            "The manuscript's reference list appears to cover the canonical "
            "prior work for its scope. Verify against your own field "
            "knowledge before submission — this check is a sanity net, "
            "not an exhaustive literature search.\n"
            + truncation_note
        )
    parts = [
        "# Citation Gap Analysis\n",
        f"**Result: {len(gaps)} potential gap"
        f"{'s' if len(gaps) != 1 else ''} flagged.**\n",
        "Each entry below is a citation a domain reviewer might expect to "
        "see. Verify each suggestion against your own knowledge before "
        "adding — AI recall can be wrong.\n",
        truncation_note,
    ]
    _VERIFY_LABELS = {
        "confirmed_exists": "Confirmed to exist (CrossRef match)",
        "weak_match": "CrossRef found a similar but not confident match",
        "not_found": "Not found on CrossRef — verify manually before citing",
        "crossref_unavailable": "CrossRef lookup failed — unverified",
        "network_error": "CrossRef lookup failed — unverified",
        "not_searched": "No searchable title — AI recall only, unverified",
    }
    for g in gaps:
        gap_type = g.get("gap_type", "qualitative_gap").replace("_", " ").title()
        topic = g.get("topic", "(no topic)")
        desc = g.get("expected_work_description", "")
        authors = g.get("candidate_authors") or []
        title_hint = g.get("candidate_title_hint", "")
        why = g.get("why_it_matters", "")
        where = g.get("where_in_paper", "")
        author_line = ", ".join(authors) if authors else "(unknown)"
        verification = g.get("verification") or {}
        v_status = verification.get("status", "not_searched")
        v_label = _VERIFY_LABELS.get(v_status, v_status)
        if v_status in ("confirmed_exists", "weak_match") and verification.get("found_doi"):
            v_label += f" — DOI: {verification['found_doi']}"
        parts.append(
            f"\n### {topic}\n"
            f"- **Type:** {gap_type}\n"
            f"- **Suggested authors:** {author_line}\n"
            f"- **Title hint:** {title_hint or '(unknown)'}\n"
            f"- **Verification:** {v_label}\n"
            f"- **What should be cited:** {desc}\n"
            f"- **Why a reviewer would notice:** {why}\n"
            f"- **Section to add it:** {where}\n"
        )
    return "".join(parts)


def _looks_like_abstract(text: str) -> bool:
    """Cheap sanity check that `text` resembles real abstract prose rather
    than gibberish/placeholder input (e.g. "asdf asdf asdf", "test test").
    Not a quality bar — just enough to stop obvious junk from burning a
    paid LLM call. Deliberately permissive: short but real sentences must
    still pass."""
    words = text.split()
    if len(words) < 8:
        return False
    unique_words = {w.strip(".,;:!?()\"'").lower() for w in words}
    unique_words.discard("")
    # Gibberish/placeholder text tends to repeat the same token(s) rather
    # than using varied vocabulary.
    if len(unique_words) < max(4, len(words) // 4):
        return False
    # Real abstracts contain ordinary prose words with vowels; keyboard-mash
    # strings mostly don't.
    alpha_words = [w for w in unique_words if w.isalpha()]
    if not alpha_words:
        return False
    vowelly = [w for w in alpha_words if any(c in "aeiou" for c in w)]
    if len(vowelly) / len(alpha_words) < 0.5:
        return False
    return True


@app.function(
    image=opendataloader_image,
    timeout=120,
    cpu=2.0,
    memory=3072,
    max_containers=4,
)
def pdf_structure_run(pdf_bytes: bytes) -> dict:
    """Run OpenDataLoader (default local mode) on a PDF and return
    {markdown, json, summary}. Ephemeral: writes into a temp dir deleted on
    return. No OCR / hybrid / model. Nothing is retained."""
    import subprocess
    import tempfile
    from pathlib import Path

    import opendataloader_pdf
    from latextools import pdf_structure

    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        workdir = Path(d)
        in_pdf = workdir / "input.pdf"
        out_dir = workdir / "out"
        out_dir.mkdir()
        in_pdf.write_bytes(pdf_bytes)

        kwargs = pdf_structure.safe_convert_kwargs(str(in_pdf), str(out_dir))
        try:
            opendataloader_pdf.convert(**kwargs)
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        except subprocess.CalledProcessError as e:
            return {"error": "parse", "detail": (getattr(e, "stderr", "") or "")[:500]}
        except FileNotFoundError:
            return {"error": "parse", "detail": "java runtime not found"}
        except Exception as e:  # noqa: BLE001 — surface as a generic parse failure
            return {"error": "parse", "detail": f"{type(e).__name__}: {str(e)[:200]}"}

        def _list(_):
            return [str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()]

        def _read_rel(rel):
            return (out_dir / rel).read_text(encoding="utf-8", errors="replace")

        result = pdf_structure.parse_output_dir(out_dir, _read_rel, _list)
        if not result["markdown"] and not result["json"]:
            return {"error": "empty"}
        return result


@app.function(
    image=image,
    timeout=150,
    cpu=1.0,
    memory=2048,
    max_containers=6,
    # Web function needs: shared webhook secret (verify webhook calls),
    # Stripe key (invoice generation endpoint), Resend key (volume-pack
    # token email + invoice email), subscribe secret (HMAC-verifies
    # lifecycle unsubscribe links — reuses the digest's SUBSCRIBE_SECRET,
    # namespaced, rather than minting a new one). Anthropic key is NOT
    # mounted here; only the heavy pipelines need it.
    secrets=[paper_review_shared_secret, stripe_secret, resend_secret, subscribe_secret],
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def web():
    import io
    import tempfile
    from pathlib import Path

    from fastapi import FastAPI, File, Form, Request, UploadFile
    from fastapi.concurrency import run_in_threadpool
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    from latextools import runner

    api = FastAPI()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
    )

    def _client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        peer = request.client.host if request.client else None
        return core.client_ip_from_forwarded(fwd, peer)

    def _enforce_rate_limit(request: Request, bucket: str) -> bool:
        day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        key = core.rate_limit_key(_client_ip(request), day, bucket=bucket)
        allowed, _ = core.check_and_increment(rate_dict, key)
        return allowed

    def _too_large(request: Request, max_bytes: int) -> bool:
        """True when the declared Content-Length already exceeds the cap.

        Rejects oversized uploads before they are read into memory. This is
        an early-out only: a client can omit or understate Content-Length
        (e.g. chunked transfer-encoding), so `_read_capped` below is the
        actual enforcement point.
        """
        raw = request.headers.get("content-length")
        if not raw:
            return False
        try:
            return int(raw) > max_bytes
        except ValueError:
            return False

    class _UploadTooLarge(Exception):
        pass

    async def _read_capped(upload: UploadFile, max_bytes: int) -> bytes:
        """Read an UploadFile without buffering more than max_bytes+1.

        `_too_large` only inspects Content-Length, which a client can omit
        (chunked transfer-encoding) or understate. This reads in bounded
        chunks and aborts as soon as the cap is exceeded, so an oversized
        body is never fully buffered in memory before validation runs.
        """
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise _UploadTooLarge()
        return b"".join(chunks)

    async def _read_upload(upload: UploadFile) -> tuple[str | None, bytes | None]:
        """Return (tex_source, zip_bytes); exactly one is non-None."""
        data = await upload.read()
        fname = upload.filename or ""
        if fname.lower().endswith(".zip"):
            core.validate_zip_upload(fname, len(data))
            return None, data
        core.validate_upload(fname, len(data))
        return data.decode("utf-8", errors="replace"), None

    def _pdf_response(pdf: bytes, filename: str) -> Response:
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    def _result_or_error(res) -> Response:
        if res.timed_out:
            return JSONResponse({"error": "timeout"}, status_code=422)
        if not res.ok:
            return JSONResponse(
                {"error": "compile", "errors": res.errors,
                 "log": res.log[:50_000]},
                status_code=422,
            )
        return None

    @api.post("/compile")
    async def compile_endpoint(
        request: Request,
        file: UploadFile = File(...),
        engine: str = Form("pdflatex"),
    ):
        if not _enforce_rate_limit(request, "compile"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            tex, zip_bytes = await _read_upload(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                if zip_bytes is not None:
                    core.extract_project_zip(zip_bytes, workdir)
                    return runner.run_compile(workdir, None, engine, timeout=120)
                return runner.run_compile(workdir, tex, engine, timeout=60)

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "compiled.pdf")

    @api.post("/diff")
    async def diff_endpoint(
        request: Request,
        old: UploadFile = File(...),
        new: UploadFile = File(...),
        engine: str = Form("pdflatex"),
        legend: str = Form("false"),
    ):
        if not _enforce_rate_limit(request, "diff"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            old_tex, old_zip = await _read_upload(old)
            new_tex, new_zip = await _read_upload(new)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)

                # Set up assets and new.tex.  If new is a project ZIP, extract
                # it so its figures/styles are available for compilation; copy
                # its main.tex to new.tex.
                if new_zip is not None:
                    core.extract_project_zip(new_zip, workdir)
                    new_main = (workdir / "main.tex").read_text(encoding="utf-8")
                    (workdir / "new.tex").write_text(new_main, encoding="utf-8")
                    effective_new = None   # already written
                else:
                    effective_new = new_tex

                # Set up old.tex.  If old is a project ZIP, extract to a
                # temporary subdir and pull out just main.tex.
                if old_zip is not None:
                    old_dir = workdir / "_old"
                    old_dir.mkdir()
                    core.extract_project_zip(old_zip, old_dir)
                    old_main = (old_dir / "main.tex").read_text(encoding="utf-8")
                    (workdir / "old.tex").write_text(old_main, encoding="utf-8")
                    effective_old = None  # already written
                else:
                    effective_old = old_tex

                return runner.run_diff(
                    workdir, effective_old, effective_new, engine, timeout=120,
                    add_legend=(legend == "true"),
                )

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        return _result_or_error(res) or _pdf_response(res.pdf_bytes, "diff.pdf")

    _DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    @api.post("/convert")
    async def convert_endpoint(
        request: Request,
        file: UploadFile = File(...),
        anonymize: str = Form("false"),
        style: str = Form("manuscript"),
    ):
        if not _enforce_rate_limit(request, "convert"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if style not in ("manuscript", "preprint"):
            style = "manuscript"
        try:
            tex, zip_bytes = await _read_upload(file)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                if zip_bytes is not None:
                    core.extract_project_zip(zip_bytes, workdir)
                    return runner.convert_to_manuscript(
                        workdir, None, anonymize=(anonymize == "true"), style=style
                    )
                return runner.convert_to_manuscript(
                    workdir, tex, anonymize=(anonymize == "true"), style=style
                )

        try:
            res = await run_in_threadpool(_do)
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not res.ok:
            return JSONResponse(
                {"error": "convert", "detail": res.error}, status_code=422
            )
        filename = "preprint.docx" if style == "preprint" else "manuscript.docx"
        return Response(
            content=res.docx_bytes,
            media_type=_DOCX_MIME,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # Shared async helpers for bib fetching
    # ------------------------------------------------------------------

    async def _fetch_doi_bib(client, doi: str) -> dict:
        """Fetch BibTeX for a DOI via CrossRef content negotiation."""
        from urllib.parse import quote as _urlquote
        encoded_doi = _urlquote(doi, safe="")
        try:
            resp = await client.get(
                f"https://api.crossref.org/works/{encoded_doi}/transform/application/x-bibtex",
                headers={
                    "User-Agent": "purplelink-bib-builder/1.0 (mailto:ben@purplelink.llc)",
                    "Accept": "application/x-bibtex",
                },
            )
            if resp.status_code == 404:
                return {"id": doi, "type": "doi", "status": "not_found", "bib": None}
            if resp.status_code != 200:
                return {"id": doi, "type": "doi", "status": "error", "bib": None}
            bib = resp.text.strip()
            return {"id": doi, "type": "doi", "status": "ok", "bib": bib}
        except Exception:
            return {"id": doi, "type": "doi", "status": "error", "bib": None}

    async def _fetch_arxiv_bib(client, arxiv_id: str) -> dict:
        """Fetch metadata for an arXiv ID and format as BibTeX."""
        from latextools.bibbuilder import format_arxiv_bib
        try:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={"id_list": arxiv_id, "max_results": "1"},
            )
            if resp.status_code != 200:
                return {"id": arxiv_id, "type": "arxiv", "status": "error", "bib": None}
            bib = format_arxiv_bib(arxiv_id, resp.text)
            if bib is None:
                return {"id": arxiv_id, "type": "arxiv", "status": "not_found", "bib": None}
            return {"id": arxiv_id, "type": "arxiv", "status": "ok", "bib": bib}
        except Exception:
            return {"id": arxiv_id, "type": "arxiv", "status": "error", "bib": None}

    # ------------------------------------------------------------------
    # /word-to-latex — convert .docx to a LaTeX starting point
    # ------------------------------------------------------------------

    @api.post("/word-to-latex")
    async def word_to_latex_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "word-to-latex"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOCX_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 5 MB)."}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_DOCX_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 5 MB)."}, status_code=400)
        try:
            core.validate_docx_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                docx_path = workdir / "input.docx"
                tex_path = workdir / "output.tex"
                docx_path.write_bytes(data)
                proc = _sp.run(
                    ["pandoc", str(docx_path), "-o", str(tex_path),
                     "--wrap=none", "--standalone"],
                    cwd=workdir, capture_output=True, text=True, timeout=60,
                )
                if proc.returncode != 0 or not tex_path.exists():
                    return None, proc.stderr.strip()[:500] or "pandoc failed"
                return tex_path.read_text(encoding="utf-8", errors="replace"), None

        try:
            tex_content, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "convert", "detail": "Conversion timed out."}, status_code=422)
        except (OSError, RuntimeError) as e:
            return JSONResponse({"error": "convert", "detail": "Conversion failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "convert", "detail": err}, status_code=422)
        return Response(
            content=tex_content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="converted.tex"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /render-equation — compile LaTeX math to a PNG image
    # ------------------------------------------------------------------

    @api.post("/render-equation")
    async def render_equation_endpoint(
        request: Request,
        equation: str = Form(...),
        mode: str = Form("display"),
        dpi: int = Form(300),
    ):
        if not _enforce_rate_limit(request, "render-equation"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        equation = equation.strip()
        if not equation:
            return JSONResponse({"error": "invalid", "detail": "Equation is empty."}, status_code=400)
        if len(equation) > 2000:
            return JSONResponse({"error": "invalid", "detail": "Equation is too long (max 2000 chars)."}, status_code=400)
        import re as _re
        _UNSAFE_LATEX = _re.compile(
            r'\\(input|include|openin|openout|read|write|catcode|def|let|newcommand|renewcommand)\b',
            _re.IGNORECASE,
        )
        if _UNSAFE_LATEX.search(equation):
            return JSONResponse({"error": "invalid", "detail": "Equation contains disallowed LaTeX commands."}, status_code=400)
        dpi = max(72, min(dpi, 600))
        if mode not in ("display", "inline"):
            mode = "display"

        math_body = f"\\[{equation}\\]" if mode == "display" else f"${equation}$"
        tex_src = (
            "\\documentclass[border=6pt,preview]{standalone}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{amssymb}\n"
            "\\usepackage{amsfonts}\n"
            "\\begin{document}\n"
            f"{math_body}\n"
            "\\end{document}\n"
        )

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                (workdir / "eq.tex").write_text(tex_src, encoding="utf-8")
                # Compile with pdflatex
                proc = _sp.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                     "-no-shell-escape", "eq.tex"],
                    cwd=workdir, capture_output=True, text=True, timeout=30,
                )
                pdf_path = workdir / "eq.pdf"
                if proc.returncode != 0 or not pdf_path.exists():
                    log = (workdir / "eq.log").read_text(errors="replace") if (workdir / "eq.log").exists() else proc.stdout
                    # Extract first error line for a useful message
                    for line in log.splitlines():
                        if line.startswith("!"):
                            return None, line[1:].strip()[:200]
                    return None, "Equation could not be rendered — check your LaTeX syntax."
                # Convert PDF to PNG with pdftoppm
                png_stem = workdir / "eq"
                conv = _sp.run(
                    ["pdftoppm", "-png", "-r", str(dpi), "-singlefile",
                     str(pdf_path), str(png_stem)],
                    cwd=workdir, capture_output=True, timeout=15,
                )
                png_path = workdir / "eq.png"
                if conv.returncode != 0 or not png_path.exists():
                    stderr = conv.stderr.strip()[:200] if conv.stderr else ""
                    return None, f"Image conversion failed.{(' ' + stderr) if stderr else ''}"
                return png_path.read_bytes(), None

        try:
            png_bytes, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "render", "detail": "Rendering timed out — equation may be too complex."}, status_code=422)
        except Exception as e:
            return JSONResponse({"error": "render", "detail": "An error occurred during rendering."}, status_code=422)
        if err:
            return JSONResponse({"error": "render", "detail": err}, status_code=422)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": 'attachment; filename="equation.png"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /bib-from-ids — build a .bib file from DOIs and arXiv IDs
    # ------------------------------------------------------------------

    @api.post("/bib-from-ids")
    async def bib_from_ids_endpoint(
        request: Request,
        ids: str = Form(...),
    ):
        import asyncio
        import httpx
        from latextools.bibbuilder import parse_ids

        if not _enforce_rate_limit(request, "bib-from-ids"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)

        parsed = parse_ids(ids)
        if not parsed:
            return JSONResponse({"error": "invalid", "detail": "No valid DOIs or arXiv IDs found."}, status_code=400)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        ) as client:
            coros = []
            for kind, clean_id in parsed:
                if kind == "doi":
                    coros.append(_fetch_doi_bib(client, clean_id))
                else:
                    coros.append(_fetch_arxiv_bib(client, clean_id))
            results = await asyncio.gather(*coros, return_exceptions=True)

        entries = []
        for (kind, clean_id), r in zip(parsed, results):
            if isinstance(r, Exception):
                entries.append({"id": clean_id, "type": kind, "status": "error", "bib": None})
            else:
                entries.append(r)

        combined = "\n\n".join(e["bib"] for e in entries if e.get("bib"))
        return JSONResponse({"entries": entries, "combined_bib": combined})

    # ------------------------------------------------------------------
    # /validate-bib — layered BibTeX validator
    # ------------------------------------------------------------------

    async def _doi_check(client, r) -> None:
        if not r.doi:
            return
        try:
            # doi.org is a legitimate redirector, but the redirect target is
            # chosen by the (potentially attacker-controlled) DOI registrant,
            # so we must not blindly follow it (SSRF via open redirect --
            # see the identical guard used for papercheck.py's DOI lookup).
            # _resolve_doi_redirects_safely walks the chain manually and
            # vets every hop with _is_ssrf_safe_url before requesting it.
            from latextools.papercheck import _resolve_doi_redirects_safely
            resp = await _resolve_doi_redirects_safely(client, r.doi)
            r.doi_ok = resp.status_code < 400
            r.doi_status = resp.status_code
        except Exception:
            pass  # network failure / unsafe redirect -> leave doi_ok as None

    async def _crossref_check(client, r) -> None:
        from latextools.bibcheck import author_similarity, title_similarity
        if not r.title:
            return
        params = {
            "query.bibliographic": r.title[:200],
            "query.author": r.author[:100] if r.author else "",
            "rows": "1",
            # Pull everything we need for both verification *and* the
            # corrected-bib output in a single round trip.
            "select": "title,DOI,author,issued,container-title,page,volume,issue,publisher",
            "mailto": "ben@purplelink.llc",
        }
        try:
            resp = await client.get(
                "https://api.crossref.org/works", params=params,
                headers={"User-Agent": "purplelink-bib-validator/1.0 (mailto:ben@purplelink.llc)"},
            )
            if resp.status_code != 200:
                return
            items = resp.json().get("message", {}).get("items", [])
            if not items:
                r.crossref_confidence = 0.0
                return
            item = items[0]
            found_title = (item.get("title") or [""])[0]
            r.crossref_confidence = title_similarity(r.title, found_title)
            r.crossref_title = found_title
            r.crossref_doi = item.get("DOI", "")

            # Authors: CrossRef returns [{given, family, ...}, ...].
            authors_raw = item.get("author") or []
            r.crossref_authors = [
                _crossref_author_string(a) for a in authors_raw if a
            ] or None

            # Year is the first element of issued.date-parts[0].
            issued = item.get("issued") or {}
            parts = (issued.get("date-parts") or [[]])[0]
            if parts and isinstance(parts[0], int):
                r.crossref_year = parts[0]

            # Container title (journal/booktitle) is a list — take the first.
            ct = item.get("container-title") or []
            if ct:
                r.crossref_journal = ct[0]
            r.crossref_volume = item.get("volume") or None
            r.crossref_issue = item.get("issue") or None
            r.crossref_pages = item.get("page") or None
            r.crossref_publisher = item.get("publisher") or None

            # Author comparison (only meaningful when title actually matched).
            if r.author and r.crossref_authors:
                score = author_similarity(r.author, r.crossref_authors)
                if r.author_match is None or score > r.author_match:
                    r.author_match = score
        except Exception:
            pass

    async def _s2_check(client, r) -> None:
        from latextools.bibcheck import author_similarity, title_similarity
        if not r.title:
            return
        params = {
            "query": r.title[:200],
            "fields": "title,authors,year,venue",
            "limit": "1",
        }
        try:
            resp = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params,
            )
            if resp.status_code != 200:
                return
            papers = resp.json().get("data", [])
            if not papers:
                r.s2_confidence = 0.0
                return
            found = papers[0]
            found_title = found.get("title", "")
            r.s2_confidence = title_similarity(r.title, found_title)
            r.s2_title = found_title
            r.s2_year = found.get("year")
            authors = found.get("authors") or []
            r.s2_authors = [a.get("name", "") for a in authors if a.get("name")] or None

            if r.author and r.s2_authors:
                score = author_similarity(r.author, r.s2_authors)
                # Prefer the higher of CrossRef / S2 author scores
                if r.author_match is None or score > r.author_match:
                    r.author_match = score
        except Exception:
            pass

    def _crossref_author_string(author: dict) -> str:
        """Render a CrossRef author object as "Family, Given" if possible."""
        family = (author.get("family") or "").strip()
        given = (author.get("given") or "").strip()
        name = (author.get("name") or "").strip()  # corporate / single-string author
        if family and given:
            return f"{family}, {given}"
        if family:
            return family
        return name

    @api.post("/validate-bib")
    async def validate_bib_endpoint(
        request: Request,
        file: UploadFile = File(...),
        check_doi: str = Form("false"),
        check_crossref: str = Form("false"),
        check_s2: str = Form("false"),
    ):
        import asyncio
        import httpx
        from latextools import bibcheck

        if not _enforce_rate_limit(request, "validate-bib"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_BIB_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 2 MB)."}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_BIB_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 2 MB)."}, status_code=400)
        try:
            core.validate_bib_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        bib_text = data.decode("utf-8", errors="replace")
        results = bibcheck.parse_bib(bib_text)

        do_doi = check_doi == "true"
        do_crossref = check_crossref == "true"
        do_s2 = check_s2 == "true"

        if do_doi or do_crossref or do_s2:
            net = results[: bibcheck.MAX_NETWORK_ENTRIES]
            async with httpx.AsyncClient(timeout=10.0) as client:
                coros = []
                for r in net:
                    if do_doi:
                        coros.append(_doi_check(client, r))
                    if do_crossref:
                        coros.append(_crossref_check(client, r))
                    if do_s2:
                        coros.append(_s2_check(client, r))
                await asyncio.gather(*coros, return_exceptions=True)

        return JSONResponse({
            "entries": [r.to_dict() for r in results],
            "summary": bibcheck.summarize(results),
            "annotated_bib": bibcheck.annotate_bib(bib_text, results),
            "corrected_bib": bibcheck.correct_bib(bib_text, results),
        })

    # ------------------------------------------------------------------
    # /markdown-convert — convert Markdown to PDF or Word via pandoc
    # ------------------------------------------------------------------

    @api.post("/markdown-convert")
    async def markdown_convert_endpoint(
        request: Request,
        text: str = Form(""),
        file: UploadFile = File(None),
        target: str = Form("pdf"),
    ):
        if not _enforce_rate_limit(request, "markdown-convert"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_MD_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "Markdown is too large (max 2 MB)."}, status_code=400)
        if target not in ("pdf", "docx"):
            target = "pdf"

        if file is not None and (file.filename or ""):
            try:
                data = await _read_capped(file, core.MAX_MD_UPLOAD_BYTES)
            except _UploadTooLarge:
                return JSONResponse(
                    {"error": "invalid", "detail": "Markdown is too large (max 2 MB)."}, status_code=400
                )
            try:
                core.validate_md_upload(file.filename or "", len(data))
            except core.ValidationError as e:
                return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
            md_source = data.decode("utf-8", errors="replace")
        else:
            md_source = text
            if len(md_source.encode("utf-8")) > core.MAX_MD_UPLOAD_BYTES:
                return JSONResponse({"error": "invalid", "detail": "Markdown is too large (max 2 MB)."}, status_code=400)

        if not md_source.strip():
            return JSONResponse({"error": "invalid", "detail": "No Markdown content provided."}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                md_path = workdir / "input.md"
                out_path = workdir / f"output.{target}"
                md_path.write_text(md_source, encoding="utf-8")
                cmd = ["pandoc", str(md_path), "-o", str(out_path),
                       "--standalone", "--wrap=none"]
                if target == "pdf":
                    # Pandoc passes raw LaTeX in the Markdown straight through to
                    # pdflatex, so this path is only as safe as the engine's
                    # confinement. Two layers enforce that: the image bakes
                    # openin_any=p / shell_escape=f into texmf.cnf (verified at
                    # build, see image .run_commands above), and we pass
                    # -no-shell-escape explicitly here so \write18 fails closed
                    # even if the global default ever regresses. Absolute/parent
                    # \input/\openin are blocked by openin_any=p.
                    cmd += ["--pdf-engine=pdflatex",
                            "--pdf-engine-opt=-no-shell-escape"]
                proc = _sp.run(
                    cmd, cwd=workdir, capture_output=True, text=True, timeout=90,
                )
                if proc.returncode != 0 or not out_path.exists():
                    return None, proc.stderr.strip()[:500] or "pandoc failed"
                return out_path.read_bytes(), None

        try:
            out_bytes, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "convert", "detail": "Conversion timed out."}, status_code=422)
        except (OSError, RuntimeError):
            return JSONResponse({"error": "convert", "detail": "Conversion failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "convert", "detail": err}, status_code=422)

        if target == "pdf":
            return _pdf_response(out_bytes, "converted.pdf")
        return Response(
            content=out_bytes,
            media_type=_DOCX_MIME,
            headers={
                "Content-Disposition": 'attachment; filename="converted.docx"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # /pdf-compress — shrink a PDF with Ghostscript
    # ------------------------------------------------------------------

    _GS_LEVELS = {
        "screen": "/screen",
        "ebook": "/ebook",
        "printer": "/printer",
        "prepress": "/prepress",
    }

    @api.post("/pdf-compress")
    async def pdf_compress_endpoint(
        request: Request,
        file: UploadFile = File(...),
        level: str = Form("ebook"),
    ):
        if not _enforce_rate_limit(request, "pdf-compress"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PDF_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 20 MB)."}, status_code=400)
        gs_setting = _GS_LEVELS.get(level, "/ebook")
        try:
            data = await _read_capped(file, core.MAX_PDF_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File is too large (max 20 MB)."}, status_code=400)
        try:
            core.validate_pdf_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)

        import subprocess as _sp

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                workdir = Path(d)
                in_path = workdir / "input.pdf"
                out_path = workdir / "output.pdf"
                in_path.write_bytes(data)
                proc = _sp.run(
                    ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                     f"-dPDFSETTINGS={gs_setting}", "-dNOPAUSE", "-dQUIET",
                     "-dBATCH", "-dSAFER", f"-sOutputFile={out_path}", str(in_path)],
                    cwd=workdir, capture_output=True, text=True, timeout=90,
                )
                if proc.returncode != 0 or not out_path.exists():
                    return None, None, proc.stderr.strip()[:500] or "ghostscript failed"
                return out_path.read_bytes(), len(data), None

        try:
            out_bytes, original_size, err = await run_in_threadpool(_do)
        except _sp.TimeoutExpired:
            return JSONResponse({"error": "compress", "detail": "Compression timed out."}, status_code=422)
        except (OSError, RuntimeError):
            return JSONResponse({"error": "compress", "detail": "Compression failed."}, status_code=422)
        if err:
            return JSONResponse({"error": "compress", "detail": err}, status_code=422)

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="compressed.pdf"',
                "X-Content-Type-Options": "nosniff",
                "X-Original-Size": str(original_size),
                "X-Compressed-Size": str(len(out_bytes)),
                "Access-Control-Expose-Headers": "X-Original-Size, X-Compressed-Size",
            },
        )

    # ------------------------------------------------------------------
    # /file-to-markdown — convert PDF/Office/HTML/CSV/EPUB to Markdown
    # ------------------------------------------------------------------
    @api.post("/file-to-markdown")
    async def file_to_markdown_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "file-to-markdown"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOC2MD_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        filename = file.filename or ""
        try:
            data = await _read_capped(file, core.MAX_DOC2MD_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        try:
            core.validate_doc2md_upload(filename, len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not core.doc2md_signature_ok(filename, data):
            return JSONResponse(
                {"error": "invalid", "detail": "File contents do not match its type."},
                status_code=400,
            )

        from latextools import doc2md

        def _do():
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                suffix = Path(filename).suffix.lower()
                in_path = Path(d) / f"input{suffix}"
                in_path.write_bytes(data)
                return doc2md.convert_to_markdown(str(in_path))

        try:
            md = await run_in_threadpool(_do)
        except Exception:
            # markitdown raises a variety of parser errors; the container's
            # request timeout bounds any pathological/slow input.
            logger.exception("file-to-markdown conversion failed")
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't convert this file."},
                status_code=422,
            )
        if not md or not md.strip():
            return JSONResponse(
                {"error": "convert", "detail": "No text could be extracted from this file."},
                status_code=422,
            )
        return JSONResponse(
            {"markdown": md, "filename": filename},
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ------------------------------------------------------------------
    # /pdf-structure — free PDF-to-Structured-Data tool. Runs OpenDataLoader
    # (Apache-2.0, local mode) in an isolated JVM function and returns
    # reading-order Markdown + RAG-ready JSON. Nothing is retained.
    # ------------------------------------------------------------------
    @api.post("/pdf-structure")
    async def pdf_structure_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "pdf-structure"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PDF_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        try:
            data = await _read_capped(file, core.MAX_PDF_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        try:
            core.validate_pdf_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse(
                {"error": "invalid", "detail": "File is not a valid PDF."},
                status_code=400,
            )

        try:
            result = await run_in_threadpool(lambda: pdf_structure_run.remote(data))
        except Exception:
            logger.exception("pdf-structure run failed")
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't process this PDF."},
                status_code=422,
            )

        err = result.get("error") if isinstance(result, dict) else "convert"
        if err == "timeout":
            return JSONResponse(
                {"error": "convert", "detail": "This PDF took too long to process. Try a smaller or simpler file."},
                status_code=422,
            )
        if err in ("parse", "empty"):
            return JSONResponse(
                {"error": "convert", "detail": "No structured content could be extracted from this PDF."},
                status_code=422,
            )
        if err:
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't process this PDF."},
                status_code=422,
            )

        return JSONResponse(
            {
                "markdown": result.get("markdown", ""),
                "structured": result.get("json", {}),
                "summary": result.get("summary", {}),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ------------------------------------------------------------------
    # /word-stats — free Document Insights tool. Extracts plain text from
    # an uploaded document and (for academic papers) splices it into named
    # sections. ALL statistics are computed client-side; this endpoint only
    # does the format-to-text conversion the browser can't. Retains nothing.
    # ------------------------------------------------------------------
    @api.post("/word-stats")
    async def word_stats_endpoint(
        request: Request,
        file: UploadFile = File(...),
    ):
        if not _enforce_rate_limit(request, "word-stats"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_DOC2MD_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        filename = file.filename or ""
        try:
            data = await _read_capped(file, core.MAX_DOC2MD_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        try:
            core.validate_wordstats_upload(filename, len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)

        name_lc = filename.lower()
        is_pdf = name_lc.endswith(".pdf")
        is_plaintext = name_lc.endswith(core.WORDSTATS_PLAINTEXT_EXTENSIONS)

        # Magic-byte check for binary formats (plain-text formats skip it).
        if not is_plaintext and not core.doc2md_signature_ok(filename, data):
            # doc2md_signature_ok only knows the doc2md set; for .rtf/.odt we
            # do a lighter check (.odt is a zip; .rtf starts with "{\rtf").
            ok = True
            if name_lc.endswith(".odt"):
                ok = data[:4] == b"PK\x03\x04"
            elif name_lc.endswith(".rtf"):
                ok = data[:5] == b"{\\rtf"
            elif name_lc.endswith(core.DOC2MD_ALLOWED_EXTENSIONS):
                ok = False  # doc2md_signature_ok already said no
            if not ok:
                return JSONResponse(
                    {"error": "invalid", "detail": "File contents do not match its type."},
                    status_code=400,
                )

        from latextools import doc2md, papercheck

        def _extract():
            # Plain-text formats: decode directly (fast, no conversion).
            if is_plaintext:
                return data.decode("utf-8", errors="replace")
            # Everything else → markitdown / pdfplumber via doc2md.
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                suffix = Path(filename).suffix.lower()
                in_path = Path(d) / f"input{suffix}"
                in_path.write_bytes(data)
                return doc2md.convert_to_markdown(str(in_path))

        try:
            text = await run_in_threadpool(_extract)
        except Exception:
            logger.exception("word-stats extraction failed")
            return JSONResponse(
                {"error": "convert", "detail": "Couldn't read this file."},
                status_code=422,
            )
        if not text or not text.strip():
            return JSONResponse(
                {"error": "convert", "detail": "No text could be extracted from this file."},
                status_code=422,
            )

        # Academic section splice (best-effort). For PDFs we can also count
        # pages; for everything else page_count is null.
        sections = papercheck.splice_text_sections(text)
        # "academic" if we found at least two distinct narrative/structural
        # sections beyond the catch-all body.
        structural = [k for k in sections if k not in ("body", "figure_captions")]
        kind = "academic" if len(structural) >= 2 else "plain"

        page_count = None
        if is_pdf:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    page_count = len(pdf.pages)
            except Exception:
                page_count = None

        return JSONResponse(
            {
                "text": text,
                "kind": kind,
                "page_count": page_count,
                "sections": sections if kind == "academic" else None,
                "filename": filename,
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ------------------------------------------------------------------
    # /paper-review/* — paid AI red-team manuscript review
    #
    # Flow:
    #   1. User pays via Stripe Checkout (Netlify Function).
    #   2. Stripe webhook (Netlify Function) calls /register-token here
    #      with the session_id and the freshly-minted job token.
    #   3. User is redirected to /tools/paper-review/upload/?session_id=…,
    #      which calls /redeem-session to get the job token.
    #   4. UI POSTs PDF + domain to /submit with the token. We .spawn() the
    #      heavy pipeline and immediately return.
    #   5. UI polls /status?token=… until status == "done".
    #   6. On first successful retrieval of result_md, the entry is kept
    #      for a short grace window (PAPER_RESULT_GRACE_SECONDS) so a
    #      dropped response, refresh, or duplicate tab can still retrieve
    #      it, then deleted — either inline on a later poll past the grace
    #      window, or by the sweep_stale_paper_jobs cron backstop.
    # ------------------------------------------------------------------

    import secrets as _secrets_module
    import time as _time_module

    PAPER_TOKEN_TTL_SECONDS = 7 * 24 * 3600   # 7 days to redeem after pay
    # PAPER_JOB_TTL_SECONDS lives at module scope (see top of file) so the
    # scheduled sweep_stale_paper_jobs cron can share the same constant.

    def _gen_token() -> str:
        return _secrets_module.token_urlsafe(32)

    @api.post("/paper-review/register-token")
    async def paper_review_register_token(request: Request):
        """Internal webhook target — called by the Netlify Stripe webhook
        after a successful Checkout payment. Header-authenticated only.

        Payload:
          { session_id, email, amount_paid, product, extras: {...} }

        Volume packs mint multiple tokens; everything else mints one. All
        tokens for a session are stored under the same session_id key so
        the buyer can retrieve them all if needed.

        Not IP-rate-limited: this is only reachable from the Netlify Stripe
        webhook (server-to-server), so the caller's IP is Netlify's function
        egress address shared across all purchases site-wide, not the buyer's.
        An IP-keyed limit here would risk 429-ing legitimate concurrent
        purchases rather than throttling an attacker. Auth is the header
        secret above; that plus Stripe's own signature check on the Netlify
        side is the real gate.
        """
        provided = request.headers.get("x-webhook-secret", "")
        expected = os.environ.get("BACKEND_WEBHOOK_SECRET", "")
        if not expected:
            return JSONResponse(
                {"error": "misconfigured", "detail": "backend secret not set"},
                status_code=500,
            )
        import hmac as _hmac
        if not _hmac.compare_digest(provided, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)

        session_id = (payload or {}).get("session_id", "")
        email = (payload or {}).get("email", "")
        amount_paid = (payload or {}).get("amount_paid", 0)
        product_key = (payload or {}).get("product", "paper-review-standard")
        referral_code = (payload or {}).get("referral_code", "")
        referral_code = referral_code.strip()[:32] if isinstance(referral_code, str) else ""
        if not session_id or not isinstance(session_id, str) or len(session_id) > 200:
            return JSONResponse({"error": "missing_session_id"}, status_code=400)

        product_cfg = PAID_PRODUCTS.get(product_key)
        if not product_cfg:
            return JSONResponse(
                {"error": "unknown_product", "detail": product_key},
                status_code=400,
            )

        # Defense-in-depth: the webhook is HMAC-authenticated, but a bug in
        # the Netlify Stripe webhook (e.g. a price_id -> product_key mapping
        # error) could still forward a product_key that doesn't match what
        # was actually charged. Cross-check amount_paid against the
        # catalog's expected amount for this product before minting tokens,
        # so a mismapped 5-pack can't mint a 20-pack's worth of tokens.
        expected_amount = product_cfg.get("amount")
        paid_amount = amount_paid if isinstance(amount_paid, int) else 0
        if expected_amount is not None and paid_amount != expected_amount:
            return JSONResponse(
                {
                    "error": "amount_mismatch",
                    "detail": f"product {product_key} expects {expected_amount}, got {paid_amount}",
                },
                status_code=400,
            )

        # Idempotent: re-registering the same session_id returns the same tokens.
        existing = paper_tokens_dict.get(session_id)
        if existing and isinstance(existing, dict):
            return JSONResponse({
                "tokens": existing.get("tokens", []),
                "product": existing.get("product_key"),
                "status": "exists",
            })

        qty = int(product_cfg.get("qty", 1))
        if qty < 1 or qty > MAX_PACK_QTY:
            logger.error(
                "product %s has out-of-bounds qty=%d (max %d); refusing to mint tokens",
                product_key, qty, MAX_PACK_QTY,
            )
            return JSONResponse({"error": "invalid_product_qty"}, status_code=500)
        tokens = [_gen_token() for _ in range(qty)]
        entry = {
            "tokens": tokens,
            "product_key": product_key,
            "product_cfg": product_cfg,
            "email": email[:200] if isinstance(email, str) else "",
            "amount_paid": int(amount_paid) if isinstance(amount_paid, int) else 0,
            "redeemed": False,
            "consumed_tokens": [],   # tokens that have been used
            "created_at": _time_module.time(),
            "expires_at": _time_module.time() + PAPER_TOKEN_TTL_SECONDS,
        }
        paper_tokens_dict[session_id] = entry
        for _tok in tokens:
            paper_token_index_dict[_tok] = session_id

        # Seed the lifecycle-email sequence for this purchase (tips, later
        # review-request, eventual win-back). Skipped if the buyer's email
        # already opted out. manuscript_title starts blank — the buyer
        # hasn't uploaded anything yet at purchase time; lifecycle_email_sweep
        # falls back to "your manuscript" when rendering.
        if entry["email"] and not lifecycle_optout_dict.get(entry["email"]):
            customer_lifecycle_dict[session_id] = {
                "email": entry["email"],
                "manuscript_title": "",
                "purchased_at": entry["created_at"],
                "last_stage_sent": None,
                "last_sent_at": None,
            }

        # Co-author exposure referral loop (task tracked as "referral loop"):
        # a .edu buyer who came in via a live referral code credits both
        # themselves and whoever referred them. Gated to .edu specifically
        # per spec — this is meant to spread within academic circles, not
        # become a general-purpose discount code.
        buyer_email = entry["email"]
        if referral_code and buyer_email and buyer_email.lower().endswith(".edu"):
            referrer_email = referral_dict.get(referral_code)
            if referrer_email and referrer_email != buyer_email:
                # Awaited (not backgrounded) to match the volume-pack email
                # pattern below — best-effort internally (never raises), so
                # this can't fail the purchase itself, just adds a couple
                # seconds of webhook latency, which Stripe/Netlify tolerate.
                await _credit_referral(referrer_email, buyer_email)

        # Volume-pack tokens: email them all immediately
        if qty > 1 and entry["email"]:
            try:
                from latextools import delivery as _delivery
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10.0) as _ec:
                    _email_result = await _delivery.send_email(
                        _ec,
                        to=entry["email"],
                        subject=f"Your {qty}-pack of Paper Reviews",
                        html=_delivery.html_volume_pack_tokens(tokens=tokens, pack_size=qty),
                        tags=[{"name": "product", "value": product_key}],
                    )
                if _email_result.get("status") != "ok":
                    logger.warning(
                        "volume pack email not sent for session_id=%s qty=%d: %s",
                        session_id, qty, _email_result,
                    )
            except Exception:
                logger.exception("volume pack email send failed")

        return JSONResponse({
            "tokens": tokens,
            "product": product_key,
            "qty": qty,
            "status": "registered",
        })

    def _lifecycle_unsubscribe_token(email: str) -> str:
        """Namespaced so lifecycle-unsubscribe tokens can't be replayed
        against the digest's own unsubscribe link (or vice versa), while
        still reusing SUBSCRIBE_SECRET instead of minting a new secret."""
        import hashlib as _hashlib
        import hmac as _hmac_local
        secret = os.environ.get("SUBSCRIBE_SECRET", "")
        return _hmac_local.new(
            secret.encode(), f"lifecycle:{email}".encode(), _hashlib.sha256
        ).hexdigest()

    def _lifecycle_unsubscribe_url(email: str) -> str:
        token = _lifecycle_unsubscribe_token(email)
        from urllib.parse import quote as _quote
        return (
            "https://purplelink.llc/paper-review/lifecycle/unsubscribe"
            f"?email={_quote(email)}&token={token}"
        )

    def _lifecycle_page(title: str, heading: str, body_html: str, status: int = 200) -> "HTMLResponse":
        from fastapi.responses import HTMLResponse
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>
    <div id="main-content" class="post-hero">
      <h1>{heading}</h1>
      {body_html}
    </div>
    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia &middot; Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
  </body>
</html>"""
        return HTMLResponse(html, status_code=status)

    @api.get("/paper-review/lifecycle/unsubscribe")
    async def paper_review_lifecycle_unsubscribe(request: Request):
        """One-click unsubscribe for lifecycle purchase emails. Mirrors
        netlify/functions/unsubscribe.mjs's HMAC pattern but writes to
        lifecycle_optout_dict (a Modal Dict) instead of Netlify Blobs, so
        the write and the cron read that respects it live on one system."""
        email = (request.query_params.get("email") or "").strip().lower()
        token = request.query_params.get("token") or ""

        if not email or not token or not os.environ.get("SUBSCRIBE_SECRET"):
            return _lifecycle_page(
                "Invalid link", "Invalid link",
                "<p>This unsubscribe link is missing required parameters.</p>",
                status=400,
            )

        import hmac as _hmac_local
        expected = _lifecycle_unsubscribe_token(email)
        if not _hmac_local.compare_digest(token, expected):
            return _lifecycle_page(
                "Invalid link", "Invalid link",
                "<p>This unsubscribe link is not valid. It may have been altered.</p>",
                status=400,
            )

        lifecycle_optout_dict[email] = True
        import html as _html_module
        return _lifecycle_page(
            "Unsubscribed", "Unsubscribed",
            "<p class=\"post-lede\">You've been removed from purchase-related "
            f"emails. No more emails will be sent to {_html_module.escape(email)}.</p>",
        )

    @api.post("/paper-review/redeem-session")
    async def paper_review_redeem_session(request: Request):
        """Exchange a Stripe session_id (or an already-issued job token) for
        the job token(s).

        Returns the first unconsumed token for single-purchase products,
        or the full list for volume packs. Marks the session as redeemed.

        Volume-pack buyers who saved a token from a previous redemption (the
        "Use this token" link on the pack success page) can also look their
        entry up by that token directly, without re-supplying the original
        Stripe session_id — the token itself is already an unguessable,
        payment-gated credential (see /paper-review/submit, which accepts
        it directly), so trusting it here for lookup only is no weaker.
        """
        if not _enforce_rate_limit(request, "paper-review-redeem-session"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        session_id = (payload or {}).get("session_id", "")
        token_lookup = (payload or {}).get("token", "")

        if session_id and isinstance(session_id, str) and len(session_id) <= 200:
            entry = paper_tokens_dict.get(session_id)
        elif token_lookup and isinstance(token_lookup, str) and len(token_lookup) <= 200:
            session_id, entry = _lookup_token(token_lookup)
        else:
            return JSONResponse({"error": "missing_session_id"}, status_code=400)

        if not entry or not isinstance(entry, dict):
            return JSONResponse({"error": "pending"}, status_code=404)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            # Purge on the app's own clock rather than relying on Modal
            # Dict's inactivity-based TTL, which resets on any read/write
            # to the dict (including unrelated lookups) and therefore
            # cannot be trusted to actually evict logically-expired entries.
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if token_lookup and token_lookup in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)

        tokens: list[str] = entry.get("tokens") or []
        consumed = set(entry.get("consumed_tokens") or [])
        unused = [t for t in tokens if t not in consumed]
        if not unused:
            return JSONResponse({"error": "all_used"}, status_code=409)

        if not entry.get("redeemed"):
            entry["redeemed"] = True
            paper_tokens_dict[session_id] = entry

        product_key = entry.get("product_key", "paper-review-standard")
        product_cfg = entry.get("product_cfg") or PAID_PRODUCTS.get(product_key, {})

        return JSONResponse({
            "token": unused[0],
            "tokens": tokens,           # full list (for volume packs)
            "unused_tokens": unused,
            "product": product_key,
            "category": product_cfg.get("category", "paper-review"),
            "tier": product_cfg.get("tier", "standard"),
            "bundled_anonymity": product_cfg.get("bundled_anonymity", False),
            "bundled_journal": product_cfg.get("bundled_journal", False),
            "qty": product_cfg.get("qty", 1),
            "status": "ok",
        })

    def _expire_token_entry(session_id: str, entry: dict) -> None:
        """Actively purge a logically-expired token entry.

        modal.Dict has its own inactivity-based eviction (~7 days since the
        *store* was last touched), which is independent of and cannot be
        relied on to match our application-level `expires_at` field —
        unrelated reads (e.g. `_lookup_token`'s fallback scan) keep expired
        entries alive indefinitely, and idle entries with no traffic could
        theoretically be evicted before `expires_at` even without ever being
        marked expired here. We never rely on Modal's TTL for correctness;
        this makes deletion of expired entries deterministic instead.
        """
        try:
            for _tok in (entry.get("tokens") or []):
                try:
                    del paper_token_index_dict[_tok]
                except Exception:
                    pass
            del paper_tokens_dict[session_id]
        except Exception:
            pass

    def _lookup_token(token: str):
        """Find the tokens entry containing this token. Returns
        (session_id, entry) or (None, None). For volume packs the entry
        contains many tokens — we still return the same entry.

        Uses the token->session_id reverse index (paper_token_index_dict)
        for an O(1) lookup. Falls back to a full linear scan of
        paper_tokens_dict only for entries registered before the index
        existed (or if the index is otherwise missing an entry), so older
        in-flight sessions keep working during rollout.

        Does NOT purge logically-expired entries itself — it still returns
        them so callers can tell "expired" (410) apart from "never existed"
        (404), matching the existing API contract. Callers that already
        check `expires_at` are responsible for calling `_expire_token_entry`
        once they've made that determination (see submit / redeem-session).
        """
        if not token or not isinstance(token, str) or len(token) > 200:
            return None, None

        session_id = paper_token_index_dict.get(token)
        if session_id:
            entry = paper_tokens_dict.get(session_id)
            if isinstance(entry, dict) and token in (entry.get("tokens") or []):
                return session_id, entry

        # Fallback: pre-index entries or a stale/missing index record.
        for session_id, entry in list(paper_tokens_dict.items()):
            if not isinstance(entry, dict):
                continue
            if token in (entry.get("tokens") or []):
                # Backfill the index so subsequent lookups are O(1).
                paper_token_index_dict[token] = session_id
                return session_id, entry
        return None, None

    def _claim_token(token: str) -> bool:
        """Atomically claim a token for a single in-flight submission.

        Backed by Modal Dict's compare-and-set `put(..., skip_if_exists=True)`,
        which is atomic server-side. Returns True iff this call is the one
        that created the claim (i.e. won the race); returns False if some
        other concurrent request already holds it. Callers MUST check the
        return value and bail out (without spawning a pipeline job) on False
        — this is what prevents N concurrent requests for the same token
        from all passing the "already_used" check and all spawning billable
        pipeline runs.
        """
        return paper_token_claims_dict.put(token, _time_module.time(), skip_if_exists=True)

    def _consume_token(token: str, session_id: str, entry: dict) -> None:
        """Mark a single token within a session entry as consumed.

        This only updates the (eventually-consistent, non-atomic) bookkeeping
        used for UI/status purposes. Billing-critical exclusivity is enforced
        separately by `_claim_token`, which callers must invoke first.

        Volume packs share one `entry` dict across all their tokens, so two
        concurrent submissions for different tokens in the same pack can each
        read the entry before the other's write lands. To avoid a last-write-
        wins overwrite that silently drops the other request's consumed-token
        bookkeeping, re-fetch the freshest copy of the entry from the dict
        immediately before writing and union the consumed-token sets instead
        of blindly replacing with the (possibly stale) `entry` passed in.
        """
        latest = paper_tokens_dict.get(session_id)
        base = latest if isinstance(latest, dict) else entry
        consumed = set(base.get("consumed_tokens") or [])
        consumed |= set(entry.get("consumed_tokens") or [])
        consumed.add(token)
        base["consumed_tokens"] = list(consumed)
        base["last_consumed_at"] = _time_module.time()
        paper_tokens_dict[session_id] = base

    @api.post("/paper-review/submit")
    async def paper_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        domain: str = Form("general"),
        journal_key: str = Form(""),
        anonymity_check: str = Form("false"),
        email: str = Form(""),
    ):
        """Validate the token + PDF and spawn the Paper Review pipeline.

        The tier / bundled options are inferred from the token's product
        config (set at register-token time based on which Stripe price the
        customer paid). The submit form can additionally request an
        anonymity scan on its own, supply a journal_key for compliance, or
        provide an email for completion notification.
        """
        if not _enforce_rate_limit(request, "paper-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )

        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            # Purge on the app's own clock rather than relying on Modal
            # Dict's inactivity-based TTL (see _expire_token_entry).
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)

        product_cfg = entry.get("product_cfg") or {}
        if product_cfg.get("category") != "paper-review":
            return JSONResponse(
                {"error": "wrong_product",
                 "detail": "This token is for a different product."},
                status_code=400,
            )

        # Atomically claim the token before doing any expensive work. This
        # closes the check-then-act race: only one concurrent request for
        # the same token can win this CAS, so only one pipeline run is ever
        # spawned per token, no matter how many requests race in.
        if not _claim_token(token):
            return JSONResponse({"error": "already_used"}, status_code=409)

        try:
            data = await _read_capped(file, core.MAX_PAPER_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse(
                {"error": "invalid", "detail": "File is too large (max 20 MB)."},
                status_code=400,
            )
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse(
                {"error": "invalid", "detail": "File is not a valid PDF."},
                status_code=400,
            )

        if domain not in (
            "general", "machine_learning", "biomedicine",
            "psychology_social", "chemistry_materials",
            "nca",  # AI-SCoRe: SCoRe checklist evaluation for NCA studies
        ):
            domain = "general"

        # Tier comes from the product config (set at purchase time).
        tier = product_cfg.get("tier", "standard")
        do_anonymity = (
            anonymity_check == "true" or bool(product_cfg.get("bundled_anonymity"))
        )
        chosen_journal = ""
        if product_cfg.get("bundled_journal"):
            from latextools import journals as _jnl
            if journal_key and journal_key in _jnl.JOURNAL_SPECS:
                chosen_journal = journal_key

        # Initialise the jobs_dict entry so the UI can poll immediately.
        # Uses the async Modal client (.put.aio / .spawn.aio) — calling the
        # blocking equivalents from inside this async handler silently drops
        # the write/spawn under load (confirmed via live testing: real
        # customer submissions never actually enqueued the pipeline, leaving
        # them stuck on "unknown_token" with no job ever created).
        await paper_jobs_dict.put.aio(token, {
            "status": "queued",
            "stage": "queued",
            "progress_pct": 0,
            "started_at": _time_module.time(),
            "finished_at": None,
            "error": None,
            "result_md": None,
            "result_pdf_b64": None,
            "annotated_pdf_b64": None,
            "layer_status": {},
            "tier": tier,
            "product": "paper-review",
        })

        # Only mark the token consumed once the pipeline has actually been
        # handed off. If `.spawn()` itself throws (Modal control-plane
        # error, container pool exhausted, serialization failure, etc.),
        # release the claim so the token is still redeemable and report a
        # 500 instead of silently burning the customer's paid credit on a
        # job that never started.
        try:
            await paper_review_pipeline.spawn.aio(
                token, data, domain,
                tier=tier,
                journal_key=chosen_journal,
                anonymity_check=do_anonymity,
                deliver_email=email if email and "@" in email and len(email) <= 254 else "",
            )
        except Exception:
            logger.exception("paper_review_pipeline.spawn failed for token=%s", token[:12])
            try:
                await paper_jobs_dict.pop.aio(token)
            except Exception:
                pass
            try:
                await paper_token_claims_dict.pop.aio(token)
            except Exception:
                pass
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )

        _consume_token(token, session_id, entry)

        return JSONResponse({
            "token": token,
            "tier": tier,
            "anonymity_check": do_anonymity,
            "journal_key": chosen_journal,
            "status_url": f"/paper-review/status?token={token}",
        })

    # --- AI-SCoRe (NCA) dedicated endpoint -------------------------------------
    # Thin alias over the review pipeline's `nca` domain. Reuses all token / billing /
    # job-status plumbing; the only difference is the domain is fixed to AI-SCoRe.
    #
    # There is no dedicated 'aiscore' product category today — AI-SCoRe is sold
    # as part of the paper-review catalog (same tokens, same tiers), so a
    # 'paper-review' token is the only category this endpoint accepts. This
    # gate is enforced here (not just inside paper_review_submit's own check)
    # so the category this endpoint is willing to accept is explicit and
    # doesn't silently widen if paper_review_submit's own gate is ever relaxed
    # or a new adjacent-tool category is added to PAID_PRODUCTS.
    @api.post("/score/submit")
    async def aiscore_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        _, entry = _lookup_token(token)
        if entry is not None:
            product_cfg = entry.get("product_cfg") or {}
            if product_cfg.get("category") != "paper-review":
                return JSONResponse(
                    {"error": "wrong_product",
                     "detail": "This token is for a different product."},
                    status_code=400,
                )
        return await paper_review_submit(
            request, token=token, file=file, domain="nca", email=email,
        )

    @api.get("/score/status")
    async def aiscore_status(request: Request, token: str):
        return await paper_review_status(request, token=token)

    @api.get("/paper-review/status")
    async def paper_review_status(request: Request, token: str):
        if not token or not isinstance(token, str) or len(token) > 200:
            return JSONResponse({"error": "invalid_token"}, status_code=400)
        entry = paper_jobs_dict.get(token)
        if not entry or not isinstance(entry, dict):
            return JSONResponse({"error": "unknown_token"}, status_code=404)

        status = entry.get("status", "running")
        if status == "done" and entry.get("result_md"):
            # Completed review. We used to atomically pop() the record on
            # the very first successful retrieval so we'd hold zero copies
            # of the review at rest. In practice that made delivery
            # non-idempotent: a dropped response (backgrounded/throttled
            # mobile tab, laptop sleep, flaky wifi eating the 200 after it
            # left the server) or a second tab polling the same token would
            # permanently lose the result even though the customer paid for
            # it and never actually received it.
            #
            # Instead: keep serving the cached result for a short retrieval
            # grace window after the first delivery, so refreshes/duplicate
            # tabs/retries within that window still get it. The record is
            # still deleted well before PAPER_JOB_TTL_SECONDS — either by
            # this handler once the grace window elapses, or by the
            # sweep_stale_paper_jobs cron as a backstop — so we don't retain
            # manuscripts indefinitely.
            now = _time_module.time()
            delivered_at = entry.get("delivered_at")
            if delivered_at is not None and (now - delivered_at) > PAPER_RESULT_GRACE_SECONDS:
                # Grace window elapsed — this is a late poll arriving well
                # after delivery. Clean up now rather than waiting for the
                # daily sweep.
                try:
                    await paper_jobs_dict.pop.aio(token, None)
                except Exception:
                    pass
                return JSONResponse({"error": "unknown_token"}, status_code=404)

            if delivered_at is None:
                # First successful retrieval — stamp it as delivered instead
                # of deleting it. Written back with .put.aio so concurrent
                # pollers (double-tab, retry) converge on the same
                # delivered_at rather than racing a get-and-delete.
                entry = {**entry, "delivered_at": now}
                try:
                    await paper_jobs_dict.put.aio(token, entry)
                except Exception:
                    logger.exception("failed to stamp delivered_at for token=%s", token[:12])

            # Resolve the Stripe session_id server-side so the "Get invoice"
            # button on the status page can work at all. We deliberately
            # never put session_id in the status URL (it's a bearer
            # credential for /paper-review/redeem-session — see upload.js —
            # and would otherwise leak into browser history / Referer
            # headers), so this is the only place the frontend can get it.
            # By this point the token has already been consumed to produce
            # this very result, so returning the session_id it belongs to
            # reveals nothing the token holder doesn't already control.
            session_id_for_invoice, _ = _lookup_token(token)

            payload = {
                "status": "done",
                "progress_pct": 100,
                "stage": "done",
                "product": entry.get("product", "paper-review"),
                "tier": entry.get("tier", "standard"),
                "result_md": entry.get("result_md", ""),
                "annotated_pdf_b64": entry.get("annotated_pdf_b64"),
                "structure_summary": entry.get("structure_summary", {}),
                "l1_summary": entry.get("l1_summary"),
                "l2_summary": entry.get("l2_summary"),
                "l3_summary": entry.get("l3_summary"),
                "compliance_result": entry.get("compliance_result"),
                "anonymity_result": entry.get("anonymity_result"),
                "deterministic_findings": entry.get("deterministic_findings"),
                "session_id": session_id_for_invoice,
                "_note": "This result will be deleted from server storage shortly. Save it now.",
            }
            return JSONResponse({k: v for k, v in payload.items() if v is not None or k in ("annotated_pdf_b64",)})

        return JSONResponse({
            "status": status,
            "progress_pct": entry.get("progress_pct", 0),
            "stage": entry.get("stage", "running"),
            "product": entry.get("product", "paper-review"),
            "tier": entry.get("tier", "standard"),
            "error": entry.get("error"),
            "layer_status": entry.get("layer_status", {}),
            # Set only when a post-spawn pipeline crash burned the original
            # token; a fresh, unconsumed token the customer can resubmit
            # with instead of emailing support. See _reissue_token_on_failure.
            "replacement_token": entry.get("replacement_token"),
        })

    # ------------------------------------------------------------------
    # /paper-review/journals — list journal compliance specs for a domain
    # ------------------------------------------------------------------
    @api.get("/paper-review/journals")
    async def paper_review_journals(request: Request, domain: str = "general"):
        if not _enforce_rate_limit(request, "paper-review-journals"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        from latextools import journals as _jnl
        return JSONResponse({
            "journals": _jnl.list_journals_for_domain(domain),
        })

    # ------------------------------------------------------------------
    # Adjacent paid-tool submit endpoints. Each validates the token,
    # confirms the product matches, and spawns the dispatcher.
    # ------------------------------------------------------------------
    async def _start_adjacent(token: str, session_id: str, entry: dict, *,
                        product: str, spawn_kwargs: dict) -> str:
        """Atomically claim `token` and spawn the adjacent-tool pipeline.

        Returns one of:
          - "claimed":      spawn succeeded, token is now consumed.
          - "already_used": token was already claimed by a concurrent
                             request — caller must respond with 409.
          - "spawn_failed":  the claim was won but `.spawn()` raised; the
                             claim/job-dict entry were rolled back and the
                             token was NOT consumed, so the caller must
                             respond with a retryable error (not 409).

        Uses the async Modal client (.put.aio / .spawn.aio) rather than the
        blocking calls — calling blocking Modal interfaces from inside an
        async request handler silently drops the write/spawn under load
        (confirmed via live testing: the synchronous .spawn() here never
        actually enqueued the pipeline, leaving paying customers stuck on
        "unknown_token" with no job ever created).

        Only marks the token consumed once the pipeline has actually been
        handed off. If `.spawn()` itself throws (Modal control-plane error,
        container pool exhausted, serialization failure, etc.), release the
        claim so the token is still redeemable instead of silently burning
        the customer's paid credit on a job that never started. Mirrors the
        spawn-before-consume ordering in `paper_review_submit` above.
        """
        if not _claim_token(token):
            return "already_used"
        await paper_jobs_dict.put.aio(token, {
            "status": "queued", "stage": "queued",
            "progress_pct": 0, "started_at": _time_module.time(),
            "product": product, "result_md": None,
        })
        try:
            await adjacent_tool_pipeline.spawn.aio(token, product, **spawn_kwargs)
        except Exception:
            logger.exception("adjacent_tool_pipeline.spawn failed for token=%s product=%s", token[:12], product)
            try:
                await paper_jobs_dict.pop.aio(token)
            except Exception:
                pass
            try:
                await paper_token_claims_dict.pop.aio(token)
            except Exception:
                pass
            return "spawn_failed"
        _consume_token(token, session_id, entry)
        return "claimed"

    @api.post("/cover-letter/submit")
    async def cover_letter_submit(
        request: Request,
        token: str = Form(...),
        title: str = Form(""),
        abstract: str = Form(...),
        journal_name: str = Form(...),
        custom_note: str = Form(""),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "cover-letter"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if (entry.get("product_cfg") or {}).get("category") != "cover-letter":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        abstract = (abstract or "").strip()
        if not abstract or len(abstract) > 5000:
            return JSONResponse(
                {"error": "invalid", "detail": "Abstract is required and must be ≤ 5000 chars."},
                status_code=400,
            )
        if not _looks_like_abstract(abstract):
            return JSONResponse(
                {
                    "error": "invalid",
                    "detail": "That doesn't look like a paper abstract. Please paste your actual abstract text.",
                },
                status_code=400,
            )
        if not journal_name or len(journal_name) > 300:
            return JSONResponse({"error": "invalid", "detail": "Journal name required."}, status_code=400)
        claimed = await _start_adjacent(token, session_id, entry, product="cover-letter", spawn_kwargs={
            "title_only": (title or "")[:300],
            "abstract_only": abstract,
            "journal_name": journal_name,
            "custom_note": (custom_note or "")[:1000],
            "deliver_email": email if email and "@" in email else "",
        })
        if claimed == "already_used":
            return JSONResponse({"error": "already_used"}, status_code=409)
        if claimed == "spawn_failed":
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/anonymity-check/submit")
    async def anonymity_check_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "anonymity-check"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if (entry.get("product_cfg") or {}).get("category") != "anonymity-check":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_PAPER_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        claimed = await _start_adjacent(token, session_id, entry, product="anonymity-check", spawn_kwargs={
            "pdf_bytes": data,
            "deliver_email": email if email and "@" in email else "",
        })
        if claimed == "already_used":
            return JSONResponse({"error": "already_used"}, status_code=409)
        if claimed == "spawn_failed":
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/citation-gap/submit")
    async def citation_gap_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "citation-gap"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if (entry.get("product_cfg") or {}).get("category") != "citation-gap":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_PAPER_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        claimed = await _start_adjacent(token, session_id, entry, product="citation-gap", spawn_kwargs={
            "pdf_bytes": data,
            "deliver_email": email if email and "@" in email else "",
        })
        if claimed == "already_used":
            return JSONResponse({"error": "already_used"}, status_code=409)
        if claimed == "spawn_failed":
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/revision-review/submit")
    async def revision_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        original_review_md: str = Form(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "revision-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if (entry.get("product_cfg") or {}).get("category") != "revision-review":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        if not original_review_md or len(original_review_md) > 120_000:
            return JSONResponse({"error": "invalid", "detail": "Original review required (≤ 120k chars)."}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_PAPER_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        claimed = await _start_adjacent(token, session_id, entry, product="revision-review", spawn_kwargs={
            "pdf_bytes": data,
            "original_review_md": original_review_md,
            "deliver_email": email if email and "@" in email else "",
        })
        if claimed == "already_used":
            return JSONResponse({"error": "already_used"}, status_code=409)
        if claimed == "spawn_failed":
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    @api.post("/response-review/submit")
    async def response_review_submit(
        request: Request,
        token: str = Form(...),
        file: UploadFile = File(...),
        reviewer_comments: str = Form(...),
        author_response: str = Form(...),
        email: str = Form(""),
    ):
        if not _enforce_rate_limit(request, "response-review"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if _too_large(request, core.MAX_PAPER_UPLOAD_BYTES):
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        session_id, entry = _lookup_token(token)
        if entry is None:
            return JSONResponse({"error": "unknown_token"}, status_code=404)
        if token in (entry.get("consumed_tokens") or []):
            return JSONResponse({"error": "already_used"}, status_code=409)
        if entry.get("expires_at", 0) and entry["expires_at"] < _time_module.time():
            _expire_token_entry(session_id, entry)
            return JSONResponse({"error": "expired"}, status_code=410)
        if (entry.get("product_cfg") or {}).get("category") != "response-review":
            return JSONResponse({"error": "wrong_product"}, status_code=400)
        if not reviewer_comments or len(reviewer_comments) > 60_000:
            return JSONResponse({"error": "invalid", "detail": "Reviewer comments required (≤ 60k)."}, status_code=400)
        if not author_response or len(author_response) > 60_000:
            return JSONResponse({"error": "invalid", "detail": "Author response required (≤ 60k)."}, status_code=400)
        try:
            data = await _read_capped(file, core.MAX_PAPER_UPLOAD_BYTES)
        except _UploadTooLarge:
            return JSONResponse({"error": "invalid", "detail": "File too large."}, status_code=400)
        try:
            core.validate_paper_upload(file.filename or "", len(data))
        except core.ValidationError as e:
            return JSONResponse({"error": "invalid", "detail": str(e)}, status_code=400)
        if not data.startswith(b"%PDF-"):
            return JSONResponse({"error": "invalid", "detail": "File is not a valid PDF."}, status_code=400)
        claimed = await _start_adjacent(token, session_id, entry, product="response-review", spawn_kwargs={
            "pdf_bytes": data,
            "reviewer_comments": reviewer_comments,
            "author_response": author_response,
            "deliver_email": email if email and "@" in email else "",
        })
        if claimed == "already_used":
            return JSONResponse({"error": "already_used"}, status_code=409)
        if claimed == "spawn_failed":
            return JSONResponse(
                {"error": "spawn_failed", "detail": "Could not start the review. Your token has not been used — please try again."},
                status_code=500,
            )
        return JSONResponse({"token": token, "status_url": f"/paper-review/status?token={token}"})

    # ------------------------------------------------------------------
    # /paper-review/invoice — generate Stripe invoice for a session
    # ------------------------------------------------------------------
    @api.post("/paper-review/invoice")
    async def paper_review_invoice(request: Request):
        """Use the Stripe Invoices API to create + finalise a PDF invoice
        for a past Checkout session, then email the hosted-invoice URL via
        Resend. The caller provides the Stripe session_id and (optionally)
        an institutional tax-ID line to append."""
        if not _enforce_rate_limit(request, "paper-review-invoice"):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        session_id = (payload or {}).get("session_id", "")
        tax_id_line = (payload or {}).get("tax_id_line", "")[:200]
        token = (payload or {}).get("token", "")
        if not session_id or not isinstance(session_id, str):
            return JSONResponse({"error": "missing_session_id"}, status_code=400)
        if not token or not isinstance(token, str):
            return JSONResponse({"error": "missing_token"}, status_code=400)

        # We require the session_id be one we have on record
        token_entry = paper_tokens_dict.get(session_id)
        if not token_entry:
            return JSONResponse({"error": "unknown_session"}, status_code=404)

        # session_id alone is not sufficient authorization: it is embedded
        # in the post-checkout success URL and can leak via browser
        # history/Referer/screenshots (see the comment on /paper-review/status
        # above). Require proof of possession of the associated job token,
        # matching the bar every submit/redeem endpoint already enforces.
        if token not in (token_entry.get("tokens") or []):
            return JSONResponse({"error": "invalid_token"}, status_code=403)

        stripe_key = os.environ.get("STRIPE_SECRET_KEY")
        if not stripe_key:
            return JSONResponse(
                {"error": "misconfigured", "detail": "STRIPE_SECRET_KEY not set on web function."},
                status_code=500,
            )

        import httpx as _httpx
        import urllib.parse as _ulp

        # Look up the Checkout Session to find customer + amount
        async with _httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"https://api.stripe.com/v1/checkout/sessions/{_ulp.quote(session_id, safe='')}",
                    headers={"Authorization": f"Bearer {stripe_key}"},
                )
                if resp.status_code != 200:
                    logger.error("stripe checkout session lookup failed: %s", resp.text[:300])
                    return JSONResponse({"error": "stripe_lookup_failed"}, status_code=502)
                session = resp.json()
            except Exception:
                logger.exception("stripe checkout session lookup unreachable")
                return JSONResponse({"error": "stripe_unreachable"}, status_code=502)

            customer = session.get("customer")
            customer_email = (
                (session.get("customer_details") or {}).get("email")
                or session.get("customer_email")
                or token_entry.get("email", "")
            )
            amount_total = session.get("amount_total", 0)
            currency = session.get("currency", "usd")

            # If there's no customer object on the session, create one
            if not customer:
                cust_resp = await client.post(
                    "https://api.stripe.com/v1/customers",
                    headers={"Authorization": f"Bearer {stripe_key}"},
                    data={"email": customer_email or "ben@purplelink.llc"},
                )
                if cust_resp.status_code >= 300:
                    logger.error("stripe customer create failed: %s", cust_resp.text[:300])
                    return JSONResponse({"error": "stripe_customer_failed"}, status_code=502)
                customer = cust_resp.json().get("id")

            # Create a draft invoice tied to the customer
            inv_resp = await client.post(
                "https://api.stripe.com/v1/invoices",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={
                    "customer": customer,
                    "collection_method": "send_invoice",
                    "days_until_due": "30",
                    "description": f"Purplelink Paper Review — receipt for Stripe session {session_id[-8:]}",
                    "footer": (
                        tax_id_line + ("\n" if tax_id_line else "") +
                        "Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350, USA."
                    ),
                },
            )
            if inv_resp.status_code >= 300:
                logger.error("stripe invoice create failed: %s", inv_resp.text[:300])
                return JSONResponse({"error": "stripe_invoice_failed"}, status_code=502)
            invoice = inv_resp.json()
            invoice_id = invoice.get("id")

            # Add a line item
            item_resp = await client.post(
                "https://api.stripe.com/v1/invoiceitems",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={
                    "customer": customer,
                    "invoice": invoice_id,
                    "amount": str(amount_total),
                    "currency": currency,
                    "description": f"AI Paper Review (Stripe session {session_id[-8:]})",
                },
            )
            if item_resp.status_code >= 300:
                logger.error("stripe invoice item create failed: %s", item_resp.text[:300])
                return JSONResponse({"error": "stripe_invoice_item_failed"}, status_code=502)

            # Finalise
            final_resp = await client.post(
                f"https://api.stripe.com/v1/invoices/{invoice_id}/finalize",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data={"auto_advance": "false"},
            )
            if final_resp.status_code >= 300:
                logger.error("stripe invoice finalize failed: %s", final_resp.text[:300])
                return JSONResponse({"error": "stripe_finalize_failed"}, status_code=502)
            finalised = final_resp.json()

            invoice_pdf = finalised.get("invoice_pdf")
            hosted_invoice_url = finalised.get("hosted_invoice_url")

            # Email it
            if customer_email and invoice_pdf:
                from latextools import delivery as _delivery
                try:
                    _email_result = await _delivery.send_email(
                        client,
                        to=customer_email,
                        subject="Your Purplelink invoice",
                        html=_delivery.html_invoice_ready(
                            invoice_url=invoice_pdf,
                            amount_cents=amount_total,
                        ),
                        tags=[{"name": "type", "value": "invoice"}],
                    )
                    if _email_result.get("status") != "ok":
                        logger.warning(
                            "invoice email not sent for invoice_id=%s: %s",
                            invoice_id, _email_result,
                        )
                except Exception:
                    logger.exception("invoice email failed")

        return JSONResponse({
            "status": "ok",
            "invoice_pdf": invoice_pdf,
            "hosted_invoice_url": hosted_invoice_url,
            "amount": amount_total,
        })

    return api


# ---------------------------------------------------------------------------
# Scheduled cleanup — proactive TTL sweep for paper_tokens_dict.
#
# The `expires_at` check inside /redeem-session and /submit (see
# _expire_token_entry above) only purges an entry when someone actually
# hits one of those endpoints for it. A token the buyer never redeems or
# submits is never touched again, so its entry (email, product_cfg,
# tokens, amount_paid, created_at) would otherwise sit in Modal Dict
# storage forever — a much weaker guarantee than "tokens expire after 7
# days" implies if read as a retention/deletion promise. This cron
# actively deletes any entry whose `expires_at` has passed, regardless of
# whether it was ever revisited.
# ---------------------------------------------------------------------------

@app.function(
    image=modal.Image.debian_slim(python_version="3.11"),
    schedule=modal.Cron("0 6 * * *"),  # daily, well under the 7-day TTL
    timeout=300,
)
def sweep_expired_paper_tokens() -> int:
    """Delete paper_tokens_dict (+ paper_token_index_dict) entries whose
    expires_at has passed. Returns the number of entries purged."""
    import time as _time

    now = _time.time()
    purged = 0
    for session_id, entry in list(paper_tokens_dict.items()):
        if not isinstance(entry, dict):
            continue
        expires_at = entry.get("expires_at", 0)
        if not expires_at or expires_at >= now:
            continue
        for tok in (entry.get("tokens") or []):
            try:
                del paper_token_index_dict[tok]
            except Exception:
                pass
        try:
            del paper_tokens_dict[session_id]
        except Exception:
            pass
        else:
            purged += 1
    if purged:
        logger.info("sweep_expired_paper_tokens purged %d expired entr%s", purged, "y" if purged == 1 else "ies")
    return purged


# ---------------------------------------------------------------------------
# Scheduled cleanup — proactive TTL sweep for paper_jobs_dict.
#
# /paper-review/status keeps a completed job around for
# PAPER_RESULT_GRACE_SECONDS after first delivery (see `delivered_at`) so a
# refresh, a second tab, or a dropped response doesn't permanently lose a
# paid result, and reaps it itself once that window elapses *if the token
# is polled again*. Jobs that ended in status == "error" (pipeline
# exception, empty result_md), or a delivered job that is never polled
# again after its grace window, are never touched by that inline path and
# would otherwise sit in paper_jobs_dict indefinitely — PAPER_JOB_TTL_SECONDS
# was previously just documentation, not an enforced limit. This cron
# actively deletes any job entry whose grace window (if delivered) or
# overall TTL (if not) has elapsed, regardless of whether it was ever
# polled again. Error entries carry no manuscript text (only status
# metadata + a truncated exception string), so this is a lower-severity
# cleanup than the token sweep above, but it should still happen.
# ---------------------------------------------------------------------------

@app.function(
    image=modal.Image.debian_slim(python_version="3.11"),
    schedule=modal.Cron("30 6 * * *"),  # daily, offset from the token sweep
    timeout=300,
)
def sweep_stale_paper_jobs() -> int:
    """Delete paper_jobs_dict entries past their retention window.

    Delivered jobs (delivered_at set) are purged PAPER_RESULT_GRACE_SECONDS
    after delivery; everything else is purged PAPER_JOB_TTL_SECONDS after
    it started. Covers jobs that ended in status == "error", were never
    polled to completion, or were delivered but never polled again —
    none of which are cleaned up by the normal /paper-review/status
    "done" retrieval path. Returns the number of entries purged.
    """
    import time as _time

    now = _time.time()
    purged = 0
    for token, entry in list(paper_jobs_dict.items()):
        if not isinstance(entry, dict):
            continue
        delivered_at = entry.get("delivered_at")
        if delivered_at is not None:
            if (now - delivered_at) < PAPER_RESULT_GRACE_SECONDS:
                continue
        else:
            started_at = entry.get("started_at", 0)
            if not started_at or (now - started_at) < PAPER_JOB_TTL_SECONDS:
                continue
        try:
            del paper_jobs_dict[token]
        except Exception:
            pass
        else:
            purged += 1
    if purged:
        logger.info("sweep_stale_paper_jobs purged %d stale job entr%s", purged, "y" if purged == 1 else "ies")
    return purged


# ---------------------------------------------------------------------------
# Scheduled lifecycle-email sequence — post-purchase tips, then a review
# request, then an eventual win-back nudge. One stage per run per customer;
# advances customer_lifecycle_dict[session_id]["last_stage_sent"] so a
# customer is never sent the same stage twice, and stops entirely once
# lifecycle_optout_dict[email] is set (checked fresh on every send, not just
# at signup, so an opt-out always takes effect on the next scheduled run).
# See /privacy/ for the disclosure this sequence is scoped to.
# ---------------------------------------------------------------------------

LIFECYCLE_STAGES = [
    # (stage_name, days_after_purchase, template_fn_name)
    ("tips", 3, "html_lifecycle_tips"),
    ("review_request", 14, "html_lifecycle_review_request"),
    ("winback", 90, "html_lifecycle_winback"),
]
LIFECYCLE_STAGE_ORDER = [s[0] for s in LIFECYCLE_STAGES]


@app.function(
    image=modal.Image.debian_slim(python_version="3.11").pip_install("httpx"),
    schedule=modal.Cron("0 14 * * *"),  # daily, 14:00 UTC — mid-morning US
    timeout=600,
    secrets=[resend_secret, subscribe_secret],
)
def lifecycle_email_sweep() -> dict:
    """Advance every customer_lifecycle_dict entry to its next due stage.

    Each entry starts at 'tips' 3 days after purchase, then 'review_request'
    at 14 days, then 'winback' at 90 days (final stage — entry is left in
    place afterward so a customer is never re-sent 'winback' on a later
    run). Runs synchronously over the dict since volumes here are small
    (paid manuscript reviews, not a mailing list); revisit with batching
    if that stops being true.
    """
    import asyncio
    import time as _time

    import httpx

    from latextools import delivery as _delivery

    now = _time.time()
    sent = {"tips": 0, "review_request": 0, "winback": 0}
    skipped_optout = 0

    async def _run():
        nonlocal skipped_optout
        async with httpx.AsyncClient(timeout=10.0) as client:
            for session_id, entry in list(customer_lifecycle_dict.items()):
                if not isinstance(entry, dict):
                    continue
                email = entry.get("email", "")
                if not email:
                    continue
                if lifecycle_optout_dict.get(email):
                    skipped_optout += 1
                    continue

                last_stage = entry.get("last_stage_sent")
                next_index = 0 if last_stage is None else LIFECYCLE_STAGE_ORDER.index(last_stage) + 1
                if next_index >= len(LIFECYCLE_STAGES):
                    continue  # already sent the final stage

                stage_name, days_after, template_fn_name = LIFECYCLE_STAGES[next_index]
                due_at = entry.get("purchased_at", 0) + days_after * 86400
                if now < due_at:
                    continue

                unsubscribe_url = _lifecycle_unsubscribe_url_standalone(email)
                template_fn = getattr(_delivery, template_fn_name)
                if stage_name == "winback":
                    html = template_fn(unsubscribe_url=unsubscribe_url)
                else:
                    html = template_fn(
                        manuscript_title=entry.get("manuscript_title", ""),
                        unsubscribe_url=unsubscribe_url,
                    )

                subject = {
                    "tips": "Getting the most out of your review",
                    "review_request": "How did the review hold up?",
                    "winback": "Still writing?",
                }[stage_name]

                result = await _delivery.send_email(
                    client,
                    to=email,
                    subject=subject,
                    html=html,
                    tags=[{"name": "lifecycle_stage", "value": stage_name}],
                )
                if result.get("status") == "ok":
                    entry["last_stage_sent"] = stage_name
                    entry["last_sent_at"] = now
                    customer_lifecycle_dict[session_id] = entry
                    sent[stage_name] += 1
                else:
                    logger.warning(
                        "lifecycle email stage=%s session_id=%s not sent: %s",
                        stage_name, session_id, result,
                    )

    def _lifecycle_unsubscribe_url_standalone(email: str) -> str:
        import hashlib as _hashlib
        import hmac as _hmac_local
        from urllib.parse import quote as _quote
        secret = os.environ.get("SUBSCRIBE_SECRET", "")
        token = _hmac_local.new(
            secret.encode(), f"lifecycle:{email}".encode(), _hashlib.sha256
        ).hexdigest()
        return (
            "https://purplelink.llc/paper-review/lifecycle/unsubscribe"
            f"?email={_quote(email)}&token={token}"
        )

    asyncio.run(_run())
    total_sent = sum(sent.values())
    if total_sent or skipped_optout:
        logger.info(
            "lifecycle_email_sweep sent=%s skipped_optout=%d", sent, skipped_optout,
        )
    return {**sent, "skipped_optout": skipped_optout}
