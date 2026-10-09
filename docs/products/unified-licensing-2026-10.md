# One download, one key: unified licensing (2026-10-07)

Decision (Ben, 2026-10-07): every paid Purplelink Mac app is ONE download that runs a 7-day free
trial from first launch, then needs a license key. No separate trial build. Applies to Outbound Veil,
Legroom, Keyfeel and ModernTex. People who already bought keep working with no key.

**Keyfeel is already done (separate session, live 2026-10-07, build 17).** It shipped with its own scheme:
keys `KFL1-...`, domain `KeyfeelLicenseV1`, key derived from the buyer's email, code in
`netlify/lib/keyfeel-license.mjs` and the Keyfeel repo. It is NOT part of PurplelinkLicenseV1 below. Outbound
Veil and Legroom use PurplelinkLicenseV1; ModernTex keeps MTX1 until its own move to one download.

**Tapefolio (store side built 2026-10-09)** follows the Keyfeel pattern: one download, 7-day trial, its own scheme (keys `TFL1-...`,
domain `TapefolioLicenseV1`, key derived from the buyer's email, `netlify/lib/tapefolio-license.mjs`, public key
`5qmJMOr4uux0LZrWGs/V6nc6VKXsogioMgiJ3pBlSvI=`), also not part of PurplelinkLicenseV1. See `tapefolio.md`.

Why: the Suite page showed a separate trial download and a separate "full" download per app, with no
key (ModernTex was the only one with a key). One download per app removes "install this copy in its
place" and makes the key the single paywall.

## Pieces

| Piece | Owner | State |
|---|---|---|
| Key scheme and issuer (`netlify/lib/license.mjs`), test vectors | server | done |
| Purchase email, success pages, recovery show the keys | server + site | in progress |
| Download functions serve ONE DMG (trial door serves the same file) | server | in progress |
| Outbound Veil, Legroom apps | app agents | built to this spec |
| Keyfeel app | other session | live, own scheme (see above) |
| ModernTex | after the three above are proven | later |

## Key scheme: PurplelinkLicenseV1 (Outbound Veil, Legroom)

- Key text: `<PREFIX>-` + Crockford-Base32( nonce[4] ‖ Ed25519 signature[64] ) in groups of 5, joined by `-`.
  The body is 109 characters (21 groups of 5, then a group of 4).
  Prefixes: Outbound Veil `OV1`, Legroom `LG1`.
- Signed message: UTF-8 `PurplelinkLicenseV1|<slug>|` followed by the 4 nonce bytes.
  Slugs: `outbound-veil`, `legroom`. A key for one product never verifies for another.
- One shared PUBLIC key, embedded in every app (raw 32 bytes, base64):
  `d8gyRHTJVAivaL2wx4m1dQTLxrfE2htFhxzNDF8dFs4=`
- Verification is offline and must be exactly what `verifyLicense` in `netlify/lib/license.mjs` does:
  trim, upper-case, drop dashes, drop the product prefix if present, decode Crockford Base32
  (`O`->0, `I`/`L`->1, reject other characters), require exactly 68 bytes, verify the Ed25519 signature
  over domain ‖ nonce. Case, dashes and surrounding spaces do not matter.
- The private seed never leaves the server (Netlify secret `PURPLELINK_LICENSE_PRIVATE_KEY`) and
  `~/.config/purplelink/license-keys/` on Ben's Mac. Apps never contain it. A DEBUG-only issuer for tests
  must take an injected private key and must not compile into release builds.
- ModernTex keeps its own scheme (`MTX1`, domain `ModernTexLicenseV1`, key in `LicenseKey.swift`). Do not change it.
- Test vectors (TEST key, not production): `netlify/tests/fixtures/license-vectors.json`. Every app must
  verify all of them in its own tests, including the invalid ones, using an injectable public key.

## App behaviour (all apps)

1. One build. Delete the trial edition (`OV_EDITION`/`LG_EDITION`/`KF_EDITION`, trial targets, trial
   DMG naming, trial plist keys). Every build embeds Sparkle with the real feed URL and update token.
   DMG name is the existing paid name (`OutboundVeil-x.y.z.dmg`, `Legroom-x.y.z.dmg`, `Keyfeel-x.y.z.dmg`).
