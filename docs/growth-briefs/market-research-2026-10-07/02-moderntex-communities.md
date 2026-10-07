# ModernTex: where the audience gathers and how to reach it

Research date: 2026-10-07. Research only. Nothing was posted, emailed, submitted, or signed up for.

Scope: communities, listings, roundups and email targets for ModernTex ($19.99 once, 7-day free trial, native Mac LaTeX editor, macOS 14+, Apple silicon and Intel). Read first and not repeated: `PRODUCT.md`, `docs/reddit-notes-2026-09-29.md`, the scheduled-task prompts (`muscleonglp-reddit-outreach`, `purplelink-outreach-sunday-nudge`, `weekly-growth-scan`, `outbound-veil-org-outreach`), `Outreach/` (log, launch kit, libguide pack, newsletter pitches) and `docs/moderntex-launch-outreach.md`.

Evidence labels used throughout:
- VERIFIED: the page, API or post was read directly on 2026-10-07.
- SECONDARY: a search snippet, a third-party page about the thing, or arithmetic on verified data.
- UNVERIFIED / NOT FOUND: could not be confirmed. No member counts or rules are invented.

Method limits (read these before trusting a ranking):
- The WebSearch tool hit its session cap during the research. SERP checks were done on DuckDuckGo (Bing-backed) in the browser pane. Google rankings were not checked.
- Reddit blocks fetching of rules pages, `about.json` and Reddit's own help pages. Reddit text came from the Reddit MCP tools (hot listings of up to 100 posts, full posts and comments). Reddit gives no timestamps through that route, so thread dates are estimates from post IDs, good to about one day for recent posts.
- Cloudflare challenges blocked Softpedia, Slant, SourceForge, the MacRumors main forum, latex.org and AlternativeTo's add-app form. Those were not worked around.

---

## 0. Read this first: corrections, conflicts and risks in what already exists

