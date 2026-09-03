# How to Check Whether Your Revisions Addressed the Original Findings

Researchers who have revised a manuscript after a Paper Review use the Revision Review tool to verify which original findings were fixed, which remain open, and whether the revision introduced new problems.

---

Researchers with a revised manuscript use Revision Review to confirm that each flagged problem was actually addressed before resubmission.

## Before you start

You need two things: the revised manuscript as a PDF, and the Markdown report from the original Paper Review (the file named `manuscript-review.md` that you downloaded when the first review completed). Revision Review compares the two. If you closed the tab without downloading the Markdown file, run a fresh full Paper Review on the revised manuscript from $9 instead — reports are deleted from Purplelink's servers on retrieval and cannot be recovered.

## Steps

1. Export your revised manuscript to PDF. In LaTeX, compile with your usual toolchain or use the free LaTeX to PDF tool. In Word, use File > Export > PDF.

2. Go to purplelink.llc/tools/paper-review/revision/ and click **Start revision review — $2**. Complete the Stripe checkout. You are redirected to the upload page.

   [SCREENSHOT: Revision Review landing page with the checkout button visible]

3. Drag your revised manuscript PDF onto the upload area, or click to choose the file. Limit: 20 MB.

   [SCREENSHOT: Upload area with a PDF file selected]

4. Open the `manuscript-review.md` file from your original review in any text editor. Select all, copy, and paste it into the text area on the upload page.

   [SCREENSHOT: Upload page with Markdown pasted into the text area]

5. Enter your email address if you want a notification when the report is ready (optional). Click **Submit revision**.

6. When the report appears, read the Address Tracker first. Each item from the original Rectification Checklist carries a verdict: addressed, partially addressed, not addressed, or not evaluable. Addressed items include a direct quote from your revised manuscript showing where the fix appears.

   [SCREENSHOT: Address Tracker section showing three checklist items with verdicts]

7. Review the New Issues section. Revisions sometimes introduce problems that were not in the original manuscript: a new experiment whose statistics were not reported, a trimmed paragraph that removed a necessary caveat. This section lists up to five such issues, each labeled with a severity.

8. Work through the Action Checklist. Everything that still requires a change before resubmission appears there in priority order.

   [SCREENSHOT: Action Checklist from a sample report showing two remaining items]

9. Download the Markdown report before closing the tab. Revision reports are deleted from Purplelink's servers on retrieval.

## What's happening under the hood

The tool reads your revised manuscript and the original Rectification Checklist side by side. For each A/B/C-priority item, it searches the revised text for the corresponding change and assigns a verdict. Addressed items include a direct quote from the revision as evidence. A verdict of "not evaluable" means the tool could not confirm from the text whether the change was applied — this often happens with figure-level fixes or data corrections that appear only in visual elements. The New Issues scan is targeted, not a full re-review: it focuses on changes the revision introduced rather than re-examining the whole paper. Your manuscript and the pasted review are sent to Anthropic's Claude API, which retains inputs for up to 30 days for abuse monitoring.

## Q&A

### What does "partially addressed" mean?
The original finding was acknowledged and some change was made, but the fix is incomplete. The verdict explanation names what is still missing.

### Can I run Revision Review without a previous Paper Review?
No. The tool requires the original Markdown report as a reference. Without it, run a full Paper Review ($9) on the revised manuscript instead.

### Does this replace peer review?
No. Use it to check your own revision before the editor sees it. An experienced reviewer will still notice things it misses.

Run the check at purplelink.llc/tools/paper-review/revision/.

---

## LinkedIn Post

When you finish revising a manuscript, the question is not "did I make changes" but "did I fix the actual problems." Those two things do not always overlap.

Purplelink's Revision Review takes your revised PDF and the Markdown report from the original Paper Review and compares them line by line. Each item from the Rectification Checklist gets a verdict: addressed, partially addressed, not addressed, or not evaluable. Addressed items include a direct quote from your revision as evidence. The tool also flags up to five new problems the revision may have introduced, which is something most researchers do not think to check.

The guide walks through the full upload-to-report workflow, including the prerequisite that trips people up most often: you need to have saved the original review's Markdown file before closing the tab. Reports are deleted on retrieval.

https://purplelink.llc/guides/check-revisions-addressed-findings/
