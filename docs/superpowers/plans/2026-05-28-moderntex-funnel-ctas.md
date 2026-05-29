# ModernTex Funnel CTAs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline ModernTex waitlist CTA to all 13 tool pages + 6 guide pages, funneling qualified academic traffic into the existing waitlist with per-page source attribution.

**Architecture:** A single canonical HTML block (reusing the global `.waitlist-section`/`.waitlist-form` CSS already in `site/styles.css`) is inserted immediately before the `<nav class="tool-related">` block on each of the 19 pages, via a one-time idempotent Python script — the same pattern used for the site-wide footer Guides link. Each block posts to the existing `waitlist-moderntex` Netlify form and carries a static hidden `source` field identifying the page. The existing `/moderntex/` form also gains a `source` field for consistency. No JavaScript, no new CSS, no tracking.

**Tech Stack:** Static HTML/CSS under `site/`, Netlify Forms (server-side, no JS), Netlify CLI for deploy, Python 3 for the one-time insertion + verification scripts.

---

## Background the engineer needs

- The site is hand-authored static HTML. Every page links the same global stylesheet (`/styles.css`), so the waitlist classes (`.waitlist-section`, `.waitlist-form`, `.waitlist-fine-print`, `.eyebrow`) render correctly on any page with no new CSS.
- **Netlify Forms** detects forms by parsing deployed static HTML at deploy time. A form is keyed by its `name` attribute and a matching hidden `form-name` input. Multiple pages may post to the same form name; Netlify aggregates all submissions under that one form and records the union of all fields seen (so the `source` field becomes a column). Anti-spam uses a hidden honeypot field (`bot-field`) declared via `data-netlify-honeypot="bot-field"`.
- The existing waitlist form lives at `site/moderntex/index.html` lines ~204-209:
  ```html
        <form class="waitlist-form" name="waitlist-moderntex" method="POST" data-netlify="true" data-netlify-honeypot="bot-field">
          <input type="hidden" name="form-name" value="waitlist-moderntex">
          <p hidden><input name="bot-field"></p>
          <input type="email" name="email" placeholder="your@email.com" required autocomplete="email">
          <button type="submit">Notify me at launch</button>
        </form>
  ```
- **Insertion anchor (identical on tools and guides):** the line `      <nav class="tool-related"` (6 leading spaces) occurs exactly once per page, inside `<main>`, after the tool UI / article + FAQ. The CTA block is inserted immediately before it at the same 6-space indentation.
- **The 19 target pages:**
  - Tools (13): `site/tools/<slug>/index.html` for slugs: `bib-builder`, `bib-validator`, `citation-generator`, `equation-renderer`, `latex-diff`, `latex-table-generator`, `latex-to-pdf`, `latex-to-word`, `markdown-to-pdf`, `pdf-tools`, `reference-converter`, `word-counter`, `word-to-latex`.
  - Guides (6): `site/guides/<slug>/index.html` for slugs: `citation-styles-explained`, `doi-to-bibtex`, `fix-bibtex-errors`, `latex-to-word`, `latex-track-changes`, `latex-word-count`.
- **Source value convention:** `tool:<slug>` for tools, `guide:<slug>` for guides. The `latex-to-word` slug exists as both a tool and a guide; the `tool:`/`guide:` prefix disambiguates them.
- `site/moderntex/index.html` is **not** one of the 19 — it is edited separately in Task 1.

## File structure

| File | Responsibility | Action |
|------|----------------|--------|
| `site/moderntex/index.html` | Existing waitlist page | Modify: add hidden `source` field to its form |
| `scripts/insert_moderntex_cta.py` | One-time idempotent inserter for the 19 pages | Create |
| `scripts/verify_moderntex_cta.py` | Assert end-state invariants across the 19 pages | Create |
| `site/tools/<slug>/index.html` (13) | Tool pages | Modify: CTA block inserted by script |
| `site/guides/<slug>/index.html` (6) | Guide pages | Modify: CTA block inserted by script |

The two scripts live in the existing `scripts/` directory (where `with_server.py` etc. already live). They are one-time utilities, committed for reproducibility.

---

### Task 1: Add `source` field to the existing ModernTex form

**Files:**
- Modify: `site/moderntex/index.html` (the `waitlist-moderntex` form, ~line 205)

- [ ] **Step 1: Verify the current form has no source field**

Run: `grep -c 'name="source"' "site/moderntex/index.html"`
Expected: `0`

