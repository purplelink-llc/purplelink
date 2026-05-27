# SEO, GEO & Professional Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 19 deliverables to purplelink.llc — new pages, FAQ sections, App Store badges, structured data, and metadata improvements — to strengthen SEO/GEO discoverability and professional polish.

**Architecture:** Static HTML site served from `/Volumes/Extreme SSD/Purplelink LLC/site/`. No build system. All changes are direct HTML/CSS/JSON edits. Netlify deploys from the `site/` directory. Every page shares the same `styles.css` and `site.js` from the root.

**Tech Stack:** Static HTML5, CSS custom properties (OKLCH color tokens), JSON-LD structured data, Netlify Forms, Netlify redirects via `netlify.toml`.

---

## File Map

**New files to create:**
- `site/manifest.json` — web app manifest
- `site/404.html` — custom 404 page
- `site/privacy/index.html` — Privacy Policy page
- `site/about/index.html` — About Purplelink page
- `site/press/index.html` — Press / Media Kit page
- `site/blog/what-globepin-does-differently/index.html` — blog post
- `site/blog/why-haea-is-on-device/index.html` — blog post
- `site/blog/the-latex-editor-academics-want/index.html` — blog post

**Existing files to modify:**
- `netlify.toml` — add 404 redirect
- `site/sitemap.xml` — add 8 new URLs
- `site/llms.txt` — expand with app facts + FAQ block
- `site/styles.css` — add FAQ accordion styles, footer-links styles, App Store badge styles
- `site/index.html` — theme-color, manifest, About nav, footer links, BreadcrumbList
- `site/moderntex/index.html` — theme-color, manifest, About nav, footer links, FAQ section, App Store badge, waitlist fine print, FAQPage JSON-LD, BreadcrumbList
- `site/haea/index.html` — same as moderntex
- `site/globepin/index.html` — same as moderntex
- `site/blog/index.html` — theme-color, manifest, About nav, footer links, 3 new post cards, BreadcrumbList
- `site/blog/starting-purplelink/index.html` — theme-color, manifest, About nav, footer links, BreadcrumbList
- `site/changelog/index.html` — theme-color, manifest, About nav, footer links, BreadcrumbList

---

## Task 1: netlify.toml — 404 redirect

**Files:**
- Modify: `netlify.toml`

- [ ] **Step 1: Add the 404 redirect rule**

Open `netlify.toml` and append at the end:

```toml
[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

- [ ] **Step 2: Verify the file**

The full file should end with the new block. Confirm no syntax errors (TOML is sensitive to indentation in table headers).

- [ ] **Step 3: Commit**

```bash
git add netlify.toml
git commit -m "feat: add custom 404 redirect in netlify.toml"
```

---

## Task 2: manifest.json

**Files:**
- Create: `site/manifest.json`

- [ ] **Step 1: Create the manifest file**

Create `site/manifest.json` with this exact content:

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

- [ ] **Step 2: Commit**

```bash
git add site/manifest.json
git commit -m "feat: add web app manifest"
```

---

## Task 3: CSS additions (FAQ accordion, footer links, App Store badge)

**Files:**
- Modify: `site/styles.css`

Add all new CSS in one task so product-page tasks (10–12) and global-nav tasks can reference finalized classes.

- [ ] **Step 1: Add FAQ accordion styles**

Append to the end of `site/styles.css`:

```css
/* ─── FAQ Accordion ───────────────────────────────────────────────────── */

.faq-section {
  padding: clamp(48px, 8vw, 96px) clamp(24px, 6vw, 80px);
  max-width: 760px;
  margin: 0 auto;
}

.faq-section h2 {
  font-family: 'Fraunces', serif;
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 600;
  margin-bottom: 2rem;
  color: var(--ink);
}

.faq-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.faq-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
}

.faq-item + .faq-item {
  margin-top: 6px;
}

.faq-item summary {
  padding: 16px 20px;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: var(--ink);
  user-select: none;
}

.faq-item summary::-webkit-details-marker { display: none; }

.faq-item summary::after {
  content: '+';
  font-size: 1.2rem;
  font-weight: 400;
  opacity: 0.4;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.faq-item[open] summary::after {
  transform: rotate(45deg);
}

.faq-item .faq-body {
  padding: 0 20px 16px;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--ink-dim);
}

/* ─── Footer links row ────────────────────────────────────────────────── */

.footer {
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.footer-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 20px;
}

.footer-links {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.footer-links a {
  font-size: 0.78rem;
  color: oklch(99% 0.003 310 / 0.45);
  text-decoration: none;
  transition: color 0.15s;
}

.footer-links a:hover {
  color: oklch(99% 0.003 310 / 0.8);
}

/* ─── App Store badge ─────────────────────────────────────────────────── */

.store-badge-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.store-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: #000;
  color: #fff;
  border-radius: 10px;
  padding: 8px 16px;
  text-decoration: none;
  font-size: 0.78rem;
  line-height: 1.2;
  border: 1px solid rgba(255,255,255,0.15);
  transition: opacity 0.15s;
}

.store-badge:hover { opacity: 0.8; }

.store-badge svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  fill: #fff;
}

.store-badge-text {
  display: flex;
  flex-direction: column;
}

.store-badge-coming {
  font-size: 0.65rem;
  opacity: 0.7;
  letter-spacing: 0.01em;
}

.store-badge-label {
  font-size: 0.85rem;
  font-weight: 600;
}

/* ─── Waitlist fine print ─────────────────────────────────────────────── */

.waitlist-fine-print {
  font-size: 0.75rem;
  color: var(--ink-dim);
  opacity: 0.6;
  margin-top: 10px;
  text-align: center;
}

.waitlist-fine-print a {
  color: inherit;
  text-decoration: underline;
}

/* ─── Static page (privacy / about / press / 404) ────────────────────── */

.static-page {
  max-width: 680px;
  margin: 0 auto;
  padding: clamp(48px, 8vw, 96px) clamp(24px, 6vw, 80px);
}

.static-page h1 {
  font-family: 'Fraunces', serif;
  font-size: clamp(2rem, 4vw, 3rem);
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--ink);
}

.static-page .page-meta {
  font-size: 0.82rem;
  color: var(--ink-dim);
  opacity: 0.6;
  margin-bottom: 2.5rem;
}

.static-page h2 {
  font-family: 'Fraunces', serif;
  font-size: 1.25rem;
  font-weight: 600;
  margin: 2rem 0 0.6rem;
  color: var(--ink);
}

.static-page p, .static-page li {
  font-size: 0.95rem;
  line-height: 1.75;
  color: var(--ink-dim);
}

.static-page ul { padding-left: 1.4em; }
.static-page li { margin-bottom: 0.4em; }

.static-page a {
  color: var(--purple);
  text-decoration: underline;
}

/* ─── Press page ──────────────────────────────────────────────────────── */

.press-app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
  margin: 1.5rem 0;
}

.press-app-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
}

.press-app-card h3 {
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 6px;
  color: var(--ink);
}

.press-app-card p {
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--ink-dim);
}

.press-logo-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin: 1.5rem 0;
}

.press-logo-row a {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--ink);
  text-decoration: none;
  transition: border-color 0.15s;
}

.press-logo-row a:hover { border-color: var(--purple); }

/* ─── About page ──────────────────────────────────────────────────────── */

.about-values {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin: 1.5rem 0;
}

.about-value {
  padding: 18px;
  background: var(--purple-xlight);
  border-radius: 10px;
}

.about-value h3 {
  font-size: 0.9rem;
  font-weight: 700;
  margin-bottom: 6px;
  color: var(--ink);
}

.about-value p {
  font-size: 0.83rem;
  line-height: 1.6;
  color: var(--ink-dim);
}

/* ─── 404 page ────────────────────────────────────────────────────────── */

.not-found {
  text-align: center;
  padding: clamp(80px, 12vw, 140px) clamp(24px, 6vw, 80px);
}

.not-found .error-code {
  font-family: 'Fraunces', serif;
  font-size: clamp(5rem, 12vw, 9rem);
  font-weight: 800;
  color: var(--purple-light);
  line-height: 1;
  margin-bottom: 0.25rem;
}

.not-found h1 {
  font-family: 'Fraunces', serif;
  font-size: clamp(1.5rem, 3vw, 2.25rem);
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--ink);
}

.not-found p {
  font-size: 1rem;
  color: var(--ink-dim);
  margin-bottom: 2rem;
}

