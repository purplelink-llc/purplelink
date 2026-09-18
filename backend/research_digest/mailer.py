"""Email Ben a review copy after the weekly roundup auto-publishes, and
(separately) broadcast the roundup to the MuscleOnGLP subscriber list.

The review email uses Resend (same verified sender as the MuscleOnGLP
webhook: purplelink.llc) — this is the 'auto-publish, then flag to review'
path: the post is already live; this message lets Ben spot-check and pull
or fix anything that reads wrong.

The subscriber broadcast goes through Buttondown instead — see
docs/superpowers/specs/2026-09-18-muscleonglp-subscriber-lifecycle-design.md
for why: sending via the API is free on the current plan (only Buttondown's
own automatic triggers, like RSS-to-email, are a paid add-on), and
Buttondown already owns unsubscribe/suppression handling for this list, so
there is no reason to reinvent that on top of Resend. `notify_subscribers`
schedules the send ~24h out (`status: "scheduled"` + a future
`publish_date`) rather than sending immediately, so the review window this
function's sibling exists for has actually elapsed before the public list
sees it.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone

from .models import WeeklyDigest
from .renderer import post_url
from .reddit import build_body, build_title

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "MuscleOnGLP <guides@purplelink.llc>"
REVIEW_TO = "ben@purplelink.llc"

BUTTONDOWN_API_URL = "https://api.buttondown.email/v1/emails"
SUBSCRIBER_SEND_DELAY = timedelta(hours=24)


async def notify_review(client, digest: WeeklyDigest, resend_key: str) -> bool:
    if not resend_key:
        logger.info("mailer: no RESEND_API_KEY; skipping review email")
        return False
    url = post_url(digest.slug)
    e = html.escape
    rows = "".join(
        f'<li style="margin-bottom:10px"><a href="{e(it.paper.url)}">{e(it.paper.title)}</a>'
        f'<br><span style="color:#8a9993;font-size:13px">{e(it.paper.venue)} &middot; '
        f'relevance {it.relevance}/3{" &middot; preprint" if it.paper.is_preprint else ""}</span></li>'
        for it in digest.items
    )
    # Reddit closed self-serve Data API app creation in 2026 (Responsible Builder
    # Policy), so the cross-post cannot be automated without a manual approval we
    # do not have. Ship the paste-ready post in this email instead: it is a
    # 20-second copy-paste, and a human posting reads better in a small community
    # than a bot feed anyway. If API access is ever granted, reddit.post_roundup
    # takes over and this section becomes a fallback.
    r_title = build_title(digest)
    r_body = build_body(digest)
    reddit_block = f"""
  <hr style="border:none;border-top:1px solid #dde7e3;margin:28px 0">
  <p style="font-weight:600;margin-bottom:6px">Paste-ready post for r/GLP_Research</p>
  <p style="font-size:13px;color:#8a9993;margin-top:0">Title, then body. Post as a text post.</p>
  <p style="font-size:13px;font-weight:600;margin-bottom:4px">Title</p>
  <pre style="white-space:pre-wrap;word-break:break-word;background:#f4f8f6;border:1px solid #dde7e3;border-radius:10px;padding:12px 14px;font-size:13px;margin:0 0 14px">{e(r_title)}</pre>
  <p style="font-size:13px;font-weight:600;margin-bottom:4px">Body</p>
  <pre style="white-space:pre-wrap;word-break:break-word;background:#f4f8f6;border:1px solid #dde7e3;border-radius:10px;padding:12px 14px;font-size:13px;margin:0">{e(r_body)}</pre>
"""
    body = f"""<div style="font-family:-apple-system,sans-serif;max-width:560px;margin:0 auto;color:#1b2420">
  <h2 style="color:#2f6f5e">Weekly research roundup is live</h2>
  <p>The {e(digest.week_label)} roundup auto-published with {digest.count} papers. It is already public, so please skim it and pull or edit anything that reads wrong.</p>
  <p style="margin:22px 0"><a href="{url}" style="background:#2f6f5e;color:#fff;padding:12px 24px;border-radius:100px;text-decoration:none;font-weight:600">Review the live post</a></p>
  <p style="font-weight:600;margin-bottom:6px">Papers included:</p>
  <ol style="padding-left:18px">{rows}</ol>
  {reddit_block}
  <p style="font-size:13px;color:#8a9993;margin-top:24px">To pull a post, delete <code>research/{e(digest.slug)}/</code> from the repo (Netlify redeploys). Each summary is drawn from the abstract only.</p>