- [ ] **Step 2: Add the hidden source field**

Use an exact-string edit. Replace:
```html
        <input type="hidden" name="form-name" value="waitlist-moderntex">
        <p hidden><input name="bot-field"></p>
```
with:
```html
        <input type="hidden" name="form-name" value="waitlist-moderntex">
        <input type="hidden" name="source" value="moderntex-page">
        <p hidden><input name="bot-field"></p>
```

- [ ] **Step 3: Verify the field was added exactly once**

Run: `grep -c 'name="source" value="moderntex-page"' "site/moderntex/index.html"`
Expected: `1`

- [ ] **Step 4: Confirm the page still has exactly one form and one closing tag**

Run: `grep -c '<form ' "site/moderntex/index.html"; grep -c '</form>' "site/moderntex/index.html"`
Expected: `1` and `1`

- [ ] **Step 5: Commit**

```bash
git add site/moderntex/index.html
git commit -m "feat(funnel): tag ModernTex waitlist form with source field"
```

---

### Task 2: Write the verification script (defines the end state)

This script encodes every invariant the inserted CTA must satisfy. It is written first so it FAILS before insertion and PASSES after — the TDD check for an HTML-content change.

**Files:**
- Create: `scripts/verify_moderntex_cta.py`

- [ ] **Step 1: Write the verifier**

Create `scripts/verify_moderntex_cta.py` with exactly:
```python
#!/usr/bin/env python3
"""Verify the ModernTex CTA block is present and correct on all 19 pages."""
import sys

TOOL_SLUGS = [
    "bib-builder", "bib-validator", "citation-generator", "equation-renderer",
    "latex-diff", "latex-table-generator", "latex-to-pdf", "latex-to-word",
    "markdown-to-pdf", "pdf-tools", "reference-converter", "word-counter",
    "word-to-latex",
]
GUIDE_SLUGS = [
    "citation-styles-explained", "doi-to-bibtex", "fix-bibtex-errors",
    "latex-to-word", "latex-track-changes", "latex-word-count",
]

MARKER = "<!-- moderntex-cta -->"


def targets():
    for s in TOOL_SLUGS:
        yield f"site/tools/{s}/index.html", f"tool:{s}"
    for s in GUIDE_SLUGS:
        yield f"site/guides/{s}/index.html", f"guide:{s}"


def check(path, source):
    errors = []
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    # Exactly one CTA block.
    if html.count(MARKER) != 1:
        errors.append(f"{path}: expected 1 '{MARKER}', found {html.count(MARKER)}")
    # Exactly one CTA form posting to the shared waitlist.
    if html.count('name="waitlist-moderntex"') != 1:
        errors.append(f"{path}: expected 1 waitlist-moderntex form, found "
                      f"{html.count('name=\"waitlist-moderntex\"')}")
    # Correct, unique source value.
    needle = f'name="source" value="{source}"'
    if html.count(needle) != 1:
        errors.append(f"{path}: expected 1 '{needle}', found {html.count(needle)}")
    # CTA must appear before the related-tools nav.
    cta_i = html.find(MARKER)
    nav_i = html.find('<nav class="tool-related"')
    if cta_i == -1 or nav_i == -1 or cta_i >= nav_i:
        errors.append(f"{path}: CTA not positioned before tool-related nav "
                      f"(cta={cta_i}, nav={nav_i})")
    # Structure intact: still exactly one <main> and one footer.
    if html.count("</main>") != 1:
        errors.append(f"{path}: expected 1 '</main>', found {html.count('</main>')}")
    if html.count('<footer class="footer"') != 1:
        errors.append(f"{path}: expected 1 footer, found "
                      f"{html.count('<footer class=\"footer\"')}")
    return errors


def main():
    all_errors = []
    for path, source in targets():
        all_errors.extend(check(path, source))
    if all_errors:
        for e in all_errors:
            print("FAIL", e)
        print(f"\n{len(all_errors)} problems across pages")
        sys.exit(1)
    print("OK: all 19 pages have a correct, unique ModernTex CTA block")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the verifier and confirm it FAILS (no blocks inserted yet)**

Run: `python3 scripts/verify_moderntex_cta.py`
Expected: many `FAIL ... expected 1 '<!-- moderntex-cta -->', found 0` lines and exit code 1.

- [ ] **Step 3: Commit the verifier**

```bash
git add scripts/verify_moderntex_cta.py
git commit -m "test(funnel): add verifier for ModernTex CTA invariants"
```

---

### Task 3: Write the insertion script and insert the CTA on all 19 pages

**Files:**
- Create: `scripts/insert_moderntex_cta.py`
- Modify (via the script): all 13 tool + 6 guide `index.html` files

- [ ] **Step 1: Write the inserter**

Create `scripts/insert_moderntex_cta.py` with exactly:
```python
#!/usr/bin/env python3
"""Insert the ModernTex waitlist CTA block into all 19 tool/guide pages.

Idempotent: a page that already contains the CTA marker is skipped, so the
script is safe to re-run. The block is inserted immediately before the
'<nav class="tool-related"' line, at 6-space indentation, matching the
surrounding <main> content.
"""
import sys