.not-found-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
```

- [ ] **Step 2: Update `.footer` to use the new two-row layout**

The existing `.footer` rule (around line 731) sets `flex-direction: row`. The new CSS above overrides it to `column`. Verify the existing `.footer` rule doesn't conflict. If it does, remove `align-items` and `justify-content` from the old rule — the `.footer-top` class handles that now.

The old `.footer` block is:
```css
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px clamp(24px, 6vw, 80px);
  background: var(--ink);
  border-top: 1px solid oklch(99% 0.003 310 / 0.1);
  color: oklch(99% 0.003 310);
}
```

Replace with:
```css
.footer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px clamp(24px, 6vw, 80px);
  background: var(--ink);
  border-top: 1px solid oklch(99% 0.003 310 / 0.1);
  color: oklch(99% 0.003 310);
}
```

- [ ] **Step 3: Commit**

```bash
git add site/styles.css
git commit -m "feat: add CSS for FAQ accordion, footer links, App Store badge, static pages"
```

---

## Task 4: Global changes to all existing pages

Apply four changes to every existing page: `<meta name="theme-color">`, `<link rel="manifest">`, About in nav, and new footer structure.

**Files (all 7 existing pages):**
- `site/index.html`
- `site/moderntex/index.html`
- `site/haea/index.html`
- `site/globepin/index.html`
- `site/blog/index.html`
- `site/blog/starting-purplelink/index.html`
- `site/changelog/index.html`

### Pattern to apply to every `<head>` section

Add these two lines immediately after `<link rel="icon" ...>`:

```html
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
```

### Pattern to apply to every `<nav>` section

Current nav (all pages):
```html
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/#contact">Contact</a>
```

Replace with:
```html
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
```

### Pattern to apply to every `<footer>` section

Current footer (all pages):
```html
    <footer class="footer">
      <div class="footer-brand">
        <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
        <span>Purplelink LLC</span>
      </div>
      <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
    </footer>
```

Replace with:
```html
    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
```

- [ ] **Step 1: Apply pattern to `site/index.html`**

(Three edits: head, nav, footer)

- [ ] **Step 2: Apply pattern to `site/moderntex/index.html`**

- [ ] **Step 3: Apply pattern to `site/haea/index.html`**

- [ ] **Step 4: Apply pattern to `site/globepin/index.html`**

- [ ] **Step 5: Apply pattern to `site/blog/index.html`**

- [ ] **Step 6: Apply pattern to `site/blog/starting-purplelink/index.html`**

- [ ] **Step 7: Apply pattern to `site/changelog/index.html`**

- [ ] **Step 8: Verify in browser**

Open `http://localhost:4200` (or run a local server: `python3 -m http.server 4200 --directory site`). Check:
- Top nav shows "About" between Changelog and Contact on every page
- Footer shows two rows on every page
- In Chrome DevTools > Application > Manifest, the manifest is loaded
- Theme color appears in mobile browser chrome (test at 375px width)

- [ ] **Step 9: Commit**

```bash
git add site/index.html site/moderntex/index.html site/haea/index.html site/globepin/index.html site/blog/index.html "site/blog/starting-purplelink/index.html" site/changelog/index.html
git commit -m "feat: add theme-color, manifest, About nav, footer links to all pages"
```

---

## Task 5: Privacy Policy page

**Files:**
- Create: `site/privacy/index.html`

- [ ] **Step 1: Create the file**

Create `site/privacy/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>Privacy Policy — Purplelink LLC</title>
    <meta name="description" content="Purplelink LLC privacy policy. We collect only your email address for waitlist notifications and nothing else.">
    <link rel="canonical" href="https://purplelink.llc/privacy/">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Privacy Policy", "item": "https://purplelink.llc/privacy/" }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content" class="static-page">
      <h1>Privacy Policy</h1>
      <p class="page-meta">Effective date: May 27, 2026 · <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a></p>

      <h2>What we collect</h2>
      <p>When you join a waitlist on this site, we collect your email address and nothing else. We do not collect your name, location, device information, or any other personal data.</p>

      <h2>How we use it</h2>
      <p>Your email is used for one purpose: to notify you when the app you signed up for launches. You will receive at most one email per app — the launch announcement. We do not send newsletters, marketing emails, or third-party promotions.</p>

      <h2>Who we share it with</h2>
      <p>Nobody. Your email address is stored by Netlify (our hosting provider) via Netlify Forms and is not shared with, sold to, or disclosed to any third party for any purpose.</p>

      <h2>How long we keep it</h2>
      <p>Your email is retained until the relevant app launches and the notification is sent, at which point it is deleted. You may request deletion at any time by emailing <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> with the subject line "Delete my data."</p>

      <h2>Your rights</h2>
      <p>If you are located in the European Union or United Kingdom, you have rights under GDPR including the right to access, correct, or delete your personal data. To exercise any of these rights, email <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>
      <p>If you are a California resident, you have rights under CCPA. We do not sell personal information.</p>

      <h2>Cookies and tracking</h2>
      <p>This site does not use cookies, analytics scripts, or any tracking technology. No data is collected about how you browse or interact with the site.</p>

      <h2>Contact</h2>
      <p>Questions about this policy? Email <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>.</p>
    </main>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add site/privacy/index.html
git commit -m "feat: add Privacy Policy page"
```

---

## Task 6: About page

**Files:**
- Create: `site/about/index.html`

- [ ] **Step 1: Create the file**

Create `site/about/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>About — Purplelink LLC</title>
    <meta name="description" content="Purplelink LLC is a software studio based in Atlanta, Georgia building native macOS and iOS apps — ModernTex, Haea, and GlobePin — with craft and longevity.">
    <link rel="canonical" href="https://purplelink.llc/about/">
    <meta property="og:title" content="About Purplelink LLC">
    <meta property="og:description" content="A software studio in Atlanta building native macOS and iOS apps that last.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://purplelink.llc/about/">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Organization",
          "@id": "https://purplelink.llc/#organization",
          "name": "Purplelink LLC",
          "legalName": "Purplelink LLC",
          "url": "https://purplelink.llc/",
          "logo": "https://purplelink.llc/assets/purplelink-logo.png",
          "description": "Purplelink LLC is a software studio based in Atlanta, Georgia building native macOS and iOS apps — ModernTex, Haea, and GlobePin — with an emphasis on craft, longevity, and privacy.",
          "foundingDate": "2026",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Atlanta",
            "addressRegion": "GA",
            "addressCountry": "US"
          },
          "contactPoint": {
            "@type": "ContactPoint",
            "email": "ben@purplelink.llc",
            "contactType": "general inquiries"
          },
          "knowsAbout": ["macOS app development", "iOS app development", "Swift", "SwiftUI", "applied AI", "LaTeX", "health analytics"],
          "slogan": "Making software that lasts."
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "About", "item": "https://purplelink.llc/about/" }
          ]
        }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/" aria-current="page">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content" class="static-page">
      <h1>About Purplelink</h1>
      <p class="page-meta">Atlanta, Georgia · Founded 2026 · Georgia LLC</p>

      <p>Purplelink LLC is a software studio building native macOS and iOS apps. The mission is simple: make software that solves real problems, works reliably, and lasts — not software that ships fast and deteriorates.</p>

      <h2>What we build</h2>
      <p>Three apps are in active development:</p>

      <div class="about-values" style="margin-bottom: 2rem;">
        <div class="about-value">
          <h3><a href="/moderntex/" style="color: inherit; text-decoration: none;">ModernTex</a></h3>
          <p>A native macOS LaTeX studio for academic researchers. Multi-file editing, synchronized PDF preview, BibTeX autocomplete, and submission-readiness checks in one coherent interface.</p>
        </div>
        <div class="about-value">
          <h3><a href="/haea/" style="color: inherit; text-decoration: none;">Haea</a></h3>
          <p>An on-device iOS health analytics platform. Advanced ML models for recovery, circadian rhythm, and biological age — all running locally with no cloud sync.</p>
        </div>
        <div class="about-value">
          <h3><a href="/globepin/" style="color: inherit; text-decoration: none;">GlobePin</a></h3>
          <p>An iOS travel tracking app for mapping everywhere you've been, every flight taken, and every destination on the list. 3D globe, stats, goals, and shareable postcards.</p>
        </div>
      </div>

      <h2>How we build</h2>

      <div class="about-values">
        <div class="about-value">
          <h3>Native first</h3>
          <p>Every app is written in Swift for the Apple platform it belongs on. No cross-platform shortcuts. Fast, native, and coherent.</p>
        </div>
        <div class="about-value">
          <h3>Privacy by design</h3>
          <p>Haea runs fully on-device. No cloud sync, no analytics SDKs, no data sold. Privacy isn't a policy — it's an architecture decision.</p>
        </div>
        <div class="about-value">
          <h3>Craft over speed</h3>
          <p>Software that lasts takes more time to build. The tradeoff is worth it: apps people actually keep on their phones and open every day.</p>
        </div>
        <div class="about-value">
          <h3>Small and focused</h3>
          <p>Purplelink is a one-person studio. Small means accountable: every line of code and every design decision has an owner.</p>
        </div>
      </div>

      <h2>Contact</h2>
      <p>For inquiries, press, or general questions: <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a></p>
    </main>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/" aria-current="page">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add site/about/index.html
git commit -m "feat: add About page with Organization JSON-LD"
```

