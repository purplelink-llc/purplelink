# Purplelink Daily Digest: a real paid subscription tier

**Status:** spec, not started · **Owner:** Ben · **Requested:** 2026-09-19, from
wanting genuine recurring MRR — everything currently sold (ModernTex, Paper
Review, the guides) is one-time or per-use. Chosen over a "Paper Review Pro"
subscription alternative because the Digest has real, proven organic demand
(`/blog/digest/` is the 4th-highest-traffic page on purplelink.llc) versus
zero Paper Review orders in the trailing 30 days.

---

## 0. What's real today — verified against the code, not assumed

- **Generation pipeline**: Modal app `purplelink-digest`, daily cron
  (`backend/digest/app.py`). `harvester.py` (~35 RSS/API sources) →
  `curator.py` (one Claude call; system prompt explicitly forbids mere
  summarization — "Do NOT summarize the abstract — add a perspective the
  abstract doesn't give") → `publisher.py`, which already has **separate**
  render functions for the web page (`render_html`, line 97) and the email
  (`render_email_html`, line 241) — this split already existing is what
  makes tier-specific footers straightforward, not something this spec has
  to build.
- **Subscriber capture/delivery, already fully working end-to-end, but
  single-tier and free**: `netlify/functions/subscribe.mjs` writes to a
  Netlify Blobs store; `subscribers-list.mjs` (Bearer-token gated) is pulled
  by `mailer.py`'s `_get_subscribers()`; `mail_digest()` sends via Resend
  through `_send_one()`; `unsubscribe.mjs` handles HMAC-signed opt-out
  links.
- **Zero billing code anywhere near this system** — confirmed by search.
  `netlify/functions/checkout.mjs`'s `PRODUCT_CATALOG` (line 77) has every
  Stripe session hardcoded to `mode: "payment"` (line 175) — one-time only,
  site-wide, for every product including Paper Review and ModernTex.
  `netlify/functions/stripe-webhook.mjs` subscribes to and handles exactly
  one event type, `checkout.session.completed` (line 297: everything else
  is 200-OK'd and dropped) — no subscription lifecycle handling exists at
  all today.
- **Copyright/fair-use**: researched separately this session and assessed
  low-risk. The pipeline never reproduces verbatim excerpts (confirmed: no
  blockquote markup anywhere in rendered output), always links to source
  with attribution, and is structurally close to how paid commentary
  newsletters (Stratechery, TLDR) already operate commercially without
  issue — contrasted against *AP v. Meltwater* (SDNY 2013), which lost
  specifically for verbatim excerpting with no real added commentary.
  Recommended before launch, not part of this spec: a real IP attorney
  review, and a pass over the ~35 regular sources' ToS for derivative-use
  restrictions.
- **Buy Me a Coffee**: a real, existing account, `buymeacoffee.com/bampel`,
  already linked (plain text, no badge image) from several tool pages
  (e.g. `site/tools/index.html:285`). No local badge asset exists yet.

---

## 1. Tiers

| Tier | Who | Delivery | Price |
|---|---|---|---|
| Web (unchanged) | Anyone | Same-day, public, indexed | Free |
| New free email | Anyone who signs up after launch | **3 days delayed** | Free, forever |
| Paid email | Stripe subscribers | Same-day (today's behavior) | $5/mo or $40/yr |
| Legacy free email | Everyone subscribed *before* launch | Same-day (unchanged from today) | Free, forever |

**Why delayed, not ad-supported, for the new free tier**: programmatic ad
networks (AdSense and similar) cannot serve inside email — mail clients
strip scripts and iframes for security, so there is no way to drop a live
ad unit into the newsletter itself. "Ad-supported" email in practice means
manually-sold sponsor placements (how Morning Brew/TLDR actually do it), a
sales effort worth pursuing later once subscriber volume justifies selling
a slot, not something to build now. The web archive already can and does
carry AdSense like the rest of the site.

**Why legacy subscribers get same-day, not the new tier's 3-day delay**:
they already have same-day delivery today. Downgrading people who already
have something free to get something worse-than-what-they-have is the
"you're taking away something free" complaint risk flagged earlier in this
conversation. Keeping them on same-day costs nothing extra to run (one
mailing-list entry either way) and avoids that risk entirely. This is a
judgment call, not something asked directly — flag if a different
grandfathering behavior was intended.

**3-day delay number**: a starting proposal, not derived from data (there
isn't any yet). Easy to change later — it's a single constant, not woven
through the architecture. Revisit once there's real free-vs-paid conversion
data to look at.

---

## 2. Data model

New fields on each subscriber's existing Netlify Blobs record (alongside
whatever `subscribe.mjs` already writes):

```
tier: "legacy" | "free" | "paid"
stripe_customer_id: string | null       # set on first successful paid checkout
stripe_subscription_id: string | null
last_sent_slug: string | null           # the most recent issue slug (YYYY-MM-DD)
                                         # actually delivered to this subscriber —
                                         # the idempotency guard described in §4
```

Every subscriber who exists in Blobs *before* this ships gets `tier:
"legacy"` in a one-time migration (a short script, not part of the daily
cron) run once at launch. Every subscriber created by the free signup form
after launch gets `tier: "free"`. `tier: "paid"` is only ever set by the
Stripe webhook, never by the signup form directly.

---

## 3. Billing

**`checkout.mjs`**: add a `mode` field to each `PRODUCT_CATALOG` entry,
defaulting to `"payment"` (zero behavior change for every existing
product — ModernTex, Paper Review, kits all keep working exactly as today).
Two new entries, `digest-monthly` and `digest-annual`, set `mode:
"subscription"` and point at two new Stripe Prices ($5/mo, $40/yr, both on
the same Product). Line 175's hardcoded `mode: "payment"` becomes
`mode: entry.mode || "payment"`.

**`stripe-webhook.mjs`**: two changes, not a rewrite.
1. Extend the existing `checkout.session.completed` handler: when
   `session.mode === "subscription"` and the product is one of the digest
   Prices, upsert (not create-blind — look up by email first, since this
   person may already have a `tier: "free"` or `"legacy"` Blobs record from
   signing up separately) the subscriber's record with `tier: "paid"`,
   `stripe_customer_id`, `stripe_subscription_id`.
2. Add one new handler, `customer.subscription.deleted`: look up the
   subscriber by `stripe_subscription_id`, set `tier: "free"` (not deleted
   from the list — a softer landing than being cut off entirely).

**Deliberately not building `invoice.payment_failed` handling.** Stripe's
own automatic retry/dunning process runs for roughly 2-3 weeks on a failed
renewal payment and only fires `customer.subscription.deleted` once it's
exhausted every retry. Reacting to that single terminal event is sufficient
and means the webhook doesn't need to track a separate "past_due" state or
grace-period logic of its own — Stripe already ran the grace period.

**Stripe Dashboard setup (manual, not code)**: the webhook endpoint needs
`customer.subscription.deleted` added to its subscribed-events list — right
now it's likely configured for only `checkout.session.completed`, matching
what the code actually handles.

---

## 4. Sending logic

`mailer.py`'s daily run changes from one send to two:

1. **Same-day send** (today's behavior, unchanged): today's issue, to every
   subscriber with `tier` in `{"paid", "legacy"}`.
2. **Delayed send** (new): the issue from 3 days ago, to every subscriber
   with `tier == "free"` **and** `last_sent_slug != that issue's slug`.
   After sending, set `last_sent_slug` to that slug.

The `last_sent_slug` check is the idempotency guard: if the daily cron
fails to run on a given day (it already has, per this session's own
run-log history for the traffic dashboard's cron), the next successful run
still finds every free-tier subscriber who's behind and catches them up
from wherever they actually are, rather than skipping a day or, worse,
resending an issue they already got.

---

## 5. Footer content (web + email templates)

Both `render_html` (web) and `render_email_html` (email) get a footer
block, but not the identical one:

- **Web and the new free (delayed) email**: the self-hosted BMAC badge
  (linking to `buymeacoffee.com/bampel`) plus a paid-tier upgrade CTA
  ("today's issue, every morning — $5/mo or $40/yr").
- **Paid-tier email**: neither — a plain "thanks for subscribing" line
  instead. Showing a paying subscriber an upgrade offer for the thing
  they're already paying for reads as not knowing who they are.
- **Legacy-tier email**: same as paid, since they already get the same-day
  experience free — showing them an upgrade CTA for something they already
  have for free would be confusing, not motivating.

This placement (who sees what) is a default I chose, not something asked
directly — flag it if a different split was intended, e.g. showing legacy
subscribers the upgrade CTA too as a way to convert some of them to paying
even though they don't functionally need to.

**BMAC badge asset**: self-host a copy of the official Buy Me a Coffee
button image under `site/assets/` rather than linking to their CDN — this
project's own design rules require self-hosting fonts and scripts rather
than third-party CDN loads, and the one existing exception (AdSense) was
explicit and owner-authorized, not a precedent to extend casually.

---

## 6. Account management

Stripe's hosted Customer Portal, not custom UI. A small new Netlify
function creates a portal session from `stripe_customer_id` and redirects;
the paid-tier email footer's "Manage subscription" link is a signed URL
(same HMAC pattern `unsubscribe.mjs` already uses) carrying enough to look
up the right customer without requiring a login system. Covers self-serve
cancel and payment-method updates entirely through Stripe's own page —
this resolves what would otherwise have been its own sub-project, so it's
folded into this spec rather than deferred.

---

## What's explicitly out of scope

- **Personalization** (per-subscriber topic mixes) — cut from v1 per this
  conversation's earlier decision. Revisit only if paying subscribers
  actually ask for it.
- **Ad-supported email** — not technically achievable the way "ad-supported"
  usually means (see §1). Manually-sold sponsorships are a future business
  decision, not an engineering task for this spec.
- **A login/account system beyond the Stripe Customer Portal** — the signed
  portal-link pattern covers the one thing that needed self-service
  (billing), without building general subscriber authentication.

## Tests

- Unit: `checkout.mjs`'s `mode` defaulting — every existing product key
  still produces `mode: "payment"` with no entry changes required; the two
  new digest keys produce `mode: "subscription"`.
- Unit: webhook's email-lookup-before-upsert logic, covering all three
  starting states (no existing record, existing `tier: "free"` record,
  existing `tier: "legacy"` record) all converging correctly to `tier:
  "paid"` with the Stripe IDs attached.
- Unit: `customer.subscription.deleted` handler demotes to `tier: "free"`,
  not deleted from Blobs entirely.
- Unit: the delayed-send idempotency guard — a fixture subscriber whose
  `last_sent_slug` is 2 issues behind catches up to exactly the correct
  (3-days-ago) issue on the next run, not the oldest unsent one and not
  today's.
- Live: after the Stripe Dashboard webhook-events change, a real (or
  Stripe-test-mode) subscription checkout end-to-end, confirming the
  Blobs record updates correctly before trusting it against a real
  customer.
