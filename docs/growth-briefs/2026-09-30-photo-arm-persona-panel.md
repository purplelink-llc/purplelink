# Photo arm: ten-persona panel, collated (2026-09-30)

Ten independent advisor personas (microstock veteran, fine-art print seller,
direct-licensing rep, SEO marketer, short-video creator, skeptical CFO,
data engineer, product diversifier, two buyers, community operator) each
got the same brief and returned 5-8 moves with payoff, effort and a kill
criterion. This file keeps what overlapped, what conflicted, and a plan.

Base rate they all worked from: 967 photos, 8 agencies, ~$22 lifetime,
$0 cash received (every platform is below its payout floor), Etsy 43
listings / 10 visits a week / 0 sales, FAA $1.60.

## Where they converged

1. **A destination hub on purplelink.llc is the spine.** Five personas
   (SEO, community, diversifier, direct-licensing, video) independently
   asked for one page per place (`/photography/iceland/`,
   `/photography/japan/kyoto/` ...) generated from the metadata CSVs, with
   8-25 self-hosted images, real captions, a few hand-written lines, image
   sitemap and `ImageObject` JSON-LD with `license`/`creator` so Google
   Images shows the Licensable badge. Everything else (Pinterest, Shorts,
   photo-for-credit, licensing, Etsy links) needs somewhere to point.
   Effort ~17 h once, $0. Kill: <50% indexed at 8 weeks.

2. **Sell direct on the domain with the Stripe plumbing that already
   exists.** Fine-art, B2B, SEO, diversifier and video all proposed it,
   from different angles:
   - license tiers (`/photography/license/`): roughly $19 web/blog,
     $59-79 commercial web/social, $149-249 print/editorial, quote form
     above that; 40-120 verified images with clean previews.
   - print editions for the 10 heroes via a POD lab (Prodigi/Bay Photo),
     three sizes ($89/$169/$289), honest numbered counts if editions are
     claimed.
   This is the only route where Ben keeps ~97% instead of 15-40%, and it
   gives Pixsy matches a rate card. Effort ~8 h + ~$150-200 proofs if
   editions. Kill: <2 sales by month 6.

3. **Freeze inventory expansion.** Veteran, CFO, SEO, community,
   diversifier and video all said stop adding microstock listings, stop
   new platforms, stop adding Etsy listings. Volume is not the constraint;
   discovery and price are. Leave live inventory up (free), let 123RF /
   Depositphotos / Vecteezy reviews finish, no further labor there.

4. **Metadata work only where it can be measured.** Veteran: rewrite
   captions/keywords on the top ~150 (Alamy first, since 320 views/week at
   0.6% CTR is traffic without conversion and Alamy's net per sale is the
   highest). Data engineer: do it as a 50/50 A/B on Alamy views+zooms and
   only roll out if B beats A by >25% at 28 days. Combined effort ~6 h.

5. **One concrete lead is sitting open.** Direct-licensing persona read
   the pitch log: Hotel d'Angleterre (Copenhagen) asked for previews on
   9/25. Follow up once with a one-page license (12 months web/social/
   email, $250 per image or $450 for both) and a Stripe payment link. A
   single yes exceeds all revenue to date. Then 15 individually written
   pitches a week to operators and hotels (Reykjavik tours, Zermatt/
   Grindelwald hotels, Kyoto ryokan, Copenhagen hotels), not tourism
   boards (they have free image banks and procurement).

