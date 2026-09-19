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
FROM_EMAIL = "Purplelink Daily Digest <ben@purplelink.llc>"
SITE_URL = "https://purplelink.llc"
SUBSCRIBERS_URL = f"{SITE_URL}/.netlify/functions/subscribers-list"


def _unsubscribe_url(email: str, secret: str) -> str:
    token = hmac.new(secret.encode(), email.encode(), hashlib.sha256).hexdigest()
    return (
        f"{SITE_URL}/.netlify/functions/unsubscribe"
        f"?email={quote(email)}&token={token}"
    )


async def _get_subscribers(client: httpx.AsyncClient, subscribe_secret: str) -> list[dict]:
    try:
        resp = await client.get(
            SUBSCRIBERS_URL,
            headers={"Authorization": f"Bearer {subscribe_secret}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("subscribers", [])
    except Exception as exc:
        logger.warning("mailer: get_subscribers failed: %s", exc)
        return []


def split_by_send_group(subscribers: list[dict], delayed_slug: str) -> tuple[list[dict], list[dict]]:
    """Split subscribers into (same_day, delayed) groups.

    paid/legacy -> same_day, always. A missing `tier` field is treated as
    legacy (same-day) -- not free -- since subscribe.mjs's backfill only
    runs when someone re-submits the signup form, so a record can reach
    this function with no tier field at all. Treating that as "free"
    would silently start delaying delivery to people who've had same-day
    delivery all along; treating it as legacy preserves what they already
    have, matching this whole feature's grandfathering principle.

    free -> delayed, but only if this subscriber hasn't already received
    the specific issue being delayed-sent today (last_sent_slug check) --
    the idempotency guard that lets a missed cron run self-heal on the next
    run instead of double-sending or permanently skipping someone.
    """
    same_day, delayed = [], []
    for sub in subscribers:
        tier = sub.get("tier") or "legacy"
        if tier in ("paid", "legacy"):
            same_day.append(sub)
        elif tier == "free":
            if sub.get("last_sent_slug") != delayed_slug:
                delayed.append(sub)
    return same_day, delayed


async def _mark_sent(client: httpx.AsyncClient, email: str, slug: str, subscribe_secret: str) -> None:
    try:
        resp = await client.post(
            f"{SITE_URL}/.netlify/functions/subscriber-update",
            headers={"Authorization": f"Bearer {subscribe_secret}", "Content-Type": "application/json"},
            json={"email": email, "fields": {"last_sent_slug": slug}},
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("mailer: mark_sent failed for %s: %s", email, exc)


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
    delayed_digest=None,
    delayed_slug: str = "",
) -> int:
    """Fetch subscriber list, split by send group, email each. Returns
    total count sent across both groups.

    delayed_digest/delayed_slug: the digest from DELAY_DAYS ago (see
    app.py), already reloaded from its JSON snapshot -- None if that day
    has no snapshot (predates this feature), in which case the delayed
    group is simply skipped this run rather than erroring; those
    subscribers catch up automatically once a snapshotted day reaches the
    right age.
    """
    from digest.publisher import _fmt_date

    async with httpx.AsyncClient() as client:
        subscribers = await _get_subscribers(client, subscribe_secret)
        if not subscribers:
            logger.info("mailer: no subscribers, skipping email send")
            return 0

        same_day, delayed = split_by_send_group(subscribers, delayed_slug)
        sent = 0

        subject = f"Purplelink Daily Digest #{digest.number} — {_fmt_date(digest.date)}"
        for sub in same_day:
            email = sub["email"]
            tier = sub.get("tier") or "legacy"
            unsub_url = _unsubscribe_url(email, subscribe_secret)
            html = render_email_html(digest, unsubscribe_url=unsub_url, tier=tier)
            await _send_one(client, email, subject, html, resend_key)
            sent += 1

        if delayed_digest is not None and delayed:
            delayed_subject = f"Purplelink Daily Digest #{delayed_digest.number} — {_fmt_date(delayed_digest.date)}"
            for sub in delayed:
                email = sub["email"]
                unsub_url = _unsubscribe_url(email, subscribe_secret)
                html = render_email_html(delayed_digest, unsubscribe_url=unsub_url, tier="free")
                await _send_one(client, email, delayed_subject, html, resend_key)
                await _mark_sent(client, email, delayed_slug, subscribe_secret)
                sent += 1
        elif delayed:
            logger.info("mailer: %d free-tier subscriber(s) behind, but no snapshot for %s yet", len(delayed), delayed_slug)

        logger.info("mailer: done, sent=%d (same_day=%d, delayed=%d)", sent, len(same_day), len(delayed))
        return sent
