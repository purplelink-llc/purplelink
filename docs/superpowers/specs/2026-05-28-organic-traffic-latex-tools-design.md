# Organic Traffic Program — Free LaTeX Tools — Design Spec

## Context

Purplelink LLC runs 13 free, client-and-server LaTeX/academic web tools at
`/tools/`. They exist as top-of-funnel marketing for the studio's native macOS
product, ModernTex. On-page SEO is already strong (keyword-rich titles, FAQ /
WebApplication / BreadcrumbList / Offer structured data, OG images, a 28-URL
sitemap, AI crawlers explicitly welcomed in `robots.txt`, and a published
`llms.txt`). Google Search Console is active.

This spec defines a **phased, multi-channel organic-traffic program** for the
tools across three reinforcing channels — GEO (AI-assistant citation), Google
organic, and academic community — sequenced **foundation-first**. The channels
compound: community posts create backlinks (Google authority) and AI-crawlable
mentions (GEO); how-to guides capture Google long-tail and are the
"answer-shaped" content AI assistants cite.

### Hard constraints

- **Privacy brand.** The privacy policy states the site uses no cookies,
  analytics scripts, or tracking technology. This program adds **no site-side
  tracking of any kind.** Measurement is limited to Google Search Console and
  Netlify referrer/deploy logs (server-side, no visitor PII).
- **No paid acquisition.** Organic only.
- **Static site.** Tools are static HTML/CSS/JS under `site/`, deployed to
  Netlify. The only backend is the Modal FastAPI service the tools call.

### Current-state findings that drive the design

1. **`llms.txt` is stale.** Its "Tools (free web tools)" section lists only 3
   of the 13 tools (latex-to-pdf, latex-diff, latex-to-word). The other 10 are
   invisible to AI assistants that read the file. This is the single
   cheapest GEO win.
2. **No how-to content.** All 5 blog posts are product/announcement posts. There
   are no informational guides mapped to the queries academics actually search,
   so the tools capture little long-tail intent and offer little for AI
   assistants to cite.
3. **Foundation already built.** The 2026-05-27 SEO/GEO spec created `llms.txt`,
   the sitemap, structured data, and the privacy/about/press pages. This spec
   builds on that, it does not redo it.

## Goal & success criteria

Grow qualified organic traffic to the tools, measured exclusively through
Google Search Console (GSC) and Netlify referrer logs.

Checkpoints (targets the user can adjust):

- **Within ~30 days of Phase 1 shipping:** all 13 tool pages register
  impressions in GSC; all 13 tools present in `llms.txt`; every tool page has
  an intro paragraph + FAQ block + related-tools links.
- **Within ~90 days:** the 6 seed guides indexed and registering impressions;
  measurable click growth on tool pages; a set of academic queries ranking in
  the top 20.
- **Phase 3 (ongoing):** referral spikes from community posts visible in Netlify
  referrer logs; durable backlinks live in at least a few directories/lists.

## Phase 1 — Foundation (on-site, cheap, compounding)

### 1.1 Complete `llms.txt`
Add the 10 missing tools to the "Tools (free web tools)" section, each as a
one-line `Name: URL — capability, privacy note` entry matching the existing 3
entries' format. Tools to add: bib-builder, bib-validator, citation-generator,
equation-renderer, latex-table-generator, markdown-to-pdf, pdf-tools,
reference-converter, word-counter, word-to-latex. Keep the "files never stored"
phrasing where true.

### 1.2 Answer-shaped on-page content (all 13 tool pages)
Bring every tool page to parity on two elements:
- **Intro paragraph** — one short paragraph stating what the tool does and when
  to use it, phrased in the literal language of the target search query
  (e.g., "Convert a LaTeX paper to a Word .docx for free…").
- **FAQ block with FAQ schema** — 3–5 Q&As using the literal question phrasing.
  Some pages already have this; audit all 13 and add where missing so coverage
  is uniform.

Implementation: a single shared content pattern (intro + FAQ + related-tools)
applied consistently across the 13 pages, so the markup and schema stay uniform
and maintainable.

### 1.3 Internal linking
Add a "Related tools" block (3–4 contextually related tools) to the bottom of
each tool page, and ensure the `/tools/` hub uses descriptive anchor text. This
flows link equity and signals topical clustering to crawlers.

## Phase 2 — Content engine (how-to guides)

### 2.1 New `/guides/` section
A new content type separate from `/blog/` (cleaner topical signal; separates
evergreen how-tos from company announcements). Includes:
- A templated guide page layout with article + FAQ + BreadcrumbList schema.
- A `/guides/` index page.
- Sitemap entries for the index and each guide.
- Each guide links to (and is linked from) its corresponding tool page.

### 2.2 Seed guides (6)
Each maps to a high-intent academic query and embeds/links its tool:

| Guide | Target query intent | Tool |
|-------|--------------------|------|
| Convert a LaTeX paper to Word (free) | "latex to word converter" | latex-to-word |
| Fix common BibTeX errors | "bibtex error / not working" | bib-validator |
| IEEE vs APA vs MLA vs Chicago citation formats | "ieee vs apa citation" | citation-generator |
| Show changes between two LaTeX versions (latexdiff) | "latex track changes / diff" | latex-diff |
| Count words in a LaTeX document | "latex word count" | word-counter |
| Get BibTeX from a DOI or arXiv ID | "doi to bibtex" | bib-builder |

### 2.3 Cadence
After the seed set, a sustained cadence (target: ~1 guide/week) is the long-term
engine. The cadence is a commitment recorded here; ongoing authoring is not part
of this build.

## Phase 3 — Community outreach & backlinks (playbook, not code)

Claude cannot post to third-party platforms on the user's behalf. This phase is
a **written playbook** the user executes:
- **Launch posts** for r/LaTeX, r/PhD, r/AskAcademia, academic Mastodon, TeX
  StackExchange (answer real questions; link only when genuinely helpful), and
  Show HN — each with a copy template and the optimized page as the target.
- **Durable listings** for backlinks that also feed GEO: GitHub "awesome" lists,
  AlternativeTo, and relevant tool directories.
- A target list + cadence + the rule that every post points at a Phase-1/2
  optimized page.

## Measurement (brand-safe)

A short measurement doc defining:
- **GSC** as primary KPI source: tool/guide impressions, clicks, queries ranked,
  average position. How to read each, and the checkpoint thresholds above.
- **Netlify referrer logs** for community-driven referral traffic.
- Explicit statement that **no site-side analytics is added** (privacy brand).
- Note: a privacy-preserving server-side hit counter on the Modal backend is a
  **separate future sub-project**, not built here.

## Deliverable units

1. Updated `site/llms.txt` (10 tools added).
2. A shared tool-page content pattern (intro + FAQ + related-tools) applied
   across all 13 tool pages, with uniform schema.
3. `/guides/` section: templated layout, index page, sitemap entries.
4. 6 seed guides (Phase 2.2), each cross-linked with its tool.
5. Outreach playbook doc (Phase 3).
6. Measurement doc.

## Out of scope (YAGNI)

- Paid ads / paid acquisition.
- Any site-side analytics or tracking script.
- ModernTex funnel CTAs from the tools (separate sub-project #1).
- Net-new tools (separate sub-project).
- The privacy-preserving server-side hit counter (separate future sub-project).
- Automated/ongoing guide authoring beyond the 6 seed guides.
