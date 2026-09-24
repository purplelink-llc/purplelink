"""Transactional email delivery for paid Paper Review tools.

Uses Resend (https://resend.com) — a small, modern transactional email API
with generous free tier. Falls back gracefully when not configured: the
caller's flow still completes; only the email step is skipped.

Required env var (set as Modal secret `resend-secret`):
  RESEND_API_KEY — `re_…` from the Resend dashboard.

The FROM_ADDRESS domain must be verified in the Resend dashboard — this is
a separate, manual step from setting the API key. Resend verifies domains
exactly: the apex `purplelink.llc` is verified, but a subdomain such as
`mail.purplelink.llc` is treated as a distinct domain that must be added and
verified on its own. Sending from an unverified domain fails with a 403, so
FROM_ADDRESS must stay on `purplelink.llc` unless a subdomain is separately
verified. This module does NOT check verification status ahead of time
(Resend has no cheap "is this domain verified" endpoint); if the key is set
but the domain is unverified, every send fails with a 403 from Resend.
send_email() detects that specific case and returns
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
FROM_ADDRESS = "Purplelink Paper Review <reviews@purplelink.llc>"
# Every email invites a reply, and reviews@ is not a monitored inbox.
REPLY_TO = "ben@purplelink.llc"


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
    from_name: Optional[str] = None,
) -> dict:
    """POST to Resend. Returns {"status": "ok"|"skipped"|"error", ...}.

    *from_name* replaces the display name ("Purplelink Paper Review") for
    emails that are not about Paper Review; the address stays on the
    verified domain.

    *attachments* — list of {"filename": str, "content": bytes-or-base64-str}
    *tags* — list of {"name": "...", "value": "..."} for Resend analytics
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.info("RESEND_API_KEY not set; skipping email send to %s", to)
        return {"status": "skipped", "reason": "no_api_key"}

    if not _is_valid_email(to):
        return {"status": "error", "reason": "invalid_email"}

    sender = FROM_ADDRESS
    if from_name:
        sender = f"{from_name} <{FROM_ADDRESS.split('<', 1)[1]}"
    body: dict = {
        "from": sender,
        "reply_to": REPLY_TO,
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


# What the ready email calls each product, and the one next step it offers.
# Keys are PAID_PRODUCTS keys (adjacent tools) or "paper-review".
_READY_NAMES = {
    "paper-review": "Paper Review",
    "citation-gap": "Citation Gap report",
    "anonymity-check": "Anonymity Check",
    "cover-letter": "cover letter draft",
    "revision-review": "Revision Review",
    "response-review": "Response Review",
    "resume-review": "Resume Review",
}
_LINK = 'style="color: #6d28d9;"'
_READY_NEXT = {
    "paper-review": (
        f'Next, if you need it: <a href="https://purplelink.llc/tools/citation-gap/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Citation Gap</a> '
        f'($3) lists prior work a reviewer may expect you to cite, and <a href="https://purplelink.llc/tools/cover-letter/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Cover Letter</a> '
        '($2) drafts the letter from your abstract.'
    ),
    "citation-gap": (
        f'For the full read, <a href="https://purplelink.llc/tools/paper-review/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Paper Review</a> '
        '($9) puts the manuscript in front of four AI reviewers and checks every reference against CrossRef.'
    ),
    "anonymity-check": (
        f'For the full read, <a href="https://purplelink.llc/tools/paper-review/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Paper Review</a> '
        '($9) covers methods, statistics and references, with an anonymity scan included.'
    ),
    "cover-letter": (
        f'Before you send it, <a href="https://purplelink.llc/tools/paper-review/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Paper Review</a> '
        '($9) reads the manuscript the way a reviewer panel would.'
    ),
    "response-review": (
        f'For the manuscript itself, <a href="https://purplelink.llc/tools/paper-review/revision/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Revision Review</a> '
        '($2) checks the revision against the findings in your original Paper Review.'
    ),
    "revision-review": (
        f'For the letter that goes with it, <a href="https://purplelink.llc/tools/response-review/?utm_source=email&amp;utm_campaign=ready" {_LINK}>Response Review</a> '
        '($6) checks every reply against the reviewer comments.'
    ),
}


def html_review_ready(
    *, status_url: str, manuscript_title: str = "", amount_cents: int = 900,
    product: str = "paper-review",
) -> str:
    name = _READY_NAMES.get(product, "result")
    refund_amount = f"${amount_cents / 100:.2f}".rstrip("0").rstrip(".")
    if product == "paper-review":
        title = _html.escape((manuscript_title or "(your manuscript)")[:200])
        lead = f"The red-team review of <strong>{title}</strong> has finished."
        cta = "Open my review"
    else:
        lead = "It has finished and is waiting for you."
        cta = "Open it"
    next_step = _READY_NEXT.get(product, "")
    next_html = f'\n  <p style="color: #555; font-size: 0.9em;">{next_step}</p>' if next_step else ""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your {name} is ready</h2>
  <p>{lead}</p>
  <p>
    <a href="{status_url}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 12px 22px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      {cta}
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">
    Open it within 24 hours and save a copy when the page loads. The result
    is deleted from our server 30 minutes after you first open it, or after
    24 hours if you never do.
  </p>{next_html}
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">
    Sent by Purplelink LLC. If a result is low quality, reply to this email
    within 14 days and we'll refund the {refund_amount}.
  </p>
</div>
"""


def html_purchase_link(*, product_name: str, link: str) -> str:
    """Sent at purchase for single-use tools, so a buyer who paid on one
    device, or closed the tab, can upload later from another."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your {_html.escape(product_name)} is paid for</h2>
  <p>Thanks for your purchase. When you are ready, open this link to start:
  upload your file or paste your text. It works on any device, and you can
  use it once within 7 days.</p>
  <p>
    <a href="{_html.escape(link)}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 12px 22px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Open my purchase
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">Keep this email until you have
  used the link. Anyone with it can use your purchase.</p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC. Questions:
  reply to this email.</p>
</div>
"""


def html_purchase_waiting(*, product_name: str, link: str, ends: str) -> str:
    """One reminder for a single purchase that has not been used two days in."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your {_html.escape(product_name)} is still waiting</h2>
  <p>You paid for this a couple of days ago and have not started it yet.
  The link below works on any device until {_html.escape(ends)}.</p>
  <p>
    <a href="{_html.escape(link)}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 12px 22px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Open my purchase
    </a>
  </p>
  <p>If something went wrong, or the upload did not work, reply to this
  email and we will sort it out.</p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC about a
  purchase you made. This is the only reminder.</p>
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
  you want; tokens don't expire.</p>
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
    Store this email somewhere safe. The tokens above are your only copy.
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


def _lifecycle_footer(unsubscribe_url: str, product_name: str = "a Paper Review", reason: str = "") -> str:
    why = reason or f"because you bought {product_name}. A few follow-up emails about that purchase, and no mailing list."
    return f"""
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">
    Sent by Purplelink LLC {why}
    <a href="{unsubscribe_url}" style="color: #888;">Unsubscribe</a>.
  </p>
"""


def html_lifecycle_tips(*, manuscript_title: str = "", unsubscribe_url: str) -> str:
    title = _html.escape((manuscript_title or "your manuscript")[:200])
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Getting the most out of your review</h2>
  <p>A few days ago you ran a Paper Review on {title}. A couple of things
  that help authors get more out of it:</p>
  <ul style="padding-left: 20px;">
    <li>Work top-down through the flagged issues by severity, not by
    section order. The highest-severity ones are what a real reviewer
    would raise first.</li>
    <li>Where the review disagrees with a choice you made deliberately,
    that disagreement is still useful: it tells you the reasoning isn't
    landing on the page and needs to be made explicit.</li>
    <li>After you revise, <a href="https://purplelink.llc/tools/paper-review/revision/?utm_source=email&amp;utm_campaign=tips" style="color: #6d28d9;">Revision Review</a>
    ($2) checks the new version against this review's findings and flags
    anything the edits introduced. Keep the Markdown file; it reads it.</li>
  </ul>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Run another review
    </a>
  </p>
  {_lifecycle_footer(unsubscribe_url)}
</div>
"""


def html_lifecycle_review_request(*, manuscript_title: str = "", unsubscribe_url: str) -> str:
    title = _html.escape((manuscript_title or "your manuscript")[:200])
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">How did the review hold up?</h2>
  <p>You ran a Paper Review on {title} a little while ago. If it caught
  something a real reviewer later raised too, or missed something they
  did catch, I'd like to know. Just reply to this email.</p>
  <p>That feedback goes directly into what gets fixed next; this is a
  small, actively-maintained tool, not a product team.</p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #555; font-size: 0.9em;">
    Submitting elsewhere soon? A second pass on the camera-ready draft
    often catches things a first pass misses.
  </p>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Run another review
    </a>
  </p>
  {_lifecycle_footer(unsubscribe_url)}
</div>
"""


def html_lifecycle_winback(*, unsubscribe_url: str) -> str:
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Still writing?</h2>
  <p>It's been a while since your last Paper Review. If you've got a new
  manuscript, a fresh red-team pass before submission is usually cheap
  insurance against the reviews that actually sting.</p>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Start a review
    </a>
  </p>
  {_lifecycle_footer(unsubscribe_url)}
</div>
"""


def html_lifecycle_mtx_tips(*, unsubscribe_url: str, **_ignored) -> str:
    """Day 3 after a ModernTex purchase: the features people most often miss."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">A few things in ModernTex worth knowing</h2>
  <p>Thanks for buying ModernTex. Now that you have had it a few days, here
  are four parts that are easy to miss:</p>
  <ul style="padding-left: 20px;">
    <li><strong>Three compile modes.</strong> Fast for drafting, Live to keep
    the PDF updating as you type, and Full for the complete pass before you
    submit.</li>
    <li><strong>Citations by name, not key.</strong> BibTeX autocomplete
    searches your .bib by author and title, so you do not need to remember
    what you called an entry.</li>
    <li><strong>Click to locate.</strong> Click in the PDF to jump to the
    source line that produced it, and the other way round.</li>
    <li><strong>Figures and tables without the syntax.</strong> The TikZ
    Designer and the Table Editor build the LaTeX for you; paste cells
    straight from a spreadsheet.</li>
  </ul>
  <p>If something does not work the way you expect, reply to this email.
  I read every reply and fix what I can in the next update, which your
  purchase includes.</p>
  <p>
    <a href="https://purplelink.llc/blog/tikz-and-tables-without-the-syntax/?utm_source=email&amp;utm_campaign=mtx-d3"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      See the TikZ and table tools
    </a>
  </p>
  {_lifecycle_footer(unsubscribe_url, "ModernTex")}
</div>
"""


def html_lifecycle_mtx_before_submit(*, unsubscribe_url: str, **_ignored) -> str:
    """Day 21 after a ModernTex purchase: the pre-submission checks, once."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Before you submit</h2>
  <p>If the paper you are writing in ModernTex is heading to a journal or
  conference soon, three checks are worth running first:</p>
  <ol style="padding-left: 20px;">
    <li><strong>ModernTex's submission readiness check.</strong> It looks at
    anonymization, page limits, required sections and packaging before you
    upload.</li>
    <li><strong>Your references.</strong> The free
    <a href="https://purplelink.llc/tools/bib-validator/?utm_source=email&amp;utm_campaign=mtx-d21" style="color: #6d28d9;">BibTeX Validator</a>
    checks that every entry resolves, and the
    <a href="https://purplelink.llc/tools/submission-checklist/?utm_source=email&amp;utm_campaign=mtx-d21" style="color: #6d28d9;">submission checklist</a>
    covers the rest.</li>
    <li><strong>A reviewer's read.</strong> Paper Review ($9) puts the PDF in
    front of four AI reviewers (methods, statistics, data integrity and an
    editor), checks every reference against CrossRef, and quotes the
    passages it questions. Results in minutes, no account, and the file is
    deleted when you retrieve the review.</li>
  </ol>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/?utm_source=email&amp;utm_campaign=mtx-d21"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      See Paper Review
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">This is the last of these
  emails. Product updates arrive inside the app.</p>
  {_lifecycle_footer(unsubscribe_url, "ModernTex")}
</div>
"""


def html_lifecycle_decision_reminder(*, manuscript_title: str = "", unsubscribe_url: str) -> str:
    """Sent around the decision date a Paper Review buyer chose on upload."""
    title = _html.escape((manuscript_title or "your manuscript")[:200])
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">When the reviews come back</h2>
  <p>When you uploaded {title} for a Paper Review, you asked for one
  email around the time you expected a decision. This is that email.</p>
  <p>If the decision is a revise and resubmit, two checks help:</p>
  <ul style="padding-left: 20px;">
    <li><strong>Response to Reviewers ($6)</strong> reads your response letter
    against every reviewer comment and flags replies that are missing,
    vague, or likely to read as defensive.</li>
    <li><strong>Revision Review ($2)</strong> checks the revised manuscript
    against the findings in your original Paper Review. It needs the
    Markdown file you saved from that review.</li>
  </ul>
  <p>The free guide to
  <a href="https://purplelink.llc/guides/how-to-respond-to-reviewer-2/?utm_source=email&amp;utm_campaign=decision" style="color: #6d28d9;">responding to Reviewer 2</a>
  covers sorting the comments before you write a word, and
  <a href="https://purplelink.llc/tools/latex-diff/?utm_source=email&amp;utm_campaign=decision" style="color: #6d28d9;">LaTeX Diff</a>
  makes the marked-up PDF many journals ask for.</p>
  <p>
    <a href="https://purplelink.llc/tools/response-review/?utm_source=email&amp;utm_campaign=decision"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Check my response letter
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">If it was accepted, congratulations.
  The <a href="https://purplelink.llc/guides/camera-ready-checklist/?utm_source=email&amp;utm_campaign=decision" style="color: #555;">camera-ready checklist</a>
  covers the last step.</p>
  {_lifecycle_footer(unsubscribe_url)}
</div>
"""


_DEADLINE_REASON = "because you asked for one reminder before a submission deadline on purplelink.llc. This is the only one."


def html_lifecycle_deadline_week(*, venue: str = "", deadline: str = "", unsubscribe_url: str, **_ignored) -> str:
    """Sent a week before a deadline someone entered on the submission checklist."""
    where = _html.escape((venue or "").strip()[:80])
    when = _html.escape((deadline or "").strip()[:40])
    if where and when:
        lead = "Your submission to %s is due on %s." % (where, when)
    elif when:
        lead = "Your submission is due on %s." % when
    else:
        lead = "Your submission deadline is about a week away."
    utm = "utm_source=email&amp;utm_campaign=deadline"
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">A week to go</h2>
  <p>{lead} You asked for one email a week ahead, while there is still time
  to fix what a reviewer would catch.</p>
  <ol style="padding-left: 20px;">
    <li><strong>Go through the checklist.</strong> The
    <a href="https://purplelink.llc/tools/submission-checklist/?{utm}" {_LINK}>submission checklist</a>
    covers anonymization, word limits, figures and the files most venues ask for.</li>
    <li><strong>Check the references.</strong> The free
    <a href="https://purplelink.llc/tools/bib-validator/?{utm}" {_LINK}>BibTeX Validator</a>
    finds malformed entries, missing fields and DOIs that do not resolve.</li>
    <li><strong>Get a read before a reviewer does.</strong> Paper Review ($9)
    has four AI reviewers read the manuscript for methods, statistics and
    claims the data do not support, and checks every reference against
    CrossRef. It takes a few minutes, which leaves the week for fixing.</li>
  </ol>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/?{utm}"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Review my paper
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">Double-blind venue? The
  <a href="https://purplelink.llc/tools/anonymity-check/?{utm}" style="color: #555;">Anonymity Check</a>
  ($2) finds names, institutions and self-citations that give you away.</p>
  {_lifecycle_footer(unsubscribe_url, reason=_DEADLINE_REASON)}
</div>
"""


_TRIAL_REASON = "because you asked for ModernTex trial emails on purplelink.llc. Three trial emails in all."


def html_lifecycle_trial_setup(*, unsubscribe_url: str, **_ignored) -> str:
    """Sent right after someone asks for trial emails next to the download."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Setting up the ModernTex trial</h2>
  <p>Here is what to expect in the first ten minutes.</p>
  <ol style="padding-left: 20px;">
    <li><strong>Install.</strong> Open the disk image and drag ModernTex to
    Applications. It is signed and notarized, so it opens like any other
    Mac app.</li>
    <li><strong>TeX.</strong> ModernTex compiles with a TeX distribution such
    as MacTeX or TinyTeX. If it cannot find either, it offers a one-click
    TinyTeX install.</li>
    <li><strong>Your paper.</strong> Open the folder of an existing project,
    or start from a
    <a href="https://purplelink.llc/templates/?utm_source=email&amp;utm_campaign=mtx-trial-1" style="color: #6d28d9;">venue template</a>
    (IEEE, ACM, NeurIPS, Elsevier, APA 7).</li>
  </ol>
  <p>The trial is the complete app for seven days from the first time you
  open it. If you keep it, it is $10 once, and the license key from your
  receipt unlocks the copy you already have.</p>
  <p>Stuck on anything? Reply to this email.</p>
  <p>
    <a href="https://purplelink.llc/.netlify/functions/moderntex-download?trial=1"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Download the trial
    </a>
  </p>
  <p style="color: #6b7280; font-size: 13px;">Signed up from a phone? Open
  this email on your Mac and use the button above. ModernTex needs macOS 14
  or later.</p>
  {_lifecycle_footer(unsubscribe_url, reason=_TRIAL_REASON)}
</div>
"""


def html_lifecycle_trial_features(*, unsubscribe_url: str, **_ignored) -> str:
    """Day 4 of a trial sign-up: the features that are easy to miss."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Four things to try in ModernTex</h2>
  <ul style="padding-left: 20px;">
    <li><strong>Live compile.</strong> Switch to Live mode and the PDF keeps
    up as you type. Fast is for drafting; Full is the complete pass before
    you submit.</li>
    <li><strong>Cite by name.</strong> Start a citation and search your .bib
    by author or title instead of remembering keys.</li>
    <li><strong>Click to locate.</strong> Click anywhere in the PDF to jump
    to the source that produced it.</li>
    <li><strong>A table from a spreadsheet.</strong> Paste cells from Excel
    or Google Sheets into the Table Editor and get booktabs LaTeX back.</li>
  </ul>
  <p>
    <a href="https://purplelink.llc/moderntex/?utm_source=email&amp;utm_campaign=mtx-trial-4#buy"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Keep ModernTex for $10
    </a>
  </p>
  {_lifecycle_footer(unsubscribe_url, reason=_TRIAL_REASON)}
</div>
"""


def html_lifecycle_trial_ending(*, unsubscribe_url: str, **_ignored) -> str:
    """Day 6 of a trial sign-up: the trial is about to end."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">Your ModernTex trial ends soon</h2>
  <p>If you started the trial when you downloaded it, it ends in about a
  day. When it does, the window shows a notice and a Buy button. Your .tex
  files are ordinary files on disk and are not touched either way.</p>
  <p>Keeping it is $10 once, with every 1.x update included. The receipt
  email carries a license key: paste it into the trial's "Have a license
  key?" and the same copy unlocks, with no reinstall. To get updates in
  place, install the download from your receipt page once.</p>
  <p>
    <a href="https://purplelink.llc/moderntex/?utm_source=email&amp;utm_campaign=mtx-trial-6#buy"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Buy ModernTex, $10
    </a>
  </p>
  <p style="color: #555; font-size: 0.9em;">If it was not for you, a reply
  saying what was missing helps more than you would think. This is the last
  trial email.</p>
  {_lifecycle_footer(unsubscribe_url, reason=_TRIAL_REASON)}
</div>
"""


def html_referral_credit(*, promo_code: str, reason: str) -> str:
    """Sent when a referral credit is earned — either the referrer (a
    colleague they referred bought a review with a .edu email) or the
    referee (they bought using a referral link with a .edu email). `reason`
    is the one line explaining which of those this is, written by the
    caller so this template doesn't need to encode that branching itself."""
    return f"""
<div style="{_EMAIL_BASE_CSS}">
  <h2 style="color: #6d28d9;">You've got a referral credit</h2>
  <p>{reason}</p>
  <p style="font-size: 1.3em; font-weight: 700; letter-spacing: 0.04em;
     background: #f7f5fb; padding: 10px 16px; border-radius: 8px;
     display: inline-block;">
    {promo_code}
  </p>
  <p>$2 off your next Paper Review purchase. Enter this code at checkout.
  One-time use.</p>
  <p>
    <a href="https://purplelink.llc/tools/paper-review/"
       style="display: inline-block; background: #7c3aed; color: #fff;
              padding: 10px 18px; border-radius: 6px; text-decoration: none;
              font-weight: 600;">
      Use it now
    </a>
  </p>
  <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 24px 0;">
  <p style="color: #888; font-size: 0.85em;">Sent by Purplelink LLC.</p>
</div>
"""
