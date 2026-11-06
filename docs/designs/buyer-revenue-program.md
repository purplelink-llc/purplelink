# Buyer revenue program

Status: approved by Ben 2026-11-05 (the six decisions below); this doc fixes the mechanics.
One PR per piece, in the order of the "Rollout" section.

The goal is more revenue from people who already bought, using only real prices and honest copy:
no timers, no fake scarcity, no pre-ticked boxes, no new marketing email, nothing sent to past buyers.

## Shared rules

- **One discount per order.** Every Checkout Session already sets `allow_promotion_codes=true`, and Stripe
  refuses `discounts[]` on the same session. When we apply our own coupon (cross-sell or friend), checkout.mjs
  drops `allow_promotion_codes`, so no typed code can stack on top. When a buyer has both a cross-sell code
  and a referral link, the larger discount (30%) wins and the referral is still recorded.
- **Never below cost.** Paper Review compute averages $3.88 a review (`docs/designs/paper-review-growth.md`).
  Discounts never apply to bundles, the suite, ModernTex seats, the sheet and calendar bundles (already
  discounted) or subscriptions (annual plan, Vitae Plus, live sheets). The worst remaining case is 30% off a
  Standard review: $6.30, less about $0.48 in Stripe fees, is $5.82 against $3.88 of compute.
- **Unsubscribe.** No new email is added. The codes ride on emails that are already sent (the delivery email)
  and on pages the buyer is already looking at. The one new email, a referral reward notice, delivers
  something the referrer earned (like the annual plan's reward email, which it copies); it is sent once per reward
  and not at all to an address in the follow-up suppression list.
- **Copy.** Plain and specific: the code, what it is worth, what it applies to, the date it ends.

## 1. Cross-sell code (30% off another product, 30 days)

- **When.** The webhook's `checkout.session.completed` handler, for a paid one-time order (`amount_total > 0`,
  mode `payment`), on both the Blob-delivered path and the Modal-forwarded path. A free order (100% code) gets
  no code.
- **What.** One Stripe **coupon** per buyer: `percent_off=30`, `duration=once`, `max_redemptions=1`,
  `redeem_by = purchase + 30 days`, id `xs-<code>`. We use a coupon, not a promotion code, so it cannot be typed
  into Stripe's box and used on a bundle. Stripe enforces single use and the end date itself.
- **Where it lives.** Netlify Blobs store `buyer-codes`: `code/<CODE>` →
  `{coupon, source_product, family, owned_parts, email_hash, created, expires}` and `session/<cs_id>` → `CODE`
  (which makes creation idempotent when Stripe retries the webhook). Codes look like `PL-7KQ2MX9D`
  (8 characters from a 31-letter alphabet with no 0/O/1/I/L).
- **Checkout.** checkout.mjs accepts `code` in the body. It is refused, with a plain reason, when it is
  unknown, past its date, for the same product family as the purchase that earned it (Paper Review tiers and
  packs are one family; photo licenses one; calendars one; everything else is its own), for an app the buyer
  already owns through a bundle, or for an excluded product (see Shared rules). Valid → `discounts[0][coupon]`,
  `metadata[buyer_code]`. The code joins the idempotency key.
- **Shown.** A new function `buyer-offers?session_id=cs_…` (rate limited, session must be paid) returns the
  code, its end date and the suggestions from piece 4. A shared `site/buyer-offers.js` renders it on every
  success page and on the Paper Review upload page. The Netlify delivery email (`emailDownloadLink`) gets one
  short paragraph; the Modal-sent emails (Paper Review, tools) get the same paragraph from a `buyer_code` field
  that the webhook adds to the register-token payload.
- **Product pages** read `?code=` from the URL and pass it to checkout, so the success-page links pre-fill it.

## 2. Referrals for all products

Modal stays the source of truth for referral codes (`referral_dict`, `_paper_referral_code`).

- **Every buyer gets a link.** The webhook asks Modal (`POST /referral/register`, shared webhook secret) for the
  buyer's code after every paid order and stores it in the `buyer-codes` record, so the success page and the
  delivery email can show `https://purplelink.llc/?ref=<code>`. Modal-path orders register inside register-token.
  Checkout also writes a Blobs mirror `ref/<code>` so it can validate a code without calling Modal; on a miss
  (codes minted before this program) it calls `GET /referral/check?code=` with a 2.5 s timeout and treats a
  failure as "no discount".
- **The friend's 20%.** One shared Stripe coupon `purplelink-friend-20` (`percent_off=20`, `duration=once`),
  applied by checkout.mjs when `ref` is a known code and the product is eligible: the Shared rules exclusions,
  plus list price under $7 (the $2 to $6 tools), where a 20% discount is cents and the reward could not pay
  for itself. The checkout page shows the discount; nothing else changes.
- **"First purchase"** cannot be checked when the session is created (we do not know the email yet), so it is
  enforced when the reward is decided: a reward needs the referred buyer's canonical email to have no earlier
  paid order in Modal's new `buyer_ledger_dict` (canonical email → first paid time, card fingerprints). The
  ledger is filled by every paid order from deploy day, and a one-off backfill (`backend/scripts/
  backfill_buyer_ledger.py`) lists the paid Checkout Sessions in Stripe so earlier buyers do not count as new.
