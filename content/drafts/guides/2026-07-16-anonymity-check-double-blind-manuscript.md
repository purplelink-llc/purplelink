# How to Check a Manuscript for Double-Blind Leaks

Researchers preparing a double-blind submission use Purplelink's Anonymity Check to catch identifying information that manual blinding missed.

## Steps

1. Compile your manuscript to PDF. If you're working in LaTeX, use the free [LaTeX to PDF tool](https://purplelink.llc/tools/latex-to-pdf/) if you don't have a local install. In Word, use File > Export > PDF.

   [SCREENSHOT: PDF file ready for upload]

2. Go to [purplelink.llc/tools/anonymity-check/](https://purplelink.llc/tools/anonymity-check/) and click **Start scan — $2.**

   [SCREENSHOT: Anonymity Check page with the Start scan button]

3. Complete the Stripe checkout. You're redirected to an upload page.

4. Upload your PDF. The scan takes under a minute for a typical manuscript.

   [SCREENSHOT: upload area with a PDF selected]

5. Read the findings. Each entry shows the exact text that identified you, the category (author name, institution, grant number, IRB protocol, self-citation, or named software artifact), and its location in the manuscript.

   [SCREENSHOT: scan results showing findings by category]

6. Open your source document and fix each finding.
   - Author names: replace with "Anonymous Author(s)" or remove the phrase.
   - Institution names: replace with "the authors' institution" or remove.
   - Grant numbers and IRB protocols: delete the identifying numbers. Some venues require removing the acknowledgements section entirely.
   - Self-citation patterns: replace "In our previous work [N]" with "In prior work [N]" and confirm the cited entry's title doesn't reveal authorship.
   - Named software or author-owned URLs: anonymize or omit if they identify you.

   [SCREENSHOT: source document with a grant number highlighted for removal]

7. Re-export to PDF and upload again to confirm no leaks remain.

   [SCREENSHOT: scan results showing zero findings]

## What's happening under the hood

The scan sends your manuscript to Anthropic's Claude API, which reads the full text and flags each category of identifying information. Purplelink deletes the result from its servers the moment you retrieve it. Anthropic retains the manuscript for up to 30 days for abuse monitoring, not for training. The tool covers the body and abstract; supplementary materials, figures, and PDF metadata require a separate manual pass.

## Q&A

### Does this replace a manual read-through before submission?

No. Treat it as a final pass to catch what you missed. It doesn't scan figures, supplementary files, or PDF metadata.

### What about PDF metadata? Does the tool catch author names there?

PDF metadata fields (Author, Creator, Producer) are outside the scan. In Word, clear them via File > Info > Properties > Remove Personal Information. In LaTeX, add `\hypersetup{pdfauthor={}, pdftitle={}}` to the preamble before compiling.

### The scan flagged a citation to my own published paper. Do I need to remove it?

Not necessarily. A reference list entry alone rarely breaks blind review. The surrounding prose does — for example, "As we showed in [N]..." Fix the prose and confirm the entry's title doesn't reveal authorship.

Run a scan at [purplelink.llc/tools/anonymity-check/](https://purplelink.llc/tools/anonymity-check/).

## LinkedIn Post

Double-blind submissions have a specific failure mode: you remove your name from the title page, then leave grant numbers, IRB protocol IDs, or "as we showed in [N]..." in the body. A reviewer doesn't need your name to identify you if they can search your NSF award number.

I wrote a short guide on using Purplelink's Anonymity Check before submitting to a double-blind venue. It's a $2 scan that looks for seven categories of identifying information (author names, institutions, funders, protocol numbers, self-citation patterns, named software, and author-owned URLs) and quotes the exact text so you know what to fix.

The guide covers the full workflow: compile to PDF, run the scan, fix each finding in source, re-scan to confirm. It also covers what the tool doesn't catch: figures, supplementary files, and PDF metadata each need a separate manual pass.

https://purplelink.llc/guides/anonymity-check-double-blind-manuscript/
