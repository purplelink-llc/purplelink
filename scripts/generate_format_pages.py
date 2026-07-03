#!/usr/bin/env python3
"""Generate the /format/references-for-<slug>/ venue pages + hub index from
format_pages_data.VENUES. Re-run after editing the dataset; this fully
overwrites the generated files so there's no drift between the dataset and
the pages on disk.

Usage: python3 scripts/generate_format_pages.py
"""
import html
import json
import os

from format_pages_data import VENUES

SITE = os.path.join(os.path.dirname(__file__), "..", "site")
FORMAT_LABELS = {"bibtex": "BibTeX", "ris": "RIS", "endnote": "EndNote"}


def venue_page(v):
    e = html.escape
    default_to = v["default_to"]
    format_label = FORMAT_LABELS[default_to]
    title = f"References for {v['abbr']} | Purplelink"
    description = (
        f"What reference format {v['name']} ({v['abbr']}) expects, and a free tool "
        f"to convert your bibliography to {format_label}."
    )
    canonical = f"https://purplelink.llc/format/references-for-{v['slug']}/"
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "name": title,
                "url": canonical,
                "description": description,
                "about": {"@type": "Organization", "name": v["name"]},
                "isPartOf": {"@type": "WebSite", "name": "Purplelink", "url": "https://purplelink.llc/"},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/"},
                    {"@type": "ListItem", "position": 2, "name": "Reference formats", "item": "https://purplelink.llc/format/"},
                    {"@type": "ListItem", "position": 3, "name": v["abbr"], "item": canonical},
                ],
            },
        ],
    }, indent=2)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{e(title)}">
    <meta property="og:description" content="{e(description)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{e(title)}">
    <meta name="twitter:description" content="{e(description)}">
    <script type="application/ld+json">
    {jsonld}
    </script>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/tools/reference-converter/reference-converter.css">
    <script src="/site.js" defer></script>
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
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content">
      <a class="back-link" href="/format/">← All venues</a>
      <div class="tools-hero">
        <p class="eyebrow">{e(v['field'])}</p>
        <h1>References for {e(v['abbr'])}</h1>
        <p>{e(v['name'])} accepts <strong>{e(v['manuscript_formats'])}</strong> manuscripts. Paste your references below and convert them to <strong>{format_label}</strong> — everything runs in your browser.</p>
      </div>

      <div class="tool-app" data-default-to="{default_to}">
        <div class="rc-field">
          <label for="rc-input">References to convert</label>
          <textarea id="rc-input" class="rc-input" spellcheck="false" placeholder="@article{{smith2020,
  title   = {{On Things}},
  author  = {{Smith, Jane and Doe, John}},
  journal = {{Journal of Examples}},
  year    = {{2020}},
  volume  = {{12}},
  pages   = {{3--14}},
  doi     = {{10.1000/example}}
}}"></textarea>
        </div>

        <div class="rc-selects">
          <div class="rc-field">
            <label for="rc-from">From</label>
            <select id="rc-from">
              <option value="auto" selected>Auto-detect</option>
              <option value="bibtex">BibTeX</option>
              <option value="ris">RIS</option>
              <option value="endnote">EndNote</option>
            </select>
          </div>
          <div class="rc-field">
            <label for="rc-to">To</label>
            <select id="rc-to">
              <option value="bibtex"{' selected' if default_to == 'bibtex' else ''}>BibTeX</option>
              <option value="ris"{' selected' if default_to == 'ris' else ''}>RIS</option>
              <option value="endnote"{' selected' if default_to == 'endnote' else ''}>EndNote</option>
            </select>
          </div>
        </div>

        <div class="tool-options">
          <button class="btn btn-primary" id="rc-run" type="button">Convert</button>
        </div>

        <p class="tool-status" id="rc-status" aria-live="polite"></p>
        <div class="tool-result" id="rc-result" hidden>
          <div class="rc-result-head">
            <h2>Converted output</h2>
            <button class="btn" id="rc-copy" type="button">Copy</button>
          </div>
          <pre class="rc-out"><code id="rc-out"></code></pre>
          <p class="rc-detected" id="rc-detected"></p>
        </div>
        <p class="tool-privacy">Your references never leave your browser — there's no upload and nothing is stored.</p>
      </div>

      <section class="tool-howto">
        <h2>What {e(v['abbr'])} expects</h2>
        <ul>
          <li><strong>Manuscript format:</strong> {e(v['manuscript_formats'])}</li>
          <li><strong>Template:</strong> {e(v['template'])}</li>
          <li><strong>Citation style:</strong> {e(v['citation_style'])}</li>
        </ul>
        <p>{e(v['format_note'])}</p>
      </section>

      <section class="tool-faq">
        <h2>Where this comes from</h2>
        <p class="faq-body">Sourced from <a href="{e(v['source_url'])}" rel="noopener">{e(v['source_url'])}</a>. {e(v['source_note'])}</p>
      </section>

      <!-- moderntex-cta -->
      <section class="waitlist-section">
        <p class="eyebrow">From the team behind these tools</p>
        <h2>Writing LaTeX on a Mac?</h2>
        <p>We're building ModernTex - a native macOS LaTeX studio. Join the waitlist for one email at launch.</p>
        <form class="waitlist-form" name="waitlist-moderntex" method="POST" data-netlify="true" data-netlify-honeypot="bot-field">
          <input type="hidden" name="form-name" value="waitlist-moderntex">
          <input type="hidden" name="source" value="format:{v['slug']}">
          <p hidden><input name="bot-field"></p>
          <input type="email" name="email" placeholder="your@email.com" required autocomplete="email" aria-label="Email address">
          <button type="submit">Notify me at launch</button>
        </form>
        <p class="waitlist-fine-print">We'll only use your email to notify you at launch. <a href="/privacy/">Privacy Policy</a> · <a href="/moderntex/">Learn more about ModernTex →</a></p>
      </section>

      <nav class="tool-related" aria-label="Related tools">
        <h2>More reference tools</h2>
        <ul>
          <li><a href="/tools/reference-converter/">Full reference converter →</a></li>
          <li><a href="/tools/bib-builder/">Build a BibTeX entry →</a></li>
          <li><a href="/format/">All venues →</a></li>
        </ul>
      </nav>

      <p class="tool-support">If this saves you time, you can <a href="https://buymeacoffee.com/bampel" target="_blank" rel="noopener">leave a tip</a> — it helps keep these tools free and online.</p>

      <script src="/tools/reference-converter/reference-converter.js" defer></script>
    </main>

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
</html>
"""


def hub_page():
    e = html.escape
    rows = "\n".join(
        f'          <li><a href="/format/references-for-{v["slug"]}/">'
        f'<strong>{e(v["abbr"])}</strong> — {e(v["name"])}<br>'
        f'<span class="venue-field">{e(v["field"])}</span></a></li>'
        for v in VENUES
    )
    title = "Reference Formats by Venue | Purplelink"
    description = "What reference/bibliography format each academic venue expects, with a free converter preset to the right output."
    canonical = "https://purplelink.llc/format/"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{e(title)}">
    <meta property="og:description" content="{e(description)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/tools/reference-converter/reference-converter.css">
    <script src="/site.js" defer></script>
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
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tools-hero">
        <p class="eyebrow">Reference formats</p>
        <h1>What each venue expects</h1>
        <p>A quick reference for what manuscript format, template, and bibliography format specific CS / IS / security venues use — with a free converter preset to the right output for each.</p>
      </div>

      <nav aria-label="Venues">
        <ul class="venue-list">
{rows}
        </ul>
      </nav>

      <p class="tool-support">Don't see your venue? Use the <a href="/tools/reference-converter/">full reference converter</a> — it converts between BibTeX, RIS, and EndNote for any target.</p>
    </main>

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
</html>
"""


def main():
    fmt_dir = os.path.join(SITE, "format")
    os.makedirs(fmt_dir, exist_ok=True)
    with open(os.path.join(fmt_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(hub_page())
    print("wrote site/format/index.html")

    for v in VENUES:
        page_dir = os.path.join(fmt_dir, f"references-for-{v['slug']}")
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(venue_page(v))
        print(f"wrote site/format/references-for-{v['slug']}/index.html")


if __name__ == "__main__":
    main()
