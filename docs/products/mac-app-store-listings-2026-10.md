# Tapefolio and Keyfeel: Mac App Store listings, ready to submit

Written 2026-10-28, so that both apps can be submitted in one sitting once Vitae is approved. Nothing here has been
entered in App Store Connect. Vitae's listing (submitted 2026-10-27) is the pattern: same privacy policy, same
copyright line, same review-note style.

Every claim below was checked against the App Store edition's code on each repo's `main` (Tapefolio 1.2.0, `e8b0346`;
Keyfeel `999b35c` plus the fix in "Code changed for review"). Where an answer rests on code, the file is named. The
App Store editions differ from the direct downloads: no Sparkle update check, no license keys, a free "7-Day Trial"
in-app purchase and a one-time unlock. Copy below describes the App Store edition only.

Character limits: name 30, subtitle 30, promotional text 170, keywords 100 (comma separated, no spaces needed),
description 4,000. Keywords leave out the app's own name (it is indexed already), other apps' names and trademarks.

## Tapefolio

### Listing

| Field | Value |
|-------|-------|
| Name | Tapefolio |
| If "Tapefolio" is taken | Tapefolio: Transcribe on Mac (28). The scope doc's "Tapefolio: Private Transcription" is 32, over the limit. |
| Subtitle | Private, on-device transcripts (30) |
| Bundle id | `llc.purplelink.tapefolio.appstore` |
| SKU | `tapefolio-mac` |
| Primary category | Productivity |
| Secondary category | Education |
| Price | Free download, with in-app purchases |
| Support URL | https://purplelink.llc/tapefolio/ |
| Marketing URL | https://purplelink.llc/tapefolio/ |
| Privacy policy URL | https://purplelink.llc/privacy/ |
| Terms of use | Apple's standard EULA, https://www.apple.com/legal/internet-services/itunes/dev/stdeula/ (the purchase sheet links it: `Sources/TapefolioApp/AppStoreLicense.swift`) |
| Copyright | 2026 Purplelink LLC |
| Keywords | transcribe,interview,qualitative,research,speakers,diarization,ocr,dictation,redact,offline,call (96) |
| Minimum macOS | 26.0, Apple silicon (`LSMinimumSystemVersion` in `scripts/make-app.sh`; SpeechAnalyzer needs 26) |

Promotional text (167):

> Transcribe interviews and calls on your Mac, label the speakers, replace names with codes before you share, and read scans into text. Your recordings are not uploaded.

Description:

> Tapefolio transcribes interview and meeting recordings on your Mac, labels the speakers, helps you replace names and other identifiers, and reads scanned pages and photos into searchable text. Your files are not uploaded.
>
> TRANSCRIPTION
> Open audio files or record from the microphone, and Tapefolio transcribes on your Mac with the time of every word. It starts with Apple's on-device speech recognition. Better models are optional downloads in Settings: NVIDIA Parakeet for English, Whisper base for English, and Whisper large-v3 turbo for many languages. You can delete any of them.
>
> SPEAKERS
> Tapefolio labels who is speaking. In the review screen you name each speaker once and merge two labels that are one person. Speaker memory is optional and off until you turn it on for a project and record a consent note; voices are stored encrypted on your Mac and you can delete them.
>
> REVIEW AGAINST THE AUDIO
> The review screen plays the recording beside the text and highlights the word being spoken. Find any word and jump the audio to it. A word list of names and jargon helps the recognizer spell them.
>
> IDENTIFIER REMOVAL
> Tapefolio finds names, places, organizations, emails, phone numbers, addresses, links, ID numbers and dates of birth, and replaces them with consistent codes. You decide case by case. The key that maps codes back is saved in a separate file. It misses some identifiers, so read the result before you share it.
>
> CALL RECORDING
> Record a video call with the call's sound on its own track beside your microphone. No bot joins the call. You start and stop it yourself, and before each call Tapefolio asks you to confirm that everyone agreed to be recorded.
>
> DICTATION
> Press Control-Option-Space in any app, speak, and press it again. The text is transcribed on your Mac and typed where the cursor is, or left on the clipboard if you do not allow that. The audio is deleted once it is transcribed.
>
> DRAFT SUMMARY
> On a Mac with Apple Intelligence, Apple's on-device model writes a short overview and a list of topics with times. A quote is shown only when it matches the transcript word for word.
>
> BATCH OCR
> Read photos, scans and PDFs, one file or a folder, into a searchable PDF, text, Markdown, Word, JSON or CSV. Two-column pages keep their reading order.
>
> EXPORT
> Word, HTML, Markdown, plain text, SRT, VTT, JSON, and a timestamped Word file for qualitative analysis software.
>
> AI APPS (OPTIONAL)
> AI apps that support the Model Context Protocol can search and read your saved transcripts, read only, with identifiers replaced by codes by default. It is off until you add Tapefolio to that app. What the AI app reads goes to that app's own servers.
>
> WHAT IT WILL NOT DO
> It will mishear words and mislabel speakers; check anything you quote against the recording. Identifier removal does not anonymize a transcript or make a study compliant.
>
> PRICE
> Free to download. Start the free 7-day trial in the app to use everything; nothing is charged and nothing renews. Then unlock Tapefolio with a single in-app purchase. A license key from purplelink.llc does not unlock this edition.

