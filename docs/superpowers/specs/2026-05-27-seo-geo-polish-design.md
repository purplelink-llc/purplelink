# SEO, GEO & Professional Polish — Design Spec
**Date:** 2026-05-27  
**Project:** purplelink.llc  
**Scope:** Approach C — Full Content Expansion  
**Goal:** Strengthen Purplelink brand presence for app users; improve discoverability via search engines and AI systems.

---

## Context

The site is a static HTML site deployed on Netlify. All pages are already well-structured with canonical URLs, OG/Twitter meta, JSON-LD structured data on the homepage, and a working sitemap + robots.txt + llms.txt. The audit showed zero broken links or JS errors.

**Primary audience:** Future users of ModernTex, Haea, and GlobePin.  
**Strategy:** Brand-first, company-forward (not founder-forward). All three apps treated equally.  
**No social media accounts exist** — no social links added until accounts are set up.

---

## Section 1 — New Pages

### 1.1 Privacy Policy — `/privacy/index.html`
- **Why:** Legally required (GDPR, CAN-SPAM) for email collection via the three waitlist forms. Currently there is no policy linked anywhere.
- **Content:** What data is collected (email address only), how it's used (one launch notification email per app), retention policy (deleted on request), no third-party sale or sharing, contact address (`ben@purplelink.llc`). Plain English, not legalese. ~300 words.
- **Linked from:** Footer (new link row) + one-line fine print under each waitlist form.

### 1.2 About — `/about/index.html`
- **Why:** Entity establishment for SEO and GEO. Gives search engines and AI systems a canonical "what is Purplelink" reference page. Company-forward — no founder bio or photo.
- **Content:** Company mission ("making software that lasts"), three app pillars (ModernTex / Haea / GlobePin), founding context (Atlanta, 2026, Georgia LLC), values (native apps, privacy-first, craft over speed). Includes `Organization` JSON-LD schema with fuller detail than homepage.
- **Linked from:** Top nav (added as 6th item before Contact) + footer.

### 1.3 Press / Media Kit — `/press/index.html`
- **Why:** Makes it easy for journalists, app review sites, and bloggers to write accurately about Purplelink and its apps.
- **Content:** Company boilerplate (2–3 sentences), per-app one-liners, logo download section (linking to existing `/assets/purplelink-logo.png` and `/assets/purplelink-logo-v2.png`), contact email for press inquiries. Single page, minimal.
- **Linked from:** Footer only.

### 1.4 Custom 404 — `/404.html`
- **Why:** Any unknown URL currently serves Netlify's generic error page, breaking the user experience.
- **Content:** On-brand error message in Purplelink voice, links to Home and Products. Matches site nav and footer exactly.
- **Netlify routing:** Add `[[redirects]] from = "/*" to = "/404.html" status = 404` to `netlify.toml`.

### 1.5 Three New Blog Posts
Each ~400–600 words, written in the same first-person voice as "Starting Purplelink." Filed at `/blog/[slug]/index.html` matching the existing pattern.

| Slug | Title | SEO target |
|------|-------|-----------|
| `what-globepin-does-differently` | "What GlobePin does that no other travel app does" | travel tracking app, flight tracker iOS |
| `why-haea-is-on-device` | "Why we built Haea on-device" | private health app iOS, on-device health analytics |
| `the-latex-editor-academics-want` | "The LaTeX editor that academics actually want" | LaTeX editor macOS, academic writing app mac |

- Blog index (`/blog/index.html`) updated with all three new cards.
- Sitemap updated with all three new URLs.

---

## Section 2 — Changes to Existing Pages

### 2.1 Product Pages — FAQ Section (ModernTex, Haea, GlobePin)
Each product page gets a **FAQ section** above the footer with 4–5 questions tailored to that app.

**Interaction:** Accordion (click to expand). Closed by default.  
**Schema:** `FAQPage` JSON-LD added to each product page's `<head>`. Enables Google rich snippets and gives AI systems structured facts.

Sample questions per app:

**ModernTex:** When does ModernTex ship? / What macOS version is required? / Is there a free trial? / How is it different from TeXShop or Overleaf? / Does it support multi-file projects?

**Haea:** When does Haea ship? / Is there a free tier? / Does Haea sync to the cloud? / What health data sources does it support? / Is it HIPAA-compliant?

**GlobePin:** When does GlobePin ship? / How do I log a flight? / Does it sync across devices? / Is there a free tier? / What's the difference between GlobePin and other travel trackers?

