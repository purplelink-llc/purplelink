# Measurement — Organic Traffic Program (brand-safe)

> **Privacy brand constraint:** this program adds **no site-side analytics,
> no cookies, no tracking scripts, no pixels.** Measurement is limited to
> Google Search Console (server-side, aggregate) and Netlify's own
> referrer/deploy logs (server-side, no visitor PII). A privacy-preserving
> server-side hit counter on the Modal backend is a separate future
> sub-project, not part of this program.

## Primary source: Google Search Console (GSC)

GSC is the source of truth for organic search performance. It reports
aggregate, privacy-safe data Google already has — nothing is added to the
site.

**Metrics to watch (Performance report):**

| Metric | What it tells you | Where |
|--------|-------------------|-------|
| Impressions | How often a page appeared in results | Performance → Pages |
| Clicks | How often someone clicked through | Performance → Pages |
| Average position | Typical ranking for a query | Performance → Queries |
| Queries | The actual searches surfacing each page | Performance → Queries |
| Coverage / Indexed | Whether a page is indexed at all | Pages report |

**How to read them:**
- **Impressions before clicks.** A new guide earns impressions first; clicks
  follow as it climbs. Rising impressions on a page that's a week old is the
  early success signal.
- **Position 11–20 = page 2.** Pages ranking there are the best optimization
  targets (small improvements can move them to page 1).
- **Query mismatch.** If a page ranks for queries you didn't intend, the
  intro/FAQ phrasing is steering it — adjust the literal wording to match the
  query you want.
- **Submit new URLs** via URL Inspection → Request Indexing after each ship
  (sitemap already lists them, but requesting speeds it up).

## Secondary source: Netlify referrer logs

For community-driven referral traffic (Phase 3), Netlify's analytics/logs
show referrers server-side without any client tracking.

- **Referrer spikes** after a Reddit/HN/Mastodon post confirm the post drove
  traffic and to which page.
- **Top pages** indicate which tool/guide resonates.
- Note: Netlify Analytics is server-log based (paid add-on); if not enabled,
  deploy logs and any function logs still show referrer headers.

## Checkpoint thresholds (from the spec)

**~30 days after Phase 1 ships:**
- [ ] All 13 tool pages register impressions in GSC.
- [ ] All 13 tools present in `llms.txt`. (Done in Task 1.)
- [ ] Every tool page has intro + FAQ + related-tools. (Verified in Task 2.)
- [ ] All 6 guides + the guides index indexed (Coverage report).

**~90 days:**
- [ ] The 6 guides registering impressions.
- [ ] Measurable click growth on tool pages vs. the 30-day baseline.
- [ ] A set of academic queries ranking in the top 20 (position ≤ 20).

**Phase 3 (ongoing):**
- [ ] Referral spikes from community posts visible in Netlify referrer logs.
- [ ] Durable backlinks live in at least a few directories/lists.

## Review cadence

- **Weekly (5 min):** glance at GSC Performance for new impressions and any
  page that jumped/dropped. Check Netlify referrers if a post went out.
- **Monthly:** compare against the checkpoint thresholds; pick the two page-2
  pages with the most impressions and improve their on-page wording.
