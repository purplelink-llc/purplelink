# Where BibTeX errors actually come from

When I built the [BibTeX validator](/tools/bib-validator/), I expected it to catch the kind of mistakes researchers make directly: a misspelled author name, a missing journal field, a stray character in a citekey. The mental model was proofreading. Someone writes their bibliography, the validator flags their typos, they fix it.

That's not what happens.

Most of the errors the validator flags come from software exports, not from researchers. Mendeley, Zotero, Google Scholar, Scopus, even publisher download pages: each one produces BibTeX that's subtly wrong in its own way. Google Scholar omits the `month` field and sometimes drops page numbers entirely. Mendeley serializes the `author` field correctly but writes DOIs into the `url` field, which breaks certain bibliography styles. Zotero handles most entry types well but produces nonstandard output for conference papers. Some export tools write month as a number; others use the three-letter abbreviation LaTeX expects; others use the full word, which requires extra package support to parse.

None of these are researcher errors. The researcher opened their bibliography manager, exported to BibTeX, and dropped it into their project. The software they trusted to get this right didn't.

That reframing changed how I built it. A compatibility layer between incompatible software is a different job than a proofreader, and it needs different checks.

It also meant rethinking what "valid" means. A BibTeX file that compiles without errors in one journal's template will sometimes fail in another. Some styles require `number` fields that others ignore. Some demand a `publisher` entry for book chapters; others don't care. The BibTeX spec is loose enough that valid-by-spec isn't the same as valid-in-practice, and in-practice depends on which packages you're using.

The validator now checks against what commonly-used packages actually expect, not just what the original 1985 spec requires. It also surfaces a category of warnings that aren't errors: fields that will compile fine today but may cause problems if the researcher switches to a different bibliography style later. Whether to act on a warning is the researcher's call.

The thing I didn't see coming: the warnings are what researchers find most useful. The errors they already knew about. The subtle compatibility issues they didn't.

I started this with a proofreading metaphor. The more accurate one is translation. The validator is reading what four different pieces of software produced and telling you what will and won't survive the trip to the journal template.

---

## LinkedIn Post

Most BibTeX errors don't come from researchers. They come from the tools researchers use to manage citations.

When I built the BibTeX validator for Purplelink's tools page, my assumption was that researchers needed help catching their own mistakes. After watching it actually get used, that assumption fell apart. The errors showing up were from Mendeley, Zotero, Google Scholar, and publisher export pages, each producing subtly incompatible output. Month fields as numbers when LaTeX expects abbreviations. DOIs in URL fields that break bibliography styles. Nonstandard conference paper formats.

The researcher did everything right. Their software didn't.

That realization changed how I built the tool. The validator now checks what commonly-used LaTeX packages actually expect, not just what the 1985 spec says. It also flags compatibility warnings: fields that will compile fine now but break when you switch to a different journal template. Those warnings turned out to be more useful than the hard errors.

https://purplelink.llc/blog/where-bibtex-errors-actually-come-from/
