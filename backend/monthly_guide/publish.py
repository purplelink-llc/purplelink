"""Filesystem edits that list a new monthly guide on a cloned site checkout.

Mirrors research_digest/publisher.py: the Modal job clones the private site
repo, this module edits files on disk (append the product to the registry,
write the landing + success pages, add a hub card, add sitemap URLs), then the
job commits and deploys the whole directory via the Netlify CLI.

Every edit here is idempotent: re-running the monthly job for the same month
must not create duplicate registry entries, cards, or sitemap URLs. Pages are
simply overwritten with identical content.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

PRODUCTS_REL = "netlify/functions/lib/products.mjs"
GUIDES_HUB_REL = "guides/index.html"
SITEMAP_REL = "sitemap.xml"
SITE_ORIGIN = "https://getmuscleonglp.com"


# --------------------------------------------------------------------------- #
# Naming: one stable slug per month drives the product key, env var, page      #
# paths, and PDF filename. Kept here so app.py and publish.py cannot drift.    #
# --------------------------------------------------------------------------- #

def month_slug(year: int, month: int) -> str:
    return f"research-review-{year:04d}-{month:02d}"


def month_label(year: int, month: int) -> str:
    return f"{_MONTH_NAMES[month - 1]} {year}"


def guide_title(year: int, month: int) -> str:
    return f"GLP-1 & Muscle: Research Review, {month_label(year, month)}"


def env_key(slug: str) -> str:
    """e.g. research-review-2026-07 -> STRIPE_PRICE_RESEARCH_REVIEW_2026_07."""
    return "STRIPE_PRICE_" + slug.upper().replace("-", "_")


def pdf_filename(slug: str) -> str:
    return f"{slug}.pdf"


def success_path(slug: str) -> str:
    return f"/success/{slug}/"


def landing_path(slug: str) -> str:
    return f"/guides/{slug}/"


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# --------------------------------------------------------------------------- #
# 1. Product registry (lib/products.mjs)                                       #
# --------------------------------------------------------------------------- #

def append_product(site_dir: str, slug: str, title: str) -> bool:
    """Append the new product to the PRODUCTS map in lib/products.mjs.

    Returns True if the file was modified, False if the slug was already
    present (idempotent). The entry is inserted just before the closing ``};``
    of the PRODUCTS object literal.
    """
    path = os.path.join(site_dir, PRODUCTS_REL)
    with open(path) as f:
        src = f.read()
    if f'"{slug}"' in src:
        logger.info("publish: product %s already in registry", slug)
        return False

    entry = (
        f'  "{slug}": {{\n'
        f'    envKey: "{env_key(slug)}",\n'
        f'    successPath: "{success_path(slug)}",\n'
        f'    title: {_js_string(title)},\n'
        f'    file: "{pdf_filename(slug)}",\n'
        f'  }},\n'
    )
    marker = "\nexport const PRODUCTS = {"
    idx = src.find(marker)
    if idx == -1:
        raise RuntimeError("append_product: could not find PRODUCTS object in products.mjs")
    # Close of the object is the first "};" after the marker.
    close = src.find("};", idx)
    if close == -1:
        raise RuntimeError("append_product: could not find end of PRODUCTS object")
    new_src = src[:close] + entry + src[close:]
    with open(path, "w") as f:
        f.write(new_src)
    logger.info("publish: appended product %s to registry", slug)
    return True


def _js_string(value: str) -> str:
    """Render *value* as a double-quoted JS string literal (escaped)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --------------------------------------------------------------------------- #
# 2. Landing page + 3. success page                                           #
# --------------------------------------------------------------------------- #

