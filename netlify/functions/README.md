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

Issues Vitae Plus license keys. The success page `/vitae/plus/success/` calls
`GET /.netlify/functions/vitae-license?session_id=cs_…` after Stripe Checkout
(product key `vitae-plus` in `checkout.mjs`, price `STRIPE_PRICE_VITAE_PLUS`).
The function retrieves the Checkout Session from Stripe, requires
`payment_status === "paid"` and `metadata.product === "vitae-plus"`, and returns
`{ "key": "VP1-…", "email": "<Stripe receipt address>" | null }`. The email is
only displayed on the page and is never logged. Responses are `no-store`, and
each IP gets 60 requests per UTC day (`rate-limits` Blobs store). Errors: 400
for a malformed session id, 404 when no Vitae Plus order matches, 402 while the
payment has not cleared.

Required env vars:
- `STRIPE_SECRET_KEY`: shared with `checkout`.
- `VITAE_LICENSE_PRIVATE_KEY`: the Ed25519 private key as a PKCS#8 PEM string.
  Newlines may be pasted escaped as `\n`. The matching public key is compiled
  into Vitae, which verifies keys offline and never calls this function.

Key format, which must match the app's verifier exactly:

```
payload = UTF-8 JSON.stringify({ iat, id, p: "vitae-plus", v: 1 })   // key order iat, id, p, v
          iat = the session's Stripe `created` time, unix seconds
          id  = first 16 hex characters of sha256(session.id)
sig     = Ed25519 signature over payload (crypto.sign(null, payload, key))
key     = "VP1-" + base64url(payload) + "." + base64url(sig)         // no padding
```

Both payload fields come from the session, so reloading the success page returns
the same key. The key carries no name or email. `buildLicenseKey()` is exported
so the format can be tested without Stripe. The webhook does not handle
`vitae-plus`; there is nothing for it to deliver.

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
