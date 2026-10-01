# Photo Licensing — Account Signup Runbook

Every decision is pre-made below with its rationale. Work top to bottom; each
platform is 5–15 minutes. **All of it requires you personally** — signups, terms
acceptance, and tax forms can't be delegated to an agent.

Record account status in `docs/photo-licensing/tracker.csv` as you go.

---

## Before you start — three decisions

**1. Tax identity for W-9s.** You'll file a W-9 at ~7 US platforms.
Disregarded-entity rule: **line 1 = Benjamin M. Ampel** (your name, not the LLC),
**line 2 = Purplelink LLC**, and the TIN is either your SSN or the LLC's EIN
(in `Legal/CP_575_G - EIN Confirmation Letter.pdf`).

> **Recommendation: use the EIN.** Same tax outcome, but it keeps your SSN off a
> dozen third-party platforms. Decide once and use it everywhere.

**2. Adobe Stock and AI training.** Uploading to Adobe Stock means consenting to
Firefly training on your images, with no opt-out (a contributor challenged this
and lost in March 2026). Adobe is also the single biggest earner in stock today,
by roughly 2–4× over Shutterstock.

> **Recommendation: opt in.** Skipping Adobe costs you the largest revenue
> channel; the training happens across the industry regardless. But this is a
> values call and it is entirely yours — if you'd rather not, skip step 3 below
> and everything else still works.

**3. Business address.** Use the principal office from the Operating Agreement:
8735 Dunwoody Place #12398, Atlanta, GA 30350. Support email: ben@purplelink.llc

---

## Copy-paste text (every platform asks for these)

**Artist / contributor bio — short (under 200 chars):**
> Benjamin Ampel is a photographer based in Atlanta. He shoots travel, landscape,
> and night skies, from Iceland's south coast to the Sonoran Desert.

**Artist bio — long (for FAA, Picfair, premium applications):**
> Benjamin Ampel is a photographer based in Atlanta, Georgia. His work centers on
> travel and landscape — Iceland's waterfalls and glacier lagoons, the Swiss Alps,
> Japan's temples and city streets, and the Sonoran Desert under monsoon lightning.
> He shoots on Nikon Z-series bodies and works primarily in natural light. Prints
> and licensing are handled through Purplelink LLC.

**Business/shop name:** Purplelink LLC
**Website:** https://purplelink.llc
**Preferred username (keep consistent across platforms):** benampel

---

## Order of operations (why this sequence)

Juried platforms first — they have review lead time, so applying early means the
waiting happens in parallel with everything else.

### Step 1 — iStock / Getty *(juried, apply first)*
- URL: https://www.gettyimages.com/workwithus
- Submit 3–6 of your strongest images. **Six are staged and ready** in
  `photo-licensing-workspace/getty-application/` — Interlaken panorama, Kilauea
  caldera, desert night sky with light trails, redwood sunburst, Sonoran Desert
  waterfall, and the Cologne skyline panorama. Chosen for range (alpine, volcanic,
  astro, forest, desert, urban) rather than picking six of the same thing, which
  is what jurors look for.
- Getty offers the **non-exclusive agreement by default** on acceptance (verified
  on their site). Exclusivity is a later opt-in upsell — **decline it.** It locks
  those images to Getty alone and kills the multi-platform strategy.
- Payout minimum is $100 — expect this one to accrue slowly.

**Getty's AI-retouching rules affect 85 of your images** (verified from their
May 2025 Retouching & Modification Requirements):
- Getty allows AI-assisted retouching only on **≤10% of an image's pixels**, and
  bans generative AI for anything larger. Whole-image Topaz upscale or denoise
  plausibly exceeds that — Getty explicitly declines to rule tool-by-tool and
  puts the judgment call on you.
- Stricter still: **editorial files must not be retouched with any tool**, beyond
  whole-image color correction. **50 of your editorial keepers** are Topaz-processed
  (the `-Enhanced` basketball series is the bulk of it). These are the real risk.
- Consequence for violations is not just rejection — Getty's page names "account
  suspension, or account closure."
- **A conservative 666-image Getty-safe set** (no AI-processed files at all) is at
  `photo-licensing-workspace/getty-safe-set.csv`. Start there; the 85 excluded
  files can still go to Adobe, Alamy, and FAA.
- The 6 application images are all clean — verified, none AI-processed.

### Step 2 — Vecteezy *(juried, apply second)*
- URL: https://www.vecteezy.com/contributors
- Requires 25 sample files plus government ID verification; decision in ~5–7 days.
- Use the 25 in `batch-01-first25/`.
- **Keep your work in the Pro (paid) tier, not the Free pool** — free-pool
  downloads pay a flat pittance and undercut the same images elsewhere.

### Step 3 — Adobe Stock *(only if you opted in above)*
- URL: https://contributor.stock.adobe.com
- Sign in with your Adobe ID, complete the tax interview (W-9).
- Note your **SFTP credentials** — Adobe has the best bulk pipeline of any
  platform and I'll use them to automate uploads.
- No exam, no jury. 33% flat royalty, $25 payout minimum.

### Step 4 — Shutterstock
- URL: https://submit.shutterstock.com
- Complete the tax interview (W-9).
- **Toggle the AI data-licensing opt-out** in Account Settings if you want to
  exclude your work from their AI data deals — unlike Adobe, Shutterstock lets you.
- Note your **FTPS credentials**.
- Levels reset every January 1, so royalties start at 15% and climb with volume.

### Step 5 — Alamy *(best fit for your editorial work)*
- URL: https://www.alamy.com/contributor/
- UK company: no W-9, no 1099 — you self-report the income on Schedule C.
- **Your first submission is inspected at 100%.** Send 3–5 technically flawless
  files first (pick from the 5-star landscapes), pass QC, then upload in volume.
