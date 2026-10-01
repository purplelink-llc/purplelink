---
id: q-20261001-mtx1
created: 2026-10-01T18:00:00-04:00
job: manual-seed
model: "hosted:claude"
kind: submission
target: "AlternativeTo and MacUpdate: ModernTex listings"
executor: ben
risk: low
effort_minutes: 40
expires: 2026-10-22
expected_effect: 10-40 visits a month and two listing pages that mention ModernTex (estimate)
ledger: directory-submissions
status: pending
value: 3
---

## Ask
Submit ModernTex to AlternativeTo and to MacUpdate from your own accounts with the text below, and decide whether to open a versioned public trial URL so a Homebrew cask becomes possible.

## Why now
- ModernTex has no directory listing yet, and AlternativeTo says a new app waits in its backlog for at least a few months (https://alternativeto.net/faq/, read 2026-09-29), so the wait starts when you submit.
- Homebrew will not take a cask today: the trial URL has no version in it, and the notability rule asks for public interest beyond the author (https://docs.brew.sh/Acceptable-Casks and https://docs.brew.sh/Package-Acceptance-Policy, read 2026-10-01). Listings like these two are the evidence that rule asks for.
- The SaaS panel on 2026-10-01 found that the site's weak point is trust and links from other sites, not page copy (docs/growth-briefs/saas-panel-2026-10-01.md).

## Draft
AlternativeTo (no links or email addresses in the description):
```
Name: ModernTex
Platform: Mac
License: Commercial, free trial (7 days), then $10 one-time
Short description: A native macOS LaTeX editor for researchers.
Description: ModernTex is a native macOS LaTeX editor for academic writing. It keeps the source and the PDF in sync in both directions, explains LaTeX errors in plain language, and checks a manuscript for anonymization, page limits and required sections before submission. It also offers revision snapshots, BibTeX completion that searches the whole bibliography, a visual TikZ Designer and a spreadsheet-style Table Editor. It runs on macOS 14 or later, on Apple silicon and Intel, and uses MacTeX or TinyTeX. There is a free 7-day trial, then a one-time $10 purchase with all 1.x updates included. Files stay as ordinary .tex and .bib files on your disk. It compiles on your Mac, with no account, and does not offer real-time co-editing.
Tags: LaTeX, LaTeX editor, academic writing, PDF preview, BibTeX
Alternative to: Overleaf, TeXShop, Texifier
```

MacUpdate:
```
App Name: ModernTex
Developer: Purplelink LLC
Price: 10 (USD, one-time, 7-day trial)
Version: 1.3.0
Download URL: https://purplelink.llc/moderntex/
Product Page URL: https://purplelink.llc/moderntex/
Short Description: A native macOS LaTeX editor for researchers.
System Requirements: macOS 14 Sonoma or later. Apple silicon and Intel. Needs a TeX distribution (MacTeX or TinyTeX); if neither is installed, ModernTex offers a one-click TinyTeX install.
Description: the three-paragraph text in docs/products/moderntex-listings-2026-10.md, section (b).
```

## Verify
- Price, trial, version, requirements and every feature named: site/moderntex/index.html ("At a glance" table and Features section) and site/llms.txt lines 28 to 38.
- AlternativeTo rules (email verification, no links in descriptions, optional $5 queue fee, months of backlog): https://alternativeto.net/faq/, quoted in docs/directory-submissions.md section 4.
- MacUpdate field names: https://www.macupdate.com/help/submit-app, quoted in docs/directory-submissions.md section 5. Its listing terms (fees, any required link back) were not read: the support article returned 404 on 2026-09-29. The first approved step is for you to read them on the form; nothing in the draft depends on them.
- Homebrew rules and the trial delivery path: docs/products/moderntex-listings-2026-10.md section (a), from netlify/functions/moderntex-download.mjs and the three docs.brew.sh pages named there.

## If approved
1. You sign in to AlternativeTo, verify your email, choose "Suggest new application", paste the AlternativeTo block, add the three screenshots listed in docs/products/moderntex-listings-2026-10.md, and skip the $5 priority fee.
2. You open the MacUpdate submit page, read the listing terms first, and stop if they ask for payment or a link back from purplelink.llc. Otherwise paste the MacUpdate block and the long description.
3. Mark this item done with both listing URLs, and add them to docs/directory-submissions.md.
4. Homebrew: reply "cask yes" if you want a versioned public trial URL added to moderntex-download.mjs and a cask in our own tap. That is a separate code change and gets its own item; nothing is submitted to Homebrew under this one.

## If rejected
Give a reason code: tone, wrong-target, wrong-fact, not-now, no-value or risk.

## Evidence
docs/products/moderntex-listings-2026-10.md (drafts and Homebrew findings, vendor pages read 2026-10-01). docs/directory-submissions.md sections 4 and 5 (vendor terms read 2026-09-29).