---

## Task 7: Press / Media Kit page

**Files:**
- Create: `site/press/index.html`

- [ ] **Step 1: Create the file**

Create `site/press/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>Press — Purplelink LLC</title>
    <meta name="description" content="Press and media kit for Purplelink LLC — company boilerplate, app descriptions, logo downloads, and press contact.">
    <link rel="canonical" href="https://purplelink.llc/press/">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Press", "item": "https://purplelink.llc/press/" }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content" class="static-page">
      <h1>Press &amp; Media</h1>
      <p class="page-meta">For press inquiries: <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a></p>

      <h2>About Purplelink LLC</h2>
      <p>Purplelink LLC is a software studio based in Atlanta, Georgia, building native macOS and iOS apps with an emphasis on craft, longevity, and user privacy. The company is developing three apps: ModernTex (macOS LaTeX studio for academic researchers), Haea (on-device iOS health analytics platform), and GlobePin (iOS travel tracking app). Founded in 2026.</p>

      <h2>Apps in development</h2>

      <div class="press-app-grid">
        <div class="press-app-card">
          <h3>ModernTex — macOS</h3>
          <p>A native macOS LaTeX manuscript studio for academic researchers. Multi-file editing, synchronized PDF preview, BibTeX autocomplete, plain-language error diagnostics, and submission-readiness checks. Built in Swift for macOS 14+.</p>
        </div>
        <div class="press-app-card">
          <h3>Haea — iOS</h3>
          <p>An on-device iOS health analytics platform. Integrates sleep, nutrition, weight, and biometric data with advanced ML models including Kalman filtering and Granger causality analysis. All computation runs locally — no cloud sync, no third-party SDKs.</p>
        </div>
        <div class="press-app-card">
          <h3>GlobePin — iOS</h3>
          <p>An iOS travel tracking app for logging places visited, flights taken, and destinations planned. Features a 3D globe view, statistics dashboard, travel goals, anniversary reminders, and shareable travel postcards via iCloud sync.</p>
        </div>
      </div>

      <h2>Logo downloads</h2>
      <p>Use these assets in editorial coverage. Do not alter the logo colors or proportions.</p>

      <div class="press-logo-row">
        <a href="/assets/purplelink-logo.png" download>
          <img src="/assets/purplelink-logo.png" alt="" width="20" height="20">
          Purplelink Logo (PNG)
        </a>
        <a href="/assets/purplelink-logo-v2.png" download>
          <img src="/assets/purplelink-logo-v2.png" alt="" width="20" height="20">
          Purplelink Logo v2 (PNG)
        </a>
        <a href="/assets/purplelink-mark.svg" download>
          Purplelink Mark (SVG)
        </a>
      </div>

      <h2>Press contact</h2>
      <p>For interview requests, review copies, screenshots, or other press inquiries: <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a></p>
    </main>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/" aria-current="page">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add site/press/index.html
git commit -m "feat: add Press / Media Kit page"
```

---

## Task 8: Custom 404 page

**Files:**
- Create: `site/404.html`

- [ ] **Step 1: Create the file**

Create `site/404.html` (note: top-level, not in a subdirectory — Netlify requires `/404.html`):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>Page Not Found — Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content" class="not-found">
      <p class="error-code">404</p>
      <h1>Nothing here.</h1>
      <p>That page doesn't exist — or maybe it moved. Head back somewhere useful.</p>
      <div class="not-found-actions">
        <a class="btn btn-primary" href="/">Go home</a>
        <a class="btn btn-ghost" href="/#projects">See our apps</a>
      </div>
    </main>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add site/404.html
git commit -m "feat: add custom 404 page"
```

---

## Task 9: Blog post — GlobePin

**Files:**
- Create: `site/blog/what-globepin-does-differently/index.html`

- [ ] **Step 1: Create the file**

Create `site/blog/what-globepin-does-differently/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>What GlobePin does that no other travel app does — Purplelink LLC</title>
    <meta name="description" content="Why GlobePin is different from every travel tracking app on the market — and what we built that the others missed.">
    <link rel="canonical" href="https://purplelink.llc/blog/what-globepin-does-differently/">
    <meta property="og:title" content="What GlobePin does that no other travel app does">
    <meta property="og:description" content="Why GlobePin is different from every travel tracking app on the market — and what we built that the others missed.">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://purplelink.llc/blog/what-globepin-does-differently/">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="What GlobePin does that no other travel app does">
    <meta name="twitter:description" content="Why GlobePin is different from every travel tracking app on the market — and what we built that the others missed.">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "BlogPosting",
          "headline": "What GlobePin does that no other travel app does",
          "description": "Why GlobePin is different from every travel tracking app on the market — and what we built that the others missed.",
          "datePublished": "2026-05-27",
          "author": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "publisher": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "url": "https://purplelink.llc/blog/what-globepin-does-differently/"
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://purplelink.llc/blog/" },
            { "@type": "ListItem", "position": 3, "name": "What GlobePin does differently", "item": "https://purplelink.llc/blog/what-globepin-does-differently/" }
          ]
        }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <a class="back-link" href="/blog/">← All posts</a>

    <div class="post-hero">
      <p class="post-date">May 27, 2026</p>
      <h1 class="post-title">What GlobePin does that no other travel app does</h1>
      <p class="post-lede">Every travel tracker on the App Store solves a piece of the problem. Most miss the same things. Here's what we built differently — and why.</p>
    </div>

    <article id="main-content" class="post-body">
      <p>I've tried a lot of travel tracking apps. Most of them fall into one of two categories: the social-network kind that wants you to check in for other people's benefit, and the minimal kind that's basically a glorified spreadsheet. Neither is what I was looking for.</p>

      <p>What I wanted was something in between: a complete personal travel record. Not just a list of countries visited, but a real map. Every city. Every flight. Every place I'd been and where I wanted to go next. A record I'd actually enjoy looking at.</p>

      <p>GlobePin started as that scratch — and as I built it, I kept running into the same gaps in the existing options. Here's what we did differently.</p>

      <h2>The complete flight record</h2>

      <p>Most travel apps track destinations, not journeys. You mark a country as visited and move on. But the journey matters. The eleven-hour flight to Tokyo, the connection through Heathrow, the short hop from Barcelona to Madrid — those are part of the travel story.</p>

      <p>GlobePin tracks every flight: departure airport, arrival airport, date, distance, duration. That data feeds into stats that actually mean something — total miles flown, flight count by year, longest route, most visited airports. For frequent travelers, this record becomes genuinely interesting over time.</p>

      <h2>A 3D globe that earns its place</h2>

      <p>Map apps use flat projections. Most travel trackers do too. The problem is that a flat map distorts how the world actually looks, and it makes long-haul routes look strange — a direct flight from New York to Tokyo crossing the Pacific isn't a straight line on a Mercator projection.</p>

      <p>GlobePin has a 3D globe view because it shows routes the way they actually exist on the earth's surface. It's not a gimmick — it changes how you see your own travel history. Watching great circle routes arc across the sphere gives context that a flat map can't.</p>

      <h2>Travel goals that aren't checklists</h2>

      <p>Most travel goal features are just checklist apps in disguise. Check off countries. Unlock badges. It's gamification for gamification's sake.</p>

      <p>GlobePin's goals work differently. You set goals like "visit every continent" or "fly 50,000 miles" or "spend time in 10 new countries this year" — and your existing travel data fills in progress automatically. Goals connect to history. The app knows you've already been to four continents and shows you what's left. No manual updating.</p>

      <h2>Anniversary reminders</h2>

      <p>This one's small but I haven't seen it anywhere else. GlobePin can remind you when an anniversary of a trip is coming up — "One year ago today, you arrived in Kyoto." It's the kind of feature that turns a data app into something that feels personal.</p>

      <h2>Shareable postcards without the social network</h2>

      <p>Travel apps that have sharing built in usually want you to share inside the app — to followers, to friends, as part of their retention loop. I didn't want that model.</p>

      <p>GlobePin generates shareable travel postcards — a single image combining your map, your stats, and a personal note — that you export and share wherever you want. iMessage, Instagram, email, wherever. The app isn't the destination. It's a tool.</p>

      <h2>iCloud sync, not a proprietary account</h2>

      <p>Your travel data should be yours. GlobePin syncs across devices using iCloud via CloudKit — Apple's sync infrastructure that you're already paying for as an iPhone owner. No account, no subscription for sync, no data stored on Purplelink's servers.</p>

      <p>That also means if GlobePin ever went away, your data would still be in iCloud. That's the kind of guarantee most apps can't make.</p>

      <p>GlobePin is coming to the App Store in 2026. If you're the kind of traveler who wants a real record of everywhere you've been — <a href="/globepin/">join the waitlist</a>.</p>
    </article>

    <div class="post-footer">
      <a class="back-link" href="/blog/" style="border: none; padding: 0;">← Back to blog</a>
    </div>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add "site/blog/what-globepin-does-differently/index.html"
