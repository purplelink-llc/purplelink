# Plan without advertising (2026-10-07)

Source reports in this folder: 01-ad-spend (parked), 03-outbound-veil-b2b, plus the ModernTex and consumer-app findings the research helpers saved under the session scratchpad. Nothing here has been sent or submitted. Every outward action waits for approval.

## What the numbers say

- ModernTex converts: 54 trial downloads became 8 paid orders. The constraint is how many people see it.
- Outbound Veil, Legroom, Keyfeel and Vitae each get single digits of product-page views a month.
- Search brings 86% of referred visits, and the new guides are not in Search Console's top pages yet, so search will lag. Direct reach (listings, outreach, communities) is faster.

## Rules learned from the research (do not break)

- r/PhD bans tools that have a free trial or free tier. Never mention ModernTex there.
- r/macapps allows one promotion per developer in 30 days. The 09-29 App Pile comment may count, so the next one is not before 10-29.
- r/LaTeX has an AI-content rule and developer-editor posts there mostly score 0. Reply to questions, disclose, never post a launch.
- r/postdoc, r/labrats and r/AcademicPhilosophy remove tool promotion.
- Cold email: every message says it is an ad and gives a clear opt-out (the daily Outbound Veil task now does). One follow-up at most.
- Mac use is rare among CPA firms (2.0% in a 2020 survey), so CPAs are paused for Outbound Veil.

## Wave 1: this week, free

### A. Directory and listing submissions

| Where | Product | Route | Who acts |
|---|---|---|---|
| TUG "TeX Resources on the Web" | ModernTex | email webmaster@tug.org (page says additions are welcome) | I send with approval |
| TechGDPR privacy tech directory | Outbound Veil | email to add a tool (techgdpr.com/privacy-tech-directory) | I send with approval |
| MacUpdate "Add App" | ModernTex, Outbound Veil, Legroom, Keyfeel | web form, needs an account | Ben (account creation is yours) |
| AlternativeTo | all four | email-verified account, optional $5 priority review | Ben |
| Vucense tools directory | Outbound Veil | editorial form | Ben, I supply the text |
| Indie App Catalog | all Mac apps | free web form | Ben, I supply the text |
| OnTheHub vendor form | ModernTex | web form with CAPTCHA | Ben |
| awesome-mac (GitHub) | ModernTex (lists TeXstudio and Texifier, not ModernTex) | pull request | Ben decides, I prepare the line |
| iTechGuides LaTeX roundup (updated 2026-10-07) | ModernTex | pitch via their published contact | I draft, Ben approves |

I will write the exact listing text for each (name, one-line description, price, trial, link with a utm_source tag) and put them in one file so form submissions are copy and paste.

### B. ModernTex to universities (10 emails, one each)

Priority 1 (role addresses, an editor gap on the page):
1. Georgia Tech Graduate Studies, thesis@grad.gatech.edu. Page lists Texmaker and MiKTeX only.
2. UW-Madison Libraries, libraries@wisc.edu. Guide has no TeXShop and no native Mac editor.
3. University of Akron Libraries, librarians@uakron2.libanswers.com. Guide names no editors.
4. St. Mary's College of Maryland Library, ask@smcm.libanswers.com. Guide lists TeXShop and Texmaker for Mac and already mentions a paid editor's price.
5. Purdue Graduate School, thesishelp@purdue.edu. Framed as a question about offline LaTeX for controlled-content theses, not a pitch.

Priority 2: Reed College IT (cus@reed.edu), UMaine Graduate Student Government (gsg@maine.edu), UTK OIT help desk, LSU Math (dept@math.lsu.edu), Texas Tech Libraries guide contacts.

Verify each address on its own live page before sending (the research read pages through a summarizer). Expect "we do not endorse software" from some; that is fine.

Draft (change only the one sentence in brackets):

> Subject: A native Mac LaTeX editor for your thesis resources
>
> Hello,
>
> I am Ben Ampel, the developer of ModernTex, a LaTeX editor made for the Mac. It handles multi-file projects, keeps a synced PDF preview beside the source (Command-click in the PDF jumps to the line), completes BibTeX keys, works offline, and keeps your work in ordinary .tex files. It is $19.99 once, with a free 7-day trial, and runs on Apple silicon and Intel Macs.
>
> [One sentence about their page, for example: Your LaTeX guide lists TeXShop and Texmaker for Mac; I would be glad for ModernTex to be considered for that list.]
>
> If you do not list commercial software, I understand. The product page is https://purplelink.llc/moderntex/?utm_source=email&utm_medium=outreach&utm_campaign=mtx-edu
>
> Ben Ampel
> Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350
> ben@purplelink.llc
>
> This is a one-time commercial message from Purplelink LLC. Reply "no thanks" and I will not email you again.

### C. Outbound Veil (already running, retargeted)

The daily task now: uses the 40 new targets first, favors therapy practices, solo law firms and legal aid, nonprofits and clinics, pauses CPAs and campus offices, uses the T1 and L1 templates, tags links per segment, and sends one follow-up after 7 to 10 days. It still sends nothing on a day with two or more bounces or any complaint.

Not changed: the free-pilot offer (T2) needs a way to issue extended trial keys. If you want it, I add that to the license server first.

### D. Reddit and forums (no new promotional posts yet)

- Your r/LaTeX post from about 10-03 still says "$10" and "1.0.2". A reply under it with the current price and version fixes that for the person who asked. I draft it, you approve.
- Three threads in the research window fit a disclosed reply (a Mac M1 editor question, the TeXstudio Homebrew cask disabled on 09-01, an Overleaf timeout thread), but they are 2 to 3 weeks old. I would reply only if they are still active.
- Please paste the r/LaTeX sidebar rules from your own browser. Reddit blocked the research from reading them.

### E. Your launches

- Show HN for ModernTex (the 7-day trial qualifies). Needs your account and a weekday morning US time; I draft the post and first comment.
- Product Hunt for Outbound Veil or Keyfeel, no company account, no upvote requests.
- r/macapps App Pile: not before 10-29.

## Wave 2: next week

- Wait for the consumer-app research (Legroom, Keyfeel, Vitae outlets and creators) and the full ModernTex community report, then add their targets.
- Email the 18 past customers once about the Suite ($54.99) with an opt-out. Needs your approval of the text.
- Make the optional trial-download email capture more visible, so there is a list to write to.

## How we will know

Every link carries utm_source, utm_medium and utm_campaign. The dashboard now prints a funnel per first-touch channel (page views, trial downloads, buy clicks) and counts attributed orders, so each batch can be judged by trials it produced, not by opens.
