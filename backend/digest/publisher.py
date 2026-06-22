# backend/digest/publisher.py
"""Publisher: render HTML, push to GitHub, send via Buttondown."""
from __future__ import annotations

import datetime
import logging

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
          <a class="digest-item-title" href="{item.url}" target="_blank" rel="noopener">{item.title}</a>
          <span class="digest-item-source">{item.source_name}</span>
        </div>
        <p class="digest-item-note">{item.editorial_note}</p>
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

      <p class="digest-intro">{digest.intro}</p>

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
  <p>{digest.intro}</p>
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
        f'          <p class="blog-post-excerpt">{digest.intro[:180]}...</p>\n'
        f'        </div>\n'
        f'      </a>'
    )
