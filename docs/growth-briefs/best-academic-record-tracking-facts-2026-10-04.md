# Fact table: best software for tracking your research record

Checked 2026-10-04 for `site/guides/best-academic-record-tracking-software/index.html`. Method: `competitive-landscape-research`.
Tiers: 1 = vendor's own page, store listing, project repo, or the regulator's own notice; 2 = named independent source;
3 = aggregator or search summary (never stated flatly in the article).

Reading notes:

- WebFetch returns a model-written summary of a page, not the page. Rows marked "fetch summary" were read that way; the article words them conservatively.
- Rows marked "search excerpt" rest on a search-result excerpt of the named vendor page because the page itself returned an error to automated fetches.
- `researchgate.net`, `academia.edu`, `clarivate.com` (WoS Reviewer Recognition, ScholarOne), `support.orcid.org`: HTTP 403 to fetches. `symplectic.co.uk/elements/` returned a corrupt image; `/products/symplectic-elements/` worked. `auctorium.app` returned a GitHub Pages 404 (site gone or moved); the App Store listing was read through Apple's iTunes Search API instead.
- Prices read on the vendor page on 2026-10-04 unless a row says otherwise. Enterprise systems publish no price; the article says "no public price" only where the vendor page says to contact sales or request a demo.

## Vitae (Purplelink, own product)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Version and status | v1.0.1, page badge says "Beta" | 1 | `site/vitae/index.html`, `site/vitae/version.json` | 2026-10-04 | `site/guides/track-academic-cv-tenure-case/` still says "0.4 beta" (stale; not edited beyond the requested link) |
| Price | Free, no account, no limits on the record | 1 | `site/vitae/index.html` | 2026-10-04 | none |
| Platform | macOS 15 Sequoia or later; Mac only | 1 | same (FAQ) | 2026-10-04 | none |
| Data location | On the Mac, SwiftData; no account; no sync; "iCloud sync is supported in the schema and can be enabled in future versions" | 1 | same (FAQ) | 2026-10-04 | none |
| iPhone/iPad/web | Existing guide says "no iPad, iPhone or web version and no sync between machines yet"; the Vitae page lists none | 1 | `site/guides/track-academic-cv-tenure-case/index.html`, `site/suite/index.html` ("no Windows or iPhone version") | 2026-10-04 | none |
| Multi-user / collaboration | Page describes tracking coauthors and collaborators as records; nothing about shared or multi-user editing; with local storage and no sync it is single-user. Article words it as "I found nothing describing shared editing" | 1 (absence) | `site/vitae/index.html` | 2026-10-04 | none |
| Submission tracking | Status, dates, each review round, decision; target venues; acceptance rates for about 13,700 journals and conferences; timeline forecast from own history | 1 | same | 2026-10-04 | none |
| Grants | NSF, NIH and others, planning to award, deadlines, requested and awarded amounts, reporting dates, your share; Grants.gov search | 1 | same | 2026-10-04 | none |
| Award auto-fill, RIS export, Publish or Perish import | NSF and NIH award auto-fill from award number; RIS export for Interfolio, Watermark and reference managers; Publish or Perish import for Google Scholar counts | 1 | `site/changelog/index.html` (Vitae 1.0) | 2026-10-04 | not on the Vitae page itself |
| CV import | From Word, PDF, RTF, ODT or a web page; APA, Chicago, MLA, IEEE, ACM, Harvard, Vancouver; review before saving | 1 | `site/vitae/index.html` | 2026-10-04 | none |
| CV export | Seven CV formats or your own; export several at once to PDF, LaTeX, or rich text that opens in Word; .docx templates are Plus | 1 | same | 2026-10-04 | **Conflict:** Plus page lists free exports as "PDF, rich text and Markdown" (no LaTeX). Article states PDF, LaTeX and rich text (Vitae page) and does not mention Markdown |
| Inbox triage | iCloud, Gmail, Outlook, Yahoo, Fastmail or university mail, read-only; recognizes journal-system messages and proposes updates; you review each | 1 | same | 2026-10-04 | none |
| Tenure view | Your own expectations vs your record: articles, lead-author papers, funding, h-index, invited talks, service | 1 | same | 2026-10-04 | none |
| Zotero | Send any publication to Zotero in one click | 1 | same | 2026-10-04 | none |
| Backups/undo | Daily backup, undo; 30-day Recently Deleted | 1 | same; changelog | 2026-10-04 | none |
| Plus price | $3 a month or $24 a year, 7-day free trial | 1 | `site/vitae/plus/index.html` | 2026-10-04 | none |
| Plus features | NIH biosketch draft, Current and Pending report, AACSB summary, progress report, personal website; Word export with own templates; revision workspace (splits decision letter into reviewer points, exports response letter); Shareables; collaboration map and research profile; batch DOI lookup and ORCID sync (daily); Reminders and calendar sync; themes | 1 | same | 2026-10-04 | none |
| Free (stays free) | Submissions and review rounds, grants, projects, collaborators, teaching, service, mentoring, tenure view, inbox triage, citation counts, CV and package exports, backups, updates | 1 | same | 2026-10-04 | none |
| Mac Suite | $39 once; ModernTex, Outbound Veil and Vitae Plus for life | 1 | `site/suite/index.html` | 2026-10-04 | none |
| Does not submit to Interfolio or Watermark | Export and upload | 1 | `site/vitae/index.html` FAQ ("you still submit there, using what Vitae exports") | 2026-10-04 | none |