- This is where your **413 editorial images** shine — Alamy needs no model or
  property releases for editorial, unlike everyone else.
- Note: commission drops to 20% for contributors under $3k/yr as of Sept 1.

### Step 6 — Fine Art America *(print-on-demand)*
- URL: https://fineartamerica.com
- Start on the free tier (25 images) or go straight to Premium ($30/yr, unlimited).
- Verified limits: **25MB max per file**, formats **.jpg/.jpeg/.png**, no minimum
  pixel size. Collections are Premium-only. Digital downloads let you set your own
  price and keep 100% (FAA adds 30% on top for the buyer).
- W-9 required; US company, so you'll get a 1099.
- Upload `batch-01-first25/` first — already ordered by quality and print size.

**STATUS: Default Settings are configured and saved (2026-08-05).** Print markups
set across all 16 size tiers, category set to Photographs, medium "Photograph",
**AI Writing turned OFF** (it would have overwritten the 267 curated descriptions
with generic text), and **Post to Twitter turned OFF** (it was on by default and
would have fired one auto-tweet per upload — 267 of them).

**Remaining FAA work is manual** — the browser file-upload tool is sandboxed to
files shared directly with a chat session, so an agent cannot feed it your photo
library. Uploading is yours to do, from
`photo-licensing-workspace/faa-upload/batch-01-first25/`.

**Do this BEFORE bulk uploading** (can't be fixed cheaply later):

**Test upload ONE image first.** FAA reportedly auto-fills Title, Description, and
Keywords from embedded IPTC, but they don't document it. Every staged file is
already tagged, so upload one and check whether the form pre-populates.
**This single test decides whether the remaining 266 take two hours or twelve.**
Tell me the result either way — if it doesn't auto-fill, I'll produce a
copy-paste sheet ordered to match your upload sequence.

**Pricing that was applied** (markup per size tier, by shortest dimension — this
is how FAA actually models it, one markup across all print products at that size):

| Shortest edge | Markup | | Shortest edge | Markup |
|---|---|---|---|---|
| 8" | $12 | | 36" | $55 |
| 10" | $15 | | 40" | $65 |
| 12" | $18 | | 48" | $80 |
| 14" | $22 | | 60" | $100 |
| 16" | $26 | | 72" | $120 |
| 20" | $30 | | 84" | $140 |
| **24"** | **$35** | | 96" | $160 |
| 30" | $45 | | 108" | $180 |

FAA's defaults were $5–25, which isn't a business — a $5 markup on a $55 canvas
base is not worth the shelf space. The 24" tier is the anchor: a 24×36 canvas
(base $55.70) now retails at ~$91, competitive against decor sites, and one sale
recoups the $30 Premium fee. Raise to 55–65% on anything that sells twice.

**Note on disabling products:** FAA's Default Settings page has no on/off toggle —
only a markup field per product. Apparel, phone cases, shower curtains, towels,
and pillows are therefore still enabled at their default markups. FAA auto-centers
crops with no repositioning, so a 3:2 landscape on a phone case is unrecognizable.
Check for a per-product enable/disable control on the individual image page after
your first upload, and tell me if one exists.

**Other things worth knowing:**
- **Keywords are FAA's entire internal search.** Their FAQ states the search engine
  ignores titles completely. The keyword ordering in your files is already
  front-loaded with the highest-intent terms.
- **Location names are your best keywords** — geographic intent is how decor buyers
  search, and it's the one axis where you aren't competing with 580,000 artists.
- **Nothing is searchable for 24 hours** after upload. Don't debug on upload day.
- Bulk upload is weak: roughly **5 images at a time**, no CSV import, no API, no
  FTP. Plan several sessions rather than one marathon.
- Payouts: no minimum, sent the 15th monthly, but held through a 30-day return
  window — so a sale in mid-October pays out December 15.
- **Realistic expectation:** FAA is a checkout and fulfillment layer, not a demand
  channel. A new portfolio with no external audience typically earns $0–200 in
  year one. The seller earning ~$2,100/yr has 2,700 images, 14 years of tenure,
  and drives his own traffic.

### Step 7 — Dreamstime and Depositphotos *(set-and-forget)*
- https://www.dreamstime.com/sell-stock-photos-images
- https://depositphotos.com/seller-price.html
- Both take W-9, both support FTP. Decline any per-image exclusivity option.

### Step 8 — Optional / later
- **123RF** (https://www.123rf.com/contributors) — lowest priority; history of
  unannounced royalty cuts. Watch payments if you join.
- **Picfair Plus** (~$11/mo) — your own storefront; worth it once the agencies
  prove the portfolio sells.
- **Offset** — apply through your Shutterstock account once your port is live.
- **Pond5** — only if you start shooting video.

---

## After each signup, tell me

- Platform name and that the account is live
- Whether FTP/SFTP is available and where the credentials live (put the actual
  secrets in Keychain — don't paste them into chat)

Then I take over: per-platform metadata formatting, category mapping, editorial
captioning, CSV generation, and batch upload prep.

---

## Still outstanding (not blockers for signup)

- **GRUPH copyright registration** — $55, up to 750 photos, at eco.copyright.gov.
  Your title list is ready at `photo-licensing-workspace/copyright-title-list.csv`.
  Ideally filed *before* first upload; if the accounts go live first, file within
  90 days of first publication.
- **GSU outside-activity disclosure** — email ethics/compliance about whether the
  existing disclosure needs amending for the photography line. Draft is in
  `docs/photo-licensing/gsu-disclosure-email.md`.
