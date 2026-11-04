# Paper Review growth, weeks 1-4: metrics, first use, one landing page, an annual plan, labs CRM

Status: revised after EGM review, awaiting Ben's approval, 2026-11-04. Owner: Ben. Source: `Purplelink_Strategy_and_ROI_Analysis.pdf` (weeks 1-4).
Scope: build and draft only. Nothing goes outward (emails, posts, spend, Stripe settings) without Ben's yes.

## Concepts brief

**Problem.** Paper Review has almost no sales: 21 page views in 120 days as of 2026-10-09. Nobody can say where the
few visitors who arrive stop: at the free reference check, at checkout, or between payment and the first report. There
is also no record of what a review costs against what it earned, so pricing work has no footing. The strategy plan's
first month asks for three things:
- a baseline of the funnel and the unit economics;
- a cleaner path from upload to first result;
- one page that matches a researcher's search.

It then asks for an annual plan and a small pipeline of warm labs for interviews and pilots.

**Hypothesis.** Most of the loss is in two places:
1. The free check ends on a vague upsell, so few visitors go on to checkout.
2. After paying, small breaks lose people before they see the report: a 30-second payment wait, wrong 409 messages,
   jargon on the status page, and a status link that is not saved anywhere.

Fixing these two places, measuring them, and adding one page aimed at the confidentiality question will produce the
first readable funnel. A lab or a heavy individual user needs a yearly option that is cheaper per review than single
purchases.

**Success measures** (the plan's 90-day targets, read on the dashboard from the first scheduled build that publishes
this):

| Target | Value |
|---|---|
| Signups (purchases including free-code ones) | 100 |
| Activated | at least 40 |
| Repeat within 60 days | at least 15 |
| Pilots | 3 to 5 |
| Paid individuals | at least 10 |
| Paid lab | at least 1 |

Every metric below has a definition the dashboard computes the same way each day.

**Boundaries.**
- No new third-party script, no cookie, no tracking across sites.
- No new personal identifier is stored. Repeat buyers are counted with the salted hash `sales.mjs` already computes,
  and jobs join to orders by a hash of the Stripe session ID.
- No change to how manuscripts are processed or kept.
- No outreach is sent and no Stripe settings are changed.

## What exists (and what this touches)

- **Free check.**
  - `POST /paper-review/preview` (`backend/app.py`) runs the free reference and anonymity check on the landing page
    (`site/tools/paper-review/preview.js`).
  - It is rate limited: 5 per IP per hour, 20 per IP per day, and 300 a day for everyone.
  - Nothing is stored. There is no count of runs except the generic `tool_use`/`tool_outcome` beacons.
- **Purchase and token minting.**
  - Checkout runs `checkout.mjs` (`PRODUCT_CATALOG`) → Stripe → `stripe-webhook.mjs`, which forwards
    `{session_id, email, amount_paid, amount_subtotal, product, referral_code}` → `/paper-review/register-token`.
  - That endpoint mints `qty` tokens into `paper_tokens_dict` and stores `amount_paid`.
  - Single tokens expire in 7 days. Pack tokens never expire.
  - The entry is purged when it expires, so it is not a permanent record.
- **Per-job cost record.** `usage_ledger_dict` holds one permanent record per job: product, status, list price,
  token counts, `cost_usd`, models. It is keyed by `token[:16]_ts`. The price is the catalog price, not what was
  paid. A 100%-off `PRSTART` review therefore shows $11 of revenue.
- **First view.** `/paper-review/status` sets `delivered_at` the first time a finished report is served. That
  timestamp is the "viewed actionable findings" signal. It lives on the job entry, which is purged 30 minutes later.
- **Dashboard.**
  - `sales.mjs` (owner-only) already passes the backend's `/lifecycle/stats` through to the traffic dashboard.
  - The dashboard artifact is built outside the repo (`~/.purplelink/traffic/`).
  - The Marketing tab reads the hub's export (`scripts/hub/hub.py export`, data in `~/.purplelink/hub/`).