What's new (115):

> First release on the Mac App Store. Start the free 7-day trial from the app, then unlock Tapefolio once to keep it.

Why the copy is worded this way:

- No third-party product names beyond the model credits (NVIDIA Parakeet, Whisper), which say what is downloaded. The
  product page names Claude Desktop, Zoom, Teams, Meet, FaceTime and MAXQDA; the listing says "AI apps that support the
  Model Context Protocol", "a video call" and "qualitative analysis software" instead, to stay clear of guidelines
  2.3.7 and 5.2.1 (other parties' names and trademarks in metadata).
- The accuracy figures on the product page are left out. They are measured, but a listing cannot carry their caveats.
- "Not uploaded" holds for the App Store edition: there is no `URLSession` in `Sources/`; the only network use is the
  model downloads that FluidAudio and WhisperKit make from Hugging Face. The direct edition's update check is compiled
  out.

### In-app purchases

| Product id | Type | Reference name | Display name | Price | Family Sharing | Description (55 max) |
|------------|------|----------------|--------------|-------|----------------|----------------------|
| `llc.purplelink.tapefolio.trial` | Non-consumable | 7-Day Trial | 7-Day Trial | Free | Off | Use every feature free for 7 days. Nothing is charged. |
| `llc.purplelink.tapefolio.unlock` | Non-consumable | Tapefolio Unlock | Unlock Tapefolio | $29.99 | On | Keep every feature of Tapefolio, with updates. |

The ids and the $29.99 price match `Sources/TapefolioCore/AppStoreEntitlement.swift` and `StoreKit/Tapefolio.storekit`
(a test checks that they agree). Each needs a review screenshot of Settings > Purchase at 2880x1800; Vitae's first
review screenshot was refused for its aspect ratio.

### Age rating

Every question answered None or No, which gives 4+: no parental controls or age assurance, no unrestricted web access
(the only downloads are fixed model files), no user-generated content shared with other people, no messaging, no
advertising, no mature themes, no medical or treatment information, no gambling, no contests. Basis: the app opens no
web view and has no account or sharing feature.

### App Privacy

**Data Not Collected.** Each data type, and why the answer is no:

| Data type | Answer | Rests on |
|-----------|--------|----------|
| Audio data (recordings, calls, dictation) | Not collected | Recorded and transcribed on the Mac; no networking code in `Sources/`. Dictation audio is deleted after transcription. |
| Other user content (transcripts, OCR text) | Not collected | Saved in the app's container. The MCP server answers a local client over stdio; what that client sends to its own servers is the user's choice in another app, not data Tapefolio transmits. |
| Biometric data (voice profiles) | Not collected | `SpeakerLibrary.swift` stores them encrypted with CryptoKit in the container; they are never exported. |
| Identifiers, usage data, diagnostics | Not collected | No analytics, crash reporter or telemetry: no such package in `Package.swift` (FluidAudio, WhisperKit, PurplelinkPII, and Sparkle in the direct edition only) and no such code in `Sources/`. |
| Purchases | Not collected | StoreKit transactions are read on the Mac; Purplelink receives only Apple's sales reports. |
| Contact info, location, financial, health, browsing, search | Not collected | None of these APIs is used. |

Model downloads from Hugging Face are an ordinary request for a fixed file and carry no user data, the same position
Vitae took for its lookups. Encryption: `ITSAppUsesNonExemptEncryption` is false; the only cryptography is Apple's
CryptoKit for data at rest, which is exempt.

### Review notes

> No account or sign-in is needed. Tapefolio is free to download; Settings > Purchase (or the sheet shown when a paid
> feature is used) has Start 7-Day Free Trial, Unlock Tapefolio and Restore Purchases. The trial is a free
> non-consumable named "7-Day Trial"; the 7 days count from its purchase date.
>
> To try transcription with no download, open any audio file (File > Open): Tapefolio uses Apple's on-device speech
> recognition. Speech models in Settings > Models are optional Core ML model files from Hugging Face; they are data,
> not code, and each can be deleted.
>
> Microphone: asked the first time you press Record or start dictation. System audio: asked the first time you record
> a call; call recording is started by the user for each call, after a sheet asking them to confirm that everyone on
> the call agreed. Dictation types into the front app only if the user allows it in Privacy & Security > Accessibility;
> if not, the text stays on the clipboard. Speaker memory (voice profiles) is opt-in per project, requires a recorded
> consent note, is stored encrypted on the Mac and is never exported.
>
> The AI apps tab in Settings explains an optional, read-only Model Context Protocol server: an AI app the user
> configures can start this app's own binary with `--mcp` to search saved transcripts. Tapefolio never edits another
> app's configuration; the user pastes it. No data leaves the Mac unless the user connects such an app.

## Keyfeel

### Listing

| Field | Value |
|-------|-------|
| Name | Keyfeel |
| If "Keyfeel" is taken | Keyfeel: Keyboard Sounds (24) |
| Subtitle | Real switch sounds as you type (30) |
| Bundle id | `llc.purplelink.keyfeel.appstore` |
| SKU | `keyfeel-mac` |
| Primary category | Utilities (matches `LSApplicationCategoryType` in `scripts/make-app.sh`) |
| Secondary category | Productivity |
| Price | Free download, with in-app purchases |
| Support URL | https://purplelink.llc/keyfeel/ |
| Marketing URL | https://purplelink.llc/keyfeel/ |
| Privacy policy URL | https://purplelink.llc/privacy/ |
| Terms of use | Apple's standard EULA (linked from the purchase window: `Sources/KeyfeelApp/AppStoreLicense.swift`) |
| Copyright | 2026 Purplelink LLC |
| Keywords | keyboard,sound,mechanical,typing,click,clicky,switch,asmr,haptic,trackpad,scroll,typewriter,menubar (99) |
| Minimum macOS | 13.0, Apple silicon or Intel; "quiet while other audio plays" needs 14.2 |

Promotional text (167):

> Recorded keyboard-switch sounds on every key press, plus click sounds, scroll ticks and trackpad haptics. It lives in the menu bar and stays quiet while the mic is on.

Description:

> Keyfeel plays recorded keyboard-switch sounds when you press a key on your Mac, and adds mouse-click sounds, scroll ticks and optional trackpad haptics. It runs in the menu bar and works offline.
>
> HOW IT WORKS
> With the Input Monitoring permission, macOS tells Keyfeel when a key goes down and comes back up. Keyfeel uses the key code, which says which key it was, and never the characters you type. When a password field has focus, macOS stops telling it anything.
>
> SOUNDS
> Recorded tactile, brown-switch and dome profiles, a buckling-spring keyboard, a fun set and a calm set for all-day typing, and synthesized extras such as a typewriter. Each press plays a different recording, each key has its own pitch, and the sound moves from left to right across the keyboard. On headphones, 3D sound places the keyboard in front of and below you.
>
> YOUR OWN SOUNDS
> Import a sound pack made for other keyboard-sound apps (its folder or its .zip, with a config.json), or choose a short sound file of your own.
>
> MOUSE, SCROLLING AND TRACKPAD
> Press and release sounds for clicks, a ripple where you click, and scroll ticks in nine styles that follow how fast you scroll. Optional haptic feedback on scroll and click, only while a finger is on the trackpad.
>
> SHORTCUTS
> Copy, paste, undo, save and seven more shortcuts can each have their own sound. Copy plays a softer sound when nothing was copied, so you hear whether it worked.
>
> QUIET WHEN IT SHOULD BE
> Silence in the apps you choose, automatic silence on the speakers while the microphone or a camera is in use, an option to stay silent in full-screen apps, and quiet hours. Headphones keep their own switch and volume.
>
> PER APP AND FAVORITES
> Pick a different sound for each app, star the sounds you like, and let Keyfeel move to the next favorite each day.
>
> CONTROL AND AUTOMATION
> A volume slider and sound picker in the menu bar, separate levels for keys, the space bar, modifiers, clicks and scrolling, and shortcuts you can record. Shortcuts actions turn Keyfeel on or off, mute it for a while, set the volume or choose a sound, and a Focus filter keeps it silent during a Focus you pick.
>
> PRIVACY
> No account and no analytics. Keyfeel uses the network only when you import a sound pack from a link, after you confirm the address. Settings > Privacy lists what Keyfeel looks at and shows live counts of the presses, clicks and scrolls it has been told about, which reset when it quits.
>
> PRICE
> Free to download. Start the free 7-day trial from the menu bar; nothing is charged and nothing renews. Then unlock Keyfeel with a single in-app purchase. A license key from purplelink.llc does not unlock this edition.

What's new (118):

> First release on the Mac App Store. Start the free 7-day trial from the menu bar, then unlock Keyfeel once to keep it.

Why the copy is worded this way:

- The product page's "Cherry MX Brown" and "IBM Model M" are other companies' trademarks; the listing says
  "brown-switch" and "buckling-spring" (guideline 5.2.1). The profiles keep their names inside the app. Rival apps
  (Mechvibes, Klack, Thock) are left out of the description and keywords; "thock" is not used as a keyword.
- The product page's sentence about the update check is left out: the App Store edition has none (`UpdaterService` under
  `MAS`).