TOOL_SLUGS = [
    "bib-builder", "bib-validator", "citation-generator", "equation-renderer",
    "latex-diff", "latex-table-generator", "latex-to-pdf", "latex-to-word",
    "markdown-to-pdf", "pdf-tools", "reference-converter", "word-counter",
    "word-to-latex",
]
GUIDE_SLUGS = [
    "citation-styles-explained", "doi-to-bibtex", "fix-bibtex-errors",
    "latex-to-word", "latex-track-changes", "latex-word-count",
]

MARKER = "<!-- moderntex-cta -->"
ANCHOR = '      <nav class="tool-related"'


def block(source):
    return (
        f"      {MARKER}\n"
        '      <section class="waitlist-section">\n'
        '        <p class="eyebrow">From the team behind these tools</p>\n'
        "        <h2>Writing LaTeX on a Mac?</h2>\n"
        "        <p>We're building ModernTex — a native macOS LaTeX studio. "
        "Join the waitlist for one email at launch.</p>\n"
        '        <form class="waitlist-form" name="waitlist-moderntex" '
        'method="POST" data-netlify="true" data-netlify-honeypot="bot-field">\n'
        '          <input type="hidden" name="form-name" value="waitlist-moderntex">\n'
        f'          <input type="hidden" name="source" value="{source}">\n'
        '          <p hidden><input name="bot-field"></p>\n'
        '          <input type="email" name="email" placeholder="your@email.com" '
        'required autocomplete="email">\n'
        '          <button type="submit">Notify me at launch</button>\n'
        "        </form>\n"
        '        <p class="waitlist-fine-print">We\'ll only use your email to '
        'notify you at launch. <a href="/privacy/">Privacy Policy</a> · '
        '<a href="/moderntex/">Learn more about ModernTex →</a></p>\n'
        "      </section>\n\n"
    )


def targets():
    for s in TOOL_SLUGS:
        yield f"site/tools/{s}/index.html", f"tool:{s}"
    for s in GUIDE_SLUGS:
        yield f"site/guides/{s}/index.html", f"guide:{s}"


def main():
    changed, skipped, failed = [], [], []
    for path, source in targets():
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        if MARKER in html:
            skipped.append((path, "already has CTA"))
            continue
        idx = html.find(ANCHOR)
        if idx == -1:
            failed.append((path, "anchor not found"))
            continue
        if html.find(ANCHOR, idx + 1) != -1:
            failed.append((path, "anchor found more than once"))
            continue
        new_html = html[:idx] + block(source) + html[idx:]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_html)
        changed.append(path)

    print(f"changed: {len(changed)}")
    print(f"skipped: {len(skipped)}")
    for p, r in skipped:
        print("  SKIP", p, "-", r)
    if failed:
        for p, r in failed:
            print("  FAIL", p, "-", r)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the inserter**

Run: `python3 scripts/insert_moderntex_cta.py`
Expected:
```
changed: 19
skipped: 0
```
(no `FAIL` lines)

- [ ] **Step 3: Run the verifier and confirm it PASSES**

Run: `python3 scripts/verify_moderntex_cta.py`
Expected: `OK: all 19 pages have a correct, unique ModernTex CTA block` and exit code 0.

- [ ] **Step 4: Confirm idempotency — re-running the inserter changes nothing**

Run: `python3 scripts/insert_moderntex_cta.py`
Expected:
```
changed: 0
skipped: 19
```
(every line a `SKIP ... already has CTA`)

- [ ] **Step 5: Sanity-check the diff is purely additive**

Run: `git diff --numstat -- site | awk '{a+=$1; d+=$2} END{print "added:"a" removed:"d}'`
Expected: `removed:0` (only insertions across the 19 files).

