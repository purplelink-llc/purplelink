# Getting a research paper into an LLM without losing the math

Copying text from an academic PDF works fine for prose. Hit a table and you get misaligned columns. Hit an equation and you get a string of meaningless characters. If you're trying to feed a paper into an LLM or build a retrieval pipeline, that's a problem.

I built the PDF to Structured Data tool for exactly this. Here's how a session goes.

Say you're doing a lit review and you want an LLM to summarize a paper's methodology, or compare its findings to something else you've read. You download the paper. The abstract looks fine, but Table 2 has six columns of mixed numerical and textual data, and Section 3.2 is built around three equations.

You open purplelink.llc/tools/pdf-structure/. Drag the paper in. About ten seconds later you have two outputs.

The Markdown version has the body text in reading order, not column order, which is what most extractors produce on a two-column layout. Table 2 is a real Markdown table. The equations come through as LaTeX strings. Figure captions are preserved. Nothing is stored; the file is processed in memory and discarded.

The JSON output has the same content split into labeled blocks, useful if you're scripting across multiple papers or building a vector store for retrieval. Most of the time, the Markdown is enough. You paste it into the LLM prompt, or drop it into your note-taking app alongside your annotations.

A few edge cases worth knowing: papers that were scanned rather than generated from source files have variable OCR quality. Papers with complex multi-panel figures include the captions but not the image data, by design. Born-digital PDFs from arXiv or a journal site are usually clean.

The part that surprised me when I started testing this: once the paper is in clean text, everything you want to do with it becomes simpler. Quoting an equation accurately in a note. Asking an LLM to explain a specific derivation. Searching for a particular claim across ten papers at once. None of that requires anything sophisticated. Just content that wasn't garbled on the way out of the PDF.

## LinkedIn Post

Most PDF text extractors handle prose fine. They break on tables and equations. For an academic paper, that's often the most important content.

I built a free tool that converts a PDF into reading-order Markdown and RAG-ready JSON, with tables preserved as Markdown tables and equations as LaTeX strings. The file is processed in memory and never stored. No account needed.

I've been testing it against papers from arXiv and journal sites. Born-digital PDFs come through cleanly. Once the paper is in clean text, things that felt annoying before get straightforward: quoting a specific equation, asking an LLM to explain a derivation, searching for a claim across ten papers at once.

https://purplelink.llc/blog/pdf-to-llm-without-losing-the-math/