git commit -m "feat: add blog post — What GlobePin does differently"
```

---

## Task 10: Blog post — Haea

**Files:**
- Create: `site/blog/why-haea-is-on-device/index.html`

- [ ] **Step 1: Create the file**

Create `site/blog/why-haea-is-on-device/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>Why we built Haea on-device — Purplelink LLC</title>
    <meta name="description" content="Why Haea keeps all your health data on your iPhone — and why that decision shapes everything about how the app works.">
    <link rel="canonical" href="https://purplelink.llc/blog/why-haea-is-on-device/">
    <meta property="og:title" content="Why we built Haea on-device">
    <meta property="og:description" content="Why Haea keeps all your health data on your iPhone — and why that decision shapes everything about how the app works.">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://purplelink.llc/blog/why-haea-is-on-device/">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="Why we built Haea on-device">
    <meta name="twitter:description" content="Why Haea keeps all your health data on your iPhone — and why that decision shapes everything about how the app works.">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "BlogPosting",
          "headline": "Why we built Haea on-device",
          "description": "Why Haea keeps all your health data on your iPhone — and why that decision shapes everything about how the app works.",
          "datePublished": "2026-05-27",
          "author": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "publisher": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "url": "https://purplelink.llc/blog/why-haea-is-on-device/"
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://purplelink.llc/blog/" },
            { "@type": "ListItem", "position": 3, "name": "Why we built Haea on-device", "item": "https://purplelink.llc/blog/why-haea-is-on-device/" }
          ]
        }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <a class="back-link" href="/blog/">← All posts</a>

    <div class="post-hero">
      <p class="post-date">May 27, 2026</p>
      <h1 class="post-title">Why we built Haea on-device</h1>
      <p class="post-lede">Your health data is the most personal data you have. Here's why we decided early on that none of it would leave your phone — and what that decision cost us.</p>
    </div>

    <article id="main-content" class="post-body">
      <p>The first real architectural decision we made on Haea was this: no server. Your health data stays on your iPhone, full stop. No cloud sync to Purplelink's infrastructure, no processing on our end, no data stored anywhere we control.</p>

      <p>It's a hard constraint. It rules out features that would be straightforward with a server — cross-device sync that works instantly, personalized recommendations trained on aggregate data, collaborative features. We gave those up deliberately. Here's why.</p>

      <h2>Health data is different</h2>

      <p>Most apps treat your data as an asset. It's used to personalize ads, train models, improve the product, or sometimes sold outright. For lifestyle data — what music you listen to, what articles you read — that tradeoff might be reasonable. For health data, it isn't.</p>

      <p>Sleep patterns, menstrual cycles, medication adherence, weight trends, biometric readings — this is data that can affect your insurance rates, your employment, your relationships. It's data that people have been discriminated against for. It belongs to you, and only you.</p>

      <p>Putting health data on a server means creating a target. Servers get breached. Companies get acquired. Business models change. Any health data we stored could eventually end up somewhere we didn't intend. The only reliable way to prevent that is to never have it in the first place.</p>

      <h2>On-device ML is genuinely viable now</h2>

      <p>The practical reason on-device health analytics wasn't common five years ago is that the compute wasn't there. Running Kalman filtering on a week of biometric data in real time, or computing Granger causality between health variables, required server-side processing.</p>

      <p>Apple Silicon changed that. The Neural Engine on a current iPhone does machine learning inference at a speed that would have required a server cluster a few years ago. The models we run in Haea — Kalman-filtered recovery state, circadian rhythm phase tracking, TDEE calculation, VO₂ max estimation — all run in milliseconds on-device.</p>

      <p>This isn't a compromise. On-device computation is faster than a round trip to a server. Haea's analytics are available instantly, offline, without latency. The privacy constraint turned out to be the performance-optimal choice too.</p>

      <h2>What we gave up</h2>

      <p>We want to be honest about the tradeoffs. Cross-device sync for Haea uses iCloud via HealthKit — Apple's own infrastructure, not ours — which means it's reliable but has the constraints Apple imposes. Some features that are easy with a server are genuinely hard without one.</p>

      <p>We also can't build certain types of population-level intelligence. A server-side health app can tell you "users with your sleep pattern tend to have lower recovery scores on Tuesdays." We can't — we don't see any user data at all. That's a real limitation we accepted.</p>

      <h2>Why it's worth it</h2>

      <p>The health apps people stick with long-term are the ones they trust. Trust is hard to rebuild once it's lost, and health data breaches are the ones people remember. By making the on-device architecture a core constraint rather than an afterthought, we can make a promise to users that most apps can't: we literally cannot access your health data, because we never receive it.</p>

      <p>That's not just a privacy policy. It's an architecture decision. And it's the decision that makes Haea worth building.</p>

      <p>Haea is coming to the App Store in 2026. <a href="/haea/">Join the waitlist</a> to be notified at launch.</p>
    </article>

    <div class="post-footer">
      <a class="back-link" href="/blog/" style="border: none; padding: 0;">← Back to blog</a>
    </div>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add "site/blog/why-haea-is-on-device/index.html"
