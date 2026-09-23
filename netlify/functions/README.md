# Netlify Functions

## `checkout`

Creates a Stripe Checkout session for the paid Paper Review tool. Hit by the
"Start review — $5" button on `/tools/paper-review/`. Returns the hosted
Stripe Checkout URL; the browser is redirected to Stripe, payment is
captured there, and on success Stripe sends the user back to
`/tools/paper-review/upload/?session_id=…`.

**Function URL:** `https://purplelink.llc/.netlify/functions/checkout`

Required env vars (set via `netlify env:set --context production`):
- `STRIPE_SECRET_KEY` — `sk_test_…` while testing, `sk_live_…` once live.
- `STRIPE_PRICE_ID` — `price_…` of the $5 Paper Review one-time price.

## `stripe-webhook`

Receives Stripe webhook events. Only acts on `checkout.session.completed`.
Verifies the Stripe signature using HMAC-SHA256, extracts session_id +
customer email + amount, and forwards to the Modal backend's
`/paper-review/register-token` endpoint so the backend can mint a
redemption token for that session.

**Function URL:** `https://purplelink.llc/.netlify/functions/stripe-webhook`

Required env vars:
- `STRIPE_WEBHOOK_SECRET` — `whsec_…` signing secret from the Stripe
  webhook endpoint configuration.
- `BACKEND_WEBHOOK_SECRET` — same value as the Modal secret
  `paper-review-shared`. Authenticates the function -> Modal call.

**Wiring it into Stripe:**

1. In the Stripe dashboard, add a webhook endpoint at
   `https://purplelink.llc/.netlify/functions/stripe-webhook`.
2. Subscribe to the single event `checkout.session.completed`.
3. Copy the signing secret (`whsec_…`) and set it as
   `STRIPE_WEBHOOK_SECRET` in Netlify.

Detailed end-to-end Stripe + Modal setup is in
[`docs/paper-review-runbook.md`](../../docs/paper-review-runbook.md).

## `moderntex-download`

Session-gated delivery of the ModernTex DMG (buyers) and the token-gated Sparkle
feed and update DMGs (the app). See `docs/products/moderntex.md`. The webhook
above also emails Blobs-delivered buyers (kits, ModernTex) their success-page
link via Resend; set `ALERT_EMAIL_TO` so a failed send reaches you.

## `vitae-license`

Issues, refreshes and manages Vitae Plus subscription keys. Vitae Plus is a
subscription sold through `checkout.mjs` as `vitae-plus-monthly`
(`STRIPE_PRICE_VITAE_PLUS_MONTHLY`, $3/month) and `vitae-plus-annual`
(`STRIPE_PRICE_VITAE_PLUS_ANNUAL`, $24/year), both with a 7-day trial
(`subscription_data[trial_period_days]=7`). Three GET modes:

- **Issue** `?session_id=cs_…`, called by `/vitae/plus/success/`. Retrieves the
  Checkout Session with `expand[]=subscription`, requires `metadata.product` to
  start with `vitae-plus-` and a subscription to exist, stores
  `{ subscription, plan }` in the `vitae-plus` Blobs store under the key's id,
  and returns `{ "key": "VP2-…", "email": "<Stripe receipt address>" | null }`.
  The email is only displayed on the page and is never logged or stored.
  402 while the session or subscription is not complete (the page retries).
- **Refresh** `?refresh=<id>`, called by the app about once a month with the
  16-lowercase-hex id from its current key and nothing else. Looks up the
  mapping, retrieves the subscription from Stripe, and returns
  `{ "key": "VP2-…", "status": "<subscription status>" }`. `active` and
  `trialing` get exp = current period end + 7 days; `past_due` gets exp = now +
  7 days; any other status returns 410 `{ "status": "<status>" }`. Unknown id:
  404. Never returns an email.
- **Recover** `POST {"recover": "<email>"}`, from `/vitae/plus/recover/`. Finds
  Stripe customers with that email and their live Vitae Plus subscriptions
  (`metadata.product` starting `vitae-plus-`, status active, trialing or
  past_due), restores each id-to-subscription mapping, and emails a current key
  to that address through Resend. Always answers `{ "status": "sent_if_found" }`
  (so it cannot reveal who subscribes); 400 for a malformed address, 429 after
  3 requests per address per day or the per-IP limit, 502 if the email failed.
- **Manage** `POST {"manage": "<id>"}`, sent by the app's "Manage
  Subscription" button. A POST keeps the id out of browser URLs and history.
  Looks up the subscription's customer, creates a Stripe billing portal
  session (return URL `/vitae/plus/`) with a limited portal configuration
  (invoices, card update, cancel at period end; no email, address or plan
  changes), and returns `{ "url": "<portal url>" }`,
  which the app opens in the browser. On any failure the app opens
  `/vitae/plus/manage/`, which explains how to cancel by email. The old
  `GET ?manage=` form now redirects to that page.

All responses are `no-store`, and each IP gets 60 requests per UTC day across
all modes (`rate-limits` Blobs store). Malformed ids get 400.