- The connection list in Settings > Privacy is not promised in the listing; see "Sandbox checks added" below.

### In-app purchases

| Product id | Type | Reference name | Display name | Price | Family Sharing | Description (55 max) |
|------------|------|----------------|--------------|-------|----------------|----------------------|
| `llc.purplelink.keyfeel.trial` | Non-consumable | 7-Day Trial | 7-Day Trial | Free | Off | Use every feature free for 7 days. Nothing is charged. |
| `llc.purplelink.keyfeel.unlock` | Non-consumable | Keyfeel Unlock | Unlock Keyfeel | $9.99 | On | Keep every sound and feature of Keyfeel, with updates. |

The ids and $9.99 match `Sources/KeyfeelCore/AppStoreEntitlement.swift` and `StoreKit/Keyfeel.storekit`. Review
screenshot for each: the purchase window at 2880x1800.

### Age rating

Every question None or No, which gives 4+. The pack download from a link is not unrestricted web access: it fetches
one file at an https address the user confirmed, with cookies off and a size limit (`PackDownloader.swift`), and opens
no web view.

### App Privacy

**Data Not Collected.**

| Data type | Answer | Rests on |
|-----------|--------|----------|
| Keystrokes and other input | Not collected | `EventMonitor.swift` is a listen-only event tap reading key codes; nothing is kept beyond the in-memory counts shown in Settings > Privacy, and there is no network code apart from the pack downloader. |
| Usage data, diagnostics, identifiers | Not collected | No analytics or crash reporting; the only `URLSession` in `Sources/` is `PackDownloader.swift`. |
| Other user content (imported sounds) | Not collected | Converted into the container's Application Support folder; never uploaded. |
| Purchases | Not collected | StoreKit transactions are read on the Mac. |
| Camera | Not collected | Only whether some app is using a camera is read, in memory (`ContextMonitor.swift`); no image is captured. |
| Everything else Apple lists | Not collected | Not used. |

