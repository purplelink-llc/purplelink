# Daily Digest — Design Spec

**Date:** 2026-06-22
**Status:** Approved
**Owner:** Ben Ampel / Purplelink LLC

## Summary

A fully automated daily newsletter published as a static blog post on
`purplelink.llc/blog/` and sent as an email blast via Buttondown. Content is
harvested from ~35 sources across academic papers, AI/ML, cybersecurity,
finance, and entrepreneurship, then curated and ranked by Claude using a
Ben-specific profile. The digest has a distinct editorial identity — the
intersection of academia, entrepreneurship, AI, and cybersecurity, written for
someone who is both a researcher and a builder. Others can subscribe and read;
the curation is optimized for Ben.

Each issue is titled "Daily Digest #N — June 22, 2026" and lives at
`purplelink.llc/blog/digest/YYYY-MM-DD.html`. No new tool page, no new
checkout. The entire pipeline is added to the existing monorepo.

## Architecture

**Approach:** Modal Cron → GitHub API Push → Netlify auto-deploy → Buttondown
email blast.

```
backend/digest/
  __init__.py
  sources.py      — source registry (RSS URLs, API endpoints, category tags)
  harvester.py    — async fetch from all sources → list[RawItem]
  curator.py      — Claude ranks + writes editorial notes → DigestData
  publisher.py    — renders HTML, pushes to GitHub, calls Buttondown API
```

Modal cron fires daily at **10:00 UTC (6am ET)**. Sequence:

1. Harvest all sources concurrently (target ~30s, 10s timeout per source)
2. Curate — one Claude call scores, selects, and annotates items
3. Publish:
   a. Write `site/blog/digest/YYYY-MM-DD.html` via GitHub API
   b. Update `site/blog/index.html` (prepend new entry) via GitHub API
   c. Netlify auto-deploys on push (existing webhook, ~30s)
   d. Buttondown API: create and send email broadcast

**Abort condition:** If fewer than 5 items survive curation after harvesting all
sources, the run is skipped and logged. No empty digest is published.

## Content Sources

All sources return `RawItem(title, url, source_name, snippet, published_at,
category)`. Source failures degrade silently — no single source is
load-bearing.

### Papers & Research

| Source | Endpoint | Auth | Notes |
|---|---|---|---|
| arXiv | `rss.arxiv.org/rss/cs.AI+cs.LG+cs.CR+stat.ML+q-fin.GN` | None | OAI-PMH preferred for daily pipelines; RSS Mon–Fri only |
| Semantic Scholar | `api.semanticscholar.org/graph/v1/paper/search/bulk` | Free key | Abstracts + OA PDF links |
| OpenAlex | `api.openalex.org/works` | None (100k req/day) | Replaces SSRN/IEEE/ACM for open-access coverage |
| HuggingFace Daily Papers | `huggingface.co/api/daily_papers` | None | Replaces Papers with Code (dead July 2025) |
| OpenReview | `openreview.net/notes` API | None | NeurIPS/ICLR/ICML preprints |

### AI & Technology

| Source | RSS URL | Notes |
|---|---|---|
| HuggingFace Blog | `huggingface.co/blog/feed.xml` | Use `<guid>` for URL (not `<link>`) |
| OpenAI | `openai.com/news/rss.xml` | Official |
| Google DeepMind | `deepmind.google/blog/rss.xml` | Note `.google` TLD |
| Anthropic | `raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml` | Scraped daily; no official feed |
| Mistral AI | `mistral.ai/rss.xml` | Native Astro feed, confirmed current |
| Cohere | Alan Turing Institute proxy feed | No native RSS (Sanity CMS) |
| Together AI | RSS.app-generated feed from `together.ai/blog` | No native RSS (Webflow) |
| Hacker News | `hnrss.org/frontpage?points=100` | Score-filtered; single Algolia call via `/search_by_date?tags=front_page,story&numericFilters=created_at_i>YESTERDAY_UNIX` |
| TLDR AI | `tldr.tech/api/rss/ai` | Daily concise |
| Import AI (Jack Clark) | `importai.substack.com/feed` | Weekly |
| The Gradient | `thegradientpub.substack.com/feed` | |
| AI Alignment Forum | `alignmentforum.org/feed.xml` | |

### Cybersecurity

