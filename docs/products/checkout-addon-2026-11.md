# Optional second app at 25% off in Checkout (2026-11-06)

A buyer of one Mac app alone sees one or two unchecked rows in Stripe Checkout (`optional_items`), each the app's own
price less 25%. Code: `netlify/lib/addons.mjs`. Prices: `node scripts/stripe_addon_prices.mjs` (test mode) and
`--live` (idempotent; looks up by lookup_key before creating).

- Prices: one one-time USD Price per app, `lookup_key` `addon_<slug>_25`, `metadata.addon_slug`. Checkout finds them by
  lookup_key at runtime (5-minute in-memory cache), so no env vars. Changing an app's price in `bundles.mjs`
  (`PART_CENTS`) needs a new Price: the lookup validates the amount and leaves the row out on a mismatch.
- Offered only for a single keyed Mac app in plain payment mode. Left out for bundles, the Suite, seat packs, Paper
  Review and other tools, kits, buyer-code or friend-discount orders, and Managed Payments.
- Entitlement is derived from the paid line items (`addonsFromSession`), never from client input or metadata. The
  webhook, the nine download functions, `purchase-license`, and `purchases-recover` expand `line_items`. The webhook
  reads them only when `metadata.addon_offered` is present. Single-app success pages redirect to `/suite/success/`
  (`?from=addon`) when the order has two apps.
- Any failure (Prices lookup, Stripe refusing `optional_items`) sends the plain checkout. Refunds and disputes treat
  the session as a whole.
