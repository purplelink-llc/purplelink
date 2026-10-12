# Panely: paid macOS app, launch runbook

Built overnight 2026-10-11 to 2026-10-12 (see "State" below). App source: `/Volumes/Extreme SSD/Panely` (local git, no remote; Swift package
`PanelyCore` + `PanelyApp`; `scripts/make-app.sh`, `build-release.sh`, `publish-release.sh`, `release-common.sh`, adapted from Keyfeel's).
Panely is a working name Ben has not cleared: screened 2026-10-11 against the Mac App Store, GitHub and domain records only
(no match, .com and .app looked unregistered); the USPTO search is Ben's.

Panely is a menu-bar window manager: snaps the front window to halves, quarters, thirds, two thirds and sixths (shortcut, menu, or drag to a screen edge or corner with a preview), repeats cycle half, two thirds and one third, a margin and a gap, move to next or previous display, restore, saved layouts, a rule-based "describe a layout" parser (no model), and an automatic layout per arrangement of displays that is re-applied when a display returns. Accessibility permission only; shortcuts use Carbon hotkeys, so no Input Monitoring.

$9.99 once, free 7 days inside the same download, then a license key (`PNL1`, Ed25519, its own key pair, derived from the buyer's address,
`netlify/lib/panely-license.mjs`), one key on two Macs, 14-day refund, in the Mac Suite ($54.99, now seven apps and Vitae Plus). Requires macOS 14 or
later; both slices (arm64 and x86_64) compile, the Intel slice has not been run on an Intel Mac.

## State

- Branch `new-apps/summonly-panely` (safe to merge any time): licence libraries and download functions for both apps, product and success pages
  (noindex, gate closed), icons, share images, tests. Nothing links to them and nothing can be bought.
- Branch `new-apps/launch-day` (stacked on it, DO NOT MERGE before a release is published): checkout catalog entries, webhook delivery and
  email blocks, recovery email, custom-bundle parts (the Suite becomes eight parts), Suite page and success page, products, pricing, terms,
  llms.txt, footers, trial-download beacon (`pf_`/`sm_trial_download`), tests. Merging it makes the Suite entitle apps that have no download.
- `scripts/go-live-app.py <slug> <version> <sizeMb> <date>` turns one app's pages on (launch.js, robots, availability, static controls, sitemap).
- Not done by anyone: notarized DMG, Blobs upload, Netlify secrets, Stripe test purchase, the hand checks below, the home-page dock tile
  (the dock is a layout decision: 8 tiles already), `site/assets/og/mac-suite.png` re-render (`_gen.html` is updated, the PNG is not),
  traffic-dashboard collector for the new trial events, the Homebrew/Setapp questions.

## Release steps (in this order)

1. In the app repo: `PN_VERSION=1.0.0 scripts/build-release.sh` (universal, Developer ID signed, notarized with the `moderntex` notary profile; stages
   under `releases/staging/`). The icon is in (`assets/brand/Panely.icns`). Needs `PN_UPDATE_TOKEN` (generate once, keep in
   `~/.config/purplelink/panely-update-token`; a token was generated 2026-10-12, never printed).
2. Test the staged DMG on a clean Mac and do the hand checks below.
3. Netlify env: `PANELY_LICENSE_PRIVATE_KEY` (the seed in `~/.config/purplelink/panely-license-private-key`; also add it to the W1 off-Mac backup list: it exists
   only on this Mac), `PANELY_UPDATE_TOKEN`. Blobs store `panely-files` is created by the first upload. Public key is compiled into the app and the lib:
   `g5PuqTjIibETZuP5AVqwYZPUsJ/lS6ox9z3QyVkRNvw=`.
4. `scripts/publish-release.sh 1.0.0` in the app repo (uploads the DMG and appcast, reads both back and compares bytes).
5. In this repo: merge the launch-day branch only after step 4, run `python3 scripts/go-live-app.py panely <version> <sizeMb> <date>`, run both test
   suites, push once (Netlify build minutes), verify the live page and `/.netlify/functions/panely-download?download=1`.
6. A 100%-off Stripe promotion code test purchase: receipt email, success page, key, download, byte-identical DMG, recovery email, Suite session.

## Hand checks before the gate flips (written from code and unit tests, never run end to end on a real Mac)

- [ ] The Accessibility prompt appears when Panely first opens (not on the first snap), and snapping works after it is granted.
- [ ] Every default shortcut moves a window to the right place on one and on two displays; the half shortcut cycles; Restore returns the first size.
- [ ] Drag to each edge and corner: preview appears, release snaps, a click in window content does not snap, macOS's own edge tiling on at the same time (Settings warning shows and its button opens the right pane).
- [ ] Apps that enforce a minimum size or refuse resizing (Electron, Terminal, Xcode) end up sensible.
- [ ] Unplug and replug a monitor: windows return (this is the headline claim; it is untested live). Sleep and lock do not overwrite the saved arrangement.
- [ ] Save a layout, quit apps, relaunch, apply it: the unmatched list is accurate. Describe a layout with a real phrase.
- [ ] Trial ends after 7 days (set the clock forward), the alert offers Buy and Enter Key, a key unlocks, setting the clock back does not extend it.
- [ ] Sparkle update from an older build to a newer one through the real feed.

## Tests

`PanelyCoreTests` in the app repo (`DEVELOPER_DIR="/Volumes/Extreme SSD/Xcode.app/Contents/Developer" swift test`), including
`CrossLanguageVectorTests` (keys made by the website issuer must verify in the app). Here: `netlify/tests/panely-license.test.mjs`,
`panely-download.test.mjs`, `panely-site.test.mjs` (gate states, copy rules, images, success script against a fake DOM) and
`new-apps-purchase.test.mjs` (checkout, emails, bundles, entitlement). Tests must never touch real folders: Summonly's scanner tests build
their own temporary folders, and the benchmark test is opt-in (`SUMMONLY_BENCH_ROOT`, `SUMMONLY_BENCH_DB`).

## Rules for this product

- Copy: list only shipped features; no AI claims beyond what is built; the page says the illustration or sample is not the real thing.
- Never launch the GUI on Ben's session to test: the global shortcuts move real windows. Use `PanelyApp --status` (prints trust and displays, starts no trial) and the unit tests. AX integration tests need Accessibility granted to a test binary, which only Ben can do.
- No App Store build. Sparkle updates through `panely-download?update=` with the `X-Panely-Channel` header.
