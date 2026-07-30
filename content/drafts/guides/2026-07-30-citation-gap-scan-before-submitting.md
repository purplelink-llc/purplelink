# How to Run a Citation Gap Scan Before Submitting

Researchers preparing to submit use Citation Gap Analysis to find the prior-art omissions a reviewer would flag.

## Steps

1. Export your manuscript to PDF. Citation Gap reads the full text and your existing bibliography together. In LaTeX, build the PDF with your usual toolchain or use the free [LaTeX to PDF](https://purplelink.llc/tools/latex-to-pdf/) tool. In Word, use File > Export > PDF.

   [SCREENSHOT: file picker showing a PDF selected]

2. Go to [purplelink.llc/tools/citation-gap/](https://purplelink.llc/tools/citation-gap/) and click **Start scan** ($3). Complete the Stripe checkout. You're redirected to a status page that polls until the result is ready.

   [SCREENSHOT: Citation Gap tool page with the Start scan button visible]

3. Read the scan result. Each suggestion includes the section of your manuscript where the citation belongs (Methods, Related Work, Discussion), a reason a reviewer would expect it cited, and a candidate paper with author and title when the tool can identify one.

   [SCREENSHOT: sample result showing three suggestions with section labels]

4. Verify each candidate in Google Scholar or your institution's database. The tool flags candidates, not confirmed gaps: suggested titles and authors can be imprecise. Read the abstract before citing anything.

5. Add relevant papers to your bibliography. For each verified paper that supports or contextualizes your claims, add the entry and integrate a citation in the relevant section. Citing papers that aren't genuinely relevant is visible to experienced reviewers.

6. Download the scan result before closing the tab. The report is deleted from Purplelink's servers the moment it renders.

   [SCREENSHOT: download button at the top of the scan result]

## What's happening under the hood

The tool reads your full manuscript and flags three categories of potential omissions: foundational references in your method or framework that experts assume will be cited, near-identical prior findings your paper should differentiate against, and dataset or technique references you build on without attribution. It compares what your manuscript claims against what your bibliography contains, then flags the gaps. Each suggestion includes the section where the reference belongs and a reason a reviewer would notice the absence, giving you enough context to judge relevance quickly. Your manuscript is sent to Anthropic's Claude API, which retains inputs for up to 30 days for abuse monitoring.

## Q&A

### How is this different from checking my existing citations?

The free [BibTeX Validator](https://purplelink.llc/tools/bib-validator/) checks the citations you already have for accuracy and existence. Citation Gap runs in the opposite direction: it looks for papers you should include but haven't cited.

### What if a suggestion is wrong?

Verify every candidate before adding it. If a whole scan reads as low-quality, email ben@purplelink.llc for a refund.

### Should I run this before or after Paper Review?

Either order works. Running Citation Gap first, adding relevant citations, then running [Paper Review](https://purplelink.llc/tools/paper-review/) on the updated draft is a common sequence.

Run the scan at [purplelink.llc/tools/citation-gap/](https://purplelink.llc/tools/citation-gap/).

## LinkedIn Post

The most consistent post-rejection note I see on academic manuscripts is a variant of "the authors have not engaged with relevant prior work." More often than not, the authors did engage with it; they just missed a canonical paper the reviewer expected.

Citation Gap Analysis, a $3 scan I built at Purplelink, takes a submitted PDF and flags the prior-art omissions a reviewer would likely notice: foundational method references, near-identical prior findings, missing dataset attributions. Each suggestion comes with a reason so you can judge relevance quickly, not just a list of titles to evaluate cold.

It is not a substitute for doing your own literature review. It is a last check before submission, the same way you would reread your bibliography for broken DOIs the night before you hit submit.

https://purplelink.llc/guides/citation-gap-scan-before-submitting/
