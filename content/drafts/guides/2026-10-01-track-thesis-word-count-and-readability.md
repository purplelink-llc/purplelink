# How to Track Thesis Word Count and Readability While You Write

Purplelink's free Word Counter tracks word count, readability and writing-style flags across a thesis draft, chapter by chapter, with a CSV export to compare one revision against the next.

Most PhD students reach for a word counter once, near submission. Used earlier, it gives a running record: chapter length, reading-level trend, and whether passive voice creeps back under deadline pressure. For a one-off count against a journal limit, see how to check a manuscript against a journal word limit instead.

## Steps

1. Go to purplelink.llc/tools/word-counter/ and paste the chapter you're drafting, or switch to Upload a file and drop a Word, PDF, LaTeX, Markdown, RTF, ODT or EPUB file (up to 20 MB).

2. Check the live counts above Analyse. Words, characters, sentences, paragraphs and reading time update as you type or as soon as the file loads.

   [SCREENSHOT: Word Counter live counts panel with a pasted chapter]

3. Click Analyse. The full report adds readability scores (Flesch-Kincaid, Gunning Fog, SMOG, ARI), vocabulary diversity, and style flags for passive voice, hedging and clichés.

   [SCREENSHOT: Full Analyse report showing readability scores and style flags]

4. If the chapter uses recognizable headings, Introduction, Methods, Results, Discussion, Conclusion, the section panel breaks the count down with checkboxes. Everything else groups under Main text.

   [SCREENSHOT: Section panel with checkboxes for Introduction, Methods, Results, Discussion, Conclusion]

5. Click Download CSV and save it as, for example, ch3-methods-2026-10-01.csv, your baseline for the next revision.

6. After editing the chapter, repeat the upload and Analyse, download a new CSV, and compare word count and readability against the last export.

7. Treat the style flags as a prompt to look, not an edit order. Some passive voice belongs in a methods section.

## What's happening under the hood

Pasted text never leaves your browser. An uploaded file is converted to plain text in a server container that's deleted immediately, then every statistic, readability included, runs locally.

Section detection matches headers against common academic section names, reading LaTeX section commands directly. The readability formulas were derived in 1975 for the U.S. Navy to grade technical manuals, not dissertations, which is why academic prose scores several grades above plain-language advice. (Source: Kincaid et al., "Derivation of New Readability Formulas," 1975, https://stars.library.ucf.edu/istlibrary/56/)

## Q&A

### Does the Word Counter split a thesis by chapter the way it splits a journal manuscript by section?
Only when headings match what it recognizes: Introduction, Methods, Results, Discussion and Conclusion. A Literature Review or Background chapter has no dedicated bucket, so it's counted inside Main text.

### What readability grade should a thesis chapter aim for?
The tool sets no target: these formulas were calibrated on Navy training manuals, not dissertations, so a technical chapter commonly reads several grades higher than plain-language advice. Compare your own drafts over time, not an outside benchmark.

### Can I track word count and readability across an entire thesis, not just one chapter?
Run each chapter separately and save the CSV exports in one folder named by chapter and date. The tool doesn't merge files into one report, so a spreadsheet of your own CSVs is the practical way to see the whole document's trend.

For a LaTeX thesis, see counting words in a LaTeX document (/guides/latex-word-count/). For the abstract alone, the free Abstract Checker (/tools/abstract-checker/) checks your count against 25 journals' limits.

Further reading: Paul Silvia's *How to Write a Lot* makes a short case for scheduling writing like a class you teach. Steven Pinker's *The Sense of Style* explains why expert writing gets dense, useful once a score flags a passage worth revisiting. More on the research desk (/desk/).

Disclosure: the Amazon links in the published guide are affiliate links. As an Amazon Associate I earn from qualifying purchases.

Word Counter is free to use at purplelink.llc/tools/word-counter/, with no account and nothing saved after you leave the page.

## Screenshots to capture

- Word Counter live counts panel with a pasted thesis chapter (words, characters, sentences, paragraphs, reading time).
- Full Analyse report showing readability scores (Flesch-Kincaid, Gunning Fog, SMOG, ARI) and the style-flags card.
- Section panel with checkboxes for Introduction, Methods, Results, Discussion, Conclusion and Main text.

## LinkedIn Post

If you only run a word counter once, right before submission, you're missing the more useful version of the habit: use it every week while you draft the thesis.

I added a workflow to Purplelink's free Word Counter that treats it as a running record instead of a one-time check. Paste or upload a chapter, click Analyse, and you get readability scores, style flags for passive voice and hedging, and a count broken down by section when your headings match Introduction, Methods, Results, Discussion, Conclusion. Download a CSV after each revision and you can watch whether your editing is actually moving the numbers, not just guessing.

One thing worth knowing: the readability formulas (Flesch-Kincaid, Gunning Fog, SMOG) were built in 1975 to grade Navy training manuals, not dissertations. A chapter of dense methodology will score several grades above plain-language advice, which is normal. Use the score to compare your own drafts, not to chase an outside number.

Guide: https://purplelink.llc/guides/track-thesis-word-count-and-readability/
