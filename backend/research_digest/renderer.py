"""Render the weekly roundup post and the /research/ hub as static HTML.

Design reuses the site's existing .article / .learn-card CSS. Every paper links
to its own source (DOI/PubMed); nothing is presented as MuscleOnGLP's own
finding. A standing transparency note states the post is an automated summary of
published abstracts, not medical advice or peer review.
"""
from __future__ import annotations

import html
from .models import WeeklyDigest

SITE = "https://getmuscleonglp.com"
DISCLAIMER = (
    "This roundup is compiled automatically from the abstracts of newly published "
    "research and is a neutral summary, not medical advice, not peer review, and not "
    "an endorsement. Studies vary in quality and preprints are not yet peer-reviewed. "
    "Read the linked source and talk to your clinician before changing anything."
)


def _nav() -> str:
    return """<header class="nav">
  <div class="wrap nav-inner">
    <a class="brand" href="/"><span class="brand-mark">M</span> MuscleOnGLP</a>
    <nav class="nav-links" aria-label="Primary">
      <a href="/research/">Research</a>
      <a href="/learn/">Learn</a>
      <a href="/guides/">Mini-Guides</a>
      <a href="/tools/">Calculators</a>
      <a class="btn btn-primary nav-cta" href="/#pricing">The Full Handbook</a>
    </nav>
  </div>
</header>"""


def _footer() -> str:
    return """<footer>
  <div class="wrap">
    <p class="foot-disclaimer">These summaries are educational and do not constitute medical advice. They provide no dosing, titration, or sourcing guidance for any medication. Consult your prescribing clinician before beginning a new exercise, nutrition, or supplement program, particularly while taking a GLP-1 medication.</p>
    <div class="foot-legal">
      <span>&copy; 2026 MuscleOnGLP. All rights reserved.</span>
      <span><a href="/terms/">Terms of Service</a></span>
      <span>Not affiliated with Novo Nordisk, Eli Lilly, or any medication manufacturer.</span>
    </div>
  </div>
</footer>
<script src="/analytics.js"></script>"""


def post_url(slug: str) -> str:
    return f"{SITE}/research/{slug}/"


