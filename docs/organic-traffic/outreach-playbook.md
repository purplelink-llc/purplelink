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
