# How to Use Paper Review Before Submitting a Manuscript

Researchers preparing to submit use Paper Review to find the problems a real reviewer will flag: figure integrity, citation support, and methodological blind spots.

## Steps

1. Compile your manuscript to PDF. Paper Review accepts PDF files up to 20 MB. If you're working in LaTeX, use the free [LaTeX to PDF tool](https://purplelink.llc/tools/latex-to-pdf/) if you don't have a local install. In Word, use File > Export > PDF.

[SCREENSHOT: file upload area showing a PDF selected]

2. Go to [purplelink.llc/tools/paper-review/](https://purplelink.llc/tools/paper-review/) and choose a tier. Standard ($3) runs the full four-layer review. Journal Pack ($5) adds a compliance check against your target journal. Deep Review ($8) runs two adversarial passes so each persona sharpens against the others' first-round findings.

[SCREENSHOT: tier picker with Standard selected]

3. Click the checkout button and pay through Stripe. You're redirected to a status page that polls automatically until the review is ready.

[SCREENSHOT: status page showing a progress indicator]

4. When the report appears, read Critical Blind Spots first. These are the findings multiple personas flagged independently, and they carry the most weight. Each finding quotes your manuscript and names the personas that raised it.

[SCREENSHOT: Critical Blind Spots section from a sample report]

5. Work through the Rectification Checklist in A/B/C order. A-priority items need to be addressed before submission. B items strengthen the paper. C items are minor presentation fixes.

[SCREENSHOT: rectification checklist with A/B/C labels]

6. Check the Citation Support Audit. References marked "Contradicted" need verification against the full source text. "Not supported by abstract" means the claim may appear in the paper body but wasn't confirmed at the abstract level. "Source unavailable" means the DOI or title didn't resolve: fix those references before submitting.

[SCREENSHOT: citation audit table with verdict column]

7. Download or copy the Markdown report before closing the tab. The review is deleted from Purplelink's servers the moment it renders. It is not recoverable once the tab is closed.

[SCREENSHOT: Download button at the top of the report]

## What's happening under the hood

The review runs four layers in sequence. Layer 1 renders every page as an image and examines figures for integrity issues: broken axes, missing error bars, discrepancies between a figure and its caption. Layer 2 checks every reference against CrossRef, then fetches the abstracts of the most load-bearing cited sources and compares them to your claims. Layer 3 runs four AI personas in parallel: Methodology Critic, Statistical Skeptic, Data Integrity Officer, and Editor-in-Chief. A consensus filter surfaces findings raised by more than one persona first. Layer 4 synthesizes the structured report with blind spots, contradictions, the rectification checklist, and a novelty estimate. Your domain profile (Machine Learning, Biomedicine, Psychology, Chemistry, or General) loads the attack vectors relevant to your field.

## Q&A

**Does the review replace peer review?**
No. Use it as a first-pass audit to fix the obvious problems before a real reviewer sees them. Every editorial decision remains yours.

**What if a finding is wrong?**
Each finding quotes the relevant text so you can verify it. If a whole result reads as poor quality, email ben@purplelink.llc for a refund.

**My paper contains patient data. Is it safe to upload?**
Redact any identifiable patient information before uploading. The manuscript is sent to Anthropic's Claude API, which retains inputs for up to 30 days for abuse monitoring.

Run a review at [purplelink.llc/tools/paper-review/](https://purplelink.llc/tools/paper-review/).

## LinkedIn Post

Most manuscript rejections come back with the same categories of feedback: figures that don't hold up under scrutiny, citations that don't support the claims they're attached to, and methodological gaps the author stopped noticing after the fourth revision.

I published a short guide walking through Purplelink's Paper Review tool. Upload your PDF, choose a domain profile, and in about five minutes you get a Markdown report: critical blind spots (ranked by how many AI reviewer personas flagged them independently), a citation audit with per-citation verdicts, and an A/B/C rectification checklist sorted by submission priority.

The guide covers how to read each section of the report and how to act on flagged citations. Useful for any researcher preparing to submit to a peer-reviewed journal. Starts at $3.

https://purplelink.llc/guides/use-paper-review-before-submitting/
