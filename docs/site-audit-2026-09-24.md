# purplelink.llc site audit (2026-09-24)

This audit was read-only. It covers all 235 HTML files in `site/`, served locally and driven with Playwright at 1440px and 390px in light and dark mode, plus about 330 screenshots. Six parallel passes covered conversion, visual design, navigation, technical SEO, GEO (AI search) and performance/accessibility. I re-checked every finding marked **[verified]** by hand. The live site was not reachable from the sandbox, and ads and analytics were blocked locally, so the production weight and layout shift from AdSense are estimates.

---

## The short version

Most of the pieces are already strong. The editorial typography (Fraunces display, the blog index, the changelog) looks premium. The ModernTex screenshots are real and good. The technical SEO basics are clean: 0 broken links, correct canonicals, noindex where it belongs, valid JSON-LD. There are 0 console errors and CLS is 0.

Three things hold the site back from "I want to buy software from this guy":

1. **The homepage sells a consulting agency, while the rest of the site sells products.** The title is "macOS & iOS App Development | Atlanta, GA", the schema is a "Software Services" catalog, and the page ends on "Build with *Purplelink.* If a project sounds like a fit…". The six paid AI tools, Vitae Plus and the review packs never appear on the homepage. Paper Review shows up only as a chip under **"Free** tools". Search engines, LLMs and first-time visitors all come away thinking this is an Atlanta dev shop.
2. **Navigation is broken or inconsistent, and most pages are dead ends.** "Software" and "Products" in the main nav point to anchors that no longer exist, on 226 pages. There are 9 nav variants and 6 footer variants. 48 pages cannot be reached from the homepage, and 13 of 23 blog posts link to no product at all, including the post about Paper Review.
3. **The pages that sell show the least proof, and carry ads.**
   - Paid tool pages are all text, with a "View sample" link hidden behind a click.
   - Vitae has no screenshots.
   - The GlobePin and Haea screenshots render as giant broken crops.
   - There are no testimonials anywhere, and About doesn't say who Ben is.
   - AdSense Auto Ads load on the checkout, upload and "waiting for your review" pages.

---