## Purplelink spreadsheets (own products)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Submission & R&R Tracker | $12 one-time, .xlsx for Excel and Google Sheets; tabs Start Here, Dashboard, Submissions, R&R Responses, Journals, Settings; 150 submission rounds, 400 reviewer comments; days in review, overdue and nudge flags | 1 | `site/sheets/submission-tracker/index.html` | 2026-10-04 | none |
| Tenure & Promotion Dossier Tracker | $12; five logs (publications, grants, teaching, service, mentoring); you set targets; pro-rated pace; timeline; tracks progress, does not predict a decision | 1 | `site/sheets/tenure-tracker/index.html` | 2026-10-04 | none |
| Grant Pipeline & PI Effort Tracker | $12; up to 100 proposals; stages; effort by person (up to 200 rows) with cap flag; does not know sponsor effort rules; no connection to a grants system | 1 | `site/sheets/grant-pipeline-tracker/index.html` | 2026-10-04 | none |
| Job Market Tracker | $9 | 1 | `site/sheets/job-market-tracker/index.html` | 2026-10-04 | not used beyond a mention |
| Bundle | $39 for six spreadsheets; the five trackers sold separately total $59 | 1 | `site/sheets/index.html` | 2026-10-04 | none |
| Google Sheets import | File, Import, Upload, Replace spreadsheet | 1 | tracker pages | 2026-10-04 | none |

## Researcher profile systems

