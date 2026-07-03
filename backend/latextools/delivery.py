"""Transactional email delivery for paid Paper Review tools.

Uses Resend (https://resend.com) — a small, modern transactional email API
with generous free tier. Falls back gracefully when not configured: the
caller's flow still completes; only the email step is skipped.

Required env var (set as Modal secret `resend-secret`):
  RESEND_API_KEY — `re_…` from the Resend dashboard.

A verified sending domain (`mail.purplelink.llc` or similar) must also be
configured in the Resend dashboard — this is a separate, manual step from
setting the API key. This module does NOT check verification status ahead
of time (Resend has no cheap "is this domain verified" endpoint); if the
key is set but the domain is unverified, every send fails with a 403 from
Resend. send_email() detects that specific case and returns
{"status": "error", "reason": "domain_not_verified", ...} instead of a
generic resend_http_403, so callers/logs can tell the two apart.
"""
from __future__ import annotations

import asyncio
import base64
import html as _html
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "Purplelink Paper Review <reviews@mail.purplelink.llc>"


def _is_valid_email(addr: str) -> bool:
    if not addr or not isinstance(addr, str) or len(addr) > 254:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr))


def _is_domain_not_verified_error(status_code: int, body_text: str) -> bool:
    """True if a Resend error response indicates the sending domain has not
    completed domain verification (a separate, manual dashboard step from
    setting RESEND_API_KEY). Resend returns 403 with a message mentioning
    the domain in this case; matched loosely since Resend does not expose a
    stable machine-readable error code for it."""
    if status_code != 403:
        return False
    lowered = (body_text or "").lower()
    return "domain" in lowered and (
        "not verified" in lowered or "verify" in lowered
    )


async def send_email(
    client,
    *,
    to: str,
    subject: str,
    html: str,
    plain_text: Optional[str] = None,
    attachments: Optional[list[dict]] = None,
    tags: Optional[list[dict]] = None,
) -> dict:
    """POST to Resend. Returns {"status": "ok"|"skipped"|"error", ...}.

    *attachments* — list of {"filename": str, "content": bytes-or-base64-str}
    *tags* — list of {"name": "...", "value": "..."} for Resend analytics
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.info("RESEND_API_KEY not set; skipping email send to %s", to)
        return {"status": "skipped", "reason": "no_api_key"}

    if not _is_valid_email(to):
        return {"status": "error", "reason": "invalid_email"}

    body: dict = {
        "from": FROM_ADDRESS,
        "to": [to],
        "subject": subject[:200],
        "html": html,
    }
    if plain_text:
        body["text"] = plain_text
    if tags:
        body["tags"] = tags

    if attachments:
        encoded = []
        for att in attachments:
            content = att.get("content")
            if isinstance(content, bytes):
                content = base64.b64encode(content).decode("ascii")
            if not content:
                continue
            encoded.append({
                "filename": att.get("filename", "attachment"),
                "content": content,
            })
        if encoded:
            body["attachments"] = encoded

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Retry transient failures (network errors, timeouts, 429 rate-limit,
    # 5xx) with exponential backoff, mirroring the hardening applied to the
    # Anthropic client in papercheck._anthropic_message. Non-transient 4xx
    # (bad request, auth, invalid recipient, etc.) fail fast on the first
    # attempt since a retry won't change the outcome.
    max_attempts = 3
    last_err: Optional[dict] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.post(RESEND_API_URL, json=body, headers=headers)
        except Exception as e:
            logger.warning("Resend send attempt %d/%d failed: %s", attempt, max_attempts, e)
            last_err = {"status": "error", "reason": str(e)[:200]}
            if attempt < max_attempts:
                await asyncio.sleep((attempt * attempt) * 2.0)  # 2s, 8s
                continue
            logger.exception("Resend send failed after %d attempts", max_attempts)
            return last_err

        if resp.status_code >= 300:
            text = ""
            try:
                text = resp.text[:300]
            except Exception:
                pass
            if _is_domain_not_verified_error(resp.status_code, text):
                logger.error(
                    "Resend rejected send: sending domain is not verified "
                    "(RESEND_API_KEY is set, but the Resend dashboard domain "
                    "verification step was not completed). detail=%s",
                    text,
                )
                return {
                    "status": "error",
                    "reason": "domain_not_verified",
                    "detail": text,
                }
            transient = resp.status_code == 429 or resp.status_code >= 500
            last_err = {
                "status": "error",
                "reason": f"resend_http_{resp.status_code}",
                "detail": text,
            }
            if transient and attempt < max_attempts:
                logger.warning(
                    "Resend returned %d (attempt %d/%d), retrying: %s",
                    resp.status_code, attempt, max_attempts, text,
                )
                retry_after = resp.headers.get("retry-after")
                try:
                    delay = float(retry_after) if retry_after else (attempt * attempt) * 2.0
                except ValueError:
                    delay = (attempt * attempt) * 2.0
                await asyncio.sleep(delay)
                continue
            logger.warning("Resend returned %d: %s", resp.status_code, text)
            return last_err

        try:
            data = resp.json()
            return {"status": "ok", "id": data.get("id")}
        except Exception:
            return {"status": "ok", "id": None}

    return last_err  # pragma: no cover — loop always returns/continues above


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

_EMAIL_BASE_CSS = (
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
    "line-height: 1.55; color: #1a1a1a; max-width: 600px;"
)


def html_review_ready(
    *, status_url: str, manuscript_title: str = "", amount_cents: int = 900
) -> str:
    title = manuscript_title or "(your manuscript)"
    title = _html.escape(title[:200])
    refund_amount = f"${amount_cents / 100:.2f}".rstrip("0").rstrip(".")
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your Paper Review is ready</h2>
  <p>The red-team review of <strong>{title}</strong> has finished.</p>
  <p>
    <a href="{status_url}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 12px 22px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Open my review
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">
    The review is held on our server only until you retrieve it. Open the
    link soon and save a copy locally — once you download the Markdown, the
    review is deleted from our infrastructure.
  </p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">
    Sent by Purplelink LLC. If a review is low-quality, reply to this email
    and we'll refund the {refund_amount}.
  </p>
</div>
"""


def html_volume_pack_tokens(*, tokens: list[str], pack_size: int) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 10px;border:1px solid #eee;font-family:monospace;font-size:13px;">{t}</td>'
        f'<td style="padding:6px 10px;border:1px solid #eee;">'
        f'<a href="https://purplelink.llc/tools/paper-review/upload/?direct_token={t}">Use this token</a>'
        f'</td></tr>'
        for t in tokens
    )
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your {pack_size}-pack of Paper Reviews</h2>
  <p>Thanks for the volume purchase. Below are your {pack_size} review
  tokens. Each token is good for one manuscript review. Use them whenever
  you want — tokens don't expire.</p>
  <table style="border-collapse: collapse; margin: 12px 0; font-size: 0.9em;">
    {rows}
  </table>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Start a review
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">
    Store this email somewhere safe — the tokens above are your only copy.
    If you misplace them, reply to this email with your Stripe receipt.
  </p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC.</p>
</div>
"""


def html_invoice_ready(*, invoice_url: str, amount_cents: int) -> str:
    dollars = f"${amount_cents / 100:.2f}"
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your Purplelink invoice</h2>
  <p>The invoice for your {dollars} purchase is ready.</p>
  <p>
    <a href="{invoice_url}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Download the invoice (PDF)
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">
    The invoice is itemised for institutional reimbursement. If you need
    your institution's tax ID added to the invoice line, reply to this
    email with the details and we'll re-issue it.
  </p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC.</p>
</div>
"""
