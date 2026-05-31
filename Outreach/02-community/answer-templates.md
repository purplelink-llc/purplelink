# TeX SE + Reddit answer templates

When the target-discovery agent surfaces a specific thread, customize the relevant template below. The key rule: **answer the question fully first, then mention the tool as the convenience option.** Drive-by tool drops get downvoted on TeX SE and silently dropped on Reddit.

---

## Template T1: TeX SE — "I keep getting BibTeX errors"

> The most common BibTeX failures cluster into about eight categories: missing required fields per entry type, unbalanced braces (the worst kind, because one missing brace cascades into every entry after it), duplicate citation keys, unescaped special characters in titles (`&`, `%`, `_`, `#` need a leading backslash), missing commas between fields, and stray Unicode pasted from a PDF or publisher's website. Then there are the newer ones: AI-hallucinated DOIs and fabricated titles, which look plausible but don't resolve to real papers.
>
> The bisection strategy when nothing else works:
>
> 1. Comment out every entry in your `.bib` and confirm the document compiles with an empty bibliography.
> 2. Uncomment half. Compile.
> 3. Whichever half broke is where the bug is. Halve again.
> 4. Five or six iterations isolates the bad entry in a 500-line file.
>
> If you'd rather not bisect manually, I maintain a free in-browser validator that catches all eight categories in a single pass — including the AI-hallucination check via CrossRef and Semantic Scholar title comparison. It also produces an annotated `.bib` with one comment per entry summarizing its state, which is convenient for a final pre-submission sanity check: https://purplelink.llc/tools/bib-validator/
>
> Longer write-up of the recurring errors with code examples: https://purplelink.llc/guides/fix-bibtex-errors/

---

## Template T2: TeX SE — "How do I get BibTeX from a DOI / arXiv ID?"

> A DOI dereferences cleanly through CrossRef's content-negotiation API:
>
> ```
> curl -L -H "Accept: application/x-bibtex" \
>      https://api.crossref.org/works/10.1145/3292500.3330701/transform/application/x-bibtex
> ```
>
> Returns a well-formed BibTeX entry. arXiv IDs go through `export.arxiv.org/api/query?id_list=2103.00020`, which returns Atom XML you have to format yourself.
>
> Three post-import gotchas to watch for:
>
> 1. **Title capitalization** — BibTeX styles automatically lowercase title words. Wrap proper nouns, acronyms, and language names in extra braces: `title = {{BERT}: Pre-training of...}`.
> 2. **Diacritics** — CrossRef returns UTF-8. Classic 8-bit BibTeX needs `{\"u}`, `{\'e}`, etc. — or switch to Biber, which handles UTF-8 natively.
> 3. **Entry type** — CrossRef sometimes returns `@misc` for workshop papers that should be `@inproceedings`. Adjust to match your bibliography style.
>
> If you want a tool that handles the curl + formatting for you: https://purplelink.llc/tools/bib-builder/ (paste a DOI or arXiv ID, get back a BibTeX entry). It also handles batch input — paste a list of identifiers, one per line.
>
> More on the preprint-vs-published-version pattern: https://purplelink.llc/guides/doi-to-bibtex/

---

## Template T3: TeX SE — "How do I convert LaTeX to Word?"

> Pandoc is the standard answer. The command:
>
> ```
> pandoc main.tex -o manuscript.docx --citeproc --bibliography=refs.bib --csl=apa.csl
> ```
>
> The `--citeproc` flag converts `\cite{}` calls to formatted in-text citations using a CSL stylesheet; `apa.csl` is downloadable from the Zotero style repository. Without `--citeproc` your citations end up as `[?]`.
>
> Common conversion losses:
>
> - Equations end up as Word equations on macOS Pandoc, OMML elsewhere. Editable but slightly different layout.
> - Custom LaTeX commands (`\newcommand`) need a Lua filter or manual replacement.
> - Figures need their files in the working directory.
>
> If you don't want to install Pandoc locally, I built a free web tool that wraps the same Pandoc invocation with a journal-friendly manuscript template (double-spaced, 12pt, standard margins): https://purplelink.llc/tools/latex-to-word/ — also has an optional anonymize step for blind review.
>
> Full guide with the journal-style breakdown: https://purplelink.llc/guides/latex-to-word/

---

## Template T4: TeX SE — "How do I track changes between two LaTeX versions?"

> `latexdiff` is the standard tool. Install it via your TeX distribution (it ships with MacTeX and TeX Live). Run:
>
> ```
> latexdiff old.tex new.tex > diff.tex
> pdflatex diff.tex
> ```
>
> The result is a PDF with deletions struck through and additions colored. Works at the LaTeX-source level, so it understands the document structure (not just text diff).
>
> Multi-file projects: `latexdiff --flatten` first to inline includes.
>
> If you'd rather not install anything, my web wrapper does the same: https://purplelink.llc/tools/latex-diff/ — upload two `.tex` files (or two `.zip` projects), get a tracked-changes PDF.
>
> Guide with options for journal-revision workflows: https://purplelink.llc/guides/latex-track-changes/

---

## Template R1: r/LaTeX — sharing a guide (not a tool drop)

> **[Guide] Eight recurring BibTeX errors, with bisect-debugging for the ones you can't find**
>
> I wrote up the failure modes I see most often (missing fields per entry type, unbalanced braces, etc.) with before-and-after code samples and a debugging strategy when the error message points at a line that's nowhere near the actual mistake.
>
> Free, no signup. Pairs with an in-browser validator that catches the same categories plus AI-hallucinated citations.
>
> Guide: https://purplelink.llc/guides/fix-bibtex-errors/
>
> Happy to answer questions in the thread.

---

## Template R2: r/AskAcademia / r/PhD — when relevant question appears

Only post if someone explicitly asks "how do I..." about citation management, LaTeX-to-Word for submission, or BibTeX errors. Skip otherwise. Format:

> I've been writing up some of this stuff for my own studio's site — for [the specific thing they asked], the short answer is [direct answer in 2–3 sentences].
>
> [If they need more depth] I wrote a longer piece on this here: [specific guide URL]. It pairs with a free tool that handles [whichever automation] in the browser if you want to skip the command line.
>
> Happy to dig into the specifics if it'd help.

---

## What NOT to post

- "Hi everyone, I just launched my tool, check it out!" — flagged on every academic subreddit.
- Drive-by tool-only answers on TeX SE — gets downvoted and possibly tagged spam.
- LLM-generated answers with no specific technical content — TeX SE moderators are sharp about this.
- Replying with the same template across 10 threads — visible pattern, gets flagged.

Each post should look like a person who happened to have a tool, not a tool that's trying to get clicks.
