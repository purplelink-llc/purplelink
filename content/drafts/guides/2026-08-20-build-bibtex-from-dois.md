# How to Build a BibTeX File from DOIs and arXiv IDs

Researchers collecting references for a LaTeX paper use BibTeX Builder to convert a list of DOIs and arXiv IDs into a ready-to-use .bib file in under a minute.

Manual BibTeX entry means copying author names, fixing capitalization, and tracking down DOIs one reference at a time. BibTeX Builder skips that: paste your identifiers, download the file.

## Steps

1. Collect your DOIs and arXiv IDs as you read through your references. DOIs appear in paper headers, Google Scholar result rows, and on journal sites as doi.org URLs or "doi:" prefixed strings. arXiv IDs appear in the URL of any arXiv abstract page: arxiv.org/abs/2301.12345 gives you the ID 2301.12345. Keep them in a text file, one per line.

   [SCREENSHOT: a plain text list of DOIs and arXiv IDs, one per line]

2. Go to purplelink.llc/tools/bib-builder/ and paste your list into the input field. The tool accepts DOIs starting with "10.", doi.org URLs, arXiv IDs, and arxiv.org/abs/ URLs. Up to 50 entries per request.

   [SCREENSHOT: input field with a mixed list of DOIs and arXiv IDs pasted in]

3. Click "Build .bib file". Each entry is fetched live: DOIs from CrossRef, arXiv IDs from the arXiv API. The output shows formatted BibTeX entries and a separate list of any IDs that failed to resolve.

   [SCREENSHOT: output area showing generated BibTeX entries and a short failed-lookups list below]

4. Check the failed-lookups list. A failed entry usually means a typo in the ID or a DOI that is not yet registered in CrossRef. Open each one in your browser to verify, then add the entry by hand or correct and re-run it.

5. Click "Download .bib" to save the file. Open it in a text editor and spot-check a few entries: author name formatting, title capitalization, and year. CrossRef data is generally accurate but occasionally has inconsistent title casing or missing page numbers on newer articles.

   [SCREENSHOT: downloaded .bib file open in a text editor showing several entries]

6. Move the .bib file into your LaTeX project directory. Reference it in your preamble with `\bibliography{yourfile}` if you are using BibTeX, or `\addbibresource{yourfile.bib}` if you are using biblatex. Compile as normal.

7. Before submitting, run the .bib file through the BibTeX Validator (purplelink.llc/tools/bib-validator/) to catch malformed entries, duplicate citation keys, and missing required fields.

## What's happening under the hood

For DOIs, the tool sends a GET request to CrossRef's content-negotiation endpoint with the BibTeX Accept header. CrossRef returns a formatted entry directly, typed as @article, @inproceedings, @book, or whichever type is registered.

For arXiv IDs, the tool queries the arXiv Atom API, parses the response, and formats an @misc entry with `eprint`, `archivePrefix`, and `primaryClass` fields. That format is what most LaTeX journals and style files expect for preprints.

Citation keys are generated from the first author's surname and the publication year. You can rename them in the .bib file; just update your `\cite{}` commands to match. Nothing is uploaded to Purplelink's servers after the response is sent.

## Q&A

### A DOI I know exists is showing up in the failed list.
Paste the DOI directly into your browser with the doi.org prefix (e.g. doi.org/10.1234/example) to confirm it resolves. If CrossRef redirects to the paper, the DOI is valid and the issue may be a trailing space or punctuation character in your list.

### Can I use this with Overleaf?
Yes. Download the .bib file and upload it to your Overleaf project using the file upload button in the left panel, then reference it with `\addbibresource{filename.bib}` in your preamble.

### My author names are formatted as "Last, First" but my style file wants "First Last".
BibTeX style files handle that transformation automatically during compilation. Leave the author names in the "Last, First" format that CrossRef returns; your bibliography style (.bst or biblatex style) will format them correctly in the output.

Build your .bib file at purplelink.llc/tools/bib-builder/.

---

## LinkedIn Post

Most BibTeX files start the same way: copying reference data by hand from Google Scholar, then fixing broken author names and missing DOIs one entry at a time.

BibTeX Builder is a different approach. Paste a list of DOIs and arXiv IDs, one per line, and it fetches the formatted .bib entries directly from CrossRef and the arXiv API. Download the file, drop it into your LaTeX project, and compile. Entries that fail to resolve are listed separately so you know exactly which IDs to check.

I wrote up the full workflow, including how to spot-check entries after download and how to validate the file with the BibTeX Validator before submitting. If you write papers in LaTeX and have been building your reference list manually, this is probably worth 2 minutes of your time.

https://purplelink.llc/guides/build-bibtex-from-dois/