2. Startup decides one of four states, ONCE, before Sparkle starts, and persists the decision:
   1. **licensed**: a stored key that verifies (re-verify on every launch; never store a boolean).
   2. **legacy paid**: first run of the unified build on a copy that ran before as a legacy FULL build
      (rules below). Treated as licensed, no key needed, forever.
   3. **trial**: 7 days from first launch, using the app's existing trial clock and stores.
      A legacy TRIAL copy keeps its existing start date (its Keychain/file record).
   4. **expired**: the trial is over and there is no key. Behaviour is the app's existing expiry
      behaviour (Outbound Veil stops checking and shows the alert; Legroom locks the paid features and
      keeps the free readout and alerts; Keyfeel goes silent), plus a way to enter a key.
3. Legacy classification, evaluated only when the unified build has no persisted decision yet, in this order:
   1. a valid stored key -> licensed;
   2. Sparkle's own defaults show the updater ran before this build started it (`SUHasLaunchedBefore`
      or `SULastCheckTime` in the app's UserDefaults domain). Only legacy FULL builds ever started Sparkle,
      so this means a legacy paid install -> **legacy paid**, even if a trial record also exists
      (a trial user who then bought and installed the full build);
   3. a legacy trial record exists (Keychain/file) -> **trial**, continue its clock;
   4. app data or preferences from earlier use exist but no trial record -> **legacy paid**;
   5. nothing -> fresh: start the 7-day trial now.
   Put this logic in the app's pure core library as a function over plain Bool inputs, with a table test
   covering every row and the persisted-decision-wins rule. Do not start Sparkle (or anything that writes
   Sparkle defaults) before the decision is made and persisted. Persist the decision in the Keychain and
   a file, like the trial clock does, so deleting one does not change it.
4. UI, in each app's existing idiom, with this wording:
   - status line: `Trial: N days left` (`Trial: last day`), `Trial ended`, or `Licensed`;
   - `Enter license key…` opens a small window or sheet with a text field. It validates as the user
     pastes, shows `Unlocked` or `That key does not match this app`, stores the key in the Keychain on
     success and updates the UI at once; no restart;
   - `Buy …` keeps opening the product page with `?from=trial`;
   - a licensed copy shows no trial UI and no buy button; Settings/About may show `Licensed`.
   Where: Outbound Veil menu "Trial" block + Settings General "Trial" section + the expiry alert;
   Legroom dropdown `licenseRow` + Settings General + `LockedFeatureView`; Keyfeel menu + Settings General
   "Trial" section + the trial-ended alert.
5. Existing guard tests may be rewritten where they pin the old two-edition design (Legroom's
   `LicensingAppLayerTests` pins "no license key text", "no Keychain in app sources", "no LGEdition").
   Keep the intent (core owns Keychain and policy; the app layer stays thin) and update them.
6. Tests: key vectors, classification table, trial clock unchanged, license activation/persistence with an
   in-memory store, and that a licensed state ignores an expired clock. Use the repo's own test command.
7. Release scripts: single edition, one DMG, one manifest, notarized, stapled; the publish script uploads
   only that DMG and regenerates the appcast. Remove trial-DMG upload, trial-only asserts and branches.
   Do NOT run any publish script. Staging a notarized build for verification is fine.
8. Versions: Outbound Veil 1.1.0, Legroom 1.1.0.
   Write the release notes file each repo's pipeline expects, in plain voice, no em dashes.

## Server behaviour (this repo)

- Purchase email and the success pages show the key for each product the session is entitled to
  (Suite: ModernTex plus the three above; Vitae Plus keeps its own flow). Keys are derived from the Stripe
  session id, so the page, the email and the recovery page always show the same key.
- `GET /.netlify/functions/purchase-license?session_id=cs_...` returns `{keys:[{product,label,key}]}` for a
  paid session (rate limited), no key material otherwise.
- The trial door (`?trial=1`) serves the same newest DMG the buyers get. The legacy `*-Trial-*.dmg` files stay in
  the store for old links but are no longer produced.
- Anyone can run the trial; the key is the paywall. The update token is no longer the paywall.

## Not doing

- No server-side activation counts or revocation (offline keys, same as ModernTex).
- No keys sent to past buyers, by Ben's decision. Past buyers are recognised by the legacy rules above.
