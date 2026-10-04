# The co-author who writes in Word

Most of my coauthored papers involve someone who will never open a .tex file. I write in LaTeX. They write in Word, with track changes and comments in the margin, because that is what their department uses and what their last three papers were written in. The manuscript has to exist in both formats. The harder part is moving the document between them without losing its structure, and getting their edits back into your source without retyping every comment by hand.

Going from LaTeX to Word is the easier direction. Headings, lists, bold and italic, basic tables, and a bibliography built from your .bib file all convert cleanly through Pandoc. That is what runs behind the free LaTeX to Word converter in the Purplelink tools. Equations mostly come across as native Word equations. Anything built from a custom macro is worth a visual check before the file goes out, because Pandoc handles standard LaTeX well and degrades on packages it does not recognize.

The trip back is messier. The Word to LaTeX converter runs the same way, through Pandoc, and handles headings, paragraphs, lists and basic tables cleanly. What it cannot reconstruct is a review. Track changes, margin comments, and a table someone reformatted by hand are things a structural converter was never built to represent. A heavily marked-up .docx comes back as a document you still have to read against the original, one comment at a time. The guide to converting a Word manuscript to LaTeX goes through what survives that trip and what does not.

None of that is a flaw in the tool. Pandoc converts structure, not editorial history, and reconciling a marked-up Word file with your LaTeX source is real work no matter how the file arrives. Once something comes back through a conversion, I run the result against my last saved .tex in the LaTeX Diff tool. It marks every addition and deletion in a PDF, which is a faster way to see what changed than trusting a converter and a co-author's edits landed the way you expect.

Further reading: if the conversions keep breaking on packages you did not expect, The LaTeX Companion, third edition, is the reference for what a given package actually does. That is most of what a converter degrades on in the first place. Lamport's original LaTeX manual is shorter and older, but it explains why structure and appearance are kept apart in the first place. That is the reason a .docx and a .tex file never map onto each other cleanly. There are more books on the research desk.

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

If you write LaTeX on a Mac, ModernTex keeps a synced PDF preview and BibTeX autocomplete in one native app, free for a 7-day trial and $19.99 to keep.

## Screenshots to capture

- The LaTeX to Word converter mid-conversion, showing the style dropdown (Manuscript vs Preprint) and the anonymize checkbox.
- A before/after: a marked-up Word paragraph next to the same passage converted to LaTeX.
- The LaTeX Diff tool's output PDF, with additions and deletions marked, after a round-trip conversion.

---

## LinkedIn Post

The easy direction in a LaTeX and Word workflow is not the one people worry about. Converting a LaTeX manuscript into a clean Word document happens automatically through Pandoc: headings, tables, even the bibliography come across fine. The trip back is where it breaks, because a structural converter has no way to represent a week of track changes and margin comments.

Every coauthored paper I write ends up needing both formats, since at least one collaborator will never open a .tex file. The real work happens after the file converts: reading a marked-up Word file against your original source, and getting a reviewer's comments back into LaTeX without retyping each one by hand.

I wrote up how I handle both directions, and the tool I run afterward to confirm exactly what changed.

https://purplelink.llc/blog/the-co-author-who-writes-in-word/
