# backend/listen/app.py
"""Modal scheduled function for the listen-and-surface agent.

Polls HN (Algolia Search API) and Stack Exchange (Academia site) daily for
posts that look like genuine near-term intent to use one of Purplelink's
manuscript tools, scores them with Claude, and emails a digest to the
founder with suggested (never auto-posted) replies for human review.

Runs daily at 11:00 UTC, offset from the content digest cron (10:00 UTC)
so the two crons don't compete for the same Anthropic rate-limit window.

Required Modal secrets:
  anthropic-secret -> ANTHROPIC_API_KEY
  resend           -> RESEND_API_KEY

Set DRY_RUN=1 to skip the email send and print a preview to stdout instead.
"""
import logging
import os

import modal

logger = logging.getLogger(__name__)

app = modal.App("purplelink-listen")

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx==0.27.2")
    .add_local_python_source("listen", "digest")
)

FOUNDER_EMAIL = "ben@purplelink.llc"
RESEND_API = "https://api.resend.com/emails"
FROM_EMAIL = "Purplelink Listen Agent <ben@purplelink.llc>"


@app.function(
    image=_image,
    schedule=modal.Cron("0 11 * * *"),
    secrets=[
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("resend"),
    ],
    timeout=600,
)
async def run_daily_listen():
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    import httpx
    from listen.renderer import render_digest_html, REPLY_THRESHOLD
    from listen.scorer import score_items
    from listen.sources import fetch_hn, fetch_stackexchange

    resend_key = os.environ.get("RESEND_API_KEY", "")
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    async with httpx.AsyncClient(timeout=20.0) as client:
        hn_items = await fetch_hn(client)
        se_items = await fetch_stackexchange(client)
        all_items = hn_items + se_items
        logger.info(
            "listen: found %d HN + %d SE = %d total items",
            len(hn_items), len(se_items), len(all_items),
        )

        scores = await score_items(client, all_items)
        scored_pairs = list(zip(all_items, scores))

        html_body = render_digest_html(scored_pairs)
        actionable = sum(1 for _, s in scored_pairs if s.get("score", 0) >= REPLY_THRESHOLD)
        subject = f"Listen agent: {actionable} worth a look" if actionable else "Listen agent: nothing today"

        if dry_run or not resend_key:
            reason = "DRY_RUN set" if dry_run else "RESEND_API_KEY not set"
            print(f"=== not emailing ({reason}) ===")
            print(subject)
            print(html_body[:1000])
            return

        resp = await client.post(
            RESEND_API,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": FROM_EMAIL, "to": FOUNDER_EMAIL, "subject": subject, "html": html_body},
        )
        resp.raise_for_status()
        logger.info("listen: digest emailed to %s (id=%s)", FOUNDER_EMAIL, resp.json().get("id", "?"))


if __name__ == "__main__":
    import asyncio
    os.environ.setdefault("DRY_RUN", "1")
    asyncio.run(run_daily_listen.local())
