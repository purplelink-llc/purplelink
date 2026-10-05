# Fact table: best disk space analyzer and cleaner for Mac

Checked 2026-10-04 (date held fixed for the guide, as in the sibling guides) for
`site/guides/best-disk-space-analyzer-for-mac/index.html`. Method: `competitive-landscape-research`.

Tiers: 1 = vendor's own site or documentation, the Mac App Store listing, an Apple support page or a local Apple man page /
tool help, or the project's own repository README; 2 = named independent source; 3 = aggregator or search summary (never
stated flatly in the article).

Reading notes:

- App Store facts: Apple's iTunes lookup JSON (`itunes.apple.com/lookup?id=`) for price, version, minimum macOS and release
  date, plus the rendered `apps.apple.com/us/app/id<ID>` page for the privacy label and the in-app purchase list. Prices
  are US storefront.
- Vendor pages were read with `curl` and tag stripping (rows marked "curl") or with WebFetch, which returns a model-written
  summary (rows marked "fetch summary"; the article words those conservatively). WebSearch summaries were used only to find
  URLs; every claim taken from one was re-read on the page itself.
- Local tools: `man tmutil`, `man du`, `xcrun simctl help delete`, `xcrun simctl runtime help` were read on a Mac running
  macOS 27.2. Only read-only commands were run (`tmutil listlocalsnapshots /`, `du`); no deletion command was run.
- Nothing here was installed or tested. The guide says so.
- No page returned 403 in this pass. `DaisyDisk` guide URLs from the guide's table of contents 404 under a guessed slug; the
  real slugs (`DeletingFiles`, `Snapshots`, `PurgeableSpace`, `WhatToDelete`) were found by search and read directly.
- Not confirmed live in 2026, so left out: PrunePanda (no product page or store listing found), SpaceSift (nothing found),
  Funter (App Store search returns only unrelated FUNTERU apps).

## macOS Storage settings, Optimize Storage, System Data (Apple)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Where | System Settings > General > Storage (macOS Ventura 13 or later) | 1 | support.apple.com/en-us/102624 (curl; page dated July 6, 2026) | 2026-10-04 | none |
| System Data | "a general category that measures the storage space used by all Apple and third-party files that don't belong to any more specific category" | 1 | same | 2026-10-04 | a search summary said "you can't manage the contents"; not on the page, not used |
| Recommendations | Store in iCloud; Optimize Storage (removes watched Apple TV movies and shows, keeps only recent mail attachments); Empty Trash automatically (items in the Trash more than 30 days) | 1 | support.apple.com/guide/mac-help/optimize-storage-space-sysp4ee93ca4/mac (curl) | 2026-10-04 | none |
| Automatic cache clearing | "When space is needed on your Mac, macOS also clears caches and logs that are safe to delete, including temporary database files, interrupted downloads, staged macOS and app updates, Safari website data, and more" | 1 | same | 2026-10-04 | none |
| Safe mode | Clears certain system caches, recreated as needed; may free enough for one task such as an update | 1 | support.apple.com/en-us/102624 | 2026-10-04 | none |
| Trash | Space is not available until you empty the Trash | 1 | same | 2026-10-04 | none |
| Purgeable | Available space "can include both free space and 'purgeable space', or space that macOS can free up when needed ... you can't manually remove the files that are designated purgeable" | 1 | support.apple.com/guide/disk-utility/get-detailed-information-about-a-disk-dskutl1005/mac (curl) | 2026-10-04 | none |
| Local snapshots | One about every hour, kept 24 hours; extra snapshot of last successful backup until space is needed; one before a macOS update; counted as available storage; deleted as they age or as space is needed; manual deletion: set Time Machine backups to manual for a few minutes | 1 | support.apple.com/en-us/102154 (curl, dated July 6, 2026) | 2026-10-04 | none |
| SIP | Protects /System, /usr, /bin, /sbin, /var and pre-installed apps; third-party installers can still write to /Applications, /Library, /usr/local | 1 | support.apple.com/en-us/102149 (curl, dated March 20, 2025) | 2026-10-04 | none |
| Old iPhone backups | Apple lists "delete old backups" among ways to free space | 1 | support.apple.com/en-us/102624 | 2026-10-04 | none |

