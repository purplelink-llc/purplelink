#!/usr/bin/env python3
"""One-off backfill: add section anchors to existing digest posts and build
the 6 topic hub pages (site/blog/digest/topics/<slug>/index.html) from the
digest issues already published, so the archive has real cross-linked topic
pages immediately instead of only accumulating them from the next cron run
onward.

Going forward, backend/digest/publisher.py's publish() keeps these hubs
updated on every daily run — this script only needs to run once, plus
again if older un-anchored digest posts are ever added out of band.

Usage: python3 scripts/backfill_topic_hubs.py
"""
import glob
import html
import os
import re

SITE = os.path.join(os.path.dirname(__file__), "..", "site")
DIGEST_DIR = os.path.join(SITE, "blog", "digest")
TOPICS_DIR = os.path.join(DIGEST_DIR, "topics")

SECTION_LABELS = {
    "papers": "Papers & Research",
    "ai_tech": "AI & Technology",
    "cybersecurity": "Cybersecurity",
    "finance": "Finance & Business",
    "entrepreneurship": "Entrepreneurship",
    "general_tech": "Worth Reading",
}
LABEL_TO_SLUG = {label: slug for slug, label in SECTION_LABELS.items()}

_MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

SECTION_RE = re.compile(
    r'<section class="digest-section"[^>]*>\s*<h2>(.*?)</h2>(.*?)</section>', re.S
)
ITEM_TITLE_RE = re.compile(
    r'<a class="digest-item-title"[^>]*>(.*?)</a>', re.S
)


def fmt_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{_MONTHS[m]} {d}, {y}"


def add_section_anchors(path):
    with open(path, encoding="utf-8") as fh:
        html_content = fh.read()
    if 'id="section-' in html_content:
        return False, html_content

    def repl(m):
        label = m.group(1)
        slug = LABEL_TO_SLUG.get(label, "")
        anchor = f' id="section-{slug}"' if slug else ""
        return f'<section class="digest-section"{anchor}>\n      <h2>{label}</h2>{m.group(2)}</section>'

    new_content = SECTION_RE.sub(repl, html_content)
    if new_content != html_content:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_content)
    return new_content != html_content, new_content


def topic_hub_skeleton(section_label, slug):
    canonical = f"https://purplelink.llc/blog/digest/topics/{slug}/"
    title = f"{section_label} — Purplelink Daily Digest"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{html.escape(title)} | Purplelink LLC</title>
    <meta name="description" content="Every Purplelink Daily Digest issue that covered {html.escape(section_label)}, newest first.">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{html.escape(title)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="alternate" type="application/rss+xml" title="Purplelink Daily Digest by Benjamin Ampel" href="/blog/digest/feed.xml">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Daily Digest", "item": "https://purplelink.llc/blog/digest/" }},
        {{ "@type": "ListItem", "position": 3, "name": "{html.escape(section_label)}", "item": "{canonical}" }}
      ]
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
    <a class="back-link" href="/blog/digest/">← All digest issues</a>
    <div class="blog-hero" id="main-content">
      <h1>{html.escape(section_label)}</h1>
      <p>Every Purplelink Daily Digest issue that covered {html.escape(section_label)}, newest first.</p>
    </div>
    <div class="blog-list">
<!-- DIGEST_LIST_START -->
    </div>
    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia &middot; Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
  </body>
</html>"""


def render_topic_entry(iso, digest_number, section_label, item_titles):
    slug = LABEL_TO_SLUG.get(section_label, "")
    date_str = fmt_date(iso)
    title = f"Purplelink Daily Digest #{digest_number}"
    excerpt = "; ".join(item_titles[:3])
    return (
        f'      <a class="blog-post-item" href="/blog/digest/{iso}.html#section-{slug}">\n'
        f'        <span class="blog-post-date">{date_str}</span>\n'
        f'        <div>\n'
        f'          <div class="blog-post-title">{title} — {html.escape(section_label)}</div>\n'
        f'          <p class="blog-post-excerpt">{html.escape(excerpt)}</p>\n'
        f'        </div>\n'
        f'      </a>'
    )


def main():
    os.makedirs(TOPICS_DIR, exist_ok=True)

    # Collect (iso, digest_number, {label: [titles]}) per day, newest last
    # so we can prepend in newest-first order to the hub pages.
    days = []
    for path in sorted(glob.glob(os.path.join(DIGEST_DIR, "*.html"))):
        name = os.path.basename(path)
        if name == "index.html":
            continue
        iso = name.replace(".html", "")

        changed, content = add_section_anchors(path)
        if changed:
            print(f"anchored: {path}")

        m_num = re.search(r"Purplelink Daily Digest #(\d+)", content)
        digest_number = m_num.group(1) if m_num else "?"

        sections = {}
        for label, body in SECTION_RE.findall(content):
            titles = [html.unescape(t) for t in ITEM_TITLE_RE.findall(body)]
            if titles:
                sections[label] = titles
        days.append((iso, digest_number, sections))

    # newest first
    days.sort(key=lambda d: d[0], reverse=True)

    hub_entries = {slug: [] for slug in SECTION_LABELS}
    for iso, digest_number, sections in days:
        for label, titles in sections.items():
            slug = LABEL_TO_SLUG.get(label)
            if not slug:
                continue
            hub_entries[slug].append(render_topic_entry(iso, digest_number, label, titles))

    for slug, label in SECTION_LABELS.items():
        entries = hub_entries[slug]
        if not entries:
            print(f"SKIP {slug}: no entries found")
            continue
        hub_dir = os.path.join(TOPICS_DIR, slug)
        os.makedirs(hub_dir, exist_ok=True)
        content = topic_hub_skeleton(label, slug)
        content = content.replace(
            "<!-- DIGEST_LIST_START -->",
            "<!-- DIGEST_LIST_START -->\n" + "\n".join(entries),
        )
        with open(os.path.join(hub_dir, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"wrote {slug}/index.html with {len(entries)} entries")


if __name__ == "__main__":
    main()
