# Outbound Veil: paid macOS app, live status

Live since 2026-10-04 (release 1.0.0, build 41). Tour video: https://youtu.be/EWlyzL88-uo. Purchase chain tested end to end with a one-use 100%-off promotion code.

Outbound Veil is sold on purplelink.llc/outbound-veil as a one-time purchase, all updates included forever (including future major versions; Ben, 2026-10-04), with a
7-day trial edition. It is a menu-bar app that checks the focused text field, in any app, for personal
information before the user sends it. Source: the `OutboundVeil` repo (`/Volumes/Extreme SSD/OutboundVeil`,
private). Design: that repo's `docs/superpowers/specs/2026-10-03-outbound-veil-design.md`.

## Stripe (live mode)

| Item | Value |
|---|---|
| Product | `prod_VNOyQCox4pCwN3` (account `acct_1TnewbJkzNxf3fKq`, created 2026-10-04) |
| Price | $29 USD one-time (decided 2026-10-03; `price_1UMeAEJkzNxf3fKqTmF7jfE2`) |
| Env var | `STRIPE_PRICE_OUTBOUND_VEIL` (production context, set 2026-10-04); `OUTBOUND_VEIL_UPDATE_TOKEN` (production, secret, write-only; local copy at `~/.config/purplelink/outbound-veil-update-token`, which the build reads) |
| Product key | `outbound-veil` in `netlify/functions/checkout.mjs` |
| Success page | `/outbound-veil/success/?session_id=cs_...` |

## Delivery

`netlify/functions/outbound-veil-download.mjs`, a copy of `moderntex-download.mjs`, streams from the private
`outbound-veil-files` Blobs store:

- Buyers: `?session_id=cs_...` lists files; `&file=OutboundVeil-x.y.z.dmg` streams one. The session must be
  paid and carry `metadata.product=outbound-veil`.
- Trial (public): `?trial=1` streams the newest `OutboundVeil-Trial-x.y.z.dmg`, 20 downloads per IP per day.
  The trial edition is the same source built with `OV_EDITION=trial`: seven days from first launch (Keychain
  plus Application Support, earliest wins), then an alert and the app stops checking. No Sparkle feed.
- Updates (Sparkle): `?feed=1` and `?update=<dmg>`, requiring the header
  `X-OutboundVeil-Channel: <OUTBOUND_VEIL_UPDATE_TOKEN>` (Netlify production env). The build script compiles
  the token into the app (`OVUpdateChannelToken` in Info.plist).

There is no licence key. The buyer email (the webhook's `BLOB_DELIVERED_PRODUCTS` list) carries the success-page
link. No lifecycle follow-up emails in v1.

## Releasing a version

From the OutboundVeil repo, on a clean commit:

```
OV_VERSION=1.0.0 scripts/build-release.sh                        # stages the paid DMG, notarized
OV_VERSION=1.0.0 OV_EDITION=trial scripts/build-release.sh       # then the trial
scripts/publish-release.sh 1.0.0 --dry-run                       # shows what would go live
scripts/publish-release.sh 1.0.0                                 # asks you to type "publish"
scripts/publish-release.sh 1.0.0 --rollback                      # pulls it back
```
Then update the version text on `/outbound-veil/` and deploy the site (`bash scripts/deploy.sh`). The Sparkle
EdDSA key is the same one ModernTex uses (login keychain, "Private key for signing Sparkle updates").

## Attribution (required)

The detection model is Rampart, National Design Studio, CC BY 4.0. The app's About screen, the product page
and the repo's `NOTICE.md` must credit it and say what changed. Check all three before every release.

## Open items at launch

USPTO search for VEIL and OUTBOUND VEIL (classes 9, 42, 45); register outboundveil.com and .app; 
note: the two env vars take effect only after the next site deploy.
