# ModernTex listings, October 2026 (drafts only)

Nothing here has been submitted. Product facts come from `site/moderntex/index.html` and `site/llms.txt` (lines 28 to 38) as of 2026-10-01. Vendor rules were read on 2026-10-01 (Homebrew) and 2026-09-29 (AlternativeTo, MacUpdate; see `docs/directory-submissions.md` in the main checkout).

## (a) Homebrew cask

### Verdict

**Not possible today in the official `homebrew/cask` repository.** Two blockers are ours to fix and one is not.

| Requirement | Today | Met? |
|---|---|---|
| Notability | Closed-source app, first released 2026-09-04, no public repository, a handful of buyers, no independent coverage or third-party requests for a cask | No |
| Stable, versioned, publicly fetchable URL | The only public URL is `https://purplelink.llc/.netlify/functions/moderntex-download?trial=1`, which streams whichever `ModernTex-Trial-x.y.z.dmg` is newest. It has no version in it and its bytes change at every release | No |
| sha256 | Cannot be pinned against a URL whose content changes. Only `version :latest` with `sha256 :no_check` would work | No |
| Trial eligibility | The trial copy unlocks with the license key and needs no second download to become the full app, but it carries no Sparkle feed, so a buyer must install the paid DMG once to get updates | Borderline |
| Gatekeeper | Signed and notarized disk image | Yes |
| Public fetch | No session or account for the trial; 20 downloads per IP per day (`TRIAL_DAILY_LIMIT` in `netlify/functions/moderntex-download.mjs`) | Yes, with a cap |

The paid DMG cannot be a cask at all: it is served only to a paid Stripe session (`?session_id=cs_...&file=...`), and Homebrew rejects "a download hidden behind account registration" or any equivalent gate.

### What Homebrew's pages say (read 2026-10-01)

`docs.brew.sh/Adding-Software-to-Homebrew` carries no cask URL or notability rule of its own. Its only cask instruction is: "For a cask, use the Cask Cookbook for token rules, required stanzas, artifact selection, uninstall behaviour and `zap` guidance." The rules below are from the pages it points to.

Notability, from `docs.brew.sh/Package-Acceptance-Policy` (the "shared notability metrics" that Acceptable Casks links to):

> A new package must demonstrate public interest beyond its author. A GitHub project normally satisfies this requirement by meeting one of these thresholds: at least 30 forks, 30 watchers or 75 stars; at least 90 forks, 90 watchers or 225 stars for a self-submission by the repository owner. Equivalent public evidence may be considered for software hosted elsewhere. [...] A code repository less than 30 days old is normally not eligible.

Notability exceptions, from `docs.brew.sh/Acceptable-Casks`:

> A recently released application may receive further consideration when there is substantial, independently verifiable public interest and multiple requests for inclusion. These circumstances permit further review but do not guarantee inclusion.

Trials, from `docs.brew.sh/Acceptable-Casks`:

> A time-limited trial is eligible only when the same download can be activated as the full version without being downloaded again.

Gated downloads, from `docs.brew.sh/Acceptable-Casks`:

> An unendorsed third-party build, a binary available only through a forum or similar posting or a download hidden behind account registration on a host unrelated to the homepage is not eligible.

Gatekeeper, from `docs.brew.sh/Acceptable-Casks`:

> On macOS, apps, installers and other executable artefacts that Gatekeeper can assess must pass Homebrew's Gatekeeper checks and must not require System Integrity Protection or Gatekeeper to be disabled or bypassed.

URL and checksum, from `docs.brew.sh/Cask-Cookbook`. Neither Acceptable Casks nor Adding Software uses the words "stable URL"; the working rule is in the Cookbook's `sha256` and `version` stanzas:

> The special value `sha256 :no_check` is used to turn off SHA checking whenever checksumming is impractical due to the upstream configuration, e.g. when `url` does not change between releases.

> The special value `version :latest` is used when: `url` does not contain any version information and there is no way to retrieve the version using a `livecheck`.