def write_pages(site_dir: str, slug: str, title: str, label: str, papers: list) -> None:
    """Write the guide landing page and the post-purchase success page.

    *papers* is a list of objects with ``.title`` and ``.meta`` attributes
    (roundups.RoundupPaper) used to build the honest "what's inside" list.
    Overwrites any existing pages (idempotent).
    """
    landing_dir = os.path.join(site_dir, "guides", slug)
    os.makedirs(landing_dir, exist_ok=True)
    with open(os.path.join(landing_dir, "index.html"), "w") as f:
        f.write(_render_landing(slug, title, label, papers))

    success_dir = os.path.join(site_dir, "success", slug)
    os.makedirs(success_dir, exist_ok=True)
    with open(os.path.join(success_dir, "index.html"), "w") as f:
        f.write(_render_success(slug, title, label))
    logger.info("publish: wrote landing + success pages for %s", slug)


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _render_landing(slug: str, title: str, label: str, papers: list) -> str:
    inside_items = "".join(
        "      <li><svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" "
        "stroke=\"currentColor\" stroke-width=\"2.4\"><path d=\"M20 6L9 17l-5-5\"/></svg> "
        f"{_esc(p.title)}"
        + (f" <span style=\"color:#8a9993\">({_esc(p.meta)})</span>" if getattr(p, 'meta', '') else "")
        + "</li>\n"
        for p in papers
    ) or (
        "      <li><svg width=\"20\" height=\"20\" viewBox=\"0 0 24 24\" fill=\"none\" "
        "stroke=\"currentColor\" stroke-width=\"2.4\"><path d=\"M20 6L9 17l-5-5\"/></svg> "
        "Every peer-reviewed study and preprint on GLP-1 medications and muscle "
        f"covered on MuscleOnGLP during {_esc(label)}.</li>\n"
    )
    tmpl = _LANDING_TEMPLATE
    return (
        tmpl.replace("__TITLE__", _esc(title))
        .replace("__LABEL__", _esc(label))
        .replace("__SLUG__", slug)
        .replace("__ORIGIN__", SITE_ORIGIN)
        .replace("__INSIDE_ITEMS__", inside_items)
    )


def _render_success(slug: str, title: str, label: str) -> str:
    return (
        _SUCCESS_TEMPLATE.replace("__TITLE__", _esc(title))
        .replace("__LABEL__", _esc(label))
    )


# --------------------------------------------------------------------------- #
# 4. Guides hub card (guides/index.html)                                       #
# --------------------------------------------------------------------------- #

def add_hub_card(site_dir: str, slug: str, title: str, label: str) -> bool:
    """Insert a guide card for this month at the top of the hub's guide-grid.

    Also adds the guide to the hub's ItemList JSON-LD. Idempotent: returns
    False (no change) if a card for *slug* already exists.
    """
    path = os.path.join(site_dir, GUIDES_HUB_REL)
    with open(path) as f:
        src = f.read()
    href = f"/guides/{slug}/"
    if href in src:
        logger.info("publish: hub card for %s already present", slug)
        return False

    card = _HUB_CARD_TEMPLATE.replace("__TITLE__", _esc(title)) \
        .replace("__LABEL__", _esc(label)).replace("__SLUG__", slug)
    marker = '<div class="guide-grid">'
    idx = src.find(marker)
    if idx == -1:
        raise RuntimeError("add_hub_card: could not find guide-grid in guides hub")
    insert_at = idx + len(marker)
    src = src[:insert_at] + "\n" + card + src[insert_at:]

    # Prepend to the ItemList JSON-LD so structured data stays complete. Best
    # effort: if the JSON-LD shape changes, skip silently rather than corrupt it.
    list_marker = '"itemListElement": ['
    lidx = src.find(list_marker)
    if lidx != -1:
        insert_ld = lidx + len(list_marker)
        ld_entry = (
            "\n    {\n"
            '      "@type": "ListItem",\n'
            '      "position": 1,\n'
            f'      "name": {_json_str(title)},\n'
            f'      "url": "{SITE_ORIGIN}/guides/{slug}/"\n'
            "    },"
        )
        src = src[:insert_ld] + ld_entry + src[insert_ld:]

    with open(path, "w") as f:
        f.write(src)
    logger.info("publish: added hub card for %s", slug)
    return True


def _json_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --------------------------------------------------------------------------- #
# 5. Sitemap                                                                    #
# --------------------------------------------------------------------------- #

def sitemap_add(site_dir: str, slug: str, date: str) -> bool:
    """Add the landing page URL to sitemap.xml. Idempotent."""
    path = os.path.join(site_dir, SITEMAP_REL)
    if not os.path.exists(path):
        return False
    with open(path) as f:
        xml = f.read()
    loc = f"{SITE_ORIGIN}/guides/{slug}/"
    if loc in xml:
        return False
    block = (
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{date}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>\n"
    )
    xml = xml.replace("</urlset>", block + "</urlset>")
    with open(path, "w") as f:
        f.write(xml)
    logger.info("publish: added sitemap entry for %s", slug)
    return True


# --------------------------------------------------------------------------- #
# HTML templates (reuse the site's existing CSS classes; no new styles)        #
# --------------------------------------------------------------------------- #

_LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ | MuscleOnGLP ($1 PDF)</title>
<meta name="description" content="A $1 PDF that synthesizes every GLP-1 and muscle research roundup MuscleOnGLP published in __LABEL__ into one cited monthly review. Fully sourced, not medical advice.">
<link rel="canonical" href="__ORIGIN__/guides/__SLUG__/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="MuscleOnGLP">