| Tool | Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|---|
| ORCID | Cost | Free; not-for-profit sustained by member fees | 1 | https://info.orcid.org/what-is-orcid/ (fetch summary) | 2026-10-04 | none |
| ORCID | Sections | Eleven activity sections including Education, Employment, Service, Funding, Peer Review, Works | 1 | https://info.orcid.org/documentation/integration-guide/orcid-record/ (fetch summary) | 2026-10-04 | none |
| ORCID | Works | Researchers can add works directly, or client applications can | 1 | same | 2026-10-04 | none |
| ORCID | Peer review | "Peer review items can only be added by the API; the user is not able to enter new items" | 1 | same | 2026-10-04 | none |
| ORCID | Submission status | No section for work under review or decisions (absence from the eleven-section list) | 1 (absence) | same | 2026-10-04 | none |
| ORCID | NIH | ORCID iD required and linked to eRA Commons for SciENcv common forms | 1 | https://grants.nih.gov/grants/guide/notice-files/NOT-OD-26-018.html (fetch summary) | 2026-10-04 | none |
| Google Scholar | Cost and function | Free; needs a Google account; citation metrics computed automatically; h-index, i10-index, total citations "All" and "Recent"; articles added by search, manual entry, groups or automatic updates | 1 | https://scholar.google.com/intl/en/scholar/citations.html (fetch summary) | 2026-10-04 | none |
| ResearchGate | Function | "Professional network"; join for free; claim publications; stats on uploaded research; Research Interest Score, reads | 1 | https://help.researchgate.net/getting-started/what-is-researchgate (fetch summary); stats from help-center search excerpt | 2026-10-04 | home page 403 |
| Academia.edu | Function | Profiles to upload and share papers, readership analytics | 3 | search excerpt of support.academia.edu "Profile overview" (403) | 2026-10-04 | Premium price reported as $99 a year (Inside Higher Ed headline) and $9.99 monthly (aggregator); not stated in article |
| Semantic Scholar | Author pages | Created automatically from publicly accessible publications; free; claim and edit via Edit Author Page | 1 | https://www.semanticscholar.org/faq/author-profile (fetch summary); claim/edit from FAQ search excerpt | 2026-10-04 | none |
| SciENcv | NIH | From due dates on or after 2026-01-25, NIH requires SciENcv to complete Biographical Sketch and Current and Pending (Other) Support Common Forms and the Biosketch Supplement; certify yourself; ORCID linked | 1 | NOT-OD-26-018 (fetch summary) | 2026-10-04 | none |
| Web of Science Reviewer Recognition | Function | Reviewers opt in; reviews from 9,500+ participating journals added to Web of Science Researcher Profile; verified; CV download that includes reviews; links with ORCID | 1 | clarivate.com Reviewer Recognition page (search excerpt; page 403) | 2026-10-04 | free: Clarivate profile page headline "Register for your FREE Web of Science profile" (search excerpt) |

## Journal submission systems

| Tool | Fact | Value | Tier | Source | Checked |
|---|---|---|---|---|---|
| ScholarOne Manuscripts | Author Center | Submit manuscripts and track status; summaries of submitted manuscripts; recent correspondence; prompts for revision and resubmission | 1 | clarivate.com ScholarOne page (search excerpt; 403) | 2026-10-04 |
| Editorial Manager | Authors | "Track manuscript status"; cloud workflow system for journals, used by publishers and societies | 1 | https://www.ariessys.com/software/editorial-manager/ (fetch summary) | 2026-10-04 |

## Institutional systems

| Tool | Fact | Value | Tier | Source | Checked |
|---|---|---|---|---|---|
| Interfolio | Owner | Part of Elsevier; modules: Faculty Search, Review Promotion & Tenure, Lifecycle Management, Faculty Activity Reporting | 1 | https://www.elsevier.com/products/interfolio (fetch summary) | 2026-10-04 |
| Interfolio FAR | Function | Collects teaching, research, service; export to CVs, promotion, annual reviews; request a consultation (no public price) | 1 | https://www.elsevier.com/products/interfolio/activity-reporting | 2026-10-04 |
| Interfolio FAR | Former name | Faculty180: stated by university pages (URI, Fordham, TAMU listed in search); vendor page does not mention it. article does not use the former name | 2 | search results | 2026-10-04 |
| Interfolio RPT | Function | Candidates curate their story across teaching, service, research; can pull from FAR or institutional systems; no public price, "Request a consultation" | 1 | https://www.elsevier.com/products/interfolio/review-and-promotion | 2026-10-04 |
| Interfolio Dossier | Function and price | Free: letter requests, job search, applications to Interfolio-hosted positions; Dossier Deliver $59.99 for 50 electronic and/or mail deliveries; stores career materials and confidential letters | 1 | https://www.interfolio.com/dossier/ (fetch summary) | 2026-10-04 |
| Watermark Faculty Success | Function | Formerly Digital Measures; teaching and mentoring, scholarship and research (publications, presentations, grants), service, administrative data; reports include CVs, biographical sketches, annual reports; review processes; contact sales, no public price | 1 | https://www.watermarkinsights.com/solutions/faculty-success/ (fetch summary) | 2026-10-04 |
| Elsevier Pure | Function | Research information management; 500+ institutions in 50+ countries; publications, funding, people, projects, impact; syncs with Scopus, ORCID, HR and finance systems; researcher profiles; contact us, no public price | 1 | https://www.elsevier.com/products/pure | 2026-10-04 |
| Symplectic Elements | Function | Digital Science; harvests publications from PubMed, Web of Science, Scopus, Crossref, arXiv; grants via Dimensions integration; teaching and professional activities; faculty activity reporting; AI-assisted profile curation from CVs; no price, "book a demo or contact" | 1 | https://www.symplectic.co.uk/products/symplectic-elements/ (fetch summary) | 2026-10-04 |