| Source | Endpoint | Notes |
|---|---|---|
| Krebs on Security | `krebsonsecurity.com/feed/` | Full text in feed |
| Schneier on Security | `schneier.com/blog/atom.xml` | Full text in feed |
| Bleeping Computer | `bleepingcomputer.com/feed/` | Full text; most reliable |
| SANS ISC | `isc.sans.edu/rssfeed_full.xml` | Requires contact email in User-Agent |
| The Hacker News | `thehackernews.com/feeds/posts/default` | Excerpts only |
| Dark Reading | `darkreading.com/rss.xml` | Excerpts only |
| CrowdStrike Blog | `crowdstrike.com/en-us/blog/feed/` | |
| Mandiant/Google TI | `cloud.google.com/blog/topics/threat-intelligence/rss/` | |
| GreyNoise Blog | `greynoise.io/blog/rss.xml` | Signal/noise threat intel |
| Google Project Zero | `googleprojectzero.blogspot.com/feeds/posts/default` | High-signal vuln research |
| Trail of Bits | `blog.trailofbits.com/feed/` | Developer security |
| PortSwigger Research | `portswigger.net/research/rss` | High-signal vuln disclosures |
| CISA KEV | `cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | JSON, diff daily; RSS retired May 2025 |
| CVE.org | `cve.org/new-cves.rss` | NVD RSS retired 2024; use CVE.org or NVD API v2 |
| NVD API v2 | `services.nvd.nist.gov/rest/json/cves/2.0` | Free API key, 50 req/30s with key |

### Finance & Business

| Source | RSS URL | Notes |
|---|---|---|
| Morning Brew | `morningbrew.com/daily/rss` | |
| The Hustle | `thehustle.co/feed/` | |
| MarketWatch | `feeds.marketwatch.com/marketwatch/topstories/` | |
| Yahoo Finance | `finance.yahoo.com/news/rssindex` | |
| CoinDesk | `coindesk.com/arc/outboundfeeds/rss/` | |
| Alpha Vantage | `alphavantage.co/query?function=NEWS_SENTIMENT` | Free key, 25 req/day; news + sentiment |

### Entrepreneurship & Startups

| Source | RSS URL | Notes |
|---|---|---|
| a16z | `a16z.com/feed/` | |
| First Round Review | `review.firstround.com/rss` | |
| Paul Graham | `paulgraham.com/rss.html` | Infrequent, high signal |
| Y Combinator Blog | `ycombinator.com/blog/rss.xml` | |
| Indie Hackers | `indiehackers.com/feed.xml` | |
| Lenny's Newsletter | `lennysnewsletter.com/feed` | Free posts |
| SaaStr | `saastr.com/feed/` | |
| Stratechery | `stratechery.com/feed/` | 1 free essay/week |

### General Tech

| Source | RSS URL | Notes |
|---|---|---|
| Ars Technica | `feeds.arstechnica.com/arstechnica/index` | |
| MIT Technology Review | `technologyreview.com/feed/` | Full text in feed (legacy behavior) |
| IEEE Spectrum | `spectrum.ieee.org/feeds/feed.rss` | Full text in feed; topic sub-feeds available |
| Wired | `wired.com/feed/rss` | Excerpts; prefer category feeds to avoid deals spam |
| TechCrunch | WP REST API: `techcrunch.com/wp-json/wp/v2/posts` | Better than RSS; structured JSON |

**LinkedIn excluded:** no viable public API.
**Bloomberg excluded:** hard paywall, no public RSS.

## Ben's Profile (Personalization)

Stored as `BEN_PROFILE` constant in `curator.py`. Passed to Claude with every
curation call. Not user-configurable at runtime.

```
Benjamin Ampel is a PhD-level researcher in cybersecurity, AI, and Information
Systems based in Atlanta, GA. He runs Purplelink LLC, a one-person macOS/iOS
software studio. Research focus: LLMs applied to cybersecurity, adversarial ML,
dark web intelligence, cyber threat detection, and information systems. Side
interests: AI/ML tooling and inference infrastructure, startup/indie hacking on
Apple platforms, quantitative finance and macro trends, and the business of
academic publishing. Prefers novel findings over incremental work, practical
implications over pure theory, papers with reproducible results or strong
empirical evidence, and well-argued contrarian takes. Skeptical of hype; values
specificity. Already reads widely in these areas, so novelty and non-obviousness
matter more than topic relevance alone.
```

## Curation Logic

One Claude call per run using **`claude-sonnet-4-6`** (upgrade to Opus if
curation quality is underwhelming in practice). Input: all raw items (title,
source, snippet, URL, published date). Output: structured JSON with selected
items, scores, category assignments, and editorial notes.

The curation prompt instructs Claude to favor items a well-read researcher would
want to have read today — prioritizing novelty and non-obviousness over pure
topic relevance. Editorial notes are 2–3 sentences, plain and specific, no hype,
no promotional language, matching the Purplelink brand voice.

**Section caps per run:**

| Section | Cap |
|---|---|
| Papers & Research | 6 |
| AI & Technology | 5 |
| Cybersecurity | 4 |
| Finance & Business | 3 |
| Developer / Security Research | 3 |
| Worth Reading (misc) | 2 |

**Total max items per digest: 23.**

## Blog Post Format

Static HTML file at `site/blog/digest/YYYY-MM-DD.html`. Uses existing
`styles.css` with no new CSS classes. Rendered from a Python f-string template
in `publisher.py` (no Jinja2 dependency added).

**Post structure:**

```
Daily Digest #N — June 22, 2026

