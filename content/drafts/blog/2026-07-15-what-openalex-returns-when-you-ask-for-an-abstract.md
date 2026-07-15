# What OpenAlex returns when you ask for an abstract

OpenAlex's API returns paper abstracts as an inverted index. Not a string. A dictionary where keys are words and values are arrays of integer positions: `{"adversarial": [5], "attacks": [6], "large": [8, 15], "language": [9, 16], "models": [10, 17]}`. To read the abstract, you sort the word-position pairs and join with spaces.

I found this when I built the Daily Digest's paper fetcher. The plan was simple: hit the OpenAlex works endpoint, grab the abstracts, pass them to the curation model as context. When I first decoded the response and saw `abstract_inverted_index`, I assumed it was supplementary metadata. Then I looked for the actual abstract field. There isn't one.

The reason is architectural. OpenAlex is built as a search engine for academic literature, covering roughly 250 million works across all disciplines with no paywall. Search engines store text as inverted indexes internally: for each word, a list of documents and positions where it appears. OpenAlex built their backend this way, and the API exposes the internal representation directly. From a search-system perspective this is sensible. From a reader's perspective it is backward. If you are building a tool that searches papers, you would never need the raw abstract text. If you are building one that reads them, this is the first thing you hit.

The reconstruction is mechanical. Sort by position, join with spaces, done. The one thing it loses is punctuation. Commas and periods within a sentence are part of the word stream in the original abstract. The inverted index has no way to preserve them at word boundaries, so they drop. "We achieve 94.2% accuracy, improving over the baseline by 12 points." becomes "We achieve 94.2% accuracy improving over the baseline by 12 points". Close, but not exact.

For the curation pipeline's purposes, this is fine. The model reads the abstract to decide if a paper belongs in the digest. It's looking for signals about what the paper actually claims, not parsing for grammatical precision. An abstract missing a few internal commas carries enough signal that selection quality doesn't change.

What I didn't expect: some abstracts reconstruct cleanly and some don't. When a paper's abstract was written by multiple authors in separate segments, or when the original uses special characters, the reconstruction can produce awkward word order. Not broken. Just slightly off in ways that are hard to predict without reading each output. The ones that come back cleanest are short abstracts with simple vocabulary. The ones that come back worst are the highly technical ones, which are also the ones the curation model most needs to read carefully.

The `_reconstruct_abstract` function in the harvester is eight lines and works for the pipeline. But every time I look at it, I'm reminded that OpenAlex is a search engine that happens to index paper content, not a repository that happens to support search. The API format says which one it is.

## LinkedIn Post

OpenAlex, one of the best free academic paper APIs available, returns abstracts as inverted indexes. Not strings. A dictionary where keys are words and values are arrays of positions. To read the abstract, you sort by position and join with spaces.

I ran into this while building the Purplelink Daily Digest's paper fetcher. OpenAlex is built as a search engine, so it exposes the internal search data structure directly in the API response. The reconstruction is eight lines of code. It works, but loses commas and sentence-internal periods in the process.

For the curation pipeline this is fine: the model reading abstracts to pick which papers belong in the digest does not need grammatical precision, just enough signal to make the selection. But the data format is a reminder that APIs designed for search and APIs designed for reading have different mental models of what text is for.

https://purplelink.llc/blog/what-openalex-returns-when-you-ask-for-an-abstract/