git commit -m "feat: add blog post — Why we built Haea on-device"
```

---

## Task 11: Blog post — ModernTex

**Files:**
- Create: `site/blog/the-latex-editor-academics-want/index.html`

- [ ] **Step 1: Create the file**

Create `site/blog/the-latex-editor-academics-want/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>The LaTeX editor that academics actually want — Purplelink LLC</title>
    <meta name="description" content="Why existing LaTeX editors fail academic researchers — and what ModernTex does differently to serve the manuscript workflow.">
    <link rel="canonical" href="https://purplelink.llc/blog/the-latex-editor-academics-want/">
    <meta property="og:title" content="The LaTeX editor that academics actually want">
    <meta property="og:description" content="Why existing LaTeX editors fail academic researchers — and what ModernTex does differently to serve the manuscript workflow.">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://purplelink.llc/blog/the-latex-editor-academics-want/">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="The LaTeX editor that academics actually want">
    <meta name="twitter:description" content="Why existing LaTeX editors fail academic researchers — and what ModernTex does differently to serve the manuscript workflow.">
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="manifest" href="/manifest.json">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="preload" href="/assets/purplelink-logo.png" as="image">
    <link rel="stylesheet" href="/styles.css">
    <script src="/site.js" defer></script>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "BlogPosting",
          "headline": "The LaTeX editor that academics actually want",
          "description": "Why existing LaTeX editors fail academic researchers — and what ModernTex does differently to serve the manuscript workflow.",
          "datePublished": "2026-05-27",
          "author": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "publisher": {
            "@type": "Organization",
            "name": "Purplelink LLC",
            "url": "https://purplelink.llc/"
          },
          "url": "https://purplelink.llc/blog/the-latex-editor-academics-want/"
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://purplelink.llc/blog/" },
            { "@type": "ListItem", "position": 3, "name": "The LaTeX editor academics want", "item": "https://purplelink.llc/blog/the-latex-editor-academics-want/" }
          ]
        }
      ]
    }
    </script>
  </head>
  <body>

    <a class="skip-link" href="#main-content">Skip to content</a>

    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-logo.png" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <a class="back-link" href="/blog/">← All posts</a>

    <div class="post-hero">
      <p class="post-date">May 27, 2026</p>
      <h1 class="post-title">The LaTeX editor that academics actually want</h1>
      <p class="post-lede">TeXShop is from 2000. Overleaf is a web app built for collaboration. Neither was designed around the manuscript workflow that most researchers actually live in. ModernTex is.</p>
    </div>

    <article id="main-content" class="post-body">
      <p>LaTeX has a tooling problem. The language itself is powerful — it produces typeset output that word processors still can't match — but the editors that support it were mostly designed for programmers or haven't changed meaningfully since the early 2000s. Academic researchers put up with them because there's no better option on macOS.</p>

      <p>ModernTex is an attempt to fix that. Here's what's wrong with the current options, and what we're doing differently.</p>

      <h2>The options researchers currently have</h2>

      <p><strong>TeXShop</strong> is a classic. It's free, it works, and it's been shipping on macOS since 2001. But it shows its age. The interface predates modern macOS design conventions, the error reporting is raw compiler output, and the multi-file support is functional but not designed around the project structure of a real manuscript.</p>

      <p><strong>Overleaf</strong> is the popular choice for collaboration-heavy workflows. But it's a web app — meaning it requires an internet connection, stores your work on someone else's server, and delivers the performance characteristics of a web app rather than a native one. For a solo researcher working offline on a dissertation, it's the wrong tool.</p>

      <p><strong>VSCode with LaTeX Workshop</strong> is the programmer's choice. It's powerful, highly configurable, and actively developed. It's also a general-purpose code editor with LaTeX bolted on. The manuscript workflow — managing chapters, tracking citation keys, preparing for submission — isn't what it was designed for.</p>

      <h2>What academics actually need</h2>

      <p>When I talked to researchers about their LaTeX workflows, the same problems came up repeatedly.</p>

      <p><em>Error messages are incomprehensible.</em> LaTeX's error output is famously hostile. A missing brace three paragraphs up produces an error message pointing to a different paragraph, and deciphering it requires experience or a Google search. Researchers lose hours to errors that should take minutes.</p>

      <p><em>Multi-file projects are painful.</em> A dissertation or journal article often spans dozens of files — a main document, individual chapter files, a bibliography, custom style files, figure directories. Managing those relationships in a general-purpose editor requires configuration and discipline that adds friction.</p>

      <p><em>Submission prep is manual and error-prone.</em> Most conferences and journals have specific requirements — page limits, anonymous review mode, specific formatting packages, single-file submission. Checking all of those before submission is a checklist that researchers do manually and sometimes forget.</p>

      <p><em>Citation management is awkward.</em> Keeping a BibTeX file, remembering entry keys, and citing correctly across a long document are friction points in every manuscript. The existing autocomplete in most editors requires exact key matches — not useful when you can only remember the author's name.</p>

      <h2>What ModernTex does differently</h2>

      <p>ModernTex is designed around the manuscript as the unit of work, not the file. It understands project structure: root files, chapter files, bibliography files. The sidebar reflects the manuscript, not the filesystem.</p>

      <p>Error messages are translated. When a compilation fails, ModernTex parses the raw LaTeX output and presents a plain-language explanation with a suggested fix and a direct jump to the relevant source location. Most common LaTeX errors become understandable in seconds.</p>

      <p>Submission readiness is a first-class feature. Before submitting to a venue, ModernTex can check anonymization (are any author names visible?), page count, required sections, and package compatibility. It surfaces the issues that cause desk rejections.</p>

      <p>Citation search works on author names, titles, and keywords — not just exact BibTeX keys. Type the author's last name and get a list of matching entries from your bibliography. Cite with a keystroke.</p>

      <p>And it's native macOS. Built in Swift, dark and light mode, proper keyboard shortcuts, fast compilation that doesn't make you wait. It feels like it belongs on your Mac, because it was designed for one.</p>

      <p>ModernTex is in active development. If you're a researcher who's put up with the current options for too long — <a href="/moderntex/">join the waitlist</a>.</p>
    </article>

    <div class="post-footer">
      <a class="back-link" href="/blog/" style="border: none; padding: 0;">← Back to blog</a>
    </div>

    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-logo.png" alt="Purplelink" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/blog/">Blog</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>

  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add "site/blog/the-latex-editor-academics-want/index.html"
git commit -m "feat: add blog post — The LaTeX editor academics want"
```

---

## Task 12: Blog index — add 3 new post cards

**Files:**
- Modify: `site/blog/index.html`

- [ ] **Step 1: Update the blog list**

In `site/blog/index.html`, replace the current `.blog-list` section:

```html
    <div class="blog-list">
      <a class="blog-post-item" href="/blog/starting-purplelink/">
        <span class="blog-post-date">May 27, 2026</span>
        <div>
          <div class="blog-post-title">Starting Purplelink</div>
          <p class="blog-post-excerpt">Why I formed a software LLC, what I'm building with it, and the philosophy behind making software that's meant to last — not just ship.</p>
        </div>
      </a>
    </div>
```

Replace with:

```html
    <div class="blog-list">
      <a class="blog-post-item" href="/blog/what-globepin-does-differently/">
        <span class="blog-post-date">May 27, 2026</span>
        <div>
          <div class="blog-post-title">What GlobePin does that no other travel app does</div>
          <p class="blog-post-excerpt">Every travel tracker on the App Store solves a piece of the problem. Most miss the same things. Here's what we built differently — and why.</p>
        </div>
      </a>
      <a class="blog-post-item" href="/blog/why-haea-is-on-device/">
        <span class="blog-post-date">May 27, 2026</span>
        <div>
          <div class="blog-post-title">Why we built Haea on-device</div>
          <p class="blog-post-excerpt">Your health data is the most personal data you have. Here's why we decided early on that none of it would leave your phone — and what that decision cost us.</p>
        </div>
      </a>
      <a class="blog-post-item" href="/blog/the-latex-editor-academics-want/">
        <span class="blog-post-date">May 27, 2026</span>
        <div>
          <div class="blog-post-title">The LaTeX editor that academics actually want</div>
          <p class="blog-post-excerpt">TeXShop is from 2000. Overleaf is a web app. Neither was designed around the manuscript workflow researchers actually live in. ModernTex is.</p>
        </div>
      </a>
      <a class="blog-post-item" href="/blog/starting-purplelink/">
        <span class="blog-post-date">May 27, 2026</span>
        <div>
          <div class="blog-post-title">Starting Purplelink</div>
          <p class="blog-post-excerpt">Why I formed a software LLC, what I'm building with it, and the philosophy behind making software that's meant to last — not just ship.</p>
        </div>
      </a>
    </div>
```

- [ ] **Step 2: Commit**

```bash
git add site/blog/index.html
git commit -m "feat: add 3 new post cards to blog index"
```

---

## Task 13: ModernTex product page additions

Add FAQ accordion with FAQPage JSON-LD, App Store badge, and waitlist fine print to `site/moderntex/index.html`.

**Files:**
- Modify: `site/moderntex/index.html`

- [ ] **Step 1: Add FAQPage JSON-LD to `<head>`**

Add a second `<script type="application/ld+json">` block in `<head>`, after the existing one (if any):

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "FAQPage",
          "mainEntity": [
            {
              "@type": "Question",
              "name": "When does ModernTex ship?",
              "acceptedAnswer": { "@type": "Answer", "text": "ModernTex is expected to launch in 2026. Join the waitlist to be notified at launch." }
            },
            {
              "@type": "Question",
              "name": "What macOS version does ModernTex require?",
              "acceptedAnswer": { "@type": "Answer", "text": "ModernTex requires macOS 14 (Sonoma) or later." }
            },
            {
              "@type": "Question",
              "name": "Is there a free trial?",
              "acceptedAnswer": { "@type": "Answer", "text": "Pricing details will be announced at launch. Join the waitlist to be among the first to know." }
            },
            {
              "@type": "Question",
              "name": "How is ModernTex different from TeXShop or Overleaf?",
              "acceptedAnswer": { "@type": "Answer", "text": "ModernTex is a native macOS app designed specifically for the academic manuscript workflow — not a web app and not a general-purpose code editor. It combines multi-file manuscript navigation, synchronized PDF preview, BibTeX autocomplete, plain-language error diagnostics, and submission-readiness checks in one coherent interface built for researchers." }
            },
            {
              "@type": "Question",
              "name": "Does ModernTex support multi-file projects?",
              "acceptedAnswer": { "@type": "Answer", "text": "Yes. ModernTex has built-in multi-file manuscript navigation with root file detection and a structured sidebar for jumping between chapters, sections, and bibliography files without losing context." }
            }
          ]
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "ModernTex", "item": "https://purplelink.llc/moderntex/" }
          ]
        }
      ]
    }
    </script>
```