<meta property="og:type" content="website">
<meta property="og:site_name" content="MuscleOnGLP">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="A cited monthly synthesis of __LABEL__ GLP-1 and muscle research. $1 PDF.">
<meta property="og:url" content="__ORIGIN__/guides/__SLUG__/">
<meta property="og:image" content="__ORIGIN__/assets/og-card.png">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="A cited monthly synthesis of __LABEL__ GLP-1 and muscle research. $1 PDF.">
<meta name="twitter:image" content="__ORIGIN__/assets/og-card.png">

<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="stylesheet" href="/styles.css">

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "__TITLE__",
  "description": "A $1 PDF that synthesizes every GLP-1 and muscle research roundup MuscleOnGLP published in __LABEL__ into one cited monthly review.",
  "brand": { "@type": "Brand", "name": "MuscleOnGLP" },
  "category": "Health & Fitness Guide",
  "image": "__ORIGIN__/assets/og-card.png",
  "offers": {
    "@type": "Offer",
    "price": "1.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "url": "__ORIGIN__/guides/__SLUG__/"
  }
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "__ORIGIN__/" },
    { "@type": "ListItem", "position": 2, "name": "Mini-Guides", "item": "__ORIGIN__/guides/" },
    { "@type": "ListItem", "position": 3, "name": "__TITLE__", "item": "__ORIGIN__/guides/__SLUG__/" }
  ]
}
</script>
</head>
<body>

<header class="nav">
  <div class="wrap nav-inner">
    <a class="brand" href="/"><span class="brand-mark">M</span> MuscleOnGLP</a>
    <nav class="nav-links" aria-label="Primary">
      <a href="/research/">Research</a>
      <a href="/learn/">Learn</a>
      <a href="/guides/">Mini-Guides</a>
      <a href="/#evidence">The Evidence</a>
      <a class="btn btn-primary nav-cta" href="/#pricing">The Full Handbook</a>
    </nav>
  </div>
</header>

<main>
<section class="guide-hero">
  <div class="wrap">
    <p class="crumbs"><a href="/">Home</a><span>/</span><a href="/guides/">Mini-Guides</a><span>/</span>__TITLE__</p>
    <span class="eyebrow">Monthly research review &middot; __LABEL__</span>
    <h1>Every GLP-1 and muscle study from __LABEL__, synthesized into one cited review</h1>
    <p class="guide-sub">This mini-guide pulls together every paper covered in the weekly research roundups during __LABEL__ and turns them into a single, plain-language synthesis. Every claim traces back to a study named in the guide, and preprints are flagged as such.</p>
    <div class="guide-buybox" id="buy">
      <div class="p"><span class="now">$1</span><span class="unit">one-time &middot; instant PDF download</span></div>
      <label class="tos-check">
        <input type="checkbox" data-terms>
        <span>I have read and agree to the <a href="/terms/">Terms of Service</a>, including the medical disclaimer and the assumption of risk. I understand this is educational content, not medical advice.</span>
      </label>
      <button type="button" class="btn btn-primary btn-lg" data-checkout data-product="__SLUG__" data-status="status-__SLUG__">Buy now &mdash; instant download</button>
      <p id="status-__SLUG__" class="checkout-status" role="status" aria-live="polite"></p>
      <p class="guarantee">Secure checkout. You will be asked to accept our <a href="/terms/">Terms of Service</a> and medical disclaimer before payment.</p>
    </div>
  </div>
</section>

<section class="section features">
  <div class="wrap center">
    <h2>What is inside</h2>
    <ul class="inside-list">
__INSIDE_ITEMS__    </ul>
    <p class="evidence-note">Every finding in this review is attributed to a specific study named in the guide, drawn from that month's research roundups. Where the evidence is a preprint, mixed, or thin, the guide says so instead of rounding up.</p>
  </div>
</section>

<section class="section" style="padding-top:0">
  <div class="wrap center">
    <p class="lead">Prefer to skim the sources first? Browse the free weekly <a href="/research/">research roundups</a> this review is built from.</p>
  </div>
</section>

<section class="section finalcta">
  <div class="wrap center">
    <h2>__TITLE__</h2>
    <p class="lead">One dollar. Instant download. Every source named.</p>
    <div style="margin-top:28px">
      <a class="btn btn-primary btn-lg" href="#buy">Get it for $1 &rarr;</a>
    </div>
    <p class="guarantee" style="margin-top:22px">Purchases are subject to our <a href="/terms/">Terms of Service</a> and medical disclaimer.</p>
    <p class="guarantee">Want everything? The <a href="/#pricing">full 30-page handbook</a> covers the fundamentals for $5.</p>
  </div>