## Personal and dedicated tools

| Tool | Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|---|
| Manuscripts (manuscripts-app.com) | Price, trial | $49 one-time; 14-day free trial, no card; 30-day refund; all 1.x updates free; up to three Macs per license; lab licenses for 5+ | 1 | https://manuscripts-app.com/ (fetch summary) | 2026-10-04 | existing guide says "sold through Gumroad"; fetch summary says direct from site. Article says "sold from its own site" |
| Manuscripts | Platform | macOS 14.6 (Sonoma) or later; Apple silicon and Intel; Mac only | 1 | same | 2026-10-04 | none |
| Manuscripts | Tracks | Drafting, peer-review rounds, revisions, authors, journal submissions, deadlines, decision letters; local data with automatic backups on launch; no server | 1 | same | 2026-10-04 | CV, grants, teaching: none mentioned |
| Papertrek | Price | Free while in beta; paid plans 2027 at the earliest; a free tier planned | 1 | https://papertrek.app/ (fetch summary) | 2026-10-04 | none |
| Papertrek | Function | Idea to published; submissions, revisions, reviewer notes, decisions; connect ORCID or drop a BibTeX file; export or delete everything; hosted in the EU; no grants, CV or teaching on page | 1 | same | 2026-10-04 | none |
| Paperpin | Price, function | Free, no card; web dashboard; deadlines for 600+ conferences and 75+ journals; manuscript status, rebuttal windows, decision dates, revision history | 1 | https://www.getpaperpin.com/ (fetch summary) | 2026-10-04 | not in the earlier guide; vendor's own count claims not verified |
| Auctorium | Price, platform | $4.99 on the App Store; iPhone, iPad and Mac; minimum OS 26.2; seller Ezequiel Santos; last release 2026-09-06 | 1 | iTunes Search API, https://apps.apple.com/us/app/auctorium/id6756827686 | 2026-10-04 | search summary reported an in-app "Scholar" unlock at $9.99; unconfirmed (site 404). Article gives the store price and notes in-app options may exist |
| Auctorium | Function | Submissions from idea to published with venues, coauthors, notes, attachments; multiple deadlines per submission; reminders; dashboard | 1 | App Store description | 2026-10-04 | none |
| Subthesis tracker | Price, storage | Free, no login; data kept in browser localStorage; export submission records; fields: title, journal, date, manuscript ID, editor, status, decision dates, revision deadlines | 1 | https://www.subthesis.com/tools/journal-submission-tracker (fetch summary) | 2026-10-04 | none |
| VitaMine | Price, access | Free tier; VitaMine+ EUR 25 a year; invitation code for early testers; web | 1 | https://vitamine.cloud/ (fetch summary) | 2026-10-04 | none |
| VitaMine | Function | Import existing CV or biosketch; ORCID, OpenAlex, Zotero sync; portable SQLite database download; Word templates; sends selected CV text to OpenAI for AI-assisted import with consent; no submission or deadline tracking mentioned | 1 | same | 2026-10-04 | none |
| PaperRoute-Tracker | Function | Open-source (GPL-3.0), local-first Windows app (Windows 11, .NET 10) for tracking manuscripts draft to publication | 1 | https://github.com/JUhalt/PaperRoute-Tracker (fetch summary) | 2026-10-04 | none |
| SigmaCV | Function | Free for individuals, open source; builds CV from OpenAlex, ORCID, Crossref and others; exports PDF, DOCX, LaTeX, Markdown | 1 | https://sigmacv.org/ (fetch summary) | 2026-10-04 | none |
| Zotero | Price | Free 300 MB; 2 GB $20/yr; 6 GB $60/yr; unlimited $120/yr | 1 | https://www.zotero.org/storage (fetch summary) | 2026-10-04 | none |
| Zotero | Platforms | Mac, Windows, Linux, iOS, Android | 1 | https://www.zotero.org/download/ (fetch summary) | 2026-10-04 | none |
| Zotero | My Publications | Bibliography of your own work shared on zotero.org profile, with licensing options | 1 | https://www.zotero.org/support/my_publications (fetch summary) | 2026-10-04 | none |
| Notion | Price | Free $0; Plus $10 per member per month; Education: free Plus for students and educators, one member, school email | 1 | https://www.notion.com/pricing (fetch summary) | 2026-10-04 | none |
| Notion | Templates | Gallery lists "Submission Tracker - Scientific Manuscripts", "Manuscript Submissions Tracker", "Paper Tracker", "Research Project Tracker" | 1 | notion.com template gallery (search excerpt) | 2026-10-04 | none |
| Airtable | Price | Free plan for individuals and small teams; Team $20 per user per month billed annually; Business $45 | 1 | https://www.airtable.com/pricing (fetch summary) | 2026-10-04 | free-plan record limit not read |
| Airtable | Templates | Nonprofit Grant Tracker template with application status fields; a search found no academic submission tracker | 1/absence | airtable.com templates (search excerpt) | 2026-10-04 | absence claim worded "I did not find" |
| Overleaf | Price | Free (1 collaborator per project); Student $8.25 a month billed annually; Standard $199 a year; Pro $399 a year | 1 | https://www.overleaf.com/user/subscription/plans (fetch summary) | 2026-10-04 | none |
| moderncv | Version | 2.6.1, released 2026-06-24; LPPL 1.3c; in TeX Live and MiKTeX; five styles | 1 | https://ctan.org/pkg/moderncv (search excerpt) | 2026-10-04 | none |
| Excel, Numbers, Google Sheets | Price | Not verified; the article gives no price for them ("whatever you already pay for") | n/a | Apple support page (fetch summary) states Numbers exports to Excel format; no price on Numbers or Sheets pages read | 2026-10-04 | none |
| Word CV templates | Specific template | Microsoft template page returned 404; article says only that templates come with Word or from your department | n/a | n/a | 2026-10-04 | none |

