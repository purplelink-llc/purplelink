# Buddy's 20% code: one for anyone who asks, one by email

Status: v2, 2026-11-04, after an EGM review (three Sonnet Goldfish reviewers: design, implementation readiness,
scope; log at the end). Decided by Ben 2026-11-04 and built (see "Decisions" and "As built" at the end). Owner: Ben. Builds on
`docs/designs/buddy-chat.md`.

## Concepts brief

**Ask (Ben, 2026-11-04).** "Can you have buddy offer a 20% discount code if someone asks him for one? I feel like
that's likely to drive sales, a lil coupon." Then, choosing between the options offered: "Email for code and also
anyone who asks buddy for one gets a one time, expires in 10 minutes code".

**Two flows.**
1. **Ask:** a visitor asks Buddy for a discount and gets a single-use 20% code that expires 10 minutes later.
2. **Email:** a visitor gives an email address and is sent a single-use 20% code.

**Constraints already on record.**
- Studio rule 1 (Ben, 2026-10-17): "No price, trial or discount change on any product before 2027-01-12." Ben did not
  lift it when asking, so the codes switch on at 00:00 UTC on 2027-01-12 unless he says otherwise (decision 1).
- Buddy's guard rails (`buddy-chat.md`): the model grants nothing and never writes a code; offers are buttons the
  page draws from fixed rules and the server checks.
- The chat holdout runs 2026-12-28 to 2027-02-21. A coupon starting 2027-01-12 becomes part of the B arm (chat shown)
  from day 16; the read-out reports the two halves separately as well as together.

**Hypothesis and measure.** A small, time-boxed code turns some undecided visitors into buyers. Measured from
Stripe: codes issued and redeemed per flow, and orders and net revenue on the Mac apps in the 28 days after the
switch-on compared with the 28 days before (a before/after read, labelled as such; the holdout covers the chat as a
whole). Kill if redeemed codes are under 3 in 28 days, or if full-price Mac-app orders fall while coupon orders do not
make it up.

## What exists today

- `backend/app.py` holds `STRIPE_SECRET_KEY` (Modal secret `stripe-secret`, mounted on the web function) and already
  mints single-use promotion codes for referrals in `_mint_referral_promo_code`: `POST /v1/promotion_codes` with
  `promotion[type]=coupon`, `promotion[coupon]=<coupon id>`, `code`, `max_redemptions=1`, metadata. The coupon itself
  is made once by `backend/setup_referral_coupon.py`. This account's API version nests the coupon reference under
  `promotion[...]`.
- `netlify/functions/checkout.mjs` creates Checkout Sessions with `allow_promotion_codes: "true"`, so a buyer types a
  code on Stripe's page. `stripe-webhook.mjs` already handles discounted and 100%-off sessions; Paper Review's cost
  ceiling (`_order_cost_ceiling`) uses the list price, not the amount paid.
- Buddy: proof-of-work sessions, per-IP and global caps, strikes, the "no deals" reply screen (`_DEALS_RE`,
  `NO_DEALS_LINE`), the free-check email form with canonical addresses, a disposable-domain list, durable per-inbox
  claims (`_buddy_claims()`), HMAC keys from `BUDDY_FREE_SECRET`, and `scripts/buddy_flag.py`.

## Design

### 1. The coupon

- One Stripe coupon, id `buddy-20`: `percent_off=20`, `duration=once`, `applies_to[products]` = the Stripe products of
  the paid Mac apps and the Mac Suite (ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio, Panely, Summonly,
  Lenscrib, Née, Mac Suite). Not the paper tools, kits, sheets or bundles (decision 2). Made once by
  `backend/setup_buddy_coupon.py`, which reads the product ids from the prices named in `checkout.mjs`'s env keys.
- Every code is its own promotion code on that coupon: `BUDDY-` plus 6 characters from an alphabet without
  look-alikes, `max_redemptions=1`, and metadata `source` (`buddy-ask` or `buddy-email`) and `key` (an HMAC of the
  session or the address, never the address).

### 2. Ask flow

- **Recognising the ask, in code, before the model.** `/buddy/chat` checks the visitor's message against
  `COUPON_ASK_RE` (coupon, discount, promo or promotion code, voucher, a deal, cheaper, sale, "N% off"). On a match,
  and only while the coupon is live, the server answers without calling the model: "I can give you a one-time 20% code
  for our Mac apps. It works once and expires 10 minutes after I make it." with `offer: "coupon"`. The panel draws a
  **Get my code** button under it. Before the switch-on date, a match gets the existing `NO_DEALS_LINE`.
