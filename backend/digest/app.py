"""Modal scheduled function for the daily digest.

Runs daily at 10:00 UTC (6am ET). Set DRY_RUN=1 to skip GitHub push
and print a preview to stdout instead.

Required Modal secrets:
  anthropic-secret   -> ANTHROPIC_API_KEY
  github             -> GITHUB_TOKEN

Optional Modal secrets:
  subscribe-secret   -> SUBSCRIBE_SECRET      (enables email sending)
  resend             -> RESEND_API_KEY         (enables email sending)
  linkedin           -> LINKEDIN_ACCESS_TOKEN  (enables LinkedIn post)
                     -> LINKEDIN_AUTHOR_URN    (person or org URN)
"""
import logging
import os

import modal

logger = logging.getLogger(__name__)

app = modal.App("purplelink-digest")

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "httpx==0.27.2",
        "feedparser>=6,<7",
        "anthropic>=0.25,<1",
    )
    .add_local_python_source("digest")
)


@app.function(
    image=_image,
    schedule=modal.Cron("0 10 * * *"),
    secrets=[
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("github"),
        modal.Secret.from_name("subscribe-secret"),
        modal.Secret.from_name("resend"),
        modal.Secret.from_name("linkedin", required=False),
    ],
    timeout=600,
)
async def run_daily_digest():
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    import httpx
    from digest.harvester import harvest_all
    from digest.curator import curate
    from digest.publisher import publish, render_html

    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    subscribe_secret = os.environ.get("SUBSCRIBE_SECRET", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    linkedin_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    linkedin_author_urn = os.environ.get("LINKEDIN_AUTHOR_URN", "")

    logger.info("digest: starting (dry_run=%s)", dry_run)

    async with httpx.AsyncClient(timeout=30.0) as client:
        items = await harvest_all(client)
        logger.info("digest: harvested %d items", len(items))

        digest = await curate(client, items)

    if digest is None:
        logger.warning("digest: curation aborted (too few items)")
        return

    logger.info(
        "digest: %d items selected from %d reviewed",
        digest.items_selected, digest.sources_reviewed,
    )

    if dry_run:
        print("=== DRY RUN — not publishing ===")
        print(f"Date: {digest.date}, Intro: {digest.intro[:100]}...")
        for section, section_items in digest.sections.items():
            print(f"\n{section} ({len(section_items)} items):")
            for it in section_items:
                print(f"  - {it.title} ({it.source_name})")
        print("\n=== HTML preview (first 500 chars) ===")
        print(render_html(digest)[:500])
        return

    await publish(digest, github_token, linkedin_token, linkedin_author_urn)
    logger.info("digest: published successfully")

    if subscribe_secret and resend_key:
        from digest.mailer import mail_digest
        from digest.publisher import render_email_html
        sent = await mail_digest(digest, render_email_html, subscribe_secret, resend_key)
        logger.info("digest: emailed %d subscribers", sent)
    else:
        logger.info("digest: email skipped (SUBSCRIBE_SECRET or RESEND_API_KEY not set)")


if __name__ == "__main__":
    import asyncio
    os.environ.setdefault("DRY_RUN", "1")
    asyncio.run(run_daily_digest.local())