## Part A. Funnel and unit-economics instrumentation

The rule for this part: reuse what already records purchases, add only the missing joins, and compute everything in
the local dashboard script, not in a new public endpoint.

### What already exists and is reused

- **Orders.** `sales.mjs` (owner-only) returns a per-order `ledger` built from Stripe. It includes:
  - `cust`, a salted email hash already used for new versus returning buyers;
  - product, amount, the actual Stripe `fee`, `net`, `refunded`, `disputed`;
  - `attr` (first-touch channel) and `heard`.

  It excludes owner test purchases and counts 100%-off orders separately as `comps`. Signups, paid buyers, repeat
  buyers, refunds and channel all come from here. There is no new backend purchase store and no new email hash.
- **Jobs and model costs.** `usage_ledger_dict` holds one permanent record per job.
- **Reading the data.** `scripts/traffic-dashboard/traffic_dashboard.py` already reads the job ledger through
  `DurableDict` (`fetch_api_usage`), Modal compute cost per app, and `sales.mjs`.
- **Spend.** The hub already holds campaign spend (`hub.py campaign-spend`, `manual-ads.json`).

### Definitions

The dashboard computes each figure the same way every day, from the populations named.

| Metric | Numerator | Denominator / note |
|---|---|---|
| Free checks | successful `/paper-review/preview` runs per day (errors and rate-limited shown beside them) | new daily counters |
| Signups | Paper Review orders, paid plus comps, excluding owner tests and fully refunded orders | `sales.mjs` ledger |
| Activated | signups with at least one job that has `status ok` and a `viewed_at` within 7 days of the order | ÷ signups, by order week |
| Repeat (30/60 d) | activated buyers (`cust`) with a second viewed job, from any order, within 30/60 days of the first | ÷ activated buyers |
| Free-check → paid (upper-bound proxy) | paid orders flagged `pr_preview` | ÷ free checks in the same window. A device can carry the flag for 30 days, so read this as an upper bound. |
| Comp → paid | buyers whose first order was a comp and who later paid more than $0 within 60 days | ÷ those buyers |
| Cost per evaluation | model cost (`cost_usd`) of all jobs, failed included, plus the Paper Review share of Modal compute | ÷ jobs with `status ok`; also median and p90 of ok jobs |
| Revenue per evaluation | the order's `net ÷ qty` for the token used (cash basis; unused pack and annual tokens are not revenue per evaluation) | |
| Gross margin | (revenue − model and compute cost) ÷ revenue over paid jobs; comp jobs reported as promotion cost | |
| CAC by channel | (hub campaign spend for the channel + founder hours × $50 + promotion cost) ÷ new paid buyers whose first touch is that channel | hours come from Part E |
| CAC payback (months) | CAC ÷ (gross profit per paid buyer in their first 90 days ÷ 3) | |

**Before tracking.** Jobs that predate this change have no `purchase` field. They appear in a separate "before
tracking" row and are left out of activation and margin. Sales so far are close to zero, so nothing is backfilled.

**Sample size.** At current volume most rates have n below 10. The dashboard shows each rate with its counts
("3 of 7") and greys any rate with a denominator under 10.

### Data changes

1. **Job → order link** (`backend/app.py`).
   - The pipeline looks up the token's session through `paper_token_index_dict` and passes it on.
   - `_write_usage_ledger` then adds three fields:
     - `purchase`: `sha256(session_id)[:16]`, which `sales.mjs` computes for each order too;
     - `sold_as`: the purchased product key;
     - `attempt`: the attempt number for the token.
   - Today the ledger's `product_key` is derived from tier and journal (`app.py:640`), so a pack token logs as standard
     at $9. `sold_as` fixes that without touching the cost ceiling.
   - `_write_usage_ledger` returns its key, and the job entry stores it.
2. **First view.**
   - When `/paper-review/status` sets `delivered_at`, it also stamps `viewed_at` on the ledger record with that key.
   - The stamp is best-effort: wrapped, logged on failure, and never blocking the report.
   - The dashboard shows a "delivered, not stamped" count, so a gap shows up instead of hiding.