1. **The awesome-LaTeX pull request is already open.** PR #128 "Add ModernTex to LaTeX-focused editors" on `egeerardyn/awesome-LaTeX`, opened 2026-10-03, state open, 0 comments, affiliation disclosed. VERIFIED, GitHub API 2026-10-07: https://github.com/egeerardyn/awesome-LaTeX/pull/128. It is not in the "already done" list.
2. **`docs/moderntex-launch-outreach.md` names the wrong repo.** It says `danphilps/awesome-LaTeX`. That repo has 0 stars and was last pushed 2020-08-22 (https://api.github.com/repos/danphilps/awesome-LaTeX). The live list (1,672 stars, pushed 2026-08-08) is `egeerardyn/awesome-LaTeX`. PR #128 went to the right one.
3. **The SaaSHub listing already exists** with your copy, 0 reviews: https://www.saashub.com/moderntex (VERIFIED). The outreach pack still lists it as a to-do.
4. **A public GitHub repo may be exposing internal planning.** https://github.com/purplelink-llc/purplelink is public (GitHub API, `private: false`, pushed 2026-10-07). https://github.com/purplelink-llc/purplelink/blob/main/docs/moderntex-launch-outreach.md returns HTTP 200 and appeared in DuckDuckGo results for "ModernTex". The `/docs` folder lists `paper-review-runbook.md`, `security-paper-review.md`, `growth-briefs` and other files (API listing 2026-10-07). I did not read the other files. Worth confirming this is intended. Competitors, mods and reporters can read your unsent drafts and sales counts.
5. **The 2026-10-03 r/LaTeX post has stale facts.** "I built a native Mac LaTeX editor for writing papers..." by u/PurplelinkPL (https://www.reddit.com/r/LaTeX/comments/1wwtdoy/, VERIFIED) says "$10 once" and "1.0.2". The site says $19.99 and 1.3.6. One commenter already asked about it. Score 0, 4 comments, not removed. Top reply (5 points): "Does not seem to do enough to warrant a switch away from things like Overleaf." Edit the post if possible.
6. **`Outreach/03-launches/moderntex-launch-kit.md` is stale.** It says $29, Mac App Store, "Octree/Texifier" positioning, and a title framed as "After 2 years...". Do not reuse its Show HN and r/LaTeX drafts as written. The drafts in section 7 replace them.
7. **r/PhD bans tools with a free trial.** See 1.3. Do not mention ModernTex there.
8. **The Wikipedia comparison page reverts self-added editors within hours.** See 2.9. Do not touch it.
9. **MacOSX-TeX is almost silent now.** The archive index shows only 6 months with files in the last 10 (Jan, Feb, Mar, Jun, Jul, Sep 2026), each 1 to 6 KB (https://email.esm.psu.edu/pipermail/macosx-tex/, 2026-10-07, SECONDARY reading of file sizes). The audience is right, the volume is tiny. The list's info page states no posting or promotion policy and says new members need email confirmation and moderator approval (https://email.esm.psu.edu/mailman/listinfo/macosx-tex, VERIFIED).

---

## 1. Reddit

Source for everything in this section: `scratchpad` findings built from the Reddit MCP tools on 2026-10-07 unless a URL says otherwise. Subscriber counts are SECONDARY (gummysearch.com, each page shows its own update date), because Reddit's `about.json` is blocked.

### 1.1 Subreddit table

| Subreddit | Size (source date) | Self-promotion rule status | Conventions and what happens to developer posts |
|---|---|---|---|
| r/LaTeX | 89k (2026-10-02) | Full sidebar rules NOT FOUND. Verified: AI-content rule (below). | No weekly or monthly thread in the last 100 posts. Many developer posts survive; one was removed (LeafOver). Posts that score are technical or solve a named workflow. "I built an editor" posts score 0 and draw "why use this over VS Code or Overleaf". |
| r/macapps | 255k (2026-10-05) | VERIFIED (mod post, about 2026-03-08): post format Problem / Comparison / Pricing; three tiers; Rule 3: once per developer per 30 days, counted from the last app post even if removed; comments promoting your own app need 10 karma in the sub and must disclose. | Monthly "App Pile" megathread; direct-download apps without an established-developer flair go there or meet Tier 2 requirements for the main feed. |
| r/MacOS | 646k (2026-10-05) | NOT FOUND | Support-heavy. Not a venue. |
| r/mac | 3.1M (2026-10-05) | NOT FOUND | Same. |
| r/MacOSApps | 27k (2026-10-05) | NOT FOUND | Open self-promotion in practice; posts sit at 0 to 63 points. |
| r/GradSchool | 946k (2026-10-02) | Rule text NOT FOUND. Mod megathreads say the "rule around spam" applies inside them. | Weekly AutoModerator megathreads (AI in Grad School, Time Management). Nothing tool-related. |
| r/AskAcademia | 2.1M (2026-10-01) | NOT FOUND | Career and publishing questions. No tool megathread seen. |
| r/PhD | 288k (2026-10-01) | VERIFIED (u/Eska2020, about 2026-01-28, https://www.reddit.com/r/PhD/comments/1r11qx4/): tools allowed only if open source, industry standard, or from small indie outfits with transparent pricing, and a personal project is welcome only "if it does not have a 'free trial' button or a 'free tier'". Threatens permabans. | ModernTex has a 7-day trial, so it fails as written. Do not post or reply with it. |
| r/academia | 110k (2026-10-02) | NOT FOUND | No sticky seen. |
| r/Professors | 201k (2026-09-30) | NOT FOUND | Themed daily threads. Not a tool venue. |
| r/postdoc | 30k (2026-10-01) | VERIFIED but from a 2022 post: "No spam/scams/selling services/self-promotion." (https://www.reddit.com/r/postdoc/comments/ulmk8a/) | Skip. |
| r/labrats | 728k (2026-10-01) | VERIFIED (mod post about 2026-10-02, https://www.reddit.com/r/labrats/comments/1ww3asi/): tool posts removed; only the Monthly Bulletin Board, which still says direct product advertising is not allowed. | Skip. |
| r/math | 4.0M (2026-10-01) | NOT FOUND | Recurring "Quick Questions" and "What Are You Working On" threads. No tool thread. |
| r/AcademicPhilosophy | 63k (2026-09-30) | VERIFIED (about 2025-06): "Own work posts are now banned"; 30-day-old account plus comment history required. | Skip. |
| r/AskEconomics | 1.5M (2026-09-30) | NOT FOUND | Comments filtered. Not a venue. |
| r/compsci, r/Physics | 4.0M, 3.3M | NOT FOUND | Weekly question threads. Not tool venues. |
| r/typst | about 5k (stale figure from 2025-01-17) | NOT FOUND | A competitor community. A native Mac Typst editor (LeftBlank) was met with "contribute to an existing project instead" on 2026-10-02. |
| r/Overleaf | about 1k | NOT FOUND | Effectively dormant since late 2025. Not a venue. |
| r/OverleafGuide, r/AcademicMac, r/thesiswriting | NOT FOUND, NOT FOUND, banned | | Do not exist or are not reachable. |
| r/indiehackers | 196k (2026-10-05) | VERIFIED (mod posts about 2025-11 and 2026-07): Self Promotion flair, proof for revenue claims, new accounts must use modmail. | Only useful for a "what I learned" post, not for reaching LaTeX users. |
| r/SideProject | 863k (2026-10-06) | NOT FOUND (a directory lists it as promotion-friendly, no rule text). | Ben posted Budgetcast there 2026-09-30. Wrong audience for ModernTex. |

r/LaTeX's one verified rule: the stickied "[MEGATHREAD] AI Generated Content" (u/SonusDrums, 2026-09-10, https://www.reddit.com/r/LaTeX/comments/1wd1w1q/) says AI-generated content outside the megathread "will be removed" and minor AI assistance "should be disclosed in posts outside of this mega thread". It followed a 189-point thread, "Mods: can we get a way to report AI slop?" (https://www.reddit.com/r/LaTeX/comments/1wccvnf/, 2026-09-09). Decide how you will answer if asked whether ModernTex or a post was AI-assisted.

### 1.2 Site-wide Reddit rules

- Reddit's own help and policy pages could not be read (blocked). NOT FOUND from the primary source.
- SECONDARY (https://redship.io/blog/reddit-self-promotion-rules-2026, dated 2026-07-02): the 9:1 ratio is "widely cited guidance rather than official policy" and comes from Reddiquette, which says it is fine to be a redditor with a website but not a website with a Reddit account. There is no site-wide karma minimum. Mods set their own rules.
- VERIFIED (r/macapps FAQ in the mod post): repeated identical comments or links, unverified profile email, multiple accounts, and AI-style text with em dashes get auto-removed. This is a mod's description of filters, not Reddit's text.

### 1.3 What has worked and what has been removed (VERIFIED, 2026-10-07)

| Post | Date (est.) | Score / comments | Outcome |
|---|---|---|---|
| VS Code extension for Git + LaTeX + git-latexdiff, https://www.reddit.com/r/LaTeX/comments/1waffg6/ | 09-07 | 163 / 12 | Did well. Public README and a concrete revision-diff workflow. |
| Real-time LaTeX preview in WASM, https://www.reddit.com/r/LaTeX/comments/1wrvhig/ | 09-27 | about 33 / 27 | Did well. Technical write-up, not a pitch. |
| texlode update (real-time editor), https://www.reddit.com/r/LaTeX/comments/1wxbk8m/ | 10-04 | 14 / 34 | Kept. Top reply: "Another online service, I will pass. Why nobody offer local stuff anymore". Another (9 points): prefers local and "willing to pay". |
| LeafOver, https://www.reddit.com/r/LaTeX/comments/1ws9ou9/ | 09-28 | 0 / 17 | Body removed (cause not stated). Top reply: "...different than the thousand other options for a local setup because?" |
| Eukolia, https://www.reddit.com/r/LaTeX/comments/1wn1z9g/ | 09-22 | 0 / 16 | Author deleted. Top reply asks why use it over VS Code or Overleaf. |
| Ben's ModernTex post, https://www.reddit.com/r/LaTeX/comments/1wwtdoy/ | 10-03 | 0 / 4 | Kept. Skeptical replies. |
| LeftBlank, native Mac Typst editor (r/typst), https://www.reddit.com/r/typst/comments/1wvvb9k/ | 10-02 | 0 / 6 | Hostile. |

Pattern: technical depth or a free tool solving a named workflow scores. A generic "I built an editor" scores 0. For ModernTex the useful signals are "local, and I would pay for it" (texlode thread) and the top comment "My data is mine." (62 points) on the 46-point "How do you prefer to write LaTeX: locally vs online?" thread (https://www.reddit.com/r/LaTeX/comments/1wxhiv9/).

r/macapps September roundup (https://www.reddit.com/r/macapps/comments/1wzts9p/): no LaTeX app appears. Paid lifetime apps do appear (Nodes 2.0, a native Markdown editor, 231 votes; Caxton, 128). Paid trial apps in the App Pile score about 0 to 3 points individually.

### 1.4 Where a disclosed ModernTex reply would be legitimate

Honest summary: only 3 threads are strong fits, and the strong ones are 18 to 20 days old. Replying to them now is low value. Use them as the pattern for what to watch for (Mac user asks for an editor, or hits the Overleaf compile limit and wants local). All VERIFIED, 2026-10-07.

Fits:
1. "Need help setting up a LaTeX + LilyPond workflow for music theory exams (Mac M1)". https://www.reddit.com/r/LaTeX/comments/1wis640/, about 2026-09-17, 6 points, 6 comments. OP asks "What editor should I use? ... I'm on an M1 Pro Mac." Angle: answer the lyluatex question first. Mention ModernTex only if you confirm it compiles with shell-escape (UNVERIFIED, you must check). 20 days old.
2. "Learning Texify". https://www.reddit.com/r/LaTeX/comments/1wkc7wb/, about 2026-09-19, about 8 points, 13 comments. TeXstudio cask disabled on Homebrew (2026-09-01 per a commenter), user overwhelmed by PyCharm plus TeXiFy. Exactly the ModernTex user. Angle: confirm the website download works after approving in Privacy and Security, name TeXShop as the free option, then one disclosed sentence. 18 days old.
3. "Compiling and Collaborating with Dropbox". https://www.reddit.com/r/LaTeX/comments/1wohvqy/, about 2026-09-23, about 6 points, 14 comments. Math grad student hit the Overleaf free-plan timeout, advisor stays on Overleaf. ModernTex does not solve the shared-editing part, so say so. OP's platform not stated.

Optional, thin:
4. "How do you prefer to write LaTeX: locally vs online?" https://www.reddit.com/r/LaTeX/comments/1wxhiv9/, about 10-04, 46 points, 53 comments. High traffic but no ask, and you posted in the sub a day earlier. A drive-by pitch would look like a pattern. Reply only with a real point.
5. "Preparing a latex+git workshop. Ideas?" https://www.reddit.com/r/LaTeX/comments/1wnawgx/, about 09-22, 13 points, 2 comments. OP's colleagues "are complaining a lot about Overleaf". Give Mac install facts (MacTeX vs TinyTeX, Gatekeeper prompts), one line on ModernTex.
6. r/macapps, "What's a small Mac app you use all the time but rarely see mentioned?" https://www.reddit.com/r/macapps/comments/1wxkwu8/, about 10-04, 250 points, 507 comments. Needs 10 sub karma before promoting your own app in comments, and Rule 3's 30-day clock.

Weak (only if nothing better):
7. "LaTeX offline reference manual?" https://www.reddit.com/r/LaTeX/comments/1wxfbf7/ (about 10-04, 4 / 10). Fits only if ModernTex has a command reference (UNVERIFIED).
8. "Sorting out references in PhD before submission" (r/AskAcademia) https://www.reddit.com/r/AskAcademia/comments/1wzwngq/ (10-07). EndNote user, not an editor ask.
9. "LyX as a tool for LaTeX" https://www.reddit.com/r/LaTeX/comments/1wi6yrn/ (about 09-16, 47 / 9). Advocacy post, off topic for a reply.
10. "BEng Thesis in LaTeX" https://www.reddit.com/r/LaTeX/comments/1wgpe52/ (about 09-14, 23 / 54). LaTeX to Word question.
11. "Install size" https://www.reddit.com/r/LaTeX/comments/1w8pywr/ (about 09-05). Chromebook, over a month old.
12. "AEU (Elsevier) Guide for Authors..." (r/AskAcademia) https://www.reddit.com/r/AskAcademia/comments/1wy66fy/ (about 10-05). Submission-requirements question, no comments yet.

I could not list threads from 2026-08-15 to 2026-09-03 (only "hot" listings are reachable) or find evergreen "which Mac LaTeX editor" threads that still rank. NOT FOUND. Ask Ben to run these searches in his own browser: `https://www.reddit.com/r/LaTeX/search/?q=mac+editor&restrict_sr=on&t=year` and the same for `overleaf+offline`, `texshop+alternative`, `compile+timeout`.

### 1.5 Where mentioning ModernTex would NOT be appropriate

| Thread or venue | Why |
|---|---|
| texlode update, https://www.reddit.com/r/LaTeX/comments/1wxbk8m/ | Competitor's own launch thread. Hijacking. |
| "My Fully Local LaTeX IDE", https://www.reddit.com/r/LaTeX/comments/1x00lob/ (10-07) | Competitor launch, Android/Termux. |
| LeftBlank, https://www.reddit.com/r/typst/comments/1wvvb9k/ | Competitor launch, Typst, hostile. |
| LeafOver, https://www.reddit.com/r/LaTeX/comments/1ws9ou9/ | Competitor launch, removed body. |
| Eukolia, https://www.reddit.com/r/LaTeX/comments/1wn1z9g/ | Competitor launch, OP deleted. |
| Click-in-the-preview editor, https://www.reddit.com/r/LaTeX/comments/1wsvyvm/ | Competitor launch. |
| "I built a clone of Apple Notes, but with LaTeX and Markdown files (need beta testers)", https://www.reddit.com/r/LaTeX/comments/1wc3tch/ | Mac developer asking for testers, a month old. |
| r/macapps PDF viewer feature thread, https://www.reddit.com/r/macapps/comments/1wrsd0f/ | A developer collecting feature ideas. Pitching there hijacks it. Its replies (live reload that keeps scroll position, per-file remembered position) are useful input for ModernTex's PDF pane. |
| r/macapps, "Share some free and open source apps you use", https://www.reddit.com/r/macapps/comments/1wzw4t3/ | OP asks for free and open source only. |
| Neovim + Zathura thread, https://www.reddit.com/r/LaTeX/comments/1wu306x/ | Wrong tool, a config fix. |
| "Please help, my boss just shared an Overleaf project", https://www.reddit.com/r/LaTeX/comments/1wel1y6/ | One-off fix, already answered, OP stays on Overleaf. |
| Anything in r/PhD, r/labrats, r/postdoc, r/AcademicPhilosophy | Rules exclude it (1.1). |
| r/GradSchool weekly megathreads | Spam rule applies, nothing asks for LaTeX. |
| Any thread over about 30 days old and already answered | Few readers, reads as necro-promotion. |

### 1.6 Recurring threads and exact conventions

- r/macapps App Pile: one monthly megathread, "[Megathread] The App Pile - <Month>, 2026" by u/Mstormer. October's is https://www.reddit.com/r/macapps/comments/1wuoav5/ (about 2026-10-01, 37 points, 130 comments). Top-level developer comments start "I'm the developer" and use Problem / Comparison / Pricing headings. Next one expected about 2026-11-01 (day UNVERIFIED).
- r/macapps monthly roundup by u/NeonSerpent, early each month (September: https://www.reddit.com/r/macapps/comments/1wzts9p/). Lists main-feed posts only.
- r/GradSchool weekly megathreads, r/labrats Monthly Bulletin Board, r/math and r/Physics weekly threads: none of these accept product promotion.
- r/LaTeX: no recurring thread besides the AI megathread.

### 1.7 Your own status in r/macapps

You commented in the September App Pile on 2026-09-29 (Outreach log line 36, exact comment URL TBD). Rule 3 counts "once per developer in 30 days" from the last app post. Whether a megathread comment counts is UNVERIFIED. 30 days from 2026-09-29 is 2026-10-29, so the November App Pile (about 2026-11-01) is clear either way. If you want the main feed, you need Tier 2: a developer portfolio with real identity, LinkedIn and contact details, plus a website with a Privacy Policy and Terms of Service (mod post). Check that purplelink.llc has both Terms and Privacy pages before attempting it. I did not check.

---

## 2. Other communities, listings and roundups

### 2.1 TeX StackExchange and Software Recommendations

- VERIFIED policy, https://tex.stackexchange.com/help/promotion: self-promotion is tolerated when answers are good and relevant; you must disclose affiliation in the post; behaviours that nearly always get flagged are mentioning your product too much, answering only questions where your product is the answer, and links that substitute for content.
- VERIFIED, https://tex.stackexchange.com/help/product-support: product teams may take part but should build reputation and engage with the site generally.
- VERIFIED precedent, https://tex.meta.stackexchange.com/questions/10072/ (2023-05-10, score 12): a vendor answering with a one-line affiliation statement is accepted, and edits that remove the disclosure get reverted.
- New "which Mac editor" questions are closed as duplicates (examples: https://tex.stackexchange.com/questions/257282/, closed 2015-07-27; https://tex.stackexchange.com/questions/634128/, closed 2022-02-16). The canonical home is the community-wiki "LaTeX Editors/IDEs" big list, https://tex.stackexchange.com/questions/339/latex-editors-ides: score 951, 754,552 views, 59 answers, last activity 2026-06-09, protected (needs 10 rep earned on the site). Texifier and TeXShop have answers, ModernTex does not. Governing template: https://tex.meta.stackexchange.com/questions/3253/.
- Also ranking and open: "Alternatives to Overleaf (i.e. instant TeX compiling without sign in)", https://tex.stackexchange.com/questions/488049/ (score 31, 75,878 views, last activity 2026-04-14).
- Your account shows a "past answers not well-received / danger of answer ban" warning (Outreach log row 2026-09-20). Rating: low priority, high downside. If ever used, post the template answer on question 339 with the first line "I develop ModernTex", no marketing language, and only after earning rep on unrelated answers.
- Software Recommendations (https://softwarerecs.stackexchange.com, 23,372 questions): alive, but the newest 8 `latex`-tagged questions span 2021-06 to 2026-03, none about a Mac editor (SE API). Not worth effort. Its rule for own software (https://softwarerecs.meta.stackexchange.com/questions/2741/, 2018): disclose, stay neutral, mention limits and alternatives.

### 2.2 Hacker News

- Rules (VERIFIED, https://news.ycombinator.com/showhn.html): Show HN is for something you made that people can try, "ideally without barriers such as signups". Do not ask friends to upvote or comment. A moderator wrote on 2025-08-24 that paid features are fine if clearly marked and that the only unacceptable case is "no way to try the product out" (https://news.ycombinator.com/item?id=45006257). A downloadable full-featured trial with no account qualifies. A page whose only action is "buy" does not.
- Moderator tips (dang, edited 2026-03-28, https://news.ycombinator.com/item?id=22336638): write the text by hand, do not use an LLM even to edit it; do not use a company or project name as your username; put an email in your profile; no booster comments; new releases only if significantly different, once or twice a year.
- Second-chance pool exists (https://news.ycombinator.com/item?id=26998308); moderators no longer answer Show HN advice emails (2026-03-28 note). Do not count on it.
- What actually happens (SECONDARY arithmetic on HN Algolia data, 40,757 Show HN posts from 2025-12-09 to 2026-10-05): titles with Mac/macOS/SwiftUI have a median of 2 points; 3.4% reach 50 or more. LaTeX or Typst titles: 54 posts. The winners were free and open source ("TikZ Editor" 451 points, 2026-06-23; "TeXbrain" 118 points, 2026-08-25). Other LaTeX editor Shows scored 1 to 5 points ("Texpile" 3 and 1, "GlyphX, a local-first LaTeX editor that compiles offline" 4, "Octree" 1). The notable paid Mac exception is NetViews (243 points, 2026-02-10, https://news.ycombinator.com/item?id=46955712), where top comments objected to closed source and no Homebrew cask.
- Nothing named ModernTex or Purplelink has been posted to HN.
- Timing: no official guidance. In the same data, weekday matters little; 12:00 to 13:59 US Eastern had the highest 50-point rate (4.3% and 3.8% against a 2.9% base). Small differences, do not over-read.
- Verdict: a paid closed Mac LaTeX editor lands near the median. Expect a few useful comments, not a spike. If used, pick a technical angle and expect "why not Mac App Store, why not open source, is there a Homebrew cask".

### 2.3 Mac sites and forums

- MacRumors: written developer lane. "Guidelines for Software Developers" (https://macrumors.zendesk.com/hc/en-us/articles/201294426, page shows "Updated 14 days ago" on 2026-10-07): developers may promote their own software in their own thread in the Mac Apps forum. Required: one account, "About you" says you are a developer, website filled in, thread title is the app name, one thread per app or major release, identify yourself and your company in the first post, no consumer-style promotion, no promo codes outside the Code Sharing forum. The forum URL could not be loaded (Cloudflare). Fit moderate (Mac users, not academics). Cost: free.
- Apple Support Communities: forbids ads and product links not directly answering a support question (https://discussions.apple.com/terms, VERIFIED). Not a venue.
- Product Hunt: guidelines dated 2026-03-10 (https://help.producthunt.com/en/articles/9883485). Nothing excludes a paid app with a trial. The launch guide says you cannot ask people directly to upvote, only to visit and comment, and company accounts are prohibited (https://www.producthunt.com/launch). The earlier plan to "rally the six buyers" must be worded as "come and comment", not "upvote".
- MacUpdate: free developer submission at https://www.macupdate.com/help/submit-app (account needed). Guidelines ask for descriptions without promotional text or pricing. Your reusable copy includes "$19.99 once", so edit it. Not confirmed whether a ModernTex listing exists (UNVERIFIED).
- AlternativeTo: no ModernTex page (VERIFIED 404). Terms (updated 2026-10-06): community-submitted, backlog "usually months long", paid priority exists. Contact hello@alternativeto.net (https://alternativeto.net/about/). The add-app flow needs a login and was not opened. The Overleaf-alternatives Mac page is https://alternativeto.net/software/writelatex/?platform=mac.
- SaaSHub: listed, 0 reviews (above).
- Directories with free or cheap forms (all VERIFIED 2026-10-07):

| Directory | Free route | Notes |
|---|---|---|
| Mac Apps Library, https://www.macappslibrary.com/submit | Free with human review; $29 priority | Accepts direct-download apps. Needs 1 to 4 screenshots. |
| Bundl.run, https://bundl.run/submit | Free, email verification then review | Says direct downloads are fine; 5,057 apps listed. |
| TryMacApps, https://www.trymacapps.com/submit | Free only if you place their badge on your site | A badge on purplelink.llc is a link out. Your decision. |
| Mac Apps Daily, https://macappsdaily.com/submit | Free waitlist, "6+ months" | $39 for 48 hours. Low value. |
| AppMus, https://appmus.com/submit | Free form | It publishes comparison pages that rank. |
| Sugggest, https://sugggest.com/contact | "Software Suggestion" topic | Ranks for "texshop alternatives". |
| Indie App Catalog | Non-store submission form, needs login | Per the email-target research. |
| Indie Apps | App Store only | Not applicable. |

- Not available or not worth it: Softpedia and Slant (Cloudflare blocked, UNVERIFIED), LibHunt (open source only), Lobsters (invite-only, new users cannot use the `show` tag, https://lobste.rs/about), CTAN (free-software archive, requires a license statement; SECONDARY inference that a paid binary would be rejected).
- Setapp: application submitted 2026-10-07, reply promised within 10 business days (Outreach log line 142). Nothing else checked.

### 2.4 Mastodon, Bluesky, Facebook, Discord

- Mastodon instances (API read 2026-10-07): scholar.social 1,227 users, 282 active, sign-ups closed, "No spam", individual accounts only (post as yourself, not as Purplelink); mathstodon.xyz 27,055 users, 5,379 active, approval required, advertising of goods "inappropriate, irrelevant, or too frequent", "If in doubt, ask us"; fediscience.org 6,070 users, 905 active, approval required with proof of publications, no explicit promotion rule listed. Hashtag volume as seen from mastodon.social over 7 days to 2026-10-06: #latex 155 posts by 74 accounts, #overleaf 1, #texshop 0, #typst 6 (SECONDARY, one server's view). Reach is tens of people. One disclosed personal post is within the written rules of all three.
- Bluesky: no LaTeX or academic-Mac starter pack found (public search, 2026-10-07). Existing adjacent packs: "Typst people" and "Mac and iOS indie devs and companies". Join mechanics are the curator's choice. Per your standing note, do not chase Bluesky outreach credentials.
- Facebook groups that exist (names only, sizes NOT FOUND because Facebook requires login): "(La)TeX user group" https://www.facebook.com/groups/170883319628439/ ; "TeX Users Group" https://www.facebook.com/groups/TeXUsersGroup/ ; "LaTeX/TikZ Users' Support Group" https://www.facebook.com/groups/1053392884708403/ ; "LaTeX For Users Facebook" https://www.facebook.com/groups/LATEXFORUSERSFACE/ ; "LATEX" https://www.facebook.com/groups/1032297055642397/. Read each group's rules tab before anything. Rules NOT FOUND.
- Discord and Slack: the Typst Discord (about 13,219 members per Discord's invite API, 2026-10-07) is a competitor community, listed only for completeness. No LaTeX Discord, Slack or PhD Discord could be verified with a URL. NOT FOUND.

### 2.5 University and library guides, and how to get listed

Where TeXShop or Texmaker is listed and a Mac editor section could sit (VERIFIED 2026-10-07, "last updated" is the page's own date):

| Guide | Editors it names | Updated | Published route |
|---|---|---|---|
| UT Knoxville, https://libguides.utk.edu/latex | TeXShop, TeXstudio, Texmaker, Overleaf | 2026-05-05 | dataservices@utk.edu (page text) |
| NYU, https://guides.nyu.edu/LaTeX/installation | TeXShop, TeXstudio, Texmaker, Overleaf | 2026-05-04 | No email on page; Libraries "Ask" (not verified) |
| St. Mary's College of Maryland, https://libguides.smcm.edu/latex/SetUp | TeXShop, Texmaker, TeXworks, Overleaf | 2026-08-31 | ask@smcm.libanswers.com |
| UC Berkeley EPS libraries, https://guides.lib.berkeley.edu/latex | TeXstudio, Texmaker, TeXworks, Overleaf | 2026-08-27 | epslibs@berkeley.edu (on page) |
| UW-Madison, https://researchguides.library.wisc.edu/latex/guides | Overleaf, LyX, TeXworks, TeXstudio, Kile | 2026-10-02 | libraries@wisc.edu |
| Florida Tech, https://libguides.lib.fit.edu/c.php?g=427921&p=5199720 | TeXstudio, Texmaker, Papeeria, Overleaf | 2025-06-29 | library-reference@fit.edu (in page markup) |

Overleaf-only (low fit): CMU, Caltech, Princeton, Harvard Library (updated 2026-10-06), Penn, Cornell, MIT thesis page, UMass Amherst, Texas State. Math department pages (Harvard Math, UCSD Math) list TeXShop only, are old, and rarely have a maintainer address. None of the pages names Texifier, TeXpad or any other commercial Mac editor, so ModernTex would be a new category for them.

TUG is the cleanest route in the report: https://tug.org/interest.html says "Additions and corrections are always welcome, please email webmaster@tug.org." It has a separate section "Commercial and shareware TeX vendors and projects" (lists Scientific Word, WinEdt, Overleaf and others) and a free front-ends section with no Texifier. The University of Akron guide defers to this page. CTAN, the LaTeX Project "Get LaTeX" page and the AMS vendors page (https://www.ams.org/arc/resources/tex-vendors.html, Mac section lists only BaKoMa TeX and Scientific Word) are weak fits.

### 2.6 Wikipedia (do not touch)

"Comparison of TeX editors" lists only editors with their own Wikipedia article. Revision history (API, 2026-10-07): 2026-07-31 entries without articles removed; 2026-10-02 and 2026-10-06 two self-added editors reverted. Wikipedia's conflict-of-interest policy discourages direct edits and allows proposals on talk pages with disclosure (https://en.wikipedia.org/wiki/Wikipedia:Conflict_of_interest). ModernTex has no independent coverage, so there is nothing to propose yet. Revisit only after real third-party reviews exist.

### 2.7 GitHub awesome lists

| List | Rules that matter | ModernTex status |
|---|---|---|
| `egeerardyn/awesome-LaTeX` (1,672 stars) | One item per commit; format `[Name](link) - description.`; self-promotion fine if involvement is stated. | PR #128 open since 2026-10-03. Merges are occasional (2026-08-04 and 08-08, 2026-03); many PRs unmerged since 2026-08-14. Do not chase. |
| `jaywcjlove/awesome-mac` (115,602 stars) | One PR per suggestion, title-case AP style, alphabetical, annotate the PR. Closed-source and paid apps are listed (Texifier is). | Not submitted. Recent PRs merged in 0 to 1 days (10 merges checked, 2026-10-03 to 10-07). Best return in this report. |
| `open-saas-directory/awesome-native-macosx-apps` (1,623) | Native only, under about 200 MB, excludes "self-promoted apps (unless truly exceptional)". | Lower odds. |
| `writing-resources/awesome-scientific-writing` | Software must be open source. | Not eligible. |
| `xiaohanyu/awesome-tikz` | Generally used, maintained, documented. | Poor fit. |

### 2.8 Roundups that rank for "Overleaf alternative" and "best LaTeX editor Mac"

Where you rank today (DuckDuckGo, 2026-10-07, Google not checked): #1 for "best latex editor for mac 2026", "best latex editor mac", "best free latex editor for mac" (your guide https://purplelink.llc/guides/best-mac-latex-editors/); #3 for "latex editor mac native" (product page, behind TexSpark and Texifier); #1 and #2 for "ModernTex Mac LaTeX editor". Not in the top 10 for "overleaf alternative", "overleaf alternatives offline", "offline latex editor mac", "texshop alternative" and "overleaf free tier limits alternative". Those gap queries are the ones the pages below hold. ModernTex is mentioned on none of them (each page was fetched and searched for "moderntex" and "purplelink").

Independent, human-run pages with a published route (best targets):

| Page | Run by | Date | Route | Money signals |
|---|---|---|---|---|
| https://danmackinlay.name/notebook/latex_editors.html | Dan MacKinlay, personal notebook | none shown | https://danmackinlay.name/contact.html says he welcomes "cold contacts from strangers" | none seen |
| https://crypticinsight.com/posts/best-offline-latex-alternatives-to-overleaf | Jonathan Cook, personal blog | published 2026-05-28, modified 2026-09-26 | contact form https://crypticinsight.com/posts/contact-us | none stated |
| https://gauravtiwari.org/latex-editors/ | Gaurav Tiwari, blogger | modified 2026-10-03 | contact form https://gauravtiwari.org/contact/ and an address on the page | affiliate: "reader-supported... may earn a small commission"; expect a sponsorship or affiliate ask |
| https://techdator.com/best-latex-editors/ | TechDator | 2026-03-26 | https://techdator.com/contact/ | none stated |
| https://nav-ai.net/tutorials/how-to-build-and-insert-a-tikz-diagram-with-moderntex | Nav - AI directory | 2026-09-16 | Route not verified | Unsolicited third-party mention of ModernTex (with a ModernTex review entry). Not recorded in your outreach files. If you did not submit it, a thank-you note to its owner is the easiest contact on this list. |

Pay-to-play or vendor-run (skip or expect a request for money): Guru99 (no suggestion form, sells ads), FixThePhoto (affiliate), Worldmetrics ("includes paid placements"), SoftwareSuggest (lead-partner program), iTechGuides (sells listings; use corrections only), and vendor pages by latex.to, TypeTeX, Octree, inscrive.io, LetX, PapersFlow, Bibby, Murfy, TeX64. Stale: TechCult (2023), Beebom (2022), Medevel (open source only).

Competitors owning "native Mac LaTeX": TexSpark (https://texspark.io/), Texifier, TeX64 (https://tex64.com/latex-editor, updated 2026-09-16), Folio, Typetex, Compositor.

Third-party mentions of ModernTex found: SaaSHub (your copy), Nav - AI (above), your own YouTube videos, LinkedIn post and the open PR. No independent review, article or Reddit thread names ModernTex. Getting the first independent review is itself a goal (SaaSHub shows 0 reviews).

---

## 3. Email and form targets (36 verified routes, ranked)

Verified by fetching each target's own page on 2026-10-07 (HTML via curl; browser pane for ams.org and alternativeto.net). Addresses behind Cloudflare protection were decoded from the page. No address was guessed. Excluded as already contacted or queued: UVA, RMIT, Montclair State, Tennessee State, Fresno State, Toronto, UC Irvine, MIT, Yale, UMass Amherst, UNLV, Setapp. Note UT Knoxville is a different school from Tennessee State.

How to read priority: 1 = best fit and a role address; 2 = usable; 3 = weak fit, personal address published for the topic, or policy-limited. "Form" and "GitHub" rows are for Ben to submit himself.

| # | Target | Page | Published route | Why it fits | Pri | Policy notes |
|---|---|---|---|---|---|---|
| 1 | Georgia Tech Office of Graduate Education | https://grad.gatech.edu/theses-dissertations/templates | thesis@grad.gatech.edu | Lists Texmaker with setup steps and free Overleaf Pro accounts; no Mac-native editor. Atlanta. | 1 | Page says it "does not offer direct technical support" for LaTeX. Frame as a resource-list suggestion. |
| 2 | UT Knoxville Libraries LaTeX guide | https://libguides.utk.edu/LaTeX | dataservices@utk.edu | Lists TeXShop, TeXstudio, Texmaker, Overleaf. | 1 | Send one message for this and row 10. |
| 3 | UW-Madison Libraries LaTeX guide | https://researchguides.library.wisc.edu/latex/guides | libraries@wisc.edu | Lists Overleaf, LyX, TeXworks, TeXstudio, Kile; no Mac-native editor. Updated 2026-10-02. | 1 | Role address. |
| 4 | St. Mary's College of Maryland Library | https://libguides.smcm.edu/c.php?g=617273&p=4354716 | ask@smcm.libanswers.com | Editor table has a Cost column and lists WinEdt at $40 (student), so paid editors are not excluded. | 1 | Small college. |
| 5 | TeX Users Group (TUG) | https://tug.org/interest.html | webmaster@tug.org ("Additions and corrections are always welcome") | Separate commercial-vendors section; no paid Mac editor listed. Akron's guide defers to it. | 1 | Contact page also lists support@tug.org and office@tug.org; use the webmaster address. |
| 6 | UC Berkeley EPS libraries | https://guides.lib.berkeley.edu/latex | epslibs@berkeley.edu (on page, per the communities research) | Lists TeXstudio, Texmaker, TeXworks, Overleaf; updated 2026-08-27. | 1 | Not in the email-target agent's own table; verified by the communities pass. Overleaf-heavy. |
| 7 | Purdue Graduate School, Thesis & Dissertation | https://www.purdue.edu/academics/ogsps/thesis/templates/ | thesishelp@purdue.edu | LaTeX offered only as an Overleaf template; offline is a gap. | 2 | Address is for format questions. Page warns against the Overleaf template for export-controlled material. Keep it short. |
| 8 | Texas State Graduate College | https://www.gradcollege.txst.edu/students/research-thesis-dissertation/thesis-dissertation/latex-template-guide.html | gradcollege@txstate.edu | Says "your LaTeX editor of choice", names Overleaf only. | 2 | Requires LuaLaTeX with TeX Live 2025. Confirm ModernTex handles LuaLaTeX before mentioning it. |
| 9 | University of Akron Libraries | https://libguides.uakron.edu/latex | librarians@uakron2.libanswers.com | Names no editor, points to TUG's list. | 2 | Do after TUG. |
| 10 | UT Knoxville OIT LaTeX page | https://oit.utk.edu/research/research-software/latex/ | form http://help.utk.edu | Lists TeXstudio (Windows), TeXShop (Mac), Overleaf. | 2 | OIT supports only TeXstudio and TeXShop. Ask only about listing. |
| 11 | Reed College Computer User Services | https://www.reed.edu/it/help/LaTeX/install.html | cus@reed.edu | Names TeXShop, says "feel free to explore other options for editors". | 2 | Small college. |
| 12 | LSU Mathematics | https://www.math.lsu.edu/comp/resources/texinstall | webmaster@math.lsu.edu; dept@math.lsu.edu | macOS section covers only TeXShop. | 2 | One message for both LSU pages. |
| 13 | Claremont McKenna ITS | https://its.cmc.edu/services/academic-software.html | help@cmc.edu | Catalog lists MacTeX and TeXShop; has a software-request route. | 2 | Aimed at campus users. Ask a short question. |
| 14 | NC State University Libraries | https://www.lib.ncsu.edu/software/mactex | library_askus@ncsu.edu | MacTeX catalog entry names only TeXShop and BibDesk. | 2 | No add form; general Ask Us. |
| 15 | OnTheHub (Kivuto), Sell With Us | https://onthehub.com/sell-with-us | web form on the page | Academic-discount storefront for students and faculty. | 2 | Form, terms not published. You submit. |
| 16 | MacUpdate app submission | https://www.macupdate.com/help/submit-app | form (account needed); support@macupdate.com | Paid apps accepted (Price field). | 2 | No promo text, no price in description. |
| 17 | awesome-mac | https://github.com/jaywcjlove/awesome-mac | pull request per CONTRIBUTING.md | Lists Texifier; fast merges. | 2 | GitHub, you submit. |
| 18 | Indie App Catalog | https://indieappcatalog.com/app/submit | non-store form, needs login | "Non-store apps welcome too!" | 2 | Login is your call. |
| 19 | MacStories | https://www.macstories.net/about/ | viticci@macstories.net, voorhees@macstories.net (About page) | Covers indie Mac apps in depth. Already in your newsletter notes. | 2 | "never done and never will do paid reviews". Personal inboxes published for contact. Offer a free license, expect nothing. |
| 20 | East Texas A&M Graduate School | https://inside.tamuc.edu/academics/graduateschool/thesis%20and%20dissertation%20services/templates,-forms,--guidelines.aspx | TDS@tamuc.edu | LaTeX template, no editor named. | 3 | Format-question address. |
| 21 | Southern Illinois University ETD | https://siu.edu/admissions/graduate/academic-support/thesis-dissertation-research/etd/etd-templates.php | etdsupport@siu.edu | LaTeX template zip. | 3 | LaTeX treated as niche. |
| 22 | Texas A&M Graduate School | https://grad.tamu.edu/degree-completion/thesis-and-dissertation/writing-tools/index.html | grad@tamu.edu | LaTeX template link. | 3 | Do not use `ogaps-latex@tamu.edu`; it was not on the page. |
| 23 | University of Florida T&D Support | https://it.ufl.edu/helpdesk/graduate-resources/ | T&DSupport-hd@ufl.edu | Maintains LaTeX templates. | 3 | Templates require LuaLaTeX. Check first. |
| 24 | Rice Graduate and Postdoctoral Studies | https://graduate.rice.edu/academics/candidacy-defense-thesis-submission/thesisformat | graduate@rice.edu | Links a LaTeX template. | 3 | Off-purpose address. |
| 25 | UTSA Graduate School | https://graduateschool.utsa.edu/gps/formatting-requirements.html | gps@utsa.edu | Template "for LaTeX and LyX users". | 3 | Says "we do not offer technical support for LaTeX". Skip. |
| 26 | Texas Tech University Libraries | https://guides.library.ttu.edu/c.php?g=631905 | ian.barba@ttu.edu; shelley.barba@ttu.edu (guide owners, "Email Me" links) | Graduate LaTeX workshop built on Overleaf. | 3 | Personal addresses published on the guide. |
| 27 | University of Chicago Library | https://guides.lib.uchicago.edu/latex | hartj@uchicago.edu (guide owner) | Lists Texmaker, TeXstudio, TeXworks, MacTeX. Updated 2026-10-02. | 3 | Personal address; built around the campus Overleaf license. |
| 28 | Caltech Library | https://library.caltech.edu/latex/latex4thesis | library@caltech.edu | Overleaf-centred, template for local use. | 3 | Footer is a problem-report link. |
| 29 | University of Maine Graduate Student Government | https://umaine.edu/gsg/latex-file/ | gsg@maine.edu | Maintains the thesis class. | 3 | Student officers turn over yearly. |
| 30 | American Mathematical Society | https://www.ams.org/arc/resources/tex-vendors.html | tech-support@ams.org | Mac section lists only BaKoMa TeX and Scientific Word. | 3 | Support address; no "add your product" route stated. |
| 31 | The TeX FAQ | https://texfaq.org/FAQ-editors | GitHub issue https://github.com/texfaq/texfaq.github.io/issues | Mac section names TeXShop only. | 3 | "only a personal selection". GitHub, not email. |
| 32 | MacUpdate Content Team | https://www.macupdate.com/write-for-us | support@macupdate.com | Best Apps and Reviews sections. | 3 | Same address as row 16; free pitch only. |
| 33 | AlternativeTo | https://alternativeto.net/about/ | hello@alternativeto.net | ModernTex absent from TeXShop's alternatives. | 3 | Listings are user-driven. Use the add-app form instead. |
| 34 | iTechGuides roundup | https://www.itechguides.com/contact-us/ | hello@itechguides.com | Names TeXShop and Texifier for macOS. | 3 | Sells listings. Corrections route only; do not buy. |
| 35 | The Sweet Setup | https://thesweetsetup.com/contact/ | desk@blancmedia.org | Curated Mac app lists. | 3 | Latest post seen was May 2024. Check activity first. |
| 36 | TidBITS | https://tidbits.com/about/contact/ | ace@tidbits.com (page says all usernames are @tidbits.com) | Apple newsletter with Mac App Updates. | 3 | "We do not accept guest posts or sponsored posts", no press releases. A short personal note or skip. |
| 37 | Mac Power Users | https://relay.fm/mpu/feedback | feedback form | Weekly Apple workflow podcast. | 3 | Listener feedback form, not pitches. |

Dropped after checking: Cornell (no contact on page), Georgetown (phone only), Duke, Penn State library (no address), Berkeley Math computing, Princeton (Overleaf-only, 2024), Dickinson (2021), The Carpentries (no LaTeX content), Academic Superstore and JourneyEd (quote forms only), Student Beans and UNiDAYS (no business page found), Macworld, The Thesis Whisperer, Six Colors, 9to5Mac, Cult of Mac, MacRumors tips (not for pitches).

Roundup owners from 2.8 (Dan MacKinlay, Cryptic Insight, Gaurav Tiwari, TechDator) are additional targets with published contact routes; they are not in the table above.

Do not email non-US institutions from this list without reading 4.3. Every row above is US except Toronto and RMIT, which are already contacted.

---

## 4. Rules of the road

This is a summary of public sources, not legal advice. Penalties and rules can change; check the FTC page before a large send.

### 4.1 CAN-SPAM (US)

Source: FTC, "CAN-SPAM Act: A Compliance Guide for Business", https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business (fetched 2026-10-07).

- It applies to B2B email: "The law makes no exception for business-to-business email." It applies to every commercial message, one recipient or many.
- No prior consent is required. Cold first-contact email to US recipients is lawful if you meet the requirements below. CAN-SPAM is an opt-out regime.
- Requirements:
  1. No false or misleading header information (From, To, Reply-To, routing). Send from `ben@purplelink.llc` in your own name.
  2. No deceptive subject lines. The subject must reflect the content.
  3. Identify the message as an advertisement, clearly and conspicuously. The FTC does not prescribe wording. A plain sentence such as "This is a one-time note about a commercial product I sell." satisfies the intent.
  4. Include a valid physical postal address: a current street address, a registered USPS box, or a registered commercial mailbox. The address already in your signature is 8735 Dunwoody Place #12398, Atlanta, GA 30350. Whether it is a registered commercial mailbox is UNVERIFIED.
  5. Tell recipients how to opt out. A reply address works if it is monitored; the mechanism must work for at least 30 days after sending.
  6. Honor opt-outs within 10 business days. No fee, no extra information beyond an email address, and do not sell or transfer the address of someone who opted out (FTC guide; 16 CFR 316 text could not be fetched, so the last point rests on the guide).
  7. You are responsible for anyone sending on your behalf.
- Is "please consider adding ModernTex to your editor list" a commercial message? Its primary purpose is to promote a product, so treat it as commercial (FTC primary-purpose test, same guide). Do not rely on a "just a resource suggestion" argument.
- Penalty: up to $53,088 per email (same FTC page; the 2025 figure). SECONDARY (https://sanctionsnews.bakermckenzie.com/us-inflation-adjustment-for-federal-civil-monetary-penalties-nixed-for-2026/): no 2026 inflation adjustment was made, so the 2025 amount still applies. Enforcement is rare against one-person 1:1 notes, but the exposure is per message.
- Practical standard already used in your Outbound Veil task, and it fits here: one email per organization, role or published address only, signature with name, company and postal address, an opt-out line, a suppression list (the `do-not-contact` status in `Outreach/outbound-veil-orgs.csv`), no follow-ups. Reuse that list format for ModernTex and check it before every send.

### 4.2 Deliverability limits that matter for a small sender

Source: Google sender guidelines, https://support.google.com/a/answer/81126 (fetched 2026-10-07).
- All senders to Gmail need SPF or DKIM; bulk senders (5,000 or more messages a day) also need DMARC and one-click unsubscribe.
- Spam-complaint rate: keep under 0.10%; 0.30% is the hard line. With 10 to 30 emails a month, a single complaint is a large percentage, so one complaint matters. Check that `purplelink.llc` has SPF, DKIM and DMARC aligned for Mail (not checked here).
- Suggested frequency (my judgment, not a rule): at most 5 sends a day, spaced minutes apart, no repeat contact, and pause all sending for 3 days after any hostile reply or bounce pair, which matches your Outbound Veil rule.

### 4.3 Non-US recipients (read before emailing outside the US)

- Canada, CASL: conspicuously published business addresses may be used only for messages relevant to the person's business role, and a sender identity plus unsubscribe mechanism is required (CRTC guidance, https://crtc.gc.ca/eng/com500/guide.htm, via search summary, SECONDARY).
- Australia, Spam Act 2003: consent may be inferred from conspicuous publication only if the address is not accompanied by a "no commercial messages" statement and the message relates to the recipient's role (SECONDARY summaries; ACMA is the regulator).
- UK, PECR: corporate subscribers can be marketed without prior consent if you identify yourself and give an opt-out; sole traders and partnerships are treated as individuals and need consent. UK GDPR still needs a lawful basis for named individuals (SECONDARY summaries).
- Practical: a role address (library, thesis office) with a message relevant to that role is the safest case in all three. Do not email named individuals outside the US.

### 4.4 Disclosing as the developer on Reddit

- First sentence, plain: "Disclosure: I make ModernTex." Not in a footnote, not after the link.
- r/macapps requires it (and says promoting your app in comments is "in poor taste when hijacking another developer's promotion").
- Answer the question first. If the best answer is "use TeXShop, it is free", say so. Mention ModernTex only when it fits and say what it costs.
- State limits: needs a TeX distribution (MacTeX or TinyTeX), macOS 14 or later, paid after 7 days, does not do shared real-time editing with Overleaf users.
- Do not link-drop twice in one thread. No identical text in two places (Reddit filters repeated comments).
- Use the same account (u/PurplelinkPL). One account only.
- If asked whether AI was used in the app or the text, answer directly (r/LaTeX and r/macapps both care).
- Never ask anyone to upvote. Never have customers post on your behalf. Do not argue with criticism; reply with a fix or "you are right".

### 4.5 Frequency limits to avoid being flagged

Verified limits: r/macapps one app post per developer per 30 days (counting removed posts); r/macapps 10 sub karma before promoting your app in comments. Everything else below is my judgment and not a written rule:
- At most one ModernTex mention per subreddit per 30 days, across posts and comments.
- At most 2 ModernTex mentions on Reddit in any week, and at least 10 non-promotional helpful comments or posts for each ModernTex mention (the 9:1 idea, which is guidance and not policy).
- You posted in r/LaTeX on 2026-10-03. Make no promotional mention there until about 2026-11-15 unless someone directly asks for a Mac editor.
- Email: one message per organization, no follow-up, caps from 4.2.
- Directories: one submission per site, spaced across days.

---

## 5. Prioritised 30-day plan (2026-10-08 to 2026-11-06)

Baseline from your own data: search drives most traffic, 8 paying customers, trial to paid about 15% (given). Using that figure only as arithmetic: 20 trials from these channels would be about 3 sales (estimate, no evidence beyond the 15%). Under 5 conversions is WEAK-EVIDENCE under your weekly-growth-scan rules, so judge by link, referral and trial starts, not revenue, at day 30.

### 5.1 Tracking convention (first-party, already supported)

`site/analytics.js` records `utm_source` (60 chars), `utm_medium` (40), `utm_campaign` (80) and the referrer host only. It stores the first and the latest non-direct arrival for 90 days and attaches them to the Stripe order at checkout. Allowed characters: letters, digits, `.`, `-`, `:`, `/`, space.

Convention: `?utm_source=<site-or-list>&utm_medium=<email|listing|pr|comment|post>&utm_campaign=mt-oct26`

Examples: `https://purplelink.llc/guides/texshop-alternative-mac/?utm_source=gatech-grad&utm_medium=email&utm_campaign=mt-oct26`; `https://purplelink.llc/moderntex/?utm_source=tug&utm_medium=email&utm_campaign=mt-oct26`.

Notes:
- For email, link to a guide (the TeXShop or Overleaf alternative guide) rather than the product page. It is more useful and less salesy, and the Buy and trial buttons are one click away.
- Reddit shows only the host (`www.reddit.com`) as referrer, so you cannot split subreddits by referrer. Put the sub in `utm_source` (for example `reddit-macapps`). A plain tagged link is allowed; r/macapps removes repeated identical links, so tag each differently.
- Directories and PRs that strip query strings: rely on referrer host.
- Weekly check: `/stats/` referrers, the `analytics` blobs by `utm_campaign`, `sales.mjs` orders, Search Console links report. Record each action in `Outreach/OUTREACH-LOG.md` with the UTM used.
- Day-30 report columns: sends, replies, listings live, referral visits, trial starts, orders by `utm_campaign`.

### 5.2 Plan

| Wk | Channel | Exact action | Effort | Measure |
|---|---|---|---|---|
| 1 (Oct 8-14) | Fix own assets | Edit the r/LaTeX post to $19.99 and 1.3.6 (or leave a pinned correction comment). Confirm whether the public `purplelink-llc/purplelink` repo should expose `docs/`. Retire or correct `moderntex-launch-kit.md` and the awesome-LaTeX repo name. | 45 min | Done or not. |
| 1 | awesome-mac | Open one PR to `jaywcjlove/awesome-mac` under Reading and Writing Tools, annotate it, disclose. | 30 min | PR merged; referrer `github.com`. |
| 1 | Mac directories | Submit to Mac Apps Library, Bundl.run, AppMus, MacUpdate (no price in the description), AlternativeTo (free route). One per day. | 20 min each, 100 min | Listings live; referrers. |
| 1 | TUG | Send one email to webmaster@tug.org (draft 6.4). | 15 min | Listed or replied. |
| 1 | Roundups | Contact Dan MacKinlay and Cryptic Insight (draft 6.3). | 30 min | Reply; inclusion; `utm_source` tags. |
| 1 | Reddit watch | Start a 15-minute Monday sweep of r/LaTeX, r/macapps hot for Mac-editor asks and Overleaf-limit complaints. Reply to at most 1 qualifying thread (draft 6.1) per week, only if fresh (under 3 days). | 15 min/week | Replies posted; UTM clicks. |
| 2 (Oct 15-21) | Library and thesis offices, batch 1 | Send 5 emails: Georgia Tech (row 1), UW-Madison (3), St. Mary's (4), UT Knoxville Libraries plus OIT (2, 10), Berkeley EPS (6). Draft 6.4. Spread over 3 days. | 15 min each, 75 min | Replies; guide edits; referrals by `utm_source`. |
| 2 | Roundups | Contact TechDator. For Gaurav Tiwari, send the note but decline any paid or affiliate arrangement unless you choose one. | 30 min | Same. |
| 2 | MacRumors | Create one "ModernTex" thread in the Mac Apps forum per their developer guidelines (disclose, price, trial, link). Answer replies for 48 hours. | 45 min | Thread views; replies; referrer `forums.macrumors.com`. |
| 2 | Personal posts | One disclosed post from your own account on mathstodon.xyz (if you have an account) or LinkedIn (already used for the guide). | 20 min | Referrers. |
| 3 (Oct 22-28) | Department and IT pages, batch 2 | Send up to 6: Reed (11), LSU (12), Claremont McKenna (13), NC State (14), Akron (9, after TUG answers), Purdue (7). Confirm LuaLaTeX before Texas State (8) and UF (23). | 15 min each, 90 min | Replies; edits. |
| 3 | Reviews | Ask your 8 customers, once, by the delivery or update email, for an honest review on SaaSHub (or a short reply you may quote). No incentives. | 30 min | Reviews posted. The first independent review unlocks later listings. |
| 3 | Show HN decision | Optional. If you do it, post once, text written by hand, weekday about noon ET, profile email, username that is not the company, answer everything. Prepare answers for "why not Mac App Store, open source, Homebrew cask". Expect median-ish results (2.2). Skipping it costs nothing. | 3 h including replies | Points, comments, referrer `news.ycombinator.com`. |
| 4 (Oct 29-Nov 6) | r/macapps | Comment in the November App Pile (about 11-01) in Problem / Comparison / Pricing format (draft 6.2). | 30 min | Votes, replies; `utm_source=reddit-macapps`. |
| 4 | Mac media | Send 2 short personal notes: MacStories (row 19) and Mac Power Users feedback form. Offer a free license, expect nothing. Skip TidBITS unless you have a real hook. | 40 min | Replies. |
| 4 | Day-30 review | Pull the report from 5.1. Decide what to repeat. Mark non-replies `no-response` in the log. | 60 min | Report. |

Deliberately left out: Product Hunt (needs a hunting plan and rules on upvote asks, and ModernTex is a niche paid app; revisit after 3 reviews exist), Lobsters, TeX.SE (high downside, see 2.1), Wikipedia, r/PhD and other banned venues, Facebook groups (rules unverified), paid listing tiers.

Top 5 actions in order of expected return per hour: (1) awesome-mac PR, TUG email and the free Mac directories; (2) the independent roundup owners (MacKinlay, Cryptic Insight, TechDator); (3) role-address emails to library and thesis offices that list only TeXShop or Texmaker; (4) a weekly Reddit sweep with fresh-only, disclosed replies, plus the November App Pile comment; (5) fix your own stale assets and collect the first independent reviews.

---

## 6. Draft messages

Facts allowed in every draft (all from `site/llms.txt` and `PRODUCT.md`): native Mac LaTeX editor; live PDF preview; jump between source and PDF; works offline; ordinary .tex files; universal Apple silicon and Intel; macOS 14 or later; needs MacTeX or TinyTeX (one-click TinyTeX install offered); 7-day free trial, no account; $19.99 once, updates included. Do not add claims you cannot back. Avoid em dashes, emojis and hype.

### 6.1 Reddit reply (answer first, fresh thread only)

> [Answer the actual question in two to four sentences, including the free options. For a Mac user asking for an editor: TeXShop ships with MacTeX and is free; TeXstudio and VS Code with LaTeX Workshop also work.]
>
> Disclosure: I make ModernTex, a paid native Mac editor, so weigh this accordingly. It opens ordinary .tex files, shows a live PDF preview, jumps between source and PDF, and works offline. There is a 7-day free trial with no account, then $19.99 once, updates included. It needs MacTeX or TinyTeX and macOS 14 or later. It does not do shared editing with people who are on Overleaf. If you only need something free, TeXShop is the better first try.
>
> https://purplelink.llc/moderntex/?utm_source=reddit-latex&utm_medium=comment&utm_campaign=mt-oct26

### 6.2 Reddit post (r/macapps App Pile or Tier 2 main feed; this is the only standalone format worth using)

Title (main feed only): `ModernTex: native Mac LaTeX editor, 7-day free trial, then $19.99 once`

> I'm the developer. [One sentence on why you wrote it, in your own words.]
>
> **Problem.** [One concrete problem: for example, Overleaf's free plan limits compile time, and some people want to write papers offline in plain .tex files on a Mac.]
>
> **Comparison.** TeXShop is free, long established and ships with MacTeX; its interface is older. TeXstudio is free and cross-platform. Texifier is a paid native Mac editor. Overleaf is web-based with a subscription for more compile time and collaborators. ModernTex is a native Mac app with a live PDF preview and source-to-PDF jumping, and it works offline on ordinary .tex files. It is not for real-time shared editing.
>
> **Pricing.** 7-day free trial of the full app, no account, then $19.99 once, updates included. macOS 14 or later, Apple silicon and Intel. Needs MacTeX or TinyTeX (it can install TinyTeX for you). Signed and notarized direct download.
>
> https://purplelink.llc/moderntex/?utm_source=reddit-macapps&utm_medium=post&utm_campaign=mt-oct26

Edit the Comparison paragraph to match what you can verify about each competitor on the day. Do not use a long list of features.

### 6.3 Blog or roundup inclusion request

> Subject: ModernTex, a native Mac LaTeX editor, for your editors page
>
> Hello [Name],
>
> I read your page "[title]" and noticed it covers [specific editors it lists, for example TeXShop, TeXstudio and Overleaf] but no paid native Mac editor. I make one, so I am writing about a product I sell.
>
> ModernTex opens ordinary .tex files, has a live PDF preview with source-to-PDF jumping, and works offline. It runs on Apple silicon and Intel with macOS 14 or later and needs MacTeX or TinyTeX. There is a 7-day free trial with no account, then $19.99 once.
>
> If it fits the page, I can send a license so you can try it first. If it does not, no reply is needed, and I will not write again. A comparison of Mac editors that you are welcome to check against your own: https://purplelink.llc/guides/best-mac-latex-editors/?utm_source=[site]&utm_medium=email&utm_campaign=mt-oct26
>
> Ben Ampel
> Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350, USA
> ben@purplelink.llc
> This is a one-time message about a commercial product. Reply "no" and I will not contact you again.

### 6.4 Department, library or thesis-office email (role address)

> Subject: A Mac editor to consider for your LaTeX page
>
> Hello,
>
> Your page "[title]" lists [editors named on the page] for Mac users. I am an independent developer and I sell a native Mac LaTeX editor called ModernTex, so you should weigh this as a product suggestion.
>
> It opens ordinary .tex files, shows a live PDF preview, jumps between source and PDF, and works offline. It runs on Apple silicon and Intel with macOS 14 or later, and needs MacTeX or TinyTeX. The trial is 7 days and complete, with no account; the price after that is $19.99 once. I would be glad to send a license to whoever maintains the page.
>
> I know that [page-specific note, for example "the page says Graduate Education does not offer direct technical support", so I am only asking whether the page could list it, not asking for support]. If it does not fit, please ignore this; I will not write again.
>
> More detail and a comparison with TeXShop and TeXstudio: https://purplelink.llc/guides/texshop-alternative-mac/?utm_source=[org]&utm_medium=email&utm_campaign=mt-oct26
>
> Ben Ampel
> Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350, USA
> ben@purplelink.llc
> This is a one-time message about a commercial product. Reply "no" and I will not contact you again.

TUG variant (row 5), replace the middle paragraphs with: "Your page 'TeX Resources on the Web' says additions are welcome. It has a commercial vendors section but lists no native Mac editor. ModernTex is one: [two-sentence description as above]. I can send a license or a short factual entry in whatever format you prefer."

For Georgia Tech, Texas State and UF, check the page's engine requirement (LuaLaTeX with TeX Live 2025 on the last two) against ModernTex before sending; the Engine section of the start guide says the root file's `% !TEX program =` line selects xelatex and an engine can be set by hand, but LuaLaTeX support is not stated on the pages I read.

---

## 7. Unverified items and gaps (for the next pass)

- Full r/LaTeX, r/AskAcademia, r/GradSchool, r/academia, r/math, r/MacOS rules: NOT FOUND. Read the sidebars in your own browser before any new Reddit action.
- Threads from 2026-08-15 to 2026-09-03 and evergreen "which Mac LaTeX editor" threads: not reachable. Use Reddit search in your browser.
- Google rankings (only DuckDuckGo was checked). Search Console is the better source.
- Whether a megathread comment counts against r/macapps Rule 3; whether the Tier system is unchanged since about 2026-03.
- Whether purplelink.llc has Terms and Privacy pages sufficient for r/macapps Tier 2, whether the postal address is a registered commercial mailbox, SPF/DKIM/DMARC state, and whether ModernTex handles LuaLaTeX and `--shell-escape`.
- Nav - AI's contact route and whether you submitted that listing; whether a ModernTex page exists on MacUpdate.
- Softpedia, Slant, SourceForge, MacRumors forum page: Cloudflare-blocked.
- Facebook group sizes and rules; any Slack or Discord community for LaTeX users: NOT FOUND.
- Count of competitor threads is from hot listings only and is not a census.