## Not verified at tier 1 (handling)

- Academia.edu: page 403. The article says it is "built around uploading and sharing papers" (from a search excerpt of its support page) and gives no price; the reported $99 a year is omitted.
- Interfolio FAR former name (Faculty180): stated by university pages, not by the vendor page; omitted from the article.
- Auctorium in-app price: unconfirmed (website gone); the article gives the App Store price and says further unlocks could not be confirmed.
- Numbers, Excel, Google Sheets, Word prices: omitted.
- WoS Reviewer Recognition and ScholarOne: Clarivate pages 403; wording rests on vendor-page search excerpts and is stated as "per Clarivate" or "according to Clarivate"; the article says so for Reviewer Recognition.
- Paperpin's counts (600+ conferences, 75+ journals) are the vendor's own claim; the article says "its page lists" and "I have not checked those counts".
- Manuscripts distribution: earlier guide says Gumroad; the vendor page read in this pass did not say so; the article does not state a storefront.
- No tool other than Vitae and the Purplelink spreadsheets was tested; the article says so in the disclosure.
- Vitae export formats differ across three pages: Vitae page (PDF, LaTeX, rich text), Plus page (PDF, rich text, Markdown), tenure guide (PDF, Word-compatible rich text, Markdown). The article states PDF, LaTeX and rich text and does not mention Markdown.