3. **Daily counters.**
   - `/paper-review/preview` bumps `preview:{day}:{ok|error|limited}` in a small `DurableDict`.
   - The dict is keyed per container plus day, and the dashboard sums the keys. That avoids lost increments when two
     containers write at once.
4. **Free-check flag.**
   - After a successful free check, `preview.js` stores the time in `localStorage` (`pl_pr_preview_at`, wrapped in
     try/catch).
   - `paper-review.js` sends `pr_preview: 1` when that time is under 30 days old.
   - `checkout.mjs` writes `metadata[pr_preview]` for Paper Review products and adds the flag to the idempotency-key
     hash (`checkout.mjs:447`). Otherwise a retry would reuse a key with new parameters and Stripe would reject it.
   - `sales.mjs` exposes the flag on each ledger order.
   - The flag holds no identifier, only a time.
5. **`sales.mjs`.** Each Paper Review order gains `purchase` (the same hash) and `pr_preview`.

### Dashboard

- **Funnel section.** `traffic_dashboard.py` gets a `paper_review_funnel()` function, unit-tested with fixtures. It
  joins the `sales.mjs` orders, the job ledger and the counters, and writes `paper_review_funnel.json`.
- **What the section shows.** A "Paper Review" section on the dashboard artifact shows:
  - the funnel: free checks → signups → activated → repeat → paid;
  - cost, revenue and margin per evaluation;
  - CAC and payback by channel;
  - progress toward the 90-day targets.

  The artifact is outside the repo, so it is backed up before it is edited.
- **Change log.** Each number-moving change is logged with `~/.purplelink/insights/changelog/log_change.py`.

### Stop rule

If there are fewer than 10 signups by day 30 (2026-12-04), stop adding instrumentation and spend the time on the
interviews in Part F. The funnel will not have enough data to read.

## Part B. First-use flow fixes

A code read of landing → free check → checkout → upload → status found twelve frictions. This change fixes the ones that
cost the most and are small.

1. **Free-check upsell** (`preview.js`).
   - Replace the unpunctuated line with a specific one: what the full review reads, that it takes 4 to 8 minutes, and
     that the file is uploaded again after paying.
   - Lead with the "not shown here: N more" line.
   - Add a link to the sample report.
   - Give the upsell button its own `checkout_click` meta (`<product>+preview`).
2. **Free check refused** (rate limit or busy): add a next step under the error, either the full review or the sample.
3. **Upload page 409 after the review has started.**
   - The backend returns `status_url` and a plain `detail` with the 409.
   - The page links to the status page instead of saying "use another token from your pack".
4. **Submit errors.**
   - A 409 on submit goes to the status page.
   - A 410 says the link expired and how to get it reissued.
   - A 429 says to wait a minute.
5. **Payment wait.**
   - Poll for about 90 seconds with backoff instead of 30.
   - Use calm copy: "Confirming your payment. This usually takes a few seconds."
   - On timeout show a "Check again" button and point to the start-link email.
   - Fire a `redeem_timeout` beacon so webhook trouble shows on the dashboard.
6. **Status page.**
   - Use the time estimate for the tier (Deep takes 10 to 15 minutes).
   - Use one deletion sentence everywhere, matching the backend: "The online copy can be opened again for 30 minutes
     after you first open it and is deleted within a day. The emailed PDF is yours to keep."
   - Plain stage labels: Read the paper, Check figures and references, Seven reviewers, Write the report.
7. **Status link saved.** After submit, the status URL is saved in `localStorage`. The landing and upload pages then
   show "Your review is running: open it" until the report has been viewed.
8. **Upload form.**
   - The decision reminder and the report-address override go into a "More options" `<details>`.
   - Pack, annual and direct-token visits require a report address, labelled "Where should we send the report?". The
     page repeats it back as "The report will be sent to …".
   - A Journal token with no journal chosen asks for confirmation before submitting.

