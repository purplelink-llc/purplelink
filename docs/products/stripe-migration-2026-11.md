# Stripe migration: off the Buy Me a Coffee-controlled account (2026-11)

Goal: take checkout off `acct_1Tnewb…`, which Buy Me a Coffee controls, and onto a new Stripe account that Purplelink LLC
controls directly, so Stripe Managed Payments (Stripe as merchant of record for VAT, GST and US sales tax) can be switched on.
Managed Payments is blocked on every platform-controlled account (Buy Me a Coffee, ExtensionPay, Gumroad, Payhip), so a new
account in the existing Purplelink LLC organization is the only route. Ben creates the account and its keys himself.

This PR changes no live behavior. Everything below is behind env vars that are unset today.

## What is in the PR

| Piece | File |
| --- | --- |
| Two-account helper | `netlify/lib/stripe-account.mjs` |
| Catalog migration script | `scripts/stripe_catalog_migrate.mjs` |
| Tests | `netlify/tests/stripe-account.test.mjs` |
| Wiring | `checkout.mjs`, `stripe-webhook.mjs`, `purchase-license.mjs`, `purchases-recover.mjs`, the 12 `*-download.mjs` functions |

### New env vars (all unset; set in Netlify production at cutover)

| Name | Meaning |
| --- | --- |
| `STRIPE_SECRET_KEY_NEW` | `sk_live_…` of the new account. |
| `STRIPE_WEBHOOK_SECRET_NEW` | `whsec_…` of the new account's webhook endpoint (same URL, `/.netlify/functions/stripe-webhook`). |
| `STRIPE_NEW_ACCOUNT` | `on` makes new Checkout Sessions use the new account. Off or unset: sessions stay on the old account. |
| `STRIPE_PRICE_*_NEW` | One per `STRIPE_PRICE_*` env var (21 of them). Read instead of the old name while the flag is on. The migration script prints them. |

`STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` stay as they are, forever: they are the old account.

### How routing works

- **Creating a session** (`checkout.mjs`): new key and `<envKey>_NEW` Price ids only while `STRIPE_NEW_ACCOUNT` is on and the new key is set. A missing `_NEW` Price is a 500 `misconfigured`, never the old account's Price id (that Price does not exist in the new account). Inline-priced products need no Price.
- **Reading a session** (the 12 download functions, `purchase-license`): `stripeFetchAny` tries the new key first, then the old one. Stripe answers 404 for an object that lives in the other account, so an old buyer's `cs_live_…` link falls through to the old key and still delivers. With no new key set it makes the same single call it made before.
- **Webhook**: accepts either account's signature. The secret that verified the event picks the key used for the follow-up Stripe calls in that request (per-request `AsyncLocalStorage`, so concurrent events cannot mix).
- **Find a purchase** (`purchases-recover.mjs`): lists checkout sessions by email in each account in turn, because a list is a 200 with no rows, not a 404.
- **`FOLLOWUP_UNSUBSCRIBE_SECRET`**: the unsubscribe HMAC falls back to `STRIPE_WEBHOOK_SECRET`. The fallback now reads the old secret explicitly, so adding the new secret never changes existing unsubscribe links. Pin `FOLLOWUP_UNSUBSCRIBE_SECRET` anyway before any future rotation of the old secret.

### Converted in the second PR

Every reader now looks in the new account first and then the old one (objects by id fall through a 404; lists are read once per account and merged):

- Vitae Plus: `vitae-license.mjs` (activation, refresh, manage, recover by email, billing portal), `portal-link.mjs`, `subscription-portal.mjs`, `live-sheet.mjs`, `unsubscribe.mjs`. A billing portal configuration belongs to one account, so the new account reads `STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS_NEW` and `STRIPE_PORTAL_CONFIG_VITAE_PLUS_NEW`, or creates and caches its own.
- Trial and reminder buyer checks (`trial-reminder.mjs` and `outbound-veil-reminder.mjs`): a buyer in either account is a buyer; an unreadable account means unknown, so the run skips that address.
- `sales.mjs` (including balance), `delivery-health.mjs`, `post-purchase-followup.mjs`: lists from both accounts, merged.
- Modal backend (`backend/stripe_account.py`, `app.py`, `monthly_guide/app.py`): see the backend section below.

