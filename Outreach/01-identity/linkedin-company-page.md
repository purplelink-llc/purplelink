# LinkedIn Company Page — Purplelink LLC

**Target URL:** `linkedin.com/company/purplelinkhq` · **fallback:** `getpurplelink`

## Setup checklist

- [ ] Sign in to LinkedIn (personal account; required as admin)
- [ ] Go to https://www.linkedin.com/company/setup/new/ and choose "Small business"
- [ ] **Page name:** Purplelink LLC
- [ ] **Public URL:** `purplelinkhq` (or `getpurplelink` if first is taken)
- [ ] **Website:** `https://purplelink.llc`
- [ ] **Industry:** Software Development
- [ ] **Company size:** 1
- [ ] **Type:** Privately held
- [ ] **Tagline** (max 120 chars): `Native macOS & iOS apps + free academic tools. Atlanta-based studio. Making software that lasts.`
- [ ] **Logo:** `Social Media/assets/profile-light-1000.png` (already generated)
- [ ] **Cover image:** `Social Media/assets/cover-linkedin-1128x191.png` (already generated)

## About section (paste verbatim)

> Purplelink LLC is a one-person software studio in Atlanta, Georgia, founded in 2026 by Benjamin Ampel. The studio ships native macOS and iOS apps and a set of free web tools for academic writing — LaTeX compilation, BibTeX validation, citation generation, Markdown conversion — that process files in memory and never store them.
>
> **Products in development (2026):**
> • ModernTex — native macOS LaTeX studio for researchers.
> • Haea — on-device iOS health analytics; data never leaves your iPhone.
> • GlobePin — travel mapping for iOS, with a 3D globe and a flight log.
>
> **Free open tools at purplelink.llc/tools** — built for academic authors, no account required, files processed in memory only.
>
> Privacy is an architectural constraint, not a marketing position. The apps are built so the data can't leave the device. The website itself uses cookieless Cloudflare Web Analytics; there's no tracking pixel, no third-party SDKs, no consent banner needed.

## First-4-weeks posting calendar

Post Mondays 10am ET. Each is ~700 chars and links to a page on the site.

### Week 1 — Studio intro
> I'm Benjamin Ampel, founder of Purplelink LLC — a one-person software studio in Atlanta building native macOS and iOS apps with privacy as an architectural constraint, not a marketing position.
>
> Three apps coming in 2026: GlobePin (travel mapping), Haea (on-device health analytics), and ModernTex (a native LaTeX studio for researchers). Plus a growing library of free tools for academic writing at purplelink.llc/tools — no account, no install, files processed in memory only.
>
> Following along here as we ship.
>
> #IndieDev #macOS #iOS #AppleDeveloper

### Week 2 — Tools highlight
> If you've ever had a BibTeX bibliography break on submission day, you know the cryptic-error feeling.
>
> I built a free BibTeX Validator that catches the eight most common failure modes — including AI-hallucinated citations against CrossRef and Semantic Scholar. Runs in your browser. Files never leave your machine.
>
> 👉 purplelink.llc/tools/bib-validator
>
> Pairs with a longer guide on the recurring BibTeX errors that derail builds: purplelink.llc/guides/fix-bibtex-errors
>
> #LaTeX #AcademicWriting #PhDLife

### Week 3 — Privacy stance
> "Privacy-first" gets used loosely, so here's what it concretely means at Purplelink:
>
> Haea (our upcoming iOS health analytics app) processes everything on-device. No cloud sync to our servers. No third-party SDKs. No analytics calls. The data — sleep, nutrition, biometrics — is stored in your iPhone's Apple Health and analyzed locally.
>
> That's an architectural decision, not a toggle you have to find. The app literally cannot leak data because the code that would leak it doesn't exist.
>
> 👉 purplelink.llc/haea
>
> #PrivacyByDesign #iOS #HealthTech

### Week 4 — Comparison guide
> Just published an honest comparison of LaTeX editors that work on Mac in 2026: TeXShop, Texifier, Octree, VS Code, Overleaf, and our upcoming ModernTex.
>
> No affiliate links, no rankings padding. Most academics should pick TeXShop. People who want polished and modern should pick Texifier. ModernTex is the right answer when academic manuscript workflow is your dominant use case (and it's not shipping until 2026).
>
> 👉 purplelink.llc/guides/best-mac-latex-editors
>
> #LaTeX #AcademicWriting #macOS

---

## After registering — give me the URL

Once the page is live, paste the URL into our next session (or just edit `site/index.html` line ~70 to add `"https://www.linkedin.com/company/purplelinkhq"` to the `sameAs` array in the Organization JSON-LD). I can also do the edit for you.
