# backend/digest/publisher.py
"""Publisher: render HTML, push to GitHub, send via Buttondown."""
from __future__ import annotations

import base64
import datetime
import html
import logging
from typing import Optional

from digest.curator import DigestData, DigestItem

logger = logging.getLogger(__name__)

GITHUB_REPO = "purplelink-llc/purplelink"
GITHUB_API = "https://api.github.com"
DIGEST_DIR = "site/blog/digest"
DIGEST_INDEX_PATH = f"{DIGEST_DIR}/index.html"
BUTTONDOWN_API = "https://api.buttondown.email/v1"

_MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _fmt_date(d: datetime.date) -> str:
    return f"{_MONTHS[d.month]} {d.day}, {d.year}"


def _render_item_html(item: DigestItem) -> str:
    return f"""      <div class="digest-item">
        <div class="digest-item-meta">
          <a class="digest-item-title" href="{html.escape(item.url, quote=True)}" target="_blank" rel="noopener">{html.escape(item.title)}</a>
          <span class="digest-item-source">{html.escape(item.source_name)}</span>
        </div>
        <p class="digest-item-note">{html.escape(item.editorial_note)}</p>
      </div>"""


def _render_sections_html(digest: DigestData) -> str:
    parts = []
    for section_label, items in digest.sections.items():
        items_html = "\n".join(_render_item_html(it) for it in items)
        parts.append(f"""    <section class="digest-section">
      <h2>{section_label}</h2>
{items_html}
    </section>""")
    return "\n\n".join(parts)


def render_html(digest: DigestData) -> str:
    """Render the full blog post HTML for a digest issue."""
    date_str = _fmt_date(digest.date)
    iso_date = digest.date.isoformat()
    title = f"Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{title} | Purplelink LLC</title>
    <meta name="description" content="Daily curated reading at the intersection of cybersecurity, AI, and entrepreneurship.">
    <link rel="canonical" href="https://purplelink.llc/blog/digest/{iso_date}.html">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="Daily curated reading at the intersection of cybersecurity, AI, and entrepreneurship.">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://purplelink.llc/blog/digest/{iso_date}.html">
    <meta property="og:image" content="https://purplelink.llc/assets/og/purplelink-card.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": "{title}",
      "datePublished": "{iso_date}",
      "author": {{ "@id": "https://purplelink.llc/about/#person" }},
      "publisher": {{ "@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/" }},
      "url": "https://purplelink.llc/blog/digest/{iso_date}.html"
    }}
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/blog/" aria-current="page">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <a class="back-link" href="/blog/digest/">← All issues</a>

    <div class="post-hero">
      <p class="post-date">{date_str}</p>
      <h1 class="post-title">{title}</h1>
      <p class="post-byline">By <a href="/about/" rel="author">Benjamin Ampel</a> · <time datetime="{iso_date}">{date_str}</time></p>
      <p class="post-lede">{digest.sources_reviewed} sources reviewed. {digest.items_selected} selected.</p>
    </div>

    <article id="main-content" class="post-body digest-body">

      <p class="digest-intro">{html.escape(digest.intro)}</p>

{sections_html}

    </article>

    <div class="post-footer digest-footer">
      <p>Get this in your inbox. <a href="/blog/digest/">Subscribe to the Daily Digest</a>.</p>
      <a class="back-link" href="/blog/digest/">← All issues</a>
    </div>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="/blog/">Blog</a>
        <a href="/guides/">Guides</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  <!-- Cloudflare Web Analytics --><script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "cf4dd1d7290844b4ab9693930738cad4"}}'></script><!-- End Cloudflare Web Analytics -->
  </body>
</html>"""


def render_email_html(digest: DigestData) -> str:
    """Render email-safe HTML: no nav/footer."""
    date_str = _fmt_date(digest.date)
    title = f"Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
  <p>{html.escape(digest.intro)}</p>
{sections_html}
  <hr>
  <p><a href="https://purplelink.llc/blog/digest/{digest.date.isoformat()}.html">Read on the web</a> &middot; <a href="https://purplelink.llc/blog/digest/">All issues</a></p>
</body>
</html>"""


def render_index_entry(digest: DigestData) -> str:
    """Render a single <a> block for the digest index page."""
    date_str = _fmt_date(digest.date)
    iso = digest.date.isoformat()
    title = f"Daily Digest #{digest.number}"
    return (
        f'      <a class="blog-post-item" href="/blog/digest/{iso}.html">\n'
        f'        <span class="blog-post-date">{date_str}</span>\n'
        f'        <div>\n'
        f'          <div class="blog-post-title">{title}</div>\n'
        f'          <p class="blog-post-excerpt">{html.escape(digest.intro[:180])}...</p>\n'
        f'        </div>\n'
        f'      </a>'
    )


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "PurplelinkDigest/1.0",
    }


