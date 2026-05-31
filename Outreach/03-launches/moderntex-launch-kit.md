# ModernTex — launch kit (template)

ModernTex is the strongest launch story of the three because:
- Definable niche (academic LaTeX writers on Mac)
- Specific competitor cluster (TeXShop, Texifier, Octree)
- Strong adjacent communities (TeX SE, r/LaTeX, #academictwitter, r/PhD)
- Pre-existing topical authority via the LaTeX guides on the site

## Pre-launch (2 weeks before)

- [ ] Mac App Store listing live (or direct DMG; pick one)
- [ ] Refresh `/moderntex/` with download links + price
- [ ] Update `SoftwareApplication.downloadUrl` JSON-LD
- [ ] Update `/guides/best-mac-latex-editors/` — change "in development" → "now shipping"
- [ ] Write a launch announcement blog post for `/blog/launching-moderntex/` (TBD)

## Show HN

**Title:**
> Show HN: ModernTex – a native macOS LaTeX editor for academic manuscripts

**Body:**

> Hi HN — Ben from Purplelink LLC.
>
> ModernTex is a native macOS LaTeX editor I built for one specific use case: writing journal-length academic manuscripts. Not for LaTeX-as-typesetting-language; for LaTeX-as-academic-writing-tool. The distinction matters because the existing options optimize for one or the other:
>
> - **TeXShop**: free, reliable, but the interface is 2010. Fine for power users, hostile to newcomers.
> - **Texifier**: polished and modern, but generalist — it's great at LaTeX, not specifically at manuscripts.
> - **Octree**: AI-assisted, but cloud-first. Your draft lives on someone else's server.
> - **VS Code + LaTeX Workshop**: works, but the document feels like a code file.
> - **Overleaf**: collaborative + web-only.
>
> ModernTex narrows: multi-file manuscript navigation with structural sidebar by chapter/section, plain-language compile errors (BibTeX's "missing field smith2024" becomes "Missing required field 'journal' in entry smith2024"), BibTeX autocomplete that searches by author/title across your entire `.bib`, revision snapshots tied to ideas not files, submission-readiness checks for journal-specific requirements (e.g., "ACM template detected, file passes their checklist").
>
> The interesting technical bits: tree-sitter for parsing, native PDFKit for the preview (no Electron wrapper), the BibTeX autocomplete uses an SQLite FTS index of the user's .bib regenerated on save.
>
> Comparison vs the alternatives: https://purplelink.llc/guides/best-mac-latex-editors
> Mac App Store: [URL]
>
> Pricing: $29 once, no subscription. The first manuscript you compile pays for it.
>
> Happy to take questions on the architecture, the niche choice, or anything else.

## TeX StackExchange

This is where I'd post the most valuable single answer. **Don't make a launch post on TeX SE — they hate that.** Instead:

- Pick the 5–10 best-answered questions about "native Mac LaTeX editor", "what's the best LaTeX editor for...", etc. from the target list
- On each, add a comment to the existing accepted answer: "[Editor] is also worth considering for manuscript-specific workflows — comparison here: [link]"
- Wait. The community will discover.

## r/LaTeX

**Title:**
> [OC] After 2 years of writing journal papers in TeXShop/VS Code/Texifier, I built the LaTeX editor I actually wanted (macOS)

**Body:**

> Long-time LaTeX writer here. Got tired of the trade-offs in existing editors and built ModernTex — a native macOS app focused on academic manuscript workflows.
>
> What's different:
>
> - Plain-language compile errors instead of "I was expecting a comma."
> - Multi-file structural sidebar (chapter / section / bibliography navigation).
> - BibTeX autocomplete by author or title.
> - Revision snapshots tied to ideas, not files.
> - Submission-readiness checks for journal-specific formatting.
>
> Comparison vs TeXShop, Texifier, Octree, VS Code, Overleaf: [URL]
>
> Mac App Store: [URL]. $29 once, no subscription. AMA on the architecture or any of the choices.

## r/AcademicMac, r/PhD, r/GradSchool

Lighter touch — these aren't tool-launch communities. Post only if relevant context appears, and lead with a tip from the guides rather than the tool announcement.

## LinkedIn

> ModernTex ships today.
>
> A native macOS LaTeX editor for academic manuscripts — multi-file navigation, plain-language compile errors, BibTeX autocomplete by author or title, submission-readiness checks. Built for the workflow of writing a journal article, not a code file.
>
> Mac App Store: [URL]
> Honest comparison vs every other Mac LaTeX editor: purplelink.llc/guides/best-mac-latex-editors
>
> $29 once. No subscription.
>
> #LaTeX #AcademicWriting #macOS

## Bluesky

> ModernTex shipped.
>
> Native macOS LaTeX editor for academic manuscripts. Multi-file navigation, plain-language errors, BibTeX autocomplete by author/title.
>
> $29 once. Mac App Store: [URL]
> Comparison: purplelink.llc/guides/best-mac-latex-editors

## Newsletter pitches

- **MacStories** — strongest single placement for a Mac-native indie launch. Targeted pitch with the architectural decisions (PDFKit not Electron, tree-sitter, etc.).
- **iOS Dev Weekly** — light fit (iOS only) but Dave covers Mac when it's notable.
- **Lobste.rs** — short, specific submission about the tree-sitter usage if you want a technical audience.
- **/r/Compsci** newsletter / community boards at the major CS-PhD-producing universities (CMU, Stanford, MIT, Berkeley) — many maintain internal recommended-tool lists.

## Long-tail: university LibGuides

After launch, the LibGuides outreach (see `04-outreach/`) becomes worth it again. Specifically target:
- Anywhere that already lists Overleaf, Texifier, or TeXShop as recommended editors.
- Computer-science department wikis at PhD-granting universities.
- Math-department LaTeX tutorials at universities that produce many papers.

The pitch: "I noticed your guide lists [X] as a Mac LaTeX editor. ModernTex is a newer option built specifically for academic manuscripts — happy to provide a copy for evaluation."

## Don't do

- Don't position ModernTex as "better than Texifier." Texifier is excellent for its audience. ModernTex is for a narrower slice.
- Don't subscription-pricing model. Academic users hate it and the audience is small enough that one-time pricing builds goodwill.
- Don't downplay alternatives. Honest comparison plays better than zero-sum framing.