</section>
</main>

<footer>
  <div class="wrap">
    <p class="foot-disclaimer">This guide is educational and does not constitute medical advice. It provides no dosing, titration, or sourcing guidance for any medication. Consult your prescribing clinician before beginning a new exercise, nutrition, or supplement program.</p>
    <div class="foot-legal">
      <span>&copy; 2026 MuscleOnGLP. All rights reserved.</span>
      <span><a href="/terms/">Terms of Service</a></span>
      <span>Not affiliated with Novo Nordisk, Eli Lilly, or any medication manufacturer.</span>
    </div>
  </div>
</footer>

<script src="/checkout.js"></script>
</body>
</html>
"""


_SUCCESS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your guide is ready — __TITLE__</title>
<meta name="robots" content="noindex, nofollow">
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="stylesheet" href="/styles.css">
</head>
<body>

<header class="nav">
  <div class="wrap nav-inner">
    <a class="brand" href="/"><span class="brand-mark">M</span> MuscleOnGLP</a>
  </div>
</header>

<main>
<section class="section">
  <div class="wrap center" style="max-width:640px">
    <span class="eyebrow">Payment confirmed</span>
    <h2>Your __LABEL__ research review is ready.</h2>
    <p class="lead">Thanks for your purchase. Your download is below, and a copy of this link is on its way to your email. Save the file somewhere you will find it again.</p>
    <div style="margin-top:32px">
      <a class="btn btn-primary btn-lg" data-download href="#">Download the PDF &rarr;</a>
    </div>
    <p id="dl-note" class="guarantee" style="margin-top:28px">Your download link is tied to this order and to your acceptance of the <a href="/terms/">Terms of Service</a>. A copy has been emailed to you.</p>
    <p class="guarantee">Trouble downloading? Email <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> with your payment confirmation and we will resend it.</p>
    <p class="guarantee">Browse the <a href="/guides/">other mini-guides</a> or the <a href="/#pricing">full handbook</a>.</p>
  </div>
</section>
</main>

<footer>
  <div class="wrap">
    <p class="foot-disclaimer">This guide is educational and does not constitute medical advice. It provides no dosing, titration, or sourcing guidance for any medication. Consult your prescribing clinician before beginning a new exercise, nutrition, or supplement program.</p>
    <div class="foot-legal">
      <span>&copy; 2026 MuscleOnGLP. All rights reserved.</span>
      <span><a href="/terms/">Terms of Service</a></span>
      <span>Not affiliated with Novo Nordisk, Eli Lilly, or any medication manufacturer.</span>
    </div>
  </div>
</footer>

<script src="/download-link.js"></script>
</body>
</html>
"""


_HUB_CARD_TEMPLATE = """      <article class="guide-card">
        <a class="gc-thumb" href="/guides/__SLUG__/" aria-label="__TITLE__">
          <img src="/assets/cover.png" width="900" height="1165" loading="lazy"
               alt="Cover of __TITLE__">
        </a>
        <div class="gc-body">
          <p class="gc-kicker">Monthly review</p>
          <h3><a href="/guides/__SLUG__/">__TITLE__</a></h3>
          <p class="gc-desc">Every GLP-1 and muscle study from __LABEL__, synthesized into one cited review. Preprints flagged, sources named.</p>
          <div class="gc-meta">
            <span class="gc-price">$1</span>
            <span class="gc-pages">Monthly &middot; fully cited</span>
          </div>
          <label class="tos-check">
            <input type="checkbox" data-terms>
            <span>I agree to the <a href="/terms/">Terms</a> and medical disclaimer.</span>
          </label>
          <button type="button" class="btn btn-primary" data-checkout data-product="__SLUG__" data-status="hub-__SLUG__">Buy now</button>
          <p id="hub-__SLUG__" class="checkout-status" role="status" aria-live="polite"></p>
          <a class="gc-more" href="/guides/__SLUG__/">Read what is inside &rarr;</a>
        </div>
      </article>
"""


def list_monthly_guide(site_dir: str, year: int, month: int, date: str, papers: list) -> str:
    """Run all filesystem edits to list the month's guide. Returns the slug.

    *date* is the publish date (YYYY-MM-DD) used for the sitemap lastmod.
    *papers* feeds the landing page's "what's inside" list.
    """
    slug = month_slug(year, month)
    title = guide_title(year, month)
    label = month_label(year, month)
    append_product(site_dir, slug, title)
    write_pages(site_dir, slug, title, label, papers)
    add_hub_card(site_dir, slug, title, label)
    sitemap_add(site_dir, slug, date)
    return slug