So an unversioned URL is tolerated by the tooling, but only as an unchecked `:latest` cask, and that does nothing for the notability rule.

### What would have to change

1. **A versioned public trial URL.** For example `https://purplelink.llc/moderntex/download/ModernTex-Trial-1.3.0.dmg`, or `?trial=1&version=1.3.0` on the existing function, serving that exact file for as long as the version exists in the `moderntex-files` store. The function already matches `ModernTex-Trial-x.y.z.dmg` names, so this is a small addition to the trial branch; the unversioned `?trial=1` stays for the site button.
2. **A public version source for `livecheck`.** The Sparkle appcast is token-gated (`X-ModernTex-Channel`) and lists only paid builds. A cask needs either a public trial appcast or the version string on `/moderntex/` (already there as "Version 1.3.0").
3. **The trial rate limit.** 20 per IP per day is fine for individual users. Homebrew CI and university NAT addresses could hit it; exempting the versioned path or raising the cap for it would avoid failed installs.
4. **Trial and paid in one build.** To satisfy the trial rule without argument, the trial DMG should update itself once licensed (give it the Sparkle feed after a key is entered), so "the same download" really is the full version.
5. **Notability.** Not something a code change fixes. It needs independent, checkable public interest: reviews, forum threads, listing pages, and requests for a cask from people other than the author. Revisit after the listings below are live and there is evidence to cite.

### What is possible today

A cask in **our own tap** (for example `purplelink-llc/homebrew-tap`, installed with `brew install --cask purplelink-llc/tap/moderntex`). A tap we own has no notability review. It would still be better after change 1, so the cask can pin a version and a sha256.

No cask Ruby file is included in this document: the requirements for a pinned `version` and `sha256` cannot be met until change 1 ships, and a `:latest` plus `:no_check` draft would be thrown away the day it does. Once a versioned URL exists, the cask is about twelve lines (`version`, `sha256`, `url`, `name`, `desc`, `homepage`, `livecheck`, `depends_on macos: ">= :sonoma"`, `app "ModernTex.app"`, `zap`). The `zap` paths and the bundle identifier must be read from the ModernTex repo, not guessed.

## (b) MacUpdate submission draft

Submit page: https://www.macupdate.com/help/submit-app. Field names are the ones quoted from that page in `docs/directory-submissions.md` section 5.

Not confirmed: fees, review time, icon and screenshot specifications, and whether a free listing requires a link back to MacUpdate from our site. The support article on listing terms returned 404 on 2026-09-29. Read the terms on the form before submitting and stop if they ask for payment or a reciprocal link.

- **App Name:** `ModernTex`
- **Developer:** `Purplelink LLC`
- **Category:** Productivity, or Education if the form offers a Writing or LaTeX subcategory (choose the closest; the site lists it as "Productivity / academic writing")
- **Price:** `10` USD, one-time. License type: Shareware or Trial (7 days).
- **Version:** `1.3.0`
- **Download URL:** `https://purplelink.llc/moderntex/` (the product page; the trial button is there). The direct trial link `https://purplelink.llc/.netlify/functions/moderntex-download?trial=1` works without an account, but it is unversioned and capped per IP, so use it only if the form insists on a direct file link.
- **Product Page URL:** `https://purplelink.llc/moderntex/`
- **Support URL:** `https://purplelink.llc/support/`
- **System Requirements:**

```
macOS 14 Sonoma or later. Apple silicon and Intel. Needs a TeX distribution (MacTeX or TinyTeX); if neither is installed, ModernTex offers a one-click TinyTeX install. 15 MB disk image, signed and notarized.
```

- **Short Description:**

```
A native macOS LaTeX editor for researchers.
```

- **Description** (MacUpdate asks for no promotional text and no pricing here):