`ITSAppUsesNonExemptEncryption` is false (no cryptography beyond HTTPS for pack downloads, which is exempt).

### Review notes

> Keyfeel is a menu-bar app with no Dock icon: look for its symbol in the menu bar after launch. No account is
> needed. The menu has Start Free Trial (a free non-consumable named "7-Day Trial") and, after it, Unlock Keyfeel;
> Settings > General, License, has Restore Purchases.
>
> Keyfeel plays sounds for key presses, so it needs Input Monitoring (System Settings > Privacy & Security > Input
> Monitoring). It uses a listen-only event tap: it reads key codes to choose a sound, never characters, stores and
> sends nothing, and cannot change or block a key. macOS stops delivering events while a password field has focus.
> Without the permission Keyfeel stays silent and says why.
>
> Accessibility is optional and only used by two features that are off until the user turns them on: stopping scroll
> ticks at the end of a page (reads the scroll bar under the pointer) and the Mission Control / App Exposé sounds (reads
> the Dock's accessibility tree). Launch at login is off by default and only changes when the user flips the switch in
> Settings. Sound packs are audio files plus a JSON description; they are data, not code.
>
> The camera entitlement is used only to ask macOS whether another app is using a camera (CoreMediaIO's "running
> somewhere" property), so Keyfeel can stay silent during video calls. Keyfeel never opens a camera and never asks for
> camera access.

## Review risk, both apps

| Guideline | Tapefolio: how the sandboxed build answers | Keyfeel: how the sandboxed build answers |
|-----------|--------------------------------------------|------------------------------------------|
| 2.4.5(i) App Sandbox, only the entitlements needed | `app-sandbox`, `device.audio-input`, `network.client`, `files.user-selected.read-write`, `files.bookmarks.app-scope`; no temporary exceptions (`scripts/make-app.sh --mas`). Each has a feature that needs it (table in Tapefolio's `docs/mac-app-store-plan.md`). | `app-sandbox`, `network.client`, `files.user-selected.read-only`, and `device.camera` (from the branch below: only to see whether another app is using a camera; it never opens one); no exceptions. |
| 2.4.5(iii) no auto-launch without consent | No login item at all (no `SMAppService` in `Sources/`). | Off by default; `SMAppService.mainApp.register()` is called only from the Settings switch (`SettingsView.swift`). |
| 2.4.5(iv) no downloaded code or features | Speech models are Core ML weights, optional, deletable; Apple's recognizer works with none. Medium; the review note answers it. | Sound packs are audio plus JSON, imported only after a confirmation. Low. |
| 2.4.5(v) updates only through the App Store | Sparkle is not linked: `make-app.sh --mas` refuses a binary that links it. | Same. |
| 2.5.1 public APIs only | Core Audio process tap (`AudioHardwareCreateProcessTap`) for calls; `CGRequestPostEventAccess` for auto-paste. | `CGEvent.tapCreate(.listenOnly)`, CoreMediaIO, the Core Audio process list, AX reads of the Dock and scroll bars. All public. |
| 2.5.2 self-contained | The `--mcp` server is the app's own binary, read only, started by another app only after the user pastes its configuration. Low to medium; if App Review objects, the App Store edition can hide the AI apps tab with `#if MAS` and nothing else changes. | n/a |
| 3.1.1 in-app purchase | Free download; trial as a tier-0 non-consumable named "7-Day Trial" (the pattern 3.1.1 describes); unlock as a non-consumable; Restore Purchases present; no license-key field and no link to buy on the web in the App Store edition. | Same pattern. A `keyfeel://license/...` link opens the purchase window, not a key field. |
| 5.1.1 privacy and permission strings | Microphone, system audio and speech recognition usage strings are in the Info.plist and say when and why (`make-app.sh`). Post Event access (auto-paste) has no Info.plist string by design; the dictation panel says "Typing needs Accessibility access. Without it, the text is copied to the clipboard." next to its Allow button (`DictationView.swift`). Privacy policy URL set. | Input Monitoring and Accessibility have no Info.plist string by design; a permission window explains Input Monitoring before macOS asks (`AppDelegate.swift`), and Settings > Privacy lists both. Privacy policy URL set. |
| 5.1.1 / legal: recording other people | Call recording is started by the user per call, after a consent sheet. | n/a |
| 5.1.2 biometric data | Voice profiles: opt-in per project, recorded consent note, stored encrypted, never exported or uploaded. | n/a |
| Camera entitlement | n/a | Reviewers may ask why a keyboard-sound app has `device.camera`. The usage string and review note answer it: it reads only whether a camera is in use. Low to medium. If Ben prefers no camera entitlement, the alternative is hiding the camera option in the App Store edition. |
| Input monitoring | n/a | Listen-only tap, key codes not characters, nothing stored or sent. Other keyboard-sound apps are sold on the Mac App Store. Medium only because reviewers look hard at keystroke access; the review note answers it. |
| Accessibility | Optional, for auto-paste only; falls back to the clipboard. | Optional, for two off-by-default features. |
| 2.3.3 screenshots show the app | Existing captures are real windows. | The product page uses drawings, which cannot be used (see the screenshot plan). |

## Code changed for review

- **Keyfeel, a zip picked in the import panel** (branch `mas-zip-copy` in purplelink-llc/keyfeel). The sandbox grants
  a file picked in the open panel to Keyfeel, but not necessarily to `zipinfo` and `ditto`, which Keyfeel starts to
  check and unpack the archive. The App Store edition now copies the archive into its own container first and hands
  the tools the copy (`PackImporter.archiveForTools`); an archive larger than a pack may unpack to (300 MB) is refused
  before the copy. The direct edition is unchanged. Two new tests.
- **Keyfeel, camera in use** (same branch): the App Store edition adds `com.apple.security.device.camera` and an
  `NSCameraUsageDescription` ("Keyfeel never opens a camera..."), so CoreMediaIO lists the cameras; see "Sandbox checks
  added".
- **Keyfeel, Show connections** (same branch): no longer claims there are no connections when `lsof` was refused
  (`ConnectionsText` in `SettingsView.swift`, with a test).
- Keyfeel has no CI, so the branch is left as an open pull request for Ben. Tapefolio needed no code change for review.

## Sandbox checks added

Two checks were added to Keyfeel's read-only `--sandbox-report` and run on throwaway copies (`.handtest` bundle ids,
ad hoc signed, launched in the background), sandboxed and plain, on 2026-10-28:

| Check | Sandboxed, as merged in keyfeel#16 | Plain | Result |
|-------|------------------------------------|-------|--------|
| Camera list (CoreMediaIO), for "silent while a camera is in use" | 0 cameras | 3 cameras | The feature would never fire in the App Store edition. With `com.apple.security.device.camera` added, the sandboxed copy saw all 3, showed no camera prompt and opened no camera (it reads only whether a camera is running). The entitlement and an `NSCameraUsageDescription` that says this are on the branch; a rebuilt copy with them matched the plain copy (1 camera each on the rerun; the count moves as Continuity Camera devices come and go). |
| `lsof` on its own process, for Settings > Privacy > Show connections | refused: "Operation not permitted" | 24 lines | The window would have said "No network connections are open right now." when it had not looked. It now says macOS did not let it list them, and that this edition connects only for a pack download the user confirmed. |

Every other line of the report still matches between the two copies (the table in Keyfeel's
`docs/mac-app-store-plan.md`).

## Screenshot plan

What Apple accepts for a Mac app: 1 to 10 screenshots, PNG or JPEG, no transparency, 16:10 at one of 1280x800,
1440x900, 2560x1600 or 2880x1800. Use 2880x1800 throughout (Vitae's set), and the same size for each in-app purchase's
review screenshot. All captures come from a test copy with invented data, never Ben's screen or files.

### Tapefolio

| # | Screen | Exists? |
|---|--------|---------|
| 1 | Review screen with the audio player and highlighted word (demo interview) | Yes, `marketing/captures/review-main.png` in the Tapefolio repo (1960x1384). Needs a 2880x1800 canvas. |
| 2 | Identifier review, decisions made | Yes, `review-decisions.png` (2450x1616). Canvas only. |
| 3 | Redaction preview with codes | Yes, `review-preview.png` (2450x1616). Canvas only. |
| 4 | Export sheet | Yes, `export-sheet.png` (2450x1616). Canvas only. |
| 5 | Batch OCR results | Yes, `ocr-results.png` (2480x1560). Canvas only. |
| 6 | Call recording: the consent sheet and the two-track recorder | No. New capture (1.2.0 feature). |
| 7 | Dictation: the dictation panel over a text editor | No. New capture. |
| 8 | Draft summary with topics and times | No. New capture; needs a Mac with Apple Intelligence on. |
| 9 | Settings > Models | `settings-models.png` (1200x1296) shows the 1.0 list; recapture. |
| IAP | Settings > Purchase in the App Store edition, trial not started | No. Needed for both in-app purchases. |

The five existing captures date from 2026-10-09 (1.0.x); check the window chrome still matches 1.2.0 before using
them.

### Keyfeel

Keyfeel has no app screenshots: the product page uses drawings, which App Review does not accept. All captures are new:

| # | Screen |
|---|--------|
| 1 | The menu-bar menu open: on/off, volume, the sound list with play buttons (needs the menu-bar capture technique: a backdrop and a real click) |
| 2 | Settings > Sounds: the sound list, favorites and shuffle |
| 3 | Settings > Quiet: right now, quiet hours, stay quiet during calls, full screen and other audio |
| 4 | Settings > Apps: apps where Keyfeel is silent, and a different sound in one app |
| 5 | Settings > Privacy: what Keyfeel looks at, the live counts, the permissions |
| 6 | Settings > General: the License section in the App Store edition, the delay readout |
| IAP | The purchase window (`AppStorePurchaseWindow`) in the App Store edition, trial not started |

Settings windows are small; place each on a 2880x1800 canvas with a plain background and one line of caption, as
Vitae's set does.

## What Ben must provide

1. **Developer portal:** App IDs `llc.purplelink.tapefolio.appstore` and `llc.purplelink.keyfeel.appstore` (In-App
   Purchase on), and a Mac App Store Connect profile for each. The installer certificate made for Vitae is reused.
2. **App Store Connect:** the two app records with the names above (or the fallbacks if taken) and the four in-app
   purchases from the tables. The Paid Apps agreement is already active from Vitae.
3. **Decisions:** keep the copy's choice to leave rival and trademark names out (or say which to put back); confirm
   Family Sharing on for both unlocks.
4. **Hands-on checks only a person can do,** on TestFlight copies:
   - Tapefolio: the System Audio Recording prompt and one real call; auto-paste approval; a folder picked in Settings >
     AI apps read by `--mcp` after a relaunch; trial, unlock and Restore Purchases with a Sandbox account.
   - Keyfeel: Input Monitoring granted and key sounds heard; Accessibility granted and the scroll-edge stop; a `.zip`
     picked in the import panel (the new branch); trial, unlock and Restore Purchases.
5. **Screenshots:** the new captures in the plan (Tapefolio 6 to 9 and its purchase screen; all of Keyfeel's), or a
   go-ahead for a session to stage them from test copies with invented data.
6. **Merge** the Keyfeel `mas-zip-copy` pull request after reading it (no CI in that repo), or say to drop the camera
   entitlement and hide that option in the App Store edition instead.
