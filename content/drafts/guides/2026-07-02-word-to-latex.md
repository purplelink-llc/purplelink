# How to Convert a Word Manuscript to LaTeX

Researchers submitting to a LaTeX-only journal use Purplelink's free Word to LaTeX converter to get a compilable .tex starting point from a .docx file.

## Steps

1. Accept all tracked changes and delete comments before converting. In Word, open the Review tab, click **Accept > Accept All Changes**, then delete all comments. The converter sees only the final, accepted document.

   [SCREENSHOT: Word Review ribbon with Accept All Changes menu open]

2. Go to purplelink.llc/tools/word-to-latex/. Drag your .docx file onto the upload area, or click to select it. Maximum file size is 5 MB.

   [SCREENSHOT: upload dropzone with a .docx file selected]

3. Click **Convert to LaTeX**. The conversion runs server-side and returns a .tex file within a few seconds.

   [SCREENSHOT: Convert to LaTeX button active after file selection]

4. Download the .tex file and open it in your LaTeX editor. Standard content transfers cleanly: headings, paragraph text, bold, italic, lists, basic tables, and footnotes. Check these areas manually before submitting:

   - Cross-references (Figure 1, Table 2, etc.) become plain text. Rebuild them using `\ref{}` and `\label{}`.
   - Multi-column layouts and text boxes become ordinary paragraphs.
   - Equations are converted from Word's native format and need review; verify each one.
   - Tables with merged cells rarely convert correctly and usually need to be rebuilt.

   [SCREENSHOT: downloaded .tex file open in a LaTeX editor]

5. Compile and fix. Run pdfLaTeX (or your project's engine) and work through any build errors. Most are minor: table column specs, equation syntax, or a missing package.

   [SCREENSHOT: LaTeX editor showing the compiled PDF alongside the source]

## What's happening under the hood

The tool runs `pandoc --standalone` on your file. Pandoc maps Word structure to LaTeX equivalents: headings become `\section{}`, bold becomes `\textbf{}`, numbered lists become `enumerate` environments, and footnotes become `\footnote{}`. The `--standalone` flag produces a complete preamble with common packages, so the file compiles without additional setup. Word elements without a LaTeX equivalent, including field codes, embedded objects, and custom styles, are dropped or converted to plain text.

## Q&A

### Is my file stored?

No. The file is processed in a temporary container and discarded the moment the output is returned. Nothing is written to durable storage or logged.

### My equation looks wrong in the output. What should I do?

Pandoc converts from Word's internal equation format to LaTeX math. Complex equations often need manual rewriting; check each one against your original document.

### The table layout is wrong. How do I fix it?

Pandoc assigns default column specifiers. Open the `tabular` block and set the column specs (`l`, `c`, `r`, or `p{width}`) to match your original layout.

Convert your manuscript at purplelink.llc/tools/word-to-latex/.

## LinkedIn Post

Most Word-to-LaTeX conversions produce a workable first draft but leave the same things to fix: cross-references become plain text, merged table cells break, and equations need a manual pass.

Purplelink's free Word to LaTeX converter runs Pandoc server-side and returns a complete, compilable .tex file in a few seconds. Headings, lists, footnotes, bold, and italic transfer cleanly. The things that need attention afterward are predictable, and I wrote a short guide covering all of them: what to do before you upload, what transfers automatically, and how to fix the three areas that usually don't.

Useful if you've written a manuscript in Word and need to move it into LaTeX for a journal submission.

https://purplelink.llc/guides/word-to-latex/
