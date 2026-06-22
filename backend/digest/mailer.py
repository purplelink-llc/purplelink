# backend/digest/mailer.py
"""Send the daily digest email to all subscribers via Resend.

Called from app.py after publish() succeeds when RESEND_API_KEY is set.

Required env vars:
  RESEND_API_KEY      — Resend API key
  SUBSCRIBE_SECRET    — shared secret used to sign unsubscribe tokens
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Callable
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"
FROM_EMAIL = "Daily Digest <ben@purplelink.llc>"
SITE_URL = "https://purplelink.llc"
SUBSCRIBERS_URL = f"{SITE_URL}/.netlify/functions/subscribers-list"


def _unsubscribe_url(email: str, secret: str) -> str:
    token = hmac.new(secret.encode(), email.encode(), hashlib.sha256).hexdigest()
    return (
        f"{SITE_URL}/.netlify/functions/unsubscribe"
        f"?email={quote(email)}&token={token}"
    )


async def _get_subscribers(client: httpx.AsyncClient, subscribe_secret: str) -> list[str]:
    try:
        resp = await client.get(
            SUBSCRIBERS_URL,
            headers={"Authorization": f"Bearer {subscribe_secret}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("emails", [])
    except Exception as exc:
        logger.warning("mailer: get_subscribers failed: %s", exc)
        return []


async def _send_one(
    client: httpx.AsyncClient,
    email: str,
    subject: str,
    html: str,
    resend_key: str,
) -> None:
    try:
        resp = await client.post(
            RESEND_API,
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={"from": FROM_EMAIL, "to": email, "subject": subject, "html": html},
            timeout=15.0,
        )
        resp.raise_for_status()
        logger.info("mailer: sent to %s (id=%s)", email, resp.json().get("id", "?"))
    except Exception as exc:
        logger.warning("mailer: send to %s failed: %s", email, exc)


async def mail_digest(
    digest,
    render_email_html: Callable,
    subscribe_secret: str,
    resend_key: str,
) -> int:
    """Fetch subscriber list and email the digest to each. Returns count sent."""
    from digest.publisher import _fmt_date

    async with httpx.AsyncClient() as client:
        subscribers = await _get_subscribers(client, subscribe_secret)
        if not subscribers:
            logger.info("mailer: no subscribers, skipping email send")
            return 0

        subject = f"Daily Digest #{digest.number} — {_fmt_date(digest.date)}"
        sent = 0

        for email in subscribers:
            unsub_url = _unsubscribe_url(email, subscribe_secret)
            html = render_email_html(digest, unsubscribe_url=unsub_url)
            await _send_one(client, email, subject, html, resend_key)
            sent += 1

        logger.info("mailer: done, sent=%d/%d", sent, len(subscribers))
        return sent