async def github_count_digests(client, token: str) -> int:
    """Count existing digest HTML files (excluding index.html)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{DIGEST_DIR}"
    try:
        resp = await client.get(url, headers=_gh_headers(token), timeout=15.0)
        resp.raise_for_status()
        files = [f for f in resp.json()
                 if f.get("type") == "file"
                 and f.get("name", "").endswith(".html")
                 and f.get("name") != "index.html"]
        return len(files)
    except Exception as exc:
        logger.warning("github_count_digests failed: %s", exc)
        return 0


async def _github_get_file(client, path: str, token: str) -> tuple[Optional[str], Optional[str]]:
    """Return (decoded content, sha) for a file, or (None, None) if not found."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    try:
        resp = await client.get(url, headers=_gh_headers(token), timeout=15.0)
        if resp.status_code == 404:
            return None, None
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    except Exception as exc:
        logger.warning("_github_get_file %s failed: %s", path, exc)
        return None, None


async def _github_put_file(
    client, path: str, content: str, message: str,
    token: str, sha: Optional[str] = None,
) -> None:
    import asyncio as _asyncio
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    body: dict = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode(),
    }
    if sha:
        body["sha"] = sha
    for attempt in range(1, 4):
        try:
            resp = await client.put(url, headers=_gh_headers(token), json=body, timeout=20.0)
            resp.raise_for_status()
            return
        except Exception as exc:
            if attempt < 3:
                await _asyncio.sleep(attempt * 3)
            else:
                raise RuntimeError(f"_github_put_file {path} failed: {exc}") from exc


async def github_write_digest(
    client, html: str, digest: DigestData, token: str,
) -> None:
    """Write the digest HTML file to the repo."""
    iso = digest.date.isoformat()
    path = f"{DIGEST_DIR}/{iso}.html"
    _, existing_sha = await _github_get_file(client, path, token)
    await _github_put_file(
        client, path, html,
        message=f"chore(digest): Daily Digest #{digest.number} ({iso})",
        token=token,
        sha=existing_sha,
    )
    logger.info("github_write_digest: wrote %s", path)


_INDEX_LIST_MARKER = "<!-- DIGEST_LIST_START -->"


async def github_update_digest_index(
    client, entry_html: str, token: str,
) -> None:
    """Prepend entry_html to the digest index page list."""
    current, sha = await _github_get_file(client, DIGEST_INDEX_PATH, token)
    if current is None:
        logger.warning("github_update_digest_index: index file not found, skipping")
        return
    if _INDEX_LIST_MARKER not in current:
        logger.warning("github_update_digest_index: marker not found in index, skipping")
        return
    updated = current.replace(
        _INDEX_LIST_MARKER,
        f"{_INDEX_LIST_MARKER}\n{entry_html}",
    )
    await _github_put_file(
        client, DIGEST_INDEX_PATH, updated,
        message="chore(digest): update digest index",
        token=token, sha=sha,
    )
    logger.info("github_update_digest_index: updated index")


async def buttondown_send(
    client, digest: DigestData, email_html: str, key: str,
) -> None:
    date_str = _fmt_date(digest.date)
    subject = f"Daily Digest #{digest.number} — {date_str}"
    body = {
        "subject": subject,
        "body": email_html,
        "status": "about_to_send",
    }
    headers = {
        "Authorization": f"Token {key}",
        "Content-Type": "application/json",
    }
    try:
        resp = await client.post(
            f"{BUTTONDOWN_API}/emails",
            headers=headers,
            json=body,
            timeout=20.0,
        )
        resp.raise_for_status()
        logger.info("buttondown_send: broadcast created id=%s", resp.json().get("id"))
    except Exception as exc:
        logger.error("buttondown_send failed (post is already live): %s", exc)


async def publish(
    digest: DigestData,
    github_token: str,
    buttondown_key: str,
) -> None:
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        count = await github_count_digests(client, github_token)
        digest.number = count + 1

        html_content = render_html(digest)
        email_html = render_email_html(digest)
        entry = render_index_entry(digest)

        await github_write_digest(client, html_content, digest, github_token)
        await github_update_digest_index(client, entry, github_token)
        await buttondown_send(client, digest, email_html, buttondown_key)

    logger.info(
        "publish complete: Digest #%d, %d items, %s",
        digest.number, digest.items_selected, digest.date,
    )
