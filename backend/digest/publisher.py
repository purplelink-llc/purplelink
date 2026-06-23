# backend/digest/publisher.py
"""Publisher: render HTML + RSS, push to GitHub, ping WebSub, post to LinkedIn."""
from __future__ import annotations

import base64
import datetime
import email.utils
import html
import logging
from typing import Optional

from digest.curator import DigestData, DigestItem

logger = logging.getLogger(__name__)

GITHUB_REPO = "purplelink-llc/purplelink"
GITHUB_API = "https://api.github.com"
DIGEST_DIR = "site/blog/digest"
DIGEST_INDEX_PATH = f"{DIGEST_DIR}/index.html"
DIGEST_FEED_PATH = f"{DIGEST_DIR}/feed.xml"
SITE_URL = "https://purplelink.llc"

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


def _meta_desc(digest: DigestData, max_len: int = 155) -> str:
    """Plain-text intro truncated for meta description."""
    text = digest.intro.replace('"', '&quot;').replace('\n', ' ').strip()
    return text[:max_len]


def render_html(digest: DigestData) -> str:
    """Render the full blog post HTML for a digest issue."""
    date_str = _fmt_date(digest.date)
    iso_date = digest.date.isoformat()
    title = f"Purplelink Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)
    desc = _meta_desc(digest)
    topic_labels = list(digest.sections.keys())
    keywords = ", ".join(topic_labels + ["Purplelink Daily Digest", "Benjamin Ampel", "cybersecurity research", "AI papers"])

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{title} | Purplelink LLC</title>
    <meta name="description" content="{desc}">
    <meta name="keywords" content="{html.escape(keywords)}">
    <meta name="author" content="Benjamin Ampel">
    <link rel="canonical" href="{SITE_URL}/blog/digest/{iso_date}.html">
    <link rel="alternate" type="application/rss+xml" title="Purplelink Daily Digest by Benjamin Ampel" href="{SITE_URL}/blog/digest/feed.xml">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{desc}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{SITE_URL}/blog/digest/{iso_date}.html">
    <meta property="og:image" content="{SITE_URL}/assets/og/purplelink-card.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="article:published_time" content="{iso_date}">
    <meta property="article:author" content="Benjamin Ampel">
    <meta property="article:section" content="Research Digest">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{desc}">
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
      "description": "{desc}",
      "keywords": "{html.escape(keywords)}",
      "datePublished": "{iso_date}",
      "author": {{
        "@type": "Person",
        "@id": "{SITE_URL}/about/#person",
        "name": "Benjamin Ampel",
        "url": "{SITE_URL}/about/"
      }},
      "publisher": {{ "@type": "Organization", "name": "Purplelink LLC", "url": "{SITE_URL}/" }},
      "url": "{SITE_URL}/blog/digest/{iso_date}.html",
      "isPartOf": {{ "@type": "Blog", "url": "{SITE_URL}/blog/digest/" }}
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
      <p>Get this in your inbox. <a href="/blog/digest/">Subscribe to Purplelink Daily Digest</a>.</p>
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


def render_email_html(digest: DigestData, unsubscribe_url: str = "") -> str:
    """Render email-safe HTML: no nav/footer, inline-friendly."""
    date_str = _fmt_date(digest.date)
    title = f"Purplelink Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)
    unsub_line = (
        f'<p style="font-size:12px;color:#888;margin-top:24px;">'
        f'You\'re receiving this because you subscribed at purplelink.llc. '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}" style="color:#888;">Unsubscribe</a>'
        f'</p>'
    ) if unsubscribe_url else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:24px 16px;color:#1a1a1a;">
  <h1 style="font-size:22px;margin-bottom:8px;">{title}</h1>
  <p style="color:#555;margin-bottom:24px;">{html.escape(digest.intro)}</p>
{sections_html}
  <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
  <p style="font-size:13px;color:#555;">
    <a href="https://purplelink.llc/blog/digest/{digest.date.isoformat()}.html">Read on the web</a>
    &middot;
    <a href="https://purplelink.llc/blog/digest/">All issues</a>
  </p>
  {unsub_line}
</body>
</html>"""


def render_index_entry(digest: DigestData) -> str:
    """Render a single <a> block for the digest index page."""
    date_str = _fmt_date(digest.date)
    iso = digest.date.isoformat()
    title = f"Purplelink Daily Digest #{digest.number}"
    return (
        f'      <a class="blog-post-item" href="/blog/digest/{iso}.html">\n'
        f'        <span class="blog-post-date">{date_str}</span>\n'
        f'        <div>\n'
        f'          <div class="blog-post-title">{title}</div>\n'
        f'          <p class="blog-post-excerpt">{html.escape(digest.intro[:180])}...</p>\n'
        f'        </div>\n'
        f'      </a>'
    )


_RSS_MARKER = "<!-- DIGEST_RSS_START -->"

_RSS_SKELETON = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Purplelink Daily Digest by Benjamin Ampel</title>
    <link>https://purplelink.llc/blog/digest/</link>
    <description>Daily curated reading at the intersection of cybersecurity, AI, research, and entrepreneurship. Curated by Benjamin Ampel.</description>
    <language>en</language>
    <managingEditor>ben@purplelink.llc (Benjamin Ampel)</managingEditor>
    <atom:link href="https://purplelink.llc/blog/digest/feed.xml" rel="self" type="application/rss+xml"/>
    <!-- DIGEST_RSS_START -->
  </channel>
</rss>"""


