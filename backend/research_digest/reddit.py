"""Post the weekly roundup to r/GLP_Research.

Runs at the very end of the weekly pipeline, after the site has already been
committed and deployed, and is deliberately best-effort: a Reddit failure logs
and returns False rather than raising, so it can never cost us the published
post. Same posture as mailer.notify_review.

Credentials come from a Modal secret and are never handled in code review or
logs. Required env vars (all four, or the module no-ops):

  REDDIT_CLIENT_ID       from reddit.com/prefs/apps -> create a "script" app
  REDDIT_CLIENT_SECRET   the secret for that app
  REDDIT_USERNAME        the account that moderates the subreddit
  REDDIT_PASSWORD        that account's password

Optional:
  REDDIT_SUBREDDIT       defaults to GLP_Research

A note on the password grant: Reddit's "script" app type authenticates with the
account password, which is why this is scoped to a secret the pipeline reads at
runtime. If the account has 2FA enabled the password grant needs a TOTP suffix
and will otherwise fail with 401; in that case either disable 2FA for this
account, or switch to a refresh-token flow (obtained once interactively) and
swap _get_token below.

We submit a self post rather than a link post on purpose. A community whose
feed is nothing but outbound links reads as a billboard; putting the actual
summaries in the thread means the post is useful without leaving Reddit, and
the link is there for anyone who wants the full write-up.
"""
from __future__ import annotations

import logging
import os

from .models import WeeklyDigest
from .renderer import post_url

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"
# Reddit's API rules require a descriptive, unique User-Agent identifying the
# app and its operator. A generic or spoofed one is a fast route to a ban.
USER_AGENT = "python:com.purplelink.muscleonglp.roundup:v1.0 (by /u/PurplelinkPL)"

MAX_BODY = 39000  # Reddit self-post limit is 40k; leave headroom.


def _creds() -> dict | None:
    got = {
        "client_id": os.environ.get("REDDIT_CLIENT_ID", ""),
        "client_secret": os.environ.get("REDDIT_CLIENT_SECRET", ""),
        "username": os.environ.get("REDDIT_USERNAME", ""),
        "password": os.environ.get("REDDIT_PASSWORD", ""),
    }
    missing = [k for k, v in got.items() if not v]
    if missing:
        logger.info("reddit: missing %s; skipping post", ", ".join(sorted(missing)))
        return None
    return got


async def _get_token(client, c: dict) -> str | None:
    resp = await client.post(
        TOKEN_URL,
        auth=(c["client_id"], c["client_secret"]),
        data={"grant_type": "password", "username": c["username"], "password": c["password"]},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if not resp.is_success:
        # Never log the response body: it can echo submitted credentials.
        logger.warning("reddit: token request failed (%s)", resp.status_code)
        return None
    token = resp.json().get("access_token")
    if not token:
        logger.warning("reddit: token response had no access_token")
    return token


async def _already_posted(client, token: str, sub: str, slug: str) -> bool:
    """Guard against double-posting if the weekly job is re-run by hand."""
    try:
        resp = await client.get(
            f"{API}/r/{sub}/search",
            params={"q": slug, "restrict_sr": 1, "sort": "new", "limit": 25, "t": "year"},
            headers={"Authorization": f"bearer {token}", "User-Agent": USER_AGENT},
            timeout=30,
        )
        if not resp.is_success:
            return False  # can't tell; let the submit attempt proceed
        children = resp.json().get("data", {}).get("children", [])
        for ch in children:
            d = ch.get("data", {})
            if slug in (d.get("selftext") or "") or slug in (d.get("url") or ""):
                return True
    except Exception as err:  # noqa: BLE001 - the guard must never break the run
        logger.info("reddit: dedupe check skipped (%s)", err)
    return False


def build_title(digest: WeeklyDigest) -> str:
    t = f"Research roundup: GLP-1 and muscle, {digest.week_label} ({digest.count} papers)"
    return t[:300]


def build_body(digest: WeeklyDigest) -> str:
    """Self-post body: the summaries themselves, then the link, then the caveat."""
    url = post_url(digest.slug)
    lines = [
        f"New peer-reviewed work on GLP-1 medications and muscle, published the week of "
        f"{digest.week_label}. {digest.count} "
        f"{'paper' if digest.count == 1 else 'papers'} this week, every source linked.",
        "",
    ]
    for it in digest.items:
        p = it.paper
        tag = " *(preprint)*" if getattr(p, "is_preprint", False) else ""
        lines.append(f"**[{p.title}]({p.url})**{tag}")
        meta = " · ".join(x for x in [getattr(p, "venue", ""), getattr(p, "pub_date", "")] if x)
        if meta:
            lines.append(f"*{meta}*")
        lines.append("")
        lines.append(it.summary)
        if getattr(it, "why_it_matters", ""):
            lines.append("")
            lines.append(f"**Why it matters:** {it.why_it_matters}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"Full write-up with the rest of the detail: {url}")
    lines.append("")
    lines.append(
        "These summaries are compiled automatically from published abstracts. They are a "
        "neutral summary, not medical advice, not peer review, and not an endorsement. "
        "Study quality varies and preprints are not yet peer-reviewed. Read the linked "
        "source and talk to your clinician before changing anything."
    )
    lines.append("")
    # Deliberately worded to be true whether this is pasted by hand or posted by
    # the API path, since the same body serves both.
    lines.append(
        "*Disclosure: I run getmuscleonglp.com, which publishes these roundups free and "
        "also sells a paid guide, so treat me as an interested party and check the "
        "sources yourself.*"
    )
    body = "\n".join(lines)
    return body[:MAX_BODY]


async def post_roundup(client, digest: WeeklyDigest) -> bool:
    """Submit the week's roundup. Returns True only if Reddit accepted the post."""
    c = _creds()
    if c is None:
        return False
    sub = os.environ.get("REDDIT_SUBREDDIT", "GLP_Research").lstrip("/").removeprefix("r/")

    try:
        token = await _get_token(client, c)
        if not token:
            return False

        if await _already_posted(client, token, sub, digest.slug):
            logger.info("reddit: %s already posted to r/%s; skipping", digest.slug, sub)
            return False

        resp = await client.post(
            f"{API}/api/submit",
            data={
                "sr": sub,
                "kind": "self",
                "title": build_title(digest),
                "text": build_body(digest),
                "api_type": "json",
                "sendreplies": "true",
                "resubmit": "false",
            },
            headers={"Authorization": f"bearer {token}", "User-Agent": USER_AGENT},
            timeout=45,
        )
        if not resp.is_success:
            logger.warning("reddit: submit failed (%s)", resp.status_code)
            return False

        payload = resp.json().get("json", {})
        errors = payload.get("errors") or []
        if errors:
            # Reddit returns HTTP 200 with an errors array for rate limits,
            # subreddit permission problems, and duplicate submissions.
            logger.warning("reddit: submit rejected: %s", errors)
            return False

        posted_url = (payload.get("data") or {}).get("url", "")
        logger.info("reddit: posted %s to r/%s %s", digest.slug, sub, posted_url)
        return True
    except Exception as err:  # noqa: BLE001 - never let Reddit break the weekly run
        logger.warning("reddit: post skipped after error (%s)", err)
        return False