### 2.2 Product Pages — App Store Badge
Below the hero CTA on each product page, add:
- iOS apps: "Coming to the App Store" badge (SVG, official Apple badge style)
- macOS app (ModernTex): "Coming to the Mac App Store" badge
- Both link to `#waitlist` for now. The `href` is the only thing that changes at launch.

### 2.3 Product Pages — Waitlist Form Fine Print
Add one line below each waitlist form submit button:
> "We'll only use your email to notify you at launch. [Privacy Policy](/privacy/)"

### 2.4 All Pages — Footer Expansion
Add a second row of footer links below the existing brand/location line:

`About · Press · Privacy · Blog · Changelog`

All internal links. No external social links (no accounts exist yet).

### 2.5 Navigation — About Link
Add **About** to the primary nav on all pages, between Changelog and Contact:

`Software · Products · Blog · Changelog · About · Contact`

---

## Section 3 — Technical & Metadata

### 3.1 Breadcrumb Structured Data
Add `BreadcrumbList` JSON-LD to all inner pages. Pages covered:

`/moderntex/`, `/haea/`, `/globepin/`, `/blog/`, `/blog/[post]/`, `/changelog/`, `/about/`, `/press/`, `/privacy/`

Format: Home → [Section] → [Page] (3-level for blog posts, 2-level for top sections).

### 3.2 Theme Color Meta Tag
Add to `<head>` on all pages:
```html
<meta name="theme-color" content="#7c3aed">
```
Sets the browser chrome to Purplelink purple on mobile. Use the existing `--purple` CSS variable value.

### 3.3 Web App Manifest
New file: `/site/manifest.json`

```json
{
  "name": "Purplelink LLC",
  "short_name": "Purplelink",
  "description": "Making software that lasts.",
  "start_url": "/",
  "display": "browser",
  "theme_color": "#7c3aed",
  "background_color": "#faf9fb",
  "icons": [
    { "src": "/assets/purplelink-logo.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/assets/purplelink-logo.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Linked from all pages: `<link rel="manifest" href="/manifest.json">`.

### 3.4 llms.txt — Expanded
Current file is well-structured but sparse on facts. Additions:
- Per-app: pricing tiers, privacy model, key differentiators, target user description
- Company: founding date, EIN status, CEO name, contact email, NAICS code
- FAQ-style Q&A block for common questions
- Links to all pages including new ones (`/about/`, `/press/`, `/privacy/`)
- Remove the stale "business domain being established" note (already done)

### 3.5 Sitemap.xml Updates
- Add entries for `/about/`, `/press/`, `/privacy/`, and all three new blog posts
- Blog posts: `changefreq = never`, `priority = 0.7`
- New static pages: `changefreq = yearly`, `priority = 0.6`

### 3.6 Netlify 404 Routing
Add to `netlify.toml`:
```toml
[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

---

## Deliverables Summary

| # | Type | Deliverable |
|---|------|-------------|
| 1 | New page | `/privacy/index.html` |
| 2 | New page | `/about/index.html` |
| 3 | New page | `/press/index.html` |
| 4 | New page | `/404.html` |
| 5 | New post | `/blog/what-globepin-does-differently/index.html` |
| 6 | New post | `/blog/why-haea-is-on-device/index.html` |
| 7 | New post | `/blog/the-latex-editor-academics-want/index.html` |
| 8 | Edit | FAQ section + schema on `/moderntex/`, `/haea/`, `/globepin/` |
| 9 | Edit | App Store badges on all three product pages |
| 10 | Edit | Waitlist fine print + privacy link on all three product pages |
| 11 | Edit | Footer link row on all pages |
| 12 | Edit | About added to nav on all pages |
| 13 | Edit | Blog index updated with 3 new post cards |
| 14 | Technical | BreadcrumbList JSON-LD on all inner pages |
| 15 | Technical | `theme-color` meta on all pages |
| 16 | New file | `/manifest.json` + manifest link on all pages |
| 17 | Edit | `llms.txt` expanded |
| 18 | Edit | `sitemap.xml` updated |
| 19 | Edit | `netlify.toml` 404 redirect |

---

## Out of Scope
- Social media accounts or links (none exist yet — add when set up)
- Founder/personal brand content
- App Store submissions or real App Store links
- Analytics or tracking scripts
- Backend or database changes (site remains static)