- **`POST /buddy/coupon`** (session required): flag on and coupon live; one code per session; 2 per IP a day; 40 a
  day site-wide (atomic slots, as the free check). It mints the promotion code with `expires_at` now plus 600
  seconds and returns `{code, expires_at}`.
- **Panel:** shows the code in a copy box with "Enter it at checkout under Add promotion code. It expires at 3:42
  pm." (local time from `expires_at`) and the product link for the page the visitor is on. No countdown animation.
- **What 10 minutes means:** Stripe checks `expires_at` when the code is applied on its checkout page; a session that
  applied it in time keeps it until the session is paid or expires (to be verified with a test-mode run before
  launch, see Build order).

### 3. Email flow

- A second button, **Email me a 20% code**, opens the same small form as the free check (email, honeypot, signed
  form stamp). One code per canonical inbox ever (durable claim key `coupon:<hmac>`), 3 per IP a day, 20 a day
  site-wide.
- It mints a promotion code with `expires_at` 72 hours later (decision 3) and sends it with a new template
  `coupon_code_html(code, expires)`. Over the per-inbox cap: the same success text, so addresses cannot be probed.
- No marketing list: the address is not added to any newsletter; that needs its own opt-in later.

### 4. Model and screen

- The model's prompt says Buddy has no codes and must point to the button; the "no deals" screen stays and still
  replaces any reply that writes a code or promises a discount, so the model can never hand one out.
- `NO_DEALS_LINE` while the coupon is live: "I can't write codes myself. The button below makes a one-time 20% code
  for our Mac apps." Before the switch-on: unchanged.

### 5. Switch-on and kill switch

- `COUPON_START = "2027-01-12"` in `latextools/buddy.py`; the server treats the coupon as live only from then and
  only while `buddy_dict["flag:coupon"]` is not False. `scripts/buddy_flag.py coupon off|on` turns it off in seconds.
  Already-issued codes stay valid until they expire; `setup_buddy_coupon.py --deactivate` turns the coupon off in
  Stripe if a code leaks.

### 6. Measurement and privacy

- Events: `coupon_offer` (the button shown), `coupon_issued` (meta `ask` or `email`). Redemptions come from Stripe:
  `scripts/buddy_coupon_report.py` lists promotion codes on `buddy-20` with `times_redeemed`, by `source`.
- Privacy policy, "Chat" paragraph: a code request stores an HMAC of the session or address, not the address; the
  email flow sends one email and keeps the address only in the sending log.

## Build order

1. `setup_buddy_coupon.py` in Stripe test mode; verify a 10-minute code applied at minute 9 still discounts a
   session paid at minute 15, and one applied at minute 11 is refused.
2. Server: ask detection, `/buddy/coupon`, email route, caps, flag, start date; tests for each cap, the start date,
   idempotency, the model never being called on an ask, and the screen.
3. Panel: button, code box, email form; tests.
4. Live-mode coupon created by Ben's yes; backend deploy; the site change at a scheduled build.

## Decisions for Ben

1. **Start:** 2027-01-12 (keeps studio rule 1) or earlier.
2. **Products:** the paid Mac apps and the Suite only, or also the paper tools and kits.
3. **Email code expiry:** 72 hours, or another length.

## v2: what the review changed

The sections above are v1. Where they differ, this section wins.

**Products (was section 1).** Two reviewers found the same blocker: only Outbound Veil and Legroom reach checkout as a
stable Stripe Price. ModernTex, Keyfeel, Tapefolio, Lenscrib, Née, Panely, Summonly and the Suite are priced inline
(`price_data` with `product_data[name]`), so Stripe makes a new product per session and `applies_to[products]` would
match almost nothing. Two ways out, decision 2:
- (a) **No product limit.** The coupon takes 20% off any order, paper tools, kits, sheets, bundles and the first
  payment of Vitae Plus included. No change to the live checkout. Paper Review's cost ceiling is unaffected (it uses
  the list price).