Not in this change: the 300-a-day global free-check cap (no traffic yet presses on it) and keeping the file across a
failed-job redirect.

## Part C. One high-intent landing page

- **Page.** `/tools/paper-review/confidential-manuscript-review/`.
- **Query it answers.** "Which AI is safe for confidential pre-submission peer review?" Search Console shows that query
  verbatim, beside "ai manuscript review", "manuscript review ai" and "manuscript feedback tool". No existing page
  answers the confidentiality question on its own, and it is also the first question a lab or a security reviewer asks.
- **Content.** It states only what the architecture does:
  - who sees the manuscript: our server in memory, then Anthropic's API, which keeps inputs up to 30 days for abuse
    monitoring and does not train on them;
  - what Resend, Stripe and Netlify receive, and what they never receive;
  - when the copy is deleted;
  - what the cost record keeps;
  - what the page cannot promise: no on-premises option, and Anthropic's 30 days are Anthropic's. A data processing
    addendum, the subprocessor list and a HECVAT Lite are on request (as `/labs/` and `/security/` already say), not
    signed by default;
  - how this differs from pasting a draft into a chat assistant, whose retention and training settings depend on the
    user's account;
  - a short checklist for researchers: co-author consent, embargoed data, journal AI policy.
- **Calls to action.** It ends with the free check and the review button, using the same checkout as the main page.
- **Build.**
  - Follow DESIGN.md and impeccable: no emojis and no buzzwords.
  - Add FAQ structured data limited to the visible questions.
  - Link it from the main page's data-handling section and from the discipline pages.
  - Run `gen_og_cards.py --only tools/paper-review/confidential-manuscript-review`, then `fingerprint_assets.py` and
    both test suites. (Built: the card script covers only single-level `/tools/` pages with a generic image, so the
    page reuses `paper-review.png` like the four discipline pages.)

### Comparison figure: "Why not paste it into a chatbot?" (added 2026-11-04, Ben's request)

- **What it shows.** On the left, one chat prompt: one model, one pass, and the gaps that follow from that. On the
  right, the four stages Paper Review actually runs (`run_review_pipeline`). Stage 2 has four parallel lanes:
  database lookups (CrossRef, OpenAlex, Semantic Scholar), rule-based checks with no AI (statcheck, GRIM, citation
  matching, numbering), vision, and the seven-reviewer panel.