6. **Etsy: fix ten hero listings or let it lapse, decide by Nov 30.**
   Buyer persona and fine-art agreed on what a listing needs: place-first
   searchable title ("Skogafoss waterfall Iceland wall art print"), all
   13 tags, one download containing 2:3 / 3:4 / 4:5 / 5:7 / ISO crops with
   printed max size stated, 3-4 calm room mockups, sets of 3 at ~$39,
   honest facts instead of reviews (camera, places, dates, "I took every
   photo", what the license allows). CFO's view: 9 visits/week is ~0.1
   expected sales; if visits stay <30/week after two retag rounds, stop
   renewing. Etsy Ads unlock ~Oct 10: cap at $1/day only if the ten
   listings are fixed first.

7. **Earned links through photos, not tools.** Community + SEO: offer 3
   matching photos free-for-credit to small travel bloggers whose posts
   have weak images (10 individually written emails a month, disclosed).
   Links point at the hub pages. Kill: <3 replies from 40 sends.
   Secondary: a transparency post with the real numbers (professor-style
   table), shared once where rules allow.

8. **Pinterest is the one social channel everyone endorsed.** SEO and
   video both: 1 board per place, ~5 pins/day from the CSV titles, links
   to the hub pages; pins live 6-12 months. ~5 h to script. Kill: <1,000
   monthly viewers at day 90.

9. **Short video as a demand sensor, not a revenue line.** Video persona:
   "Where is this?" 7-9 s guess-and-reveal format (no TTS, loop ending,
   pinned comment to the photography page), 1/day; before/after RAW edits
   3/week. Data engineer: use the first 12 to rank countries by
   watch-through and feed that into what gets pinned, listed and pitched.
   SEO: don't dilute @PurplelinkPL with it unless it earns its place.
   Stop: static slideshows with narration.

10. **Replace daily attention with a weekly decision memo and one metric.**
    CFO and data engineer: the metric is trailing-4-week accrued royalties
    divided by owner hours (currently ~$2.75/week over unknown hours;
    above $5/hour justifies growth). The sweep can keep running daily, but
    a Monday 5-line memo should say what changed, which test is mid-flight,
    which rule fired, and which action is queued. A collector that never
    changes a decision in 8 weeks gets dropped from the memo.

## Where they conflicted

- **Hours.** CFO: cap the arm at 1 hour/week, redirect to ModernTex and
  Paper Review (one extra $10 sale equals the arm's monthly revenue).
  Fine-art and B2B: spend 10-20 hours and ~$200 to test real prices.
  Resolution: most of the converged list is automation (hub pages, pins,
  shorts, memo) and costs near-zero owner hours after setup. The two
  experiments that need Ben's time and money (direct license page +
  print proofs, hotel pitches) are the only ones that can change the
  unit economics, so run them once under a 90-day gate rather than
  forever.
- **Etsy.** CFO: kill. Buyer/fine-art: fix ten listings first. Resolved
  above with the Nov 30 gate.
- **FAA.** Fine-art: passive catalogue, stop bulk work. CFO: downgrade to
  the free 25-image tier at renewal unless trailing revenue covers the
  fee. Both agree: no more uploads or metadata sweeps there.
- **Video pipeline.** Video persona builds an audience with it; CFO would
  not spend an hour on it. Resolved by the demand-sensor framing: 12
  videos, read the signal, then decide.

## Facts to verify before acting (flagged by the panel)

- Alamy's post-September-2026 split and minimum: platform-matrix.md says
  15% Bronze / $75, the brief assumed 40% / $50. Pull the statement.
- FAA analytics showed 7,411 visitors in 7 days (+452%); assume bots until
  referrers and geography say otherwise.
- Agency terms on selling the same files direct (Adobe, Shutterstock,
  Getty non-exclusive terms allow it, but check price-parity language).
- Country labels in the consultant package (sequoia photos labelled
  "Switzerland") and the Atlantis pitch going to a reservations inbox.
- Adobe: 105 "not accepted". Tally the reasons once; if it is Topaz
  artifacts or over-sharpening, fix the export, don't resubmit.

## Seasonal windows the panel flagged

- Christmas-market and autumn files (Cologne, Heidelberg, Kyoto) need to be
  live by mid-October to catch December searches.
- 2027 printable calendars (12 photos each, Letter + A4, $5.99, bundle
  $19) only sell until ~January 15. ~8 h scripted.

## A 30/60/90 plan with owner-hours

**Days 1-30 (Ben ~4 h, automation ~30 h)**
- Follow up Hotel d'Angleterre with the one-page license + Stripe link.
- Build the destination hub pages from the CSVs (generator + image SEO +
  JSON-LD + sitemap); Ben writes ~15 short intros.
- Fix the ten hero Etsy listings (titles, tags, multi-ratio downloads,
  mockups, facts block). Enable Etsy Ads at $1/day on Oct 10 if done.
- Start the Alamy 50/50 metadata test on 100 comparable images.
- Weekly Monday memo replaces reading the dashboard.
- Verify the five facts above.

**Days 31-60 (Ben ~3 h, automation ~20 h)**
- License page with three Stripe tiers on 40-60 verified images.
- Pinterest pipeline: boards per place, 5 pins/day to hub pages.
- Photo-for-credit outreach: 40 sends in the month, Ben approves each.
- 15 hotel/operator pitches a week, Ben approves each batch.
- 12 "Where is this?" shorts as the demand sensor.
- Read the Alamy test at day 28; roll out or stop.

**Days 61-90 (Ben ~2 h plus one decision)**
- Print proofs of the top 3 only if the license page or a pitch has
  produced a sale; otherwise skip the ~$200.
- Calendars before Jan 15 if Pinterest or hub traffic shows a destination
  with real pull.
- Day-90 gate on the whole arm: trailing-4-week royalties plus direct
  sales divided by owner hours. Above $5/hour, keep growing. Below it,
  hold the freeze and run the inventory as an annuity on 1 hour/week, as
  the CFO proposed.

## What everyone said to stop

- Adding microstock listings, Etsy listings or platforms.
- Daily human attention to balances that cannot change a decision.
- Treating national tourism boards as pitch targets.
- Posting photos or shop links in r/itookapicture-style subreddits.
- Static slideshow-with-narration video.
- Bulk uploads and metadata sweeps on FAA.