- [ ] **Step 2: Add App Store badge below the hero CTA**

Find the hero actions section:

```html
        <div class="app-hero-actions">
          <a class="btn btn-primary" href="#waitlist">Join the waitlist</a>
        </div>
```

Replace with:

```html
        <div class="app-hero-actions">
          <a class="btn btn-primary" href="#waitlist">Join the waitlist</a>
        </div>
        <div class="store-badge-row">
          <a class="store-badge" href="#waitlist" aria-label="Coming to the Mac App Store">
            <svg viewBox="0 0 814 1000" aria-hidden="true"><path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-42.3-148.3-110.7c-44.3-70.3-65.3-142-65.3-209.8 0-197.1 127.4-301.5 252.7-301.5 33.5 0 96.8 16.7 138.3 16.7 39.9 0 113.9-21.5 163.9-21.5 11.5 0 108.2 1.3 171.7 65.2zm-170.6-271.2c31.4-37.9 53.5-90.5 53.5-143.1 0-7.7-.6-15.4-1.9-21.5-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 8.3 1.3 16.7 1.9 19.2 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.1-67.2z"/></svg>
            <span class="store-badge-text">
              <span class="store-badge-coming">Coming to the</span>
              <span class="store-badge-label">Mac App Store</span>
            </span>
          </a>
        </div>
```

- [ ] **Step 3: Add waitlist fine print**

Find the waitlist form's submit button:

```html
        <button type="submit">Notify me at launch</button>
      </form>
```

Replace with:

```html
        <button type="submit">Notify me at launch</button>
      </form>
      <p class="waitlist-fine-print">We'll only use your email to notify you at launch. <a href="/privacy/">Privacy Policy</a></p>
```

- [ ] **Step 4: Add FAQ section above the footer**

Add this block immediately before `<footer class="footer">`:

```html
    <section class="faq-section" id="faq" aria-labelledby="faq-heading">
      <h2 id="faq-heading">Frequently asked questions</h2>
      <div class="faq-list">
        <details class="faq-item">
          <summary>When does ModernTex ship?</summary>
          <div class="faq-body">ModernTex is expected to launch in 2026. Join the waitlist above to be notified the moment it's available.</div>
        </details>
        <details class="faq-item">
          <summary>What macOS version is required?</summary>
          <div class="faq-body">ModernTex requires macOS 14 (Sonoma) or later.</div>
        </details>
        <details class="faq-item">
          <summary>Is there a free trial?</summary>
          <div class="faq-body">Pricing details will be announced at launch. Sign up for the waitlist to be among the first to know.</div>
        </details>
        <details class="faq-item">
          <summary>How is ModernTex different from TeXShop or Overleaf?</summary>
          <div class="faq-body">ModernTex is a native macOS app designed specifically for the academic manuscript workflow — not a web app and not a general-purpose code editor. It combines multi-file manuscript navigation, synchronized PDF preview, BibTeX autocomplete that searches by author or title, plain-language error diagnostics, and submission-readiness checks in one coherent interface. It was designed for researchers, not programmers.</div>
        </details>
        <details class="faq-item">
          <summary>Does ModernTex support multi-file projects?</summary>
          <div class="faq-body">Yes. ModernTex has built-in multi-file manuscript navigation with root file detection and a structured sidebar for jumping between chapters, sections, and bibliography files without losing context.</div>
        </details>
      </div>
    </section>
```

- [ ] **Step 5: Commit**

```bash
git add site/moderntex/index.html
git commit -m "feat: add FAQ, App Store badge, and waitlist fine print to ModernTex page"
```

---

## Task 14: Haea product page additions

Same three additions as Task 13 but for Haea.

**Files:**
- Modify: `site/haea/index.html`

- [ ] **Step 1: Add FAQPage JSON-LD to `<head>`**

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "FAQPage",
          "mainEntity": [
            {
              "@type": "Question",
              "name": "When does Haea ship?",
              "acceptedAnswer": { "@type": "Answer", "text": "Haea is expected to launch in 2026. Join the waitlist to be notified at launch." }
            },
            {
              "@type": "Question",
              "name": "Is there a free tier?",
              "acceptedAnswer": { "@type": "Answer", "text": "Yes. Haea has a free tier for core health logging and charts. Premium features ($1.99/month or $14.99/year) include advanced analytics like Kalman-filtered recovery state, Granger causality analysis, and biological age estimation." }
            },
            {
              "@type": "Question",
              "name": "Does Haea sync to the cloud?",
              "acceptedAnswer": { "@type": "Answer", "text": "No. All health data stays on your device. Haea uses no cloud sync, no third-party SDKs, and no analytics services. Your data never leaves your iPhone." }
            },
            {
              "@type": "Question",
              "name": "What health data sources does Haea support?",
              "acceptedAnswer": { "@type": "Answer", "text": "Haea reads from Apple Health and integrates sleep, nutrition, weight, exercise, and biometric data including heart rate, HRV, and blood oxygen." }
            },
            {
              "@type": "Question",
              "name": "Is Haea HIPAA-compliant?",
              "acceptedAnswer": { "@type": "Answer", "text": "Haea is designed with a privacy-first architecture: all data is stored on-device with no cloud transmission or third-party access. While Haea is a consumer app and not a covered entity under HIPAA, its design exceeds typical health app privacy standards." }
            }
          ]
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "Haea", "item": "https://purplelink.llc/haea/" }
          ]
        }
      ]
    }
    </script>
```

- [ ] **Step 2: Add App Store badge below hero CTA**

Find `<div class="app-hero-actions">` and add the badge row after it:

```html
        <div class="store-badge-row">
          <a class="store-badge" href="#waitlist" aria-label="Coming to the App Store">
            <svg viewBox="0 0 814 1000" aria-hidden="true"><path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-42.3-148.3-110.7c-44.3-70.3-65.3-142-65.3-209.8 0-197.1 127.4-301.5 252.7-301.5 33.5 0 96.8 16.7 138.3 16.7 39.9 0 113.9-21.5 163.9-21.5 11.5 0 108.2 1.3 171.7 65.2zm-170.6-271.2c31.4-37.9 53.5-90.5 53.5-143.1 0-7.7-.6-15.4-1.9-21.5-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 8.3 1.3 16.7 1.9 19.2 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.1-67.2z"/></svg>
            <span class="store-badge-text">
              <span class="store-badge-coming">Coming to the</span>
              <span class="store-badge-label">App Store</span>
            </span>
          </a>
        </div>
```

- [ ] **Step 3: Add waitlist fine print** (same as ModernTex — add after `</form>`)

```html
      <p class="waitlist-fine-print">We'll only use your email to notify you at launch. <a href="/privacy/">Privacy Policy</a></p>
```

- [ ] **Step 4: Add FAQ section above footer**

```html
    <section class="faq-section" id="faq" aria-labelledby="faq-heading">
      <h2 id="faq-heading">Frequently asked questions</h2>
      <div class="faq-list">
        <details class="faq-item">
          <summary>When does Haea ship?</summary>
          <div class="faq-body">Haea is expected to launch in 2026. Join the waitlist above to be notified the moment it's available.</div>
        </details>
        <details class="faq-item">
          <summary>Is there a free tier?</summary>
          <div class="faq-body">Yes. Haea has a free tier for core health logging and charts. Premium features ($1.99/month or $14.99/year) unlock advanced analytics including Kalman-filtered recovery state, Granger causality analysis between health variables, and biological age estimation.</div>
        </details>
        <details class="faq-item">
          <summary>Does Haea sync to the cloud?</summary>
          <div class="faq-body">No. All your health data stays on your device. Haea uses no cloud sync, no third-party analytics SDKs, and no advertising frameworks. Your data never leaves your iPhone.</div>
        </details>
        <details class="faq-item">
          <summary>What health data sources does it support?</summary>
          <div class="faq-body">Haea reads from Apple Health and integrates sleep, nutrition, weight, exercise, and biometric data including heart rate, HRV, and blood oxygen.</div>
        </details>
        <details class="faq-item">
          <summary>Is Haea HIPAA-compliant?</summary>
          <div class="faq-body">Haea is designed with privacy-first architecture: all data is stored on-device with no cloud transmission or third-party access. While Haea is a consumer app and not a covered entity under HIPAA, its design exceeds typical health app privacy standards — there is simply no data to breach on our end.</div>
        </details>
      </div>
    </section>