def render_post_html(d: WeeklyDigest) -> str:
    e = html.escape
    title = f"GLP-1 &amp; Muscle Research Roundup: {e(d.week_label)}"
    desc = (f"New research on GLP-1 medications and muscle, lean mass, protein, and "
            f"training, published the week of {e(d.week_label)}. {d.count} papers "
            f"summarized with links to every source.")

    # JSON-LD: the post as an Article, plus each source as a referenced ScholarlyArticle.
    parts = []
    refs_ld = ",".join(
        '{"@type":"ScholarlyArticle","headline":%s,"url":%s}' % (
            _json(it.paper.title), _json(it.paper.url)) for it in d.items)
    ld_article = (
        '{"@context":"https://schema.org","@type":"Article",'
        f'"headline":{_json("GLP-1 & Muscle Research Roundup: " + d.week_label)},'
        f'"description":{_json("Weekly summary of new GLP-1 and muscle research.")},'
        f'"datePublished":"{d.date}","dateModified":"{d.date}",'
        '"author":{"@type":"Organization","name":"MuscleOnGLP","url":"https://getmuscleonglp.com/"},'
        '"publisher":{"@type":"Organization","name":"MuscleOnGLP","logo":{"@type":"ImageObject","url":"https://getmuscleonglp.com/assets/favicon.png"}},'
        f'"mainEntityOfPage":{{"@type":"WebPage","@id":"{post_url(d.slug)}"}},'
        f'"citation":[{refs_ld}]}}'
    )
    ld_crumb = (
        '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        '{"@type":"ListItem","position":1,"name":"Home","item":"https://getmuscleonglp.com/"},'
        '{"@type":"ListItem","position":2,"name":"Research","item":"https://getmuscleonglp.com/research/"},'
        f'{{"@type":"ListItem","position":3,"name":{_json(d.week_label)},"item":"{post_url(d.slug)}"}}]}}'
    )

    items_html = []
    for it in d.items:
        p = it.paper
        badge = ' <span class="rr-preprint">Preprint</span>' if p.is_preprint else ""
        meta = " &middot; ".join(x for x in [e(p.venue), e(p.pub_date), e(p.author_line())] if x)
        items_html.append(f"""      <article class="rr-item">
        <h2><a href="{e(p.url)}" target="_blank" rel="noopener">{e(p.title)}</a>{badge}</h2>
        <p class="rr-meta">{meta}</p>
        <p>{e(it.summary)}</p>
        {f'<p class="rr-why"><strong>Why it matters:</strong> {e(it.why_it_matters)}</p>' if it.why_it_matters else ''}
        {f'<p class="rr-action"><strong>What this means for you:</strong> {e(it.action)}</p>' if it.action else ''}
        <p class="rr-source"><a href="{e(p.url)}" target="_blank" rel="noopener">Read the {'preprint' if p.is_preprint else 'paper'} &rarr;</a></p>
      </article>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | MuscleOnGLP</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{post_url(d.slug)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="MuscleOnGLP">
<meta property="og:type" content="article">
<meta property="og:site_name" content="MuscleOnGLP">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{post_url(d.slug)}">
<meta property="og:image" content="https://getmuscleonglp.com/assets/og-card.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="stylesheet" href="/styles.css">
<script type="application/ld+json">{ld_article}</script>
<script type="application/ld+json">{ld_crumb}</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6407975157274256" crossorigin="anonymous"></script>
</head>
<body>
{_nav()}
<main>
<article>
  <header class="article-hero">
    <div class="wrap">
      <p class="crumbs"><a href="/">Home</a><span>/</span><a href="/research/">Research</a><span>/</span>{e(d.week_label)}</p>
      <p class="article-eyebrow">Weekly research roundup</p>
      <h1>GLP-1 and muscle research: {e(d.week_label)}</h1>
      <p class="article-dek">{e(d.intro)}</p>
      <div class="article-meta"><span>Published {e(d.date)}</span><span class="badge-cited">{d.count} papers &middot; every source linked</span></div>
    </div>
  </header>
  <section class="section" style="padding-top:16px">
    <div class="wrap">
      <div class="key-takeaways"><h2>How to read this</h2><ul><li>{e(DISCLAIMER)}</li></ul></div>
      <div class="article rr-list">
{chr(10).join(items_html)}
      </div>
      <div class="article-cta">
        <p class="k">Turn the evidence into a plan</p>
        <h3>The MuscleOnGLP handbook</h3>
        <p>These studies point the same direction our guides already put into practice: resistance training and enough protein preserve muscle while you lose weight. The 30-page handbook is the full, cited protocol.</p>
        <a class="btn btn-primary btn-lg" href="/#pricing">See the handbook &mdash; $5 &rarr;</a>
      </div>
    </div>
  </section>
</article>
</main>
{_footer()}
</body>
</html>
"""


def render_hub_html(posts: list[dict]) -> str:
    """posts: list of {slug, week_label, date, count, blurb} newest-first."""
    e = html.escape
    cards = []
    for m in posts:
        cards.append(f"""      <article class="learn-card">
        <p class="lc-kicker">Week of {e(m['week_label'])}</p>
        <h3><a href="/research/{e(m['slug'])}/">GLP-1 and muscle research: {e(m['week_label'])}</a></h3>
        <p>{e(m.get('blurb',''))}</p>
        <a class="lc-more" href="/research/{e(m['slug'])}/">Read the roundup &rarr;</a>
      </article>""")
    ld_items = ",".join(
        '{"@type":"ListItem","position":%d,"url":"%s/research/%s/"}' % (i + 1, SITE, m["slug"])
        for i, m in enumerate(posts))
    ld = ('{"@context":"https://schema.org","@type":"CollectionPage",'
          '"name":"GLP-1 & Muscle Research Roundup","url":"https://getmuscleonglp.com/research/",'
          f'"hasPart":[{ld_items}]}}') if posts else \
         ('{"@context":"https://schema.org","@type":"CollectionPage",'
          '"name":"GLP-1 & Muscle Research Roundup","url":"https://getmuscleonglp.com/research/"}')
    grid = ("\n".join(cards) if cards else
            '      <p class="lead">The first weekly roundup will appear here shortly.</p>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GLP-1 &amp; Muscle Research Roundup | Weekly, Cited | MuscleOnGLP</title>
<meta name="description" content="A weekly, automatically compiled roundup of new research on GLP-1 medications and muscle, lean mass, protein, and training. Every paper linked to its source.">
<link rel="canonical" href="https://getmuscleonglp.com/research/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MuscleOnGLP">
<meta property="og:title" content="GLP-1 & Muscle Research Roundup">
<meta property="og:description" content="A weekly, cited roundup of new GLP-1 and muscle research.">
<meta property="og:url" content="https://getmuscleonglp.com/research/">
<meta property="og:image" content="https://getmuscleonglp.com/assets/og-card.png">
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="stylesheet" href="/styles.css">
<script type="application/ld+json">{ld}</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6407975157274256" crossorigin="anonymous"></script>
</head>
<body>
{_nav()}
<main>
<section class="section">
  <div class="wrap center">
    <span class="eyebrow">Research &middot; updated weekly</span>
    <h1>New GLP-1 and muscle research, every week</h1>
    <p class="lead">Each week we scan PubMed and Europe PMC for new studies on GLP-1 medications and muscle, lean mass, protein, and training, then summarize the relevant ones with a link to every source. Neutral summaries, not medical advice.</p>
    <div class="learn-grid">
{grid}
    </div>
  </div>
</section>
</main>
{_footer()}
</body>
</html>
"""


def _json(s: str) -> str:
    import json
    return json.dumps(s or "")