## 1. Fix first: bugs that take minutes to hours

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 1 | **A screenshot of a Claude desktop session is deployed publicly** [verified]. It shows the menu bar, date, battery, "Bypass permissions" and the repo name. | `site/assets/vitae-screens/dashboard.png` (1.04 MB, referenced nowhere) | Delete it. |
| 2 | **"Software" and "Products" nav links go nowhere** [verified]. The 404 page's "See our apps" button has the same problem. | 226 pages link `/#software` and `/#projects`; `index.html` has neither id | One shared nav (see §3). The quick patch is to point them at `/#moderntex` and `/#apps`. |
| 3 | **GlobePin and Haea screenshots render at 394×2622**, as zoomed crops of half-words ("imeline", "Replay") [verified]. The GlobePin page is 8,700px tall on desktop and 20,100px on mobile. | `styles.css:1437` `.screenshot-grid img` lacks `height:auto`, so the `height="2622"` attribute wins | Add `height:auto`. `.screenshot-wide` already has this fix and a comment explaining it. |
| 4 | **llms.txt quotes the old prices**: Paper Review at $3/$5/$8 (the site charges $9/$11/$15), packs at $12/$40 (the site: $38/$150), and ModernTex at "1.0.2, 13 MB". It leaves out Vitae, Resume Review and Kits [verified]. | `site/llms.txt:36-40, 138-145` | Regenerate it from `checkout.mjs` and the pages at deploy time so it can't drift again. |
| 5 | **Six share images don't exist**, so shared links to Paper Review and 5 other paid tools show no image [verified]. | `assets/og/{paper-review,anonymity-check,citation-gap,cover-letter,pdf-structure,response-review}.png` missing | Generate them with `assets/og/_gen.html`, and add a deploy check that fails when an `og:image` file is missing. |
| 6 | **Buttons on tool pages carry a browser-default 2px black border** [verified]. Examples: Generate, Start review, Buy pack. `.btn-secondary` buttons also get the browser's grey fill. | `.btn` never resets `border` on `<button>` | `button.btn{border:0;font:inherit}` plus an explicit background on `.btn-secondary`. |
| 7 | **"Add to Chrome — free" fails contrast in dark mode** at about 2.8:1: light-purple text on a white pill [verified]. This is the same bug the last commit fixed on the ModernTex button. | `.btn-light` uses `color: var(--purple)`, which turns light in dark mode | Give `.btn-light` a fixed dark-purple text color. |
| 8 | **Word spaces collapse in the body font** [verified]. Chips read "Paperreview" and "Browsealltools", and body text reads "themwith". Plus Jakarta Sans's space glyph is 0.17em. | measured from `plus-jakarta-sans-latin.woff2` hmtx | `body{word-spacing:0.04em}`, applied to buttons and chips too. |
| 9 | **12 pages scroll sideways on phones**: `/guides/doi-to-bibtex/` is 910px wide, `/guides/bibtex/` 477px, plus the citation-styles guide, fix-bibtex-errors, 4 format pages, 2 comparison tables and latex-to-word's `<select>`. | no `pre` rule in `styles.css` | `.post-body pre{overflow-x:auto}`, `.post-body table{display:block;overflow-x:auto}`, `overflow-wrap:anywhere` on long links, `select{max-width:100%}`. |
| 10 | **"What you get" on Paper Review sits flush left**, outside the content column. | `tools/paper-review/paper-review.css:172` `.pr-pricing{margin:1.5rem 0}` cancels `margin-inline:auto` | Use `margin-block`. |
| 11 | **The digest subscribe link points to the wrong id** [verified]. | links go to `/blog/digest/#subscribe`; the id is `subscribe-form` | Fix the anchor. |
| 12 | **Paper Review promises an annotated PDF in one place and not the other.** | `paper-review/index.html:211` vs `:278` | Make the Standard tier and "What you get" lists match. |
| 13 | **Native controls stay white in dark mode**: selects, checkboxes, scrollbars. | no `color-scheme` declared | `:root{color-scheme:light dark; accent-color:var(--purple)}` |
| 14 | **The homepage schema has problems.** The Chrome Web Store rating is marked up as `aggregateRating`, which Google's review-snippet rules forbid. Haea reads "A on-device iOS health app for iOS" and has no `PreOrder` availability. | `index.html` JSON-LD | Remove the rating, fix the typo, add `availability: PreOrder`. |

---

## 2. Selling: make it feel like a product company

**Reposition the homepage around what you sell.**
- **Title:** something like "LaTeX Editor for Mac, AI Paper Review & Free LaTeX Tools | Purplelink". Remove `meta keywords` from all 90 pages; search engines ignore it.
- **Hero:** "Making software that lasts." is beautiful but says nothing about the products, and the right half of the hero is empty at 1440px. Keep the type and put a product in the empty half: the ModernTex window, or a stack of the app icons.
- **New section, "Before you submit":** Paper Review (from $9), Response Review ($6), Citation Gap ($3), Anonymity Check ($2), each with its price and one line. Move the Paper Review chip out of "Free tools".
- **Replace "Build with Purplelink."** with a plain contact line, for example: "Questions about any of these? Email ben@purplelink.llc. I read and answer every message myself." Also update the `OfferCatalog`/`knowsAbout` schema so it lists the products rather than services.

**Take ads off the money pages.** AdSense Auto Ads currently loads on:
- `/moderntex/`, `/vitae/`, the kits pages;
- every paid tool landing page;
- the upload and compose pages, and `tools/paper-review/status/`, where a customer who just paid $15 waits 4–8 minutes.

Auto Ads can place a competitor's ad next to your Buy button, and ads undercut the "nothing is kept" privacy message. Keep the CSP exception, but drop the script tag (or exclude those URLs in AdSense) on paid, product, checkout, upload, status, About and Privacy pages. Keep ads on free tools, guides, the blog and the digest, using fixed-height slots so they don't shift the layout. Also remove the no-op `ethicalads.js` tag (`PUBLISHER=""`) from 128 pages.