```
ModernTex is a native macOS LaTeX editor for academic writing. It handles multi-file manuscripts with root file detection and a structured sidebar, and keeps the source and the PDF in sync in both directions: click the source to jump to the PDF, or the PDF to jump to the source. Three compile modes (Fast, Live and Full) cover drafting and the final build.

LaTeX errors are explained in plain language with a suggested fix. BibTeX completion searches the whole bibliography by author, title or key. Submission checks look at anonymization, page limits, required sections and packaging before a manuscript goes to a journal. Snapshots record a version before a revision and show the difference between two of them.

A visual TikZ Designer builds flowcharts and diagrams by dragging shapes and connections, and a Table Editor accepts a range pasted from Excel or Google Sheets; both write ordinary LaTeX into the document. Files stay as ordinary .tex and .bib files in a folder on your disk, with no account and no cloud storage. There is no real-time co-editing.
```

- **Version Changes (1.3.0):**

```
Table Editor: paste a range from a spreadsheet and get booktabs-style LaTeX. Version 1.2.0 added the TikZ Designer.
```

- **Screenshots**, in this order, from `site/assets/moderntex-screens/`:
  1. `01-editor-clean.webp` (2880 x 1584): outline, source and synced PDF side by side. Lead image.
  2. `07-tikz-editor.webp` (2840 x 1812): the TikZ Designer.
  3. `08-table-editor.webp` (1488 x 974): the Table Editor.

  Skip `01-editor.webp`; it duplicates the first. The files are WebP. If the form refuses WebP, export PNG copies first (`sips -s format png <file> --out <file>.png`).
- **Icon:** the app icon from the ModernTex repo, at the size the form asks for.

## (c) AlternativeTo entry draft

Rules, from https://alternativeto.net/faq/ (read 2026-09-29): verify your email before submitting; descriptions must not contain addresses, telephone numbers, email addresses or website links; English only; the app must be released. The optional $5 fee only moves the entry up the queue; skip it. Expect a backlog of months. Submit path: user icon, top right, "Suggest new application".

- **Name:** `ModernTex`
- **Website:** `https://purplelink.llc/moderntex/` (in the URL field only, never in the description)
- **Platform:** Mac
- **License:** Commercial, free trial (7 days), then $19.99 one-time
- **Short description:**

```
A native macOS LaTeX editor for researchers.
```

- **Description** (no links, no email address):

```
ModernTex is a native macOS LaTeX editor for academic writing. It keeps the source and the PDF in sync in both directions, explains LaTeX errors in plain language, and checks a manuscript for anonymization, page limits and required sections before submission. It also offers revision snapshots, BibTeX completion that searches the whole bibliography, a visual TikZ Designer and a spreadsheet-style Table Editor. It runs on macOS 14 or later, on Apple silicon and Intel, and uses MacTeX or TinyTeX. There is a free 7-day trial, then a one-time $19.99 purchase with all updates included, forever. Files stay as ordinary .tex and .bib files on your disk. It compiles on your Mac, with no account, and does not offer real-time co-editing.
```

- **Tags:** LaTeX, LaTeX editor, academic writing, PDF preview, BibTeX
- **Alternative to:** Overleaf, TeXShop, Texifier. All three are named on the ModernTex page. Confirm each exists in the form's search before selecting it.
- **Screenshots:** the same three as MacUpdate, same order.

## Fact sources

| Claim | Source |
|---|---|
| $19.99 once, free 7-day trial, all updates included, forever | `site/moderntex/index.html` "At a glance", Price row; `site/pricing/index.html` Apps section |
| Version 1.3.0, 15 MB, macOS 14 or later, Apple silicon and Intel, signed and notarized | `site/moderntex/index.html` hero note and "Runs on" row |
| MacTeX or TinyTeX, one-click TinyTeX install | "TeX distribution" row |
| Sync both ways, three compile modes, BibTeX search, plain-language errors, submission checks, snapshots, TikZ Designer, Table Editor | Features section |
| No real-time co-editing; ordinary files; no account | "Working with co-authors" and "Your files" rows |
| Trial served at `?trial=1`, unversioned, 20 per IP per day; paid DMG session-gated; appcast token-gated | `netlify/functions/moderntex-download.mjs` header comment and trial branch; `docs/products/moderntex.md` |