Left as is on purpose: `scripts/stripe-mp-smoke.mjs`, `scripts/stripe_addon_prices.mjs`, `scripts/vitae-weekly-report.mjs` and the `backend/setup_*.py` one-offs read `STRIPE_SECRET_KEY` from the environment. Run them with the new account's key exported as `STRIPE_SECRET_KEY` when they are meant for the new account.

## Inventory

### Where `STRIPE_SECRET_KEY` is read

About 100 occurrences, no shared helper before this PR.

- Netlify functions (30): checkout, stripe-webhook, delivery-health, purchase-license, purchases-recover, sales, live-sheet, post-purchase-followup, unsubscribe, subscription-portal, vitae-license, the per-app download functions (keyfeel, kit, legroom, lenscrib, lenses, moderntex, nee, outbound-veil, panely, photo, summonly, tapefolio) and the six reminder functions.
- Netlify lib: `portal-link.mjs`, `trial-reminder.mjs`.
- Backend (Modal, secret `stripe-secret`): `backend/app.py`, `backend/monthly_guide/app.py`, `setup_buddy_coupon.py`, `setup_early_reviewer_coupon.py`, `setup_referral_coupon.py`, `setup_resume_review_price.py`.
- Scripts: `stripe-mp-smoke.mjs`, `stripe_addon_prices.mjs`, `vitae-weekly-report.mjs`.
- Separate platform, not part of this move: `STRIPE_EXTPAY_KEY` (ExtensionPay, Scholar Utility Belt Pro).

### Webhook

- One endpoint, `stripe-webhook.mjs`. Signature check is a hand-rolled HMAC (`verifyStripeSignature`), 5-minute tolerance, multiple `v1` values allowed.
- Create a second endpoint in the new account with the same URL and the same event list as the old one (`checkout.session.completed`, `checkout.session.expired`, `charge.refunded`, `charge.dispute.created`, `charge.dispute.closed`, `customer.subscription.updated`, `customer.subscription.deleted`), copy its signing secret to `STRIPE_WEBHOOK_SECRET_NEW`. Confirm the old endpoint's list in the old dashboard first; the code is the authority on what it handles.
- Keep the old endpoint enabled: refunds and disputes on old charges still arrive there.

### Hardcoded ids

Almost nothing is hardcoded in code; ids live in Netlify env.

- `prod_VZncC6arvZzEdp` (Lenses) in a comment in `netlify/functions/checkout.mjs`; `STRIPE_PRICE_LENSES` is the live pointer.
- Docs only: `docs/agent-context.md`, `docs/products/{moderntex,legroom,outbound-veil,lenses,kits-activation,template-tier-activation}.md` carry `acct_1Tnewb…`, `prod_…` and `price_…` ids. They describe the old account and stay true as history; add the new ids next to them at cutover.
- Test fixtures (`paper-review-annual.test.mjs`, `checkout-addon.test.mjs`) use ids as inert strings.
- Counts from the scan: 6 `acct_`, 18 `price_` (including `XXXX` placeholders), 8 `prod_` references.

### Prices

- Env Prices (21 names read by `checkout.mjs`): `STRIPE_PRICE_` + `MODERNTEX`, `LEGROOM`, `LENSES`, `OUTBOUND_VEIL`, `PAPER_REVIEW_STANDARD / DEEP / JOURNAL / PACK_5 / PACK_20 / ANNUAL`, `RESEARCH_REVIEW_2026_07`, `COVER_LETTER`, `ANONYMITY_CHECK`, `CITATION_GAP`, `REVISION_REVIEW`, `RESPONSE_REVIEW`, `RESUME_REVIEW`, `KIT_CLIP / MONETIZATION / FACELESS / BUNDLE`, `VITAE_PLUS_MONTHLY`, `VITAE_PLUS_ANNUAL`. The migration script clones each from the old account's live Price (read only) with lookup key `pl_<name>`.
- Inline-priced (amount sent with the session, nothing to create): ModernTex, `moderntex-seats` (`seats.mjs`), journal-check, and the Mac apps. Lenses and ModernTex also accept an env Price that wins when set.
- Add-ons: `addon_<slug>_25`, one-time USD, 75% of the app price, found at runtime by lookup key (`netlify/lib/addons.mjs`, 5-minute cache). The migration script creates them in the new account the same way `scripts/stripe_addon_prices.mjs` does. Until they exist there, checkout with the flag on has no add-on suggestions (it degrades quietly).

