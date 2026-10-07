# Consumer apps: where the buyers already are, and a 30-day plan (2026-10-07)

Scope: Legroom ($9.99 disk space), Keyfeel ($9.99 keyboard and mouse sounds), Vitae (free academic record app, Plus $2.99 a month or $23.99 a year), and the Mac Suite ($54.99). Research only. Nothing was posted, emailed, signed up for or changed.

Known inputs not repeated here: PRODUCT.md, the 2026-09-29 Reddit notes, the 2026-10-01 disk-space feasibility brief, the 2026-10-04 disk-analyzer fact table, `docs/directory-submissions.md` and the file names under `Outreach/`. Where this report overlaps an Outreach file (iOS Dev Weekly, MacStories, The Sweet Setup, Hacker Noon, Indie Hackers, LibGuides), it says so.

## How far to trust this report

- **Reddit's own pages could not be read by any tool.** Subreddit rules for r/macapps, r/MacOS, r/mac, r/MechanicalKeyboards, r/asmr, r/AskAcademia, r/GradSchool, r/academia, r/Professors and r/postdoc came from a Redlib mirror (redlib.groet-infra.nl, read 2026-10-07), a ThreadOtter summary, or search snippets. The r/PhD tool policy was read through the Reddit MCP tool and is first-hand. Read every rule on reddit.com yourself before posting. Each such claim below is marked "second-hand".
- **Reddit dates are inferred** from post IDs (calibrated against the October App Pile, about 2026-10-01, and posts with known dates) or from mirror timestamps. Treat "about" as plus or minus one day.
- **The web-search budget (200 calls) was exhausted in all four research passes.** Gaps are listed at the end. "Not found" means not found in what was read, not that it does not exist.
- **Visit estimates in the plan are my judgment**, built from the few data points cited. No dataset for small paid Mac utilities was found.

---

## Findings that change the plan

