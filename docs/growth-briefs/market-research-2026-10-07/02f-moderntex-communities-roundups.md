# ModernTex: other communities, directories, guides and roundups (read-only research)

Researched 2026-10-07. Nothing was posted, submitted, emailed or changed. Every claim carries a source URL and date.

Evidence labels
- VERIFIED: I loaded the primary page or API myself on 2026-10-07 (date shown is the page's own date where it has one).
- SECONDARY: from a search snippet, a third-party page about the thing, or my arithmetic on verified data.
- UNVERIFIED: could not be confirmed; stated as such. No member counts are invented.

Method limits you should know about
- The WebSearch tool hit its 200-call session cap partway through, so SERP checks were done by loading DuckDuckGo results in the Browser pane (DuckDuckGo is Bing-backed). Google rankings were NOT checked. Treat all "ranks #N" statements as DuckDuckGo, 2026-10-07.
- Cloudflare bot challenges blocked Softpedia, Slant, SourceForge, MacRumors main forum, latex.org and AlternativeTo's add-app flow. I did not try to get past them. Those items are marked UNVERIFIED.
- Reddit was out of scope here (covered elsewhere).

---------------------------------------------------------------------------------------------------

## 0. Things you should know first (corrections and flags)

1. The awesome-LaTeX PR is already open. BenAmpel opened egeerardyn/awesome-LaTeX PR #128 "Add ModernTex to LaTeX-focused editors" on 2026-10-03, state open, 0 comments, with the affiliation disclosed. VERIFIED: https://github.com/egeerardyn/awesome-LaTeX/pull/128 (API read 2026-10-07). It is not in your "already done" list.
2. docs/moderntex-launch-outreach.md names the wrong repo. It says github.com/danphilps/awesome-LaTeX. That repo has 0 stars and was last pushed 2020-08-22 (VERIFIED, https://api.github.com/repos/danphilps/awesome-LaTeX). The live list (1,672 stars, pushed 2026-08-08) is egeerardyn/awesome-LaTeX. The PR above went to the right one.
3. The SaaSHub listing already exists, with your copy: https://www.saashub.com/moderntex (VERIFIED 2026-10-07; 0 reviews). The outreach doc lists SaaSHub as a to-do.
4. A public GitHub repo exposes your internal outreach plan. https://github.com/purplelink-llc/purplelink is public (VERIFIED via API: private=false, pushed 2026-10-07). https://github.com/purplelink-llc/purplelink/blob/main/docs/moderntex-launch-outreach.md returns HTTP 200 and is indexed: it appeared in DuckDuckGo for "ModernTex" queries. The same /docs folder lists paper-review-runbook.md, security-paper-review.md, growth-briefs, site-audit files and others (VERIFIED, https://api.github.com/repos/purplelink-llc/purplelink/contents/docs). That file includes unsent drafts, sales counts and the anti-AI-tell word list. Worth checking whether this is intended. I did not read the other docs.
5. Library guides at the big R1 schools are Overleaf-only (section 4). A "Mac editor" pitch to CMU, Caltech, Princeton, Harvard Library, Penn or Cornell has almost nothing to attach to.
6. The Wikipedia comparison article was purged of entries without Wikipedia articles on 2026-07-31, and two self-added editors were reverted on 2026-10-02 and 2026-10-06 (section 4). ModernTex does not qualify.

---------------------------------------------------------------------------------------------------

## 1. TeX StackExchange and the Software Recommendations site

### 1.1 Self-promotion policy (all Stack Exchange sites, applies to TeX.SE)
- VERIFIED. https://tex.stackexchange.com/help/promotion ("How to not be a spammer", same text at https://stackoverflow.com/help/promotion, loaded 2026-10-07):
  - Overt self-promotion gets downvoted and flagged as spam. "Good, relevant answers" where some happen to be about your product are fine.
  - If you mention your product, website, etc. in a question, answer or any other contribution, "you must disclose your affiliation in your post."
  - Behaviors that nearly always get flagged: talking about your product too much; answering only questions where your product is the answer; asserting instead of showing; links that do not directly support what you wrote; links as a substitute for information in the answer itself.
  - "If the only reason you're here is to sell something or drive traffic to your site, then please avoid posting answers."
- VERIFIED. https://tex.stackexchange.com/help/product-support (loaded 2026-10-07): "Can I support my product on this site?" Product teams are welcome within limits: search for existing questions about the product, answer or vote up, take part in the site generally (not only your product), build reputation before commenting or editing, and guide users on what to ask where. The page says explicitly that the site "can't be the only support."
- VERIFIED. TeX.SE meta, "self promotion of an own code" (2014-07-17, score 10), https://tex.meta.stackexchange.com/questions/4531/self-promotion-of-an-own-code. Top answer (score 5, 2014-08-05): linking to something you made once or twice is fine; if every post links to the same place you are "probably Doing It Wrong." Old, but consistent with the help-center text.
- VERIFIED. TeX.SE meta, "Editing out someones professional affiliation to a company" (2023-05-10, score 12), https://tex.meta.stackexchange.com/questions/10072/editing-out-someones-professional-affiliation-to-a-company. The question is about an Overleaf support-staff answer. The community position (answer score 8, 2023-05-16) is that a disclosure must not be edited out; edits that remove it are rejected or reverted with the note "Restore ... disclosure as required by /help/promotion". This is a TeX.SE precedent for a vendor answering with a one-line affiliation statement.

### 1.2 Does TeX.SE allow software-recommendation questions?
- VERIFIED. The on-topic help page for TeX.SE (https://tex.stackexchange.com/help/on-topic, loaded 2026-10-07) lists formats, engines, distributions and "related software and tools." It says nothing about recommendation questions. The generic "what to avoid" page (https://tex.stackexchange.com/help/dont-ask) bars "What's your favorite ___?" style questions.
- VERIFIED. TeX.SE meta, "Can one ask for TeX related software recommendations here?" (2014-05-01, score 2), https://tex.meta.stackexchange.com/questions/4391/. No answers. Comment (2014-05-01): "What sort of recommendations? We have a big question on IDEs." There is no written TeX.SE rule I could find on recommendation questions.
- VERIFIED (observed behavior). Fresh "which Mac LaTeX editor" questions get closed as duplicates. Closed examples from the API: https://tex.stackexchange.com/questions/257282/need-to-find-a-good-editor-for-mac (closed Duplicate, 2015-07-27); https://tex.stackexchange.com/questions/634128/ (Duplicate, 2022-02-16). SECONDARY inference: the duplicate target is the editors list below. Do not post a new "what editor" question.
- VERIFIED. The canonical home for editor listings is the community-wiki "big list" "LaTeX Editors/IDEs", https://tex.stackexchange.com/questions/339/latex-editors-ides (API read 2026-10-07): created 2010-07-27, score 951, 754,552 views, 59 answers, last activity 2026-06-09, not closed, not locked, protected since 2016-05-31 (protection means a new account needs 10 rep earned on this site, not the association bonus). Texifier and TeXShop already have answers; ModernTex does not. Newest answers are from long-standing users (Werner, 2026-06-09 and 2025-08-27).
  - Governing meta thread: "Let's polish the Editors/IDEs question" (2013-02-08, score 68), https://tex.meta.stackexchange.com/questions/3253/. It defines a per-editor answer template (platforms, license, Unicode, SyncTeX, etc.) and "editor caretakers." Any ModernTex answer should follow that template and open with the affiliation.
- VERIFIED. Other open questions that rank for your terms: "Alternatives to Overleaf (i.e. instant TeX compiling without sign in)" (score 31, 75,878 views, 3 answers, last activity 2026-04-14, open) https://tex.stackexchange.com/questions/488049/ ; "A LaTeX editor between TexShop and Texmaker for Mac OS?" (18,907 views, 4 answers, last activity 2018-02-15, open) https://tex.stackexchange.com/questions/108128/ ; "Alternative to overleaf (with a better free plan)" was closed as Duplicate on 2025-09-10 https://tex.stackexchange.com/questions/750873/ .
- VERIFIED (negative). A search of TeX.SE and softwarerecs for "ModernTex" returns 0 results (SE API, 2026-10-07).
- Your standing: you have a TeX.SE account with a "past answers not well-received" warning. I did not look at it (no account access). On this evidence, the lowest-risk route is nothing at all on TeX.SE until you have earned rep on unrelated answers; if an answer is ever posted it should be the template answer on question 339 with the first line "I develop ModernTex" and no marketing language. The 10-rep protection and the community's reaction to a new vendor are the risks. Rated: low priority, high downside.

### 1.3 The separate "Software Recommendations" site
- VERIFIED. It exists and is alive: https://softwarerecs.stackexchange.com . API 2026-10-07: 23,372 questions, 24,772 answers, 92,207 users; newest question 2026-10-06.
- VERIFIED. Topic rule (https://softwarerecs.stackexchange.com/help/on-topic): questions must ask for ready-to-use software for a task; good ones have a purpose plus objective requirements; "answers demonstrate how the recommended product meets the requirement." A generic blurb is never an appropriate answer.
- VERIFIED. Own-software rule: softwarerecs meta, "Are there any guidelines for answering with your own software?" (2018-05-02, score 7), https://softwarerecs.meta.stackexchange.com/questions/2741/ . Top answer (score 5, 2018-05-19): no site-specific policy; follow the general SE self-promotion text; disclose clearly ("which I work on" is enough); do not pose as a customer; stay neutral; mention limitations and cheaper or competing options where relevant.
- VERIFIED (it is not a real venue for you). The 8 newest latex-tagged questions run from 2021-06-03 to 2026-03-23, which is about one or two a year recently, and none is about a Mac editor (SE API, tagged=latex sorted by creation, read 2026-10-07). The one on-topic old thread, "What is a good LaTeX editor for writing thesis?" (2014-02-04, score 29) https://softwarerecs.stackexchange.com/questions/135/ is a 12-year-old question. Rated: not worth effort unless a matching new question appears (set a saved search; do not go looking).

---------------------------------------------------------------------------------------------------

## 2. Hacker News

### 2.1 Rules
- VERIFIED. Show HN rules, https://news.ycombinator.com/showhn.html (loaded 2026-10-07, page undated):
  - "Something you've made that other people can play with"; must be something you "worked on personally" and are around to discuss.
  - Not allowed as Show HN: blog posts, sign-up pages, newsletters, lists, reading material, landing pages, fundraisers, minor version bumps.
  - "Make it easy for users to try your thing out, ideally without barriers such as signups or emails."
  - "Please don't ask friends to upvote or comment."
- VERIFIED. Guidelines, https://news.ycombinator.com/newsguidelines.html (2026-10-07): do not use HN primarily for promotion ("ok to post your own stuff part of the time"); do not solicit upvotes, comments or submissions.
- VERIFIED. FAQ, https://news.ycombinator.com/newsfaq.html (2026-10-07): submissions, accounts and sites that solicit votes are penalized or banned; reposted stories within about a year are auto-buried as duplicates.
- VERIFIED. Moderator tips comment by dang (posted 2020-02-15, edited 2026-03-28), https://news.ycombinator.com/item?id=22336638 :
  - Write the post text by hand; do not use an LLM to generate or even edit it (added 2026-03-28; the community is hostile to LLM-sounding text right now).
  - State clearly what it is and what is different; include backstory; drop marketing language; factual and direct.
  - "Don't have your username be that of your company or project."
  - Put an email address in your profile (HN sends repost invites to those).
  - Friends and users must not add booster comments.
  - A new release is a valid Show HN only if "significantly different"; this should happen "once or twice a year" at most.
  - He also notes that they can no longer answer emails about Show HN advice ("far too many of them") since 2026-03-28.
- VERIFIED. Paid and trial is fine. A moderator (dang) wrote on 2025-08-24: "it's fine to talk about paid features, as long as it's clear which ones are paid and which ones not. The only thing that wouldn't be fine is to post a Show HN with no way to try the product out" (https://news.ycombinator.com/item?id=45006257, in the Show HN thread https://news.ycombinator.com/item?id=45003420). Earlier moderator answer (2015-02-18, https://news.ycombinator.com/item?id=9066410): "It's ok if people have to download an app to do that." Conclusion: a downloadable 7-day full-featured trial with no account qualifies; a page whose only action is "buy" would not.
- VERIFIED. Second-chance pool: explained in "Show HN: Second-Chance Pool" (dang, 2021-04-30), https://news.ycombinator.com/item?id=26998308 : moderators and a few reviewers pick old submissions that did not get attention; software drops them at random onto the lower half of the front page. You may write hn@ycombinator.com about your own post but moderators prefer others to nominate. Pool page: https://news.ycombinator.com/pool . Recent examples of dang using it: 2026-08-31 (https://news.ycombinator.com/item?id=49513694) and 2026-06-22 (https://news.ycombinator.com/item?id=48624103). Given the 2026-03-28 note, do not count on email replies.
- VERIFIED. HN's own text on voting rings (dang, multiple years, e.g. 2014-10-15 https://news.ycombinator.com/item?id=8461504 and 2025-09-17 https://news.ycombinator.com/item?id=45270968): friends upvoting or commenting is detected, penalized, and "comes across as astroturfing." Do not ask the six buyers to go upvote. Product Hunt is where "ask people to visit and comment" is acceptable; HN is not.

### 2.2 Norms for paid Mac apps (evidence from threads)
- VERIFIED. Direct-download, closed-source and paid is a recurring objection but not fatal. In the NetViews thread (paid, $20 and $50 tiers, direct download, 243 points, 61 comments, 2026-02-10, https://news.ycombinator.com/item?id=46955712), one top comment says "closed source and not being on the App Store is a bit of a dealbreaker for me," another says it must be on Homebrew. The developer replied he would add a Homebrew cask. Plan to be asked: why not Mac App Store, why not open source, is there Homebrew (SECONDARY inference: the answer is useful to have ready; I cannot check ModernTex's cask status).
- VERIFIED. Subscription pricing draws the harshest comments: "Swift Mail" (native, $3/month, 79 points, 102 comments, 2024-02-20, https://news.ycombinator.com/item?id=39443927) and the AirPods app (23 EUR per year, 223 points, 309 comments, 2024-09-30, https://news.ycombinator.com/item?id=41695756). One-time pricing at $19.99 avoids that thread of criticism; "one-time purchase" is a plus in the comments I read (e.g. https://news.ycombinator.com/item?id=46614469 titled "Offline macOS dictation. One-time purchase, no sub" got only 1 point, so the label alone does not carry a post).

### 2.3 What happens to Mac and LaTeX-editor Show HN posts (my computation from the HN Algolia API)
- VERIFIED data, SECONDARY arithmetic. I pulled every Show HN submission from 2025-12-09 to 2026-10-05 via https://hn.algolia.com/api/v1/search_by_date (tags=show_hn; 40,757 posts).
  - Overall: 8.1% reached 10+ points, 2.9% reached 50+, 1.6% reached 100+.
  - Titles containing macOS/Mac/MacBook/SwiftUI as a word: 1,245 posts, median 2 points, 87 reached 10+, 42 reached 50+ (3.4%), 27 reached 100+.
  - The high-scoring ones are mostly free or open source (examples: "A native macOS client for Hacker News, built with SwiftUI", 265 points, 2026-02-20, https://news.ycombinator.com/item?id=47088166; "Apfel", 743 points; "boringBar", 520 points; "Tolaria", 318 points). The notable paid exception is NetViews (243 points, above).
  - LaTeX/Typst/TeX titles: 54 posts. Top: "TikZ Editor – WYSIWYG editor for figures in LaTeX" 451 points, 74 comments, 2026-06-23, free and open source (https://news.ycombinator.com/item?id=48645437); "TeXbrain, a LaTeX editor that runs pdfTeX in the browser via WASM" 118 points, 28 comments, 2026-08-25, free and open source (https://news.ycombinator.com/item?id=49441375). Almost every other LaTeX-editor Show HN in 2025-2026 scored 1 to 5 points, for example "Texpile" (3 and 1 points, 2026-08-03 and 2026-10-06), "TeXposit" (4 and 2 points), "GlyphX, a local-first LaTeX editor that compiles offline" (4 points, 2026-06-14), "TeXlyre" (2 points, 2025-10-05), "Octree" (1 point, 2026-02-12). Sources: Algolia search of tags=show_hn, query "LaTeX editor" run 2026-10-07.
  - Nothing named ModernTex or Purplelink has been posted to HN (Algolia story and comment search, 2026-10-07).
- Meaning (SECONDARY): HN rewards free, open or technically novel tools. A paid, closed LaTeX editor for Mac is closer to the median (about 2 points) than to the tail. The realistic upside is a handful of useful comments, not a front-page spike.

### 2.4 Timing
- No official guidance exists (searched FAQ, guidelines and moderator comments). UNVERIFIED as policy.
- My own analysis of the same 40,757 posts (times in US Eastern): success rates barely vary by weekday (50+ points: 2.7% to 3.4%, highest Sunday 3.4% and Saturday 3.1%). By hour, 12:00 to 13:59 ET shows the highest 50+ rate (4.3% and 3.8%) against a base of 2.9%, and 01:00 to 07:00 ET is lowest (1.6% to 2.8%). The differences are small relative to the noise; do not over-read them. The existing launch-kit advice (weekday, 8-10am ET) is not contradicted, but noon ET is slightly better in this sample.

---------------------------------------------------------------------------------------------------

## 3. Mac forums, directories, social

### 3.1 MacRumors
- VERIFIED. There is an explicit, free developer-promotion policy: "Guidelines for Software Developers", https://macrumors.zendesk.com/hc/en-us/articles/201294426-Guidelines-for-Software-Developers (page shows "Updated 14 days ago" at load on 2026-10-07):
  - Developers of macOS software may promote their own products in their own threads in the "Mac Apps and Mac App Store" forum (https://forums.macrumors.com/forums/mac-apps-and-mac-app-store.xx/, URL unverified because of Cloudflare) and other listed Software Discussion Forums.
  - You may solicit feedback, recruit beta testers, discuss prices, and answer questions.
  - Required: one account only; fill in "About you" saying you are a developer; put your website in the Website field; thread title should be the app name; at most one thread per app (or per major release) per forum; post updates in that thread, not new ones; identify yourself and your company in the first post.
  - Forbidden: promoting as if you were a consumer; promoting outside those forums; bumping without anything new to say; copying website text only; promo codes outside the "Code Sharing and Software Promos" forum (giveaways go there).
  - They also sell advertising.
  - This is the only forum I found with a written, developer-friendly self-promotion lane. Fit: moderate (a Mac user audience, but not academic). Cost: free. The registration agreement forbids advertising elsewhere on the site (https://macrumors.zendesk.com/hc/en-us/articles/201146626-MacRumors-Registration-Agreement).

### 3.2 Apple Support Communities
- VERIFIED. "No advertising. Do not use the Site to sell or market products or services to others and do not post a URL unless it directly answers a user's question." Forbidden: a submission created solely to advertise software; any link to a commercial product not directly related to a technical support question. Source: https://discussions.apple.com/terms (loaded 2026-10-07). Not a venue.

### 3.3 Product Hunt
- VERIFIED. Featuring guidelines (dated 2026-03-10), https://help.producthunt.com/en/articles/9883485-product-hunt-featuring-guidelines : features live digital products; does not feature directories, lists, services, courses, waitlisted products (unless immediate access) and so on; one criterion is "Value Over Monetization," avoiding minimal, undifferentiated products focused on immediate monetization. Nothing excludes a paid app with a trial. UNVERIFIED whether a paid-with-trial Mac app is treated favorably; the guidelines do not say.
- VERIFIED. Launch guide, https://www.producthunt.com/launch (2026-10-07, undated): "you cannot ask people directly to upvote your product. Instead, ask them to visit and comment." No company accounts ("Company accounts are prohibited"). 12:01 am Pacific is stated as the best time for makers who plan ahead. Makers can hunt their own product.
- Existing doc plans "rally the six buyers"; the rule is no direct upvote asks, so word it as "come and comment."

### 3.4 MacUpdate
- VERIFIED. Free-form developer submission exists: https://www.macupdate.com/help/submit-app ("New App Submission Guidelines"; footer has "Add App"). Fields: App Name (no version or promo text), Download URL (direct installer such as .dmg or .pkg is accepted), Product Page URL, Price, Short Description (do not include the app name), Description ("avoid promotional text and pricing information"), Version Changes, System Requirements. Requires an account (the header shows "Sign in / Create account"). The page does not state a fee or a review time (UNVERIFIED). A listing for ModernTex was not found in DuckDuckGo results for "ModernTex" (UNVERIFIED that none exists; the MacUpdate search URL I tried returned 404).
- Note: the "description avoids pricing information" rule conflicts with the reusable listing copy in your outreach doc (which says "$19.99 once").

### 3.5 AlternativeTo
- VERIFIED. No ModernTex page: https://alternativeto.net/software/moderntex/ returns the site's 404 view (loaded 2026-10-07). The Overleaf alternatives page with the Mac filter is https://alternativeto.net/software/writelatex/?platform=mac (it ranked in DuckDuckGo for "overleaf alternative offline mac native").
- VERIFIED. Terms of Use (last updated 2026-10-06), https://alternativeto.net/about/terms/ : the site lists software "submitted and described by our community"; submitted apps go into a review backlog that is "usually months long"; a one-time fee buys priority review (price shown at checkout); they may remove or edit listings. Contact: hello@alternativeto.net (https://alternativeto.net/about/). The add-app form itself needs a login and I did not open it. Free route exists; paid fast lane exists; do not pay without deciding.
- UNVERIFIED: the "no company submissions" rule, if any. The terms page does not mention one.

### 3.6 SaaSHub
- VERIFIED. Already listed: https://www.saashub.com/moderntex (title "Is ModernTex good? - SaaSHub", 0 reviews). Alternatives page: https://www.saashub.com/moderntex-alternatives . Submission tool: https://www.saashub.com/submit/list . Nothing further to do except get a first review.

### 3.7 Softpedia, Slant, LibHunt
- Softpedia: UNVERIFIED how to submit. mac.softpedia.com and its contact page (https://www.softpedia.com/user/contact.php) are behind a Cloudflare challenge; I did not pass it. Search results for submission surfaced only third-party submitter tools.
- Slant (slant.co): UNVERIFIED. Returns a Cloudflare block (HTTP 403).
- LibHunt: VERIFIED irrelevant. Its own title is "Trending open-source projects and their alternatives" (https://www.libhunt.com, 2026-10-07). ModernTex is closed source. Skip.

### 3.8 Setapp
- Status per your log: developer application submitted 2026-10-07 via setapp.com/developers; they say they reply within 10 business days (Outreach/OUTREACH-LOG.md line 142). Nothing else checked.

### 3.9 Mac-app directories (all checked 2026-10-07)
| Directory | Free route | Paid route | Fit and notes |
|---|---|---|---|
| Mac Apps Library https://www.macappslibrary.com/submit | Standard $0, human review | Priority $29, decision within 24 business hours | Form accepts "Available through: Direct" and a direct download URL; needs 1 to 4 screenshots. Good fit. |
| Bundl.run https://bundl.run/submit | Free; email verification, then review, then listing (stays draft until verified) | not seen | "Homebrew cask, Mac App Store, or a direct download all work." Site says 5,057 apps listed. Good fit. |
| TryMacApps https://www.trymacapps.com/submit | Free if you add their badge to your landing page (listing and a backlink) | $29 "with our badge" tier shown; Editor's Choice $199 (was $299) | Requires a badge on purplelink.llc, which is a link out from your page. Ask yourself whether you want that. |
| Mac Apps Daily https://macappsdaily.com/submit | Free waitlist, "Estimated review: 6+ months" | $39 for 48-hour review (states it does not influence the decision) | Low value unless paid. |
| Indie Apps https://indie-apps.com/submit | Paste an App Store link; also TestFlight and open source | Placement from $24.99/month | Not applicable: ModernTex is not on the App Store. |
| Indie App Catalog https://indieappcatalog.com/ | has a "Non-App Store" category and a "Submit App" link; https://indieappcatalog.com/submit returns 404 | n/a | UNVERIFIED how to submit; look at the header link when you are ready. |
| AppMus https://appmus.com/submit | Free form (name, website, logo URL, description, categories) | n/a | It publishes comparison pages that rank (e.g. "TeXstudio vs TeXShop"), which do not mention ModernTex. |
| Sugggest https://sugggest.com/contact | Contact form has a "Software Suggestion" topic | n/a | It ranks for "texshop alternatives"; no ModernTex mention. |
| Awesome-lists | see section 5.4 | | |

### 3.10 Lobsters
- VERIFIED. https://lobste.rs/about (2026-10-07): self-promotion rule of thumb is "less than a quarter of one's stories and comments"; authors are welcome but not as a "write-only tool for product announcements." Accounts are invite-only; new users (first 70 days) cannot use the "show" tag, cannot submit links to unseen domains, and cannot resubmit. "Show Lobsters / Projects" is the `show` tag (https://lobste.rs/t/show.json lists posts such as an Apple Intelligence remover, 19 points, 2026-10-06). There is no latex tag; there is a `mac` tag ("Apple macOS"). Fit: poor (programmer audience, invite barrier, no paid-app tradition in what I saw). Not recommended.

### 3.11 Mastodon (instance API read 2026-10-07)
| Instance | Users (v1 stats) | Active this month | Sign-up | Self-promotion wording |
|---|---|---|---|---|
| scholar.social | 1,227 | 282 | closed | Rules include "No spam" and "No bots or 'institutional' accounts operated by non-members (Scholar Social is for individuals)." Post as yourself, not as Purplelink. https://scholar.social/api/v2/instance |
| mathstodon.xyz | 27,055 | 5,379 | approval required | "No spam. ... the advertising of goods or services we find inappropriate, irrelevant, or too frequent. If in doubt, ask us." https://mathstodon.xyz/api/v2/instance |
| fediscience.org | 6,070 | 905 | approval required, must show publications | No explicit self-promo rule listed; "Promotion of pseudoscience" and misinformation banned; must verify you are a scientist. https://fediscience.org/api/v2/instance |
- Hashtag volume as seen from mastodon.social over the last 7 days to 2026-10-06 (https://mastodon.social/api/v1/tags/latex): #latex 155 posts by 74 accounts; #overleaf 1 post; #texshop 0; #typst 6 posts; #academicmastodon 8 posts; #phdchat 6 posts. This is one server's view of the federation, so treat it as a floor, not a count. Take away: LaTeX chatter is small and thin; a hashtag post will reach tens of people, not thousands.
- Fit: low volume, but the audience is correct and one honest, disclosed post from your personal account is within the written rules of all three. mathstodon.xyz also renders LaTeX.

### 3.12 Bluesky
- UNVERIFIED completeness. Public starter-pack search (https://public.api.bsky.app/xrpc/app.bsky.graph.searchStarterPacks) returned no starter pack for LaTeX typesetting or academic Mac software; "latex" queries return only fetish-content packs. Existing relevant packs I did find: "Typst people" by typst.app (https://bsky.app/starter-pack/typst.app/3m62vo3m6762c) and "Mac and iOS indie devs and companies" by bjango.com (https://bsky.app/starter-pack/bjango.com/3lbynlb5buz2w); both show 0 "joined" from the search result. Starter packs are curated by their creators, so the route is to ask a curator or build your own; do not expect an existing LaTeX pack.

### 3.13 Facebook groups (names only; sizes not verified)
Search results (DuckDuckGo, 2026-10-07) show these groups exist. Facebook requires login to see member counts, so all sizes are UNVERIFIED.
- "(La)TeX user group" https://www.facebook.com/groups/170883319628439/
- "TeX Users Group" https://www.facebook.com/groups/TeXUsersGroup/
- "LaTeX/TikZ Users' Support Group" https://www.facebook.com/groups/1053392884708403/
- "LaTeX For Users Facebook" https://www.facebook.com/groups/LATEXFORUSERSFACE/
- "LATEX" https://www.facebook.com/groups/1032297055642397/
(Other hits were unrelated: latex crafts, printers, fetish.) Group rules are unverified; read each group's rules tab before anything.

### 3.14 Discord and Slack
- Typst Discord (a competitor community): VERIFIED invite https://discord.gg/2uDybryKPe, shown on https://typst.app/community; Discord's public invite API on 2026-10-07 reports about 13,219 members, about 2,324 online. Not a place to promote ModernTex; listed because it is the largest verifiable TeX-adjacent Discord.
- LaTeX Discord: UNVERIFIED. A LaTeX.org thread titled "A Discord server for LaTeX" exists (https://latex.org/forum/viewtopic.php?t=35552, seen in search results), but the page would not load for me, so I do not have an invite or size. A "TeXit" Discord bot also exists (https://top.gg/bot/510789298321096704), which is a bot, not a community.
- Slack, PhD Discords, Programming Historian: not found or not verified. I did not list any I could not confirm with a URL.

---------------------------------------------------------------------------------------------------

## 4. University and standards-body pages that list LaTeX editors

### 4.1 Library guides that list local Mac editors (best-fit targets). All loaded 2026-10-07.
| School and guide | Editors named on the page | "Last Updated" on the page | Published contact route |
|---|---|---|---|
| Univ. of Tennessee Knoxville https://libguides.utk.edu/latex | TeXShop, TeXstudio, Texmaker, Overleaf | May 5, 2026 | Page says to "contact dataservices@utk.edu"; mailto links for eproblems@utk.edu and sgavel@utk.edu appear in the page markup (role of the latter not verified) |
| NYU https://guides.nyu.edu/LaTeX/installation | TeXShop (4 mentions), TeXstudio, Texmaker, Overleaf | May 4, 2026 | No email on the page; use NYU Libraries "Ask" (not verified) |
| St. Mary's College of Maryland https://libguides.smcm.edu/latex/SetUp | TeXShop (5 mentions), Texmaker, TeXworks, Overleaf | Aug 31, 2026 | ask@smcm.libanswers.com (on page) |
| Occidental College https://libguides.oxy.edu/LaTeX/basics | TeXShop, TeXstudio, Texmaker | Jun 25, 2025 | none on page |
| UC Berkeley EPS libs https://guides.lib.berkeley.edu/latex | TeXstudio, Texmaker, TeXworks, Overleaf (Overleaf-heavy) | Aug 27, 2026 | "contact epslibs@berkeley.edu" (on page) |
| UChicago https://guides.lib.uchicago.edu/latex/home | TeXstudio, Texmaker, TeXworks, Authorea; Overleaf-centered | Oct 2, 2026 | hartj@uchicago.edu in the page markup (CS, geophysical sciences, math and statistics librarian contact box) |
| Dickinson College https://libguides.dickinson.edu/LaTeX | TeXShop, Overleaf | Jul 19, 2021 (stale) | thompken@dickinson.edu in page markup |
| Florida Tech https://libguides.lib.fit.edu/c.php?g=427921&p=5199720 | TeXstudio, Texmaker, Papeeria, Overleaf | Jun 29, 2025 | library-reference@fit.edu in markup |
| UMass Amherst https://guides.library.umass.edu/LaTeX/Home | Overleaf only (MacTeX, MiKTeX as distributions) | Sep 15, 2026 | queued via Ask form per your notes |
Note: none of these name Texifier, TeXpad or any commercial Mac editor, so ModernTex would be a new category for them, not a swap. All emails above are published on the cited pages; I did not guess any.

### 4.2 R1 library and thesis pages that are Overleaf-only (low fit)
Same date, 2026-10-07: CMU https://guides.library.cmu.edu/overleaf ("Overleaf for Scholarly Writing", only Overleaf named); Caltech https://library.caltech.edu/write/overleaf (library@caltech.edu); Princeton https://libguides.princeton.edu/c.php?g=1066954 (only Overleaf); Harvard Library https://guides.library.harvard.edu/overleaf/latex (updated Oct 6, 2026; only Overleaf); Penn https://guides.library.upenn.edu/latex (Overleaf); Cornell https://guides.library.cornell.edu/latex (Overleaf, one mention); Georgia Tech thesis templates https://grad.gatech.edu/theses-dissertations/templates (thesis@grad.gatech.edu; Overleaf, Texmaker, MiKTeX); MIT thesis template https://web.mit.edu/thesis/tex/ (mit-theses@mit.edu; Overleaf); Texas State Graduate College https://www.gradcollege.txst.edu/students/research-thesis-dissertation/thesis-dissertation/latex-template-guide.html (gradcollege@txstate.edu; Overleaf). Stanford's CS103 pages and Overleaf's own EDU pages dominate those searches.
Not found: library LaTeX guides for Stanford, UMich, Purdue, UIUC, UW, Columbia and a Georgia Tech library guide. Searches did not surface them and guessed URLs returned 404. UNVERIFIED that they do not exist.

### 4.3 Math and CS department pages
- Harvard Mathematics "Computing: LaTeX" https://people.math.harvard.edu/computing/latex/index.html (lists TeXShop only; webmaster@math.harvard.edu appears in the markup; undated).
- UCSD Math "TeX/LaTeX for Apple macOS" https://www.math.ucsd.edu/~wcheung/texformacosx.html (a staff member's personal page, TeXShop and TeXworks; no contact email on page).
- Fit: a one-line addition to a department page is plausible only where a named Mac user maintains it; both are old pages. Low yield.

### 4.4 TUG, CTAN, LaTeX Project
- TUG "TeX Resources on the Web": VERIFIED. https://tug.org/interest.html states: "Additions and corrections are always welcome, please email webmaster@tug.org." The page has "Free editors and front-ends" (lists TeXShop, TeXworks, TeXstudio, Texmaker and others, with no Texifier) and a separate section "Commercial and shareware TeX vendors and projects" (lists Scientific Word, WinEdt, Overleaf, LaTeXBase, GrindEQ and others). A commercial Mac editor belongs in the latter. This is the cleanest "how do I get listed" route in this whole report: a short factual email to webmaster@tug.org. Fit: high authority, low traffic; no conflict-of-interest rule is stated.
- MacTeX page https://tug.org/mactex/ : names TeXShop, TeX Live Utility, LaTeXiT, BibDesk, hintView as the bundled programs; no third-party editor list (2026-10-07).
- CTAN editors catalogue (https://ctan.org/topic/editor): not a fit. CTAN is an archive of freely redistributable TeX software; its upload page requires you to state a license (https://ctan.org/upload) and its license page treats non-free terms as an exception (https://ctan.org/license/). ModernTex is a paid binary with a trial. SECONDARY inference that it would be rejected; I did not find a rule that says so outright.
- LaTeX Project "Get LaTeX" page https://www.latex-project.org/get/ : names only MacTeX, MiKTeX/TeX Live, and online services (Overleaf, Papeeria, CoCalc). No editor list for Mac. Contact is at the foot of the page (not verified). Not a fit.

### 4.5 Wikipedia
- VERIFIED. "Comparison of TeX editors" (https://en.wikipedia.org/wiki/Comparison_of_TeX_editors): carries maintenance banners for original research and synthesis (April 2026) and out of date (August 2022). It lists only editors that have their own Wikipedia articles (AUCTeX, Authorea, CoCalc, Kile, LyX, Overleaf, TeXShop, TeXstudio, Texmaker, TeXworks, VS Code and so on). Texifier, TeXpad, TeX64 and ModernTex are not in it. Revision history (API, 2026-10-07): 2026-07-31 MrOllie "rm entries without wikipedia articles"; 2026-10-02 reverted an editor's "added my personnal LaTeX Editor"; 2026-10-06 reverted "Add my personal LaTeX block editor." So self-added rows get removed within hours.
- VERIFIED. There is no page named "TeX editor" (API title lookup returns missing). TeX software lives under TeX and the comparison article.
- Proper route (VERIFIED policy text, https://en.wikipedia.org/wiki/Wikipedia:Conflict_of_interest): paid or connected editors are "strongly discouraged from editing affected articles directly" and "can propose changes on article talk pages," disclosing the connection (the page shows the {{Connected contributor}} template). Edits are judged on the same standards as anyone's; the comparison page's own practice (above) means a row needs a Wikipedia article, which needs independent significant coverage. ModernTex has none yet. Recommendation: do not touch it. Revisit only after real third-party reviews exist.

---------------------------------------------------------------------------------------------------

## 5. "Overleaf alternative" and "best LaTeX editor Mac" roundups

### 5.1 What I checked
SERPs loaded 2026-10-07 on DuckDuckGo for: overleaf alternative; overleaf alternatives offline; best latex editor mac; best latex editor for mac 2026; best latex editor; best free latex editor for mac; texshop alternative; texshop vs texstudio vs texifier mac; latex editor mac native; offline latex editor mac; overleaf free tier limits alternative; best overleaf alternatives 2026; overleaf alternative offline mac native latex one-time purchase. Each page below was fetched and searched for "moderntex" and "purplelink". ModernTex appears in none of them (0 mentions each).

### 5.2 Where ModernTex and your pages rank (DuckDuckGo, 2026-10-07; Google not checked)
- #1 for "best latex editor for mac 2026", "best latex editor mac" and "best free latex editor for mac": your guide https://purplelink.llc/guides/best-mac-latex-editors/ ("Best LaTeX editor for Mac in 2026: 14 editors compared").
- #3 for "latex editor mac native" (page https://purplelink.llc/moderntex/ title "ModernTex - Native LaTeX Editor for Mac"), behind TexSpark https://texspark.io/ and Texifier https://www.texifier.com/mac ; the guide also appears at #7.
- #1 and #2 for "ModernTex Mac LaTeX editor" (the product page and homepage).
- Not in the top 10 for: "overleaf alternative", "overleaf alternatives offline", "offline latex editor mac", "texshop alternative", "overleaf free tier limits alternative", "latex editor mac" variants beyond "native." The gap queries are exactly the ones you want (Overleaf and TeXShop switchers), and the pages that hold those positions are the ones in 5.3.
- Competitors owning "native Mac LaTeX": TexSpark (https://texspark.io/), Texifier, TeX64 (https://tex64.com/latex-editor, updated 2026-09-16), Folio (https://github.com/bgar324/Folio), Typetex (https://github.com/jonasgunklach/Typetex), Compositor (https://compositorapp.com/).

### 5.3 Third-party mentions of ModernTex found (all as of 2026-10-07)
- https://www.saashub.com/moderntex : listing with your own copy, 0 reviews (VERIFIED).
- https://nav-ai.net/tutorials/how-to-build-and-insert-a-tikz-diagram-with-moderntex : "How to Build and Insert a TikZ Diagram with ModernTex," published 2026-09-16 on the Nav - AI directory, with a linked "ModernTex Review: A Focused LaTeX Workspace for Academic Writing on Mac" entry (VERIFIED page load). Whether you submitted it is not recorded in your outreach files (I grepped Outreach/ and docs/ for "nav-ai" and "saashub"; only SaaSHub is mentioned). If you did not, it is an unsolicited mention and an easy contact.
- https://www.youtube.com/watch?v=wSLfShkNJoY , https://www.youtube.com/watch?v=60PsEnayb0A , https://www.youtube.com/watch?v=EdhGVgJBEl0 (Purplelink channel, yours) and your LinkedIn post https://www.linkedin.com/posts/benampel_i-built-a-latex-editor-for-mac-its-called-activity-7504367171461111808-QX-T (yours).
- https://github.com/egeerardyn/awesome-LaTeX/pull/128 (yours, open).
- NOT a mention: https://linktr.ee/moderntex is an unrelated "moderntex" social account (TikTok/Facebook/Twitch). Do not chase it.
- No independent review, article, or Reddit thread naming ModernTex turned up in any search.

### 5.4 Ranked table. Columns: who runs it, date, ModernTex listed, published route, money signals.
Ranking logic: fit (does the page list Mac or commercial editors, and does it welcome additions), then likelihood (independent operator, recently updated, a real way to reach a human), then discount for pay-to-play. "Date" is the page's own published/updated date; "none shown" means the page exposes none.

| # | Page | Run by | Date | Lists ModernTex | Published way to suggest | Affiliate / money signals | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | https://danmackinlay.name/notebook/latex_editors.html "Editors for LaTeX" | Dan MacKinlay, personal academic notebook (author in page metadata) | none shown | No (lists TeXShop, TeXstudio, Texmaker, Overleaf, VS Code, TeXworks, LyX, Papeeria, Authorea) | https://danmackinlay.name/contact.html says he "welcome[s] cold contacts from strangers" | none seen | Best-fit individual. A short disclosed note is within his stated norms. |
| 2 | https://gauravtiwari.org/latex-editors/ "Best LaTeX Editors for Windows & Mac (2026)" | Gaurav Tiwari, independent blogger | published 2021-12-26, modified 2026-10-03 | No | Contact form https://gauravtiwari.org/contact/ and gaurav@gauravtiwari.org (on the page) | Yes: "reader-supported ... I may earn a small commission." He is monetized, so expect interest in an affiliate or sponsored deal. | Good reach; may ask for payment or affiliate terms. |
| 3 | https://crypticinsight.com/posts/best-offline-latex-alternatives-to-overleaf | Jonathan Cook, personal blog | published 2026-05-28, modified 2026-09-26 | No | Contact form https://crypticinsight.com/posts/contact-us | none stated | The exact query "offline alternatives to Overleaf." Independent and recent. |
| 4 | https://www.guru99.com/best-latex-editors-window-mac.html "14 BEST LaTeX Editor for Mac & Windows in 2026" | Guru99 (author shown: Lucas Bennett); large publisher | updated 2026-08-06 | No | No suggestion form. https://www.guru99.com/contact-us.html says corrections go to writers via their personal pages; advertising offered on the same page | Footer "Affiliate Disclaimer"; ads sold. Likely to ask for money. | High traffic, hard to get in free. |
| 5 | https://fixthephoto.com/best-latex-editor-for-mac.html "5 Best LaTeX Editors for Mac in 2026" | FixThePhoto (author Eva Williams) | none shown | No (lists Texmaker, TeXpad, LyX, Papeeria) | /contact form is a company/role form (https://fixthephoto.com/contact); author email addresses appear in the page markup | "When you purchase through affiliate links ... we may earn a commission." Affiliate-driven. | Likely to want affiliate terms; low trust. |
| 6 | https://techdator.com/best-latex-editors/ | TechDator (author Afar Afrarul Sk) | published and modified 2026-03-26 | No | https://techdator.com/contact/ (address admin@techdator.com in page markup) | none stated | Independent tech blog; mid priority. |
| 7 | https://latex.to/overleaf-alternatives/ | latex.to (a browser LaTeX product; ConTeXt/TeX Live in WASM) | updated 2026-09-05 | No | none found on page | vendor page for its own tool | Competitor-run. Low chance. |
| 8 | https://www.typetex.app/best-latex-editors-2026 (updated 2026-09-09) and https://www.typetex.app/alternatives/overleaf-alternatives (updated 2026-05-07) | TypeTeX (a LaTeX/Typst product) | as shown | No | hello@typetex.dev appears on a sister guide https://www.typetex.app/guides/overleaf-offline-mode-alternative | "rewardful" (affiliate tracker) in the markup; vendor page | Competitor-run. Low. |
| 9 | https://www.useoctree.com/blog/best-latex-editors-mac-comparison | Octree (AI LaTeX editor) | none shown | No (lists TeXShop, Texmaker, Overleaf, VS Code; Octree 19 times) | /contact (https://www.useoctree.com/contact) | vendor page | Competitor-run. Low. |
| 10 | https://inscrive.io/articles/overleaf-alternatives | inscrive.io (product) | updated 2026-10-07 (published 2025-01-31) | No | none found | vendor page | Low. |
| 11 | https://letx.app/compare/overleaf-alternatives-2026/ and https://letx.app/compare/free-latex-editor/ | LetX (product; author Shihab Shahriar Antor) | 2026-07-16 and 2026-09-27 | No | shahriar@letx.app and support@letx.app appear on the pages | vendor page | Low, and it is on awesome-LaTeX itself. |
| 12 | https://papersflow.ai/blog/overleaf-alternatives-2026 ; https://stoicdocs.com/blog/alternatives/overleaf-alternatives/ ; https://trybibby.com/blog/overleaf-alternative-2026 ; https://www.murfy.ai/en/alternatives/overleaf ; https://tex64.com/latex-editor ; https://dev.to/tex64/... (2026-03-29) | AI or SaaS vendors | PapersFlow 2026-02-11; Bibby 2026-03-08; Murfy 2026-05-06; TeX64 2026-09-16 | No | none found | vendor pages | Skip. |
| 13 | https://worldmetrics.org/best/latex-editing-software/ | Worldmetrics (author Tatiana Kuznetsova) | published 2026-06-26, updated 2026-08-27 | No | info@worldmetrics.org on page; https://worldmetrics.org/contact-us/ | "Includes paid placements ... may earn a commission through links on this page." Pay-to-play. | Will ask for money. |
| 14 | https://www.softwaresuggest.com/overleaf/alternatives | SoftwareSuggest (author Supriya Bajaj) | 2026-10-01 | No | support@softwaresuggest.com on the page; page links "Write for Us" and "Lead Partner Program" | says rankings contain no paid placements, but runs a lead-partner program | Vendor listing portal; likely lead-gen. |
| 15 | https://alternativeto.net/software/writelatex/?platform=mac ("Overleaf Alternatives for Mac") and /software/texshop/ | AlternativeTo (27 Kilobyte AB, Stockholm) | n/a | No ModernTex page | Needs login; backlog "usually months"; paid priority | paid fast lane | Worth the free submission; see 3.5. |
| 16 | https://sugggest.com/alternatives-to/texshop | Sugggest | none shown | No | https://sugggest.com/contact ("Software Suggestion" topic) | none seen | Free; low traffic. |
| 17 | https://appmus.com/vs/texmakerx-vs-texshop | AppMus | none shown | No | https://appmus.com/submit (free form) | none seen | Free. |
| 18 | https://medevel.com/10-latex-tex-editors-macos/ | Medevel (author Hamza Musa) | published 2019-08-14, modified 2022-01-06 | No | https://medevel.com/about-contact/ | none stated | Title is "Free and Open-source" only, so ModernTex is out of scope. Skip. |
| 19 | https://techcult.com/best-latex-editors/ ; https://beebom.com/best-latex-editors/ | TechCult (2023-09-19); Beebom (updated 2021-12-27, title "in 2022") | stale | No | contact@beebom.com on the Beebom page | none stated | Stale; skip. |
| 20 | https://www.scijournal.org/articles/best-latex-editors ("25 Best LaTeX Editors") | SciJournal (author SJ Tsai) | none shown | No | https://www.scijournal.org/contact | none seen | Low. |
Also on the SERPs but not worth auditing: Wikipedia's comparison page (see 4.5), SourceForge's TeX/LaTeX Mac directory (Cloudflare-blocked, UNVERIFIED), TeX.SE and r/LaTeX threads, texifier.com, texspark.io.

Reading the table
- Only three independent, human-run, recently updated pages came up (rows 1 to 3), plus Techdator at row 6. Everything else is vendor content marketing, an affiliate site, or a pay-to-play portal.
- Most roundups do not name Texifier or any commercial Mac editor, so ModernTex would fill a gap there rather than displace a competitor.
- You can send each of rows 1 to 3 one short factual note with a link to a page that compares editors (not just the product page). I did not write any copy.

### 5.5 GitHub awesome-lists (all read 2026-10-07)
| List | Stars (last push) | Rules that matter | ModernTex status |
|---|---|---|---|
| egeerardyn/awesome-LaTeX https://github.com/egeerardyn/awesome-LaTeX | 1,672 (2026-08-08) | CONTRIBUTING.md: one item per commit; format `[Name](link) - description.`; add at the bottom of the category; "Self-promotion can be okay, but only if you clearly state your involvement"; "only awesome stuff ... you can personally recommend"; explain why it is on the list | Your PR #128 is open (2026-10-03). The README has a "LaTeX-focused" editors section that already lists Texifier and TeX64 (a Mac-native competitor), so a Mac commercial editor is in scope. Maintainer cadence: merges seen 2026-08-04 and 2026-08-08, 2026-03-10 and 2026-03-22; many PRs open since 2026-08-14 are still unmerged, so expect weeks or months. 10 open issues. Do not chase. |
| jaywcjlove/awesome-mac https://github.com/jaywcjlove/awesome-mac | 115,602 (2026-10-07) | docs/CONTRIBUTING.md: one PR per suggestion, title-case AP style, alphabetical within category, "Annotate your PR"; AI-assisted PRs allowed. Closed-source and paid apps are listed (Texifier is under Reading and Writing Tools, Others). | Not submitted. Merges are fast: recent PRs merged in 0 to 1 days (checked 10 merges, 2026-10-03 to 2026-10-07), though 998 PRs are open. Best-return list in this report. Entries are mirrored in zh, ja and ko READMEs (a repo skill helps). |
| open-saas-directory/awesome-native-macosx-apps https://github.com/open-saas-directory/awesome-native-macosx-apps | 1,623 (2026-10-06) | CONTRIBUTING.md: native only, under about 200MB, HIG, maintained within 2 years; excludes "self-promoted apps (unless truly exceptional)" | ModernTex meets "native" but the self-promoted exclusion is a stated risk. Lower odds. |
| iCHAIT/awesome-macOS https://github.com/iCHAIT/awesome-macOS | 19,293 (2026-08-23) | no CONTRIBUTING.md (404); its README has no LaTeX editor entries | I did not find a rule; many open PRs. UNVERIFIED fit. |
| writing-resources/awesome-scientific-writing https://github.com/writing-resources/awesome-scientific-writing | 1,008 (2026-09-15) | CONTRIBUTING.md: one entry per PR; software entries must be open source, maintained (commit in past 3 years) with at least a one month history; short pitch required | Not eligible (closed source). |
| xiaohanyu/awesome-tikz https://github.com/xiaohanyu/awesome-tikz | 1,810 (2026-07-14) | one link per PR; "generally used, actively maintained, stable, documented, tests" | ModernTex's TikZ designer is a side feature. Poor fit. |
| BibbyAI/Awesome-Latex-Tools https://github.com/BibbyAI/Awesome-Latex-Tools | 0 | vendor-run | Skip. |

---------------------------------------------------------------------------------------------------

## 6. Summary ranking of every venue by fit, risk and cost
1. awesome-mac (PR, free, fast): do first. https://github.com/jaywcjlove/awesome-mac
2. TUG (one email to webmaster@tug.org, commercial vendors section): high authority, no stated COI rule.
3. Mac Apps Library and Bundl.run (free forms; direct downloads accepted).
4. MacUpdate (free, account needed; remove the price from the description).
5. MacRumors "Mac Apps" thread (written developer lane; one thread per app).
6. Dan MacKinlay, crypticinsight.com, gauravtiwari.org (roundup owners with published contact routes).
7. Library guides in 4.1 where TeXShop is listed (UTK, SMCM, Berkeley EPS, NYU, UChicago).
8. AlternativeTo (free submission, months of backlog).
9. Hacker News Show HN (allowed with the trial; expect median-ish results; hand-written text; no friends).
10. Product Hunt (ask for visits and comments, not upvotes; no company account).
11. Mastodon personal posts (scholar.social, mathstodon.xyz, fediscience.org) and the #LaTeX hashtag.
12. TeX.SE: only the community-wiki answer on question 339, with disclosure, and only after rep; high downside. Software Recommendations: not worth it.
Skip: Lobsters (invite-only), Apple Support Communities (forbids ads), CTAN (free software archive), Wikipedia (no article, self-additions reverted within hours), LibHunt (open source), Indie Apps (App Store only), Mac Apps Daily and TryMacApps paid tiers, vendor-written "Overleaf alternatives" pages.
