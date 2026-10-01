# AdSense readiness audit, 2026-10-01

Publisher: pub-6407975157274256. Site: purplelink.llc.
Console state read 2026-10-01: Sites page shows purplelink.llc as "Needs attention",
detail "Low value content", last updated 2026-09-15; ads.txt status "Not found";
account banner says payment information is still missing. The site is not approved
and no ads are serving. The memory note that Auto Ads are live is wrong; this audit
is the preparation for re-requesting review.

Worktree: /tmp/pl-panel. Nothing here is committed; the coordinator commits.

## Why Google says "Low value content"

Google's wording for this status is: "Your site has content quality issues. We
believe that there isn't enough original, rich content that would be of value to
users" (https://support.google.com/adsense/answer/9680050). The reviewer crawls the
whole site, not the index, so `noindex` does not take a page out of the review.
Counting every HTML file under `site/` (287 pages), these are the pages most likely
being counted against the site:

1. **The daily digest: 102 machine-compiled pages, 36% of the site.** 95 daily
   issues (`/blog/digest/2026-06-22.html` through `2026-09-30.html`), 6 topic hubs
   (`/blog/digest/topics/{ai_tech,cybersecurity,entrepreneurship,finance,general_tech,papers}/`)
   and the archive index `/blog/digest/`. Each issue is an automated summary of
   other people's articles. That is the profile the publisher policy calls
   "replicated content": "embedded or copied content from others without
   additional commentary, curation, or otherwise adding value"
   (https://support.google.com/adsense/answer/9335564). The issues and hubs were
   set `noindex` after the 2026-07-05 rejection and the per-issue template has no
   ad tag, but the archive index was still indexable, still in the footer, and
   still carried the AdSense loader until this audit. A new issue lands every day
   at 06:00 from the Modal cron, so the ratio gets worse over time.

2. **The "why it matters" cluster: 16 pages of 186 to 261 words, all carrying
   ads.** `/guides/why-it-matters/` and its 15 children. They are `noindex` and
   only reachable from Paper Review reports and one guide, so they are thin and
   orphan-adjacent. Ad tag removed from all 16 in this audit.

3. **Thin indexable pages.** Under 300 words in `<main>`: `/sheets/live/` (85),
   `/format/` (131, hub), `/tools/abstract-checker/` (197), `/recover/` (245),
   `/templates/` (295), `/tools/markdown-to-pdf/` (299). Only the last two
   carried ads; both removed. The others never carried ads but still count as
   thin pages in a site review.

4. **Templated near-duplicates.** The 5 template pages
   (`/templates/{acm-acmart,apa7,elsevier-elsarticle,ieee-conference,neurips}/`)
   share about half their vocabulary pairwise (Jaccard 0.45 to 0.54 on the word
   set of `<main>`); the 10 LaTeX tool pages share one page structure. No change
   made; the pages are legitimately different, but a reviewer skimming them sees
   repetition.

5. **Placeholder and transactional pages.** `/binnacle/` (waitlist, indexable),
   `/grant-review/` and `/budgetcast/` (noindex), `/404.html`, `/search/`,
   `/recover/`, `/vitae/plus/manage/`, five `/success/` pages. None carries ads.
   All but `/binnacle/` and `/recover/` are `noindex`. 140 of 287 pages are
   `noindex`; 117 of those are the digest and the why-it-matters cluster.

Code changes in this audit cut the pages carrying the AdSense loader from 85 to
57 and make sure every remaining ad page is a hand-written page of at least 400
words that is reachable from the nav, the footer, or a hub page. They do not shrink
the digest. If Google rejects again on the same status, the next lever is the
digest itself (stop publishing it to the site, or move it off purplelink.llc), not
more ad-tag edits.

## Blockers

| # | Rule (source) | Evidence | Status |
|---|---|---|---|
| 1 | Ads on "screens without publisher-content or with low-value content" (https://support.google.com/adsense/answer/9335564) | 16 why-it-matters pages at 186 to 261 words, `/templates/` at 295 words, `/tools/markdown-to-pdf/` at 299 words all carried the loader | Fixed in code: tag removed from all 18 |
| 2 | Replicated content without added value (same URL as #1) | 102 digest pages are machine summaries of third-party articles; archive index `/blog/digest/` carried the loader | Fixed in code for the ad tag (index tag removed; issue template `backend/digest/publisher.py` already had none). The content ratio itself needs an owner decision (see above) |
| 3 | Owner decision: no ads on any page with a file upload (manuscripts) | 10 tool pages with `input type="file"` carried the loader: bib-validator, file-to-markdown, latex-diff, latex-to-pdf, latex-to-word, markdown-to-pdf, pdf-structure, pdf-tools, word-counter, word-to-latex | Fixed in code: 0 file-input pages carry the tag |
| 4 | "Screens ... under construction" or used "for alerts, navigation or other behavioral purposes" (same URL as #1) | grant-review, budgetcast, binnacle, 404.html, 5 success pages, recover, manage, search | Already clean: none carried the tag |
| 5 | Certified CMP for EEA, UK and Switzerland: "As of 16 January 2024, a certified CMP integrated with the TCF is required" for EEA and UK, 31 July 2024 for Switzerland (https://support.google.com/adsense/answer/13554116) | No consent code anywhere in `site/` (grep for fundingchoices, googlefc, __tcfapi: nothing). Google's own "European regulations message" counts as a certified CMP and is delivered through the existing adsbygoogle.js loader, no page code needed (https://support.google.com/adsense/answer/10960768) | Needs console action (below). CSP prepared in code: `fundingchoicesmessages.google.com` added to script-src, connect-src, frame-src and img-src in `netlify.toml` so the message is not blocked when turned on |
| 6 | Privacy policy must say third-party vendors including Google use cookies to serve ads based on prior visits, and link to Google Ads Settings and aboutads.info (https://support.google.com/adsense/answer/1348695) | `site/privacy/index.html` had the AdSense paragraph and the Ads Settings link but no aboutads.info link, and listed "free tools" and "daily digest" as ad pages | Fixed in code: paragraph now has the required cookie sentence, both opt-out links, a line about the EEA consent prompt, and the corrected list of ad-free pages |
| 7 | ads.txt at the site root in the form `google.com, pub-ID, DIRECT, f08c47fec0942fa0` (https://support.google.com/adsense/answer/12171612) | `site/ads.txt` is exactly `google.com, pub-6407975157274256, DIRECT, f08c47fec0942fa0` plus one newline. Live check 2026-10-01: `curl -I https://purplelink.llc/ads.txt` returns 200, `text/plain; charset=UTF-8`, correct body. No redirect in `netlify.toml` matches `/ads.txt` (the `/*` rule is a 404 fallback that only fires when no file exists); no `_redirects`, no robots Disallow. File committed 2026-07-15 | No code fix. The console's "Not found" is Google's crawl state: "It may take a few days for your changes to be reflected in AdSense. If your site doesn't make many ad requests it may take up to a month" (same URL). An unapproved site makes no ad requests, so the status cannot clear until ads start serving. Nothing to do but recheck after approval |
| 8 | Payment information | Console banner says payment info is missing. Google's approval email goes out "after we've reviewed your payments information and site compliance" (https://support.google.com/adsense/answer/10162) | Needs console action |
| 9 | CSP must let the ad code load. Google only documents a nonce-based strict CSP (https://support.google.com/adsense/answer/16283098) and warns "more restrictive policies may break without notice" | `netlify.toml` uses an origin allowlist covering pagead2.googlesyndication.com, googleads.g.doubleclick.net, tpc.googlesyndication.com, www.googletagservices.com, www.google.com, www.gstatic.com, ad.doubleclick.net, *.adtrafficquality.google in the right directives. The live header matches the file. | Working allowlist; consent origin added (see #5). Risk accepted that Google adds an origin later; watch the browser console after approval |
| 10 | Navigation: "Sites showing Google ads should be easy for users to navigate" (https://support.google.com/adsense/answer/48182); orphan pages with ads | Every remaining ad page has at least one inbound internal link; 32 of 57 are in the shared nav or footer, the rest are linked from `/blog/`, `/guides/`, `/templates/` or `/tools/` hubs. Zero orphans | Clean |
| 11 | Duplicate content | Digest issues vs topic hubs: the hubs repeat issue summaries; all noindex, no ads. Guides: no pair above Jaccard 0.45 except the 5 template pages (0.45 to 0.54, shared boilerplate) | No change; noted |

Pre-existing, not touched: `backend/research_digest/renderer.py` carries the same
publisher's loader on the getmuscleonglp.com research roundup pages (a different
site in the same AdSense account, also "Needs attention"). Out of this audit's
scope; same machine-compiled profile applies there.

## Pages that still carry the AdSense loader (57)

Word count is words inside `<main>`, scripts excluded, measured 2026-10-01.

| Page | Words | Page | Words |
|---|---|---|---|
| / | 875 | /guides/fix-bibtex-errors/ | 1501 |
| /blog/ | 1032 | /guides/get-feedback-on-a-paper-before-submitting/ | 2128 |
| /blog/free-latex-tools/ | 510 | /guides/globepin-vs-polarsteps/ | 786 |
| /blog/keeping-up-when-your-research-crosses-fields/ | 490 | /guides/how-to-respond-to-reviewer-2/ | 633 |
| /blog/one-curation-call-per-day/ | 464 | /guides/latex-equation-to-png/ | 463 |
| /blog/pdf-to-llm-without-losing-the-math/ | 419 | /guides/latex-to-word/ | 546 |
| /blog/running-your-manuscript-through-paper-review/ | 495 | /guides/latex-track-changes/ | 498 |
| /blog/starting-purplelink/ | 656 | /guides/latex-word-count/ | 492 |
| /blog/the-latex-editor-academics-want/ | 718 | /guides/latex/ | 815 |
| /blog/tikz-and-tables-without-the-syntax/ | 649 | /guides/methodology-problems-peer-reviewers-flag/ | 5249 |
| /blog/travel-photographs-as-prints/ | 475 | /guides/overleaf-alternative-mac/ | 2645 |
| /blog/what-globepin-does-differently/ | 700 | /guides/research-paper-pdf-to-markdown/ | 484 |
| /blog/what-openalex-returns-when-you-ask-for-an-abstract/ | 575 | /guides/reviewer-says-novelty-is-limited/ | 592 |
| /blog/where-bibtex-errors-actually-come-from/ | 486 | /guides/track-academic-cv-tenure-case/ | 3596 |
| /blog/why-haea-is-on-device/ | 621 | /guides/use-paper-review-before-submitting/ | 637 |
| /changelog/ | 1790 | /guides/word-to-latex/ | 537 |
| /guides/ | 423 | /templates/acm-acmart/ | 1024 |
| /guides/ai-paper-review-tools-compared/ | 1998 | /templates/apa7/ | 1033 |
| /guides/ai-policy-checking-your-own-manuscript/ | 1468 | /templates/elsevier-elsarticle/ | 982 |
| /guides/best-mac-latex-editors/ | 3269 | /templates/ieee-conference/ | 1012 |
| /guides/best-on-device-health-apps/ | 876 | /templates/neurips/ | 1042 |
| /guides/bibtex/ | 891 | /tools/ | 974 |
| /guides/camera-ready-checklist/ | 529 | /tools/bib-builder/ | 419 |
| /guides/catch-ai-hallucinated-citations/ | 1488 | /tools/citation-generator/ | 566 |
| /guides/check-manuscript-word-limit/ | 542 | /tools/equation-renderer/ | 460 |
| /guides/citation-gap-scan-before-submitting/ | 524 | /tools/latex-table-generator/ | 526 |
| /guides/citation-styles-explained/ | 1336 | /tools/reference-converter/ | 410 |
| /guides/desk-reject-recovery/ | 832 | /tools/submission-checklist/ | 472 |
| /guides/doi-to-bibtex/ | 1321 | | |

Smallest remaining ad page is `/tools/reference-converter/` at 410 words.

## Pages the loader was removed from (28)

File-upload tools (10): /tools/bib-validator/, /tools/file-to-markdown/,
/tools/latex-diff/, /tools/latex-to-pdf/, /tools/latex-to-word/,
/tools/markdown-to-pdf/, /tools/pdf-structure/, /tools/pdf-tools/,
/tools/word-counter/, /tools/word-to-latex/.

Thin pages (17): /guides/why-it-matters/ and its 15 children, /templates/.

Digest (1): /blog/digest/ (the archive index; the 95 issues and 6 topic hubs had
no tag already, and `backend/digest/publisher.py` emits none).

The digest index is edited in place by the Modal cron (it inserts a line at
`<!-- DIGEST_LIST_START -->`), so the removal survives the next run. Committing
`site/blog/digest/index.html` is blocked by the repo guard; the coordinator handles
that file.

## Console steps for the owner

1. **Payments.** AdSense > Payments > Payments info. Add the payee name, address
   and tax form. Approval does not finish without it.
2. **Consent message (certified CMP).** AdSense > Privacy & messaging > European
   regulations > Create (or Manage > Create message). Select purplelink.llc,
   choose languages, set the "Do not consent" option, enter
   `https://purplelink.llc/privacy/` as the privacy policy URL, Publish. No page
   code is needed; the message is served through the existing adsbygoogle.js
   loader. Do this before requesting review so EEA/UK/Swiss traffic is covered
   from the first served ad. Deploy the `netlify.toml` change from this audit
   first or the message will be blocked by CSP.
3. **Deploy the code changes** (coordinator): the 28 page edits,
   `site/privacy/index.html`, `netlify.toml`.
4. **Request review.** Sites page:
   https://www.google.com/adsense/new/u/0/pub-6407975157274256/sites/my-sites
   Open purplelink.llc, click Request review. Steps per
   https://support.google.com/adsense/answer/7003627: Policy center > Fix next
   to the site > "Issues found" > Start review process > pick the reason > tick
   the confirmation > Request review. Expect "a few days, but in some cases it can
   take 2-4 weeks" (https://support.google.com/adsense/answer/7584263).
5. **After approval**, recheck the ads.txt status on the same Sites page; it
   clears once Google has crawled the file following real ad requests. Also open
   the browser console on a guide page and confirm no CSP violation lines.
6. **If rejected again for Low value content**, the remaining lever is the
   digest: 102 of 287 pages, growing by one a day. Options are to stop writing
   issues into `site/` (keep the RSS feed and email), or to move the archive to a
   subdomain not submitted to AdSense.

## Verification

- `grep -rl 'type="file"' site | xargs grep -l adsbygoogle` returns nothing.
- Pages with the loader: 85 before, 57 after. All 57 are above 400 words, have
  at least one inbound link, and are not `noindex`.
- `curl -I https://purplelink.llc/ads.txt`: HTTP 200, text/plain, correct line.
