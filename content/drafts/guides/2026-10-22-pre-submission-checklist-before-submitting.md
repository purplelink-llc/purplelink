# How to Run a Pre-Submission Checklist Before You Submit a Paper

By Benjamin Ampel · October 22, 2026

A pre-submission checklist for a journal paper compiles cleanly, validates citations and word limits, checks methods and figures, anonymizes for double-blind review, and prepares the final files, in that order. Purplelink's free submission checklist lists all twelve checks with a tool for each.

## The checklist

Work through these in order on the [submission checklist](https://purplelink.llc/tools/submission-checklist/); progress saves only in that browser tab.

1. **Compile from a clean build.** Fix every error and overfull box first; line numbers and the page count depend on it.
2. **Validate the bibliography.** Run [BibTeX Validator](https://purplelink.llc/tools/bib-validator/) for syntax errors, missing fields, duplicate keys and a CrossRef check for a [hallucinated citation](https://purplelink.llc/guides/catch-ai-hallucinated-citations/).
3. **Check the word and page limit.** Run [Word Counter](https://purplelink.llc/tools/word-counter/) and Abstract Checker, counted as the venue counts them.
4. **Match the venue's template and reference style.** Pull the right template and convert references with Reference Converter.
5. **Check the figures by eye.** Readable axes, no truncated scales, a colour-blind-safe palette, embedded fonts. See [what reviewers flag in figures](https://purplelink.llc/guides/methodology-problems-peer-reviewers-flag/).
6. **Check methods against claims.** Run Paper Review for claims the data cannot carry or an unjustified sample size.
7. **Scan for missing related work.** Run Citation Gap Analysis for prior work a reviewer will expect cited.
8. **Anonymize for double-blind review.** Run Anonymity Check for names, institutions, funding and IRB numbers, per [COPE's blinding guidance](https://publicationethics.org/).
9. **Write the cover letter.** Run Cover Letter for a one-page statement of contribution and fit, from the abstract and journal name.
10. **Prepare and record the submission.** Gather the final PDF, source files, supplementary material and data statement; log the venue, date and ID in [Vitae](https://purplelink.llc/vitae/).

## What's happening under the hood

The checklist page is static: ticking a box writes to your browser's local storage, and nothing leaves that page on its own. BibTeX Validator checks text against CrossRef without storing the file. Paper Review, Citation Gap Analysis, Anonymity Check and Cover Letter send the manuscript to an AI model, to judge a claim, not match a pattern; Paper Review's copy goes to Anthropic's API, deleted within about a day.

## Questions

**Do I need to pay to use this checklist?**
No. Compiling, validating the bibliography, counting words and converting references are free; Paper Review ($9 to $15), Citation Gap Analysis ($3) and Cover Letter ($2) are not.

**What order should I run these checks in?**
Compile first, since every later line number and page count depends on it. After that, the order avoids rework, like catching a missing reference before counting words.

**Does the checklist store my manuscript?**
No. It stores only your checkbox state in this browser, with no account. Each linked tool handles text on its own terms, stated on that tool's page.

Next: [the camera-ready checklist](https://purplelink.llc/guides/camera-ready-checklist/) if accepted, or [how to respond to Reviewer 2](https://purplelink.llc/guides/how-to-respond-to-reviewer-2/) if it needs revision.

## Further reading

Two books from the [research desk](https://purplelink.llc/desk/) fit here. [Writing Your Journal Article in Twelve Weeks](https://www.amazon.com/dp/022649991X?tag=purplelinkpl-20) walks a draft to a submitted article, one week at a time. [The Visual Display of Quantitative Information](https://www.amazon.com/dp/0961392142?tag=purplelinkpl-20) is behind most of what the figure check above looks for.

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

Run the full checklist once, in order, at the [submission checklist](https://purplelink.llc/tools/submission-checklist/).

## LinkedIn Post

Compile first, then validate your bibliography, then check word limits. In that order. Catching a missing reference before you count words means you do not recount after adding a citation, and a clean build is what every later line number and page count depends on.

I wrote up the twelve checks I would run on a manuscript before submitting it, in the order that avoids redoing earlier work: bibliography, word limit, template, figures, methods against claims, missing related work, double-blind anonymization, cover letter, and the final file prep. Each check links to the tool that runs it, free or paid, so you are not hunting for the right page mid-deadline.

Most of the rework I see in manuscripts close to a deadline comes from running these checks out of order, not from skipping them.

https://purplelink.llc/guides/pre-submission-checklist-before-submitting/
