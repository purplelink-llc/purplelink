"""Modal MONTHLY cron for the MuscleOnGLP research-review mini-guide.

Runs on the 1st of each month at 13:00 UTC. Synthesizes the just-ended
month's weekly research roundups (published by the research_digest pipeline)
into a NEW paid $1 PDF mini-guide, then auto-lists it for sale on
getmuscleonglp.com:

  clone private repo -> gather the month's roundups -> synthesize a cohesive
  guide -> red-team (medical safety, legal, voice, originality) -> typeset to
  PDF -> create a Stripe product + $1 price -> set the site's STRIPE_PRICE_*
  env var -> upload the PDF to the guide-files Netlify Blobs store -> edit the
  product registry + write the landing/success pages + hub card + sitemap ->
  commit + push -> npm install -> netlify deploy --prod -> email Ben a review
  copy flagging that a NEW PAID guide is now live.

This is money-handling automation. A dry_run=True run stops before ANY live
Stripe / Netlify / commit / push / deploy / email action and instead returns
the rendered PDF path (inside the container) and the synthesized text, so the
whole synthesis can be inspected before it ever charges anyone.

Required Modal secrets (see README.md):
  anthropic-secret -> ANTHROPIC_API_KEY
  github           -> GITHUB_TOKEN         (read+write to purplelink-llc/muscleonglp)
  netlify          -> NETLIFY_AUTH_TOKEN   (deploy + env + blobs on the muscleonglp site)
  resend           -> RESEND_API_KEY       (review email; optional)
  stripe-secret    -> STRIPE_SECRET_KEY    (LIVE key, same Stripe account as the site)
"""
from __future__ import annotations

import base64
import datetime as _dt
import logging
import os
import subprocess
from pathlib import Path

import modal

logger = logging.getLogger(__name__)

app = modal.App("muscleonglp-monthly-guide")

SITE_ID = "c6201581-69ed-4da9-b982-c71c94d30260"
REPO = "purplelink-llc/muscleonglp"
FILE_STORE = "guide-files"

# TeX Live + node + netlify-cli image. The LaTeX packages mirror backend/app.py's
# pinned toolchain (what latextools.runner / muscleonglp.typeset need), plus the
# same texmf hardening (openin_any=p, shell_escape=f) verified at build time.
_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "git",
        "curl",
        "texlive-latex-recommended",
        "texlive-latex-extra",
        "texlive-fonts-recommended",
        "latexmk",
    )
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g netlify-cli@17",
    )
    .pip_install("httpx==0.27.2")
    # Paranoid texmf hardening (same file backend/app.py bakes in), then verify.
    .add_local_file("texmf.cnf", "/etc/texmf/texmf.d/99-hardening.cnf", copy=True)
    .run_commands(
        "update-texmf",
        "test \"$(kpsewhich -var-value=openin_any)\" = p",
        "test \"$(kpsewhich -var-value=shell_escape)\" = f",
    )
    # muscleonglp.typeset/redteam import from latextools; research_digest is the
    # weekly pipeline the roundups come from; monthly_guide is this package.
    .add_local_python_source("monthly_guide")
    .add_local_python_source("muscleonglp")
    .add_local_python_source("research_digest")
    .add_local_python_source("latextools")
)


def _previous_month(now: _dt.datetime) -> tuple[int, int]:
    """Return (year, month) of the month before *now* (the just-ended month)."""
    first_of_this = now.replace(day=1)
    last_of_prev = first_of_this - _dt.timedelta(days=1)
    return last_of_prev.year, last_of_prev.month


def _resolve_month(month: str) -> tuple[int, int]:
    """Resolve the target (year, month). *month* is an optional 'YYYY-MM'
    override for testing; empty means the just-ended calendar month (UTC)."""
    if month:
        y, m = month.split("-")
        return int(y), int(m)
    return _previous_month(_dt.datetime.now(_dt.timezone.utc))