- [ ] **Step 6: Eyeball one tool and one guide render of the block**

Run: `awk '/<!-- moderntex-cta -->/,/<\/section>/' site/tools/latex-diff/index.html`
Expected: prints the CTA block with `value="tool:latex-diff"`.

Run: `awk '/<!-- moderntex-cta -->/,/<\/section>/' site/guides/doi-to-bibtex/index.html`
Expected: prints the CTA block with `value="guide:doi-to-bibtex"`.

- [ ] **Step 7: Commit**

```bash
git add scripts/insert_moderntex_cta.py site/tools site/guides
git commit -m "feat(funnel): add inline ModernTex waitlist CTA to all tool + guide pages"
```

---

### Task 4: Deploy and verify the live funnel

This task is gated on explicit user confirmation before the production deploy (per project convention: confirm before visible/external actions). Do not run the deploy command until the user says go.

**Files:** none (deploy + live checks only)

- [ ] **Step 1: Ask the user to confirm the production deploy**

State: "Funnel CTA is committed across 19 pages + the ModernTex form. Ready to deploy to production?" Wait for an affirmative reply.

- [ ] **Step 2: Deploy to production**

Run: `netlify deploy --dir=site --prod`
Expected: `Deploy is live!` and an upload count of at least 20 files (19 pages + moderntex page).

- [ ] **Step 3: Verify the CTA is live on a tool, a guide, and the count is right**

Run:
```bash
for u in https://purplelink.llc/tools/latex-diff/ https://purplelink.llc/guides/doi-to-bibtex/; do
  echo "=== $u ==="
  curl -s "$u" | grep -o 'name="source" value="[^"]*"'
done
```
Expected:
```
=== https://purplelink.llc/tools/latex-diff/ ===
name="source" value="tool:latex-diff"
=== https://purplelink.llc/guides/doi-to-bibtex/ ===
name="source" value="guide:doi-to-bibtex"
```

- [ ] **Step 4: Confirm Netlify registered the form with the source field**

Tell the user to check, or run if Netlify CLI form listing is available:
Run: `netlify api listSiteForms 2>/dev/null | grep -i 'waitlist\|source' || echo "check the Netlify dashboard: Forms → waitlist-moderntex should list email + source fields"`
Expected: the `waitlist-moderntex` form lists both an `email` and a `source` field. (Netlify registers new fields on the deploy that first contains them; if `source` is missing, confirm the deploy completed and re-check.)

- [ ] **Step 5: Submit one test signup from a tool page and one from a guide page**

In a browser with JavaScript disabled (to prove the no-JS requirement), open `https://purplelink.llc/tools/latex-diff/`, enter a test address (e.g. `ben+test-tool@purplelink.llc`), submit; repeat on `https://purplelink.llc/guides/doi-to-bibtex/` with `ben+test-guide@purplelink.llc`.
Expected: each submission shows Netlify's success response (no JS error), and the two entries appear in the Netlify Forms dashboard with `source` = `tool:latex-diff` and `guide:doi-to-bibtex` respectively.

- [ ] **Step 6: Record completion**

No commit needed (deploy only). Report the live verification result and the two test-signup sources to the user.

---

## Self-review

**Spec coverage:**
- Inline CTA on all 13 tools + 6 guides → Task 3 (insertion across all 19).
- One Netlify form, same `waitlist-moderntex` name → block markup in Task 3 + Task 1.
- Per-page hidden `source` field → Task 3 block + Task 2 verifier asserts uniqueness/correctness.
- `source: moderntex-page` on existing form → Task 1.
- Reuse existing waitlist styling, no new CSS → block uses `.waitlist-section`/`.waitlist-form`/`.waitlist-fine-print`/`.eyebrow`; no CSS task exists (intentional).
- No JS → native HTML form; Task 4 Step 5 tests with JS disabled.
- Idempotent one-time script like footer link → Task 3 inserter + Step 4 idempotency check.
- Placement before related-tools nav → ANCHOR + verifier position check.
- Testing (parse, slot, source, Netlify detection, signup, no-JS) → Task 2 verifier + Task 4 live checks.

**Placeholder scan:** none — every code/command step is concrete.

**Consistency:** `MARKER`, `ANCHOR`, slug lists, and `source` convention are identical between the inserter (Task 3) and verifier (Task 2). The block's `</section>` close is included so the verifier's structural/positional checks hold.