</div>"""

    text = (f"Weekly research roundup live: {digest.week_label} ({digest.count} papers).\n"
            f"Review: {url}\n\n" +
            "\n".join(f"- {it.paper.title} ({it.paper.venue}) {it.paper.url}" for it in digest.items)
            + f"\n\n--- paste-ready post for r/GLP_Research ---\n\n{r_title}\n\n{r_body}\n")
    try:
        resp = await client.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": FROM_ADDRESS, "to": [REVIEW_TO], "reply_to": REVIEW_TO,
                  "subject": f"[MuscleOnGLP] Roundup live: {digest.week_label} — please review",
                  "html": body, "text": text},
            timeout=30.0,
        )
        if not resp.is_success:  # httpx Response has is_success, not .ok
            logger.warning("mailer: resend http %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:
        logger.warning("mailer: send failed: %s", exc)
        return False


def subscriber_email_html(digest: WeeklyDigest) -> str:
    """Email-native HTML for the subscriber broadcast — plain inline styles,
    no external stylesheet (email clients don't load one), and none of the
    page chrome (nav, footer, JSON-LD) that render_post_html builds for a
    browser. Kept in mailer.py rather than renderer.py since it renders for
    an inbox, not the site."""
    e = html.escape
    url = post_url(digest.slug)
    items = "".join(
        f'<li style="margin-bottom:18px">'
        f'<a href="{e(it.paper.url)}" style="color:#2f6f5e;font-weight:600">{e(it.paper.title)}</a>'
        f'<br><span style="color:#8a9993;font-size:13px">{e(it.paper.venue)}'
        f'{" &middot; preprint" if it.paper.is_preprint else ""}</span>'
        f'<p style="margin:8px 0 0;font-size:14px">{e(it.summary)}</p>'
        f'<p style="margin:6px 0 0;font-size:14px;color:#45524c">{e(it.why_it_matters)}</p>'
        f'</li>'
        for it in digest.items
    )
    return f"""<div style="font-family:-apple-system,sans-serif;max-width:560px;margin:0 auto;color:#1b2420">
  <h2 style="color:#2f6f5e">GLP-1 &amp; Muscle Research Roundup — {e(digest.week_label)}</h2>
  <p>{e(digest.intro)}</p>
  <ol style="padding-left:18px">{items}</ol>
  <p style="margin:28px 0"><a href="{url}" style="background:#2f6f5e;color:#fff;padding:12px 24px;border-radius:100px;text-decoration:none;font-weight:600">Read this week's roundup &rarr;</a></p>
  <p style="font-size:13px;color:#8a9993;margin-top:24px">Every summary is drawn from the paper's abstract. This is research literacy, not medical advice — talk to your prescriber about anything here.</p>
</div>"""


async def notify_subscribers(client, digest: WeeklyDigest, buttondown_key: str) -> bool:
    """Broadcast the roundup to the whole Buttondown list, scheduled ~24h out
    so Ben's review window (notify_review, above) has actually elapsed
    before the public send goes out. Never raises: a Buttondown outage or a
    misconfigured key must not fail the run — the site is already published
    and Ben's review copy already went out by the time this is called."""
    if not buttondown_key:
        logger.info("mailer: no BUTTONDOWN_API_KEY; skipping subscriber broadcast")
        return False
    publish_date = (datetime.now(timezone.utc) + SUBSCRIBER_SEND_DELAY).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = await client.post(
            BUTTONDOWN_API_URL,
            headers={"Authorization": f"Token {buttondown_key}", "Content-Type": "application/json"},
            json={
                "subject": f"{digest.week_label} — GLP-1 & Muscle Research Roundup",
                "body": subscriber_email_html(digest),
                "status": "scheduled",
                "publish_date": publish_date,
                # No "filters" key: Buttondown's default is the empty filter
                # group, which matches every subscriber — exactly a broadcast.
            },
            timeout=30.0,
        )
        if resp.status_code != 201:
            logger.warning("mailer: buttondown http %s: %s", resp.status_code, resp.text[:200])
            return False
        logger.info("mailer: subscriber broadcast scheduled for %s", publish_date)
        return True
    except Exception as exc:
        logger.warning("mailer: buttondown send failed: %s", exc)
        return False
