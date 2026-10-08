# How to Check Your Thesis Formatting Before You Submit It

Purplelink's free Thesis Format Checker reads a thesis or dissertation PDF in your browser and checks its margins, font size, page numbers, line spacing and front matter against your graduate school's rules, flagging what needs a second look before you submit.

## Steps

1. Pull your graduate school's formatting guide for its minimums, then enter them at purplelink.llc/tools/thesis-format-checker/: a margin preset or custom inches per side, page size, minimum font size and a line spacing requirement.
2. Click **Choose a PDF** or drop your thesis into the box. Files up to 200 MB are accepted; a long document takes a minute or two to read.
3. Read the summary line once the report loads: page count, and how many checks passed, need review, or are informational.
4. Open the page size, margins, page numbers, fonts and line spacing cards. Each names the exact pages that are off, not just a pass or fail.
5. Check the front matter card. It lists which standard headings, title or approval page, copyright, abstract, table of contents and more, it found in the first 40 pages, in order. That confirms a heading exists, not that your university accepts its placement.
6. Click **Download this report as text** and save it with your draft, as a record for the next revision.
7. Fix only the pages a Review flag names, and only if it's actually wrong. Wide tables, landscape figures and chapter openings without numbers are often fine as is.

## What's happening under the hood

The checker reads your PDF with pdf.js, which runs in your browser, so the file is never uploaded, not even to Purplelink's servers. It measures where the text layer sits on each page for margins, reads font metadata for size and embedding, and reads printed page numbers for sequence. Front matter detection matches short lines against common heading patterns in the first 40 pages, skipping anything shaped like a table-of-contents entry. Because it only reads the text layer, a scanned thesis has nothing to measure.

## Q&A

### Will this tell me whether my university will accept my thesis?
No. It measures your document against the numbers you enter, so pull those numbers from your own graduate school's formatting guide first. Rules differ between universities and change over time.

### What does a Review status mean?
There's no Fail status. Review means a page measured outside what you entered, which is often fine, a wide table or a chapter opening without a number, so look at the page yourself before changing anything.

If you're still drafting, the free Word Counter can track word count and readability chapter by chapter, catching problems earlier than a formatting pass can. A LaTeX thesis already gets its margins and fonts from your editor's document class; see the Mac LaTeX editors compared if you haven't picked one.

Further reading: Booth, Colomb, Williams, Bizup and FitzGerald's *The Craft of Research* won't check your margins, but it's the book most committees assume you absorbed before the defense. Helen Sword's *Stylish Academic Writing* is worth reading once formatting is off your plate, for the sentences underneath it. More books on the research desk (/desk/).

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

Check your own thesis against your program's rules with the free Thesis Format Checker at purplelink.llc/tools/thesis-format-checker/ before you submit.

## Screenshots to capture

- The settings fieldset (margin preset, page size, minimum font size, line spacing dropdown) before a file is chosen.
- The drop zone with a thesis PDF being dragged in.
- The results view: summary line plus a Review card (e.g. margins or page numbers) showing the specific flagged pages.
- The front matter card listing detected headings in order.

## LinkedIn Post

Most thesis formatting problems get caught by a human reader three days before the deadline: a margin that's 0.1 inch short on 40 pages, a page-numbering gap after a landscape table, a missing front-matter heading nobody double-checked.

I built a free tool that catches these earlier. Drop in your thesis PDF, enter your graduate school's minimums for margins, font size, line spacing and page size, and it checks every page against them, plus whether standard front-matter sections (abstract, table of contents, approval page) show up in the right order. Nothing leaves your browser; it reads the file locally and tells you exactly which pages to look at, not just pass or fail.

It won't tell you if your university will accept the thesis; only your graduate school's own rules do that. What it does is turn a page-by-page manual check into something you can run after every revision, so formatting is done before the week it's due.

Wrote up the full workflow here: https://purplelink.llc/guides/check-thesis-formatting-before-submission/
