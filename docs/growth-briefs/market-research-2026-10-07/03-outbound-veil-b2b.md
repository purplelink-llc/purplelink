# Outbound Veil: B2B reach research (2026-10-07)

Research only. Nothing was sent, posted, submitted or changed. All web pages were read on 2026-10-07; "dated" means the source states its own date. Where I could not read a primary source, the claim says so. "Not found" means I looked and did not find it, not that it does not exist.

## 0. Headline

1. The $29.99 on-device Mac app does fill a real gap, but a narrower one than "DLP for small offices". The enterprise tools (Nightfall, Strac, Netskope, Cloudflare, Purview E5) are sold to security teams and are priced per user per year with sales calls. The cheap Mac tools that exist (ClipScrub, Whiteout, HideMyData, Secure Redact) work on documents, clipboards or screenshots, not on text as you type it. The gap is "a warning badge while typing in any app, bought by one person with a card, no IT". That is a thin but real wedge.
2. ClipScrub is the closest competitor and is cheaper per seat for a small office: $29 one time, covers up to 3 Macs, markets to HIPAA/GDPR/CCPA buyers (clipscrub.com). Outbound Veil is $29.99 per Mac. The differentiator is real-time checking in any app, not price.
3. Mac share is the weak point of the current outreach. Evidence found: CPA firms 2.0 percent Mac (2020 survey), professional tax software is Windows only (Aug 2026), solo lawyers 15.5 percent Mac in 2015 ABA data, and therapist Mac share was not found. All 24 organizations contacted so far have unconfirmed Mac use.
4. The email template has two likely CAN-SPAM gaps (no ad disclosure, and an opt-out line that says "ignore this" instead of giving a way to opt out) and one internal contradiction (it promises "I will not write again", which rules out a follow-up). Fix these before the next batch. This is a reading of the FTC guide, not legal advice.
5. Zero replies after less than 48 hours is weak evidence either way. The outreach CSV shows 24 emails sent (15 on 2026-10-06 batch 1, 7 on batch 2, 2 on 2026-10-07 batch 3), not 22, plus 7 form-only organizations not submitted.
6. Price discrepancy to resolve: the site says "$29.99 to keep" with a 14-day refund (https://purplelink.llc/outbound-veil/), while the project CLAUDE.md says "$29". The brief used $29.99, so this report does too.

## 1. Limits of this research

- The session's web-search cap (200 calls) ran out partway through, and fetch safety checks were then rate-limited. The 40-target list therefore leans on directories and sites I could reach, and some segments have zero or one entry (see section 5).
- reddit.com cannot be fetched in this environment, so subreddit rules for r/therapists, r/privacypros, r/Accounting, r/macsysadmin, r/smallbusiness were not read. Secondhand notes are marked.
- Several dollar figures come from search-result summaries of third-party pages (marked "secondary"). Treat those as leads, not quotes.

## 2. Competitors and the gap

| Product | What it is | Price as found | Who it targets | Source (read 2026-10-07) |
|---|---|---|---|---|
| Nightfall AI | Cloud/SaaS and endpoint DLP | Per user per year, dollar amounts not shown publicly; Foundation and Premier editions | "CISO or Director of Security Operations at an organization with 250 to 100,000+ users" | https://www.nightfall.ai/pricing |
| Strac | SaaS, GenAI and endpoint DLP | Custom quote after a 30-minute scoping call; itemized quote "within 24 hours". Secondary sources cite "$10 per user per month" for basic small-business DLP and "$30 to $50 per user annually" for mid-market (conflicting, unverified) | "Enterprises & ScaleUps" | https://www.strac.io/pricing ; secondary: https://www.strac.io/blog/understanding-data-loss-prevention-pricing |
| Microsoft Purview DLP | Built into Microsoft 365 | Secondary sources: Business Premium $264 per user per year; M365 E5 $720 per user per year; E5 Information Protection and Governance add-on $84 per user per year. Mail/SharePoint/OneDrive DLP is in Business Premium, E3, E5; Endpoint DLP and Teams-chat DLP are higher tiers | Organizations already on Microsoft 365 with an admin | secondary: https://blog.ciaops.com/2025/10/page/3/ (Oct 2025), https://o365hq.com/blog/purview-dlp-for-a-50-user-firm-the-first-five-policies-and-what-they-catch . Microsoft's own page timed out; not verified |
| Google Workspace DLP | Gmail, Drive, Chat rules | Not in Business Standard or Business Plus; available in Enterprise Standard and Plus (and some Education editions) | Enterprise Workspace customers with an admin | https://workspaceupdates.googleblog.com/2025/02/gmail-data-loss-prevention-general-availability.html (via search summary, Feb 2025) |
| Cloudflare One / Netskope | Network-level DLP | Cloudflare: free to 50 users, $7 per user per month pay-as-you-go (secondary); Netskope: no list price, secondary median $50 to $98 per user per year | IT/security teams; both are network gateways, not typing-time warnings | secondary: https://underdefense.com/blog/netskope-pricing-guide/ (Jun 3, 2026); https://www.rfp.wiki/it-security/security-service-edge/netskope/cloudflare |
| Grammarly | Writing assistant with a DLP setting | DLP is an Enterprise-plan feature (support page). Grammarly Business $15 per member per month (secondary) | Teams; DLP sanitizes data before it is sent to Grammarly's servers for suggestions, it is not a send-time warning | https://support.grammarly.com/hc/en-us/articles/27458670736525-Enable-Data-Loss-Prevention-DLP ; https://capterra.com/p/170306/Grammarly-Business/ |
| Microsoft Presidio | Open-source PII detection library | Free. License not verified here | Developers building pipelines; not an end-user app | search summaries only (https://github.com/pvcy/presidio) |
| ClipScrub (Mac) | Redacts PHI/PII from text, images and documents; clipboard shortcut | $29 one time, covers up to 3 Macs, macOS 15+, offline key | "healthcare workers, developers, support staff, and organizations managing HIPAA, GDPR, or CCPA" data. Document/clipboard tool, not real-time typing | https://clipscrub.com ; https://github.com/tugboatcoding/clipscrub-core |
| Whiteout (Mac) | Menu-bar app that redacts screenshots | $9.99 one time after a 7-day trial (secondary) | Screenshot sharers | https://feedbagel.com/post/whiteout |
| HideMyData (Mac) | On-device document redaction with OCR | Free, GPL-3.0; Apple silicon only; about 1.5 GB model download | Legal, medical, admin staff handling documents | https://aiindigo.com/tool/hidemydata-1?lang=fr |
| Secure Redact (Mac, iOS, Windows) | Offline pattern-based redaction | Free tier plus Pro; 7-day trial on iOS/macOS; pattern-based so it "may miss" non-standard formats | Developers, security, legal, support | https://klexaroredact.com |
| CleanPII (iOS/Mac) | Offline text PII redaction | $0.99 | Individuals | https://apps.apple.com/app/cleanpii/id6760742759 |
| Browser extensions (Prompt Armour, Blankit, Purify, Paste Redactor) | Local redaction in AI chat boxes | Free tiers; Paste Redactor free plan is 100 redactions per month | People pasting into ChatGPT, Claude, Gemini | search summary of Product Hunt and Opera add-ons pages (e.g. https://addons.opera.com/en/extensions/details/paste-redactor-clipboard-pii-redaction/) |
| SeekerDLP | Endpoint DLP with Mac support, 30-day trial | Price not found | Small organizations | https://alternativeto.net/software/seekerdlp/about |

Who buys the enterprise tools and how: a security or IT owner, through a sales call, annual per-user contracts, often with a minimum. The sources above show this for Nightfall (250+ users) and Strac (quote after a scoping call). Not found: published minimum seat counts for Strac, Cloudflare or Netskope small plans.

### Where the gap is real

- Small offices on Microsoft 365 Business Basic/Standard or Google Workspace Business tiers have no built-in DLP for typed text. Even Business Premium's Purview DLP covers Exchange, SharePoint and OneDrive, and Endpoint DLP is a higher tier (secondary sources above).
- The enterprise products need an admin. A solo therapist or two-lawyer firm will not run a scoping call.
- The Mac redaction apps act on a file, clipboard or screenshot after the fact. A badge while typing, in any app, with a redact-or-ignore choice, is not what ClipScrub, Whiteout, HideMyData or Secure Redact describe.

### Where the gap is thin

- ClipScrub covers 3 Macs for $29 and speaks directly to HIPAA/GDPR buyers. Outbound Veil cannot make compliance claims, so on a feature list a buyer who wants "HIPAA" will pick ClipScrub-style positioning.
- The detection is pattern-based and "will miss some things", as the product page states; so do Secure Redact and every regex tool.
- Many target offices are on Windows (section 3). Outbound Veil needs macOS 14 or later.
- No admin console, managed policy or license server (organizations page). IT-managed offices and Jamf shops will want those.
- Open question I could not answer from the pages: whether the badge works inside browser-based EHRs and web mail fields (SimplePractice is used in a browser). The product page says "any app". A test on SimplePractice, Gmail and Outlook web would settle it and is worth doing before pitching therapists.

## 3. Segments ranked

Size figures are US Bureau of Labor Statistics Occupational Outlook Handbook, 2025 data, read 2026-10-07. Mac share is "not found" unless stated.

| Rank | Segment | Size | Mac share | Buys at $29.99 without IT? | Reachability | Notes |
|---|---|---|---|---|---|---|
| 1 | Solo and small therapy and counseling practices | 533,400 mental health, substance abuse and behavioral counselors (https://www.bls.gov/ooh/community-and-social-service/substance-abuse-behavioral-disorder-and-mental-health-counselors.htm); social workers 816,100 (https://www.bls.gov/ooh/community-and-social-service/social-workers.htm). Share in private practice: not found | Not found | Yes for solos: the owner is the buyer | Medium. Many practices publish a general or contact email; associations are expensive to advertise in (section 4) | They type client names and DOBs into email and notes daily. EHRs such as SimplePractice run in a browser (https://support.simplepractice.com/hc/en-us/articles/40369970657549) so the browser-field test matters |
| 2 | Solo and small law firms, legal aid | 863,700 lawyers, about 11 percent self-employed (https://www.bls.gov/ooh/legal/lawyers.htm) | Highest of the segments with data: ABA survey 2015, 8.1 percent of lawyers used a Mac, 15.5 percent of solos (https://www.attorneyatwork.com/lawyers-who-use-macs/, article dated Feb 24, 2023). A search summary of the ABA TechReport archive cites solos at 21 percent in 2021, but that page returned 403 to me, so it is unverified | Yes for solos and small firms | Medium. Firms publish contact pages; bar associations run member-benefit and CLE sponsorships (prices not found) | Strongest known Mac skew among professional segments |
| 3 | Mac IT consultants and MSPs who serve small healthcare, legal and nonprofit offices | Not found | 100 percent by definition | The consultant decides, not the end office | High for a small list: Mac MSPs publish general emails (7 in the CSV) | Indirect channel. They need deployment tooling Outbound Veil lacks (no admin console). Best used as test sites and referral partners |
| 4 | Nonprofits: immigration, refugee, domestic violence, family services | Not found | Not found | Often yes, but small budgets; an executive director decides | High: most publish an info@ address (11 in the CSV) | Where the first 24 emails went. Good for goodwill and case studies, weak for revenue per seat |
| 5 | Independent insurance agencies and fee-only financial planners | Not found | Not found | Yes for owner-operators | Medium | SSNs, DOBs, account numbers in email. Windows-heavy industry software is likely but I did not find data |
| 6 | HR consultancies and PEO-type firms | Not found | Not found | Yes for small consultancies | Medium | Employee SSNs and leave details |
| 7 | Freelance journalists and small newsrooms | Not found | Not found | Yes | Low via associations, not researched further | Source protection is a fit story but the tool detects PII patterns, not source identities, so the claim would be weak |
| 8 | Schools and universities (IRB, registrar, counseling) | Not found | Not found | No: campus purchase usually needs IT review | Low. IRB offices publish mailboxes, but cycles are slow | Already tried with 4 campus mailboxes |
| 9 | CPA firms and bookkeepers | 1,595,200 accountants and auditors, about 5 percent self-employed (https://www.bls.gov/ooh/business-and-financial/accountants-and-auditors.htm) | 2.0 percent of CPA firms used Mac OS (Accounting Firm Operations and Technology Survey, published Nov 29, 2020: https://cpatrendlines.com/2020/11/29/survey-firm-size-matters-in-tax-software-choice). Drake, Lacerte, ProSeries and UltraTax CS are Windows only; Mac staff use a hosted Windows desktop; QuickBooks Desktop for Mac 2024 is the last version, supported to Sept 30, 2027 (https://verito.com/blog/mac-and-windows-tax-software/, Aug 3, 2026) | Yes for owners, but few have Macs for client work | Low yield | Deprioritize. Only cloud-only, Mac-based CPA firms are viable, and I found none with a published email |
| 10 | Real estate and mortgage brokers, customer support teams | Not found | Not found | Support teams: no, tooling is bought centrally | Low | No evidence gathered; leave out until the top segments show traction |

Mac share, broader context (all secondary or enterprise-skewed): Omdia reported Apple at 11 percent of the US enterprise PC market in 2025, up 2.4 points from 2024, and 16 percent across all segments (Computerworld, Apr 7, 2026, https://www.computerworld.com/article/4154950/apples-mac-grabs-11-of-us-enterprise-market-share.html). A figure of 27 percent for SME Mac endpoints in 2026 circulates in search summaries; the page I checked (https://axis-intelligence.com/mac-vs-windows-market-share/) does not contain it, so I do not rely on it. A Parallels survey claim that 55 percent of SMBs are "Mac-friendly" is also from a search summary of unknown date.

Trade associations and directories that publish member lists with email routes: not found for any segment. I did not look for individual-member directories, and I would not mail individuals from them. State bar and state counseling association member-benefit pages were not reached.

## 4. Channels

### 4.1 Where individual buyers are (best fit for a $29.99 price)

| Channel | Rule or price, with source | Audience | Cost | Fit |
|---|---|---|---|---|
| Product Hunt | Free; "100% free to use"; company accounts prohibited; you may not ask for upvotes, only visits and comments (https://www.producthunt.com/launch) | Tech-leaning early adopters, not therapists | Free | Good for a launch spike and backlinks |
| Show HN (Hacker News) | Must be something people can try, "ideally without barriers such as signups or emails"; asking friends to upvote is not allowed (https://news.ycombinator.com/showhn.html) | Developers, privacy-minded | Free | The 7-day trial qualifies. Audience is not the target offices |
| AlternativeTo | Free submission through an email-verified account; optional one-time $5 priority review of 1 to 2 business days (https://alternativeto.net/faq) | People searching for alternatives to named products | $0 or $5 | List it as an alternative to Nightfall, Strac, ClipScrub-style tools |
| MacUpdate | Free Add App form; guest posts and sponsored articles pitched by email, no price published (https://www.macupdate.com/write-for-us) | Mac users | Free | Easy listing |
| Privacy Guides | Developers must self-submit in the forum's Project Showcase, disclose affiliation, define a threat model; "Open-source projects are generally preferred"; no payment or affiliate links (https://www.privacyguides.org/en/about/criteria/) | Privacy-focused | Free | Weak fit, closed-source. r/privacy reportedly does not allow self-promotion unless the tool is listed on privacyguides.org (secondhand, unverified) |
| TechGDPR Privacy Tech Directory | Free; email to add a tool; lists paid tools with price (https://techgdpr.com/privacy-tech-directory/) | Privacy and compliance professionals | Free | Reasonable, the audience is the buyer type |
| Vucense Privacy Tools Directory | Free editorial form; says listings are not sold (https://vucense.com/tools/apply/) | Privacy-minded | Free | Cheap to try |
| Reddit (r/therapists, r/privacypros, r/Accounting, r/macsysadmin, r/smallbusiness) | Rules not retrievable. Secondhand: r/therapy states it is against the rules to post promotions; most subreddits expect disclosure of affiliation and a 90/10 participation ratio (https://redship.io/blog/reddit-self-promotion-rules-2026) | Large | Free | Do not post a pitch. Answer questions with disclosure only where the subreddit rules allow it, after reading them |
| Facebook solo-practitioner groups, SimplePractice and TherapyNotes communities | Not found / not researched | Not found | Not found | Join as a member and read pinned rules before any mention |

### 4.2 Paid media and sponsorships (prices published where found)

| Channel | Published price or rule | Audience figure | Source |
|---|---|---|---|
| Six Colors | $750 per week: text ad on every page for a week, a sponsor-authored post in the RSS feed, a thank-you post; no paid guest articles | About 20,000 RSS readers per the page | https://sixcolors.com/sponsorship/ |
| MacRumors | Weekly newsletter sponsorship via form; no rate shown; the form asks for budgets starting at $1,000 to $5,000 | Not found | https://www.macrumors.com/contact.php |
| MacStories | Weekly homepage and podcast sponsorships, rates by request; no paid reviews | Not found | https://www.macstories.net/advertise/ |
| Daring Fireball | $12,000 per week (reported by my research helper from the sponsor page; I did not re-verify) | Not found | not re-verified |
| NASW (social workers) | 2024 media kit: digital $1,200 to $5,000 per month by placement; podcast spot $300 to $550, episode sponsorship $895; print $550 to $8,200; conference exhibit booths $1,300 to $1,500 (2018 exhibitor page, secondary) | 107,000+ members; 600,000+ monthly web visitors | https://www.socialworkers.org/Advertise/Media-Kit-Text |
| ACA (counselors) | From a search summary of the ACA media kit: interior web ad $1,000 per month, premium $2,000 per month, banners $1,000 to $3,000, sponsored content $4,000 per month, Strategic Partner Network from $25,000 per year. The PDF is an image and I could not read it, so these figures are unverified | "More than 60,000 members" (https://www.counseling.org/publications/counseling-today-magazine) | https://counseling.org/docs/default-source/default-document-library/aca-media-kit.pdf |
| APA, AAMFT, ABA TECHSHOW, state bars, AICPA | Not found (APA page empty, AAMFT 404, ABA 403) | Not found | n/a |

Whether any association accepts "member-benefit deals" or free vendor listings: not found. The published pages I could read are paid advertising rate cards. A $29.99 product cannot repay $1,000 to $4,000 a month placements without a conversion rate, which is not yet known.

### 4.3 Mac admin and reseller channels

- MacAdmins Slack: run by the Mac Admins Foundation, a 501(c)(3). The Code of Conduct prohibits "overly sales/advertising/spam" messages and posting the same message in multiple channels; separate Vendor Guidelines and a Vendor Policy exist but I could not read them (https://github.com/macadminsdotorg/codeofconduct ; https://macadmins.org/community/slack/). Member count not found. Audience is IT admins, who will ask about MDM, configuration profiles and a license server that do not exist yet.
- Jamf Nation (now https://community.jamf.com/): rules not read (rate-limited). r/macsysadmin: not read.
- Mac MSPs: 7 firms in the CSV, each publishing a general address or contact page. Treat them as one-to-one conversations, not a mass mailing.
- Setapp: 75 percent developer share on one-time purchases, 25 percent to Setapp; requires SDK integration and technical review (https://setapp.com/developers). Ben has already applied for ModernTex (OUTREACH-LOG.md), so this is not a new target.
- Compliance blogs (HIPAA Journal and similar): advertise page returned 404; not found.

### 4.4 What to try first

Free, low-risk, aligned with the brand: AlternativeTo, MacUpdate, TechGDPR, Vucense, a Product Hunt launch, and a Show HN with the trial link. Then one-to-one conversations with 3 to 5 Mac MSPs. Hold paid sponsorships until a free channel shows a measurable trial-to-paid rate.

## 5. The 40 new targets

File: 03-outbound-veil-new-targets.csv (same folder). 40 rows, none already in Outreach/outbound-veil-orgs.csv (checked on route and name). Columns: segment, organization, city_state, route, route_type, source_url, fit_reason.

- Route types: 29 email, 7 form, 4 contact-page. Rows marked form or contact-page need the web form, not Mail. Per the existing rule, form submissions need Ben's approval.
- Mix: 9 listing sites or newsletters; 7 Mac IT consultants; 24 organizations (therapy 3, clinics 3, nonprofits 11, legal aid 1, insurance 2, financial planners 2, HR 2). Metros outside Atlanta: Seattle, Austin, Minneapolis, Phoenix, Raleigh, Philadelphia, Pittsburgh, Nashville, Columbus, Denver, Salt Lake City, Tucson, Portland, Washington DC, Cleveland, Buffalo, Chicago, New Haven, Los Angeles (19). Atlanta-area rows: Decatur, Atlanta, Kennesaw, Roswell, Clarkston.
- Every organization row was read from the organization's own site by a research helper. I re-checked four rows (Seattle Anxiety Specialists, PADV, MacWorks, Six Colors) and found all matches; MacWorks's fit reason was corrected (law-firm testimonials, no medical clients seen). I fetched and added three Atlanta-area rows myself (Raksha, Friends of Refugees, New American Pathways).
- Mac use is unconfirmed on every organization row. Only the MSP rows are Mac by definition.
- Gaps caused by the search cap: zero CPA, bookkeeper, mortgage, real estate, small law firm, campus or journalism rows; one legal-aid row; the Atlanta Mac MSP list has one entry. Fewer than 4 therapy practices. A second pass with search available should fill these.
- Judgment calls: Physicians' Care Clinic lists a Gmail address as its published route; Urban Ministries of Wake County and New American Pathways are larger than the typical target; the Utah Domestic Violence Coalition address is listed for business inquiries; Privacy Guides is included as a listing site though open source is preferred.

## 6. Why the first emails may not have worked, and what to change

These are hypotheses. I have no reply, bounce or open data.

1. Too early to judge. All 24 sends are dated 2026-10-06 or 2026-10-07. Not found: a sourced benchmark for cold-email reply rates in these segments.
2. Role inboxes. info@ and frontdesk@ addresses are read by front-desk staff, not the person who buys software.
3. Mac use unconfirmed everywhere. Recipients who are on Windows have nothing to reply to. CPA rows were the lowest-fit segment by the data above.
4. The ask is heavy. Draft A asks the recipient to count Macs and wait for a quote, with no price, while a $29.99 trial needs no conversation. A team quote is a procurement step for a $30 product.
5. The call to action leads to an organization page and not a download, and the email says "ignore this", which tells the reader that ignoring is the correct response.
6. Trial downloads of zero may be a real zero or a measurement gap. Confirm that the trial link on /outbound-veil/ is counted by a first-party function, then test with one download.
7. Deliverability is unknown. Sent from Mail with ben@purplelink.llc; whether SPF, DKIM and DMARC pass for purplelink.llc was not checked. A test send to a Gmail and an Outlook mailbox would show the headers.
8. Compliance-minded recipients (clinics, legal aid) may need something to hand to a board or IT person. A one-page "what it does and does not do" PDF is already offered only to campus offices in Draft C.

### 6.1 CAN-SPAM, what the FTC guide requires

Source: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business (read 2026-10-07; page date not shown). Summary of the points that matter here:

- The law "makes no exception for business-to-business email". Each violating email can carry penalties of up to $53,088.
- Header and routing information must be accurate, and the subject line must not mislead.
- You must "disclose clearly and conspicuously that your message is an advertisement".
- Include a valid physical postal address (the signature has one).
- Tell recipients how to opt out: "a return email address or another easy Internet-based way". The mechanism must work for at least 30 days after sending.
- Honor an opt-out within 10 business days. You cannot charge a fee or require more than an email address, and you cannot sell or transfer the address.
- You remain responsible if someone else sends on your behalf.

Gaps in the current text (Draft A, outbound-veil-organizations-2026-10-06.md; SKILL.md step 5):

- No advertisement disclosure.
- "If this is not relevant, ignore this and I will not write again" does not tell the reader how to opt out. Replying to ben@purplelink.llc would work as a return address, but the text should say so.
- The same sentence promises no further contact, so a follow-up to non-repliers would contradict it.

Suggested footer for all new emails (no em dashes):

> This is a commercial email from Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350, USA. Reply "no thanks" and I will not email you again.

### 6.2 Follow-up cadence

- Day 0: first email, with the footer above and the line "I will send one short follow-up next week if I do not hear from you."
- Day 7 to 10: one follow-up, two sentences, to non-repliers only. Subject "Re: " plus the original subject is acceptable only if the original thread exists; do not fake a thread.
- After that, stop. Mark the organization "no response" and leave it for at least 6 months.
- Any opt-out, hostile reply or complaint: add to the suppression list the same day, even though the law allows 10 business days. Keep the list in Outreach/outbound-veil-orgs.csv with status do-not-contact.
- Keep the existing safeguard: send nothing on a day with 2 or more bounces or any complaint.
- Update SKILL.md only with Ben's approval. This report does not change it.

### 6.3 Proposed first-contact emails (two per top segment)

All use the footer from 6.1. No compliance claims, no emojis, no em dashes. The statements about the app match https://purplelink.llc/outbound-veil/.

**Segment 1: therapy and counseling practices**

Version T1 (question first)
Subject: Do client names ever end up in the wrong email?

Hello,

I am Ben Ampel. I make Outbound Veil, a Mac menu-bar app that checks what you type, in any app, for names, dates of birth, Social Security numbers, card numbers and medical identifiers. A badge shows the count before you press send, and you can redact or ignore each finding.

It runs on the Mac. Nothing you type is stored or sent, and the app has no analytics. It will miss some things, it will flag some things that are fine, and it does not make a practice compliant with any regulation.

It costs $29.99 per Mac, once, with a free 7-day trial: https://purplelink.llc/outbound-veil/?utm_source=email&utm_medium=cold&utm_campaign=ov-2610&utm_content=therapy-t1

Do you use a Mac for client notes and email? A one-line answer helps me, even if it is no.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

Version T2 (free pilot)
Subject: Trying a typing check for client details, free for 30 days

Hello,

I am looking for ten small practices to try Outbound Veil for 30 days at no cost and tell me what it gets wrong. It is a Mac menu-bar app that flags names, dates of birth, Social Security and card numbers and medical identifiers as you type, before you send. It runs on the Mac, stores nothing, sends nothing and has no analytics.

In return I would ask for a short call or a few written lines at the end: what it caught, what it missed, what annoyed you. If you want to keep it, it is $29.99 per Mac, once. If not, you owe nothing.

Reply "pilot" with the number of Macs (up to 3) and I will send the licence details. It will not make a practice compliant with anything, and I will say so again on the call.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

**Segment 2: solo and small law firms and legal aid**

Version L1 (specific moment)
Subject: A check before a client's date of birth goes in the wrong email

Hello,

I am Ben Ampel. I make Outbound Veil, a Mac menu-bar app. As you type in any app, it checks for names, dates of birth, Social Security numbers, passport and driver's license numbers and card numbers, and shows a badge before you send. You choose to redact or ignore each one.

The checking happens on your Mac. Nothing is stored or sent. It does not replace your own review of an attachment or a recipient line, and it will miss some things.

$29.99 per Mac, once, free 7-day trial: https://purplelink.llc/outbound-veil/?utm_source=email&utm_medium=cold&utm_campaign=ov-2610&utm_content=law-l1

Is your office on Macs? If it is not, I will not write again.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

Version L2 (research ask)
Subject: Two questions about how your office handles client identifiers

Hello,

I make a small Mac app called Outbound Veil that flags personal information as you type. Before I spend more time on law offices, I would like to ask two things: do your staff use Macs, and has a client identifier ever gone into an email or a filing where it did not belong?

If you reply with even a sentence on either, I will send a free 30-day licence for up to 3 Macs, no payment details needed. The app runs on the Mac, stores nothing, sends nothing and has no analytics. It will miss some things and does not make anyone compliant with a rule.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

**Segment 3: Mac IT consultants and MSPs**

Version M1 (test on one client Mac)
Subject: A small Mac utility for your law and healthcare clients

Hello,

You support Mac offices that handle client records, so you see the mistakes a typing check might catch. I make Outbound Veil, a Mac menu-bar app that flags names, dates of birth, Social Security and card numbers and medical identifiers as someone types, in any app. It runs on the Mac, stores nothing, sends nothing, and has no analytics.

I am not asking you to recommend it. I am asking whether you would put it on one client or test Mac for a week and tell me where it fails: fields it cannot read, apps that conflict, false alarms. There is a free 7-day trial, and I can extend it for you.

You should know the limits now: macOS 14 or later, no admin console, no managed policy and no licence server. Each person installs it and enters a key.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

Version M2 (partner terms)
Subject: Would a partner price make this worth your time?

Hello,

Outbound Veil is a $29.99-per-Mac menu-bar app that flags personal information as someone types. Offices ask IT consultants what to use for this, so I would like to hear what terms would make it worth your time to recommend or resell it: a partner price on packs, an invoice per client, or something else.

I do not have a console or MDM profile yet, and I would rather learn now whether that blocks you. If you tell me what you would need, I will tell you honestly whether I can build it.

Trial and details: https://purplelink.llc/outbound-veil/organizations/?utm_source=email&utm_medium=cold&utm_campaign=ov-2610&utm_content=msp-m2

Ben Ampel
Purplelink LLC
ben@purplelink.llc

**Segment 4: nonprofits (immigration, refugee, domestic violence, family services)**

Version N1
Subject: A typing check for client details, from a one-person Mac studio

Hello,

I am Ben Ampel in Atlanta. I make Outbound Veil, a Mac menu-bar app that checks what staff type, in any app, for names, dates of birth, Social Security numbers and similar identifiers, and shows a badge before they send. It runs on the Mac, stores nothing, sends nothing and has no analytics. It will miss some things and does not make anyone compliant with a regulation.

If your staff use Macs, a 7-day trial is here: https://purplelink.llc/outbound-veil/organizations/?utm_source=email&utm_medium=cold&utm_campaign=ov-2610&utm_content=nonprofit-n1 . Pricing is $29.99 per Mac, once.

Does your staff use Macs?

Ben Ampel
Purplelink LLC
ben@purplelink.llc

Version N2 (free licences)
Subject: Free licences for a small nonprofit pilot

Hello,

I am offering free licences for Outbound Veil, up to 5 Macs, to a few small nonprofits for 90 days. It is a Mac menu-bar app that flags personal information as staff type, before they send. It stores nothing, sends nothing and has no analytics.

I would ask for a short note at the end on what it caught, what it missed and whether staff kept it on. After 90 days it is $29.99 per Mac, once, or you stop using it and owe nothing.

Reply "pilot" with the number of Macs and I will send the details.

Ben Ampel
Purplelink LLC
ben@purplelink.llc

Ben decides whether free pilot licences are acceptable; none of this has been offered.

### 6.4 Offer worth testing

- Free pilot: 30 days (practices, law) or 90 days (nonprofits), up to 3 to 5 Macs, in exchange for a short call or written feedback. Needs a way to issue an extended trial key; whether the licensing supports that was not checked.
- Per-seat price: $29.99 per Mac. Because ClipScrub covers 3 Macs for $29, a small-office test pack (for example 3 Macs for a single price) would remove the obvious comparison. The figure is Ben's decision; I am not proposing a number I cannot justify.
- Partner terms for MSPs: ask what they need, as in M2, before setting a discount.

### 6.5 Measuring replies and trial downloads

- One landing path per segment and variant (for example /outbound-veil/for/therapists/ with its own copy), so any first-party analytics separates them even if query strings are stripped. UTM parameters on the link as a backup: utm_source=email, utm_medium=cold, utm_campaign=ov-2610, utm_content=segment-variant. I did not verify how Cloudflare Web Analytics, the cookieless tool named in PRODUCT.md, reports UTM parameters, so test one tagged click first.
- Count trial downloads in a first-party Netlify function, logging a timestamp and the campaign tag only. No email address, no IP.
- Reply tracking: add columns to Outreach/outbound-veil-orgs.csv: variant, sent_date, followup_date, reply_date, reply_type (positive, negative, opt-out, question, bounce), trial_started (yes or unknown), sold. Reply rate is replies divided by delivered, excluding bounces.
- Sample size warning: with about 25 emails per variant, one extra reply moves the rate by 4 points. Judge each variant on the content of replies and on whether any trial or sale follows, not on percentages. Alternate variants within each segment so timing does not bias the comparison.
- Before the next batch, send a test to one Gmail and one Outlook address you control and check the headers for SPF, DKIM and DMARC results.

## 7. Not found, for the record

- Mac share for therapists, social workers, insurance, HR, real estate, journalists and nonprofits.
- Subreddit rules (Reddit not fetchable here); Facebook group rules; SimplePractice or TherapyNotes community rules.
- Published prices for ABA TECHSHOW, state bar sponsorships, APA, AAMFT, AICPA, HIPAA Journal advertising.
- Whether any association offers a member-benefit deal to a small Mac vendor.
- Jamf Nation and MacAdmins vendor policy text.
- A sourced cold-email reply benchmark for these segments.
- Microsoft's and Cloudflare's own current price pages (secondary sources used).

## 8. Source list (read 2026-10-07)

purplelink.llc/outbound-veil/ and /organizations/; nightfall.ai/pricing; strac.io/pricing; blog.ciaops.com; o365hq.com; workspaceupdates.googleblog.com; support.grammarly.com; clipscrub.com; github.com/tugboatcoding/clipscrub-core; klexaroredact.com; feedbagel.com/post/whiteout; aiindigo.com (HideMyData); apps.apple.com (CleanPII); bls.gov OOH (counselors, lawyers, accountants, social workers; 2025 data); cpatrendlines.com (Nov 29, 2020); verito.com (Aug 3, 2026); attorneyatwork.com (Feb 24, 2023); computerworld.com (Apr 7, 2026); producthunt.com/launch; news.ycombinator.com/showhn.html; alternativeto.net/faq; macupdate.com/write-for-us; privacyguides.org/en/about/criteria; techgdpr.com; vucense.com; sixcolors.com/sponsorship; macrumors.com/contact.php; macstories.net/advertise; socialworkers.org/Advertise/Media-Kit-Text; counseling.org; setapp.com/developers; macadmins.org and github.com/macadminsdotorg/codeofconduct; ftc.gov CAN-SPAM guide.