- **Fairness.** The figure has no logos and no product names on the left (Ben's choice). Each gap it lists is a plain
  fact about a single chat pass.
- **Where it appears.** The Paper Review page and the sample report page, from the seven-reviewer PR. In this
  landing page, the figure follows the data-handling section.
- **Styles.** `site/tools/paper-review/pipeline-compare.css`, using tokens only.
- **Outreach image.** The PNG for emails is private: `docs/growth-briefs/paper-review-pilots/paper-review-vs-chat-{dark,light}.png`.
- **Seven, not four.** The site said "four reviewers" while the pipeline runs seven personas on every tier, so the
  copy now says seven everywhere (Ben's choice). The published social card `assets/og/paper-review.png` still says four
  and is not re-rendered (logo rule).

## Part D. Annual plan, $79 a year, auto-renewing (revised 2026-11-04 after Ben's answers)

Ben's words: "Auto renewing annual for now, allow for referrals to give people free reviews (like 6 free reviews if
someone uses your referral code to buy an annual subscription). Please also make it embarrassingly easy to cancel a
subscription, and warn people when it's coming up, I don't want to be malicious here". Price: inline in `checkout.mjs`,
nothing created in Stripe.

**Offer.** "A year of reviews": 12 Paper Review Journal reviews a year, $79, renews yearly until cancelled.
- Each review is the standard tier with the journal check and the anonymity check (`bundled_journal`,
  `bundled_anonymity`). Deep reviews stay single purchases.
- Unused reviews do not roll over. Cancelling stops the next renewal and keeps this year's reviews until the year ends.

**Unit economics.** $6.58 a review against $11 single and $7.50 to $7.60 in packs. With every review used:
79 − 2.59 (Stripe) − 12 × 3.88 = $29.85, a 38% margin. A referral reward (below) costs 6 × 3.88 = $23.28 if fully used,
so a referred sale nets about $6.57 in its first year and $29.85 a year after that.

### Checkout
- `PRODUCT_CATALOG["paper-review-annual"] = { amount: 7900, interval: "year", mode: "subscription", successPath:
  "/tools/paper-review/packs/success/" }`, the same inline shape as `live-scholar`. If the env var
  `STRIPE_PRICE_PAPER_REVIEW_ANNUAL` is set, checkout uses that Price instead, so either answer to the price question
  works with the same code. No trial (the free first-review offers already cover trying it).
- `consent_collection[terms_of_service]=required`: the buyer ticks a box agreeing to the renewal terms. This is the
  affirmative consent auto-renewal laws expect.
- `custom_text[submit][message]` gets a new `REFUND_TEXT` entry (the test that matches it to `/terms/` is updated):
  "Renews at $79 a year on the same date until you cancel. Cancel in one click from any plan email. We email you 30
  and 7 days before each renewal. Unused reviews end with the year; cancelling stops the next charge and is not a
  refund for the current year." No computed date, so the idempotency key is unaffected.
- The same sentence sits beside the button on the Paper Review page, so the terms are visible before Stripe.
- The webhook's `PURPLELINK_PRODUCTS` set and Modal's `PAID_PRODUCTS` (qty 12) both gain `paper-review-annual`;
  without the first, the webhook drops the sale as a foreign product.

### Entitlement and renewal
How tokens work decides this. An entry holds a `tokens` list with permanent claims, not a count, and only `expires_at`
is checked at redeem and submit. So:
- **First purchase.** The webhook retrieves the subscription (period end lives on the subscription item) and forwards
  `subscription_id`, `term_ends_at`, `customer` and the first invoice's payment intent to register-token. If that
  Stripe call fails, the webhook returns 502 (Stripe retries) and sends the existing operator alert. `expires_at`
  stays 0 so the pack is kept on the Volume.
- **New check.** redeem-session, submit and the other `expires_at` call sites also refuse a token whose entry has a
  `term_ends_at` in the past or is `revoked`. Without this, unused tokens would work forever.
- **Renewal mints, it does not reset.** `/paper-review/annual-renew` (shared-secret header, like register-token) mints
  12 new tokens under `<session_id>#<period_end>`, removes the previous period's unused tokens from the token index,
  sets the new `term_ends_at`, and emails the new links with the renewal receipt. A claim on
  `subscription_id + period_end` in the claims dict makes it atomic, so two callers cannot both mint. It grants only
  when the latest invoice is `paid`.
- **Default trigger: `invoice.paid`** on the webhook, with `billing_reason = subscription_cycle`. This is the
  dependable path, and it posts the new year the moment Stripe charges.
- **Fallback: lazy.** If the plan page or the upload page finds Stripe's period end past the stored one, it calls the
  same endpoint. The claim makes a double call harmless.
- **Status changes:** `customer.subscription.updated` forwards `cancel_at_period_end` and status to Modal, so a cancel
  done in the Stripe portal is known. `customer.subscription.deleted` gets a Paper Review branch that marks the entry
  `ended` (today it falls through to the digest-subscriber loop). Failed payments: Stripe retries; nothing is granted
  while `past_due`.
- **Refunds and disputes.** A subscription session has no `payment_intent`, so the existing `recordRevocation` path
  cannot find it. The `charge.refunded` and `charge.dispute.created` handlers look up the charge's invoice, then its
  subscription, and call a new Modal `/paper-review/annual-revoke`, which sets `revoked` and drops unused tokens.
  Tested in both directions.
- **Lifecycle mail.** The existing tips, review-request and win-back sequence is not seeded for this product; a paying
  subscriber should not get win-back mail.

### Cancelling, made easy on purpose
- **One page, one button:** `/tools/paper-review/plan/?t=<token>` shows the renewal date, the price and "Cancel
  renewal". The button POSTs; a GET changes nothing (tested), because mail scanners prefetch links. Stripe is set to
  `cancel_at_period_end=true`, Modal is updated at once, and the page says "Cancelled. You keep your remaining reviews
  until <date>. Nothing more will be charged." "Undo" stays available until the period ends.
- **The token, sized to its job.** The repo removed permanent links once (`portal-link.mjs`) because a forwarded email
  gave away billing access. This token is narrower: it can only cancel or undo this one plan, and it shows no email,
  card or referral code. It expires after 60 days, carries a per-plan nonce (rotated on cancel, on each renewal, or on
  request, which revokes old links), and every plan email carries a fresh one. A forwarded email can cancel the
  renewal, which the owner can undo; the terms say so.
- **Confirmation email** on every cancel and undo, with the end date.
- **Without a token:** the plan page has an email box that sends a fresh link, with the enumeration-safe answer and
  rate limits of `subscription-portal.mjs`.
- **By reply:** every plan email says "or reply 'cancel'". Ben honours it within one business day, effective from the
  time of the reply; if a renewal charge lands in between, it is refunded. The terms say this.
- The Stripe billing portal (30-minute links, restricted config) stays the place for the card and invoices.

### Warnings before it renews
- A separate daily loop over plan entries in Modal (not the marketing lifecycle loop, which deletes opted-out
  entries). It sends at 30 and 7 days before the period end, with markers per period (`reminded_30`, `reminded_7`
  keyed on the period end), so a missed day sends late rather than never and a retry never sends twice.
- Before sending, it re-reads the subscription from Stripe: no reminder for a plan that is cancelled, ended or past due.
- Each says the date, the amount, how many reviews are unused and that they end with the year, the 14-day refund, and
  the one-click cancel link. They go even to people who opted out of marketing mail: they are about a charge.
- **14-day refund:** within 14 days of the first purchase or any renewal, if none of that period's reviews has been
  redeemed, a full refund on request. Ben refunds in the Stripe dashboard; a refund also cancels the renewal, and the
  revoke path above removes the tokens.

### Referrals (small v1)
- Reuse the existing referral system: each holder's code is the one `_paper_referral_code(email)` already makes, held
  in `referral_dict`, and `?ref=` already reaches checkout as `metadata[referral_code]`. No new store or format.
- `paper-review-annual` is excluded from the existing `.edu` single-review credit, so the two do not stack.
- Reward: **6 Journal reviews** for the referrer, issued as a normal pack token (no expiry) **14 days after** a
  referred annual payment, by the daily loop. Conditions:
  - the referred invoice actually paid $79 (no 100% promotion code) and was not refunded or disputed;
  - the referred buyer's normalised email (lowercase, `+tags` removed, Gmail dots removed) and card fingerprint differ
    from the referrer's;
  - one reward per referred buyer, at most 5 per referrer per year.
- The referred buyer gets nothing extra in v1, as Ben described. The cost record and the hub log each reward.

### Unit economics at low use
Most subscribers will not use all 12. At 4 reviews used the year costs 2.59 + 4 × 3.88 = $18.11 against $79 (77%
margin); at 12 it is 38%. A referred sale whose reward is fully used still nets about $6.57 in year one.

### Copy and terms
- Paper Review page: a fourth option, "A year of reviews: $79 a year, 12 Journal reviews, cancel in one click", with
  the renewal sentence beside the button. The packs page gets a row; the FAQ gets "How do I cancel?".
- `/terms/`: an auto-renewal section covering the price, the yearly renewal, both reminders, online cancel, reply
  cancel, that reviews end with the year and a mid-year cancel is not refunded beyond the 14-day rule, and that a
  forwarded plan email can cancel the renewal.

### Ben's actions
- **Stripe, live account (confirm through the parent session first):** add `invoice.paid` and
  `customer.subscription.updated` to the webhook endpoint `https://purplelink.llc/.netlify/functions/stripe-webhook`.
  Until then, the lazy path renews and the reminder loop's live Stripe check covers portal cancels.
- **Optional, only if the price question is answered "create a Price":** a Product and a yearly $79 Price, then
  `STRIPE_PRICE_PAPER_REVIEW_ANNUAL` in Netlify. Otherwise nothing is created.
- Owning reply-to-cancel within one business day.

## Part E. Labs and pilots in the marketing hub

Kept small until there are pilots to track.

- **Source file.** The hub database is rebuilt from its sources on every `import`, so the CRM gets its own private
  source file, `~/.purplelink/hub/crm.json`. It is never in the repo and holds:
  - `labs`: name, institution, field, PI, public URL, warmth, tie, status (prospect, contacted, interviewed, pilot,
    customer, dropped), next step and date, notes.
  - `people`: name, role, lab, roles (user, champion), `opted_out`. Contact details stay in Ben's mail, not here.
  - `pilots`: lab, start and end, reviews planned and used, terms version, status, outcome.
  - `opportunities`: lab, stage (lead, qualified, pilot, proposal, won, lost), value, and the six buying roles from the
    plan (user, champion, budget owner, procurement route, security reviewer, signer), each recorded as known or
    missing with a short note. Plus next step and date.
  - `hours`: date, channel or lab, hours, note. This feeds CAC.
- **Commands.** `hub.py crm add|set|list|hours|import-labs FILE.md`.
  - `list --due` shows next steps due and skips opted-out people.
  - Any name matching Georgia State or GSU is refused.
- **Export.** `hub.py import` loads the file into `crm_*` tables. `export` writes:
  - `marketing_crm_summary`: counts by status, and progress toward 3 to 5 pilots and 1 paid lab;
  - `marketing_labs`;
  - `marketing_pilots`;
  - `marketing_opps`, with buying roles shown as known or missing and never names.
- **Dashboard.** The Marketing tab gets a "Labs and pilots" section. The artifact is outside the repo, so it is backed
  up first.

## Part F. Private drafts (never committed)

All drafts go under `docs/growth-briefs/paper-review-pilots/` (git-ignored, mirrored to the private repo by its
`sync.sh`):

- `interview-script.md`: a 30-minute researcher interview covering the last submission, where review help came from,
  what was rejected and why, trust in AI review, the price anchor, and who pays.
- `pilot-terms.md`: a one-page pilot agreement covering:
  - scope (N manuscripts, 60 days, free);
  - authorization (only manuscripts the submitting researcher may share);
  - subprocessors (Anthropic, Modal, Netlify, Resend, Stripe);
  - retention and deletion as built;
  - no model training;
  - access control (owner-only, no human reads a manuscript unless asked for support);
  - security incident notice;
  - data ownership;
  - what we do not offer (no DPA template yet, no on-premises).
- `warm-labs-2026-11-04.md`: 30 to 50 labs with a real tie to Ben. Georgia State is excluded entirely.
- `outreach-drafts.md`: short first emails for Ben to send himself. Each has an accurate sender, the postal address,
  an opt-out line, and a note to check the suppression list (`opted_out` in the CRM) first.

## Delivery

| PR | Contents | Deploy |
|---|---|---|
| 1 | Part A (ledger link, `viewed_at`, counters, checkout flag, `sales.mjs` fields, dashboard function) and Part B | Modal deploy after merge; site waits for the scheduled build |
| 2 | Part D | Modal deploy; page waits for the slot |
| 3 | Part C | slot |
| 4 | Part E | none (local tool) |

- PRs 1 and 2 touch `backend/app.py` and land in order. PR 3 is independent.
- The dashboard artifact edits are local and go with PRs 1 and 4.
- No `[deploy now]`: nothing here blocks a customer today.

## Risks

- **Privacy.** No new personal identifier is stored.
  - The job ledger gains a hash of the Stripe session ID, which Stripe already holds.
  - The `localStorage` entry is a timestamp with no identifier.
  - The privacy policy gains one sentence on the `localStorage` entry.
- **Bearer tokens.** Annual tokens are bearer tokens shared on purpose. A refund or dispute revokes the unused ones
  through the new `revoked` flag. Tokens already used cannot be recalled.
- **Scan cost.** The ledger scan in the dashboard script reads only the last 180 days by `ts`.
- **Low n.** Every rate is shown with its counts, and the stop rule in Part A applies.

## Review findings and how they were resolved

The draft went to three EGM Goldfish reviewers on Sonnet (design, codebase accuracy, scope) on 2026-11-04.

| Finding | Resolution |
|---|---|
| Annual entry with `expires_at` loses Volume durability and is purged | `expires_at = 0`, `term_ends_at` checked in redeem and submit |
| "Journal tier" does not exist | standard tier plus `bundled_journal` |
| New purchase dict and email hash duplicate the `sales.mjs` ledger (`cust`, fee, refunds, comps, owner tests) | dropped; orders come from `sales.mjs`, jobs join by session hash |
| Ledger `product_key` is derived, not the purchased product | new `sold_as` and `purchase` fields |
| `pr_preview` breaks the checkout idempotency key | added to the hash |
| `viewed_at` second write can be lost silently | best-effort stamp plus a "delivered, not stamped" count |
| Refunds and disputes are not in the metrics; annual tokens cannot be revoked | refunded orders excluded; `revoked` flag via the refund path |
| D2 renewal needs far more than one handler | D2 out of scope |
| Metrics endpoint unnecessary; dashboard script already reads both sources | computed in `traffic_dashboard.py` |
| CRM over-built | trimmed to labs, people, pilots, opportunities and hours, with one list view |
| Signup definitions duplicated; free-check rate mislabeled | one table with explicit populations; labeled as an upper-bound proxy |
| Funnel too thin to read at this traffic | counts shown beside rates; day-30 stop rule; interviews in Part F |
| Counter increments race across containers | per-container keys summed on read |

Kept against the scope reviewer's advice:
- **CAC, payback and the CRM** stay, because the brief asked for them by name. They are thin layers on hub data that
  already exists.

### Second round, on the auto-renewing Part D (2026-11-04, two Sonnet reviewers)

| Finding | Resolution |
|---|---|
| Long-lived cancel token repeats the forwarded-link weakness `portal-link.mjs` fixed | cancel/undo only, no personal data shown, 60-day expiry, per-plan nonce, fresh token per email |
| "Reset the count to 12" does not match token lists; unused tokens never expire | renewal mints 12 new tokens per period; new `term_ends_at` and `revoked` checks at redeem and submit |
| Subscription sessions have no `payment_intent`, so refunds would not revoke | refund and dispute handlers map charge to invoice to subscription; new annual-revoke endpoint |
| Lazy renewal can double-mint or miss a period | atomic claim on subscription + period end; `invoice.paid` is now the default trigger, lazy is the fallback |
| Reminders read stale stored flags; opt-out loop deletes entries; no dedupe | own loop, per-period markers, live Stripe re-read before sending; `customer.subscription.updated` forwarded |
| Parallel referral system collides with `referral_dict` and the `.edu` credit | reuse `referral_dict`; annual excluded from the `.edu` credit |
| Referral abuse via promo codes, aliases, second cards | reward only on a paid $79 invoice, normalised email and card fingerprint checks, one per buyer |
| No affirmative consent; `<date>` cannot be filled in custom text | `consent_collection[terms_of_service]`; "on the same date" wording; text beside the button |
| Webhook drops the product; no subscription id or period end forwarded | product added to both catalogs; subscription retrieved with alert on failure |
| "Reply cancel" has no owner; no cancel confirmation | Ben, one business day, effective from the reply; confirmation email on cancel and undo |
| Lifecycle win-back mail would reach paying subscribers | not seeded for this product |
| 14-day refund undefined | first purchase and renewals; "none redeemed"; Ben refunds, which also cancels |