@app.function(
    image=_image,
    schedule=modal.Cron("0 13 1 * *"),  # 1st of the month, 13:00 UTC
    secrets=[
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("github"),
        modal.Secret.from_name("netlify"),
        modal.Secret.from_name("resend"),
        modal.Secret.from_name("stripe-secret"),
    ],
    timeout=1800,
)
async def run_monthly_guide(dry_run: bool = False, month: str = ""):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import httpx

    from monthly_guide import publish
    from monthly_guide.roundups import (
        gather_month_roundups, monthly_citation_block, assign_paper_keys)
    from monthly_guide.synthesize import draft_monthly_guide
    from muscleonglp.redteam import run_redteam_passes
    from muscleonglp.typeset import render_guide_pdf

    dry_run = dry_run or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    netlify_token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")

    year, mon = _resolve_month(month)
    label = publish.month_label(year, mon)
    slug = publish.month_slug(year, mon)
    title = publish.guide_title(year, mon)
    logger.info("monthly: target month=%s slug=%s dry_run=%s", label, slug, dry_run)

    # --- clone the repo (read-only use in dry_run) to read the roundups ---
    site = "/root/site"
    if not gh_token:
        raise RuntimeError("GITHUB_TOKEN is required to read the month's roundups")
    clone_url = f"https://x-access-token:{gh_token}@github.com/{REPO}.git"
    subprocess.run(["git", "clone", clone_url, site], check=True)

    roundups = gather_month_roundups(site, year, mon)
    if not roundups:
        logger.info("monthly: no roundups found for %s; nothing to publish", label)
        return {"slug": slug, "month_label": label, "roundup_count": 0, "published": False}
    logger.info("monthly: gathered %d roundup(s) for %s", len(roundups), label)
    all_papers = [p for r in roundups for p in r.papers]
    # The month's papers cite DIFFERENT sources than the flagship guide, so
    # build a month-specific approved-source block (keyed p1..pN) and feed it
    # to BOTH the synthesis (so it tags claims by key) and the red-team passes
    # (so medical_safety checks against this month's sources, not the flagship
    # citation_block()).
    monthly_citations = monthly_citation_block(all_papers)

    # Long read timeout: LLM synthesis + each red-team pass can take 30-90s; the
    # httpx default (5s) times out mid-generation. Mirrors the paper-review pipeline.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
    ) as client:
        draft = await draft_monthly_guide(
            client, label, [r.to_text() for r in roundups], monthly_citations)
        final_text, verdicts = await run_redteam_passes(
            client, draft, citations=monthly_citations)
        for v in verdicts:
            logger.info("monthly: red-team %s approved=%s", v.pass_name, v.approved)

        pdf_path = Path("/tmp") / publish.pdf_filename(slug)
        references = [(k, p.title, p.meta, p.url) for k, p in assign_paper_keys(all_papers)]
        render_guide_pdf(
            final_text, pdf_path, title=title,
            subtitle=f"New {label} research on muscle, lean mass, protein, and training",
            references=references,
        )
        logger.info("monthly: rendered PDF -> %s (%d bytes)", pdf_path, pdf_path.stat().st_size)

        if dry_run:
            logger.info("monthly: DRY_RUN — stopping before any live Stripe/Netlify/deploy")
            return {
                "slug": slug,
                "month_label": label,
                "title": title,
                "roundup_count": len(roundups),
                "paper_count": len(all_papers),
                "pdf_path": str(pdf_path),
                "pdf_b64": base64.b64encode(pdf_path.read_bytes()).decode("ascii"),
                "text": final_text,
                "published": False,
            }

        # ----- LIVE actions below (skipped entirely in dry_run) -----
        from monthly_guide.stripe_api import create_monthly_product
        from monthly_guide.netlify_api import set_env_var, blobs_set
        from monthly_guide.mailer import notify_new_guide

        # 1. Stripe product + $1 price (idempotent by slug metadata).
        price_id = create_monthly_product(stripe_key, title, slug)
        logger.info("monthly: stripe price=%s", price_id)

        # 2. Site env var so checkout.mjs can resolve the new product's price.
        key = publish.env_key(slug)
        set_env_var(netlify_token, SITE_ID, key, price_id)

        # 3. Upload the PDF to the guide-files Blobs store (download.mjs streams it).
        blobs_set(netlify_token, SITE_ID, FILE_STORE, publish.pdf_filename(slug), str(pdf_path))

        # 4. Filesystem edits: registry, landing + success pages, hub card, sitemap.
        publish.list_monthly_guide(site, year, mon, date=roundups[-1].date, papers=all_papers)

        # 5. Commit + push (the repo is the source of truth for the next run).
        subprocess.run(["git", "-C", site, "config", "user.email", "ben.ampel@gmail.com"], check=True)
        subprocess.run(["git", "-C", site, "config", "user.name", "MuscleOnGLP Bot"], check=True)
        subprocess.run(["git", "-C", site, "add", "-A"], check=True)
        subprocess.run(["git", "-C", site, "commit", "-m", f"guides: monthly review {slug}"], check=False)
        subprocess.run(["git", "-C", site, "push", "origin", "HEAD:main"], check=True)

        # 6. npm install (so the CLI bundles @netlify/blobs) + deploy.
        subprocess.run(["npm", "install"], cwd=site, check=True)
        env = {**os.environ, "NETLIFY_AUTH_TOKEN": netlify_token}
        subprocess.run(
            ["netlify", "deploy", "--prod", "--dir", ".",
             "--functions", "netlify/functions", "--site", SITE_ID,
             "--message", f"monthly research review {slug}"],
            cwd=site, env=env, check=True,
        )
        logger.info("monthly: deployed %s", slug)

        # 7. Email Ben that a NEW PAID guide is live.
        sent = await notify_new_guide(
            client, month_label=label, slug=slug, title=title, price_id=price_id,
            env_key=key, roundup_count=len(roundups), resend_key=resend_key,
        )
        logger.info("monthly: review email sent=%s", sent)

    return {
        "slug": slug,
        "month_label": label,
        "title": title,
        "price_id": price_id,
        "roundup_count": len(roundups),
        "published": True,
    }


@app.local_entrypoint()
def main(dry_run: bool = True, month: str = ""):
    """Local entrypoint. Defaults to dry_run=True so a bare
    `modal run monthly_guide/app.py` never charges anyone.

    Examples:
      modal run monthly_guide/app.py                       # dry run, previous month
      modal run monthly_guide/app.py --month 2026-07       # dry run, July 2026
      modal run monthly_guide/app.py --dry-run False       # LIVE (lists for sale)
    """
    res = run_monthly_guide.remote(dry_run=dry_run, month=month)
    if not res:
        print("no result"); return
    print(f"slug={res.get('slug')} month={res.get('month_label')} "
          f"roundups={res.get('roundup_count')} published={res.get('published')}")
    if res.get("pdf_b64"):
        out = os.environ.get("LOCAL_PDF_OUT", "/tmp/monthly-guide-dryrun.pdf")
        with open(out, "wb") as f:
            f.write(base64.b64decode(res["pdf_b64"]))
        print(f"LOCAL_PDF={out}")
    if res.get("text"):
        print("---- synthesized text (first 1200 chars) ----")
        print(res["text"][:1200])