Required env vars:
- `STRIPE_SECRET_KEY`: shared with `checkout`.
- `VITAE_LICENSE_PRIVATE_KEY`: the Ed25519 private key as a PKCS#8 PEM string.
  Newlines may be pasted escaped as `\n`. The matching public key is compiled
  into Vitae, which verifies keys offline.
- `RESEND_API_KEY`: shared with `stripe-webhook`; sends recovery emails.
- `STRIPE_PORTAL_CONFIG_VITAE_PLUS` (optional): a `bpc_…` portal configuration
  id to use instead of the one the function creates.

The billing portal does not use the account's default Customer Portal
configuration. On first use the function creates a Vitae Plus configuration
(invoice history, payment method update, cancel at period end; customer and
subscription updates off) and keeps its id in the `vitae-plus` Blobs store under
`_portal_config`. If it cannot be created, manage answers 502 and the app opens
the manage help page; it never falls back to an unrestricted portal. Stripe
still requires the Customer Portal to have been activated once in the dashboard
(Settings > Billing > Customer portal).

Key format v2, which must match the app's verifier exactly:

```
payload = UTF-8 JSON.stringify({ exp, iat, id, p: "vitae-plus", plan, v: 2 })
          // key order exactly: exp, iat, id, p, plan, v
          exp  = unix seconds (see the refresh rules above)
          iat  = now, unix seconds
          id   = first 16 hex characters of sha256(subscription.id)
          plan = "monthly" | "annual"
sig     = Ed25519 signature over payload (crypto.sign(null, payload, key))
key     = "VP2-" + base64url(payload) + "." + base64url(sig)         // no padding
```

`current_period_end` is read from the subscription, or from its first item on
Stripe API versions that moved it there. `plan` follows the price's billing
interval, so a plan switch in the portal shows up at the next refresh. The key
carries no name or email. `buildLicenseKey()`, `expiryFor()`, `periodEnd()` and
`planOf()` are exported so the format can be tested without Stripe.
`stripe-webhook` recognizes `vitae-plus-*` checkouts and cancellations and only
logs them: refresh reads live status from Stripe, so the webhook has nothing to do.

## `indexnow-ping`

Pings the IndexNow shared endpoint (Bing / Yandex / Seznam / Naver) with URLs from the live sitemap whose `<lastmod>` matches today. Triggered automatically after every production deploy via a Netlify outgoing webhook.

**Function URL:**
```
https://purplelink.llc/.netlify/functions/indexnow-ping?token=<INDEXNOW_WEBHOOK_TOKEN>
```

The `INDEXNOW_WEBHOOK_TOKEN` environment variable is already set in Netlify (production context). To rotate it:

```
netlify env:set INDEXNOW_WEBHOOK_TOKEN <new-value> --context production
netlify deploy --prod   # function picks up the new value on next deploy
# Then update the outgoing webhook URL in Netlify dashboard to match.
```

## One-time setup: wire the deploy-succeeded webhook

This is the only step you have to do in the Netlify UI (the CLI doesn't expose outgoing-webhook config yet).

1. Go to [Site configuration → Build & deploy → Deploy notifications](https://app.netlify.com/projects/purplelink/configuration/notifications)
2. Under **Outgoing webhooks**, click **Add notification**
3. Configure:
   - **Event:** `Deploy succeeded`
   - **URL to notify:** `https://purplelink.llc/.netlify/functions/indexnow-ping?token=_LpQkCvG08Pp7kD62F5LXipYj70JsSG9R3iUk405pik`
   - **JWT signature secret:** leave blank (auth is via the URL token instead)
4. Save

After that, every successful production deploy automatically pings IndexNow about that day's changed URLs.

## Manual invocation

If you ever need to force a full re-ping (e.g., after a large sitemap rewrite):

```
TOKEN='_LpQkCvG08Pp7kD62F5LXipYj70JsSG9R3iUk405pik'
curl -X POST "https://purplelink.llc/.netlify/functions/indexnow-ping?token=$TOKEN&all=1"
```

The `all=1` flag pings every URL in the sitemap, not just today's. Use sparingly — IndexNow rate limits at ~10k URLs/day per domain.

## Verifying it works

After a `make deploy` finishes, check Netlify's Function logs:
- https://app.netlify.com/projects/purplelink/logs/functions

Look for a `indexnow-ping` invocation with a `200 pinged` response.

## The local-vs-webhook double-ping

`make deploy` (via `scripts/deploy.sh`) ALSO pings IndexNow from your laptop. After the Netlify webhook is wired up, you can either:

- **Leave both running** — IndexNow is idempotent and the double-ping is harmless (and gives you redundancy if either path fails).
- **Disable the local one** — edit `scripts/deploy.sh` to default to `--skip-ping`, or just stop using `make deploy` and rely on the webhook.

I'd recommend leaving both for the first week, then disabling the local ping once you've confirmed the webhook is firing reliably in the Function logs.