- **The referrer's reward.** One Standard Paper Review token (no expiry, `source: "referral"`), issued by the
  daily loop 14 days after the referred sale, when all of these hold:
  - the referred order was paid, is not refunded or disputed, and paid at least **$15** after discounts
    (below that the reward costs more than the order earns: for example a $9 Standard review at 20% off is
    $7.20, minus fees and its own compute, which leaves less than a $3.88 reward);
  - it was the referred buyer's first paid order;
  - the referred and referring canonical emails differ, and the referred card fingerprint is not one the
    referrer has paid with;
  - this referred buyer has not already produced a reward in either system (shared key `referred:<canon>`,
    checked by this path and by `annual.reward_decision`);
  - the referrer has had fewer than 20 rewards in the last 365 days.
- **How it fits with the old rewards.**
  - The `.edu` $2 credit (`_credit_referral`, coupon `purplelink-referral-2usd`) stops for new orders. REFER-
    codes already issued keep working until their own expiry; the report footer changes to describe the new
    reward.
  - The annual plan keeps its own reward (6 Journal reviews per referred annual sale, `annual.py`) and never
    gets the friend discount. An annual sale never also earns a Standard token.
  - The `.edu` single-review credit and this reward never both fire for one order, because the first is
    removed.

## 3. Checkout reminder for every product

`RECOVERY_PRODUCTS` in `netlify/lib/checkout-recovery.mjs` grows from ModernTex to every one-time product
(subscriptions do not get Stripe's recovery URL). Same rules: Stripe's promotions consent box, one email, the
same price and no discount, 30 quiet days, no email to a buyer or a suppressed address. The email line becomes
per kind: apps keep "once, with updates included"; everything else says "once". `markBought` runs for every
product on both webhook paths. A test checks that each entry's cents equal checkout.mjs's inline amount or,
for env-priced products, `PAID_PRODUCTS` in `backend/app.py` and the price on the product page. The privacy
page paragraph "An unfinished ModernTex checkout" becomes "An unfinished checkout".

## 4. Thank-you page upsell

`buyer-offers` returns at most two suggestions for the product just bought, each with its normal price and the
price after the buyer's 30% code, linking to the product page with `?code=` filled in. Sales data cannot drive
this yet: the exports have no per-buyer link, and repeat buyers are a few dozen. So v1 is a hand-picked map in
`netlify/lib/upsell.mjs`, for example ModernTex → Paper Review Standard and the LaTeX sheets; Paper Review →
ModernTex and the response review; Outbound Veil → Legroom and Keyfeel. Suggestions skip anything the
buyer already owns from this order. Once `sales.mjs`'s ledger has 30 or more repeat buyers, the map can be
replaced by the observed pairs (follow-up, not in this program).

## 5. Paper Review upgrades

- **Journal check after a Standard review.** The Journal tier is a Standard review plus the journal compliance
  pass (`journals.check_compliance`, rule checks on the parsed structure). A new $2 product,
  `paper-review-journal-addon`, gives a token that runs only that pass: the buyer uploads the same PDF again
  (manuscripts are not kept) and picks the journal. It is offered on the finished Standard report page and in
  the report email for 14 days. $2 is the real difference ($11 − $9), and no model call is made, so there is no
  compute to cover.
- **Annual plan comparison after the second single review.** When a buyer's canonical email has two or more
  paid single reviews in the last 365 days, the report page and report email show their real spend and the
  plan's price, for example: "You have bought 2 single reviews this year for $20.00. The annual plan is $79 a
  year for 12 Journal reviews ($6.58 each)." The page says how much the plan would have saved only when the
  buyer's own spend in those 365 days is above $79, and then gives the exact difference. No projection.

## 6. Bundle nudge

On each app product page (Lenses included), under the buy button, one line: "Add any second Mac Suite app and save 25% on
both, or any third for 40% off all three." Since 2026-11-06 the bundles are percent tiers, so every pair saves and every
page gets the same line, with percents only and no dollar figure. The percents come from `site/suite/bundle.js`, which a
test keeps equal to `netlify/lib/bundles.mjs`. (Before that the line named only second apps that cost less than the fixed
$34.99 pick-2 price.)

## Rollout

1. This doc.
2. Checkout reminder for every product (Netlify only).
3. Cross-sell code: Stripe coupons, `buyer-codes`, checkout `code`, `buyer-offers`, success pages, emails
   (Netlify, plus a small Modal email change and deploy).
4. Referrals (Netlify and Modal, Modal deploy, Stripe coupon `purplelink-friend-20`, ledger backfill).
5. Thank-you upsell.
6. Paper Review upgrades (Modal and site).
7. Bundle nudge (site only).

Each number-moving change gets a `log_change.py` entry (area `pricing` or `site`) on the day it ships.

## How to measure

- Cross-sell: sessions with `metadata[buyer_code]` that were paid ÷ codes issued, and revenue from them, from
  `sales.mjs` (Stripe Checkout metadata).
- Referrals: paid sessions with `metadata[referral_code]`, rewards issued (Modal), and the reward cost at $3.88 each.
- Reminders: `checkout-recovery` store counts (sent, then a `bought` marker for the same email hash).
- Upsell and nudges: `track.mjs` click events on the offer links, and paid sessions that came with `?code=`.
- Paper Review: sales of `paper-review-journal-addon`, and annual plans bought by emails that saw the comparison.
