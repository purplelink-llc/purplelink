# Escaping text isn't escaping attributes

A GitHub code-scanning alert on my free BibTeX validator caught a cross-site scripting risk I had missed. The page was building an HTML attribute out of text a visitor's file supplied, using an escaping function written for a different job. The function was safe for text inside the page. It was not safe for text inside an attribute.

The validator checks a .bib file for required fields, duplicate keys, and dead DOIs. It also checks whether CrossRef or Semantic Scholar recognize the title a citation points to, a way to catch references a language model invented. The check runs entirely in the browser and touches no account or stored data. I had treated that as low risk, which is probably why the result rendering got less scrutiny than the parts of the site that take a payment.

Results get built with string concatenation: a table row per citation, a class for whether it passed, a status written into a data attribute the page's own script reads back for filtering. I had an escapeHtml function for visible text, the citation key, the title, the message a DOI lookup returned, and it did exactly what I had asked. It turned `<` and `>` into entities so nothing could open a tag inside the row. It did not touch quotation marks, because inside a block of visible text a quote is just a character. Inside an attribute, a quote is the thing holding the attribute open. A value containing one could close the attribute early and start a new one, and the pattern GitHub's scanner looks for had a path in.

I had written the function to match the first place I used it, then reused it everywhere the page built HTML. Same function, different job, depending on where the string landed. That was the part I had missed: escaping isn't one property a string has or doesn't. It depends on where the string ends up. Text in a tag, text in an attribute, and text in a URL each need their own transform. A function correct for the first isn't automatically correct for the rest.

The fix wasn't a better escaping function. It was building the error box and the table rows with the DOM API, createElement, textContent, setAttribute, instead of assembling an HTML string by hand. The browser already applies the right rule for whatever context it's given. Handing it a value through the correct call means I never have to remember which characters matter where. I went through the validator's other output paths and made the same change anywhere a server response or an uploaded file reached the page, not only the line the scanner flagged. None of this is about the syntax mistakes that usually land in a .bib file; for those, the guide to fixing common BibTeX errors is a better read than this post.

Nothing this bug touched holds data worth much to an attacker. The validator has no login and keeps no files. But a scanner reads the code, not the stakes, and neither did I when I wrote it. The fix took an afternoon. Noticing I needed it took GitHub's code scanning running on a Monday, not another pass through my own diff. I've written before about where BibTeX errors actually come from, which is a different list of mistakes entirely, mine included.

Further reading: if you want the reference for BibTeX and bibliography management in LaTeX beyond what any validator checks, The LaTeX Companion is the one I reach for when a bibliography style won't do what I want. More books like it are on the research desk.

Disclosure: the Amazon link above is an affiliate link. As an Amazon Associate I earn from qualifying purchases.

If you want to run a .bib file through the same checks before you submit, the BibTeX validator is free and the file is never stored.

## Screenshots to capture

- The old attribute-breakout line in the diff (data-status built with raw concatenation) beside the GitHub code-scanning alert that flagged it.
- The BibTeX validator results table, to show the data attribute and class the fix now builds safely.

## LinkedIn Post

An escaping function I wrote for visible text on a page turned out to be unsafe for the same text inside an HTML attribute. Angle brackets were handled. Quotation marks were not, because inside a block of text a quote is just a character, and inside an attribute it is the thing holding the attribute open.

GitHub's code scanning caught it in my free BibTeX validator before anyone else did. The fix was not a smarter escaping function. It was replacing string-built HTML with the browser's own DOM API, which applies the right rule for whatever context it is given, so I never have to remember which characters matter where.

Nothing the bug touched holds data worth much to anyone. But a scanner reads the code, not the stakes, and so should I. I wrote up what actually happened:

https://purplelink.llc/blog/escaping-text-isnt-escaping-attributes/
