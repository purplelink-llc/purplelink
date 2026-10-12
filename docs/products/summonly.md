# Summonly: paid macOS app, launch runbook

Built overnight 2026-10-11 to 2026-10-12 (see "State" below). App source: `/Volumes/Extreme SSD/Summonly` (local git, no remote; Swift package
`SummonlyCore` + `SummonlyApp`; `scripts/make-app.sh`, `build-release.sh`, `publish-release.sh`, `release-common.sh`, adapted from Keyfeel's).
Summonly is a working name Ben has not cleared: screened 2026-10-11 against the Mac App Store, GitHub and domain records only
(no match, .com and .app looked unregistered); the USPTO search is Ben's.

Summonly is a menu-bar launcher opened with Option-Space: file, folder and app search over a private SQLite full-text index (names, paths and the start of text, code, Markdown, RTF and PDF files), filters and plain-language dates, app abbreviations, ranking by name then frecency, an optional find-by-meaning layer (Apple's built-in English sentence embedding, int8 vectors, documents only, off by default), a calculator with unit conversion, web search keywords, clipboard history with privacy rules (Option-Shift-V or "clip"), and snippets. A downloadable small embedding model is a possible later addition behind the same `Embedder` protocol; none is shipped.

$9.99 once, free 7 days inside the same download, then a license key (`SML1`, Ed25519, its own key pair, derived from the buyer's address,
`netlify/lib/summonly-license.mjs`), one key on two Macs, 14-day refund, in the Mac Suite ($54.99, now seven apps and Vitae Plus). Requires macOS 14 or
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

1. In the app repo: `SM_VERSION=1.0.0 scripts/build-release.sh` (universal, Developer ID signed, notarized with the `moderntex` notary profile; stages
   under `releases/staging/`). The icon is in (`assets/brand/Summonly.icns`). Needs `SM_UPDATE_TOKEN` (generate once, keep in
   `~/.config/purplelink/summonly-update-token`; a token was generated 2026-10-12, never printed).
2. Test the staged DMG on a clean Mac and do the hand checks below.
3. Netlify env: `SUMMONLY_LICENSE_PRIVATE_KEY` (the seed in `~/.config/purplelink/summonly-license-private-key`; also add it to the W1 off-Mac backup list: it exists
   only on this Mac), `SUMMONLY_UPDATE_TOKEN`. Blobs store `summonly-files` is created by the first upload. Public key is compiled into the app and the lib:
   `/M6E93g8PkclprpJOsACLXYoHavtVvnbVKChZm1uflA=`.
4. `scripts/publish-release.sh 1.0.0` in the app repo (uploads the DMG and appcast, reads both back and compares bytes).
5. In this repo: merge the launch-day branch only after step 4, run `python3 scripts/go-live-app.py summonly <version> <sizeMb> <date>`, run both test
   suites, push once (Netlify build minutes), verify the live page and `/.netlify/functions/summonly-download?download=1`.
6. A 100%-off Stripe promotion code test purchase: receipt email, success page, key, download, byte-identical DMG, recovery email, Suite session.

## Hand checks before the gate flips (written from code and unit tests, never run end to end on a real Mac)

- [ ] Option-Space opens the panel on the screen the pointer is on; Escape and clicking away close it; focus and typing work from a cold start.
- [ ] The macOS folder prompts appear for Desktop, Documents and Downloads and indexing works after they are allowed; the first index of a real home folder finishes and the menu shows a count.
- [ ] Edit, add and delete a file: search reflects it within a few seconds (FSEvents).
- [ ] Measure: idle memory, CPU during the first index, index size on disk for a real Documents folder (the only numbers so far are 2,350 files in 1.1 s on the site folder). Nothing on the page claims a memory figure.
- [ ] Clipboard: copy from a password manager (skipped), from Terminal, a card-number-shaped string (skipped); history survives a restart unless memory-only; Clear works.
- [ ] Return opens, Command-Return reveals, Option-Return copies the path; calculator and unit answers copy; web keywords open the browser.
- [ ] Find by meaning on and off with a few hundred real documents; check that results below the word matches make sense.
- [ ] Trial and licence as for Panely; Sparkle update path.
- [ ] Intel Mac if one is available (the slice compiles, it has not been run).
- [ ] Settings: record a different Summonly hotkey and a different clipboard hotkey; try a bare key, Command-Q, and the other hotkey's combination (each is refused with a message); Command-Space shows the Spotlight note; Reset restores the defaults. Choose a combination another app holds and confirm the orange warning.
- [ ] Settings take effect without a relaunch: add a folder (indexed within a minute), remove a folder (its files stop appearing at once), leave a folder out, turn off "search inside files" (text results disappear, names remain).
- [ ] Quick tools row appears for uuid, base64 hello, sha256 abc, #ff8800, epoch, slug, count, password 24; a file whose name matches (create "uuid-list.txt") stays above the tool row; Return copies. The generated password is not recorded in Summonly's own clipboard history and is gone from the clipboard after a minute.
- [ ] System rows: type sleep (a file called "sleep schedule" outranks it), lock, screen saver, quit safari, force quit notes (the alert names the app and Cancel does nothing), wifi (opens that Settings pane). Do not run sleep or lock while anything important is open.
- [ ] Safari, Notes and other apps that are symlinks into the system volume are found by name.
- [ ] Open at login switch: restart and confirm Summonly starts; switching it off removes it from System Settings, General, Login Items.
- [ ] Clipboard privacy on macOS 27: does reading the pasteboard in the background raise a prompt or a banner? If so, say so on the page.
- [ ] A file that iCloud has moved off the Mac (Optimize Mac Storage) is not downloaded by indexing.
- [ ] Hide the menu bar icon, let the trial expire (clock forward) and confirm the icon comes back so a key can be entered.

## Tests

`SummonlyCoreTests` in the app repo (`DEVELOPER_DIR="/Volumes/Extreme SSD/Xcode.app/Contents/Developer" swift test`), including
`CrossLanguageVectorTests` (keys made by the website issuer must verify in the app). Here: `netlify/tests/summonly-license.test.mjs`,
`summonly-download.test.mjs`, `summonly-site.test.mjs` (gate states, copy rules, images, success script against a fake DOM) and
`new-apps-purchase.test.mjs` (checkout, emails, bundles, entitlement). Tests must never touch real folders: Summonly's scanner tests build
their own temporary folders, and the benchmark test is opt-in (`SUMMONLY_BENCH_ROOT`, `SUMMONLY_BENCH_DB`).

## Rules for this product

- Copy: list only shipped features; no AI claims beyond what is built; the page says the illustration or sample is not the real thing.
- Never launch the GUI on Ben's session to test: the app indexes real folders and watches the clipboard. A stale binary once ran for 30 seconds during development and indexed part of Ben's folders into `~/Library/Application Support/Summonly` (deleted afterwards). Use `SummonlyApp --demo <png>` (renders the panel with sample rows, touches no files) and the unit tests.
- No App Store build. Sparkle updates through `summonly-download?update=` with the `X-Summonly-Channel` header.