## iCloud Drive, Optimize Mac Storage (Apple)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Setting | Apple Account > iCloud > Drive > Optimize Mac Storage; older documents are stored in iCloud when space is needed | 1 | support.apple.com/guide/mac-help/store-files-in-icloud-drive-mchle5a61431/mac, .../mchl1a02d711/mac (curl) | 2026-10-04 | none |
| Remove Download | Control-click an item, Remove Download; Keep Downloaded keeps it local | 1 | .../mchl1a02d711/mac | 2026-10-04 | none |
| Deleting | Deleting from iCloud Drive on one device removes it from every device on the same Apple Account; recoverable 30 days | 1 | support.apple.com/en-us/104953; support.apple.com/guide/icloud/delete-files-mm3b7fcd0c10/icloud (curl) | 2026-10-04 | none |
| Moving out | Dragging items out of iCloud Drive to a Mac folder "removed from iCloud Drive on all your devices" | 1 | .../mchl1a02d711/mac | 2026-10-04 | none |
| Cost | Uses iCloud plan storage; starts at 50 GB for $0.99 a month (US) | 1 | support.apple.com/en-us/102624 footnote | 2026-10-04 | prices vary by region |

## DaisyDisk

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | $9.99, one-time; "Minor updates & bug fixes included"; up to 5 personal Macs; 30-day money-back; free trial | 1 | daisydiskapp.com/pricing and homepage (curl); App Store lists $9.99 too | 2026-10-04 | none |
| Version | Site 4.34.2 (July 10, 2026, fetch summary); App Store 4.34.1 (2026-07-05) | 1 | daisydiskapp.com; itunes lookup id411643860 | 2026-10-04 | site and store differ by one patch release; article says "4.34" |
| macOS | 10.13 or newer (fetch summary; App Store minimum 10.13); homepage: Apple Silicon and macOS Golden Gate supported | 1 | homepage (curl); lookup | 2026-10-04 | none |
| Deletion | Collector; Delete button; 5 seconds to cancel; "permanently removes files and folders instead of moving them to the system Trash"; will not accept /System, /Library or the home folder | 1 | daisydiskapp.com/guide/4/en/DeletingFiles/ (curl) | 2026-10-04 | `brief` already said "Only you decide what to delete" (homepage, confirmed) |
| Snapshots, purgeable | Shows local snapshots under hidden space and can delete them; forced purge of purgeable space by dragging to Collector; both partly limited in the Mac App Store edition (no snapshot size estimate, snapshot deletion via Terminal, forced purge not available) | 1 | guide/4/en/Snapshots/ and /PurgeableSpace/ (curl; the purgeable page's limit sentence was cut off at "not available in the Ma", read as "Mac App Store edition") | 2026-10-04 | the PurgeableSpace sentence is truncated in my read; the Snapshots page states the MAS limits in full |
| Admin scan | Guide lists "Scanning as administrator" | 1 | guide index (curl) | 2026-10-04 | none |
| Privacy | "DaisyDisk doesn't collect or transmit anything and doesn't track you" | 1 | homepage (curl) | 2026-10-04 | none |
| FAQ on what is safe | Delete only what you recognize; use Photos, iTunes, Time Machine's own UIs for their data; built-in protection for critical system files | 1 | guide/4/en/WhatToDelete/ (search summary of the page; not re-read in full) | 2026-10-04 | search summary only for the exact wording, so the article paraphrases |

## GrandPerspective

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free via SourceForge; $2.99 on the Mac App Store, "same app either way" | 1 | grandperspectiv.sourceforge.net (curl); lookup id1111570163 | 2026-10-04 | none |
| Version, macOS | 3.8.1; site says September 13, 2026, App Store updated 2026-09-19; macOS 14.0 or later, Apple silicon and Intel | 1 | same | 2026-10-04 | store lags the site by days |
| License | Open source, GNU GPL | 1 | site | 2026-10-04 | none |
| Deletion | "Delete files and folders from the view"; page and help pages do not say Trash or permanent | 1 | site and HelpDocumentation pages (curl) | 2026-10-04 | not stated; article says so |
| Features | Treemap; color by name, type, folders, times; filters; save and export scans; Time Machine backup analysis via hard-link support | 1 | App Store description | 2026-10-04 | none |

## OmniDiskSweeper

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free | 1 | omnigroup.com/omnidisksweeper (fetch summary; curl) | 2026-10-04 | none |
| What it does | "shows you the files on your drive, largest to smallest, and lets you quickly Trash or open them" | 1 | same (curl) | 2026-10-04 | none |
| Version | Latest download redirects to OmniDiskSweeper-1.16.dmg under a `macOS/11` folder, file dated Sept 12, 2025 | 1 | omnigroup.com/download/latest/OmniDiskSweeper headers | 2026-10-04 | the page states no macOS requirement or version; "macOS 11" is the folder name only, so the article says that |

## Disk Inventory X

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Version, date | 1.3; copyright 2019 | 1 | derlien.com (fetch summary) | 2026-10-04 | none |
| License | Free, GPL | 1 | same | 2026-10-04 | none |
| macOS | Page lists macOS 10.13 to 10.15; Intel only is the summary's reading, not stated on the page | 1 | same | 2026-10-04 | article says "the page lists 10.13 to 10.15 and I found no newer build" |

## Nektony Disk Space Analyzer: Inspector / Pro

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free to download; Pro Mode in-app: $4.99 monthly, $9.99 annual, $19.99 lifetime. A separate listing, "Disk Space Analyzer Pro" (id488920185), is $19.99 | 1 | apps.apple.com id446243721, lookup | 2026-10-04 | two listings |
| Version, macOS | 6.0.2, 2026-06-26; macOS 11.0 or later | 1 | lookup | 2026-10-04 | none |
| Free vs Pro | Free: scan, sunburst, Quick Look, Show in Finder, list of 8 biggest items. Pro: remove the biggest files, sorted list, move and copy items | 1 | listing description | 2026-10-04 | none |
| Privacy label | Data Not Collected | 1 | listing (rendered page) | 2026-10-04 | self-reported, not audited |

## CleanMyMac (MacPaw)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price (App Store) | In-app list: Yearly $39.99; Plus Yearly $65.99; Plus Monthly $15.99; Monthly (7-day trial) $9.99; "CleanMyMac X One-Time Purchase" $89.99; app is free to download | 1 | apps.apple.com id1339170533 (rendered page) | 2026-10-04 | vendor page says "Starting at $3.33/month" (fetch summary) and "one-time purchase option"; the earlier brief reported $191.95 one-time from Capterra (tier 3, conflicting). Article: App Store figures, "vendor lists from $3.33 a month", no lifetime figure |
| Trial | 7 days; "After the trial, you'll be automatically charged" | 1 | listing | 2026-10-04 | none |
| Version, macOS | 5.6.0, 2026-08-21; macOS 11.0 or later | 1 | lookup | 2026-10-04 | vendor page also says "macOS 11+" |
| Space Lens deletion | Review and Remove list; "click Remove and wait while CleanMyMac deletes the items from your Mac"; Trash vs permanent not stated | 1 | macpaw.com/support/cleanmymac/knowledgebase/space-lens-cleanup (curl, updated August 6, 2026) | 2026-10-04 | a search summary claimed "moves to Trash"; the vendor page does not say so, so the article says not stated |
| Features | Junk, malware scan (Moonlock), uninstaller, duplicates and similar photos, large and old files, cloud storage cleanup, performance tools | 1 | listing | 2026-10-04 | none |
| Notarized | "Notarized by Apple" | 1 | listing and vendor | 2026-10-04 | none |
| Privacy label | Data Not Linked to You: contact info (email, with purposes including Developer's Advertising or Marketing), identifiers (device ID), usage data, diagnostics | 1 | listing | 2026-10-04 | self-reported |
| CLI | MacPaw/cleanmymac-cli, v1.0.0 2026-07-17, 1,012 stars, dev, Docker, Homebrew, AI-tool junk, analytics toggle in config, macOS 11+ and Homebrew | 1 | github.com/MacPaw/cleanmymac-cli (API, README) | 2026-10-04 | none |

## Disk Diag (Rocky Sand Studio)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free to download; removal of scan results limited to 1 GB monthly; "Unlimited Cleaning" $16.99 yearly or $44.99 one-time | 1 | listing id672206759 | 2026-10-04 | none |
| Version, macOS | 2.0.7, 2025-10-01; macOS 12 or later | 1 | lookup | 2026-10-04 | last update about a year old |
| Features | System, user, developer scanners; large files; applications; duplicates; dashboard; menu bar | 1 | listing | 2026-10-04 | none |
| Privacy label | Data Not Linked to You: email address and product interaction, with purposes including Developer's Advertising or Marketing | 1 | listing | 2026-10-04 | self-reported |

## Hazel (Noodlesoft)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Hazel 6 $42; Family Pack (up to 5 household members) $65; upgrade from earlier $20; free trial | 1 | noodlesoft.com/store (curl) | 2026-10-04 | none (matches the Oct 1 brief) |
| What it does | Watches folders, rules by name, date, type, source; deletes files that are too old; clears Trash when too big; App Sweep offers to remove support files of apps you trash | 1 | noodlesoft.com (fetch summary), manual pages | 2026-10-04 | none |
| Free space trigger | Not a built-in condition on the pages read; the manual's AppleScript/JavaScript page lists "The amount of free space on my disk is less than 10 GB" as something a script could check | 1 | noodlesoft.com/manual/hazel/attributes-actions/using-applescript-or-javascript/ (curl) | 2026-10-04 | I did not read every condition page; article says "not built in as far as I could find" |
| Preview | Live rule preview for a selected item, plus a rule status view of what matches a folder | 1 | manual, Preview a Rule (curl) | 2026-10-04 | not a dry-run list of what would be deleted; article says so |
| macOS requirement | not found on the pages read | - | - | 2026-10-04 | article omits |
| Alternative | Rulewright, $14.99, macOS 14.0, preview before run, sandbox-friendly, no Full Disk Access; Trash action | 1 | listing id6767625525 | 2026-10-04 | none |

## Mole

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| CLI | Free, GPL-3.0, `brew install mole`, macOS 12 or newer, Intel and Apple Silicon; v1.58.0 on 2026-10-05; 69,333 stars | 1 | github.com/tw93/Mole README and API; formulae.brew.sh | 2026-10-04 | brief said 68.9k stars on Oct 1; moved |
| Safety | `--dry-run` for clean, uninstall, optimize, purge, installer; "mo analyze moves selected items to Trash after confirmation"; clean can delete; operations log at ~/Library/Logs/mole/operations.log; whitelist; run without sudo | 1 | README | 2026-10-04 | none |
| App | Mole for Mac: $19 one-time, 2 Macs, 14-day refund, macOS 14+, free updates; "Scans and cleanup stay on your Mac; files and results are never uploaded"; "System folders stay view-only, and moving anything to Trash always asks for confirmation" | 1 | mole.fit (curl) | 2026-10-04 | none |

## AppCleaner, Pearcleaner

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| AppCleaner | Version 3.7 for macOS 15 and later (3.6.8 for 10.14 to 15.6); donate; "drop an application onto the AppCleaner window ... delete them by clicking the delete button"; Trash vs permanent not stated | 1 | freemacsoft.net/appcleaner (curl) | 2026-10-04 | none |
| Pearcleaner | Free, source-available, "On Hold", last release 5.4.3 on 2025-11-26; README warns pearcleaner.com is a fake site and itsalin.com is the only real one | 1 | github.com/alienator88/Pearcleaner README and API | 2026-10-04 | none |

## DevCleaner for Xcode

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; optional tips $1.99, $3.99, $9.99; GPL-3.0 source | 1 | listing id1388020431; GitHub | 2026-10-04 | none |
| Version, macOS | 2.8.0, 2025-11-17; macOS 14.0 or later | 1 | lookup | 2026-10-04 | README says "tested with macOS 14.x and Xcode 15.x" |
| Caveat | README: relies on "internal folder structures and undocumented features"; "make backup before use it" | 1 | github.com/vashpan/xcode-dev-cleaner README | 2026-10-04 | none |
| Cleans | Device support, archives, DerivedData, documentation cache, old simulator and device logs, old documentation downloads; includes a command line tool | 1 | README and listing | 2026-10-04 | none |
| Privacy label | Data Not Collected | 1 | listing | 2026-10-04 | self-reported |
| Simulators | `xcrun simctl delete unavailable` deletes devices not supported by the current SDK; `xcrun simctl runtime delete (<identifier>|--notUsedSinceDays <days>) [--dry-run]` | 1 | local `xcrun simctl help delete`, `xcrun simctl runtime help` on macOS 27.2 | 2026-10-04 | none |

## Terminal tools

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| du | `-h`, `-x` (stay on one file system), `-d depth`, `-c`; e.g. `du -hxd 1 ~ | sort -h` | 1 | local `man du` (macOS 27.2) | none |
| ncdu | Free, MIT, 2.9.2 (2025-10-24, Zig) or 1.22 LTS (C); Homebrew formula 2.9.2; built-in delete asks for confirmation by default; `-r` read-only | 1 | dev.yorhel.nl/ncdu and /ncdu/man; formulae.brew.sh | 2026-10-04 | none |
| gdu | Free, MIT, v5.38.0 (2026-10-05); `d` delete, `D` move to trash; `--no-delete` | 1 | github.com/dundee/gdu README; formulae.brew.sh | 2026-10-04 | none |
| dua-cli | Free, MIT, v2.45.1 (2026-09-30); Homebrew `dua-cli`; interactive mode `dua i`, multi-stage deletion, config can disable permanent deletion and trashing; `dua clean`: "Nothing is deleted automatically"; macOS APFS clone dedup option | 1 | github.com/Byron/dua-cli README; formulae.brew.sh | 2026-10-04 | `xzfc/dua-cli` (an old URL) 404s; correct repo is Byron/dua-cli |

## Time Machine snapshots and tmutil

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Verbs | `listlocalsnapshots mount_point`, `listlocalsnapshotdates`, `deletelocalsnapshots {mount_point or date}`, `thinlocalsnapshots mount_point [purge_amount] [urgency]` (urgency 1 to 4) | 1 | local `man tmutil` (dated 2015 in its footer) | 2026-10-04 | man page says "Several, but not all, verbs require root and Full Disk Access"; it does not mark these four as root-only. I did not run a deletion verb, so the article does not say whether they need sudo |
| This Mac | `tmutil listlocalsnapshots /` ran and returned only a header line (no snapshots) | 1 | local run, read-only | 2026-10-04 | n/a |

## Others (more tools)

| Product | Fact | Tier | Source | Checked |
|---|---|---|---|---|
| Gemini 2 | Free download; Yearly Access $19.99, Smart Cleanup $19.99; v2.10.2 (2026-09-07); macOS 10.13+; duplicates and similar photos; Duplicates Monitor | 1 | listing id1090488118 | 2026-10-04 |
| Stats | Free, MIT, v3.0.20 (2026-10-04), macOS 12+, lists disk utilization; 42,311 stars | 1 | github.com/exelban/stats | 2026-10-04 |
| iStat Menus 7 | $11.99, macOS 14.0+, v7.30 (2026-05-27), Bjango | 1 | lookup id6499559693 | 2026-10-04 |
| OnyX | Free (donations); a separate build per macOS version; 5.1.0 for macOS Golden Gate 27, Apple silicon, released September 15, 2026 | 1 | titanium-software.fr/en/onyx.html (curl) | 2026-10-04 |
| Lemon Cleaner (Tencent) | Open source (GPL v3 per repo), 6,338 stars, latest release v5.1.20 on 2025-10-22, last push 2026-05-08; repo description is in Chinese; features: duplicates, similar photos, disk space analysis, privacy cleaning | 1 | github.com/Tencent/lemon-cleaner | 2026-10-04 |
| Harbofly | Free, open source, notarized; auto-clean triggers include "when disk runs low"; default Trash; opt-in anonymous analytics; v1.12.2 (2026-09-09); 25 stars | 1 | github.com/carloshpdoc/Harbofly README and API | 2026-10-04 |
| Dustpan | Free, MIT; opt-in auto clean daily, weekly or when space is low; caches emptied in place, user files to Trash, project artifacts deleted permanently after confirmation; v0.1.3 (2026-09-30); 1 star | 1 | github.com/GabriPalmyro/dustpan | 2026-10-04 |
| ClearDisk | Free, MIT, macOS 14+, Trash first, "No data collection. No analytics"; v2.3.2 (2026-09-10); 709 stars | 1 | github.com/bysiber/cleardisk | 2026-10-04 |
| Spacie | Native disk analyzer, Apple Silicon, sunburst and treemap, duplicate finder; v1.4.1 (2026-07-15); 86 stars; license not asserted | 1 | github.com/AlexGladkov/Spacie | 2026-10-04 |
| mac-cleaner-cli | Free MIT CLI by guhcostan, v1.4.0 (2026-09-30), 1,989 stars; described as an open-source alternative to CleanMyMac | 1 | github.com/guhcostan/mac-cleaner-cli | 2026-10-04 |
| Disk Clean Kit | Listing is now "Free" with in-app options; earlier brief said $12.99 lifetime. Not covered in the article | 1 | lookup id6752879952 | 2026-10-04 |

## Legroom (Purplelink, own product, unreleased)

Sources: `/Volumes/Extreme SSD/Legroom/docs/superpowers/specs/2026-10-01-legroom-design.md` (spec, approved 2026-10-01), the
Legroom git repo (tags `m1-complete` to `m5-complete`; `main` = m5 plus icon assets at eadb78e; branch `m6` is checked out
and unmerged), `docs/growth-briefs/disk-space-app-feasibility-2026-10-01.md`. Tier 1 for our own product, but a spec is not
a shipped artifact; the article says "planned" unless a milestone is merged.

| Feature | Spec section | Implemented in Sources/ | Milestone / merged to main |
|---|---|---|---|
| Menu-bar free-space readout, boot volume, important-usage figure | 3 | yes (`Volume/`, `Monitor/`, `MenuBar/`) | M1, merged (m1-complete) |
| Low-space notifications with levels and hysteresis | 3 | yes (`Alerts/`, `Notifier.swift`) | M1, merged |
| Folder rules, guards, preview and approval, run log, triggers (schedule, below line, app quits) | 4 | yes (`Rules/`) | M2, merged |
| Developer cache presets, Recommended rules, project scan | 4.5 to 4.6 | yes (`Presets/`, `Recommendations/`, `Projects/`) | M3, merged |
| What Grew snapshots, ranked growth, hidden space, Suggestions | 5, 5a | yes (`Growth/`, `Suggestions/`, `Probes/`) | M4, merged |
| Space Map (sunburst, Trash from the map) | 6 | yes (`SpaceMap/`) | M5, merged |
| Large, old, duplicate finder | 7 | yes on branch `m6` only (`Finder/`); not on main; its safety review stopped early with six unresolved mutation survivors (docs/superpowers/plans/2026-10-04-m6-safety-review-findings.md) | M6, not merged |
| Uninstaller and orphan finder | 8 | no (grep finds only copy mentioning it in Space Map text) | M7, not started |
| Desktop widget | 3, 14 | no (no WidgetKit target in project.yml or Sources) | M8, not started |
| Command-line tool (`legroom status`, `clean`, `grew`) | 2 | no (no CLI target) | M8, not started |
| Trial, license, Sparkle | 9 | no (`FeatureGate` uses `AlwaysLicensed` placeholder; no Sparkle, no license key code) | M9, not started |
| Website, Stripe, download | 10 | no (no /legroom/ page exists) | M10, not started |
| Price plan | 1 | n/a | 7-day trial then $9 one-time, no subscription; readout, widget and alerts stay free; planned |
| Distribution plan | 1 | n/a | direct download, Developer ID, no Mac App Store build; planned |
| Minimum macOS | 2 | `project.yml` | macOS 14 |
| Whole-disk Space Map limit | 6 | yes | measures home and /Users/Shared only; on the developer's Mac 163 GB of 203 GB used showed as hidden (80 percent), spec section 6 deviations, 2026-10-04 |
| Privacy plan | 11 | partly (no analytics code found; privacy manifest present) | no analytics, no accounts, network only for Sparkle update check (Sparkle not yet integrated) |

Corrections to the brief checked while writing: the October 1 feasibility brief says DaisyDisk "does not clean
automatically" (correct) and lists CleanMyMac's one-time price as $191.95 from Capterra (tier 3, conflicts with the App
Store's $89.99 legacy one-time item; the article gives neither a one-time figure for the current CleanMyMac).