**Add proof. Right now the only proof on the site is the Chrome extension's 1,000 users and 4.5 stars.**
- **Paper Review:** show the sample report open by default, or as a cropped screenshot.
- **Cover Letter, Anonymity Check, Citation Gap:** add a short sample output to each; they have none.
- **Vitae and Vitae Plus:** add 2–3 real screenshots. Plus costs $24/yr and has no visuals.
- **ModernTex:** a 20–30 second silent screen recording, self-hosted mp4.
- **Quotes:** ask the 16 Chrome Web Store reviewers and early buyers for 3 real ones.
- **About:** turn it into a founder page with a photo, 3–4 sentences in first person, academic background and papers, and why you built these. It currently lists only ModernTex, Haea and GlobePin, and says ModernTex is "Version 1.0".

**Fix the ModernTex flagship screenshot.** It shows:
- "1 error, 4 warnings, Package error";
- a "Your Paper Title Here" placeholder PDF;
- a personal `Kalshi.tex` tab;
- a stray third-party overlay on the right edge.

Re-shoot it with a clean build of a realistic manuscript.

**One refund line under every Buy button.** Paper Review, Resume and Response have one. Cover Letter and Anonymity Check don't. ModernTex has none on the page or in the terms. Suggested line: "If it doesn't do what this page says, email ben@purplelink.llc within 14 days for a full refund."

**Give every success page a next step.** The Paper Review status page already cross-sells well. The ModernTex, Vitae Plus, Kits and Packs success pages end with install notes. For example, on ModernTex success: "Before you submit: Paper Review checks methods, stats and citations, from $9."

**Tip jars compete with the products.** The Vitae hero offers "Buy me a coffee" and "Support monthly" but not Vitae Plus. Every free tool says "leave a tip". Asking for tips reads as a hobby project. Put Vitae Plus in the hero, move tips to the footer, and use a product card on tool pages instead.

**Kits pull against the brand.** "Sell the shovel", the faceless TikTok pipeline and the Twitch clip reposting sit in the main nav next to a manuscript reviewer that asks faculty to trust it with unpublished work. The "launch price, rising to $79" has no end date. Move Kits out of the primary nav into the footer (or a separate brand), date the price or drop the claim, and consider retiring the clip pipeline, which invites copyright objections.

**Copy that overclaims or slips out of the brand voice:**
- "senior-reviewer-level red team" (paper-review)
- "No more desk rejections" and "BibTeX autocomplete that actually works" (moderntex)
- "the COGS is lower" (revision)
- "Priced for the community" (tools)
- "a beautifully typeset setup guide" (kits)

Replace each with the plain, literal version.

---

## 3. Navigation and page-to-page flow

**One nav, one footer, generated from one partial.** There are 9 header variants today: the homepage uses "Apps", most pages use "Software/Products", Kits is missing on 60 pages, and `/kits/` drops Changelog and Contact. Proposed:

