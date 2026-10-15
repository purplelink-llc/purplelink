# How to Remove PDF Metadata Before Double-Blind Review

A PDF or Word file carries your name in its properties even after you remove it from the text. Metadata Cleaner strips the author, producer, and comment-author fields in your browser, then re-reads the file to confirm nothing identifying is left before it lets you download it.

Use this before uploading a manuscript to a double-blind venue, whether you compiled it from LaTeX or exported it from Word.

## Steps

1. Export the exact file you will upload. Compile LaTeX with your usual toolchain or the free LaTeX to PDF tool, or in Word use File > Export as PDF.
2. Go to purplelink.llc/tools/metadata-cleaner/ and drop the file into "Clean files." Add any Word, Excel, or PowerPoint supplement in the same batch.
3. Check the options first. Leave "Rename reviewers and commenters to Author" on to keep tracked changes but strip who made them, and leave the title and author fields blank unless your venue wants a placeholder.
4. Download the cleaned file, or the .zip if you cleaned more than one. The tool only offers a download once it has re-read the result and confirmed nothing from the original fields is left.
5. Open the cleaned PDF and check its properties. Author, Creator, and Producer should be empty.
6. Download the report before closing the tab. It lists a SHA-256 checksum of the file before and after, so you can show later what was removed.
7. Run Anonymity Check on the same manuscript. Metadata Cleaner only touches the file's properties; the guide to checking a manuscript for double-blind leaks covers what to look for in the text itself, since a name in your acknowledgements or a self-citation in the body is still there until a text scan catches it.

## What's happening under the hood

Metadata Cleaner runs in a background worker inside your browser tab, and its network meter shows zero bytes leaving the machine. For a PDF, it cuts the document-properties dictionary, the XMP packet, the file ID, and any private application data out of the file structure. For Word, Excel, or PowerPoint, it unzips the file, edits the XML parts holding author and company names, then zips it back up. Comment and tracked-change authors are replaced with a placeholder rather than deleted, so the edit history survives without names attached. Before offering the result, the tool reloads it with the reader that found the original fields, and withholds the download if that second read still finds something.

## Q&A

**Does this replace Anonymity Check?**
No. Metadata Cleaner edits the file's properties. Anonymity Check reads the manuscript text for names, institutions, and self-citations. A double-blind submission needs both.

**Will cleaning the file remove my tracked changes?**
No. The tool edits the properties and XML parts around your content, not the content itself. Tracked changes and comments stay in the file with their names replaced.

**What if my PDF is password-protected?**
Metadata Cleaner refuses it, since the file cannot be rewritten without the password. Remove the password in your PDF reader first, then clean the result.

Further reading: cleaning the file is the easy part. Wendy Laura Belcher's [Writing Your Journal Article in Twelve Weeks](https://www.amazon.com/dp/022649991X?tag=purplelinkpl-20) walks through choosing a journal and preparing a submission one week at a time, useful once the file-prep step above is done. More books for academic writers are on the research desk.

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

Clean your manuscript file at Metadata Cleaner before you upload it anywhere.

## Screenshots to capture

- Metadata Cleaner's "Clean files" tab with a sample PDF dropped in, showing the detected author/producer fields before cleaning.
- The Options panel expanded, showing the "Rename reviewers and commenters to Author" checkbox and the author/title fields.
- The result list after cleaning, showing the green "Nothing left to read" status and the Download report button.
- A PDF reader's Properties/Info dialog before and after, side by side, showing the Author field going from a name to empty.

## LinkedIn Post

A PDF still has your name in it after you've scrubbed it from the text. Author, Creator, and Producer fields sit in the file's properties, and most people never check them before a double-blind submission.

I added a step-by-step guide for cleaning those fields with Metadata Cleaner, a free tool that runs entirely in the browser (nothing uploaded). It strips the document properties, the XMP packet, and the names on tracked changes and comments, then re-reads the file to confirm the fields are actually gone before it lets you download anything. There's also a SHA-256 report so you have a record of what was removed, which some journals and IRBs ask for.

Metadata is only half the problem. A self-citation or a name in your acknowledgements is still identifying text, which is a separate check. The guide covers both, in order, so you're not guessing which tool handles which part of a blind submission.

If you've ever had a desk editor flag a "blinded" PDF that still listed your name in File > Properties, this is the five-minute fix.

https://purplelink.llc/guides/remove-pdf-metadata-before-double-blind-review/
