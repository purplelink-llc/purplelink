# Discovered Outreach Targets

Generated 2026-05-31. Methodology: WebSearch + WebFetch. Reddit and tex.stackexchange.com are blocked by the fetch tool, so those sections list **only entries verified via search-engine snippets or external citations**, not URLs I could load directly. Treat the Reddit/TeX.SE sections as starting points to verify manually before sending outreach.

---

## 1. TeX StackExchange questions

**Honest caveat:** The fetch tool cannot reach tex.stackexchange.com directly, and Google's `site:` operator returned no link results in this environment. Rather than fabricate URLs, I am listing **search-target patterns** to run manually on tex.stackexchange.com. These are the highest-yield query patterns based on what tools we have:

| Search query on tex.stackexchange.com | Matching tool/guide |
|---|---|
| `convert .tex to .docx` (sort: newest) | LaTeX to Word tool |
| `bibtex syntax error` / `bibtex bad entry` | BibTeX Validator + fix-bibtex-errors guide |
| `latexdiff` (filter: active, last 2 yrs) | LaTeX Diff tool + latex-track-changes guide |
| `doi to bibtex` / `cite by doi` | Citation Generator + doi-to-bibtex guide |
| `word count latex` | Word Counter tool + latex-word-count guide |
| `bibtex unbalanced braces` | BibTeX Validator |
| `track changes latex collaborator` | LaTeX Diff + latex-track-changes guide |
| `citation style change biblatex` | citation-styles-explained guide |
| `latex to pdf bibliography missing` | fix-bibtex-errors guide |
| `convert latex equation to word` | Equation Renderer + LaTeX to Word tool |

One real, verifiable thread surfaced via GitHub-issue citation:
- **latexdiff "extra }" with sections** — referenced in [ftilmann/latexdiff issue #13](https://github.com/ftilmann/latexdiff/issues/13), which cites a TeX.SE answer. Matches LaTeX Diff tool + latex-track-changes guide.

---

## 2. Reddit threads (recent)

**Honest caveat:** Reddit fetch is blocked and search queries returned no usable post URLs. **I cannot verify any specific Reddit thread URLs.** The community-level pattern is real (these subs do discuss our topics), but specific thread URLs must be confirmed manually.

Recommended manual search URLs to check during outreach review:
- `https://www.reddit.com/r/LaTeX/search/?q=word+convert&restrict_sr=on&t=year`
- `https://www.reddit.com/r/LaTeX/search/?q=bibtex+error&restrict_sr=on&t=year`
- `https://www.reddit.com/r/LaTeX/search/?q=latexdiff&restrict_sr=on&t=year`
- `https://www.reddit.com/r/AskAcademia/search/?q=latex+to+word&restrict_sr=on&t=year`
- `https://www.reddit.com/r/PhD/search/?q=latex+revision&restrict_sr=on&t=year`

No Reddit entries listed below — better to leave this blank than pad with unverified URLs.

---

## 3. University library LibGuides (verified)

All 8 entries below were fetched and confirmed live. Where a named librarian was visible, contact is included; where only a general email was shown, that is noted.

1. **MIT Libraries — LaTeX and BibTeX**
   - URL: https://libguides.mit.edu/cite-write/bibtex
   - Lists: Overleaf, JabRef, Zotero+Better BibTeX, Mendeley
   - Contact: no named librarian on page; route via MIT Libraries Ask form
   - Fit: BibTeX Builder, BibTeX Validator, doi-to-bibtex guide

2. **University of Virginia — Overleaf/LaTeX for Scholarly Writing**
   - URL: https://guides.lib.virginia.edu/overleaf-writing
   - Lists: Overleaf, reference manager integrations
   - **Contact: Ricky Patterson — ricky@virginia.edu** (Brown Sci & Eng Library)
   - Fit: LaTeX to Word, LaTeX Diff, latex-track-changes guide

3. **RMIT University — LaTeX and BibTeX (Digital Tools)**
   - URL: https://rmit.libguides.com/DigitalTools/latex-bibtex
   - Lists: MiKTeX, MacTeX, TeXstudio, Overleaf, TeXPage, Papeeria, BibTeX.eu
   - **Contact: Mike Brooks — mike.brooks@rmit.edu.au**
   - Fit: BibTeX Builder, BibTeX Validator, fix-bibtex-errors guide

4. **Montclair State University — Citation Tools and Tutorials**
   - URL: https://montclair.libguides.com/citing/tools
   - Lists: BibMe, Citation Machine, EasyBib, Zotero, Mendeley
   - **Contact: Clair Bair — bairdc@mail.montclair.edu**
   - Fit: Citation Generator, citation-styles-explained guide

5. **Tennessee State University — Citation Styles and Tools**
   - URL: https://tnstate.libguides.com/citationtools
   - Lists: ZoteroBib, BibMe, EasyBib, CiteFast, Citation Machine
   - **Contact: Xuemei (Sherry) Ge — xge@tnstate.edu**
   - Fit: Citation Generator, BibTeX Builder

6. **California State University Fresno — Citation Managers**
   - URL: https://guides.library.fresnostate.edu/citationhelp/citationmanagers
   - Lists: Zotero, ZoteroBib, EasyBib, Scribbr, MyBib
   - **Contact: D. Drexler — ddrexler@csufresno.edu**
   - Fit: Citation Generator, citation-styles-explained guide

7. **Yale University Library — BibTeX / natbib / biblatex**
   - URL: https://guides.library.yale.edu/bibtex/bibliography-documentation
   - Lists: natbib, biblatex+biber, Texmaker, LyX
   - Contact: no named librarian on page
   - Fit: BibTeX Validator, fix-bibtex-errors guide, doi-to-bibtex guide

8. **University of Massachusetts Amherst — LaTeX / Reference Databases**
   - URL: https://guides.library.umass.edu/LaTeX/refdatabase
   - Lists: **doi2bib** (direct competitor/peer), Zotero, BibTeX Entry Types
   - Contact: not shown on this sub-page; UMass Libraries has named subject librarians on the parent guide
   - Fit: Citation Generator (doi mode), doi-to-bibtex guide, BibTeX Builder — **highest fit**: page already lists a doi-to-bib tool

Bonus (verified but not contact-mapped):
- Penn Libraries — Citation Management/BibTeX: https://guides.library.upenn.edu/citationmgmt/bibtex (general: ask@upenn.libanswers.com)
- Northwestern (Math/Stats/Data Sci) — LaTeX, BibTeX, and Citation Managers: https://libguides.northwestern.edu/math/latexbibtexcitationmanagers
- Michigan State — Managing Citations in LaTeX: https://libguides.lib.msu.edu/latex/citations
- Kent State — LaTeX (Library Research Management): https://libguides.library.kent.edu/c.php?g=277970&p=1855418
- NPS Dudley Knox — BibTeX Code: https://libguides.nps.edu/citation/bibtex
- Bristol — LaTeX and Overleaf (Computer Science): https://bristol.libguides.com/computer-science/latex
