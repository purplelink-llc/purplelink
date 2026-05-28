# Organic Traffic Program — Free LaTeX Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow qualified organic traffic to the 13 free LaTeX tools by completing `llms.txt`, verifying on-page answer-content parity, shipping a new `/guides/` section with 6 seed how-to guides cross-linked to their tools, and writing the outreach playbook + measurement docs — all on the static site with zero added tracking.

**Architecture:** Pure static HTML/CSS additions under `site/`, deployed to Netlify. Every guide is a standalone HTML page that reuses the existing shared `/styles.css`, the canonical topbar/footer markup, and the established JSON-LD `@graph` pattern (Article + FAQPage + BreadcrumbList). No backend changes. No JavaScript beyond what `/styles.css` already supports (`<details>` FAQs are native HTML). Two Phase-3/measurement deliverables are Markdown docs under `docs/`.

**Tech Stack:** Static HTML5, schema.org JSON-LD, existing `site/styles.css`, Netlify CLI for deploy. No new dependencies.

---

## Conventions used by every task in this plan

- **Site root:** `site/` is the Netlify publish dir. URLs map directly: `site/guides/latex-to-word/index.html` → `https://purplelink.llc/guides/latex-to-word/`.
- **Canonical shared skeleton** (header + footer) is IDENTICAL on every page. It is given in full in Task 4 and referenced (not re-pasted) in Tasks 5–9. Copy it verbatim.
- **Guide OG image:** always `https://purplelink.llc/assets/og/tools-launch.png`. Per-guide OG images do NOT exist and creating them is out of scope (YAGNI). Using a real existing image avoids a broken-image bug.
- **No tracking:** never add analytics, cookies, pixels, or third-party scripts. Privacy brand is a hard constraint.
- **Do NOT touch:** `site/googleda12e563809d7164.html` (GSC verification), `.claude/`, `Legal/`, `Social Media/`.
- **Verification approach:** the preview server already serves `site/` on port 4200. After creating pages, load them and confirm structure renders, links resolve, and JSON-LD parses. A final task deploys to Netlify prod.
- **Commits:** each task ends with a commit. Use the repo's `feat(...)` / `docs(...)` conventional-commit style (see recent log: `feat(tools): ...`).

---

## File Structure

**Created:**
- `site/guides/index.html` — guides hub/index page
- `site/guides/latex-to-word/index.html` — Guide 1
- `site/guides/fix-bibtex-errors/index.html` — Guide 2
- `site/guides/citation-styles-explained/index.html` — Guide 3
- `site/guides/latex-track-changes/index.html` — Guide 4
- `site/guides/latex-word-count/index.html` — Guide 5
- `site/guides/doi-to-bibtex/index.html` — Guide 6
- `docs/organic-traffic/outreach-playbook.md` — Phase 3 playbook
- `docs/organic-traffic/measurement.md` — measurement doc

**Modified:**
- `site/llms.txt` — add the 10 missing tools + a new Guides section
- `site/sitemap.xml` — add `/guides/` index + 6 guide URLs
- `site/tools/latex-to-word/index.html` — add reciprocal "Guides" link
- `site/tools/bib-validator/index.html` — add reciprocal link
- `site/tools/citation-generator/index.html` — add reciprocal link
- `site/tools/latex-diff/index.html` — add reciprocal link
- `site/tools/word-counter/index.html` — add reciprocal link
- `site/tools/bib-builder/index.html` — add reciprocal link

**Verification-only (no edits expected):**
- All 13 `site/tools/*/index.html` — confirm intro paragraph + FAQ schema + related-tools block already present (Phase 1.2/1.3 parity).

---

## Task 1: Complete `llms.txt` (add 10 missing tools)

**Files:**
- Modify: `site/llms.txt:116-121` (the `## Tools (free web tools)` section)

**Context:** The section currently lists only 3 of 13 tools (latex-to-pdf, latex-diff, latex-to-word) plus the hub. AI assistants reading the file can't see the other 10. Format per existing entries: `- Name: URL — capability, privacy note.`

- [ ] **Step 1: Replace the Tools section with the complete 13-tool list**

In `site/llms.txt`, replace the block starting at `## Tools (free web tools)` through the `Tools hub:` line with:

```
## Tools (free web tools)
- LaTeX to PDF: https://purplelink.llc/tools/latex-to-pdf/ — compile a .tex file to PDF (pdfLaTeX/XeLaTeX), files never stored.
- LaTeX Diff: https://purplelink.llc/tools/latex-diff/ — compare two .tex versions, output a marked-up PDF via latexdiff, files never stored.
- LaTeX to Word: https://purplelink.llc/tools/latex-to-word/ — convert a .tex paper to a standard double-spaced Word .docx manuscript, optional anonymize, files never stored.
- Word to LaTeX: https://purplelink.llc/tools/word-to-latex/ — convert a Word .docx into LaTeX source, files never stored.
- Markdown to PDF: https://purplelink.llc/tools/markdown-to-pdf/ — render Markdown to a typeset PDF, files never stored.
- BibTeX Builder: https://purplelink.llc/tools/bib-builder/ — generate BibTeX entries from a DOI or arXiv ID, nothing stored.
- BibTeX Validator: https://purplelink.llc/tools/bib-validator/ — check a .bib file for syntax errors and missing required fields, runs in your browser.
- Citation Generator: https://purplelink.llc/tools/citation-generator/ — build IEEE, APA, MLA, and Chicago citations from entry fields, runs in your browser.
- Reference Converter: https://purplelink.llc/tools/reference-converter/ — convert references between BibTeX, RIS, and other formats, runs in your browser.
- Equation Renderer: https://purplelink.llc/tools/equation-renderer/ — render LaTeX math to an image, runs in your browser.
- LaTeX Table Generator: https://purplelink.llc/tools/latex-table-generator/ — build LaTeX tabular code from a visual grid, runs in your browser.
- Word & Character Counter: https://purplelink.llc/tools/word-counter/ — count words, characters, sentences, and reading time, runs in your browser.
- PDF Tools: https://purplelink.llc/tools/pdf-tools/ — merge, split, and compress PDF files, files never stored.
- Tools hub: https://purplelink.llc/tools/

## Guides (free how-to articles)
- Guides index: https://purplelink.llc/guides/
- Convert a LaTeX paper to Word: https://purplelink.llc/guides/latex-to-word/ — step-by-step .tex → .docx for journal submission.
- Fix common BibTeX errors: https://purplelink.llc/guides/fix-bibtex-errors/ — diagnose and repair the most frequent .bib mistakes.
- IEEE vs APA vs MLA vs Chicago: https://purplelink.llc/guides/citation-styles-explained/ — how the four major citation styles differ and when to use each.
- Show changes between two LaTeX versions: https://purplelink.llc/guides/latex-track-changes/ — track changes in LaTeX with latexdiff.
- Count words in a LaTeX document: https://purplelink.llc/guides/latex-word-count/ — accurate word counts for .tex files.
- Get BibTeX from a DOI or arXiv ID: https://purplelink.llc/guides/doi-to-bibtex/ — fetch a clean BibTeX entry from an identifier.
```

> NOTE: Verify each tool slug against `site/tools/` before saving — the directory names are authoritative (e.g. `bib-builder`, not `bibtex-builder`). The slugs above match the confirmed directory listing.

- [ ] **Step 2: Verify the file is well-formed**

Run: `grep -c "https://purplelink.llc/tools/" "site/llms.txt"`
Expected: `14` (13 tools + 1 hub line).

- [ ] **Step 3: Commit**