- (b) **Mac apps and the Suite only.** `checkout.mjs` gets one stable Stripe Product id per inline app
  (`price_data[product]=prod_...`, made once by `setup_buddy_coupon.py`), a checkout test asserts it for each key,
  and the coupon carries `applies_to[products]` with those ids plus the two Prices' products. A change to the live
  checkout path, tested end to end in test mode first.

**The 10-minute promise (was section 2).** Stripe checks a promotion code's `expires_at` when it is entered on the
checkout page; a code entered in time stays on that Checkout Session until it is paid or expires (Checkout Sessions
last at least 30 minutes). So the true promise is "enter it at checkout within 10 minutes", and the panel says so:
"Your code: BUDDY-7KQ4MX. Enter it at checkout under Add promotion code within 10 minutes (until 3:42 pm). It works
once." `max_redemptions=1` counts a redemption only when a session is paid.

**Ask detection (was section 2).** On the visitor's last message only, case-insensitive:
`\b(coupon|promo(?:tion)?\s*code|discount(?:\s*code)?|voucher|\d{1,3}\s*%\s*off|student\s+discount|on\s+sale|any\s+deals?)\b`.
Not "cheaper", "sale", "sales" or "deal" alone ("is it cheaper than Overleaf?", "what's the sales tax?",
"a deal-breaker" stay with the model). A table test of 15 asks and 15 non-asks, including the page buttons ("What
does ModernTex cost?"). An ask is answered after the origin, session, per-IP and global-message checks, before the
model and the spend reservation, and does not count toward the 20-turn limit. The offer is never shown unasked.

**Routes and caps (was sections 2 and 3).**
- `/buddy/status` adds `coupon: true|false` so the panel draws the buttons only while it is live.
- `POST /buddy/coupon` `{session}` returns `{ok: true, code, expires_at}` (epoch seconds) or `{ok: false, message}`,
  HTTP 200; no session is 401. One code per session (`buddy_dict.put("coupon:s:<sid>", code, skip_if_exists=True)`;
  a repeat returns the same code), 2 per IP a day (`_buddy_ip_ok`, bucket `buddy-coupon`).
- `POST /buddy/coupon-email` `{session, email, website, form_ts}`: one per canonical inbox ever (durable claim
  `coupon:<hmac>` with its own HMAC purpose, `"coupon:" + address`, so it can never equal a free-check key), 3 per IP
  a day, the same reply text whatever happens ("If that address can get a code, it is on its way.").
- No site-wide issuance caps: an unredeemed code costs nothing. Exposure is capped in Stripe instead: the coupon
  carries `max_redemptions=100` in all, and the kill switch stops issuing at once.
- Minting is a new shared `_mint_promo(client, coupon_id, prefix, expires_at, metadata)` (the referral function is
  left as it is). On a Stripe error or a duplicate code: one retry with a new code, then "I could not make a code just
  now. Try again in a minute." and the claims are released. The email is sent only after a code exists.
- Live check: `coupon_live(now)` is `now >= COUPON_START_EPOCH` (UTC) and `buddy_dict.get("flag:coupon", True) is not
  False`, false if the Dict cannot be read. `scripts/buddy_flag.py coupon on|off` and `status` show it.

**Screen and prompt (was section 4).** The model is told it has no codes and that the button makes one. The "no
deals" screen is unchanged and still replaces any model reply that writes or promises a code. While live,
`NO_DEALS_LINE` reads "I can't write codes myself. Ask me for a code and I'll show the button that makes a one-time
20% code." Changing the prompt regenerates the assets `test_generated_assets_are_current` checks.

**Measurement (was the brief and section 6).** At about 90 visitors a day a 28-day before/after read cannot show a
lift, so it is reported as a description only. What decides:
- `stripe-webhook.mjs` records the promotion code and its `source` metadata on the order (from the session's
  discounts), so redemptions are counted from orders, not from codes.
- **Kill** at the 8-week review if fewer than 3 codes were redeemed, or if most redemptions came from visitors who had
  already clicked a buy button before asking (the same visitor id's `checkout_click` earlier that day), which would
  mean the code mostly discounts people who were buying anyway.
- Net revenue per redeemed code (after the discount and Stripe's fee) is reported with it.
- No report script: the Stripe dashboard lists the coupon's promotion codes and redemptions.

**Start (decision 1) and the holdout.** The chat holdout runs 2026-12-28 to 2027-02-21. A coupon that starts inside
it makes the B days "chat plus a code" from that day on, which the holdout cannot separate at this traffic. Starting
on 2027-02-22, the day after the holdout ends, keeps the holdout clean and also keeps studio rule 1.

**Email flow (decision 3).** The scope reviewer pointed out that a 72-hour emailed code makes the 10-minute ask code
pointless for anyone who notices the second button. Ben asked for both, so both stay, and the email code's life is
his call: 24 hours keeps the two closer.

**Privacy.** The privacy paragraph says: a code request keeps an HMAC of the session or address; the emailed code's
address also passes through the email provider and its logs, and Stripe keeps the buyer's email on any order as
today.

### Decisions for Ben (v2)

1. **Start:** 2027-02-22, after the holdout (recommended); 2027-01-12, when the price hold ends; or now.
2. **Products:** (a) every product, no checkout change (recommended, simplest); or (b) Mac apps and the Suite only,
   which changes the live checkout.
3. **Email code life:** 24 hours (recommended) or 72 hours.

### Review log (v1, 2026-11-04)

- **Design (10 findings, 2 blockers):** inline-priced products defeat `applies_to` (now decision 2); the 10-minute
  promise did not match Stripe's expiry semantics (copy fixed); per-IP caps versus session caps were unclear (fixed);
  site-wide caps were farmable into an outage (dropped, Stripe-side redemption cap instead); orders did not record the
  code (webhook records it); the before/after read was confounded (decision 1, descriptive only); the regex was too
  broad (narrowed); the privacy claim was wrong (fixed).
- **Implementation readiness (2 blockers, 6 major):** product ids (decision 2); time source and live check (defined);
  regex, route shapes, cap keys and an HMAC collision with free-check claims (defined); Stripe failure handling and a
  shared mint function (defined); `/buddy/status` flag (added); prompt regeneration step (named).
- **Scope (3 major):** the two flows undercut each other (decision 3); the coupon would contaminate the holdout
  (decision 1); the kill rule could not detect a pure discount to existing buyers (cannibalisation check added);
  site-wide caps and the report script were not needed (dropped); a shared code would be worse (kept one per visitor).

## Decisions (Ben, 2026-11-04)

1. **Start: now.** Chosen over 2027-02-22 and 2027-01-12, knowing it sets aside studio rule 1 (no discount before
   2027-01-12) for this offer and that the chat holdout (2026-12-28 to 2027-02-21) then measures the chat with the
   code included.
2. **Products: every product**, so the live checkout does not change.
3. **Emailed code: 24 hours.**

## As built (2026-11-04), where it differs from v2

- **Off until switched on.** `buddy_dict["flag:coupon"]` defaults to off, not on: codes can only go out after
  `modal run setup_buddy_coupon.py` has made the `buddy-20` coupon (20% off, once, any product, at most 100
  redemptions) and `scripts/buddy_flag.py coupon on` has run. `coupon_live()` also needs the chat on and the Stripe
  key set, and fails closed. There is no start date in code.
- **Measurement without touching the webhook.** Stripe already counts redemptions per promotion code
  (`times_redeemed`), so the 8-week read lists the coupon's codes in the Stripe dashboard, by `source`
  metadata. The "were they buying anyway" check uses the
  analytics events: a visitor's `coupon_issued` (ask) or `coupon_requested` (email) against a `checkout_click` by the
  same visitor id earlier that day. `stripe-webhook.mjs` is unchanged.
- **The emailed-code claim** is `claim:coupon:<hmac>` (purpose `"coupon:" + address`), so `_buddy_claims()` keeps a
  durable copy past the Dict's 7-day expiry and it can never equal a free-check `claim:<hmac>`.
- **The opening line** drops "I can't give discounts" (it would now be false) and keeps "I can't look up an order".
  The offer is never shown unasked.
- **A model reply that writes a code** is still replaced; while the coupon is live the replacement is the live line
  pointing to the button.
- **Tests:** `backend/tests/test_buddy.py`: 15 asks and 15 non-asks; an ask is answered without the model and is not
  counted; the code's Stripe parameters (coupon, single use, 10-minute expiry, metadata without the session); one code
  per session; 2 per address a day; a Stripe failure retries once and frees the session; flag off; the emailed code
  once per inbox, 24 hours, its claim key, no collision with the free check, honeypot and disposable addresses; a
  model reply with a code becomes the live line.