- **Primary nav (5 items, fits 390px without scrolling):** Products · Tools · Guides · Blog · About. Guides is not in the header anywhere today. Changelog and Contact move to the footer. Set `aria-current` on every page (it's missing on all guides and format pages).
- **Mobile:** today the nav is a horizontal strip that hides About and Contact off-screen, and the sticky header is 117px (14% of the screen). Either use the 5-item nav or a `<details>` disclosure below 480px.
- **New `/products/` hub** covering:
  - Mac apps: ModernTex, Vitae and Plus
  - AI manuscript review: the 7 paid tools
  - iOS apps: GlobePin, Haea
  - Scholar Utility Belt, the Daily Digest and Kits

  Nothing lists everything in one place today.
- **4-column footer on every page:**
  - Products
  - Free tools
  - Learn (Guides, Why it matters, Venue formats, Blog, Changelog)
  - Company (About, Press, Contact email, Privacy, Terms)

  Today 228 pages have no footer link to `/tools/` and none show a contact email.

**A "Next step" block on every guide, tool, post and digest.** Generate it from one map (tool → guides → posts → product): *Do it now* (the tool), *Learn more* (2 guides), *Related writing*, and one product card.
- **Blog posts with no product link.** 13 of 23 link nowhere useful:
  - `running-your-manuscript-through-paper-review` never links to Paper Review.
  - The response-letter, blinding, cover-letter, literature-search, Vitae and GlobePin posts don't link to their products either.
- **Tools and guides link in one direction only.** Only 20 of 88 guide→tool links are returned. cover-letter, citation-gap and resume-review link to none of their guides, and paper-review links 1 of about 20.
- **Digest pages** (41% of the site's pages) link only to About and the index. Add previous/next and a product link.

**Unreachable pages:**
- **11 guides no page links to**, including `word-to-latex`, which Search Console already reported. `/guides/` lists 18 of 33 guides.
- **The 16-page `why-it-matters` series:** no link reaches it and it isn't in the sitemap.
- **The 6 digest topic pages:** unreachable by links.

**Breadcrumbs:** make them visible (Home › Guides › …) from the same data as the BreadcrumbList schema. Only a "← back" link exists today, and the schema covers some sections but not others.

**Smaller items:**
- **404 page:** add links to Tools, Guides, Blog and Products.
- **Search:** a small static search over the sitemap or llms.txt would help once a site passes about 150 pages, and this one already has.
- **Blog index:** split it into "For researchers" and "Engineering notes".

---

## 4. Visual design

**Two design languages.** The editorial pages (homepage, blog, changelog, posts, guides, 404) share Fraunces display headings and feel premium. The tool pages, paid pages and format pages look like a plainer site. The cost falls on the pages that sell. Their problems:
- A 32px sans H1.
- H2s that switch between sans and serif on the same page.
- The black button borders from §1.
- Off-palette controls:
  - the navy `#1a1a2e` textarea and Tailwind-violet `#7c3aed` focus ring in the equation renderer;
  - Arial tabs in the bib validator;
  - hard-coded `#c0392b` in the word counter.

About 80 raw hex values sit in the per-tool CSS files. **Fix:** bring tools and paid pages into the editorial template, with a Fraunces H1, token-styled inputs, and each tool framed as an app panel. The blog index and changelog heroes are the model to copy.

**Show the product on every product page.** ModernTex does this well. Elsewhere:
- **Vitae:** no screenshots.
- **GlobePin and Haea:** the heroes have an empty right half, and their screenshots are broken (§1).
- **Kit covers:** nearly blank white pages with 6px text.
- **Paid tools:** no visuals at all.

Put a framed device screenshot (about 300px phones, soft shadow) in each empty hero half.

**Grids with empty or orphan cells read as unfinished.**
- **ModernTex:** the feature grid is 10 items in 4 columns, and "For academic authors" is 3 in 4. Both are padded with a flat lavender block.
- **Vitae:** 4+2 with a filler.
- **/tools/:** rows end 3+1 and 3+2.
- **About and Press:** end on an orphan card.

Size grids to the item count, or make one item a wide feature card.

**Homepage details:**
- The hero CTAs sit far right, detached from the lede.
- "More from the studio" cards span 1280px with content only in the left half; add a screenshot or make it a 3-up card row.
- The tools section is left-aligned with an empty right half, and the chips leave "Paper review" orphaned on its own row.
- The hero orbit decoration is effectively invisible at 1440px.

**The ModernTex page:**
- The hero fine print is centered under left-aligned content.
- The page ends on the FAQ with no closing price-and-buy block. Add a final "$10, 7-day free trial" band.

**Consistency tokens:**
- 17 border-radius values; collapse to 4 tokens.
- 12 box-shadows; collapse to 3 elevation tokens.
- H1 sizes of 165, 72, 48 and 32px with no scale; define `--step-*` tokens.
- 108 raw color literals in `styles.css`, including off-hue status tags at hue 145/180/250.
- Three FAQ styles.
- Hero and back-link rules that stop part-way across the page.
- Inline `style=""` still in 44 files. The AdSense CSP exception allows it, but the house rule says no.

**Small things:**
- The blog-post header image says "14 FREE TOOLS" under an H1 that says "Seven".
- Post dates appear twice.
- The digest index is 89 identical "Purplelink Daily Digest #N" titles; show each lede and group by month.
- The format-page venue codes are low-contrast lavender.

---

## 5. SEO

What passes: 0 broken internal links, one H1 per page, unique titles and descriptions, correct canonicals, correct noindex on transactional pages and digests, all JSON-LD valid, and alt text on every image.

| Priority | Issue | Fix |
|---|---|---|
| High | 11 orphan guides, plus 16 unlinked why-it-matters pages (§3) | Link them from `/guides/` and from their tool pages |
| High | All 105 sitemap `lastmod` values are 2026-09-23 [verified]. The fingerprint stamp rewrites every HTML file whenever CSS or JS changes, and IndexNow then re-submits the whole site. | In `gen_sitemap.py`, ignore commits that only change `?v=` stamps |
| High | The homepage targets agency searches (§2) | Retarget the title, description and H1 at the products |
| Med | Money-page H1s are only the brand name ("ModernTex", "Paper Review", "Vitae"), and inbound link text is "See what it does" | H1 "ModernTex, a native LaTeX editor for Mac"; Paper Review title "AI Paper Review: Pre-Submission Manuscript Critique from $9"; descriptive link text from the guides |
| Med | 38 titles over 60 characters and 45 descriptions over 160; the brand suffix is split between "\| Purplelink LLC" and "\| Purplelink" | Trim, and pick one suffix |
| Med | 20 of 23 blog posts have exactly one inbound link | The "Next step" block (§3) |
| Med | `/blog/digest/` is indexed, 3,000 words of off-topic news, and not in the sitemap | Noindex it; RSS covers subscribers |
| Low | 51 pages use the generic share card, including `vitae/` although `og/vitae.png` exists. 22 of 23 BlogPostings have no `image`. | Per-page share cards |
| Low | `/stats/` is both disallowed in robots.txt and noindexed, so Google can't read the noindex | Drop the disallow |
| Low | The 8 format pages overlap 28–56% with each other | Add venue-specific content before adding more venues |

---

## 6. GEO (being cited by ChatGPT, Claude, Perplexity and AI Overviews)

Crawl access is fine: robots.txt allows the AI bots and the static HTML carries real text. The gaps:

1. **llms.txt is stale** (§1 #4). Its summary line still describes the company as "ModernTex, Haea, and GlobePin". Rebuild it at deploy time, lead with the academic products, and add `llms-full.txt`. Suggested opening:
   > Purplelink LLC is a one-person software studio in Atlanta, founded in 2026 by Benjamin Ampel, that makes tools for academic researchers: ModernTex (a $10 native macOS LaTeX editor), Paper Review (AI pre-submission manuscript review, $9–$15), Vitae (a free macOS academic CV and submission tracker), Scholar Utility Belt (a free Chrome extension for Google Scholar), and free in-browser LaTeX and BibTeX tools.
2. **No founder credentials anywhere.** When an LLM decides whether to recommend a paid AI manuscript reviewer, "built by a published researcher" is the deciding trust signal.
   - Add a bio to About with degree, field, institution and papers.
   - Give the Person schema `sameAs` links (Google Scholar, ORCID, LinkedIn), plus `alumniOf` and `affiliation`.
   - Use one Person `@id` sitewide. The homepage says "CEO" with no `@id`; About says "Founder".
3. **No pages for the highest-intent comparisons.**
   - Add `/guides/overleaf-alternative-mac/` and `/guides/ai-paper-review-tools-compared/`, each with an honest HTML `<table>`.
   - Convert the "Decision matrix" list on `best-mac-latex-editors` to a table.
   - Add a specs and comparison table to `/moderntex/`.

   LLMs quote tables and "X vs Y" pages heavily.
4. **The research-methods content is noindexed.** The 16 `why-it-matters` pages (p-hacking, HARKing, test/train contamination) answer exactly the definitional questions LLMs cite. Merge them into one indexed, sourced pillar page (Simmons 2011, Kerr 1998, Henrich 2010) with a byline, and link it from Paper Review.
5. **No original data.** One aggregate post is enough, e.g. "X% of .bib files run through the validator had a dead DOI", or Paper Review compared with public OpenReview reviews. That would be the most citable page on the site.
6. **Tool pages open with an instruction** ("Upload a .tex file…"), not a sentence that says what the tool is. Start each with one, e.g. "Purplelink BibTeX Validator is a free online tool that checks a .bib file for…". Also:
   - Add `dateModified` to tool schema.
   - Give Scholar Utility Belt its own page. It has the most traction of anything and no page.
   - Update Press: it still says ModernTex "Version 1.0" and omits Vitae and Paper Review.
7. **Off-site mentions LLMs weight,** in rough order:
   - AlternativeTo: ModernTex vs Overleaf/TeXShop/Texifier, Vitae vs Interfolio
   - TeX.StackExchange answers where a tool genuinely solves the question
   - r/LaTeX, r/AskAcademia, r/PhD
   - Product Hunt
   - University LibGuides
   - Wikidata items referenced in `sameAs`

Also align the numbers that disagree: ModernTex is 13, 14 or 15 MB depending on the page, and Paper Review takes "under 10 minutes" in one place and "4–8 minutes" in another. Drive them from `version.json` the way Vitae already does.

---

## 7. Performance and accessibility

Measured locally without ads (uncompressed): home 625 KB / 15 requests, `/moderntex/` 640 KB, `/globepin/` 754 KB, text pages 234–319 KB. CLS is 0, there are 0 JS errors, and contrast passes everywhere except #7 above. Focus rings are visible, the skip link works and reduced motion is respected for reveals.

- **Logo:** every page preloads a 41 KB, 512×512 PNG to show it at 30px (136 pages). Use `purplelink-mark.svg` (427 B) and drop the preload.
- **`/moderntex/` LCP:** at 1920px and wider the editor screenshot is the LCP element, but it's `loading="lazy"`. Make it eager with `fetchpriority="high"`. Add `srcset` on both it and the homepage copy, since phones download the 2940px original.
- **Hero animation:** the homepage entrance holds the H1 at `opacity:0` for up to 1.3s, and LCP was 756 ms locally against about 140 ms with reduced motion. Animate `transform` only, or shorten it.
- **Images:**
  - App icons are 21–63 KB PNGs shown at 72px; convert to WebP.
  - Phone screenshots are 1206×2622; add an 800w variant.
  - 484 of 506 images are PNG.
- **Fonts and scripts:**
  - The Fraunces italic (82 KB) loads for two words and isn't preloaded; preload it on those pages or subset it.
  - `pdf-lib` (207 KB gzipped) loads up front on `/tools/pdf-tools/`; load it on first use.
- **Accessibility:**
  - 37 pages have no `<main>` landmark, including all blog posts, `/moderntex/` and `/vitae/`.
  - Hover transforms on cards and chips, and the tool spinner, ignore `prefers-reduced-motion`.
  - Nothing stops focused elements hiding under the sticky header; add `scroll-padding-top`.
  - Several targets are under 44px: FAQ summaries at 26px, chips at 40px.
- **AdSense in production** (estimated, not measured): about 150–250 KB of JS, 0.5–1.5 MB once ads fill, 200–600 ms of mobile main-thread time. Auto Ads also insert units without reserved space, so the CLS of 0 won't hold. This is another reason to use fixed slots on content pages only.
- **Netlify headers:** confirm with `curl -I` in production that `/assets/fonts/*` doesn't get two merged `Cache-Control` values from the overlapping `/assets/*` rule.

---

## 8. Suggested order of work

1. **Day 1, bugs:**
   - §1 #1–#3, #6–#11 and #13.
   - Remove AdSense from the paid, checkout, upload and status pages.
   - Regenerate llms.txt.
   - Generate the 6 share images.
   - Re-shoot the ModernTex hero screenshot.
2. **Week 1, structure:**
   - Shared nav and footer partials.
   - The `/products/` hub.
   - Link the orphan guides.
   - Fix the sitemap dates.
   - Add the "Next step" block, starting with the 13 blog posts that link nowhere.
3. **Week 2, selling:**
   - Homepage repositioning (title, "Before you submit" section, contact line).
   - Founder About page with a photo and credentials.
   - Sample outputs on the paid tools, Vitae screenshots, refund line everywhere, success-page next steps.
   - Kits out of the primary nav.
4. **Weeks 3–4, polish and authority:**
   - Bring tools and paid pages into the editorial template.
   - Collapse radii, shadows and type scale into tokens.
   - The two comparison guides.
   - The methodology pillar page.
   - One original-data post.
   - AlternativeTo, TeX.SE and Product Hunt.