[1-paragraph curatorial intro]

Papers & Research
  Item title (Source)
  Editorial note (2–3 sentences)
  → Link

[repeat per section]

Footer: N sources reviewed · M selected · Subscribe →
```

The digest index at `site/blog/index.html` lists all past issues in reverse
chronological order. Updated on every run by the publisher (GitHub API
read → prepend → write).

**URL pattern:** `purplelink.llc/blog/digest/2026-06-22.html`

The digest number (#N) is derived by counting existing digest files in
`site/blog/digest/` via GitHub API + 1.

## Publisher Sequence

```python
# In publisher.py
async def publish(digest: DigestData, github_token: str, buttondown_key: str):
    html = render_html(digest)                      # f-string template
    await github_write(html, digest.date, github_token)   # new digest file
    await github_update_index(digest, github_token)       # update index
    # Netlify deploys automatically on push (~30s)
    await buttondown_send(digest, html, buttondown_key)   # email blast
```

Buttondown broadcast is sent immediately after the GitHub write. Blog post will
be live by the time subscribers click through (Netlify deploy is ~30s).

## Email & Subscriber Management

**Service:** Buttondown (newsletter-first, simple API, privacy-respecting,
no tracking pixels by default).

Subscribers sign up via:
- Buttondown embed form on `site/blog/index.html`
- Subscribe link in every digest footer

Buttondown handles: confirmation emails, unsubscribes, bounce handling, list
management. No subscriber data is stored in the Purplelink codebase or on
Modal.

## Deployment & Secrets

Three new Modal secrets required:

| Secret name | Value | Where to get |
|---|---|---|
| `GITHUB_TOKEN` | Fine-grained PAT with write access to this repo only | GitHub → Settings → Developer settings → Fine-grained tokens |
| `BUTTONDOWN_API_KEY` | API key from Buttondown dashboard | buttondown.email → Settings → API |
| `SEMANTIC_SCHOLAR_API_KEY` | Free key | semanticscholar.org/product/api |

`ANTHROPIC_API_KEY` already exists in Modal.

NVD and Alpha Vantage free keys are low-priority; add when setting up those
specific fetchers. IEEE Xplore API key takes 1–2 business days to issue; add
for conference tracking.

The Modal function is defined in `backend/digest/app.py`:

```python
import modal

app = modal.App("purplelink-digest")

@app.function(
    schedule=modal.Cron("0 10 * * *"),  # 10:00 UTC = 6:00am ET
    secrets=[
        modal.Secret.from_name("anthropic"),
        modal.Secret.from_name("github"),
        modal.Secret.from_name("buttondown"),
        modal.Secret.from_name("semantic-scholar"),
    ],
)
async def run_daily_digest():
    from digest.harvester import harvest_all
    from digest.curator import curate
    from digest.publisher import publish
    ...
```

**Local dry-run:** `DRY_RUN=1` env var skips the GitHub push and Buttondown
call; prints rendered HTML to stdout instead. Used during development.

## Testing

```
backend/tests/
  test_digest_harvester.py   — mock HTTP, verify RawItem shape per source
  test_digest_curator.py     — mock Anthropic, verify section caps + abort condition
  test_digest_publisher.py   — mock GitHub API + Buttondown, verify call sequence
```

Each module is pure logic + injected async IO, mirroring the existing
`citation_audit.py` pattern. No network calls in tests.

## Error Handling

- Source fetch failure → skip that source, log; never blocks the run
- < 5 items after curation → abort run, log; no post published
- GitHub push failure → retry once with exponential backoff, then log and exit
- Buttondown failure → log; don't retry (post is already live)
- All errors surface in Modal's built-in logging; no alerting infrastructure
  added at this stage

## Content Freshness

Most sources are fetched fresh on each run. The harvester tracks `published_at`
and filters items older than 48 hours (48h rather than 24h to handle weekend
gaps and timezone offsets without missing items). Deduplication across sources
is by URL normalization (strip UTM params, normalize trailing slashes).

## Out of Scope

- LinkedIn aggregation (no viable public API)
- Personalization per subscriber (all subscribers see Ben's curated view)
- Paid subscriber tiers
- Persisting digest history beyond the static HTML files
- Full-text retrieval for paywalled articles
- A/B testing digest formats
- Analytics on which items get clicks

## Risks

- **Scraped feeds (Anthropic, Cohere, Together AI) go stale** if upstream sites
  change structure. Mitigation: treat these as bonus sources, not required;
  fetcher failures degrade silently.
- **arXiv rate limits** under load. Mitigation: use OAI-PMH protocol instead of
  REST API for daily paper harvesting.
- **Buttondown deliverability** with a new sending domain. Mitigation: set up
  SPF/DKIM/DMARC on the sending domain before first send; Buttondown's docs
  cover this.
- **GitHub API rate limit** (5,000 req/hr authenticated). Two API calls per run
  is trivially within limit.