### Promo codes and coupons

Coupons and promotion codes belong to an account. None move. Recreate in the new account before cutover:

- Referral coupon `purplelink-referral-2usd` ($2 off) and minted promotion codes (`backend/setup_referral_coupon.py`, `_mint_referral_promo_code` in `backend/app.py`).
- Buddy coupon (`backend/setup_buddy_coupon.py`), early-reviewer coupon (`setup_early_reviewer_coupon.py`, needs the new `prod_` ids), buyer codes (`netlify/lib/buyer-codes.mjs`), fixed-discount handling in `checkout.mjs`.
- Codes already handed to people (buyer codes, referral codes) point at old-account coupons: after cutover they fail on new-account sessions. Decide: re-mint, or keep the flag off for the products that sell with them until they expire.

### Billing portal

`STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS` and `STRIPE_PORTAL_CONFIG_VITAE_PLUS` hold `bpc_…` configuration ids from the old account. A portal configuration cannot be shared; create the same configuration in the new account (cancel at period end, no plan switching, same return URL) and set new ids. `subscription-portal.mjs` and `portal-link.mjs` also need the two-key fallback (list above).

### Vitae Plus subscription path

`vitae-license.mjs` reads the subscription from the checkout session, derives the plan from the Price, and issues `VP2-…` keys; recovery looks up the customer by email; the portal opens through `portal-link.mjs`.

Live subscriptions cannot be repointed. Customers, subscriptions and saved payment methods do not move between Stripe accounts unless Stripe runs a data migration (support request, card data moves only with the PAN-copy process). Options for Ben:

1. Leave existing subscribers on the old account until they cancel or renew; new subscribers go to the new account. Needs the two-key fallback on `vitae-license`, `subscription-portal`, `trial-reminder` and the webhook (done) so both populations work. Lowest risk.
2. Ask Stripe for a data migration and move everyone on a set date. Cleaner, slower, needs Stripe's cooperation.
3. Cancel and re-subscribe everyone. Not recommended.

### Purchase recovery, Find a purchase, refunds

- **Past buyers need the old key forever.** Their `cs_live_…` links, charges, payment intents and refunds exist only there. Do not rotate or delete `STRIPE_SECRET_KEY`.
- Download links, `purchase-license`, and Find a purchase now try both accounts (this PR). Refund and dispute events for old charges arrive at the old endpoint, which stays enabled; `netlify/lib/refunds.mjs` records them in Blobs keyed by payment intent, and revocation checks read that store, so they are account-agnostic.
- Issuing a refund by hand: use the dashboard of whichever account holds the charge. Add the new dashboard to the support runbook.
- The Buy Me a Coffee-controlled account may restrict what the owner can do (payouts, exports). Pull the full charge and customer export from the old dashboard before cutover so the books and tax records stay whole. Binnacle imports should expect charges from two accounts.

### Managed Payments requirements

Already built and off (`netlify/lib/managed-payments.mjs`, `STRIPE_MANAGED_PAYMENTS` unset in every context):

- Enable Managed Payments and accept its terms in the new account, in test and in live separately. API version `2025-03-31.basil` or later.
- Tax codes: `txcd_10202000` (downloadable software, personal use) for the Mac apps, Outbound Veil and Legroom; `txcd_10202003` (business use) for `moderntex-seats`. Inline prices get the code from `applyManagedPayments`. Products sold through a Stripe Price need the code on the Stripe product in each mode: run the migration script with `--tax-codes`, or `scripts/stripe-mp-tax-codes.mjs`.
- Managed Payments removes `payment_method_types`, `automatic_tax`, `tax_id_collection`, `invoice_creation`, `payment_intent_data[receipt_email]` and statement descriptors. Those are stripped automatically.
- Smoke test: `scripts/stripe-mp-smoke.mjs` with the new account's test key (it refuses non-test keys).
- Stripe, not Purplelink, becomes the seller of record to the buyer. Stripe's fee for Managed Payments is higher than plain checkout; read the current rate before turning it on.