1. **Legroom has a near-identical rival that launched two days ago.** DiskFox is $9.99 one-time with a 14-day trial, keeps a scan timeline, explains likely causes and warns if cleaned items regrow (diskfox.app, announced on r/macapps about 2026-10-05, https://www.reddit.com/r/macapps/comments/1wyeery/). StorageRadar is free with Core $9.99 and Developer $19.99, 27 developer profiles, dry runs and snapshot diffs (storageradar.app; dev post about 2026-09-22, https://www.reddit.com/r/macapps/comments/1wnbuoq/). Legroom's "What Grew" and "preview then approve" are no longer unique in the $10 band. The page copy should lead with whatever is still true only of Legroom (a free-space line with low-space alerts and rules that fire when space drops below it, plus a whole-disk Space Map that hatches what it could not read).
2. **The disk-space question is spiking right now.** macOS 27 ("Golden Gate") shipped recently and r/MacOS and r/mac have many "System Data" and "Apple Intelligence takes 20 to 30 GB" threads from 2026-10-04 to 2026-10-07. A tool that strips Apple's models drew 1,199 points and 107 comments on r/mac about 2026-10-06 (https://www.reddit.com/r/mac/comments/1wyyht4/). The window is days to a few weeks. Legroom engagement should happen this week, not in week 3.
3. **r/MechanicalKeyboards bans this kind of post.** Rule 2 (second-hand, wiki rules via mirror): "We are no longer allowing the promotion of typing extensions, sites, or games", and its title also excludes "Typing Apps or Extension Promotion" (https://redlib.groet-infra.nl/r/MechanicalKeyboards/wiki/subreddit_rules). Do not post Keyfeel there. The largest keyboard community is closed to it.
4. **Keyfeel is the highest-priced app in its category.** Klack $4.99 lifetime (https://tryklack.com/faqs), KeyBell lifetime $4.99 or $9.99 in-app, FunKey $3.99, Keyboard Typing Sound $2.99, TypeLouder $2.99, Click $2.99, Clacksmith $1.49, Thock and Mechvibes free, Haptyk $8 after a 3-day trial, Snick $6.99, Typemac $7 (third-party only). Keyfeel's justification has to be breadth: recorded switch sounds plus mouse, scroll textures, trackpad haptics, Mechvibes pack import and automatic silence while the microphone is in use. Do not describe it as better than Klack.
5. **Thock is broken on macOS 27 and nobody has fixed it.** A 2026-09-19 thread reports silence on macOS 27.0 with Thock 1.23.0 (last release 2026-03-28); the asker "moved on", and commenters say Klack works on macOS 27 (https://www.reddit.com/r/macapps/comments/1wkkihk/). **Before engaging, confirm Keyfeel is tested on macOS 27.** Keyfeel's page says macOS 13 or later; nothing found says it was tested on 27.
6. **Reddit is the wrong place for Vitae.** r/PhD's Feb 2026 tool policy welcomes a personal project only if it has no "free trial" button or "free tier"; Vitae has a free tier. r/AskAcademia removes "thinly veiled pitches for products". r/Professors rule 6 covers "advertising your own or others content". The workable routes are essays, library and faculty-development pages, and Mac channels (r/macapps App Pile, Mac directories).
7. **The best-documented discovery route for a direct-download Mac app is the r/macapps monthly App Pile**, where developers post `Problem / Comparison / Pricing` and say "I'm the developer". One developer reported that 15 of his 25 paid unlocks came in the week after a post there (StorageRadar dev, about 2026-09-22; self-reported, not verified). The sub reports 250,000+ members.
8. **Directories that list menu-bar apps exist and are cheap**: MacMenuBar.com, On My Menubar, TryMacApps, Indie App Catalog (non-store form). Both Legroom and Keyfeel are menu-bar apps.

---

## 1. Disk space and cleanup (Legroom)

### 1.1 Competitors and prices (new facts only; dates are when read)

Already on file and not repeated: DaisyDisk, GrandPerspective, OmniDiskSweeper, CleanMyMac App Store prices, Hazel, Mole, Nektony, Disk Diag, Gemini 2, iStat Menus, Harbofly, Dustpan, ClearDisk.

| App | Price and model | Notes | Source and date |
|---|---|---|---|
| DiskFox | $9.99 one-time, 14-day trial, no card | v1.0.9, macOS 14+. Scan timeline, explains likely causes, warns if cleaned items regrow, 60+ known locations. Positions against DaisyDisk and CleanMyMac. A user saw less free space than System Settings; the cause was about 51 GB of purgeable space. | diskfox.app; https://www.reddit.com/r/macapps/comments/1wyeery/ (about 2026-10-05) |
| StorageRadar | Free tier; Core $9.99; Developer $19.99; no subscription | macOS 15+. Mac App Store plus direct key. 27 developer profiles, dry runs, snapshot diffs. Dev reported about 240 first-time downloads and 25 paid unlocks since April, about $300 after Apple's cut. | storageradar.app; https://www.reddit.com/r/macapps/comments/1wnbuoq/ (about 2026-09-22; self-reported) |
| McCleaner | EUR 1.99 per clean, EUR 4.99 for 5, EUR 12.99 a year, EUR 24.99 lifetime ("launch pricing") | macOS 13+, Apple silicon. Scan free. Targets "System Data". Sorts findings Safe, Caution, Advanced. | mccleaner.tech (read 2026-10-07) |
| Disk Drill (Cleverfiles) | Pricing page lists Lifetime, One-Year, a free Basic edition and Enterprise, with no dollar amounts. Search snippet only: Pro $89.99 (or $118 with lifetime upgrades). | Mainly data recovery; free edition bundles disk analysis, space hogs, duplicates. Not a direct rival. | https://cleverfiles.com/pro.html (read 2026-10-07); price snippet only |
| OnClean | $5.99 one-time | Show HN 2026-03-24 | https://onclean.onllm.dev/ |
| Trace 2.0 | "Lifetime", amount not found | Analyzer plus uninstaller | https://www.reddit.com/r/macapps/comments/1wo9mrw/ (about 2026-09-22) |
| DiskScanPro | $1.99 | Analyzer plus duplicate finder | September roundup https://www.reddit.com/r/macapps/comments/1wzts9p/ |
| DiskPress, App Archiver | "Lifetime", amounts not found | Compression and dedup | https://www.reddit.com/r/MacOSApps/comments/1wsm79j/ |
| Hyperspace | Scan free, reclaiming paid (commenter); price not read | Mac App Store dedupe | https://www.reddit.com/r/MacOS/comments/1wylv46/ |
| Headroom | Free, MIT, macOS 14+ | Markets "what is safe to delete" verdicts | headroom-app.org |
| Radix | Free, MIT, macOS 14+, 913 GitHub stars | Compares scans over time | https://github.com/colinvkim/Radix |
| Purge, OpenDisk, Mac Sai, DuckDisk, NeoDisk | Free (Purge: "over 25k downloads" per its listing in the roundup) | OpenDisk 152 votes in the September roundup | https://www.reddit.com/r/macapps/comments/1wzts9p/ |
| Mole for Mac | $19 for two Macs (dev confirms) | Dev's own post, about 2026-10-06 | https://www.reddit.com/r/macapps/comments/1wz36bh/ |
| Lemon Cleaner | Free, GPL | Latest release v5.1.20, 2025-10-22, about 11.5 months old | GitHub releases API, 2026-10-07 |
| Pearcleaner | Free, "On Hold" | Latest release 5.4.3, 2025-11-26. A 2026-09-14 thread says it and AppCleaner "haven't been updated in quite a while" (https://www.reddit.com/r/macapps/comments/1whcmaf/) | GitHub API, 2026-10-07 |
| AppCleaner | Free (donation) | v3.7 for macOS 15 and later; no macOS 27 note on the page | freemacsoft.net, 2026-10-07 |
| Funter | Free hidden-files tool | Not a rival | https://nektony.com/funter |
| Sensei (Cindori) | Free download, paid upgrade, no price on the page | Monitor plus cleanup | https://cindori.com/sensei |

### 1.2 What people complain about

Paraphrased, with source and date.

1. **CleanMyMac billing and support.** Trustpilot reviews dated 2026-09-10 and 2026-09-19 describe repeated charges and slow support; one claims "$23+ for cancelling", and MacPaw replied it charges no cancellation fee. Overall rating mix 85% 5-star, 9% 1-star, so the sample is mixed. https://www.trustpilot.com/review/macpaw.com (fetch summary).
2. **Price.** A Hacker News commenter, 2026-03-24, says about $40 a year for deleting caches is too much. https://news.ycombinator.com/item?id=47502533
3. **Trust and permissions.** A commenter, 2026-02-02, hesitates to give CleanMyMac elevated permissions because of the vendor's Russian-linked developers and political messaging. https://news.ycombinator.com/item?id=46851745
4. **Vendor reputation.** 2025-12-22 comment dismisses MacPaw for "questionable ethics" (https://news.ycombinator.com/item?id=46354385); 2025-03-04 comment says even paid CleanMyMac leaves remnants after uninstalling (https://news.ycombinator.com/item?id=43249764). No 2026 adware thread was found; the reputation shows up as distrust and "who should I trust?".
5. **Cleaners deleting too much.** The Mole developer says some rules had to "remove less" (shared vendor folders); a commenter warns never to touch Containers and Group Containers. About 2026-10-06, https://www.reddit.com/r/macapps/comments/1wz36bh/. A commenter says Pearcleaner "once cleaned too much", about 2026-09-14, https://www.reddit.com/r/macapps/comments/1whcmaf/.
6. **System Data explains nothing.** A user with 173 GB of it says it "doesn't tell you which app is responsible", about 2026-10-04, 144 comments, https://www.reddit.com/r/MacOS/comments/1wxmd39/. A user with 188 GB, 57.6 GB of it Xcode caches, 2026-01-26, https://news.ycombinator.com/item?id=46763690. 250 GB hidden in Podcasts, 2026-03-03, https://news.ycombinator.com/item?id=47237939. Eclectic Light readers call the Storage panel "next to useless", article 2025-02-11, https://eclecticlight.co/2025/02/11/what-is-system-data-in-storage-settings/.
7. **Paying a third party to fix Apple's reporting.** A commenter, 2026-01-26, says DaisyDisk works but you buy an extra app "to fix Apple's mess". https://news.ycombinator.com/item?id=46763796
8. **Free space numbers disagree** between tools and System Settings because of purgeable space (the DiskFox thread above, about 2026-10-05). Legroom's page already shows "the space macOS says it can clear" beside free space.
9. **Subscription fatigue.** A Mole user: Nektony's "subscription model doesn't work for me" (https://www.reddit.com/r/macapps/comments/1wz36bh/, about 2026-10-06). A 314-vote "Setapp has been completely enshittified" thread is listed in the September roundup (not opened).
10. **Distrust of AI-written cleaners.** "Vibe coded and costs money" about Mole, and "who should I trust?" from the asker (https://www.reddit.com/r/MacOS/comments/1wze1b4/, about 2026-10-06); "I would not trust a space saver hardlinker if it is vibed" (https://www.reddit.com/r/MacOSApps/comments/1wsm79j/, about 2026-09-28). If Legroom was built with AI help, expect this and answer it with what is checkable (preview before every delete, Trash-or-delete shown per rule, no network use apart from the update check).
11. **DaisyDisk does not say what is safe.** No direct complaint thread found. The only evidence is the DiskFox developer's claim that DaisyDisk "maps what's on your disk right now".

### 1.3 Search phrases and where the questions appear

| Exact phrase (the asker's words or title) | Example | Date |
|---|---|---|
| "System Data 160GB HELP" | https://www.reddit.com/r/mac/comments/1wz8yz8/ | about 2026-10-06 |
| "Is there a real way to remove all this system storage??" | https://www.reddit.com/r/MacOS/comments/1wxmd39/ | about 2026-10-04 |
| "System Data ballooning after macOS 27 Golden Gate" | https://www.reddit.com/r/MacOS/comments/1wz3z5d/ | about 2026-10-06 |
| "Apple Intelligence taking up around 30GB" | https://www.reddit.com/r/MacOS/comments/1wztkf9/ | about 2026-10-07 |
| "How much storage is Golden Gate/ MacOS normally supposed to take up?" | https://www.reddit.com/r/MacOS/comments/1wzfv7d/ | about 2026-10-06 or 07 |
| "Why does Safari take up 120GB of Space" | https://www.reddit.com/r/MacOS/comments/1wzsevr/ | about 2026-10-07 |
| "Is there a good app to see the largest files / cash on your drive?" | https://www.reddit.com/r/MacOS/comments/1wylv46/ | about 2026-10-05 |
| "which app is the best to free up the storage on a mac?" (title "storage issue") | https://www.reddit.com/r/MacOS/comments/1wze1b4/ | about 2026-10-06 or 07 |
| "Using External SSD to ease my storage woes" ("System Data & OS use up to half") | https://www.reddit.com/r/mac/comments/1wz571n/ | about 2026-10-06 |
| "I seriously need remove the System Data" (iPad, same wording) | https://www.reddit.com/r/applehelp/comments/1wzaogk/ | about 2026-10-06 |
| "What is System Data in Storage Settings?" | https://eclecticlight.co/2025/02/11/what-is-system-data-in-storage-settings/ | 2025-02-11 |
| "understand what's filling your Mac" (Show HN) | https://news.ycombinator.com/item?id=47523979 | 2026-03-25 |
| Apple Community: "Files/folders keep getting offloaded even though the folder is set to 'Keep Downloaded'" | https://discussions.apple.com/thread/256350453 | undated, 4 replies |

Words that recur in answers: "Calculate all sizes", "tmutil listlocalsnapshots", "local Time Machine snapshots", "Caches", "Xcode DerivedData and simulators", "Apple Intelligence models", "purgeable". Regulars say the question is asked "ten times a day" (r/mac 1wz8yz8, r/MacOS 1wxmd39, r/MacOS 1wzfv7d). r/applehelp keeps a disk-tools wiki page (r/applehelp/wiki/mac_disk_other) that a commenter cites; it was not opened, and being listed there may matter. Not searched or not reachable: MacRumors forum threads (403), Ask Different (blocked), Mac Observer, Mac Kung Fu. Apple Community had no System Data thread in the listings read.

### 1.4 Rules on promotion

| Venue | What was found | Status |
|---|---|---|
| r/macapps | Developers must disclose. Apps outside the Mac App Store, or without enough "Trust or Transparency", promote only in the monthly App Pile, format Problem / Comparison / Pricing, comparison must name competitors, pricing must include a link. Promotion limited to once per 30 days per developer; an App Pile post counts toward that. About 10 sub karma needed before promoting in comments. | Second-hand: mirror sidebar summary, ThreadOtter (https://www.threadotter.com/subreddit-rules/macapps, last checked July 2026), search snippet of the App Pile post. The tier definitions were not found. Whether the 30-day limit is per developer or per app is unclear. |
| r/MacOS | "Promotional posts are ONLY allowed on Saturdays (UTC)", whitelisted domains only, 11 rules. | Second-hand: mirror sidebar. ThreadOtter says commercial or repeated self-promotion needs modmail first. Observed 2026-10-04 to 07: disclosed replies by the McCleaner and Headroom developers stayed visible in storage threads; one comment in https://www.reddit.com/r/MacOS/comments/1wze1b4/ shows "[removed]", reason unknown. |
| r/mac, r/applehelp | No clear position on links in the ThreadOtter summaries. | Second-hand, weak. |
| r/MacOSApps | Exists; developers post there. Rules not found. | |
| Apple Community | "Do not use the Site to sell or market products or services to others and do not post a URL unless it directly answers a user's question." Also bans submissions made solely to advertise software and links to personal or professional sites. | First-hand text via fetch summary of https://discussions.apple.com/terms (effective date shown as 2026-08-11). A developer reply with your own product is effectively not allowed. |
| MacRumors forums | Self-promotional links limited to signature and profile; new users should not post self-links. Mac and iOS developers may promote in their own threads in designated forums, identifying themselves. | Search snippet only; both Zendesk pages returned 403 (https://macrumors.zendesk.com/hc/en-us/articles/201294426-Guidelines-for-Software-Developers). |
| Ask Different / Stack Exchange | Not found. The help pages were blocked. No 90/10 wording was verified. | |
| Reddit sitewide 10 percent | Reddit's own pages returned 403. A secondary source says sitewide enforcement of the "1 in 10" rule ended 2017-05-16 and it survives as a reddiquette rule of thumb (https://redreplier.com/blog/reddit-self-promotion-rule); another snippet conflicts. Treat 10 percent as a convention, not a verified policy. | Unresolved |

**A pattern to avoid.** The McCleaner account posts a near-identical "Disclosure: I develop McCleaner" paragraph in at least seven threads in two days, twice in one thread, and discloses only in some replies. That is the behavior moderators remove and readers screenshot.

### 1.5 Ten threads where a disclosed developer reply could be legitimate and useful

Dates are inferred. Comment counts from listings read 2026-10-07. Order is by fit.

| # | Thread | Date | Question | Why a disclosed reply fits and what it must contain |
|---|---|---|---|---|
| 1 | r/mac "System Data 160GB HELP" https://www.reddit.com/r/mac/comments/1wz8yz8/ (21 comments) | about 10-06 | Deleted apps, has not checked folder sizes | Needs a way to see which Library folders are big and which are safe. Give the manual method first (Finder "Calculate all sizes", `tmutil listlocalsnapshots /`), then disclose Legroom in one sentence. |
| 2 | r/MacOS "System Data ballooning after macOS 27" https://www.reddit.com/r/MacOS/comments/1wz3z5d/ (18); cross-post https://www.reddit.com/r/mac/comments/1wz3x6a/ (12) | about 10-06 | System Data 20 to 64 GB, Apple Intelligence 20 GB | No tool recommended yet. Explain how to find growth; say what What Grew does and does not see (it reports local snapshots as "size not reported"). |
| 3 | r/MacOS "Why does Safari take up 120GB" https://www.reddit.com/r/MacOS/comments/1wzsevr/ (5) | about 10-07 | Safari shows 120 GB after clearing caches | Folder-level "what is this" question, still open. Name the real folders, offer Space Map as one way to see sizes. |
| 4 | r/MacOS "which app is the best to free up the storage on a mac?" https://www.reddit.com/r/MacOS/comments/1wze1b4/ (23) | about 10-06 or 07 | Open tool ask; asker later says "who should I trust?" | Strong fit for a trust-forward reply: who you are, $9.99 with a 7-day trial, what it will not delete, free alternatives named (Mole CLI, GrandPerspective, OmniDiskSweeper). Caveat: a disclosed developer reply already sits there and one comment is removed. |
| 5 | r/mac "Using External SSD to ease my storage woes" https://www.reddit.com/r/mac/comments/1wz571n/ (10) | about 10-06 | Moving files to an external SSD; System Data stays 60 to 80 GB | Answer the SSD question first; add a disclosed note about finding what is in the 60 to 80 GB. |
| 6 | r/MacOS "How much storage is Golden Gate normally supposed to take up?" https://www.reddit.com/r/MacOS/comments/1wzfv7d/ (5) | about 10-06 or 07 | 75 GB System Data after a full reset | Lightly answered. Short reply with disclosure. |
| 7 | r/MacOS "Is there a good app to see the largest files" https://www.reddit.com/r/MacOS/comments/1wylv46/ (30) | about 10-05 | Explicit tool request, 30 GB free of 500 GB | Heavily answered, and the McCleaner developer replied twice. Only reply if you add something new, such as per-rule preview and Trash-or-delete shown before anything is removed. |
| 8 | r/MacOS "Apple Intelligence taking up around 30GB" https://www.reddit.com/r/MacOS/comments/1wztkf9/ (11) | about 10-07 | Why 30 GB when Apple says about 12 GB | Weak: a "why" question, not a tool request. Reply only with facts plus disclosure. |
| 9 | r/MacOS "Is there a real way to remove all this system storage??" https://www.reddit.com/r/MacOS/comments/1wxmd39/ (144) | about 10-04 | 173 GB of System Data | Highly visible but two disclosed developer replies exist and answers are exhausted. A late reply would be buried. Lowest priority. |
| 10 | r/macapps "[Megathread] The App Pile - October, 2026" https://www.reddit.com/r/macapps/comments/1wuoav5/ (130 comments, about 10-01) | about 10-01 | Not a question. The designated place for non-App-Store apps. | Not a "reply" but the lowest-risk placement. Use the PCP draft in section 5. |

Not usable: r/macmini 1wzid2q (a buying question), r/applehelp 1wzaogk (an iPad), the free RemoveMacAI threads (replying would read as hijacking). Threads from 2026-08-01 to 2026-09-30 could not be listed because the Reddit tools return only the current hot list. Older storage threads are likely archived, since Reddit closes comments after about six months (general knowledge, not checked per thread).

**Weekly search to find new ones** (Reddit search, sort new, past week): `System Data`, `storage full`, `Apple Intelligence storage`, `disk space app`, `DaisyDisk alternative`, `CleanMyMac alternative`, `what is taking up space`. Add `purgeable` and `local snapshots`.

---

## 2. Keyboard sounds (Keyfeel)

### 2.1 Competitors (US App Store pages and vendor pages, read 2026-10-07; every App Store page shows "not enough ratings", so there are no star ratings to report)

| App | Price | Version and macOS | Sold | Source |
|---|---|---|---|---|
| Klack (Henrik Ruscon) | $4.99 lifetime; v1 to v2 free; direct and App Store licenses are separate purchases | App Store 2.1.4, "Updated May 26" (year not shown); App Store build needs macOS 15; v2 announced 2026-05-02 | tryklack.com (Stripe) and Mac App Store | https://apps.apple.com/us/app/klack/id6446206067; https://tryklack.com/faqs |
| Mechvibes (MIT) | Free | v2.3.4, 2023-12-08; repo says it "will become legacy" | GitHub, Homebrew | https://github.com/hainguyents13/mechvibes |
| MechvibesDX (MIT, Rust) | Free | v0.8.3 published 2026-10-07; macOS arm64 only, not notarized, "experimental" | GitHub | https://github.com/hainguyents13/mechvibes-dx |
| Thock (MIT) | Free | 1.23.0, 2026-03-28; 955 stars; macOS 13.5+ | GitHub, Homebrew | https://github.com/kamillobinski/thock |
| KeyBell | Free; lifetime $4.99 or $9.99 in-app | 3.1.3 (July 29); macOS 11+ | App Store | https://apps.apple.com/us/app/keybell-mechanical-keyboard/id1530838633 |
| Keyboard Typing Sound (CokeSoft) | $2.99 | 1.8; macOS 10.13+ | App Store | https://apps.apple.com/us/app/keyboard-typing-sound/id6499143902 |
| FunKey (Digital Hole) | $3.99 | 1.5 (Sep 12); macOS 13+ | App Store | https://apps.apple.com/app/id6469420677 |
| TypeLouder (sarunw.com) | $2.99 | macOS 15.5+ | App Store | https://typelouder.app/ |
| KeyClicker | Free; "All Access Lifetime" $1.99 | 2.9.0 (2025-09-24); macOS 14+ | App Store | https://apps.apple.com/us/app/keyclicker/id6740425504 |
| Click - Keyboard Sounds | $2.99 | 1.2.0 (2025-10-24); macOS 14+ | App Store | https://apps.apple.com/us/app/click-keyboard-sounds/id6740429323 |
| Klakk (a similar name, tryklakk.com) | App Store free with IAP $4.99 and $2.99; site $4.49 with a 3-day trial | 1.3.8 (March 17); macOS 14+ | App Store, direct | https://apps.apple.com/us/app/klakk-keyboard-sounds/id6754638652 |
| Tacque | Reddit post 2026-06-14: dev says free with tip jar; Setapp page says "from $4.99" (sources conflict) | macOS 15+ | App Store, Setapp | https://setapp.com/apps/tacque |
| Keeby, Typemac, CupertinoClicks | $4.99 / $7 (third-party only) / $4.99 direct, no trial | | various | https://www.cupertinoclicks.com/best-keyboard-sound-apps-mac (vendor-written, treat as marketing) |
| Haptyk | $8 after a 3-day trial; Apple Silicon only per its site (a Reddit summary says M2 or newer) | | direct | https://www.haptyk.com |
| Clacksmith | $1.49; needs no Input Monitoring or Accessibility permission | macOS 14+ | App Store | https://redlib.groet-infra.nl/r/MacOS/comments/1vv2evr/ |

**Haptics and scroll rivals.** Snick: scroll haptics plus scroll sounds, $6.99 lifetime, no trial (https://redlib.groet-infra.nl/r/macapps/comments/1uefe6f/, 2026-06-24). FeelMyMac: trackpad textures, lifetime (amount not verified), 252-comment launch thread 2026-09-27, #2 in the September roundup (https://redlib.groet-infra.nl/r/macapps/comments/1wrsbmj/). HapticPad $4.99 (snippet only). PurrPad (Reddit 2026-08-02, price not found). Not found: distinct apps named "Tap Tap", "Kinetic", "Clicky" or a standalone typewriter-sound app. A Snick commenter called it "a perfect companion to Klack".

**Closest overlap with Keyfeel:** Klack plus FeelMyMac plus Snick. FeelMyMac claims keyboard clicks plus haptics.

### 2.2 Review sentiment (paraphrased, from Reddit threads and App Store review snippets)

- **Klack:** praised for sound quality, privacy and a responsive developer; the Klack 2 thread had users praising latency (about 60 ms down to 11 to 13 ms), the $5 price and the free upgrade. One M1 Air user reported v2.0 unresponsive, patched in v2.0.1. One asked for customizable mouse click sounds and the developer said it was planned (relevant: Keyfeel has them).
- **Thock:** 2026-09-19 sounds gone on macOS 27.0; another user said it went silent irregularly on macOS 26; a third bought Klack (https://redlib.groet-infra.nl/r/macapps/comments/1wkkihk/).
- **Tacque:** sound reverting to silent after relaunch or login, battery drain (a user reported 6 percent in 6 hours with the lid closed), lag on external keyboards. Praised for price and developer responsiveness.
- **Haptyk (2026-03):** praise for the accelerometer idea; complaints about audio delay on an M4 Air, battery, sleep prevention, dropouts, exclusion of M1.
- **KeyBell, Keyboard Typing Sound, FunKey:** "artificial" sounds, lag when typing fast, overwhelming packs, space bar sounds different.
- **Klakk:** a "does not work" review (needs Input Monitoring) and a user calling it a fake copy of Klack.
- **KeyClicker thread 2026-08-18:** a keyboard enthusiast said it is "basically worthless" unless you record real switches; others asked about latency and custom sounds.
- **Snick and FeelMyMac threads:** scratchy sounds on laptop speakers, wanting more haptic variety, license and device-count clarity, Magic Trackpad support, battery and motor wear, "noisy and broken".

What this implies for Keyfeel copy: say plainly that sounds are recordings of real switches, that it needs the Input Monitoring permission and reads key codes not characters (already on the page), how licenses and the 7-day trial work, and what happens on external keyboards and Magic Trackpad. Do not claim a latency number unless it is measured.

### 2.3 Communities

| Community | Size (mirror, 2026-10-07) | Fit |
|---|---|---|
| r/MechanicalKeyboards | about 1.4M | Rule 2 bars it (see 2.4). Use only to read. |
| r/mac | 3.1M | Disk and general Mac help; not a keyboard-sound venue |
| r/MacOS | 646k | Promo Saturdays UTC only (second-hand) |
| r/macapps | 255.5k | The route. App Pile. |
| r/macbookpro | 414.4k | Feel and sound complaints, no rules read |
| r/asmr | 334.9k | Video-content community; app post unlikely to fit |
| r/olkb | 67k | Not read |
| r/Keychron | 50.1k | Not read |
| r/typing | 29.2k | Not read |
| r/ClickandThock 166, r/TypingASMR 163, r/mechvibes 26, r/FeelMyMac 13 | tiny | Not worth effort |
| Mechvibes Discord | 15,618 members, 2,369 online (public invite API, 2026-10-07) | Not joined. Keyfeel imports Mechvibes packs, so this is the one genuinely relevant audience. Join only as Ben, read the rules, and do not drop links. |
| Klack Discord | 753 members, 138 online | Not joined. Do not market in a competitor's server. |
| Geekhack | 140,587 registered members | No software board; "Other Geeky Stuff" only |
| Lemmy mechanicalkeyboards | 247 subscribers, dormant | Skip |
| Hacker News | "clickity" Show HN 2026-03-25, 4 points, 0 comments (https://news.ycombinator.com/item?id=47522115); "Mechvibes" 2026-05-04, 1 comment (https://news.ycombinator.com/item?id=48005591) | Low audience |
| YouTube | Mechvibes tutorials: LilEternity 59k views, Teknickel 111k, Razure 29k; Klack coverage 4k to 22k | Creator route |
| TikTok | Search needs a login; not read | Not found |
| Deskhaus | deskhaus.community does not resolve | Not found |

### 2.4 Self-promotion rules

- **r/MechanicalKeyboards** (second-hand, wiki via mirror, https://redlib.groet-infra.nl/r/MechanicalKeyboards/wiki/subreddit_rules): Rule 2 bars classifieds, B2B services and "Typing Apps or Extension Promotion". Rule 4: commercial content needs Promotional Flair, no more than once per week, "Astroturfing, undisclosed guerilla marketing, and shilling is expressly forbidden", and details must be in a top-level comment. Rule 11 bans referral and affiliate links. Rule 1 sends simple questions to the daily thread. Conclusion: no Keyfeel launch post. Read the sidebar flair requirements on reddit.com before any comment about sounds.
- **r/macapps:** see 1.4. The October App Pile is https://www.reddit.com/r/macapps/comments/1wuoav5/ (read 2026-10-07 through the Reddit tool). Entries use headed `Problem`, `Comparison`, `Pricing` sections and open with "I'm the developer". Reports say AI-assisted posts are removed more often and that disclosure of AI use is expected (GitHub issue #334 dated 2026-08-23, via the keyboard research pass; not read first-hand).
- **r/MacOS:** promo Saturdays UTC only (second-hand).
- **r/asmr:** wiki says "10% or less of your submitted content should be your own", one own item per day, no upvote requests (second-hand, mirror).
- **Geekhack, Deskhaus:** not found.

### 2.5 Ten threads where a disclosed developer reply fits

**Honest count: one is a clear fit in the 2026-08-01 to 2026-10-07 window.** I did not find ten genuine recent Mac typing-sound asks. The rest are graded, and several are competitor launch threads that are useful as research, not as places to reply.

| # | Thread | Date | Comments | Question | Fit |
|---|---|---|---|---|---|
| 1 | r/macapps "Thock issues on MacOS 27?" https://www.reddit.com/r/macapps/comments/1wkkihk/ | 2026-09-19 | 18 | Thock silent on macOS 27; move to Klack or another alternative? | Strong, if Keyfeel is confirmed to work on macOS 27. Several Klack replies exist. A promo comment in a help thread may still need mod permission or the App Pile. |
| 2 | r/asmr "Is there a desktop app that gamifies the literal sound of typing" https://www.reddit.com/r/asmr/comments/1thbuof/ | 2026-05-19 | 2 | Wants an app that plays mechanical sounds on a laptop | Good match, weak venue (OS not stated, 10 percent guideline); comments may close mid-November. |
| 3 | r/MacOS "iPhone Keyboard typing sound on Mac" https://www.reddit.com/r/MacOS/comments/1txh6ae/ (twin https://www.reddit.com/r/macbookpro/comments/1txh6qx/, 0 comments) | 2026-06-05 | 7 | Wants the iPhone keyboard click on a Mac | Moderate; a specific sound; probably locked soon. |
| 4 | r/macapps "Any Mac app you bought just because it looks and feels so good?" https://www.reddit.com/r/macapps/comments/1wquiou/ | 2026-09-26 | 237 | Open recommendation thread; Klack cited several times | Moderate. A late comment will be buried; needs disclosure and mod-rule care. |
| 5 | r/macbook "Quality Apps that have made my macbook better" https://www.reddit.com/r/macbook/comments/1t4elvv/ | 2026-05-05 | 50 | List thread that includes Mechvibes | Weak, old. |
| 6 | r/macbookair "Is the M5 13in air keyboard scratchier and tinnier to you?" https://www.reddit.com/r/macbookair/comments/1vl2ktj/ | 2026-08-11 | 9 | Hardware complaint | Weak; a reply would read as an ad. |
| 7 | r/macapps FeelMyMac launch https://www.reddit.com/r/macapps/comments/1wrsbmj/ | 2026-09-27 | 252 | Not a question | Research only: buyers ask about sounds, Magic Trackpad support, battery. |
| 8 | r/macapps Snick launch https://www.reddit.com/r/macapps/comments/1uefe6f/ | 2026-06-24 | 68 | Not a question | Research only. |
| 9 | r/macapps KeyClicker v2.6 https://www.reddit.com/r/macapps/comments/1vrgw0y/ | 2026-08-18 | 12 | Not a question | Research only: "record real switches" is the stated bar. |
| 10 | r/macapps Tacque launch https://www.reddit.com/r/macapps/comments/1u592t0/ | 2026-06-14 | 116 | Not a question | Research only: persistence of the sound setting, battery, external keyboard lag. |

Threads probably locked already: the MechVibes uninstall posts (Dec 2025), "What do yall use to emulate keyboard sound like klack?" (r/macapps, 2025-07-08), the Haptyk thread (2026-03-16).

**Standing search for new real asks** (Reddit search, new, past week): `klack alternative`, `typing sounds mac`, `keyboard sounds mac`, `mechvibes mac`, `thock mac`, `trackpad haptics`, `scroll sound`, `click sound mouse mac`. Mac typing-sound questions inside r/MechanicalKeyboards go to its daily thread, but none was found there.

### 2.6 Creators who review Mac menu-bar utilities or keyboard-sound apps

Subscriber counts as displayed on each channel's About page, 2026-10-07. "Contact" is what the visible About text publishes; a "View email address" gate on YouTube cannot be read, so "not found" there means no address was in the visible description.

| # | Channel | Subs | Covers | Last upload | Published contact |
|---|---|---|---|---|---|
| 1 | Be Productive https://www.youtube.com/@BeProductiveOfficial | 57.9K | "5 New Mac Apps You Must Use in 2026" | 1 day ago | `mailbeproductive@gmail.com` as "Business mail". About text: "If you want to include your product and service in our content, just drop us an email". Discloses affiliate links. https://www.youtube.com/@BeProductiveOfficial/about |
| 2 | Bram D Media https://www.youtube.com/@bramdmedia | 26.5K | "14 Unique Mac Apps I Can't Live Without" | 2 weeks ago | "Business: `bram@bramdmedia.com`" https://www.youtube.com/@bramdmedia/about |
| 3 | André Creates https://www.youtube.com/@andrecreates | 8.82K | "I Tested 47 Mac Apps. These are the Only 5 You Need" | 19 hours ago | "Contact me at `andrecreatesofficial@gmail.com`" https://www.youtube.com/@andrecreates/about |
| 4 | A Fading Thought https://www.youtube.com/@afadingthought | 7.2K | Apps and productivity; built Taptix, an Alfred keyboard-sound workflow inspired by Klack (2 years ago); Substack afadingthought.substack.com | 1 month ago | "Reach out: `hi@afadingthought.com`" https://www.youtube.com/@afadingthought/about |
| 5 | Tobi Teaches https://www.youtube.com/@tobiteaches | 6.9K | App reviews incl. Mac apps | 2 months ago | "For Business Inquiries Only: `tobiteaches@gmail.com`" https://www.youtube.com/@tobiteaches/about |
| 6 | Feel Productive https://www.youtube.com/@FeelProductive | 52.5K | "9 Mac apps that will blow your mind" | 2 days ago | Site feelproductive.co; no email on About |
| 7 | Better Creating https://www.youtube.com/@BetterCreating | 43.4K (268K in the discovery pass; the two reads disagree) | "Amazingly Simple Apps That Make Mac Better" | 4 days ago | Site bettercreating.com; no email on About |
| 8 | TheBrimFactor https://www.youtube.com/@TheBrimFactor | 20.2K | "This FREE Mac App Will Make You Uninstall Raycast" (34.6K views) | 9 days ago | Site thebrimfactor.com; not found |
| 9 | linkarzu https://www.youtube.com/@linkarzu | 13.4K | Covered Klack ("Klack - The macOS App That Makes Your Keyboard Sound Satisfying", 1 year ago) | 6 hours ago | linkarzu.com, Ko-fi, X; no email found |
| 10 | Matthew Piccolo https://www.youtube.com/@MatthewPCLO | 12.1K | Covered Klack ("The Coolest $5 I've spent on the Mac App Store", 22.1K views, 2 years ago) | 4 days ago | Instagram and X only; not found |
| 11 | iHaadi https://www.youtube.com/@iHaadi | 4.98K | "This App Makes Mac Typing Sound Insane" (2 months ago, 1.2K views) | 22 hours ago | Linktree, Discord, X; Linktree not opened; no email found |
| 12 | thirty https://www.youtube.com/@thirty | 3.63K | "These 6 macOS apps are incredibly satisfying to use" (includes Klack, 7.9K views) | 2 months ago | thirty.digital; not found |
| 13 | Sean Oulashin https://www.youtube.com/@SeanOulashin | 16.5K (TikTok @seanoulashin 393.7K) | "10 Mac Apps That Make Using My Computer Fun" | 6 months ago | seanoulashin.com; not found |
| 14 | Rubens Nook https://www.youtube.com/@RubensNook | 5K | "Mac Apps Nobody Recommends (But Should)" | 7 days ago | dub.sh/ruben.contact (short link, not opened) |
| 15 | Lewis Lovelock https://www.youtube.com/@lewislovelock | 3.95K | "10 Mac Apps I Regret Not Using Sooner" | 8 days ago | lewislovelock.com; not found |
| 16 | Let Mike Help https://www.youtube.com/@LetMikeHelp | 3.54K | Premium Mac apps | 1 day ago | letmikehelp.com; not found |
| 17 | Orbxz https://www.youtube.com/@Orbxz | 16.6K | "10 FREE Mac Apps" | not read | Channel description prints `Orbxz.business@gmail.com` for "reviews, business inquiries and advertisements" |

Larger channels that cover small Mac utilities and are not realistic targets: Stephen Robles 235K, MacRumors 659K, Snazzy Labs 1.27M, ThisIsE 493K, Andrew Ethan Zeng 444K, Reysu 262K, MacVince 215K, Christopher Lawley 206K (published emails exist), FromSergio 109K. Snazzy Labs posted "Open Source Is Beating Paid Mac Apps" five days before 2026-10-07 (483,503 views), which is useful context for the free-versus-paid argument.

Policy: only Be Productive states a policy ("drop us an email"). No other channel stated a software-review request or sponsorship policy on the pages read.

**Directories and lists that accept Mac apps** (these are listings, not reviews): On My Menubar https://onmymenubar.app/submit (already lists Klack and FunKey); MacMenuBar.com https://macmenubar.com/submit-your-menu-bar-app/ ("true macOS menu bar apps only", manual review, about 1,600 to 1,700 app pages, about 100 removed as abandoned per the September roundup; sponsorship slots from $15 to $125 a month, mostly booked to April 2027); TryMacApps https://www.trymacapps.com/submit; Indie App Catalog non-store form (https://indieappcatalog.com/non-appstore lists 66 apps). Podfeet (wrote about Klack in 2023) returned 403, so its contact policy is not verified.

---

## 3. Discovery surfaces for the three consumer apps

### 3.1 Product Hunt (official pages read 2026-10-07 through a summarizing fetcher)

| Item | Finding | Source |
|---|---|---|
| Timing | "12:01 am Pacific Time is the best time to launch for makers that are planning ahead". "The best day to launch is the day on which you're most prepared." | https://www.producthunt.com/launch |
| Upvote asks | "you cannot ask people directly to upvote your product. Instead, ask them to visit and comment." | https://www.producthunt.com/launch/launch-day |
| Account | "Company accounts are prohibited." Profiles must "represent an individual, not a company". Paying anyone to hunt or send traffic is banned. | https://www.producthunt.com/launch/launch-guidelines; https://help.producthunt.com/en/articles/3615694-community-guidelines |
| Ranking | Points, not raw upvotes; "Not all upvotes carry the same weight"; comments count; formula unpublished | https://help.producthunt.com/en/articles/10275873-what-are-points (2025-10-01) |
| Featuring | Guidelines dated 2026-03-10: useful, novel, well designed, available now. Not featured: waitlists, directories, templates, courses, deal sites, vaporware, products that prioritize "immediate monetization". Contacting the team "does not guarantee" featuring. | https://help.producthunt.com/en/articles/9883485-product-hunt-featuring-guidelines |
| 2026 change | One-off "Randomized Leaderboard Day" 2026-03-27, described as an experiment | https://www.producthunt.com/p/producthunt/introducing-randomized-leaderboard-day-on-product-hunt |
| Maker comment | Official pages do not require one. Comments count toward points. "Expected" is third-party advice only. | pages read: /launch, /launch/launch-day, /launch/how-product-hunt-works, /launch/prepare-for-launch |
| AI content, account age, karma | Not found in official text | |
| Launches per day | Sources disagree: about 11 a day (Waitlister, Dec 2025, via shno.co), about 14 a day (Screen Charm, 429 launches in Sep 2025), 8 to 91 a day on a calendar for 18 Sep to 1 Oct 2026 (hunted.space, unclear scope) | https://www.shno.co/marketing-statistics/product-hunt-launch-statistics; https://screencharm.com/blog/how-to-launch-on-product-hunt (2025-10-10); https://hunted.space/stats |
| Best day | None named officially. Third party (Screen Charm, Oct 2025): about 633 upvotes to reach #1 on a Monday against about 366 on a Saturday; Tuesday to Thursday carry most traffic and competition. | |
| Visits | Second-hand: #1 gets 3,000 to 8,000 visitors in 24 hours, #2 to 5 get 800 to 2,500, below the front page 50 to 300 (LaunchBuff, 2026-07-20, sample not disclosed); non-featured launches 100 to 500 visitors and 1 to 15 signups (shno.co, Nov 2025). About 10 percent of launches featured, down from 60 to 98 percent in 2020 to 2023 (second-hand). | https://launchbuff.com/blog/product-hunt-launch-data-analysis-2026 |
| Mac-utility data | Not found | |

Local constraints: `docs/directory-submissions.md` says Product Hunt's main URL cannot be shortened or UTM-tracked, and that ModernTex already launched at https://www.producthunt.com/products/moderntex. A second launch is by the same personal account.

### 3.2 Hacker News and Show HN

- Show HN official text (https://news.ycombinator.com/showhn.html, read 2026-10-07): "Show HN is for something you've made that other people can play with." Blog posts, sign-up pages and lists are off topic. "The project should be non-trivial." Make it easy to try, ideally without signups. "Please don't ask friends to upvote or comment. That's not ok on HN."
- Guidelines (https://news.ycombinator.com/newsguidelines.html): "Please don't use HN primarily for promotion." "Don't solicit upvotes, comments, or submissions." FAQ (https://news.ycombinator.com/newsfaq.html): reposts are acceptable only after a year without significant attention, and do not delete and repost.
- Second-chance pool: moderators can re-queue overlooked posts; suggestions go to hn@ycombinator.com (search snippet of a moderator comment, not read on the primary page).
- Timing (third-party, Myriade, 2025-07-18, 157k Show HN posts, "30+ votes" as success): Sunday 11.75 percent and Saturday 11.08 percent against 9.45 to 9.90 percent on weekdays; best hour 12:00 UTC at 12.2 percent; good window 11:00 to 16:00 UTC; Sunday 11 to 16 UTC about 12 to 14 percent. https://www.myriade.ai/blogs/when-is-it-the-best-time-to-post-on-show-hn
- Outcomes (HN Algolia API, 2026-10-07; 332 Show HN stories since 2024-01-01 matching Mac queries, capped at 50 hits per query, so approximate): median 3 points; 114 posts with 2 points or fewer; 58 with 10 or more; 33 with 50 or more. Paid or paid-looking Mac apps: Godspeed 328 points (2024-03-19), NetViews 243 (2026-02-10), an AirPods sound-degradation fix 223 (2024-09-30), Fallinorg 88 (2025-08-17), Draw Over It 56 (2025-10-29), LookAway 25 (2025-02-20), Yoink AI 24 (2025-08-28), Macscope 15 (2025-09-26). Nearest to our products: "clickity" 4 points (2026-03-25), "Yeet" disk-space CLI 4 points (2026-01-06), "Mac Cleaner, Offline" 3 points (2026-01-11). WhatCable, a free menu-bar tool, reached 566 points (2026-05-01).
- Reading: a Show HN works only with a real technical story. "Another cleaner" or "another typing-sound app" lands at the median of 3 points.

### 3.3 r/macapps

- Current App Pile: https://www.reddit.com/r/macapps/comments/1wuoav5/megathread_the_app_pile_october_2026/ (130 comments, read 2026-10-07). Posted by Mstormer about 2026-10-01. Entries are top-level comments with `Problem`, `Comparison`, `Pricing` and links. Paid direct-sale examples include Start Menu for Mac at US$11.99 and ChillScreen at EUR 9.99 with a 14-day trial.
- Rules: second-hand, see 1.4. Karma, identity, privacy-policy and ToS requirements for the megathread were not found. Earlier research in `docs/reddit-notes-2026-09-29.md` records the stated Tier 2 demand for "a real identity, privacy policy and ToS"; Legroom and Keyfeel have named developer, terms and privacy pages on the site.
- Showcase and discount posts exist as ordinary posts (examples: "50% off Piano Glide (lifetime $9.99, code REDDIT50)", 25 points; "In Agenda ... (Lifetime 50% off)", 43 points; "OptiSound turns 3 ... 10 lifetime licenses", 12 points; Vinaa launch with giveaway, 32 points and 161 comments). Whether those were allowed as standalone posts depended on each developer's tier, which could not be established.
- Mood on the sub: a 314-vote "Setapp has been completely enshittified" thread and a 302-vote "Every app thread on r/macapps lately" thread that mocks small AI-built apps. Commenters call some single-purpose apps "AI slop". Expect skepticism; plain facts and a free trial are the answer.
- September roundup (by NeonSerpent, not official): https://www.reddit.com/r/macapps/comments/1wzts9p/monthly_roundup_september_2026_top_mac_apps/ ranks by votes and comments, and reports 250,000 members.

### 3.4 Directories and download sites

| Site | Finding | Source |
|---|---|---|
| AlternativeTo | Terms: "may remove, edit or refuse any listing at our discretion". Paid priority review usually "one to two business days", "approval criteria are exactly the same"; "Members who have earned verified status are placed ahead of the backlog without paying." Standard queue: earlier FAQ says "at least a few months". | https://alternativeto.net/about/terms/; `docs/directory-submissions.md` |
| Setapp | Developers page states a "24-hour app review process" for Single-App only; membership review time not found. Shares: developers page shows Single-App 75/15 and 75/25 while docs say 85 percent subscription and 75 percent one-time (the pages disagree). Docs: "typically recruits developers directly, though applications are welcome" via the site form or developers@setapp.com. Whether direct-download apps are accepted: not stated. A separate research pass saw "mature software with an excellent reputation" as a requirement, which makes a days-old app a long shot. | https://setapp.com/developers; https://docs.setapp.com/docs/setapp-marketplace-overview |
| MacUpdate | The old support article is replaced by https://www.macupdate.com/help; submission page https://member.macupdate.com/content/submit. Review by "content specialists". Reject list includes "Commercial applications without downloadable demos" and apps that duplicate built-in macOS features. Contact support@macupdate.com. Fees, dofollow, review time not stated. Local log: ModernTex submitted 2026-10-01, review "within 10 days". | https://www.macupdate.com/help |
| MacMenuBar.com | See 2.6. Manual review; fee and review time not stated. | https://macmenubar.com/submit-your-menu-bar-app/ |
| On My Menubar, TryMacApps | Submit pages exist; terms not read | https://onmymenubar.app/submit; https://www.trymacapps.com/submit |
| Indie App Catalog | Login required, no fee mentioned; non-store route exists | https://indieappcatalog.com/non-appstore |
| SaaSHub | Free submit plus paid "Feature My Product" | https://www.saashub.com/ |
| Softpedia, Mac Informer, MacDownload, Slant | 403; not read (Softpedia is already in `docs/directory-submissions.md`) | |
| Club MacStories, Apps Mac Library | No developer route found | |

### 3.5 Twenty outlets and newsletters

Addresses appear only if printed on the cited page; some were obfuscated by script on the page and were decoded as displayed. Nothing was guessed. Overlap with Ben's `Outreach/04-outreach/newsletter-pitches.md` is flagged (iOS Dev Weekly, MacStories, The Sweet Setup, Hacker Noon).

| # | Outlet | Published route | Stated policy |
|---|---|---|---|
| 1 | MacStories | https://www.macstories.net/about/ prints viticci@macstories.net and voorhees@macstories.net. No tips form found. (In Outreach file.) | "We have never done and never will do paid reviews." "only write about apps if we have personally tested them." |
| 2 | 9to5Mac | https://9to5mac.com/contact/ tips address and anonymous form | "Submitting a tip constitutes permission to publish and syndicate." No indie policy found. |
| 3 | MacRumors | https://www.macrumors.com/about/ prints tips@macrumors.com | Nothing on indie software |
| 4 | Macworld | https://www.macworld.com/about/contact says to email rloyola@macworld.com to "send in a product for review" | "The Macworld editors do not run guest posts or unsolicited submissions." "we cannot respond to all queries." |
| 5 | Cult of Mac | https://www.cultofmac.com/about prints reviews@cultofmac.com and news@cultofmac.com | "Get your product reviewed: If you've got tech gear (especially Apple-related tech gear), we might be interested in reviewing it." Software not mentioned. |
| 6 | TidBITS | https://tidbits.com/about/contact/ lists Adam C. Engst, "All usernames below are @tidbits.com", so ace@tidbits.com | "Please don't send us press releases." Wants app pitches researched, "not merely yet another entry into a crowded category". No guest or sponsored posts. Our apps are in crowded categories, so a poor fit. |
| 7 | Six Colors | https://sixcolors.com/about/ gives no email or form | "never accept money or gifts in exchange for coverage." |
| 8 | Daring Fireball | https://daringfireball.net/contact/ lists Signal, Mastodon, Bluesky, Threads; no email | Writer is a "slow correspondent" |
| 9 | iMore | https://www.imore.com/about prints an address for "iMore Labs" feedback only | "We do not take payment for product reviews, ever." No developer route. |
| 10 | How-To Geek | https://www.howtogeek.com/page/press-events/ prints techpartnerships@valnetinc.com | No review-request policy found |
| 11 | MakeUseOf | https://www.makeuseof.com/page/press-events/ same address | No review-request policy found |
| 12 | OSXDaily | https://osxdaily.com/contact-os-x-daily/ "send us your tips, comments, suggestions"; no address visible | None found |
| 13 | Eclectic Light Company | https://eclecticlight.co/about prints h [dot] oakley [at] btconnect [dot] com | "Please don't offer paid content, or commercial promotion". Rarely covers third-party paid apps. Useful only as a reader of its System Data articles. |
| 14 | Pixel Envy | https://pxlnv.com/about/ "Tips? Please write" desk@pxlnv.com | Not an app-review site |
| 15 | MacSources | https://macsources.com/contact/ form: "Are you a developer with an app or product you would like us to review?" | Its advertise page also sells "Sponsored Article" posts (self-reported about 100,000 unique monthly readers). I did not find whether reviews are separate from the paid products. Disclose that you will not pay. |
| 16 | The Sweet Setup | https://thesweetsetup.com/contact/ prints desk@blancmedia.org (in Outreach file) | Recommends "the best apps (not necessarily the newest)" |
| 17 | Setapp blog | https://setapp.com/news/write-for-setapp guest-article form, reply "within five business days" | Guest articles about apps in its catalog; not reviews |
| 18 | Console.dev | https://console.dev/about prints hello@console.dev | "We do not publish sponsored reviews." Developer tools only. Poor fit. |
| 19 | Indie Dev Monday | https://indiedevmonday.com/about says reply to any issue with what you are building | From 2026 follows developers over time rather than one-off profiles |
| 20 | Hacker Newsletter | No route found | Picks only what already did well on HN |

Not read: AppleInsider, The Mac Observer, Lifehacker (only corporate contacts), Mac Kung Fu. Not found anywhere: a stated policy on paid Mac utilities from solo developers beyond "no paid reviews" and "no unsolicited pitches". iOS Dev Weekly is in the Outreach file but is iOS-focused and was not researched here.

### 3.6 YouTube channels and podcasts

The 17 small channels in 2.6 are the realistic YouTube targets. Larger ones are listed in 2.6 for context.

| Show | Published route |
|---|---|
| Mac Power Users | https://www.relay.fm/mpu/feedback ("Got feedback or followup for the show? Submit it below!"); sponsorship https://www.relay.fm/sponsor prints hello@relay.fm |
| Upgrade | https://www.relay.fm/upgrade; same Relay sponsor route; no app-suggestion route found |
| Accidental Tech Podcast | https://atp.fm/feedback: "PR solicitations for potential guests are extremely unwelcome". Sponsorship https://atp.fm/sponsor prints sponsorship@atp.fm and says sponsors include apps. |
| Core Intuition | https://coreint.org/contact prints feedback@coreint.org and a Slack option; covers indie Mac development |
| Mac Geek Gab | https://www.macgeekgab.com/contact/ prints feedback@macgeekgab.com and pr@macgeekgab.com; Quick Tips page https://www.macgeekgab.com/quicktips |
| MacBreak Weekly | https://twit.tv/shows/macbreak-weekly read; no route found |
| Under the Radar | Ended; last episode #331, 2025-11-06. Do not pitch. |
| Mac Observer Daily Observations, Cortex, Launched, The Indie Dev Podcast | Not read or not found |

---

## 4. Vitae (free academic app)

### 4.1 Communities and published promotion rules

| Community | Size (mirror, 2026-10-07) | Published rule | Verdict |
|---|---|---|---|
| r/AskAcademia | 2.1M | Rule 6: "Questions that are thinly veiled pitches for products will also be removed". Rule 7: surveys only for academics. (second-hand, mirror) | Answer questions as a person; no pitch posts |
| r/GradSchool | 946.3k | Rule 6 "No irrelevant surveys or advertising." Rule 8 "No spam or spammy self-promotion", permanent ban. (second-hand) | Skip |
| r/academia | 110.4k | "Commercial posts prohibited." (paraphrase of sidebar) | Skip |
| r/PhD | 288.5k | Mod post "Policy on tools and promotions" (2026-02-10), read first-hand: tools allowed if open source, industry standard or established indie; a personal project is welcome only with no "free trial" button or "free tier"; "LLM-wrapper and other SaaS startups are not welcome here"; removal and permaban. https://www.reddit.com/r/PhD/comments/1r11qx4/policy_on_tools_and_promotions/ | Vitae has a free tier. Do not post. |
| r/Professors | 201.0k | Faculty only. Rule 6: "...This includes advertising your own or others content." Rule 7: no surveys by default. https://redlib.groet-infra.nl/r/Professors/wiki/rules (second-hand) | Participate as a faculty member; no product links unless asked |
| r/postdoc | 30.1k | Rule 5 "No spam/scams/selling services/self-promotion." (second-hand) | Skip |
| r/macapps | 250,000+ | See 1.4 | App Pile for Mac users |
| r/zotero | 15.2k (unofficial) | No promotion rule visible; plugins are announced in the Zotero forums | Only if Vitae integrates with Zotero |
| r/ObsidianMD | about 369k | Sidebar mentions avoiding self-promotion in initial posts (weak paraphrase) | Not a fit |
| scholar.social (Mastodon) | 282 monthly active users, registrations closed | Rules 1 to 13 include "No spam" and "No bots or 'institutional' accounts operated by non-members (Scholar Social is for individuals)". No explicit tool-promotion rule. https://scholar.social/api/v1/instance/rules | Registrations are closed, so Ben cannot join now |
| hcommons.social | 330 monthly active users, registration by email request | Rule 6 "No spam." | Small |

Not verified: Academic Twitter or X, LinkedIn, Facebook groups, NCFDD or Faculty Success Program spaces, graduate-student Slack or Discord, r/AcademicPsychology, the r/Professors Discord. Bluesky: the public API shows discipline-specific starter packs ("Marketing Academics", "Social Work Academics Starter Pack"), no join counts and no tools-oriented broad pack.

### 4.2 Search phrases and what ranks (Brave and Bing result pages, 2026-10-07; not Google)

| Phrase | What dominates |
|---|---|
| "journal submission tracker spreadsheet" | Fiction and poetry trackers; research entries are few: https://academia.stackexchange.com/questions/65962/software-for-tracking-next-manuscripts-to-submit, https://subthesis.com/tools/journal-submission-tracker/ |
| "how to keep track of submissions manuscripts academic" | Academia StackExchange, a Medium Trello post (https://medium.com/@audreygirouard/how-to-keep-track-of-manuscript-submissions-cc1eba9886c9), https://submitwise.org/submission-tracker/ |
| "manuscript tracker" | Publisher status portals, msTracker, Editage |
| "track grant applications researcher" | GrantWatch, Grants.gov, GrantForward and nonprofit tools; one academic: https://lennartnacke.com/how-to-build-your-grant-tracking-system/ (2025-12-27) |
| "tenure dossier organization" | University provost pages, https://theprofessorisin.com/2011/07/21/your-tenure-dossier/, Faculty Focus, Inside Higher Ed |
| "annual review record keeping faculty" | Provost pages; vendors scholarlysoftware.com, Watermark |
| "faculty activity reporting" | Interfolio FAR, Watermark (Activity Insight, Digital Measures), Elements; Baylor moved from Digital Measures to Interfolio FAR in Fall 2025 |
| "academic CV builder" | scispace.com, resumelab.com, visualcv.com, zety.com, https://cvscholar.com |
| "academic CV template" | resumegenius.com, careerservices.upenn.edu, template.net, canva.com |
| "how to keep your CV updated academic" | https://www.reddit.com/r/AskAcademia/comments/17sqdp1/how_do_you_keep_your_cv_updated/, Yale OCS ("Your CV is a living document") |
| "tenure track record keeping" | Carleton SERC "Getting Tenure", Chronicle ProfHacker "Starting a Tenure Box", C&RL News tenure tracker, The Professor Is In |

Competitors: Interfolio Faculty Activity Reporting (institutional, price undisclosed), Watermark Faculty Success (institutional, 400+ colleges claimed, price undisclosed), Scholarly (institutional, demo pricing), Paperpin (https://getpaperpin.com, free tier), SubmitWise (https://submitwise.org, free and PRO), CVScholar (https://cvscholar.com, free to start, shows 10 users and 27 CVs generated). Symplectic Elements and Academic Analytics pages were not retrievable. The Mac App Store (iTunes search API, 2026-10-07) returned no obvious Mac academic CV, submission or grant tracker in the top results, which is not proof of absence. Spreadsheets, Notion, Trello and Obsidian are the real incumbents.

### 4.3 Fifteen named targets with a published route

Ordered by my read of fit for a free Mac app that builds a CV from a record. "In Ben's files?" is a guess because only file names were read.

| # | Target | Audience | Published route and policy | Notes |
|---|---|---|---|---|
| 1 | Inside Higher Ed Views and Careers, https://www.insidehighered.com/submission-guidelines | Faculty, administrators | opinion@insidehighered.com, 1,000 to 1,500 words, authors must "disclose any relevant potential conflict of interest." | Ben already has an IHE essay folder (`Outreach/inside-higher-ed/`). Disclosure of Vitae is mandatory. |
| 2 | LSE Impact Blog, https://blogs.lse.ac.uk/impactofsocialsciences/submissions/ | Researchers; scholarly communication | impactofsocialsciences@lse.ac.uk; proposal or draft plus 50 to 80 word bio; 800 to 1,200 words; "Avoid promotional or partisan content." Authors must be PhD students, PhD holders or sector professionals. | Essay about keeping your own record, no product pitch |
| 3 | The Professor Is In, https://theprofessorisin.com/ | Job-market and tenure-track | Printed gettenure@gmail.com (Dr. Karen Kelsky); form https://theprofessorisin.com/contact-the-professor/. No stated tool policy. Guessed guest-post URL 404'd. | Hosts the tenure dossier posts that rank for these searches |
| 4 | The Thesis Whisperer, https://thesiswhisperer.com/ | PhD students, researcher developers | Guest posts opened (Mar 2025 per the home page); printed contact enquiries@ontheregteam.com; no formal guidelines found | Audience is students, not tenure track |
| 5 | C&RL News (ACRL), https://crln.acrl.org/index.php/crlnews/about/submissions | Academic librarians | dfree@ala.org; features up to 2,000 words. Hosts "Document Everything: A Tenure Tracker for Academic Librarians" (2026), https://crln.acrl.org/index.php/crlnews/article/view/27284/35084 | Narrow, but librarians run the LibGuides that list tools; the author of that article is a natural contact (not researched further) |
| 6 | Times Higher Education, https://www.timeshighereducation.com/write-times-higher-education | Global academics | THE.Submissions@timeshighereducation.com; opinion 750 to 1,000 words; AI content "usually prohibit[ed]"; several weeks to respond | Opinion essay only |
| 7 | Nature Careers, https://www.nature.com/naturecareers/contact-us/ | Scientists | Editor emails printed on the page (technology editor listed); no pitch guidelines found | Stronger for science than for business or information-systems faculty |
| 8 | Faculty Focus (Magna), https://www.facultyfocus.com/about/contribute/ | Faculty, teaching-centred | matt.nieman@magnapubs.com; 900 to 1,300 words; 5 to 6 week review | Topics listed are teaching; weak fit |
| 9 | Higher Ed Dive, https://www.highereddive.com/opinion/submit-opinion/ | Administrators | Online form; about 1,000 words; 30-day exclusivity; "promotional, biased or not grounded in fact" is judged by editors. Tips: https://www.highereddive.com/submit-tip/ | Administrator audience |
| 10 | University Affairs (Canada), https://universityaffairs.ca/us/letters-editor-comments-submissions/ | Canadian academics | Opinion portal; contact https://universityaffairs.ca/us/contact-us/ | Non-US |
| 11 | POD Network, https://podnetwork.org/ | Educational developers at about 1,300 centres (1,700+ members) | Sponsorship page and general contact; the email was obfuscated on the page | The route into faculty-development centres; conference exhibits possible |
| 12 | NCFDD, https://www.ncfdd.org/ | Faculty and graduate members at 300+ partner institutions | https://www.ncfdd.org/company/connect-with-us/; no vendor or tool route found; partnerships are institutional | Probably closed |
| 13 | Zotero forums and plugin page, https://www.zotero.org/support/plugins | Zotero users | "We don't currently provide a list of available plugins, but most plugins are announced and discussed in the Zotero Forums... An official plugin directory is planned." | Only if Vitae reads Zotero libraries |
| 14 | The Chronicle of Higher Education, https://www.chronicle.com/ | Faculty | Route not verified; every URL tried returned 403 | Unverified |
| 15 | MacStories, https://www.macstories.net/about/ | Apple-platform users | See 3.5 | Reaches Mac users, not academics specifically; already in Ben's Outreach file |

Dropped: 101 Innovations in Scholarly Communication (stale, 2015 to 2016), ORCID integrations page (404), Mark Carrigan (no stated policy), Science Careers (403). No named university teaching centre, graduate-school newsletter or LibGuide route was verified in this pass; `Outreach/04-outreach/libguide-outreach.md` already covers LibGuides.

### 4.4 Evidence that faculty keep records, and when it hurts

No survey of US faculty was found. Sources are advice and policy:

1. Faculty Focus, 2012-04-25: "start collecting evidence of your teaching, research, and service activities. We suggest keeping a file for all your evidence." https://www.facultyfocus.com/articles/faculty-development/top-10-strategies-for-preparing-the-annual-tenure-and-promotion-dossier/
2. The Professor Is In, 2011-07-21: effective departments require a dossier "in your first year in the form of a binder or a box of files". https://theprofessorisin.com/2011/07/21/your-tenure-dossier/
3. C&RL News (Naughton, 2026): "Use the Tenure Tracker every day or on most days"; practice-based, no survey data. https://crln.acrl.org/index.php/crlnews/article/view/27284/35084
4. Rice University: "it is strongly recommended that faculty members enter their activities throughout the year." https://vpaa.rice.edu/faculty/activity-report
5. Watermark ebook page (vendor claim): faculty face "8 to 12 distinct reporting requests a year." https://www.watermarkinsights.com/learn/ebook/the-essential-guide-to-faculty-activity-reporting/
6. r/Professors, 2026-08-24: one university requires entry "in three places" (CV, university database, annual evaluation); replies use the CV as master, a yearly Google Doc, or a Google Sheet. https://www.reddit.com/r/Professors/comments/1vxe4d6/

Seasonality:
- Annual reports: Penn State HHD needs Activity Insight entries by 1 February, review meetings by 15 May, summaries by 1 June (https://hhd.psu.edu/hhd-faculty-annual-review-guidelines). Rice's report campaign runs "early December... to the end of January." BYU recommends colleges finish annual reviews by 31 March (https://facultyprofilehelp.byu.edu/annual-faculty-review-process).
- Tenure file: "Early Fall of Candidate's year 6, you submit ALL elements of your record" (https://theprofessorisin.com/2018/05/25/the-path-and-timeline-of-your-tenure-application/, 2018-05-25, R1 timeline).
- Summer dossier prep appears in r/Professors, 2026-07-27 (https://www.reddit.com/r/Professors/comments/1v85crf/).
- Job-market CV season: no published source with months. CV-help threads clustered in August and September 2026 (inference, not sourced).
- Implication: pitches that land in November and December reach readers just before annual-report season. The fall tenure-file window is now.

### 4.5 Five recent threads where a disclosed developer reply could fit

| # | Thread | Date | Question | Fit and risk |
|---|---|---|---|---|
| 1 | r/Professors "Do you have a good system for logging activities?" https://www.reddit.com/r/Professors/comments/1vxe4d6/ | 2026-08-24 | Entering activities in CV, university database and annual evaluation; how not to forget | Closest to Vitae. Risk: rule 6 on advertising. Answer without a link; mention only if asked. |
| 2 | r/AskAcademia "Unsuccessful grants - include on CV or not?" https://www.reddit.com/r/AskAcademia/comments/1wvthem/ | about 2026-10-02 | Should unfunded grants go on a CV? | A reply about a private full record versus a public CV fits. Rule 6 targets question posts; comment practice untested. |
| 3 | r/AskAcademia "How do you actually build a publication pipeline as a busy early-career faculty member?" https://www.reddit.com/r/AskAcademia/comments/1wzy34e/ | 2026-10-07 ("3h ago") | "Do you have a system for maintaining a pipeline of ideas, ongoing studies, manuscripts and submissions?" | Direct. The asker wants process, not tools. |
| 4 | r/Professors "How much evidence is enough to demonstrate 'excellence' in teaching in a tenure dossier?" https://www.reddit.com/r/Professors/comments/1wb92ju/ | about 2026-09-09 | A committee member sees a thin teaching file | Not a tool request; use as essay material. |
| 5 | r/PhD "How do you keep track of the papers/abstracts you've submitted?" https://www.reddit.com/r/PhD/comments/1uscojy/ | 2026-07-10 | A fourth-year student wants better than an Excel sheet | Most direct, but r/PhD bans tools with a free tier. Do not reply with Vitae. |

Precedent (observation, not a rule): in https://www.reddit.com/r/Professors/comments/1vxq85w/ (2026-08-25) a user wrote "I started building it for similar reasons" and linked their own tool; it was still visible with a score of 1.

---

## 5. Thirty-day plan (2026-10-07 to 2026-11-06)

### 5.1 Measurement

The site's own first-party beacon (`site/analytics.js`, `netlify/functions/track.mjs`) records `utm_source` on each pageview and keeps `utm_medium` and `utm_campaign` with the first-touch attribution it attaches to a Stripe order. The referrer host is recorded too. The traffic dashboard already has a "Campaign sources" table (`topUtm`). So:

- Tag every link with `?utm_source=<channel>&utm_medium=<type>&utm_campaign=<app>-oct26`. Keep `utm_source` short and unique per placement, for example `macapps-pile`, `reddit-macos`, `reddit-mac`, `hn`, `ph`, `macmenubar`, `onmymenubar`, `trymacapps`, `macupdate`, `alternativeto`, `yt-bram`, `yt-bemoreproductive`, `pitch-macsources`.
- Exceptions: Product Hunt's main URL must not carry UTM (the referrer `producthunt.com` identifies it); put the tagged link only in the maker comment. Directory forms that ask for a plain URL get the plain URL; the referrer host identifies them.
- `?ref=` values other than the Vitae app's are deliberately not recorded; do not use `ref`.
- Measure per channel at day 14 and day 30: unique visits to the product page, trial downloads if the download page logs them (confirm with `scripts/stats-collect.py`), and Stripe orders with their first-touch tag. Reply counts and moderator removals go in `Outreach/OUTREACH-LOG.md`.
- Whether Cloudflare Web Analytics breaks out UTMs was not verified; rely on the first-party beacon.

### 5.2 Ranking by expected visits per hour (my judgment)

Baseline: each product page gets about 4 to 13 views a month. The numbers below are guesses to rank by, built from the second-hand data cited above, not forecasts.

| Rank | Action | Effort | Rough visits and why |
|---|---|---|---|
| 1 | Menu-bar and Mac directory submissions (MacMenuBar, On My Menubar, TryMacApps, Indie App Catalog, MacUpdate, AlternativeTo) for Legroom and Keyfeel | about 2 h in total | Small per listing (single digits to low tens a month) but permanent and near zero marginal cost. Best visits per hour only because the effort is tiny, and the best compounding. |
| 2 | r/macapps App Pile entry (Legroom now, Keyfeel when allowed) | 45 min each | The only developer-friendly Reddit door for direct-download apps. One developer's self-reported 15 of 25 sales in a week suggests tens to low hundreds of visits per entry. Most time-sensitive for Legroom because of the macOS 27 storage wave. |
| 3 | Helpful disclosed replies in 3 to 5 Legroom storage threads this week | 1.5 h | A few to dozens of visits per reply if it is useful and stays up; also builds a record under Ben's name. Highest risk of a removal. |
| 4 | Five personal emails to small YouTube creators for Keyfeel | 2 h | Each small channel's video could bring tens to hundreds of views, with a lead time of weeks and an unknown reply rate (not found in any source). Cheap, long-tailed. |
| 5 | Three outlet pitches (MacSources form, Cult of Mac reviews@, one more) | 1.5 h | Low probability; no outlet read states a policy for solo-developer utilities, and most say they do not take unsolicited pitches. Treat as a lottery ticket. |
| 6 | Show HN for Legroom, Sunday morning US time, with a technical story | 1 h plus 3 h of replies | Median Mac Show HN is 3 points. A hit would bring thousands, a miss under 20. Only with a real story (how Legroom reconciles free space, purgeable space and snapshots). |
| 7 | Product Hunt for Keyfeel | 4 to 5 h | Second-hand: non-featured launches 100 to 500 visitors, with weak retention. Last, and only if steps 1 to 4 show interest. |
| 8 | Vitae: one essay pitch and one directory pass | 3 h | Slow. Aim at annual-report season (Dec to Jan), so the payoff falls outside 30 days. |

**Do first (highest expected visits per hour):** the directory batch, then the App Pile entry, then this week's Legroom replies. The first takes about two hours and compounds; the second and third are time-boxed to the current macOS 27 storage wave.

### 5.3 Day-by-day

**Before anything (30 min, Ben):**
- Read the live rules on reddit.com for r/macapps (including the 30-day limit, per developer or per app, and the megathread requirements), r/MacOS and r/mac. Check Ben's own account karma against the "about 10 sub karma" report. If the account is thin, the first week is replies without links.
- Confirm Keyfeel works on macOS 27 and what its macOS 27 test status is. Without that, skip the Thock thread and any macOS 27 claim.
- Decide whether Ben's own account posts (named person, real identity, as the rules favor) and that the replies come from Ben, not a brand account. Product Hunt prohibits company accounts.

**Week 1 (Oct 7 to 13)**
1. Directories (about 2 h). Submit Legroom and Keyfeel to MacMenuBar, On My Menubar, TryMacApps and Indie App Catalog (non-store form); submit both to MacUpdate (ModernTex's submission is already pending since 2026-10-01; MacUpdate rejects "Commercial applications without downloadable demos", which the 7-day trial avoids) and to AlternativeTo as new names (the earlier ModernTex name collision on 2026-10-01 does not affect them). Skip every paid priority option. Log each in `docs/directory-submissions.md`'s status log.
2. App Pile entry for Legroom in the October thread (first draft in 6.4). If the rules say the limit is per developer, hold Keyfeel for the November pile; if per app, post Keyfeel now (second draft in 6.4).
3. Legroom replies, at most three this week, in threads 1, 2 and 3 of section 1.5 (and 5 if there is room). Space them over days. Answer fully before disclosing. Link only when the asker asked for an app (draft 6.1). r/MacOS promotion is Saturdays UTC (second-hand): the next are Oct 10 and Oct 17 UTC. Wait until the rules are read before linking there.
4. Add `utm_source` tags to every link.

**Week 2 (Oct 14 to 20)**
1. Creator emails for Keyfeel to five channels with a published business address: Be Productive, Bram D Media, André Creates, A Fading Thought, Tobi Teaches (draft 6.6). Offer a license key. Do not ask for a positive review.
2. Outlet pitches (draft 6.5) to MacSources via its form, Cult of Mac reviews@, and one of Macworld (rloyola) or The Sweet Setup. One email each, no follow-up (matches `Outreach/04-outreach/newsletter-pitches.md`).
3. A second round of Legroom replies if the first round stayed up and was not removed. If a reply is removed, stop replying in that sub and read the removal reason.
4. Check week-1 numbers against section 5.1.

**Week 3 (Oct 21 to 27)**
1. Show HN for Legroom, on a Sunday between 11:00 and 16:00 UTC (3 to 8 a.m. Pacific, 7 a.m. to noon Eastern), draft 6.2. Only if week 1 and 2 numbers justify the afternoon of replies. Otherwise hold.
2. Vitae: pick one essay target. If the IHE essay is already submitted or accepted, do not send a second; pitch an adjacent angle to LSE Impact Blog (no product pitch, disclosure of Vitae in the bio) or send The Professor Is In's printed address a short note (draft 6.7). Add Vitae to MacUpdate, AlternativeTo and Indie App Catalog.
3. Product Hunt decision: launch Keyfeel only if at least five real users can comment on launch day. Schedule for a Tuesday to Thursday at 12:01 a.m. Pacific (Oct 27 to 29), draft 6.3. If it does not go, spend that time on replies and creator follow-up.

**Week 4 (Oct 28 to Nov 6)**
1. Keyfeel entry in the November App Pile (posted about Nov 1) if it was held (draft 6.4).
2. Follow up with creators only once and only if a video went live (a thank-you that includes any bug found).
3. Review: for each channel, visits, trials, sales. Keep the two or three that produced visits and retire the rest. Record in `Outreach/OUTREACH-LOG.md`.
4. For Vitae, schedule pitches aimed at December annual-report season for the 30 days after this plan.

### 5.4 What not to do

- Do not post Keyfeel in r/MechanicalKeyboards, and do not use the Mechvibes or Klack Discords to market.
- Do not copy the McCleaner pattern: no template reply repeated across threads, no replies in the same thread more than once.
- Do not reply with Vitae on r/PhD, r/GradSchool, r/academia or r/postdoc.
- Do not use Apple Community or MacRumors for product replies.
- Do not pay for AlternativeTo priority, Uneed tiers, MacMenuBar sponsorship slots or MacSources sponsored posts. No source read ties paid placement to conversions for a $10 tool.
- Do not claim speed, "safe", "AI", latency numbers or macOS 27 support that have not been measured or tested. Do not call Legroom "safer" than DaisyDisk or Keyfeel "better" than Klack.
- Do not ask anyone to upvote anywhere (Product Hunt and Hacker News both prohibit it; Reddit communities flag vote solicitation).
- Mac Suite ($54.99) belongs in a link or a closing line on a product page, not in first contact text.

---

## 6. Draft first-contact texts

All plain, no hype. Prices and claims are only those on the product pages as read 2026-10-07 (https://purplelink.llc/legroom/, https://purplelink.llc/keyfeel/ on origin/main). Replace bracketed items. Ben sends them; none has been sent.

### 6.1 Reddit disclosed reply, Legroom (for a System Data or "what is using my space" thread)

Use after the thread has been read through and the answer is fully given in the reply itself.

```
A few places to look first, none of which need an app:
1. System Settings > General > Storage, then wait for it to finish calculating. System Data is everything that does not fit another label, so it can be large and unhelpful.
2. In Terminal, `tmutil listlocalsnapshots /` shows local Time Machine snapshots. They count as space macOS can clear when it needs to, so they can look big without being a problem.
3. In Finder, open ~/Library, choose View > Show View Options > Calculate all sizes, and sort by size. Caches, Application Support and Containers are the usual suspects.

Disclosure: I make Legroom, a $9.99 Mac app that does the checking above on a schedule. It measures where space goes once a day and shows which folders grew over 1, 7 or 30 days, and you can make a rule for a folder or cache that shows exactly what it would remove before you approve it. It does not make a Mac faster, and it cannot see local snapshots (it lists them as "size not reported"). It has a 7-day trial. If you would rather not install anything, DaisyDisk ($9.99) and GrandPerspective (free) are the usual ways to see sizes, and Mole is a free command line tool. [link only if asked, or put it in your profile]
```

### 6.2 Show HN, Legroom

- Title (under 80 characters): `Show HN: Legroom, a Mac menu-bar app that shows what grew on your disk`
- URL: `https://purplelink.llc/legroom/?utm_source=hn&utm_medium=showhn&utm_campaign=legroom-oct26`
- First comment:

```
I make Legroom. It sits in the menu bar and shows free space on the startup disk, plus the space macOS says it can clear, since Finder, System Settings and df often disagree. Once a day it measures where space goes, and "What Grew" compares those measurements over 1, 7 or 30 days so you can see which folder filled the disk. You can then make a rule for a folder or cache; every rule shows a preview of what it would remove, says whether it goes to the Trash or is deleted, and runs only after you approve it.

What it does not do: it does not scan as administrator, so local Time Machine snapshots and some other space show as "size not reported" instead of a guess. It does not run commands; where a fix needs Terminal it shows the command as text. It makes no network requests except a daily update check, and it has no account or analytics.

It is macOS 14 or later, Apple silicon and Intel, signed and notarized. The trial is the full app for 7 days with no account; after that the readout and low-space alerts keep working and the rest needs a $9.99 key. I would like to hear where its numbers disagree with yours, and which folders you would want it never to touch.
```

Check the exact HN title limit (80 characters) and that the app can be tried without a sign-up before posting.

### 6.3 Product Hunt maker comment, Keyfeel

Posted from Ben's personal account. The main URL carries no UTM.

```
I made Keyfeel because I wanted my Mac to sound like a keyboard I like without buying a different keyboard. It runs in the menu bar and plays a recording of a real switch when you press a key, with a different recording on each press. It also has mouse-click sounds, scroll ticks that follow how fast you scroll, and optional trackpad haptics.

It reads which key was pressed, as a key code, and never the characters you type. It needs the macOS Input Monitoring permission, works offline, and goes quiet on its own while the microphone is in use. You can silence it in chosen apps. It can import Mechvibes sound packs. It needs macOS 13 or later.

The trial is the full app for seven days with no account. After that it is $9.99 once, with updates included. Klack is $4.99 and does the keyboard part very well, so I would like to know whether the mouse, scroll and haptic parts are worth the difference to you. Questions about sound, latency or the permission are welcome.
```

### 6.4 r/macapps App Pile entries (PCP format)

Legroom:

```
**Legroom: menu-bar free space readout and cleanup rules for Mac**

I'm the developer.

**Problem:** macOS's storage screen says "System Data" and little else, and the numbers differ between Finder, System Settings and df. Legroom shows free space in the menu bar plus the space macOS says it can clear, measures where your space goes once a day, and shows which folders grew over 1, 7 or 30 days. You can make a rule for a folder or cache, see a preview of what it would remove, and approve it. Rules can run by hand, on a schedule, or when free space drops below a line you set.

**Comparison:** DaisyDisk ($9.99) and GrandPerspective (free) show where space is, but neither runs rules. Mole for Mac ($19) and CleanMyMac are broader cleaners. DiskFox and StorageRadar (both $9.99) are the closest to Legroom; I have not compared them side by side and will not claim Legroom is better. Legroom does not scan as administrator, so local snapshots show as "size not reported", and it does not speed up your Mac.

**Pricing:** 7-day full trial, no account. After that $9.99 once; the menu-bar readout and low-space alerts keep working without a key. macOS 14 or later, Apple silicon and Intel, signed and notarized. No analytics; the only network use is a daily update check.

[Website](https://purplelink.llc/legroom/?utm_source=macapps-pile&utm_medium=reddit&utm_campaign=legroom-oct26)
```

Keyfeel:

```
**Keyfeel: keyboard switch sounds, mouse clicks, scroll ticks and optional trackpad haptics in the menu bar**

I'm the developer.

**Problem:** I wanted real mechanical-switch sounds on a laptop keyboard, plus sounds for the mouse and scrolling, without running something that logs what I type. Keyfeel plays a recording of a real switch on each key press (a different recording each time), adds mouse-click sounds, scroll ticks that follow scroll speed, and optional trackpad haptics. It uses key codes, not the characters, and works offline.

**Comparison:** Klack ($4.99) is excellent for keyboard sounds and costs half as much. Thock and Mechvibes are free. Haptyk and Snick cover haptics and scroll. Keyfeel tries to cover keyboard, mouse, scroll and haptics in one menu-bar app, imports Mechvibes sound packs, and goes quiet while the microphone is in use or in apps you choose. It needs the Input Monitoring permission.

**Pricing:** 7-day full trial, no account. $9.99 once after that, updates included. macOS 13 or later, Apple silicon and Intel.

[Website](https://purplelink.llc/keyfeel/?utm_source=macapps-pile&utm_medium=reddit&utm_campaign=keyfeel-oct26)
```

### 6.5 Outlet pitch email (Keyfeel; swap the details for Legroom)

Subject: `Keyfeel: a Mac app for keyboard, mouse and scroll sounds ($9.99, 7-day trial)`

```
Hello [name],

I am Ben Ampel, a solo developer in Atlanta (Purplelink LLC). I released Keyfeel on October 7. It is a menu-bar app that plays recorded mechanical-switch sounds when you type, with mouse-click sounds, scroll ticks and optional trackpad haptics. It reads key codes, not the characters, and works offline. It imports Mechvibes sound packs, and goes quiet in apps you choose and while the microphone is in use.

I know Klack does the keyboard part well for $4.99, and Keyfeel costs $9.99 once, so the question for a reader is whether mouse, scroll and haptic sounds are worth it. If you would like to try it, I can send a license key, and the trial is the full app for seven days with no account. Page: https://purplelink.llc/keyfeel/?utm_source=pitch-[outlet]&utm_medium=email&utm_campaign=keyfeel-oct26

No reply is needed if it is not a fit. I will not follow up.

Ben Ampel
ben@purplelink.llc
```

### 6.6 Creator email (Keyfeel)

Subject: `Keyfeel key for you, if a Mac typing-sound app is ever useful for a video`

```
Hi [name],

I watched [exact video title] and liked [one specific, true thing from it].

I am a solo developer. I released Keyfeel on October 7: a Mac menu-bar app that plays recorded keyboard-switch sounds, mouse clicks, scroll ticks and optional trackpad haptics. It reads key codes, not the characters, and works offline. It needs macOS 13 or later and the Input Monitoring permission. The trial is the full app for 7 days with no account, then it is $9.99 once.

If you want to try it, reply and I will send you a license key at no cost. There is no obligation to cover it, and I am not asking for a positive review. If you do mention it, please say it was provided free. If you find a bug or something that sounds bad, I would rather hear it directly.

Ben Ampel, Purplelink LLC
ben@purplelink.llc
https://purplelink.llc/keyfeel/?utm_source=yt-[handle]&utm_medium=email&utm_campaign=keyfeel-oct26
```

### 6.7 Vitae first contact (essay or blog editor)

```
Subject: Pitch: why faculty should keep their own record from year one

Hello [name],

I am a tenure-track information-systems professor. I am writing to propose a [word count]-word piece on keeping your own record of submissions, grants, projects and collaborators from the first year of the tenure track, so that the CV, the annual report and the tenure file are all drawn from one place instead of rebuilt each time. [One concrete anecdote about a rebuild.]

Disclosure: I also built a free Mac app, Vitae, for this. The piece is about the habit and does not depend on the app, and I will name the app only in the bio, if you want it there.

I can send a draft within [timeframe]. 

Ben Ampel
```

### 6.8 Vitae reply (r/AskAcademia or r/Professors, only if a thread asks about systems)

```
What has worked for me is one record that everything else is generated from, rather than separate lists in the CV, the annual report and the tenure file. I keep each submission with its dates and status, each grant with the outcome (funded or not), and each project with its collaborators, and I build the CV from that record at the end rather than editing the CV by hand. Unfunded grants stay in the record even when they are not on the public CV. A spreadsheet works for this if you are strict about one row per item.

Disclosure, since you asked about systems: I wrote a free Mac app for exactly this called Vitae, but a spreadsheet does the job too and I would not push anyone to switch.
```

---

## Gaps and unresolved items

- Rules text for r/macapps, r/MacOS, r/mac, r/MechanicalKeyboards, r/asmr, r/AskAcademia, r/GradSchool, r/academia, r/Professors and r/postdoc is second-hand (Redlib mirror, ThreadOtter, snippets). The App Pile requirements (karma, identity, privacy policy, ToS) and the tier definitions are not confirmed. The 30-day limit's scope is unclear. Reddit's own spam policy and 9:1 status conflict between secondary sources.
- Stack Exchange and MacRumors rules were not read on the pages (MacRumors snippet only). No Apple Community, MacRumors or Ask Different threads from August to October were found.
- WebSearch budgets ran out in every pass, so many "not found" lines may be undiscovered rather than absent. Setapp membership review time, AlternativeTo standard queue and fee amount, MacMenuBar listing fee and review time, Disk Drill dollar prices (snippet only), Trace, DiskPress and App Archiver prices were not found.
- Product Hunt official pages were summarized by the fetcher. No official text on a required maker comment, AI-generated content, or account age and karma was found. Launch-outcome figures are all second-hand.
- The HN second-chance pool description is a search snippet only.
- Not read or 403: AppleInsider, The Mac Observer, Mac Informer, Slant, Softpedia, Lifehacker, Mac Kung Fu, Chronicle of Higher Education, Science Careers, Podfeet, ORCID. Not checked: TikTok creators (login wall), Keychron and r/MechanicalKeyboards Discords, X, LinkedIn, Facebook groups, graduate-student Slack and Discord, r/olkb, r/Keychron, r/typing rules.
- YouTube subscriber counts are YouTube's rounded display numbers on 2026-10-07. Two passes disagree on Better Creating (43.4K versus 268K); verify before contacting. Some creators gate their email behind "View email address".
- A few Reddit threads in lists 1.5 and 2.5 are only one to three days old; comment counts move quickly.
- Competitor details for Typemac, Keeby, CupertinoClicks, KeyBell lifetime price, and HapticPad come from a rival's comparison page or snippets.
- No survey of US faculty record keeping, and no credible dataset of results for small paid Mac utilities, was found.
- Keyfeel's macOS 27 compatibility and Legroom's behavior on macOS 27 were not checked here; confirm before replying to any macOS 27 thread.