def render_rss_item(digest: DigestData) -> str:
    """Render a single RSS <item> block for the digest."""
    date_str = _fmt_date(digest.date)
    iso = digest.date.isoformat()
    title = html.escape(f"Purplelink Daily Digest #{digest.number} — {date_str}")
    link = f"{SITE_URL}/blog/digest/{iso}.html"
    desc = html.escape(digest.intro)
    pub_dt = datetime.datetime.combine(digest.date, datetime.time(10, 0),
                                       tzinfo=datetime.timezone.utc)
    pub_date = email.utils.format_datetime(pub_dt)
    return (
        f"    <item>\n"
        f"      <title>{title}</title>\n"
        f"      <link>{link}</link>\n"
        f"      <guid isPermaLink=\"true\">{link}</guid>\n"
        f"      <pubDate>{pub_date}</pubDate>\n"
        f"      <dc:creator>Benjamin Ampel</dc:creator>\n"
        f"      <description>{desc}</description>\n"
        f"    </item>"
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


async def github_update_rss_feed(
    client, rss_item: str, token: str,
) -> None:
    """Prepend rss_item to feed.xml, creating the file if it doesn't exist."""
    current, sha = await _github_get_file(client, DIGEST_FEED_PATH, token)
    if current is None or _RSS_MARKER not in current:
        current = _RSS_SKELETON
        sha = None
    updated = current.replace(_RSS_MARKER, f"{_RSS_MARKER}\n{rss_item}")
    await _github_put_file(
        client, DIGEST_FEED_PATH, updated,
        message="chore(digest): update RSS feed",
        token=token, sha=sha,
    )
    logger.info("github_update_rss_feed: updated feed.xml")


_WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"
_FEED_URL = f"{SITE_URL}/blog/digest/feed.xml"

_LINKEDIN_API = "https://api.linkedin.com/v2"
_LINKEDIN_HASHTAGS = "#cybersecurity #AI #infosec #research #entrepreneurship"


async def ping_websub(client) -> None:
    """Notify the WebSub hub that the RSS feed has been updated."""
    try:
        resp = await client.post(
            _WEBSUB_HUB,
            content=f"hub.mode=publish&hub.url={_FEED_URL}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
        if resp.status_code in (200, 204):
            logger.info("ping_websub: hub notified")
        else:
            logger.warning("ping_websub: unexpected status %d", resp.status_code)
    except Exception as exc:
        logger.warning("ping_websub failed: %s", exc)


async def post_linkedin(
    client,
    digest: DigestData,
    access_token: str,
    author_urn: str,
) -> None:
    """Post a digest announcement to LinkedIn (person or organization)."""
    iso = digest.date.isoformat()
    page_url = f"{SITE_URL}/blog/digest/{iso}.html"
    title = f"Purplelink Daily Digest #{digest.number} — {_fmt_date(digest.date)}"

    # Keep post text concise: intro + link + hashtags
    intro = digest.intro[:500].rstrip()
    post_text = f"{title}\n\n{intro}\n\n{page_url}\n\n{_LINKEDIN_HASHTAGS}"

    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post_text},
                "shareMediaCategory": "ARTICLE",
                "media": [{
                    "status": "READY",
                    "description": {"text": digest.intro[:200]},
                    "originalUrl": page_url,
                    "title": {"text": title},
                }],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    try:
        resp = await client.post(
            f"{_LINKEDIN_API}/ugcPosts",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        post_id = resp.json().get("id", "unknown")
        logger.info("post_linkedin: posted %s", post_id)
    except Exception as exc:
        logger.warning("post_linkedin failed: %s", exc)


async def publish(
    digest: DigestData,
    github_token: str,
    linkedin_token: str = "",
    linkedin_author_urn: str = "",
) -> None:
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        count = await github_count_digests(client, github_token)
        digest.number = count + 1

        html_content = render_html(digest)
        entry = render_index_entry(digest)
        rss_item = render_rss_item(digest)

        await github_write_digest(client, html_content, digest, github_token)
        await github_update_digest_index(client, entry, github_token)
        await github_update_rss_feed(client, rss_item, github_token)
        await ping_websub(client)

        if linkedin_token and linkedin_author_urn:
            await post_linkedin(client, digest, linkedin_token, linkedin_author_urn)
        else:
            logger.info("post_linkedin: skipped (no credentials)")

    logger.info(
        "publish complete: Digest #%d, %d items, %s",
        digest.number, digest.items_selected, digest.date,
    )
