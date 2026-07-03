# Zotero Plugin + Directory Submissions — Scoping

Status: **scoping only, not built**. Per the growth-automation plan this task
came from: "Separate smaller project: a Zotero plugin for distribution, plus
PRs to awesome-research/awesome-zotero and academic-tool directories. Mostly
manual/one-time, not automation-heavy." This doc is the output of that
scoping pass — a future session should pick it up to actually build/submit.

## 1. Directory submissions (verified real targets)

Researched live against GitHub on 2026-07-03 — do not resubmit this research
without re-checking activity, since "awesome list" maintenance status shifts
fast (see the dead links below).

### Submit now

| Target | URL | Why | Contribution format |
|---|---|---|---|
| **writing-resources/awesome-scientific-writing** | github.com/writing-resources/awesome-scientific-writing | 960 stars, active (pushed 2026-03-06), successor to a dead "awesome-academic-writing" repo. Directly relevant to Reference Converter, BibTeX Validator/Builder, Citation Generator today — no plugin needed. | PR adding one entry, short pitch, must show maintenance (commit/release in past 3 years), validated by awesome-lint CI. |
| **MohamedElashri/awesome-zotero** | github.com/MohamedElashri/awesome-zotero | 451 stars, most recently active of the two `awesome-zotero` repos (pushed 2026-07-02). Best target **once a Zotero plugin exists** (see below) — not for the web tools. | PR using `.github/PULL_REQUEST_TEMPLATE.md`, one item per PR, title format `Add item: [name]`, alphabetical placement in `_README.md`. Curation is explicitly strict — rejects anything reading as AI-generated filler or lacking real docs/usage evidence. A submission needs a solid README and a public demo, not just a link. |

### Skip (verified dead, deprecated, or wrong format)

- **emptymalei/awesome-research** — 2,692 stars but the maintainer explicitly deprecated it in favor of an external site (tools.kausalflow.com). Don't submit here; it won't get reviewed.
- **degregat/awesome-research**, **TnTo/awesome-research** — abandoned since 2022.
- **"awesome-academic"**, **"awesome-research-tools"**, **"awesome-bibtex"** — none of these exist as real repos. Don't reference them in future copy or outreach as if they're real targets.
- **egeerardyn/awesome-LaTeX** — pushes look recent but no merged *content* PR found since ~2023; likely CI/maintenance-only activity. Low probability of a submission actually landing — worth a try only after the two "submit now" targets, not a priority.
- **zotero-chinese/zotero-plugins** — the repo itself states plugin-entry maintenance is suspended, despite ongoing infra commits.
- **OpenMindClub/awesome-zotero** — the other `awesome-zotero`, still active (453 stars, pushed 2025-11-16) but slightly less recently active than MohamedElashri's. Worth a second PR after the first lands, not instead of it.
- **Zotero's own site** — there is no official curated plugin directory on zotero.org. The community-standard discovery surfaces are the two `awesome-zotero` lists above and the GitHub `zotero-plugin` topic tag.

### Separate, technical listing (not a markdown PR)

**syt2/zotero-addons** (1,613 stars, active) is an in-app Zotero plugin
marketplace — JSON-based submission, not a README PR. Only relevant once a
Purplelink plugin actually exists and needs in-app discoverability, not for
today's web tools.

## 2. Zotero plugin — what it would do

Scoped around what Purplelink already has a paid/free backend for, not new
product surface:

1. **Citation Gap check from inside Zotero.** Select a collection, right-click
   → "Check for citation gaps" → sends the item metadata to the existing
   Citation Gap endpoint, returns a report. This is the single feature that
   justifies the plugin's existence — it's not replicable as a copy-paste web
   tool the way the converters are, since it needs library access.
2. **One-click export presets.** "Export as [Venue]'s format" using the same
   dataset as `/format/references-for-*/` (see `scripts/format_pages_data.py`)
   — picks BibTeX/RIS/EndNote per venue without the user manually checking.
3. **BibTeX Validator on save.** Optional: flag entries with missing DOIs or
   fields that would trip the free BibTeX Validator, inline in the Zotero
   library view.

Feature 1 is the only one that requires a paid-API round-trip; 2 and 3 could
ship as a free, standalone plugin with no backend calls at all (2 is a static
dataset lookup, 3 reuses existing client-side validation logic already in
`site/tools/bib-validator/`).

### Technical shape (Zotero 7 plugin architecture)

- Zotero 7 plugins are WebExtension-style: a `manifest.json` + a bootstrap
  script (`bootstrap.js`) registering lifecycle hooks (`startup`, `shutdown`,
  `install`, `uninstall`) — no XUL, unlike pre-7 plugins. Distributed as a
  `.xpi` (a zip).
- UI is added via Zotero's `Zotero.PreferencePanes` / item-pane / context-menu
  registration APIs, not a full custom window — keeps the plugin thin.
- No official public plugin store; distribution is either direct `.xpi`
  download + manual install, or the community `awesome-zotero` /
  `zotero-addons` listings above.
- **Before starting a build:** the exact current Zotero 7 plugin API surface
  should be re-verified against Zotero's own developer docs at build time —
  this scoping pass didn't do a line-by-line API check, and plugin APIs are
  the kind of thing that drifts between Zotero point releases.

### Rough effort estimate

Feature 1 (Citation Gap integration) is the bulk of the work — UI
registration, item-metadata → API-payload mapping, results display, and
handling the same job-token/polling pattern the web tools use. Features 2–3
are each a much smaller, mostly-static addition on top of that scaffolding.
Given this is a new distribution channel (not a new product), it's worth
building only after the web-based growth plays in this cycle have had time
to show traction — revisit sizing once there's a working Modal endpoint this
plugin can actually call and real usage data to justify the ongoing
maintenance surface a browser-extension-adjacent codebase adds.

## 3. Recommended order of operations

1. Submit the `writing-resources/awesome-scientific-writing` PR now — no
   plugin dependency, uses tools that already exist and are live.
2. Hold the `awesome-zotero` PRs until the plugin exists; a submission with
   nothing to link to won't survive that repo's strict curation bar.
3. Scope the plugin build as its own brainstorming/spec pass (this doc is
   input to that, not a replacement for it) once there's bandwidth for a
   genuinely new codebase surface.
