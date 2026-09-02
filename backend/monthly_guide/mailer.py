"""Email Ben a review copy after the monthly guide auto-lists for sale.

Mirrors research_digest/mailer.py (Resend, same verified sender). This is the
'auto-publish, then flag to review' path, but the stakes are higher than the
weekly roundup: a NEW PAID product is now live and charging real money. The
subject line makes that explicit and the body tells Ben exactly how to pull it
(delete the pages, unset the env var / deactivate the Stripe price) if the
synthesis reads wrong.
"""
from __future__ import annotations

import html
import logging

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "MuscleOnGLP <guides@purplelink.llc>"
REVIEW_TO = "ben@purplelink.llc"
SITE_ORIGIN = "https://getmuscleonglp.com"


async def notify_new_guide(
    client, *, month_label: str, slug: str, title: str, price_id: str,
    env_key: str, roundup_count: int, resend_key: str,
) -> bool:
    """Send Ben the 'new paid guide is live' review email. Returns sent?."""
    if not resend_key:
        logger.info("mailer: no RESEND_API_KEY; skipping review email")
        return False
    e = html.escape
    landing = f"{SITE_ORIGIN}/guides/{slug}/"
    body = f"""<div style="font-family:-apple-system,sans-serif;max-width:560px;margin:0 auto;color:#1b2420">
  <h2 style="color:#2f6f5e">A new PAID guide is live and charging $1</h2>
  <p>The {e(month_label)} monthly research review auto-published and is now for sale. It was synthesized from {roundup_count} weekly roundup(s), red-teamed, and typeset. It is already public and taking payments, so please read it and pull it if anything is wrong.</p>
  <p style="margin:22px 0"><a href="{landing}" style="background:#2f6f5e;color:#fff;padding:12px 24px;border-radius:100px;text-decoration:none;font-weight:600">Review the live guide</a></p>
  <p style="font-weight:600;margin-bottom:6px">What was created:</p>
  <ul style="padding-left:18px;font-size:14px">
    <li>Product: {e(title)}</li>
    <li>Slug / product key: <code>{e(slug)}</code></li>
    <li>Stripe price id: <code>{e(price_id)}</code></li>
    <li>Netlify env var: <code>{e(env_key)}</code></li>
    <li>Landing: <a href="{landing}">{landing}</a></li>
  </ul>
  <p style="font-size:13px;color:#8a9993;margin-top:24px">To pull it: delete <code>guides/{e(slug)}/</code> and <code>success/{e(slug)}/</code> and its entry in <code>netlify/functions/lib/products.mjs</code> from the repo (Netlify redeploys), then deactivate the Stripe price and unset the env var. The synthesis is drawn only from that month's already-vetted roundups.</p>
</div>"""
    text = (
        f"New PAID monthly guide live: {title} ({month_label}).\n"
        f"Review: {landing}\n"
        f"Slug: {slug}\nStripe price: {price_id}\nEnv var: {env_key}\n"
        f"Built from {roundup_count} weekly roundup(s).\n"
        "Pull it by deleting guides/<slug>/, success/<slug>/, the products.mjs "
        "entry, deactivating the Stripe price, and unsetting the env var."
    )
    try:
        resp = await client.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": FROM_ADDRESS, "to": [REVIEW_TO], "reply_to": REVIEW_TO,
                  "subject": f"[MuscleOnGLP] NEW PAID guide live: {title} — please review",
                  "html": body, "text": text},
            timeout=30.0,
        )
        if not resp.is_success:
            logger.warning("mailer: resend http %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:
        logger.warning("mailer: send failed: %s", exc)
        return False