```

- [ ] **Step 5: Commit**

```bash
git add site/haea/index.html
git commit -m "feat: add FAQ, App Store badge, and waitlist fine print to Haea page"
```

---

## Task 15: GlobePin product page additions

**Files:**
- Modify: `site/globepin/index.html`

- [ ] **Step 1: Add FAQPage JSON-LD to `<head>`**

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "FAQPage",
          "mainEntity": [
            {
              "@type": "Question",
              "name": "When does GlobePin ship?",
              "acceptedAnswer": { "@type": "Answer", "text": "GlobePin is the closest to launch of Purplelink's three apps, currently in active testing (build 79+). Expected App Store release in 2026." }
            },
            {
              "@type": "Question",
              "name": "How do I log a flight in GlobePin?",
              "acceptedAnswer": { "@type": "Answer", "text": "Tap the + button and enter your departure and arrival airports. GlobePin calculates the route, distance, and duration, then adds the flight to your map, stats, and timeline." }
            },
            {
              "@type": "Question",
              "name": "Does GlobePin sync across devices?",
              "acceptedAnswer": { "@type": "Answer", "text": "Yes. GlobePin uses iCloud sync via CloudKit, so your travel data is available across all your iOS devices without creating a separate account." }
            },
            {
              "@type": "Question",
              "name": "Is there a free tier?",
              "acceptedAnswer": { "@type": "Answer", "text": "Pricing details will be announced at launch. Join the waitlist to be notified." }
            },
            {
              "@type": "Question",
              "name": "What makes GlobePin different from other travel trackers?",
              "acceptedAnswer": { "@type": "Answer", "text": "GlobePin tracks the complete travel record: every place visited, every flight taken, and every destination on the list. It combines a 3D globe view, detailed flight statistics, travel goals, anniversary reminders for trips, and exportable travel postcards — without requiring a social network account or storing data on external servers." }
            }
          ]
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "GlobePin", "item": "https://purplelink.llc/globepin/" }
          ]
        }
      ]
    }
    </script>
```

- [ ] **Step 2: Add App Store badge below hero CTA** (same SVG/markup as Haea — "App Store" not "Mac App Store")

```html
        <div class="store-badge-row">
          <a class="store-badge" href="#waitlist" aria-label="Coming to the App Store">
            <svg viewBox="0 0 814 1000" aria-hidden="true"><path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-42.3-148.3-110.7c-44.3-70.3-65.3-142-65.3-209.8 0-197.1 127.4-301.5 252.7-301.5 33.5 0 96.8 16.7 138.3 16.7 39.9 0 113.9-21.5 163.9-21.5 11.5 0 108.2 1.3 171.7 65.2zm-170.6-271.2c31.4-37.9 53.5-90.5 53.5-143.1 0-7.7-.6-15.4-1.9-21.5-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 8.3 1.3 16.7 1.9 19.2 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.1-67.2z"/></svg>
            <span class="store-badge-text">
              <span class="store-badge-coming">Coming to the</span>
              <span class="store-badge-label">App Store</span>
            </span>
          </a>
        </div>
```

- [ ] **Step 3: Add waitlist fine print** (after `</form>`)

```html
      <p class="waitlist-fine-print">We'll only use your email to notify you at launch. <a href="/privacy/">Privacy Policy</a></p>
```

- [ ] **Step 4: Add FAQ section above footer**

```html
    <section class="faq-section" id="faq" aria-labelledby="faq-heading">
      <h2 id="faq-heading">Frequently asked questions</h2>
      <div class="faq-list">
        <details class="faq-item">
          <summary>When does GlobePin ship?</summary>
          <div class="faq-body">GlobePin is the closest to launch of Purplelink's three apps, currently in active testing at build 79+. Expected App Store release in 2026 — join the waitlist to be notified.</div>
        </details>
        <details class="faq-item">
          <summary>How do I log a flight?</summary>
          <div class="faq-body">Tap the + button and enter your departure and arrival airports. GlobePin calculates the route, distance, and duration, then adds the flight to your map, stats, and timeline automatically.</div>
        </details>
        <details class="faq-item">
          <summary>Does GlobePin sync across devices?</summary>
          <div class="faq-body">Yes. GlobePin uses iCloud sync via CloudKit — Apple's own infrastructure — so your travel data is available across all your iOS devices without a separate account or subscription.</div>
        </details>
        <details class="faq-item">
          <summary>Is there a free tier?</summary>
          <div class="faq-body">Pricing details will be announced at launch. Join the waitlist to be notified.</div>
        </details>
        <details class="faq-item">
          <summary>What's the difference between GlobePin and other travel trackers?</summary>
          <div class="faq-body">GlobePin tracks the complete travel record: every place visited, every flight taken, and every destination on the list. It combines a 3D globe view, detailed flight statistics, travel goals, anniversary reminders, and exportable travel postcards — all synced via iCloud, no social network required.</div>
        </details>
      </div>
    </section>
```

- [ ] **Step 5: Commit**

```bash
git add site/globepin/index.html
git commit -m "feat: add FAQ, App Store badge, and waitlist fine print to GlobePin page"
```

---

## Task 16: Sitemap updates

**Files:**
- Modify: `site/sitemap.xml`

- [ ] **Step 1: Add all new URLs**

Replace the full content of `site/sitemap.xml` with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://purplelink.llc/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/moderntex/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/haea/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/globepin/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/about/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/press/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/privacy/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/blog/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/blog/starting-purplelink/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>never</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/blog/what-globepin-does-differently/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>never</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/blog/why-haea-is-on-device/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>never</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/blog/the-latex-editor-academics-want/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>never</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://purplelink.llc/changelog/</loc>
    <lastmod>2026-05-27</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
```

- [ ] **Step 2: Commit**

```bash
git add site/sitemap.xml
git commit -m "feat: update sitemap with new pages and blog posts"
```

---

## Task 17: llms.txt expansion

**Files:**
- Modify: `site/llms.txt`

- [ ] **Step 1: Replace llms.txt with expanded version**

Replace the full content of `site/llms.txt` with:

```
# Purplelink LLC

> Purplelink LLC is a software studio based in Atlanta, Georgia building native macOS and iOS apps — ModernTex, Haea, and GlobePin — with an emphasis on craft, longevity, and user privacy. Founded in 2026 as a Georgia LLC.

## Company

- **Legal name:** Purplelink LLC
- **Type:** Georgia LLC (NAICS 541511 — Custom Computer Programming Services)
- **Location:** 8735 Dunwoody Place #12398, Atlanta, GA 30350
- **Founded:** 2026
- **Contact:** ben@purplelink.llc
- **CEO:** Benjamin Ampel
- **Website:** https://purplelink.llc/
- **Mission:** Making software that lasts.

## What Purplelink builds

Purplelink creates software with an emphasis on craft, longevity, and practical utility across three areas:

1. **Native macOS and iOS apps** — Purpose-built Apple platform applications. Performance, aesthetics, and functionality built together, not bolted on.

2. **Applied AI tools** — Internal and client-facing tools that use AI to automate analysis, writing, research, and software workflows.

3. **Web applications and automation** — Dashboards, portals, API integrations, and backend services.

## Products in development

