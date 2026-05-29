# ModernTex Funnel CTAs — Design Spec

## Context

Purplelink LLC runs 13 free LaTeX/academic web tools at `/tools/` plus 6 how-to
guides at `/guides/`. These exist as top-of-funnel marketing for the studio's
native macOS product, **ModernTex**. The organic-traffic program (shipped
2026-05-28) now drives qualified academic traffic to these pages — but none of
the tool or guide pages mention ModernTex or offer any path to it. The funnel
is currently open at the top and closed at the bottom.

ModernTex is **pre-launch**: its page (`/moderntex/`) offers a waitlist email
form (Netlify Forms, server-side, no client tracking), not a purchase. The
realistic conversion action from a tool/guide page is therefore a **waitlist
signup**, not a sale.

### Hard constraints

- **Privacy brand.** No cookies, no analytics scripts, no tracking technology
  of any kind. The CTA adds none.
- **No JavaScript dependency.** The signup form must work with JS disabled
  (server-side Netlify Forms), consistent with the existing `/moderntex/` form.
- **Static site.** Pages are hand-authored static HTML under `site/`, deployed
  to Netlify. No build step / templating engine is introduced.

## Goal & success criteria

Give every tool and guide page a consistent, honest path into the ModernTex
waitlist, and capture which page each signup came from.

- Inline waitlist CTA present on all 13 tool pages + 6 guide pages (19 total).
- All signups aggregate into the existing single ModernTex waitlist (one form),
  each tagged with a `source` value identifying the originating page.
- The CTA works with JavaScript disabled.
- No new CSS framework, no new global nav item, no tracking added.

## Decisions (resolved during brainstorming)

1. **CTA action:** inline waitlist email form embedded on every tool and guide
   page (not merely a link). The link to `/moderntex/` remains as a secondary
   "learn more" touchpoint within the block.
2. **Coverage:** all 13 tools + all 6 guides (no "plain link only" tier).
3. **Attribution:** each form carries a hidden static `source` field with the
   page identity (e.g. `tool:latex-diff`, `guide:doi-to-bibtex`).
4. **Implementation approach:** shared static HTML block copied into each page
   (reusing existing waitlist styling), inserted via a one-time script — the
   same pattern used for the site-wide footer Guides link. (Rejected: JS
   injection; build-time templating — both out of proportion to the change.)

## Architecture

### Form

- **One Netlify form**, reusing the **same form name** as the existing
  `/moderntex/` waitlist (`waitlist-moderntex`) so every signup lands in one
  list. Netlify aggregates submissions from all pages posting to that name.
- Each embed includes a **hidden `source` field** with a static per-page value
  set in the HTML (not by JS). Netlify captures it as a column in the form
  dashboard.
- For consistency, the existing `/moderntex/` form also gets
  `source: moderntex-page` added so its origin is labeled alongside the others.
- Standard Netlify anti-spam: `data-netlify="true"`,
  `data-netlify-honeypot="bot-field"`, hidden `form-name` matching the form
  name, and the hidden honeypot `bot-field` — mirroring the current form.

### CTA block

A single shared HTML section, structurally identical across all 19 pages except
for the `source` value. Reuses the existing waitlist styling so **no new CSS is
required** (apply the existing `waitlist-section` class, or an alias class that
inherits the same rules — implementer's choice, but no net-new visual design).

Block contents (in order):
- eyebrow line: "From the team behind these tools"
- headline (`<h2>`): "Writing LaTeX on a Mac?"
- sub-line: "We're building ModernTex — a native macOS LaTeX studio. Join the
  waitlist for one email at launch."
- the Netlify form: hidden `form-name`, hidden honeypot, hidden `source`, an
  `email` input (`type=email`, `required`, `autocomplete=email`), submit button
  ("Notify me at launch")
- fine print: "We'll only use your email to notify you at launch." + link to
  `/privacy/`
- secondary link: "Learn more about ModernTex →" to `/moderntex/`

### Placement

Consistent slot across page types, at the "you just got value" moment:
- **Tool pages:** after the tool's interactive area, **immediately before** the
  `<nav class="tool-related">` related-tools block.
- **Guide pages:** after the article body, **before** the reciprocal tool-links
  section.

No new entry in the global top nav or footer (the inline block is the funnel;
existing nav stays as-is).

## Components / units

| Unit | Responsibility |
|------|----------------|
| Shared CTA HTML block | The markup inserted into each page (one canonical version + per-page `source`) |
| Insertion script (one-time) | Idempotently inserts the block at the correct slot in all 19 pages; reports changed/skipped like the footer script |
| `/moderntex/` form edit | Add `source: moderntex-page` hidden field to the existing form |

## Data flow

1. Visitor on a tool/guide page submits the inline form.
2. Browser POSTs to Netlify Forms (server-side) — no client storage, no JS
   required.
3. Netlify records the submission under `waitlist-moderntex`, including the
   page's `source` value.
4. Owner reads per-source conversion counts in the Netlify form dashboard.

## Error handling / edge cases

- **JS disabled:** form submits normally (native HTML form POST). Verified in
  testing.
- **Netlify form detection:** Netlify parses deployed static HTML to register
  forms and fields. Because all pages share the form name and include the
  `source` field, the field is registered once and captured for every page. The
  block must be present in the deployed HTML (it is — static).
- **Idempotency:** the insertion script must skip any page that already contains
  the CTA block (so re-runs don't duplicate it), matching the footer-script
  pattern.
- **Topbar/footer false matches:** the insertion anchor must be specific to the
  intended slot (e.g. the `tool-related` nav open tag / guide tool-links
  anchor), not a string that also appears elsewhere on the page.

## Testing

1. Every one of the 19 pages still parses (well-formed HTML) after insertion.
2. The CTA block appears exactly once per page, in the correct slot.
3. Each page's `source` value is unique and correct (`tool:<slug>` /
   `guide:<slug>`).
4. After deploy: Netlify lists the `waitlist-moderntex` form with an `email` and
   a `source` field.
5. Submit one test signup from a tool page and one from a guide page; confirm
   both appear in the dashboard with the right `source`.
6. Confirm the block renders and the form submits with JavaScript disabled.

## Out of scope (YAGNI)

- Any analytics/tracking script or cookie.
- A new global nav/footer ModernTex link.
- New CSS design language (reuse existing waitlist styling).
- Per-page bespoke copy (one shared message; only `source` varies).
- The privacy-preserving hit counter (separate future sub-project).
- Changes to the ModernTex page beyond adding the `source` hidden field.

## Deliverable units

1. Shared CTA HTML block (canonical markup).
2. Insertion applied to all 13 tool pages + 6 guide pages, each with its
   `source` value.
3. `source: moderntex-page` added to the existing `/moderntex/` form.
4. Verified parse + correct slot + JS-disabled submit; deploy; confirm Netlify
   form detection and a test signup per page type.
