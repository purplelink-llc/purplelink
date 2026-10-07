# Reddit research for ModernTex, fetched 2026-10-07

Read-only. Nothing was posted, voted, commented, or signed up anywhere.

Labels used on every claim:
- **VERIFIED**: read directly from the Reddit post or comment text, via the Reddit MCP tools (`fetch_reddit_hot_threads`, `fetch_reddit_post_content`), on 2026-10-07.
- **SECONDARY**: from a third-party page or a search summary, not Reddit itself.
- **UNVERIFIED**: inferred, estimated, or not confirmed.
- **NOT FOUND**: could not be retrieved.

---

## 0. What worked, what was blocked, how dates were estimated

**Worked:** the Reddit MCP tools. Hot listings of up to 100 posts, and full post text plus comments for any post ID. Most "rules" below come from moderator announcement posts read this way, not from sidebars.

**Blocked (so, not retrieved):**
- `reddit.com/r/<sub>/about/rules.json`, `about.json`, `old.reddit.com/.../about/rules`. WebFetch says it cannot fetch reddit.com or old.reddit.com. curl returned HTTP 403 (Reddit's block page) or a 302.
- The built-in browser pane refuses reddit.com and old.reddit.com ("not allowed due to safety restrictions").
- WebSearch with `allowed_domains: reddit.com` returned "not accessible to our user agent". The session's WebSearch budget is also used up (200 of 200).
- DuckDuckGo showed a CAPTCHA. web.archive.org is refused by WebFetch. I did not try to get around the CAPTCHA or any bot check.
- Consequence: **the full current sidebar rule text for r/LaTeX, r/AskAcademia, r/GradSchool, r/academia, r/math, r/typst, r/SideProject and others is NOT FOUND.** Where I give a rule, it is quoted from a mod post I could read. Where no mod post was readable, I say so.
- r/thesiswriting returned "banned". r/OverleafGuide and r/AcademicMac returned "302 Found" (probably no such sub, UNVERIFIED). r/dissertation exists but is survey-recruitment spam. r/tex exists and is nearly silent (3 posts in the hot list).

**Dates:** the MCP returns no timestamps. I estimated dates from Reddit post IDs, calibrated on r/LaTeX post 1wsvyvm = 2026-09-29. Recent posts are good to about +/- 1 day. Anything before 2026-06 (mod announcement posts) is only good to +/- 3 weeks.

**Reachable window:** a hot listing is the only listing available. For r/LaTeX, 100 posts reach back to about 2026-09-04. For r/AskAcademia, r/PhD, r/macapps and r/GradSchool, 100 posts reach back only about 1 week (2026-09-29 to 10-07). So threads from 2026-08-15 to 09-03 could not be reached at all. See section 7.

---

## 1. Things Ben should know before posting anything else

1. **Ben already posted a standalone maker post in r/LaTeX.**
   - "I built a native Mac LaTeX editor for writing papers. Here's what it does and doesn't do." Author u/PurplelinkPL. https://www.reddit.com/r/LaTeX/comments/1wwtdoy/ , about 2026-10-03. VERIFIED.
   - Score 0, 4 comments. Not removed.
   - The post body says "$10 once" and "1.0.2 and about two weeks old". The site now says $19.99 (`site/moderntex/index.html`, e.g. line 209). A commenter quoted the old price ("Buying is $10 once, with every 1.x update included. What about 2.x?"). Ben replied that all updates are included forever. VERIFIED. **Any new comment must use $19.99 and the current version, or it looks inconsistent.**
   - Comments:
     - u/efusy (5 points): "Does not seem to do enough to warrant a switch away from things like Overleaf."
     - u/Hairy_Glove2064 (2 points) complained that all new LaTeX editors "advertise the same set of features".
   - Because Ben posted here four days ago, more promotional replies in r/LaTeX now would look like a pattern. I rate that risky (my judgement, not a stated rule).

2. **r/LaTeX has an AI-content rule.**
   - The stickied "[MEGATHREAD] AI Generated Content" (by u/SonusDrums, 2026-09-10, https://www.reddit.com/r/LaTeX/comments/1wd1w1q/ ) says AI-generated content posted outside the megathread "will be removed" and "Minor AI assistance should be disclosed in posts outside of this mega thread." VERIFIED.
   - It followed a thread, "Mods: can we get a way to report AI slop?" (189 points, https://www.reddit.com/r/LaTeX/comments/1wccvnf/ , 2026-09-09). That thread said "most of the recent posts are promoting some AI-built tool." A top comment (115 points) is now "[removed]". The mod replied that it "has been done". VERIFIED.
   - If any of ModernTex was AI-assisted, Ben has to decide how to disclose it. I have not assumed either way.

3. **r/PhD bans tools with a free trial.**
   - "Policy on tools and promotions" (u/Eska2020, about 2026-01-28, https://www.reddit.com/r/PhD/comments/1r11qx4/ , 83 points). VERIFIED.
   - Text: tools allowed only if open-source, industry-standard, or from "small/indie developer outfits" with "track records of transparent, fair pricing (Scrivener, Obsidian, etc.)".
   - Litmus test, quoted: a personal project is only welcome "if it does not have a 'free trial' button or a 'free tier'".
   - They threaten "removing and issuing permabans". ModernTex has a 7-day trial, so it fails this test as written. **Do not mention ModernTex in r/PhD.**

4. **r/macapps Rule 3 is once per developer per 30 days.**
   - Counted "from the last app post, even if it was removed". Updates count as promotion. VERIFIED, see 3.2.
   - Ben posted in the September App Pile on 2026-09-29. Whether a megathread comment counts toward the 30 days is **UNVERIFIED**. The safe date for the October App Pile is on or after about 2026-10-29, or ask the mods by modmail.

5. **Competitor "new LaTeX editor" posts are being met with fatigue.** See section 4. That is the climate for any new editor post.

---

## 2. Subreddit table (subscribers, self-promotion rule status, conventions)

Subscriber counts come from gummysearch.com pages fetched via WebFetch on 2026-10-07. These are **SECONDARY** (third-party aggregator). Each page states its own "Last updated" date, shown below. Reddit's own about.json was blocked.

| Subreddit | Subscribers (source date) | Self-promo rule text | Conventions seen |
|---|---|---|---|
| r/LaTeX | 89k (updated 2026-10-02). A search snippet said 75k, undated, UNVERIFIED. https://gummysearch.com/r/LaTeX | **NOT FOUND.** Only the AI rule (section 1) is verified. | Stickied AI megathread. No weekly or monthly thread in the 100-post window (VERIFIED absence). |
| r/macapps | 255k (2026-10-05). https://gummysearch.com/r/macapps . A roundup thread says it reached 250,000 members (https://www.reddit.com/r/macapps/comments/1wncput/ , VERIFIED title in roundup). | **VERIFIED**, see 3.2 | Monthly App Pile megathread. Monthly roundup by u/NeonSerpent. |
| r/MacOS | 646k (2026-10-05) | NOT FOUND | No sticky seen. Support and troubleshooting threads. |
| r/mac | 3.1M (2026-10-05) | NOT FOUND | Same. |
| r/MacOSApps | 27k (2026-10-05) | NOT FOUND | Open self-promotion. Posts like "[FREEMIUM] I Created..." and "($1 Reddit Promo)" sit in the hot list with 0 to 63 points. |
| r/GradSchool | 946k (2026-10-02) | NOT FOUND directly. Mod megathreads say "All other community rules are still applicable within this megathread, including our rule around spam." VERIFIED. | Weekly AutoModerator megathreads: "AI in Grad School" (https://www.reddit.com/r/GradSchool/comments/1wujitw/ , about 10-01) and "Time Management in Grad School" (https://www.reddit.com/r/GradSchool/comments/1wujiu8/ ). |
| r/AskAcademia | 2.1M (2026-10-01) | NOT FOUND | No tool megathread seen. Hot list is career and publishing questions. |
| r/PhD | 288k (2026-10-01) | **VERIFIED**, section 1, item 3 | "Decision Season" rules post (https://www.reddit.com/r/PhD/comments/1sa2ou0/ , about March 2026). |
| r/academia | 110k (2026-10-02) | NOT FOUND | No sticky seen. |
| r/Professors | 201k (2026-09-30) | NOT FOUND | Themed daily threads ("Oct 07: Wholesome Wednesday"). Official Discord post. |
| r/postdoc | 30k (2026-10-01) | **VERIFIED**: "No spam/scams/selling services/self-promotion." (https://www.reddit.com/r/postdoc/comments/ulmk8a/ , old 2022 post, UNVERIFIED that it is unchanged) | Mods remove PhD-admissions posts (https://www.reddit.com/r/postdoc/comments/1wwvwod/ , about 10-03). |
| r/labrats | 728k (2026-10-01) | **VERIFIED** (mod post https://www.reddit.com/r/labrats/comments/1ww3asi/ , about 2026-10-02): mods remove "tool feedback requests", "marketing surveys", and "3-5 posts/day" of tool posts. Tool posts go to the pinned **Monthly Bulletin Board** (https://www.reddit.com/r/labrats/comments/1wvmeby/ , October edition). The Bulletin Board says "direct product advertising still aren't allowed". | Monthly Bulletin Board. |
| r/math | 4.0M (2026-10-01) | NOT FOUND | Recurring: "Quick Questions: October 07, 2026" (https://www.reddit.com/r/math/comments/1x00c58/), "What Are You Working On? October 05, 2026" (https://www.reddit.com/r/math/comments/1wyas74/). |
| r/AcademicPhilosophy | 63k (2026-09-30) | **VERIFIED** (https://www.reddit.com/r/AcademicPhilosophy/comments/1lql4g3/ , about 2025-06): "Own work posts are now banned"; accounts must be at least 30 days old and have commented. Recruitment-type posts only in a stickied CFP thread. | |
| r/AskEconomics | 1.5M (2026-09-30) | NOT FOUND | Comments are filtered, so only "Quality Contributors" are auto-approved. |
| r/compsci | 4.0M (2026-10-01) | NOT FOUND | Scope-clarification sticky from about 2019. |
| r/Physics | 3.3M (2026-10-01) | NOT FOUND | Weekly AutoModerator threads: "Physics Questions" (10-06), "Careers/Education" (10-01). |
| r/typst | **5k, last updated 2025-01-17, stale** (https://gummysearch.com/r/typst); current figure UNVERIFIED | NOT FOUND | Several editor-launch posts, many hostile replies (section 4). |
| r/Overleaf | 1k (2026-09-30). The founding mod posted a "would anyone like to mod?" notice about mid-2024. The newest posts in the hot list are about Dec 2025. | NOT FOUND | Effectively dormant. Not a venue. |
| r/OverleafGuide, r/AcademicMac | NOT FOUND (302) | | |
| r/Zotero | 15k (2026-10-02) | NOT FOUND | Lots of "I built a free plugin" posts. |
| r/LyX | NOT FOUND (no aggregator page) | NOT FOUND | Hot list is mostly 2026-04 to 2026-05 posts. Quiet. |
| r/SideProject | 863k (2026-10-06) | NOT FOUND. A SECONDARY directory lists it as "Self-promotion welcome" (https://oneup.today/tools/reddit-self-promotion-checker, no rule text shown). | Old stickies: "Share your Not-AI projects" (https://www.reddit.com/r/SideProject/comments/1oaq2kx/ , about Oct 2025). |
| r/indiehackers | 196k (2026-10-05) | **VERIFIED** (mod posts https://www.reddit.com/r/indiehackers/comments/1pj44es/ about 2025-11, and https://www.reddit.com/r/indiehackers/comments/1uzsfzy/ about 2026-07): use the Self Promotion flair; MRR claims need proof; "New reddit accounts will need to wait and ask questions through modmail only." Self-promotion may be restricted to certain weekdays. | |
| r/IndieDev | 456k (2026-10-02). Mostly game developers. | NOT FOUND | |
| r/AskStatistics | 136k (2026-10-02) | NOT FOUND | No LaTeX threads in the hot list. |

---

## 3. Rule text in detail

### 3.1 r/LaTeX
- Current sidebar and rules: **NOT FOUND** (Reddit blocked).
- Verified: the AI-content rule and megathread (section 1, item 2).
- Verified by behaviour:
  - Developer posts are common. Many were not removed (Warm_Ad1115's posts, Eukolia, click-in-preview editor, Ben's).
  - One was removed after the fact: LeafOver (https://www.reddit.com/r/LaTeX/comments/1ws9ou9/ , 2026-09-28). Its body now reads "[removed]", but 17 comments remain. The reason is not stated, so I cannot say whether a mod or Reddit removed it, or why. VERIFIED that it is removed. Cause UNVERIFIED.
  - Eukolia's author deleted their account or post, and one reply is "[removed]" (https://www.reddit.com/r/LaTeX/comments/1wn1z9g/ , 2026-09-22).
- Flair conventions: not observable through the tool.

### 3.2 r/macapps (the best-documented sub)
Source: mod u/Mstormer's announcement "r/MacApps Mods Went Too Far! What's Changing (Phase 3)", https://www.reddit.com/r/macapps/comments/1ryaeex/ (about 2026-03-08, UNVERIFIED +/- 3 weeks). VERIFIED text.
- **Post format ("PCP"):** Problem, Comparison, Pricing. Name 1 to 2 competitors and say how you differ. Give the price and a link.
- **Three tiers**, described as an experiment "for the next month" back then. The App Pile still exists for October 2026, and its comments follow the PCP format, so I rate it still in force. Current status UNVERIFIED.
  - Tier 1, main feed: Mac App Store developers; established GitHub projects (1 year or more of history and 100+ stars); or a recognized-developer flair. All need 10+ local karma.
  - Tier 2, main feed, **ModernTex's likely route**: if you are not in the App Store and not an established developer, the post "must include BOTH" a developer portfolio with real-life identity, LinkedIn and contact details ("e.g. established company / business presence"), and a website with a Privacy Policy and Terms of Service. This matches the note in `/Volumes/Extreme SSD/Purplelink LLC/docs/reddit-notes-2026-09-29.md`.
  - Tier 3: everyone else goes in the monthly **App Pile** megathread. A flair that allows main-feed posting comes with "500+ r/MacApps participation karma AND Moderator's discretion".
- **Rule 3 (frequency):** "not permitted more than once per developer in 30 days. This is counted from the last app post, even if it was removed." Well-known flaired developers can post once per app per month.
- **Comments:** always disclose your relationship to the app. "Promoting your own app in comments is disallowed until you earn 10 karma in r/MacApps and in poor taste when hijacking another developer's promotion."
- **Rule 8 (from the 2025 rules post, https://www.reddit.com/r/macapps/comments/1o01a9f/ , about 2025-09):** asks developers to self-disclose AI/"vibe-coded" use. Those details are in that post. The Phase 3 post says AI disclaimers were dropped from the required format. Which applies today is UNVERIFIED.
- **Auto-removal causes (FAQ in the Phase 3 post):** AI-assisted comments with em dashes; repeated identical posts or links; an unverified profile email or multiple accounts; reposting after a removal instead of editing and waiting for a restore.
- **Current convention visible in the October App Pile** (https://www.reddit.com/r/macapps/comments/1wuoav5/ , by u/Mstormer, about 2026-10-01, 37 points, 130 comments): top-level comments by developers, each starting "I'm the developer", with **Problem / Comparison / Pricing** headings. VERIFIED.
- **Monthly dates:** one megathread per month, titled "[Megathread] The App Pile - <Month>, 2026". The October one went up about 2026-10-01 (UNVERIFIED day).

### 3.3 Other readable rule sources
- r/PhD (section 1, item 3). r/labrats (section 2). r/AcademicPhilosophy, r/indiehackers, r/postdoc (section 2). r/GradSchool: only the "rule around spam" phrase.
- No readable rule text for r/AskAcademia, r/academia, r/math, r/Physics, r/compsci, r/MacOS, r/mac, r/SideProject, r/typst, r/Zotero.

---

## 4. What happened to developer posts (evidence)

All VERIFIED from post pages and hot lists, 2026-10-07. Dates are estimates.

**r/LaTeX**
| Post | Date | Score / comments | Outcome |
|---|---|---|---|
| Ben's ModernTex maker post, https://www.reddit.com/r/LaTeX/comments/1wwtdoy/ | 10-03 | 0 / 4 | Kept. Skeptical replies (section 1). |
| LeafOver, "I got tired of Overleaf compile limits, so I built a local LaTeX workspace for coding agents", https://www.reddit.com/r/LaTeX/comments/1ws9ou9/ | 09-28 | 0 / 17 | **Body removed.** Top reply (10): "… and this is different than the thousand other options for a local setup because?" Another (4) joked "Ten AI slops posted on Reddit". |
| Eukolia, free modern editor, https://www.reddit.com/r/LaTeX/comments/1wn1z9g/ | 09-22 | 0 / 16 | Author deleted. Top reply (5): "Why should I use your project over vscode with a latex plugin or overleaf for which my institution provides a licence?" |
| Click-in-the-preview editor, https://www.reddit.com/r/LaTeX/comments/1wsvyvm/ | 09-29 | 0 / 3 | Kept. Friendly replies only. |
| "My Fully Local LaTeX IDE" (Android/Termux, Warm_Ad1115, several near-duplicate posts), https://www.reddit.com/r/LaTeX/comments/1x00lob/ | 10-07 | 0 / 7 | Kept. Top reply (9): "why should anyone use it over whatever IDE they're already using, do some advertising for your product". Another (3): "since AI has become good enough everybody and his brother has done a local viewer/editor for LaTeX". |
| "Give it a Try" (u/Educational_Fig_5775), https://www.reddit.com/r/LaTeX/comments/1wyel0b/ | 10-05 | 0 / 4 | Top reply (8): "Wow, the LaTeX market is really a multi-billion dollar industry!" |
| texlode update (real-time WYSIWYG editor), https://www.reddit.com/r/LaTeX/comments/1wxbk8m/ | 10-04 | 14 / 34 | Kept. Top reply (17): "Another online service, I will pass. Why nobody offer local stuff anymore..." Another (9, u/DungAkira): "I prefere the flexibility from a local version for which I am willing to pay." |
| "I built a VS Code extension around Git + LaTeX + git-latexdiff", https://www.reddit.com/r/LaTeX/comments/1waffg6/ | 09-07 | **163 / 12** | Did well. A tool for a concrete workflow (revision diffs for journals) with a public README and tutorial repo; price not stated. |
| Real-time LaTeX preview in WASM (engine write-up, source to be released), https://www.reddit.com/r/LaTeX/comments/1wrvhig/ | 09-27 | 32-35 / 27 | Did well. Technical substance, not a product pitch. |
| Hobby TeX engine updates (u/DanielSussman) | 09-29, 10-03 | 42-44 / 15, 34 / 13 | Did well. |

**Pattern:** what scores is technical depth or a free tool that solves a named workflow. What gets 0 is "I built an editor" with no stated difference from VS Code, TeXShop or Overleaf. Two signals fit ModernTex's offline positioning: the "local, and I'd pay for it" comments on the texlode thread, and the top comments ("My data is mine." 62 points) on the 46-point "locally vs online" thread (section 6, B1).

**r/typst**: LeftBlank, "free, open-source native Typst editor for macOS" (https://www.reddit.com/r/typst/comments/1wvvb9k/ , about 10-02, 0 / 6). Replies: "Take that effort and contribute to an existing project instead. Please!"; a link to a joke site called "days-since-last-typst-editor"; "this has to be a joke". Native-Mac editors are a visible niche, and the community is tired of them. Note this is a competitor for the same Mac-native niche: macOS 14+, Apple silicon only, free, open source, Typst not LaTeX.

**r/macapps** (hot list and roundup):
- The September roundup (https://www.reddit.com/r/macapps/comments/1wzts9p/ , by u/NeonSerpent, about 10-07) ranks main-feed posts. Paid "Lifetime" apps appear with high numbers: FeelMyMac 478 votes / 248 comments; Tracer 341 / 863; Nodes 2.0 (native Markdown editor, lifetime) 231 / 182; Caxton (editor for huge text files, lifetime) 128 / 72. Free and open source apps lead: Purge 647 / 212.
- **No LaTeX app appears anywhere in the September roundup**, including the "10+ votes" pinned comment. Ben's App Pile comment is not in it (the roundup does not list megathread comments).
- Paid one-time apps with trials post at low scores in the current hot list: DiskFox ($9.99, 2-week trial, 0 / 36), Drive Gadget ($10, 0 / 7), Start Menu for Mac (US$11.99, 14-day trial) is a top-level App Pile comment with 3 points.
- A meme thread, "Every app thread on r/macapps lately" (301 points, https://www.reddit.com/r/macapps/comments/1wyzkg0/), shows the sub is quick to attack apps seen as copying other developers' ideas.

---

## 5. Site-wide Reddit rules (what I could and could not verify)

- Reddit's own help pages (support.reddithelp.com, redditinc.com) were blocked, so I **could not read Reddit's current Content Policy or Reddiquette directly.**
- SECONDARY (search summary of Reddit's Content Policy, 2026-10-07): "post authentic content into communities where you have a personal interest, and do not cheat or engage in content manipulation (including spamming, vote manipulation, ban evasion, or subscriber fraud)". Treated as a paraphrase, not quoted text.
- SECONDARY: a third-party guide, https://redship.io/blog/reddit-self-promotion-rules-2026 (page dated 2026-07-02), says:
  - The 9:1 / 90-10 ratio is "widely cited guidance rather than official policy".
  - It comes from the Reddiquette line "it's fine to be a redditor with a website, it's not fine to be a website with a Reddit account".
  - "100+ comment karma to post at all" appears on some subs and none on others. There is no site-wide karma minimum.
- Other SECONDARY pages (search snippets) repeat that individual subreddit mods set their own self-promotion rules.
- **VERIFIED sub-level gating:**
  - r/macapps: 10 local karma to post; 10 karma before promoting your own app in comments.
  - r/AcademicPhilosophy: account at least 30 days old and prior comments.
  - r/indiehackers: new accounts "wait and ask questions through modmail only".
  - r/LaTeX, r/AskAcademia, r/GradSchool and others: NOT FOUND.
- **VERIFIED platform-level removals** (r/macapps FAQ): Reddit's own spam filters remove repeated identical comments or links, and AI-style text with em dashes; also unverified-email and multi-account profiles. This is a subreddit mod's description of Reddit's filters, not Reddit's own text.

---

## 6. Threads where a disclosed ModernTex reply could be legitimate

Honest summary first: I found **3 reasonably good fits, 3 optional fits, and 6 weak ones**. Only the first three are worth the effort. The window was limited (sections 0 and 7). All are r/LaTeX unless noted. Every reply should say who Ben is, answer the question first, use $19.99 and the 7-day trial, and not repeat his 10-03 post.

### A. Reasonable fits

**A1. "Need help setting up a LaTeX + LilyPond workflow for music theory exams (Mac M1)"**
- https://www.reddit.com/r/LaTeX/comments/1wis640/ , about 2026-09-17, score 6, 6 comments. VERIFIED.
- Asked: how to run inline LilyPond in LaTeX; "What editor should I use? ... I'm on an M1 Pro Mac." Uses TeXShop, Texmaker, TeXstudio. In a follow-up comment OP asks: "Any recommendations on LaTeX-Editors on Mac?"
- Why it fits: a direct Mac editor ask. Gaps: the thread is 20 days old, and two replies already cover lyluatex.
- Angle: answer the lyluatex / shell-escape point accurately first. Then, only if ModernTex can compile with `--shell-escape` (**UNVERIFIED, Ben must check**), say it is a native Mac option from the replier, disclosed, 7-day trial.

**A2. "Learning Texify"**
- https://www.reddit.com/r/LaTeX/comments/1wkc7wb/ , about 2026-09-19, score 7-9, 13 comments. VERIFIED.
- Asked: TeXstudio "now deprecated on homebrew (M silicon Mac)", overwhelmed by PyCharm plus TeXiFy.
- A commenter confirmed the Homebrew cask "was disabled on 2026-09-01" because it fails the Gatekeeper check. Another says the website download works after approving it in Privacy and Security. Others suggest VS Code with LaTeX Workshop, TeXShop, Neovim, Texpile.
- Why it fits: this is ModernTex's exact user (Mac, wants something lighter than an IDE). Gap: 18 days old.
- Angle: confirm the website build works, point to TeXShop as the free option, then one disclosed sentence on ModernTex (native, trial, normal .tex files).

**A3. "Compiling and Collaborating with Dropbox"**
- https://www.reddit.com/r/LaTeX/comments/1wohvqy/ , about 2026-09-23, score 6-7, 14 comments. VERIFIED.
- Asked: math grad student hit the Overleaf free-plan compile timeout; "I normally compile LaTeX natively, but I share this with my advisor".
- Replies: shared Dropbox folder, git remote on Dropbox, Overleaf Workshop for VS Code. A joke implies OP might be on Windows (OP's platform not stated).
- Why it fits: it is the Overleaf-timeout complaint. Gap: ModernTex does not solve the advisor-on-Overleaf collaboration problem. Say so.
- Angle: only add if ModernTex's folder-based project works well in a synced folder, and OP is on a Mac (**UNVERIFIED**). Otherwise skip.

### B. Optional, thin fits

**B1. "How do you prefer to write LaTeX: locally vs online?"**
- https://www.reddit.com/r/LaTeX/comments/1wxhiv9/ , about 2026-10-04, score 44-46, 53 comments. VERIFIED.
- Top comments: "My data is mine." (62); Overleaf "now any project with more figures exceeds the compilation time limit for free accounts" (40); "Getting hit with 'your document took long to compile' on a one page letter" (5).
- Fresh and high-traffic, but there is no Mac ask, and Ben posted in the sub a day before. A drive-by pitch would look like it. Angle if used: add a real point (local compile, offline use, ordinary .tex files), disclose, one line on ModernTex.

**B2. "Preparing a latex+git workshop. Ideas?"**
- https://www.reddit.com/r/LaTeX/comments/1wnawgx/ , about 2026-09-22, score 13-14, 2 comments. VERIFIED.
- OP says "My colleagues are complaining a lot about Overleaf lately" and, having never touched Mac or Windows, asks for tips from those OSes.
- Angle: give Mac install facts (MacTeX vs TinyTeX, notarization prompts). Mention ModernTex in one line. Low visibility.

**B3. r/macapps, "What's a small Mac app you use all the time but rarely see mentioned?"**
- https://www.reddit.com/r/macapps/comments/1wxkwu8/ , about 2026-10-04, score 250, 507 comments. VERIFIED.
- Fits a niche daily-use app. But r/macapps needs 10 sub karma before promoting your own app in comments, plus disclosure. The Rule 3 30-day question (section 1, item 4) also applies. Low priority.

### C. Weak fits (include only if nothing better)

**C1. "LaTeX offline reference manual?"** https://www.reddit.com/r/LaTeX/comments/1wxfbf7/ (about 10-04, 4 / 10). Asks for an offline app to look up commands. Fits only if ModernTex has a command reference (**UNVERIFIED**).

**C2. "Sorting out references in PhD before submission"** (r/AskAcademia) https://www.reddit.com/r/AskAcademia/comments/1wzwngq/ (10-07, 0 / 10). EndNote user. Not a LaTeX or editor ask.

**C3. "LyX as a tool for LaTeX"** https://www.reddit.com/r/LaTeX/comments/1wi6yrn/ (about 09-16, 47 / 9). A LyX advocacy post. Reply would be off topic.

**C4. "Install size"** https://www.reddit.com/r/LaTeX/comments/1w8pywr/ (about 09-05, 24 / 24). TeX Live size on a Chromebook. ModernTex's one-click TinyTeX install is relevant, but OP is on Linux. Also over a month old.

**C5. "BEng Thesis in LaTeX"** https://www.reddit.com/r/LaTeX/comments/1wgpe52/ (about 09-14, 23 / 54). Asks about LaTeX to Word conversion. Not an editor ask.

**C6. "AEU (Elsevier) Guide for Authors: does the 20-page limit apply..."** (r/AskAcademia) https://www.reddit.com/r/AskAcademia/comments/1wy66fy/ (about 10-05, 0 / 0). A submission-requirements question. ModernTex's journal checks are on-topic only if OP uses LaTeX with it, and there are no comments yet.

---

## 7. Threads to avoid

| # | Thread | Reason |
|---|---|---|
| 1 | texlode update, https://www.reddit.com/r/LaTeX/comments/1wxbk8m/ (10-04) | Competitor's own launch thread. A pitch here is hijacking (r/macapps even says so by name). |
| 2 | "My Fully Local LaTeX IDE", https://www.reddit.com/r/LaTeX/comments/1x00lob/ (10-07) | Competitor launch; Android/Termux, not Mac. |
| 3 | LeftBlank (r/typst), https://www.reddit.com/r/typst/comments/1wvvb9k/ (10-02) | Competitor launch (native Mac editor for Typst); hostile thread. |
| 4 | LeafOver, https://www.reddit.com/r/LaTeX/comments/1ws9ou9/ (09-28) | Competitor launch; post body removed; AI-tool thread. |
| 5 | Eukolia, https://www.reddit.com/r/LaTeX/comments/1wn1z9g/ (09-22) | Competitor launch; OP deleted. |
| 6 | "I made a lightweight text editor where you fix a LaTeX document directly from the rendered preview", https://www.reddit.com/r/LaTeX/comments/1wsvyvm/ (09-29) | Competitor launch. |
| 7 | "I built a clone of Apple Notes, but with LaTeX and Markdown files (need beta testers)", https://www.reddit.com/r/LaTeX/comments/1wc3tch/ (about 09-09, 0 / 10) | Mac-targeted developer launch asking for testers. Hijacking risk, and it is a month old. |
| 8 | r/macapps PDF viewer feature thread, https://www.reddit.com/r/macapps/comments/1wrsd0f/ (09-27, 0 / 42) | A developer asking what features to build. Not a LaTeX ask, and a pitch would hijack another developer's thread. Some replies asked for live-reload that keeps scroll position, which is a ModernTex-relevant feature. |
| 9 | r/macapps, "Share some free and open source apps you use", https://www.reddit.com/r/macapps/comments/1wzw4t3/ (10-07, 46 / 81) | OP asks for free and open source only. ModernTex is neither. |
| 10 | Neovim + Zathura PDF zoom, https://www.reddit.com/r/LaTeX/comments/1wu306x/ (09-30, 2 / 3) | A Neovim/Zathura user wants a config fix. Wrong tool. |
| 11 | "Please help, my boss just shared an Overleaf project", https://www.reddit.com/r/LaTeX/comments/1wel1y6/ (09-12, 7 / 15) | A one-off preamble fix, due in 2 days, already answered; stays on Overleaf. |
| 12 | r/PhD (anything), https://www.reddit.com/r/PhD/comments/1r11qx4/ | Tool policy bans trial or free-tier products (section 1). Includes the celebratory "I submitted!" thread (35-minute compile), https://www.reddit.com/r/PhD/comments/1wz8iae/ , which is not an ask. |
| 13 | r/labrats (anything) | Mods remove tool posts; only the Monthly Bulletin Board is allowed and "direct product advertising" is not. |
| 14 | r/postdoc, r/AcademicPhilosophy | "No ... self-promotion" and "Own work posts are now banned". |
| 15 | r/Overleaf | Dormant since mid-2024. |
| 16 | r/GradSchool weekly megathreads | They carry a spam rule, and nothing there asks for LaTeX. |
| 17 | r/macapps "What is similar to Scrivener but with Markdown and AI helps...", https://www.reddit.com/r/macapps/comments/1x029di/ (10-07, 3 / 5) | A Markdown writer, not LaTeX. |

Also avoid any thread older than about 30 days that is already answered. Those add little.

---

## 8. Recurring and long-running threads (exact conventions)

All VERIFIED titles and dates unless stated.

- **r/macapps App Pile**: monthly megathread, "[Megathread] The App Pile - October, 2026", posted about 10-01 by u/Mstormer. Comment format: Problem / Comparison / Pricing, begin with "I'm the developer". Karma gating, Rule 3 and disclosure: section 3.2. One thread per month; next one around 2026-11-01.
- **r/macapps Monthly Roundup**: by u/NeonSerpent, about the first week of the month. September: https://www.reddit.com/r/macapps/comments/1wzts9p/ ; August: https://www.reddit.com/r/macapps/comments/1wm9y0n/ . Lists main-feed posts only.
- **r/LaTeX**: no weekly or monthly thread in the 100-post window. Only the stickied AI megathread (2026-09-10).
- **r/GradSchool**: weekly AutoModerator megathreads, "Weekly Megathread - AI in Grad School" and "... Time Management in Grad School", about 10-01. The spam rule applies inside them.
- **r/labrats**: "Monthly Bulletin Board: October, 2026 edition" (https://www.reddit.com/r/labrats/comments/1wvmeby/), AutoModerator, resets monthly. It is where tool and survey posts must go. "Direct product advertising still aren't allowed."
- **r/math**: "Quick Questions: October 07, 2026" and "What Are You Working On? October 05, 2026", recurring. No tool-recommendation megathread.
- **r/Physics**: weekly "Physics Questions" (10-06) and "Careers/Education Questions" (10-01) threads.
- **r/Professors**: themed daily threads ("Oct 07: Wholesome Wednesday").
- **r/AskAcademia**: no tool-recommendation megathread seen. NOT FOUND otherwise.
- **r/indiehackers**: mods said they would likely introduce a "weekly self-promotion thread" (https://www.reddit.com/r/indiehackers/comments/1pj44es/ , about 2025-11). Whether it exists: UNVERIFIED. Two "Share what you're building" threads by one user (https://www.reddit.com/r/indiehackers/comments/1wzz31j/ and https://www.reddit.com/r/indiehackers/comments/1wuzn8z/) appear in the hot list. They are not a mod-run weekly thread.

---

## 9. Evergreen "which LaTeX editor for Mac" threads

**NOT FOUND.** I could not list or search old threads: Reddit search is blocked, WebSearch is exhausted and cannot reach reddit.com, and the MCP only lists "hot". I will not name threads I have not read.

What I can say:
- The 100-post r/LaTeX window shows the same question recurring about every 2 to 3 weeks in fresh form: 2026-09-17 (A1) and 2026-09-19 (A2) in the Mac-specific form. This suggests it is asked often, so a short, accurate Mac comparison on Ben's own site (a "TeXShop alternative for Mac" guide was committed 2026-10-07, commit 941e3ddf per `git log`) is probably higher value than replying in old threads.
- Replying to old threads is low value (my judgement): few readers, and some subs treat it as necro-promotion. The exception is a thread that still ranks on Google. I could not identify any.

---

## 10. Gaps and suggested next steps

1. **Gaps:** full r/LaTeX rules; anything before 2026-09-04 in r/LaTeX; the August 15 to September 3 window; current r/typst size; evergreen threads; Reddit's own policy pages.
2. **To close the gaps:** ask Ben to read the r/LaTeX sidebar and r/macapps rules page in his own browser and paste them, or raise `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`. I did not use Ben's logged-in Chrome session.
3. **Fix the stale facts:** Ben's 10-03 r/LaTeX post still says $10 and version 1.0.2 (VERIFIED). The site says $19.99. If the post can be edited, update it. Otherwise be ready to answer the price question in comments.
4. **Don't reply in r/PhD, r/labrats, r/postdoc, r/AcademicPhilosophy.** Rules exclude it.
5. **r/macapps:** wait out the 30-day window, then post in the main feed under Tier 2 (real identity, LinkedIn, privacy policy, terms). The App Pile is the fallback. Include a competitor comparison: TeXShop, TeXstudio, Texifier, Overleaf.
6. **Competitors seen in the window (names only, from comments and posts):** Texpile (u/PuzzleheadedShirt139), texlode (u/ClemensLode), LeftBlank (Typst, macOS), Eukolia, LeafOver, NextTex (u/humble_muse).
