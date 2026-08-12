# Producing a diff PDF for journal resubmission

When a journal sends Major Revisions, most researchers focus on two documents: the revised manuscript and the response letter. Many submission portals require a third: a diff PDF showing exactly what changed between the original and the revision.

The standard tool for this is `latexdiff`, a Perl script that compares two .tex files and produces an annotated version with additions underlined and deletions struck through. It works well when it runs. But getting it running requires Perl installed on your machine, a local LaTeX distribution to compile the output, and some comfort with the command line. Researchers on university-managed machines, or on Windows, often hit a wall before they get a usable PDF.

The Purplelink LaTeX Diff tool wraps `latexdiff` in a browser interface. The workflow takes about three clicks.

Go to purplelink.llc/tools/latex-diff/. Upload two files: the old version and the new version. Each can be a single .tex file or a .zip archive containing the full project: figures, .bib file, custom style files. If your manuscript uses `\input{}` or `\include{}` to pull in separate chapter files, or if the bibliography lives in a .bib file the compiler needs to see, use the .zip. The tool flattens the project structure before running the diff, so the result reflects what your compiler would see.

A few seconds later, the tool returns a compiled PDF. Additions appear underlined; deletions appear struck through. The diff operates at the word level, so if you rewrote a phrase but kept the surrounding sentence, the struck-through words and their replacements sit side by side in the rendered output.

One thing to know: table contents are not diffed. This is deliberate. `latexdiff` by default marks changes inside tabular environments with inline annotation markup, which corrupts column alignment and produces uncompilable LaTeX. The tool treats each table as an opaque block instead. If you revised a table's data, only the new version appears in the diff PDF.

The resulting PDF goes wherever the submission portal asks, usually as a separate upload alongside the revised manuscript, sometimes embedded in the response letter. Either way, the journal gets a clear record of what changed without the reviewer needing to compare two documents manually. Instead of a response letter that says "we expanded the limitations section," there is a diff that shows exactly which sentences were added.

## LinkedIn Post

Most journal submission portals that accept revisions also ask for a diff PDF -- a compiled document that shows exactly what changed between the original manuscript and the revised one. This is rarely mentioned in the decision letter, but it shows up as a required upload when you get to the portal.

The tool that produces this is latexdiff, a Perl script that generates an annotated .tex file with additions underlined and deletions struck through. Getting it to run locally requires Perl, a LaTeX distribution, and some patience. On a university-managed machine or Windows, that often means hours lost before you have a usable PDF.

I built a browser-based version that takes two files -- old and new, either .tex or .zip -- and returns a compiled diff PDF in a few seconds. Nothing is stored. If your project has multiple files, figures, or a separate .bib, just upload the .zip and it handles the rest.

https://purplelink.llc/blog/producing-a-diff-pdf-for-journal-resubmission/
