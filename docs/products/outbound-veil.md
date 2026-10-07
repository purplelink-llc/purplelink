# Outbound Veil: paid macOS app, live status

Live since 2026-10-04 (release 1.0.0, build 41). 1.1.0 (build 45, one download with a license key, 2026-10-07) is staged and not published at the time of writing: see "One download, one key" below and `unified-licensing-2026-10.md`. Tour video: https://youtu.be/EWlyzL88-uo. Purchase chain tested end to end with a one-use 100%-off promotion code.

Outbound Veil is sold on purplelink.llc/outbound-veil as a one-time purchase, all updates included forever (including future major versions; Ben, 2026-10-04), with a
7-day trial from first launch (one download for everyone, from 1.1.0; the 1.0.x line had a separate trial build). It is a menu-bar app that checks the focused text field, in any app, for personal
information before the user sends it. Source: the `OutboundVeil` repo (`/Volumes/Extreme SSD/OutboundVeil`,
private). Design: that repo's `docs/superpowers/specs/2026-10-03-outbound-veil-design.md`.

## Stripe (live mode)

| Item | Value |
|---|---|
| Product | `prod_VNOyQCox4pCwN3` (account `acct_1TnewbJkzNxf3fKq`, created 2026-10-04) |
| Price | $29.99 USD one-time (.99 pricing decision 2026-10-07; was $29, decided 2026-10-03). `price_1UMeAEJkzNxf3fKqTmF7jfE2` was created at $29 and a Stripe Price amount cannot be edited: create a $29.99 Price on the product, set `STRIPE_PRICE_OUTBOUND_VEIL` to it and redeploy, before or with the site deploy that shows $29.99 |
| Env var | `STRIPE_PRICE_OUTBOUND_VEIL` (production context, set 2026-10-04); `OUTBOUND_VEIL_UPDATE_TOKEN` (production, secret, write-only; local copy at `~/.config/purplelink/outbound-veil-update-token`, which the build reads) |
| Product key | `outbound-veil` in `netlify/functions/checkout.mjs` |
| Success page | `/outbound-veil/success/?session_id=cs_...` |

## Delivery

`netlify/functions/outbound-veil-download.mjs`, a copy of `moderntex-download.mjs`, streams from the private
`outbound-veil-files` Blobs store:

- Buyers: `?session_id=cs_...` lists files; `&file=OutboundVeil-x.y.z.dmg` streams one. The session must be
  paid and carry `metadata.product=outbound-veil`.
- Trial (public): `?trial=1` streams the same newest `OutboundVeil-x.y.z.dmg` the buyers get once a 1.1.0-or-later
  DMG is in the store, 20 downloads per IP per day. Until then it serves the legacy `OutboundVeil-Trial-x.y.z.dmg`.
  The trial clock is seven days from first launch (Keychain plus Application Support, earliest wins), then an alert
  and the app stops checking until a license key is entered.
- Updates (Sparkle): `?feed=1` and `?update=<dmg>`, requiring the header
  `X-OutboundVeil-Channel: <OUTBOUND_VEIL_UPDATE_TOKEN>` (Netlify production env). The build script compiles
  the token into the app (`OVUpdateChannelToken` in Info.plist). From 1.1.0 every copy, trial or licensed, sends it:
  the token is no longer the paywall.

## One download, one key (1.1.0 onward)

- One DMG for everyone (`OutboundVeil-x.y.z.dmg`, 36 MB for 1.1.0). The trial link and the buyer's download are the
  same file. The app runs the 7-day trial from first launch; after it the app asks for a license key.
- Key scheme `PurplelinkLicenseV1`, prefix `OV1` (spec: `unified-licensing-2026-10.md`; code `netlify/lib/license.mjs`).
  Keys are derived from the Stripe session id, so the purchase email, `/outbound-veil/success/` (via
  `purchase-license.mjs`) and `/recover/` all show the same key. Offline check, no account, no activation count.
- The user enters it with "Enter license key…" in the menu-bar menu or Settings, General.
- Copies that ran as a paid build before 1.1.0 are recognized on first launch of the new version and never ask
  for a key. A trial copy keeps its original start date.
- The buyer email carries the key and the success-page link. `outbound-veil-reminder.mjs` (optional trial emails) tells
  the reader the key goes into the same copy.
- Keyfeel is separate: it shipped its own scheme (`KFL1`, key derived from the buyer's email, `keyfeel-license.mjs`).
  ModernTex keeps `MTX1` and still has its own trial download until its move.

## Releasing a version

From the OutboundVeil repo, on a clean commit:

```
OV_VERSION=1.1.0 scripts/build-release.sh                        # stages the one DMG, notarized
scripts/publish-release.sh 1.1.0 --dry-run                       # shows what would go live
scripts/publish-release.sh 1.1.0                                 # asks you to type "publish"
scripts/publish-release.sh 1.1.0 --rollback                      # pulls it back

# 1.0.x only (retired): OV_EDITION=trial built the separate trial DMG; there is no edition switch from 1.1.0.
```
Then update the version text on `/outbound-veil/` ("Version 1.1.0 · 36 MB disk image") and deploy the site (`bash scripts/deploy.sh`). The Sparkle
EdDSA key is the same one ModernTex uses (login keychain, "Private key for signing Sparkle updates").

## Attribution (required)

The detection model is Rampart, National Design Studio, CC BY 4.0. The app's About screen, the product page
and the repo's `NOTICE.md` must credit it and say what changed. Check all three before every release.

## Open items at launch

USPTO search for VEIL and OUTBOUND VEIL (classes 9, 42, 45); register outboundveil.com and .app; 
note: the two env vars take effect only after the next site deploy.