```bash
git add site/llms.txt
git commit -m "$(cat <<'EOF'
feat(seo): complete llms.txt with all 13 tools + guides section

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Verify Phase 1.2 / 1.3 on-page parity (verification-only)

**Files:**
- Inspect (no edits expected): all 13 `site/tools/*/index.html`

**Context:** The spec calls for every tool page to have an intro paragraph, a FAQ block with FAQPage schema, and a related-tools block. An earlier audit this session confirmed all 13 already have these. This task confirms that assumption holds before we build guides on top of it. If any page is missing an element, add it following the `word-counter` pattern (`tools-hero` intro `<p>`, `section.tool-faq` with `<details>` + matching FAQPage JSON-LD, `nav.tool-related`).

- [ ] **Step 1: Confirm every tool page has a FAQPage schema block**

Run:
```bash
for d in site/tools/*/; do [ -f "$d/index.html" ] && printf "%-26s FAQPage:%s tool-faq:%s tool-related:%s\n" "$(basename "$d")" "$(grep -c '"FAQPage"' "$d/index.html")" "$(grep -c 'tool-faq' "$d/index.html")" "$(grep -c 'tool-related' "$d/index.html")"; done
```
Expected: every tool shows `FAQPage:1 tool-faq:1 tool-related:1` (counts ≥1).

- [ ] **Step 2: Confirm every tool page has an intro paragraph in the hero**

Run: `for d in site/tools/*/; do [ -f "$d/index.html" ] && grep -q 'tools-hero' "$d/index.html" && echo "OK $(basename "$d")" || echo "MISSING $(basename "$d")"; done`
Expected: all `OK`.

- [ ] **Step 3: If any page is missing an element, add it; otherwise no-op**

If Steps 1–2 show any gap, add the missing element to that page using `site/tools/word-counter/index.html` as the reference pattern (intro `<p>` in `.tools-hero`; `<section class="tool-faq">` with `<details><summary>Q</summary><div class="faq-body">A</div></details>` and a matching `FAQPage` entry in the JSON-LD `@graph`; `<nav class="tool-related">`). If no gaps, record "parity confirmed, no edits" and proceed. No commit if nothing changed.

---

## Task 3: Add internal "Guides" reciprocal links to 6 tool pages

**Files:**
- Modify: `site/tools/latex-to-word/index.html`, `site/tools/bib-validator/index.html`, `site/tools/citation-generator/index.html`, `site/tools/latex-diff/index.html`, `site/tools/word-counter/index.html`, `site/tools/bib-builder/index.html` (each at its `<nav class="tool-related">` block)

**Context:** Each seed guide links to its tool; the tool must link back to its guide (reciprocal internal linking flows link equity and signals topical clustering). Add one `<li>` to each tool's existing related-tools list pointing at the matching guide. Do this AFTER the guides exist (Tasks 4–8) so the links don't 404 during local verification — but it is listed here for planning clarity; the executor should perform Step 1 of this task only after Task 8 completes. (If executing strictly in order, defer this task to run right before Task 9.)

Guide→tool mapping:
| Tool page | Guide link to add |
|-----------|-------------------|
| latex-to-word | `<li><a href="/guides/latex-to-word/">Guide: Convert LaTeX to Word →</a></li>` |
| bib-validator | `<li><a href="/guides/fix-bibtex-errors/">Guide: Fix common BibTeX errors →</a></li>` |
| citation-generator | `<li><a href="/guides/citation-styles-explained/">Guide: IEEE vs APA vs MLA vs Chicago →</a></li>` |
| latex-diff | `<li><a href="/guides/latex-track-changes/">Guide: Track changes in LaTeX →</a></li>` |
| word-counter | `<li><a href="/guides/latex-word-count/">Guide: Count words in a LaTeX document →</a></li>` |
| bib-builder | `<li><a href="/guides/doi-to-bibtex/">Guide: Get BibTeX from a DOI or arXiv ID →</a></li>` |

- [ ] **Step 1: For each of the 6 tool pages, insert the mapped `<li>` as the FIRST item inside the `<ul>` within `<nav class="tool-related">`**

Example for `site/tools/latex-to-word/index.html` — find:
```html
      <nav class="tool-related" aria-label="Related tools">
        <h2>More free LaTeX tools</h2>
        <ul>
```
Insert immediately after the `<ul>`:
```html
          <li><a href="/guides/latex-to-word/">Guide: Convert LaTeX to Word →</a></li>
```
Repeat for the other 5 pages using the table above. Match each page's existing indentation.

- [ ] **Step 2: Verify all 6 links were added**

Run: `grep -l '/guides/' site/tools/latex-to-word/index.html site/tools/bib-validator/index.html site/tools/citation-generator/index.html site/tools/latex-diff/index.html site/tools/word-counter/index.html site/tools/bib-builder/index.html | wc -l`
Expected: `6`.

- [ ] **Step 3: Commit**

```bash
git add site/tools/latex-to-word/index.html site/tools/bib-validator/index.html site/tools/citation-generator/index.html site/tools/latex-diff/index.html site/tools/word-counter/index.html site/tools/bib-builder/index.html
git commit -m "$(cat <<'EOF'
feat(seo): link tool pages to their how-to guides

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Create the `/guides/` index page + define the shared skeleton

**Files:**
- Create: `site/guides/index.html`

**Context:** This task establishes the **canonical shared skeleton** (`<head>` boilerplate, topbar, footer) reused by every guide in Tasks 5–9, and ships the guides hub page. The skeleton mirrors the tool-page structure (same fonts, same `/styles.css`, same nav) so the section feels native.

- [ ] **Step 1: Create `site/guides/index.html` with the full index page**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>LaTeX &amp; Academic Writing Guides | Purplelink LLC</title>
    <meta name="description" content="Free, practical how-to guides for LaTeX and academic writing — converting to Word, fixing BibTeX errors, citation styles, tracking changes, word counts, and more.">
    <link rel="canonical" href="https://purplelink.llc/guides/">
    <meta property="og:title" content="LaTeX &amp; Academic Writing Guides">
    <meta property="og:description" content="Free, practical how-to guides for LaTeX and academic writing.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://purplelink.llc/guides/">
    <meta property="og:image" content="https://purplelink.llc/assets/og/tools-launch.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="LaTeX &amp; Academic Writing Guides">
    <meta name="twitter:description" content="Free, practical how-to guides for LaTeX and academic writing.">
    <meta name="twitter:image" content="https://purplelink.llc/assets/og/tools-launch.png">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "CollectionPage",
          "name": "LaTeX & Academic Writing Guides",
          "url": "https://purplelink.llc/guides/",
          "description": "Free how-to guides for LaTeX and academic writing.",
          "provider": { "@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/" }
        },
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
            { "@type": "ListItem", "position": 2, "name": "Guides", "item": "https://purplelink.llc/guides/" }
          ]
        }
      ]
    }
    </script>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/styles.css">
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
        <a href="/tools/">Tools</a>
        <a href="/guides/" aria-current="page">Guides</a>
        <a href="/blog/">Blog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content">
      <div class="tools-hero">
        <p class="eyebrow">Free guides</p>
        <h1>LaTeX &amp; academic writing guides</h1>
        <p>Practical, no-fluff how-to guides for the things researchers actually get stuck on — converting LaTeX to Word, fixing BibTeX errors, citation styles, tracking changes, and more. Each guide pairs with a free tool you can use right away.</p>
      </div>

      <nav class="tool-related" aria-label="All guides">
        <ul>
          <li><a href="/guides/latex-to-word/">Convert a LaTeX paper to Word (free) →</a></li>
          <li><a href="/guides/fix-bibtex-errors/">Fix common BibTeX errors →</a></li>
          <li><a href="/guides/citation-styles-explained/">IEEE vs APA vs MLA vs Chicago citation styles →</a></li>
          <li><a href="/guides/latex-track-changes/">Show changes between two LaTeX versions →</a></li>
          <li><a href="/guides/latex-word-count/">Count words in a LaTeX document →</a></li>
          <li><a href="/guides/doi-to-bibtex/">Get BibTeX from a DOI or arXiv ID →</a></li>
        </ul>
      </nav>
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

- [ ] **Step 2: Verify it renders in the preview**

Load `http://localhost:4200/guides/` in the preview. Expected: hero heading "LaTeX & academic writing guides" and a list of 6 guide links. The 6 links will 404 until Tasks 5–9 ship — that is expected at this point.

- [ ] **Step 3: Commit**

```bash
git add site/guides/index.html
git commit -m "$(cat <<'EOF'
feat(guides): add /guides/ index page and shared layout

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## SHARED GUIDE SKELETON (reused verbatim in Tasks 5–9)

Every guide page uses this exact skeleton. The four `{{PLACEHOLDER}}` regions are the ONLY parts that change per guide; their exact content is given in full in each guide's task (no guessing required). Copy the topbar and footer below verbatim — they are identical to Task 4's.

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{{TITLE}}</title>
    <meta name="description" content="{{META_DESCRIPTION}}">
    <link rel="canonical" href="{{CANONICAL}}">
    <meta property="og:title" content="{{OG_TITLE}}">
    <meta property="og:description" content="{{META_DESCRIPTION}}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{{CANONICAL}}">
    <meta property="og:image" content="https://purplelink.llc/assets/og/tools-launch.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{OG_TITLE}}">
    <meta name="twitter:description" content="{{META_DESCRIPTION}}">
    <meta name="twitter:image" content="https://purplelink.llc/assets/og/tools-launch.png">
    <script type="application/ld+json">
    {{JSON_LD_GRAPH}}
    </script>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#7c3aed">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/styles.css">
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
        <a href="/tools/">Tools</a>
        <a href="/guides/" aria-current="page">Guides</a>
        <a href="/blog/">Blog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>

    <main id="main-content">
      <a class="back-link" href="/guides/">← All guides</a>
      <div class="post-hero">
        <p class="post-date">Guide</p>
        <h1 class="post-title">{{H1}}</h1>
        <p class="post-lede">{{LEDE}}</p>
      </div>

      <article class="post-body">
        {{ARTICLE_BODY}}
      </article>

      <section class="tool-faq">
        <h2>Frequently asked questions</h2>
        {{FAQ_DETAILS}}
      </section>

      <nav class="tool-related" aria-label="Related tools and guides">
        <h2>Try the tool &amp; related guides</h2>
        <ul>
          {{RELATED_LINKS}}
        </ul>
      </nav>
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

The `{{JSON_LD_GRAPH}}` for every guide follows this shape (Article + FAQPage + BreadcrumbList); only the string values change:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "{{H1}}",
      "description": "{{META_DESCRIPTION}}",
      "author": { "@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/" },
      "publisher": { "@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/" },
      "mainEntityOfPage": "{{CANONICAL}}",
      "datePublished": "2026-05-28"
    },
    {
      "@type": "FAQPage",
      "mainEntity": [ {{FAQ_JSON_ENTRIES}} ]
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/" },
        { "@type": "ListItem", "position": 2, "name": "Guides", "item": "https://purplelink.llc/guides/" },
        { "@type": "ListItem", "position": 3, "name": "{{H1}}", "item": "{{CANONICAL}}" }
      ]
    }
  ]
}
```

**Consistency rule:** each `{{FAQ_DETAILS}}` `<details>` question/answer MUST match its corresponding `{{FAQ_JSON_ENTRIES}}` Question/Answer text. Write the FAQ once, then mirror it into both the visible HTML and the JSON-LD.

---

## Task 5: Guide 1 — Convert a LaTeX paper to Word

**Files:**
- Create: `site/guides/latex-to-word/index.html`

- [ ] **Step 1: Create the file using the SHARED GUIDE SKELETON with these exact fills**

- `{{TITLE}}` → `Convert a LaTeX Paper to Word (Free, Step by Step) | Purplelink LLC`
- `{{OG_TITLE}}` → `Convert a LaTeX Paper to Word (Free)`
- `{{META_DESCRIPTION}}` → `How to convert a LaTeX .tex paper into a Word .docx manuscript for free — what survives the conversion, what to check, and a free in-browser converter.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/latex-to-word/`
- `{{H1}}` → `How to convert a LaTeX paper to Word`
- `{{LEDE}}` → `Plenty of journals and co-authors still want a Word .docx. Here's how to convert a LaTeX manuscript to Word without losing your structure — and what to check afterward.`

`{{ARTICLE_BODY}}`:
```html
        <p>LaTeX is excellent for typesetting, but at some point a journal's submission system, a co-author, or a grant office will ask for a Word document. Converting cleanly is mostly about knowing what transfers and what needs a manual pass.</p>
        <h2>The fastest way: a direct .tex → .docx converter</h2>
        <p>The quickest route is to upload your <code>.tex</code> file (or a ZIP of your project) to a converter that runs Pandoc under the hood. Our free <a href="/tools/latex-to-word/">LaTeX to Word converter</a> produces a double-spaced manuscript-style .docx, with an optional anonymize pass for blind review. Your files are processed and never stored.</p>
        <h2>What converts well</h2>
        <ul>
          <li>Headings, paragraphs, and basic text formatting (bold, italic, emphasis).</li>
          <li>Numbered and bulleted lists.</li>
          <li>Most inline and display math, converted to Word equations.</li>
          <li>Citations and a bibliography, when a <code>.bib</code> file is included.</li>
          <li>Cross-references and figure/table captions.</li>
        </ul>
        <h2>What to check after converting</h2>
        <ul>
          <li><strong>Complex tables.</strong> Multi-row or multi-column layouts sometimes need manual cleanup in Word.</li>
          <li><strong>Custom macros.</strong> If you defined your own commands, confirm they expanded the way you intended.</li>
          <li><strong>Figures.</strong> Vector PDFs may need to be re-inserted as images depending on the target template.</li>
          <li><strong>Equation numbering.</strong> Verify numbered equations still match in-text references.</li>
        </ul>
        <h2>Tips for a clean conversion</h2>
        <ol>
          <li>Include your <code>.bib</code> file (zip the whole project) so citations resolve.</li>
          <li>Compile your LaTeX successfully first — a document that doesn't build won't convert cleanly.</li>
          <li>Keep custom macros simple, or expand them before converting.</li>
        </ol>
        <p>For most papers the converter gets you 90% of the way in seconds, and the remaining cleanup is a few minutes in Word.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>Is the LaTeX to Word converter free?</summary><div class="faq-body">Yes. The <a href="/tools/latex-to-word/">converter</a> is free, runs in your browser, and your files are never stored.</div></details>
        <details><summary>Will my equations survive the conversion?</summary><div class="faq-body">Most inline and display math converts to native Word equations. Very complex or custom-macro math should be spot-checked after conversion.</div></details>
        <details><summary>How do I keep my citations?</summary><div class="faq-body">Include your <code>.bib</code> file by uploading a ZIP of your project. The converter resolves <code>\cite</code> commands and builds the bibliography in the Word document.</div></details>
        <details><summary>Can I anonymize the paper for blind review?</summary><div class="faq-body">Yes — the converter has an optional anonymize step that strips author identifying information for double-blind submissions.</div></details>
```

`{{FAQ_JSON_ENTRIES}}` (mirror the four FAQs above; strip HTML tags from the answer text):
```json
        { "@type": "Question", "name": "Is the LaTeX to Word converter free?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. The converter is free, runs in your browser, and your files are never stored." } },
        { "@type": "Question", "name": "Will my equations survive the conversion?", "acceptedAnswer": { "@type": "Answer", "text": "Most inline and display math converts to native Word equations. Very complex or custom-macro math should be spot-checked after conversion." } },
        { "@type": "Question", "name": "How do I keep my citations?", "acceptedAnswer": { "@type": "Answer", "text": "Include your .bib file by uploading a ZIP of your project. The converter resolves cite commands and builds the bibliography in the Word document." } },
        { "@type": "Question", "name": "Can I anonymize the paper for blind review?", "acceptedAnswer": { "@type": "Answer", "text": "Yes — the converter has an optional anonymize step that strips author identifying information for double-blind submissions." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/latex-to-word/">Open the LaTeX to Word converter →</a></li>
          <li><a href="/tools/word-to-latex/">Convert Word back to LaTeX →</a></li>
          <li><a href="/guides/latex-word-count/">Count words in a LaTeX document →</a></li>
```

- [ ] **Step 2: Verify**

Load `http://localhost:4200/guides/latex-to-word/`. Confirm: title renders, the tool link `/tools/latex-to-word/` resolves, FAQ `<details>` expand, and the JSON-LD parses (paste the `<script type="application/ld+json">` contents into a JSON validator or run `python3 -c "import json,sys,re; ..."` — or visually confirm matched braces).

- [ ] **Step 3: Commit**

```bash
git add site/guides/latex-to-word/index.html
git commit -m "$(cat <<'EOF'
feat(guides): add 'Convert a LaTeX paper to Word' guide

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Guide 2 — Fix common BibTeX errors

**Files:**
- Create: `site/guides/fix-bibtex-errors/index.html`

- [ ] **Step 1: Create using the SHARED GUIDE SKELETON with these fills**

- `{{TITLE}}` → `How to Fix Common BibTeX Errors | Purplelink LLC`
- `{{OG_TITLE}}` → `How to Fix Common BibTeX Errors`
- `{{META_DESCRIPTION}}` → `The most common BibTeX errors and how to fix them — missing fields, unbalanced braces, duplicate keys, and bad characters — plus a free in-browser .bib validator.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/fix-bibtex-errors/`
- `{{H1}}` → `How to fix common BibTeX errors`
- `{{LEDE}}` → `BibTeX errors are some of the most frustrating to debug because the messages are cryptic. Here are the most common causes and exactly how to fix each one.`

`{{ARTICLE_BODY}}`:
```html
        <p>When your bibliography won't build, the problem is almost always one of a handful of recurring mistakes. Paste your <code>.bib</code> into our free <a href="/tools/bib-validator/">BibTeX validator</a> to spot them instantly, or work through the list below.</p>
        <h2>1. Missing required fields</h2>
        <p>Each entry type requires certain fields. An <code>@article</code> needs <code>author</code>, <code>title</code>, <code>journal</code>, and <code>year</code>; an <code>@inproceedings</code> needs <code>booktitle</code> instead of <code>journal</code>. A missing required field produces a "missing field" warning and a malformed reference. Add the field or switch to the correct entry type.</p>
        <h2>2. Unbalanced braces</h2>
        <p>Every <code>{</code> needs a matching <code>}</code>. A single missing brace often breaks every entry after it, which is why one typo can produce dozens of errors. Check the entry just before the first reported error.</p>
        <h2>3. Duplicate citation keys</h2>
        <p>Two entries with the same key (e.g. <code>@article{smith2020, ...}</code> twice) cause BibTeX to use only one and warn about the collision. Make every key unique.</p>
        <h2>4. Unescaped special characters</h2>
        <p>Characters like <code>&amp;</code>, <code>%</code>, <code>#</code>, and <code>_</code> are special in LaTeX. In a title or journal name, escape them (<code>\&amp;</code>, <code>\%</code>) or they will break the build.</p>
        <h2>5. Missing commas between fields</h2>
        <p>Fields are separated by commas. Forgetting one — especially after a closing brace — produces a confusing parse error. Make sure every field line except the last ends in a comma.</p>
        <h2>6. Smart quotes and stray Unicode</h2>
        <p>Pasting from a website or PDF can introduce curly quotes or non-ASCII characters that BibTeX chokes on. Replace them with plain ASCII, or use a UTF-8-aware engine like Biber.</p>
        <p>Running your file through the <a href="/tools/bib-validator/">validator</a> catches all six categories before you waste a compile cycle.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>Why does one BibTeX error break everything?</summary><div class="faq-body">An unbalanced brace or missing comma can cause the parser to misread every entry that follows. Fix the entry just before the first reported error and re-check.</div></details>
        <details><summary>What fields does each entry type require?</summary><div class="faq-body">An @article needs author, title, journal, and year; @inproceedings needs booktitle; @book needs publisher. The <a href="/tools/bib-validator/">validator</a> flags missing required fields per entry type.</div></details>
        <details><summary>How do I escape special characters in BibTeX?</summary><div class="faq-body">Escape LaTeX-special characters with a backslash: \&amp; for ampersand, \% for percent, \# for hash. Underscores in titles should be escaped or wrapped in math mode.</div></details>
        <details><summary>Is the BibTeX validator free and private?</summary><div class="faq-body">Yes. The validator runs entirely in your browser — your .bib file is never uploaded or stored.</div></details>
```

`{{FAQ_JSON_ENTRIES}}`:
```json
        { "@type": "Question", "name": "Why does one BibTeX error break everything?", "acceptedAnswer": { "@type": "Answer", "text": "An unbalanced brace or missing comma can cause the parser to misread every entry that follows. Fix the entry just before the first reported error and re-check." } },
        { "@type": "Question", "name": "What fields does each entry type require?", "acceptedAnswer": { "@type": "Answer", "text": "An @article needs author, title, journal, and year; @inproceedings needs booktitle; @book needs publisher. The validator flags missing required fields per entry type." } },
        { "@type": "Question", "name": "How do I escape special characters in BibTeX?", "acceptedAnswer": { "@type": "Answer", "text": "Escape LaTeX-special characters with a backslash: ampersand, percent, and hash all need a leading backslash. Underscores in titles should be escaped or wrapped in math mode." } },
        { "@type": "Question", "name": "Is the BibTeX validator free and private?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. The validator runs entirely in your browser — your .bib file is never uploaded or stored." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/bib-validator/">Open the BibTeX validator →</a></li>
          <li><a href="/tools/bib-builder/">Build BibTeX from a DOI or arXiv ID →</a></li>
          <li><a href="/guides/doi-to-bibtex/">Get BibTeX from a DOI or arXiv ID →</a></li>
```

- [ ] **Step 2: Verify** — load `http://localhost:4200/guides/fix-bibtex-errors/`; confirm render, links resolve, JSON-LD parses.

- [ ] **Step 3: Commit**

```bash
git add site/guides/fix-bibtex-errors/index.html
git commit -m "$(cat <<'EOF'
feat(guides): add 'Fix common BibTeX errors' guide

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Guide 3 — IEEE vs APA vs MLA vs Chicago

**Files:**
- Create: `site/guides/citation-styles-explained/index.html`

- [ ] **Step 1: Create using the SHARED GUIDE SKELETON with these fills**

- `{{TITLE}}` → `IEEE vs APA vs MLA vs Chicago: Citation Styles Explained | Purplelink LLC`
- `{{OG_TITLE}}` → `IEEE vs APA vs MLA vs Chicago Citation Styles`
- `{{META_DESCRIPTION}}` → `How the four major citation styles — IEEE, APA, MLA, and Chicago — differ in in-text citations and reference formatting, and when to use each, with a free citation generator.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/citation-styles-explained/`
- `{{H1}}` → `IEEE vs APA vs MLA vs Chicago: which citation style to use`
- `{{LEDE}}` → `The four most common citation styles look similar but differ in how they handle in-text citations and reference lists. Here's a plain comparison and when each is expected.`

`{{ARTICLE_BODY}}`:
```html
        <p>Most fields mandate one citation style. Picking the wrong one is a fast way to get a desk reject, so it's worth knowing the differences. You can format any of these automatically with our free <a href="/tools/citation-generator/">citation generator</a>.</p>
        <h2>IEEE — engineering and computer science</h2>
        <p>IEEE uses <strong>numbered</strong> in-text citations in square brackets, like <code>[1]</code>, in the order sources first appear. The reference list is numbered to match. Author names are given as initials then surname. Expect IEEE for most engineering, CS, and electronics venues.</p>
        <h2>APA — social sciences</h2>
        <p>APA uses <strong>author–date</strong> in-text citations, like <code>(Smith, 2020)</code>. The reference list is alphabetical by author surname, with the year in parentheses near the front. APA emphasizes the date because recency matters in the social sciences. Expect APA in psychology, education, and nursing.</p>
        <h2>MLA — humanities</h2>
        <p>MLA uses <strong>author–page</strong> in-text citations, like <code>(Smith 42)</code>, with no comma and no year. The reference list is titled "Works Cited" and is alphabetical by author. Expect MLA in literature, languages, and cultural studies.</p>
        <h2>Chicago — history and some humanities</h2>
        <p>Chicago has two systems: <strong>notes-bibliography</strong> (footnotes plus a bibliography, common in history) and <strong>author-date</strong> (similar to APA, common in the sciences). Which one you use depends on the discipline and the publisher's instructions.</p>
        <h2>Quick comparison</h2>
        <ul>
          <li><strong>IEEE:</strong> <code>[1]</code> — numbered, by order of appearance.</li>
          <li><strong>APA:</strong> <code>(Smith, 2020)</code> — author and year.</li>
          <li><strong>MLA:</strong> <code>(Smith 42)</code> — author and page.</li>
          <li><strong>Chicago:</strong> footnote¹ or <code>(Smith 2020)</code> depending on the system.</li>
        </ul>
        <p>Always defer to the specific journal or instructor's guidelines — many venues have house variations on these base styles.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>Which citation style should I use?</summary><div class="faq-body">Use whatever your target journal, conference, or instructor requires. As a rough guide: IEEE for engineering and CS, APA for social sciences, MLA for humanities, and Chicago for history.</div></details>
        <details><summary>What is the main difference between IEEE and APA?</summary><div class="faq-body">IEEE uses numbered citations like [1] in order of appearance, while APA uses author–date citations like (Smith, 2020) with an alphabetical reference list.</div></details>
        <details><summary>Does MLA include the year in in-text citations?</summary><div class="faq-body">No. MLA in-text citations use author and page number, like (Smith 42), with no year. The year appears only in the Works Cited entry.</div></details>
        <details><summary>Can I generate these citations automatically?</summary><div class="faq-body">Yes. The free <a href="/tools/citation-generator/">citation generator</a> formats IEEE, APA, MLA, and Chicago citations from the entry fields, entirely in your browser.</div></details>
```

`{{FAQ_JSON_ENTRIES}}`:
```json
        { "@type": "Question", "name": "Which citation style should I use?", "acceptedAnswer": { "@type": "Answer", "text": "Use whatever your target journal, conference, or instructor requires. As a rough guide: IEEE for engineering and CS, APA for social sciences, MLA for humanities, and Chicago for history." } },
        { "@type": "Question", "name": "What is the main difference between IEEE and APA?", "acceptedAnswer": { "@type": "Answer", "text": "IEEE uses numbered citations like [1] in order of appearance, while APA uses author-date citations like (Smith, 2020) with an alphabetical reference list." } },
        { "@type": "Question", "name": "Does MLA include the year in in-text citations?", "acceptedAnswer": { "@type": "Answer", "text": "No. MLA in-text citations use author and page number, like (Smith 42), with no year. The year appears only in the Works Cited entry." } },
        { "@type": "Question", "name": "Can I generate these citations automatically?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. The free citation generator formats IEEE, APA, MLA, and Chicago citations from the entry fields, entirely in your browser." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/citation-generator/">Open the citation generator →</a></li>
          <li><a href="/tools/reference-converter/">Convert references between formats →</a></li>
          <li><a href="/guides/doi-to-bibtex/">Get BibTeX from a DOI or arXiv ID →</a></li>
```

- [ ] **Step 2: Verify** — load `http://localhost:4200/guides/citation-styles-explained/`; confirm render, links, JSON-LD.

- [ ] **Step 3: Commit**

```bash
git add site/guides/citation-styles-explained/index.html
git commit -m "$(cat <<'EOF'
feat(guides): add 'IEEE vs APA vs MLA vs Chicago' guide

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Guides 4, 5, 6 — track changes, word count, DOI to BibTeX

**Files:**
- Create: `site/guides/latex-track-changes/index.html`
- Create: `site/guides/latex-word-count/index.html`
- Create: `site/guides/doi-to-bibtex/index.html`

Each uses the SHARED GUIDE SKELETON. Fills for all three are given below in full.

### Guide 4 — `site/guides/latex-track-changes/index.html`

- `{{TITLE}}` → `How to Show Changes Between Two LaTeX Versions (latexdiff) | Purplelink LLC`
- `{{OG_TITLE}}` → `Track Changes Between Two LaTeX Versions`
- `{{META_DESCRIPTION}}` → `How to show tracked changes between two versions of a LaTeX document using latexdiff — what it marks, common pitfalls, and a free in-browser diff tool.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/latex-track-changes/`
- `{{H1}}` → `How to show changes between two LaTeX versions`
- `{{LEDE}}` → `Reviewers and co-authors often want a "track changes" PDF. LaTeX doesn't have it built in, but latexdiff produces exactly that. Here's how it works.`

`{{ARTICLE_BODY}}`:
```html
        <p>When you submit a revision, editors usually ask for a version that highlights what changed. In Word that's Track Changes; in LaTeX the equivalent is <code>latexdiff</code>, which compares two <code>.tex</code> files and produces a marked-up PDF. Our free <a href="/tools/latex-diff/">LaTeX diff tool</a> runs it for you — upload the old and new versions and get the annotated PDF back.</p>
        <h2>What latexdiff marks</h2>
        <ul>
          <li><strong>Added text</strong> is underlined (and usually shown in blue).</li>
          <li><strong>Deleted text</strong> is struck through (and usually shown in red).</li>
          <li>The document still compiles, so you get a real PDF a reviewer can read.</li>
        </ul>
        <h2>How to use it</h2>
        <ol>
          <li>Keep your <strong>old</strong> (submitted) version and your <strong>new</strong> (revised) version as separate <code>.tex</code> files.</li>
          <li>Upload both to the <a href="/tools/latex-diff/">diff tool</a>, old first, new second.</li>
          <li>Download the marked-up PDF and include it alongside your revision.</li>
        </ol>
        <h2>Common pitfalls</h2>
        <ul>
          <li><strong>Tables can corrupt.</strong> latexdiff sometimes mangles <code>tabular</code> environments. Good tools treat tables as opaque blocks to avoid "Missing \cr" errors — ours does.</li>
          <li><strong>Moved blocks look like delete + add.</strong> If you relocate a paragraph, it shows as removed in one place and added in another.</li>
          <li><strong>Heavy macro use</strong> can confuse the diff; flatten complex macros if the output looks wrong.</li>
        </ul>
        <p>For most revisions, latexdiff gives editors exactly the change-tracked PDF they expect, with no manual highlighting.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>What is latexdiff?</summary><div class="faq-body">latexdiff is a tool that compares two LaTeX source files and produces a marked-up version showing additions (underlined) and deletions (struck through) as a compilable PDF.</div></details>
        <details><summary>Why do my tables break in the diff?</summary><div class="faq-body">latexdiff can corrupt tabular environments. Our <a href="/tools/latex-diff/">diff tool</a> treats tables as opaque blocks to avoid "Missing \cr" errors and table corruption.</div></details>
        <details><summary>Do I need to install anything?</summary><div class="faq-body">No. The free diff tool runs latexdiff in the cloud — upload your two .tex files and download the marked-up PDF. Your files are never stored.</div></details>
        <details><summary>How are additions and deletions shown?</summary><div class="faq-body">Added text is underlined and typically blue; deleted text is struck through and typically red. The result is a normal PDF a reviewer can read.</div></details>
```

`{{FAQ_JSON_ENTRIES}}`:
```json
        { "@type": "Question", "name": "What is latexdiff?", "acceptedAnswer": { "@type": "Answer", "text": "latexdiff is a tool that compares two LaTeX source files and produces a marked-up version showing additions (underlined) and deletions (struck through) as a compilable PDF." } },
        { "@type": "Question", "name": "Why do my tables break in the diff?", "acceptedAnswer": { "@type": "Answer", "text": "latexdiff can corrupt tabular environments. Our diff tool treats tables as opaque blocks to avoid Missing cr errors and table corruption." } },
        { "@type": "Question", "name": "Do I need to install anything?", "acceptedAnswer": { "@type": "Answer", "text": "No. The free diff tool runs latexdiff in the cloud — upload your two .tex files and download the marked-up PDF. Your files are never stored." } },
        { "@type": "Question", "name": "How are additions and deletions shown?", "acceptedAnswer": { "@type": "Answer", "text": "Added text is underlined and typically blue; deleted text is struck through and typically red. The result is a normal PDF a reviewer can read." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/latex-diff/">Open the LaTeX diff tool →</a></li>
          <li><a href="/tools/latex-to-pdf/">Compile LaTeX to PDF →</a></li>
          <li><a href="/guides/latex-to-word/">Convert a LaTeX paper to Word →</a></li>
```

### Guide 5 — `site/guides/latex-word-count/index.html`

- `{{TITLE}}` → `How to Count Words in a LaTeX Document | Purplelink LLC`
- `{{OG_TITLE}}` → `How to Count Words in a LaTeX Document`
- `{{META_DESCRIPTION}}` → `How to get an accurate word count for a LaTeX document — why \wc and editor counts disagree, what counts, and a free word counter that works on .tex source.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/latex-word-count/`
- `{{H1}}` → `How to count words in a LaTeX document`
- `{{LEDE}}` → `Word limits are strict in many venues, but counting words in LaTeX is surprisingly fiddly because of all the markup. Here's how to get a number you can trust.`

`{{ARTICLE_BODY}}`:
```html
        <p>Conferences and journals enforce word and page limits, but LaTeX source is full of commands that aren't words. The challenge is counting the prose without counting the markup. You can paste text into our free <a href="/tools/word-counter/">word counter</a> for an instant count, or read on for the trade-offs.</p>
        <h2>Why counts disagree</h2>
        <p>Three methods give three different numbers:</p>
        <ul>
          <li><strong>Counting the .tex source</strong> includes commands like <code>\section</code> and <code>\cite</code> as "words," inflating the count.</li>
          <li><strong>texcount</strong> (a Perl tool) tries to count only prose, skipping most markup — usually the most accurate for submission limits.</li>
          <li><strong>Counting the compiled PDF</strong> counts what the reader sees but includes figure captions, references, and headers unless you exclude them.</li>
        </ul>
        <h2>The practical approach</h2>
        <ol>
          <li>For a quick estimate, paste your body text into the <a href="/tools/word-counter/">word counter</a> — it reports words, characters, sentences, and reading time live.</li>
          <li>For a strict submission limit, decide what the venue counts: does the limit include the abstract? References? Captions? Read the call for papers.</li>
          <li>Count the relevant sections only, excluding the bibliography and any appendices that don't count toward the limit.</li>
        </ol>
        <h2>What usually does <em>not</em> count</h2>
        <ul>
          <li>The reference list / bibliography.</li>
          <li>Figure and table captions (venue-dependent).</li>
          <li>Author names and affiliations.</li>
          <li>Appendices (venue-dependent).</li>
        </ul>
        <p>When in doubt, the safest move is to be slightly under the limit using the strictest reasonable interpretation.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>Why is my LaTeX word count different from Word's?</summary><div class="faq-body">LaTeX source includes markup commands that aren't prose. Counting the raw .tex inflates the number, while tools like texcount or counting the compiled text give a closer match to what a reader sees.</div></details>
        <details><summary>Does the bibliography count toward a word limit?</summary><div class="faq-body">Usually not, but it is venue-dependent. Check the call for papers — some limits exclude references, captions, and appendices, and some don't.</div></details>
        <details><summary>Can I count words without compiling?</summary><div class="faq-body">Yes. Paste your body text into the free <a href="/tools/word-counter/">word counter</a> for an instant count. It runs entirely in your browser and stores nothing.</div></details>
        <details><summary>Does the counter handle LaTeX commands?</summary><div class="faq-body">The counter treats any non-whitespace sequence as a word, so raw commands are counted as written. For prose-only counts, paste the text without the surrounding markup.</div></details>
```

`{{FAQ_JSON_ENTRIES}}`:
```json
        { "@type": "Question", "name": "Why is my LaTeX word count different from Word's?", "acceptedAnswer": { "@type": "Answer", "text": "LaTeX source includes markup commands that aren't prose. Counting the raw .tex inflates the number, while tools like texcount or counting the compiled text give a closer match to what a reader sees." } },
        { "@type": "Question", "name": "Does the bibliography count toward a word limit?", "acceptedAnswer": { "@type": "Answer", "text": "Usually not, but it is venue-dependent. Check the call for papers — some limits exclude references, captions, and appendices, and some don't." } },
        { "@type": "Question", "name": "Can I count words without compiling?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. Paste your body text into the free word counter for an instant count. It runs entirely in your browser and stores nothing." } },
        { "@type": "Question", "name": "Does the counter handle LaTeX commands?", "acceptedAnswer": { "@type": "Answer", "text": "The counter treats any non-whitespace sequence as a word, so raw commands are counted as written. For prose-only counts, paste the text without the surrounding markup." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/word-counter/">Open the word counter →</a></li>
          <li><a href="/tools/latex-to-word/">Convert LaTeX to Word →</a></li>
          <li><a href="/guides/latex-to-word/">Convert a LaTeX paper to Word →</a></li>
```

### Guide 6 — `site/guides/doi-to-bibtex/index.html`

- `{{TITLE}}` → `How to Get BibTeX from a DOI or arXiv ID | Purplelink LLC`
- `{{OG_TITLE}}` → `Get BibTeX from a DOI or arXiv ID`
- `{{META_DESCRIPTION}}` → `How to turn a DOI or arXiv ID into a clean BibTeX entry — where the data comes from, what to clean up, and a free in-browser BibTeX builder.`
- `{{CANONICAL}}` → `https://purplelink.llc/guides/doi-to-bibtex/`
- `{{H1}}` → `How to get BibTeX from a DOI or arXiv ID`
- `{{LEDE}}` → `Typing BibTeX by hand is error-prone. If a paper has a DOI or an arXiv ID, you can fetch a clean entry automatically. Here's how, and what to double-check.`

`{{ARTICLE_BODY}}`:
```html
        <p>Most modern papers have a DOI (a string like <code>10.1145/3292500.3330701</code>) or an arXiv ID (like <code>2103.00020</code>). Either one is enough to pull a complete BibTeX entry. Our free <a href="/tools/bib-builder/">BibTeX builder</a> does this — paste the identifier and get an entry back, with nothing stored.</p>
        <h2>Where the data comes from</h2>
        <p>For a DOI, the entry is fetched from <strong>Crossref</strong>, the registry that publishers submit metadata to. For an arXiv ID, it comes from arXiv's own metadata. Because it's pulled from the authoritative source, the title, authors, year, and venue are usually correct out of the box.</p>
        <h2>How to do it</h2>
        <ol>
          <li>Find the DOI (on the paper's first page or the publisher's site) or the arXiv ID (in the URL or PDF header).</li>
          <li>Paste it into the <a href="/tools/bib-builder/">BibTeX builder</a>.</li>
          <li>Copy the generated entry into your <code>.bib</code> file.</li>
        </ol>
        <h2>What to double-check</h2>
        <ul>
          <li><strong>Author accents and special characters.</strong> Names with diacritics sometimes need a quick review.</li>
          <li><strong>Title capitalization.</strong> Wrap words you want to keep capitalized in braces, e.g. <code>{LaTeX}</code>, so BibTeX doesn't lowercase them.</li>
          <li><strong>Entry type.</strong> A preprint may come back as <code>@misc</code> or <code>@article</code>; pick what your bibliography style expects.</li>
          <li><strong>The citation key.</strong> Rename it to match your own convention (e.g. <code>author2021keyword</code>).</li>
        </ul>
        <p>Then run the result through the <a href="/tools/bib-validator/">validator</a> to be sure it's clean before you compile.</p>
```

`{{FAQ_DETAILS}}`:
```html
        <details><summary>Where does the BibTeX data come from?</summary><div class="faq-body">DOIs are resolved via Crossref, the publisher metadata registry; arXiv IDs use arXiv's metadata. Both are authoritative sources, so the core fields are usually correct.</div></details>
        <details><summary>What if the title's capitalization is wrong?</summary><div class="faq-body">BibTeX lowercases titles unless you protect words with braces. Wrap proper nouns or acronyms in braces, like {LaTeX}, to keep their capitalization.</div></details>
        <details><summary>Is the BibTeX builder free and private?</summary><div class="faq-body">Yes. The <a href="/tools/bib-builder/">builder</a> fetches the entry and stores nothing — the identifier and result are not retained.</div></details>
        <details><summary>Can I get BibTeX from an arXiv ID without a DOI?</summary><div class="faq-body">Yes. Paste the arXiv ID (e.g. 2103.00020) directly; the builder retrieves the metadata from arXiv.</div></details>
```

`{{FAQ_JSON_ENTRIES}}`:
```json
        { "@type": "Question", "name": "Where does the BibTeX data come from?", "acceptedAnswer": { "@type": "Answer", "text": "DOIs are resolved via Crossref, the publisher metadata registry; arXiv IDs use arXiv's metadata. Both are authoritative sources, so the core fields are usually correct." } },
        { "@type": "Question", "name": "What if the title's capitalization is wrong?", "acceptedAnswer": { "@type": "Answer", "text": "BibTeX lowercases titles unless you protect words with braces. Wrap proper nouns or acronyms in braces to keep their capitalization." } },
        { "@type": "Question", "name": "Is the BibTeX builder free and private?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. The builder fetches the entry and stores nothing — the identifier and result are not retained." } },
        { "@type": "Question", "name": "Can I get BibTeX from an arXiv ID without a DOI?", "acceptedAnswer": { "@type": "Answer", "text": "Yes. Paste the arXiv ID directly; the builder retrieves the metadata from arXiv." } }
```

`{{RELATED_LINKS}}`:
```html
          <li><a href="/tools/bib-builder/">Open the BibTeX builder →</a></li>
          <li><a href="/tools/bib-validator/">Validate a .bib file →</a></li>
          <li><a href="/guides/fix-bibtex-errors/">Fix common BibTeX errors →</a></li>
```

- [ ] **Step 1: Create all three files** using the skeleton and the fills above.

- [ ] **Step 2: Verify** — load each of `http://localhost:4200/guides/latex-track-changes/`, `/guides/latex-word-count/`, `/guides/doi-to-bibtex/`; confirm render, links resolve, and JSON-LD parses on each.

- [ ] **Step 3: Commit**

```bash
git add site/guides/latex-track-changes/index.html site/guides/latex-word-count/index.html site/guides/doi-to-bibtex/index.html
git commit -m "$(cat <<'EOF'
feat(guides): add track-changes, word-count, and DOI-to-BibTeX guides

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

> After this task completes, return to **Task 3** (reciprocal tool→guide links) if it was deferred, so those links no longer 404.

---

## Task 9: Add `/guides/` URLs to the sitemap

**Files:**
- Modify: `site/sitemap.xml`

**Context:** The sitemap uses single-line `<url>` entries. Guides are evergreen content; use `changefreq=monthly` and `priority=0.6` (slightly below tools at 0.7, above nothing critical). Add the index + 6 guides before the closing `</urlset>`.

- [ ] **Step 1: Insert the 7 new URL entries immediately before `</urlset>`**

```xml
  <url><loc>https://purplelink.llc/guides/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>
  <url><loc>https://purplelink.llc/guides/latex-to-word/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://purplelink.llc/guides/fix-bibtex-errors/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://purplelink.llc/guides/citation-styles-explained/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://purplelink.llc/guides/latex-track-changes/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://purplelink.llc/guides/latex-word-count/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://purplelink.llc/guides/doi-to-bibtex/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
```

- [ ] **Step 2: Verify the XML is well-formed**

Run: `python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse('site/sitemap.xml'); print('valid')"`
Expected: `valid`.

- [ ] **Step 3: Commit**

```bash
git add site/sitemap.xml
git commit -m "$(cat <<'EOF'
feat(seo): add /guides/ section to sitemap

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Write the outreach playbook doc

**Files:**
- Create: `docs/organic-traffic/outreach-playbook.md`

**Context:** Claude cannot post to third-party platforms. This is a written playbook the user executes. It must contain concrete copy templates and a target list, with the rule that every post points at a Phase-1/2 optimized page.

- [ ] **Step 1: Create the playbook**

```markdown
# Community Outreach & Backlinks Playbook — Free LaTeX Tools

> Execution doc for the human. Claude cannot post to third-party platforms;
> this is the runbook to do it yourself. Every post points at an optimized
> tool or guide page (never the bare homepage).

## Ground rules

1. **Be useful first.** On Q&A and discussion sites, answer the actual
   question. Link to a tool/guide only when it genuinely helps. Drive-by
   link drops get removed and hurt the brand.
2. **One link per post**, to the single most relevant page.
3. **Disclose** that you built it ("I made this free tool…") — required on
   most communities and builds trust.
4. **No tracking params.** Link to the clean URL (privacy brand).
5. **Space it out.** Don't post to five subreddits the same day.

## Target list

### Reddit (launch posts / helpful replies)
- **r/LaTeX** — most relevant. Lead with the tool that solves a recurring
  pain (latexdiff, LaTeX→Word).
- **r/PhD**, **r/AskAcademia** — frame around the workflow problem, not the
  tool. ("Submitting a revision? Here's how I generate a tracked-changes PDF.")
- **r/GradSchool** — word-count and citation-style guides fit here.

### TeX StackExchange
- Answer real questions about latexdiff, .tex→.docx, word counts, BibTeX
  errors. Link the matching guide as supporting material, not the answer
  itself.

### Academic Mastodon (e.g. fediscience.org, mastodon.social #academia)
- Short post per tool, one image (the OG card), link to the guide.

### Show HN (Hacker News)
- One post for the whole suite: "Show HN: Free privacy-first LaTeX tools
  (no upload stored)". Target the **/tools/** hub. Privacy angle is the hook.

### Durable listings (backlinks + GEO)
- **GitHub "awesome" lists**: awesome-LaTeX, awesome-academic-writing — open
  a PR adding the relevant tool.
- **AlternativeTo** — list as a free alternative to Overleaf utilities /
  paid converters.
- **Tool directories**: free-for.dev, relevant academic-tool roundups.

## Copy templates

### Reddit — r/LaTeX (tool-led)
> **Title:** I built a free, no-signup [latexdiff / LaTeX→Word / …] tool —
> files are never stored
>
> **Body:** I kept needing [the specific task] and wanted something that
> didn't require an account or upload my drafts to a server I don't trust.
> So I made a free one: [URL]. It [one sentence on what it does and the
> privacy property]. Source of the conversion is [Pandoc/latexdiff/Crossref]
> under the hood. Feedback welcome — happy to add formats people need.

### TeX StackExchange — answer pattern
> [Direct, complete answer to their question in your own words.]
>
> If you'd rather not run it locally, I maintain a free tool that does this:
> [URL] (no install, files aren't stored). [One line on the key caveat,
> e.g. how it handles tables.]

### Show HN
> **Title:** Show HN: Free privacy-first LaTeX tools (nothing stored)
>
> **Body:** A small suite of free LaTeX/academic tools — compile to PDF,
> diff two versions, convert to Word, build BibTeX from a DOI, and more.
> No accounts, no analytics, no cookies; uploaded files are processed and
> discarded. Built it because the existing options either want a login or
> keep your drafts. Hub: https://purplelink.llc/tools/

### Academic Mastodon
> Free + no-signup [tool name] for [audience]: [URL]. [Privacy line.]
> Part of a small set of LaTeX tools I maintain. #academia #LaTeX #phd

## Page-to-channel mapping

| Page | Best channels |
|------|---------------|
| /tools/ hub | Show HN, awesome-lists, AlternativeTo |
| /tools/latex-diff/ + /guides/latex-track-changes/ | r/LaTeX, TeX.SE (revision Qs) |
| /tools/latex-to-word/ + /guides/latex-to-word/ | r/AskAcademia, r/PhD |
| /tools/bib-builder/ + /guides/doi-to-bibtex/ | r/LaTeX, TeX.SE (BibTeX Qs) |
| /tools/citation-generator/ + /guides/citation-styles-explained/ | r/GradSchool, r/AskAcademia |
| /tools/word-counter/ + /guides/latex-word-count/ | r/PhD, r/GradSchool |

## Cadence

- **Week 1:** Show HN (hub) + one r/LaTeX tool post.
- **Weeks 2–6:** one community post or TeX.SE answer per week, rotating
  through the mapping above.
- **Ongoing:** answer TeX.SE questions as they appear; open one awesome-list
  PR per relevant list.
- Track referral spikes in Netlify referrer logs (see measurement doc).
```

- [ ] **Step 2: Commit**

```bash
git add docs/organic-traffic/outreach-playbook.md
git commit -m "$(cat <<'EOF'
docs(organic-traffic): add community outreach & backlinks playbook

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Write the measurement doc

**Files:**
- Create: `docs/organic-traffic/measurement.md`

**Context:** Defines GSC as the primary KPI source and Netlify referrer logs for community traffic, with the checkpoint thresholds from the spec. Must explicitly state no site-side analytics is added.

- [ ] **Step 1: Create the measurement doc**

```markdown
# Measurement — Organic Traffic Program (brand-safe)

> **Privacy brand constraint:** this program adds **no site-side analytics,
> no cookies, no tracking scripts, no pixels.** Measurement is limited to
> Google Search Console (server-side, aggregate) and Netlify's own
> referrer/deploy logs (server-side, no visitor PII). A privacy-preserving
> server-side hit counter on the Modal backend is a separate future
> sub-project, not part of this program.

## Primary source: Google Search Console (GSC)

GSC is the source of truth for organic search performance. It reports
aggregate, privacy-safe data Google already has — nothing is added to the
site.

**Metrics to watch (Performance report):**

| Metric | What it tells you | Where |
|--------|-------------------|-------|
| Impressions | How often a page appeared in results | Performance → Pages |
| Clicks | How often someone clicked through | Performance → Pages |
| Average position | Typical ranking for a query | Performance → Queries |
| Queries | The actual searches surfacing each page | Performance → Queries |
| Coverage / Indexed | Whether a page is indexed at all | Pages report |

**How to read them:**
- **Impressions before clicks.** A new guide earns impressions first; clicks
  follow as it climbs. Rising impressions on a page that's a week old is the
  early success signal.
- **Position 11–20 = page 2.** Pages ranking there are the best optimization
  targets (small improvements can move them to page 1).
- **Query mismatch.** If a page ranks for queries you didn't intend, the
  intro/FAQ phrasing is steering it — adjust the literal wording to match the
  query you want.
- **Submit new URLs** via URL Inspection → Request Indexing after each ship
  (sitemap already lists them, but requesting speeds it up).

## Secondary source: Netlify referrer logs

For community-driven referral traffic (Phase 3), Netlify's analytics/logs
show referrers server-side without any client tracking.

- **Referrer spikes** after a Reddit/HN/Mastodon post confirm the post drove
  traffic and to which page.
- **Top pages** indicate which tool/guide resonates.
- Note: Netlify Analytics is server-log based (paid add-on); if not enabled,
  deploy logs and any function logs still show referrer headers.

## Checkpoint thresholds (from the spec)

**~30 days after Phase 1 ships:**
- [ ] All 13 tool pages register impressions in GSC.
- [ ] All 13 tools present in `llms.txt`. (Done in Task 1.)
- [ ] Every tool page has intro + FAQ + related-tools. (Verified in Task 2.)
- [ ] All 6 guides + the guides index indexed (Coverage report).

**~90 days:**
- [ ] The 6 guides registering impressions.
- [ ] Measurable click growth on tool pages vs. the 30-day baseline.
- [ ] A set of academic queries ranking in the top 20 (position ≤ 20).

**Phase 3 (ongoing):**
- [ ] Referral spikes from community posts visible in Netlify referrer logs.
- [ ] Durable backlinks live in at least a few directories/lists.

## Review cadence

- **Weekly (5 min):** glance at GSC Performance for new impressions and any
  page that jumped/dropped. Check Netlify referrers if a post went out.
- **Monthly:** compare against the checkpoint thresholds; pick the two page-2
  pages with the most impressions and improve their on-page wording.
```

- [ ] **Step 2: Commit**

```bash
git add docs/organic-traffic/measurement.md
git commit -m "$(cat <<'EOF'
docs(organic-traffic): add brand-safe measurement doc

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Final verification + deploy to production

**Files:**
- None (verification + deploy only)

**Context:** Ship everything to Netlify prod and confirm the live URLs resolve. No backend changes were made, so no Modal deploy is needed.

- [ ] **Step 1: Full local link check**

Run:
```bash
for u in guides/ guides/latex-to-word/ guides/fix-bibtex-errors/ guides/citation-styles-explained/ guides/latex-track-changes/ guides/latex-word-count/ guides/doi-to-bibtex/; do test -f "site/$u/index.html" -o -f "site/${u}index.html" && echo "OK $u" || echo "MISSING $u"; done
```
Expected: all `OK`.

- [ ] **Step 2: Validate all guide JSON-LD blocks parse**

Run:
```bash
python3 - <<'PY'
import json, re, pathlib
for p in pathlib.Path("site/guides").rglob("index.html"):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', p.read_text(), re.S)
    for b in blocks:
        json.loads(b)
    print("OK", p, len(blocks), "block(s)")
PY
```
Expected: `OK` for all 7 pages (index + 6 guides), no JSON exceptions.

- [ ] **Step 3: Verify the guides index and one guide in the preview**

Load `http://localhost:4200/guides/` and `http://localhost:4200/guides/latex-to-word/`. Confirm nav shows the "Guides" item highlighted, all 6 index links resolve (no 404), and the tool links in a guide resolve.

- [ ] **Step 4: Deploy to Netlify production**

Run: `netlify deploy --dir=site --prod`
Expected: deploy succeeds; note the live URL.

- [ ] **Step 5: Spot-check live URLs**

Run:
```bash
for u in /guides/ /guides/latex-to-word/ /guides/doi-to-bibtex/ /llms.txt /sitemap.xml; do printf "%-30s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' "https://purplelink.llc$u")"; done
```
Expected: all `200`.

- [ ] **Step 6: (Manual, user) Request indexing in GSC**

In Google Search Console, use URL Inspection → Request Indexing for
`https://purplelink.llc/guides/` and each of the 6 guide URLs. The sitemap
already lists them, but this speeds up discovery. (This is a user action;
note it for the user — Claude cannot access GSC.)

---

## Self-Review (completed during plan authoring)

**Spec coverage:**
- Phase 1.1 complete `llms.txt` → Task 1. ✔
- Phase 1.2 answer-shaped on-page content (13 pages) → Task 2 (verification; confirmed already present this session). ✔
- Phase 1.3 internal linking → Task 3 (tool→guide reciprocal links) + existing related-tools blocks. ✔
- Phase 2.1 `/guides/` section (templated layout, index, sitemap) → Tasks 4, 9. ✔
- Phase 2.2 six seed guides → Tasks 5–8. ✔
- Phase 2.3 cadence → recorded in outreach playbook (Task 10) + measurement (Task 11). ✔
- Phase 3 outreach playbook → Task 10. ✔
- Measurement doc → Task 11. ✔
- Deploy/verify → Task 12. ✔

**Placeholder scan:** The `{{...}}` tokens in the SHARED GUIDE SKELETON are not placeholders left for the engineer to invent — every one is filled with exact, complete content in the per-guide tasks. No "TBD"/"add appropriate"/"similar to Task N" instructions remain.

**Type/consistency:** Guide slugs match across llms.txt (Task 1), reciprocal links (Task 3), sitemap (Task 9), and the create tasks (4–8): `latex-to-word`, `fix-bibtex-errors`, `citation-styles-explained`, `latex-track-changes`, `latex-word-count`, `doi-to-bibtex`. FAQ visible text and JSON-LD entries are specified to mirror each other. OG image path is uniform (`/assets/og/tools-launch.png`). CSS classes (`tools-hero`, `post-hero`, `post-body`, `tool-faq`, `tool-related`, `back-link`, footer/topbar) all reuse existing `/styles.css` classes confirmed in the live tool/blog pages.

**Ordering note:** Task 3 (reciprocal links) depends on the guides existing (Tasks 4–8). The plan flags this: defer Task 3's edits until after Task 8 if executing strictly top-to-bottom.
```