## Cutover order (nothing here has been run)

1. Ben creates the new account under the Purplelink LLC organization, enables Managed Payments in test, stores keys: test key in keychain service `stripe-test-secret` (account `purplelink`), later the live key in `stripe-live-secret-new`.
2. `node scripts/stripe_catalog_migrate.mjs --dry-run`, then without `--dry-run`, then `node scripts/stripe-mp-smoke.mjs` with the new test key. Everything is test mode, nothing live.
3. Done in the second PR (readers converted). Still to do by hand in the new account: recreate coupons (below) and, optionally, the portal configurations (they are created on first use otherwise).
4. Accept Managed Payments terms in live. `node scripts/stripe_catalog_migrate.mjs --live --tax-codes`. Create the live webhook endpoint.
5. In Netlify production set `STRIPE_SECRET_KEY_NEW`, `STRIPE_WEBHOOK_SECRET_NEW`, every `STRIPE_PRICE_*_NEW`. Flag still off. Place one real order on the old account to confirm nothing changed; check old and new session links both deliver.
6. Set `STRIPE_NEW_ACCOUNT=on`, then `STRIPE_MANAGED_PAYMENTS=all` (or product by product). Place one real order per product family; refund each from the new dashboard. Netlify functions read env from the deploy, so each env change reaches them with the next site build (06:00 and 17:00 ET); do not use `[deploy now]` for this unless checkout is broken.
7. Rollback: unset `STRIPE_NEW_ACCOUNT`. New sessions return to the old account; orders already placed on the new account still resolve through the two-key fallback.

## Decisions for Ben

1. **Tax-inclusive or tax-added.** Under Managed Payments, either the listed price includes tax (you keep less in high-tax regions, buyers see the same price) or tax is added at checkout (you keep the listed price, EU and UK buyers pay more than the price on the page). The site's copy and the 12-06 price read both depend on this.
2. **Vitae Plus subscribers.** Option 1 (leave in place, new ones on the new account), 2 (Stripe data migration) or 3 (re-subscribe).
3. **Cutover date.** After the 12-06 price read (scheduled task `managed-payments-switch-2026-12-07`), outside a launch week, early morning ET.
4. **Outstanding codes.** Re-mint buyer and referral codes in the new account, or hold them back until they expire.

## MuscleOnGLP (getmuscleonglp.com), ported 2026-11-07

Separate Netlify site and repo (purplelink-llc/muscleonglp), so it has its own env. Same two-key pattern as above, different names:

- `lib/stripe-keys.mjs`: a product sells on the new account only when `STRIPE_SECRET_KEY_NEW` and that product's `STRIPE_PRICE_*_NEW` are both set, else the old account. No global flag.
- Checkout drops `payment_method_types` on the new account. `download.mjs` tries the new key then the old, so pre-move buyers' links work. The webhook accepts either endpoint's signing secret.
- New account: 11 products and prices at the old amounts (lookup_key `mog_<env name>`), one webhook endpoint (`checkout.session.completed`) for `muscleonglp.netlify.app`. The monthly guide cron (`backend/monthly_guide/app.py`) now creates each new month's price on both accounts.
- Runtime key is the restricted key (keychain `stripe-live-secret-new`); the webhook secret is in the keychain as `stripe-webhook-secret-muscleonglp-new`.
- Managed Payments is NOT on for MuscleOnGLP: the PDF guides need an eligible tax code and a check first. Follow-up.
- Rollback: unset `STRIPE_SECRET_KEY_NEW` in the muscleonglp Netlify env (next build).

## Not touched

The old account, its webhook, every live env var, ExtensionPay, and Scholar Utility Belt Pro. No account was created and no key was entered by this work.