### ModernTex (macOS)
- **Platform:** macOS 14+
- **Category:** Productivity / academic writing
- **Description:** A native macOS LaTeX manuscript studio for academic researchers. Combines multi-file manuscript editing, tightly synchronized PDF preview, intelligent compile modes (Fast/Live/Full), citation management and BibTeX autocomplete, revision snapshots, plain-language error diagnostics, and submission-readiness checks in one coherent interface.
- **Target users:** PhD students, faculty, and technical coauthors writing serious LaTeX manuscripts
- **Pricing:** To be announced at launch
- **Privacy:** No cloud sync, no data collection
- **Status:** In active development, expected 2026
- **Waitlist:** https://purplelink.llc/moderntex/
- **Key differentiators:** Plain-language LaTeX error explanations; submission-readiness checks for journal/conference requirements; native macOS (not Electron, not web); academic manuscript workflow as first-class feature

### Haea (iOS)
- **Platform:** iOS 17+
- **Bundle ID:** com.BAmpel.Haea
- **Category:** Health & fitness
- **Description:** A comprehensive on-device health analytics platform. Integrates sleep, nutrition, weight, exercise, and biometric data to surface patterns and trends through advanced ML models including Kalman filtering, TDEE calculation, circadian rhythm intelligence, Granger causality analysis, and VO₂ max tracking.
- **Target users:** Health-conscious individuals who want advanced analytics without giving up their data
- **Pricing:** Free tier + Premium ($1.99/month or $14.99/year)
- **Privacy:** No cloud sync, no third-party SDKs, no analytics, on-device only, HIPAA-ready architecture
- **Status:** In active development, expected 2026
- **Waitlist:** https://purplelink.llc/haea/
- **Key differentiators:** Full on-device ML (Kalman filtering, Granger causality, biological age estimation); no cloud transmission of health data; privacy-first architecture as a core design constraint, not an add-on

### GlobePin (iOS)
- **Platform:** iOS 17+
- **Bundle ID:** com.globepin.app
- **Category:** Travel
- **Description:** A travel mapping app for tracking every place visited, every flight taken, and every destination on the list. Features interactive map visualization with 3D globe view, flight statistics dashboards, travel goal tracking, anniversary reminders for visits, and shareable travel postcards.
- **Target users:** Frequent travelers who want a complete personal travel record
- **Pricing:** To be announced at launch
- **Sync:** iCloud sync via CloudKit (no Purplelink account required)
- **Status:** Multiple builds completed (build 79+), approaching release in 2026
- **Waitlist:** https://purplelink.llc/globepin/
- **Key differentiators:** 3D globe view for route visualization; complete flight log with stats; travel goals tied to actual history; anniversary reminders; iCloud sync without a separate account; no social network features

## Open source

### Scholar Utility Belt
- **Type:** Browser extension (Google Chrome)
- **Purpose:** Utility for academic research workflows
- **Chrome Web Store:** https://chromewebstore.google.com/detail/scholar-utility-belt/omcogfcgldfmihfogbffflbocdbjockn

## Pages

- Home: https://purplelink.llc/
- ModernTex: https://purplelink.llc/moderntex/
- Haea: https://purplelink.llc/haea/
- GlobePin: https://purplelink.llc/globepin/
- About: https://purplelink.llc/about/
- Blog: https://purplelink.llc/blog/
- Press: https://purplelink.llc/press/
- Privacy Policy: https://purplelink.llc/privacy/
- Changelog: https://purplelink.llc/changelog/

## Frequently asked questions

**When do Purplelink's apps ship?**
GlobePin is nearest to launch (build 79+, expected 2026). Haea and ModernTex are in active development and also expected in 2026. All three have waitlists on their respective product pages.

**What platforms do the apps support?**
GlobePin and Haea are iOS apps (iOS 17+). ModernTex is a macOS app (macOS 14+).

**Does Haea send my health data to a server?**
No. All of Haea's data stays on-device. There is no cloud sync to Purplelink's infrastructure, no third-party SDKs, and no analytics. Your health data never leaves your iPhone.

**Does Haea work with Apple Health?**
Yes. Haea reads data from Apple Health including sleep, nutrition, weight, exercise, heart rate, HRV, and blood oxygen.

**Is Haea HIPAA-compliant?**
Haea is a consumer app, not a covered entity under HIPAA. However, its architecture exceeds typical health app privacy standards: all data is on-device with no cloud transmission.

**Does GlobePin require an account?**
No. GlobePin syncs via iCloud (CloudKit) using your existing Apple ID. No separate Purplelink account is required.

**Is ModernTex a subscription?**
Pricing has not been announced. Sign up for the waitlist at https://purplelink.llc/moderntex/ to be notified.

**Who built Purplelink?**
Purplelink LLC was founded by Benjamin Ampel in Atlanta, Georgia in 2026. It is a one-person studio.

**How do I contact Purplelink?**
Email ben@purplelink.llc for product inquiries, press, or general questions.

## Notes

- Project inquiries: ben@purplelink.llc with subject "Purplelink LLC"
- The company is a sole-proprietor LLC operated out of Atlanta, Georgia
```

- [ ] **Step 2: Commit**

```bash
git add site/llms.txt
git commit -m "feat: expand llms.txt with app details, FAQ block, and new page links"
```

---

## Task 18: BreadcrumbList on remaining existing pages

Tasks 13–15 added breadcrumbs to product pages as part of the FAQPage JSON-LD `@graph`. Tasks 5–7 added breadcrumbs to new static pages. This task covers the remaining existing pages that still need `BreadcrumbList`.

**Files:**
- Modify: `site/index.html` (homepage — no breadcrumb needed, skip)
- Modify: `site/blog/index.html`
- Modify: `site/blog/starting-purplelink/index.html`
- Modify: `site/changelog/index.html`

- [ ] **Step 1: Add BreadcrumbList to `site/blog/index.html`**

Add to `<head>` after the last existing `<script>` tag:

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://purplelink.llc/blog/" }
      ]
    }
    </script>
```

- [ ] **Step 2: Add BreadcrumbList to `site/blog/starting-purplelink/index.html`**

The existing JSON-LD is a `BlogPosting` type. Add a second `<script type="application/ld+json">` block after it:

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://purplelink.llc/blog/" },
        { "@type": "ListItem", "position": 3, "name": "Starting Purplelink", "item": "https://purplelink.llc/blog/starting-purplelink/" }
      ]
    }
    </script>
```

- [ ] **Step 3: Add BreadcrumbList to `site/changelog/index.html`**

Add to `<head>`:

```html
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Changelog", "item": "https://purplelink.llc/changelog/" }
      ]
    }
    </script>
```

- [ ] **Step 4: Commit**

```bash
git add site/blog/index.html "site/blog/starting-purplelink/index.html" site/changelog/index.html
git commit -m "feat: add BreadcrumbList JSON-LD to blog index, first post, and changelog"
```

---

## Task 19: Verification

- [ ] **Step 1: Start local server**

```bash
python3 -m http.server 4200 --directory "/Volumes/Extreme SSD/Purplelink LLC/site"
```

- [ ] **Step 2: Check all new pages load**

Visit each:
- `http://localhost:4200/privacy/` — Privacy Policy page
- `http://localhost:4200/about/` — About page
- `http://localhost:4200/press/` — Press page
- `http://localhost:4200/404.html` — 404 page (direct URL, since local server won't do the Netlify redirect)
- `http://localhost:4200/blog/what-globepin-does-differently/`
- `http://localhost:4200/blog/why-haea-is-on-device/`
- `http://localhost:4200/blog/the-latex-editor-academics-want/`

- [ ] **Step 3: Check product pages**

Visit `/moderntex/`, `/haea/`, `/globepin/` and verify:
- FAQ accordion expands/collapses on click
- App Store badge appears below the hero CTA
- Privacy Policy link appears below the waitlist form

- [ ] **Step 4: Check global elements**

On any page, verify:
- Nav shows "About" between Changelog and Contact
- Footer shows two rows (brand row + links row)
- About, Press, Privacy, Blog, Changelog links in footer all work

- [ ] **Step 5: Validate JSON-LD**

Open Chrome DevTools → Application → for a product page, check no console errors from the JSON-LD scripts. Optionally paste a page's source into Google's Rich Results Test at `https://search.google.com/test/rich-results`.

- [ ] **Step 6: Run the Playwright audit (optional but recommended)**

If the webapp-testing skill's Playwright script exists:

```bash
python3 "/Users/benampel/.claude/skills/webapp-testing/scripts/with_server.py" \
  --server "python3 -m http.server 4200 --directory site" --port 4200 \
  -- python3 /tmp/audit_purplelink.py
```

- [ ] **Step 7: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore: final cleanup from SEO/GEO/polish implementation"
```
