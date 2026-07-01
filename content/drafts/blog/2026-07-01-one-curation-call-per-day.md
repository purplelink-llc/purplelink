# One curation call per day

The Daily Digest pulls from about 35 sources each morning and collects somewhere between 400 and 800 raw items. Every day I need to pick 20 of them to publish. The question I had to answer early was how to structure the AI call that does that selection.

The obvious approach is per-item scoring: send each item to a model and ask whether it belongs in the digest, given a description of the reader. Aggregate the scores, pick the top 20. Simple to reason about, easy to test in isolation.

The problem is that relevance isn't absolute. A paper on LLM red-teaming might be a clear pick if it's the only one this week, and a clear skip if three similar papers landed in the same batch. An AI lab announcement matters more when no other lab said the same thing yesterday. Per-item scoring can't see any of that. Each call is blind to the rest of the batch.

Per-item also has an economics problem: somewhere between 400 and 800 API calls per run, every single morning. That's both slow and expensive for what is, in the end, a morning briefing.

The design I landed on is a two-step process. A pre-filter first: sort each source category by recency and cap it at 18 candidates. This collapses 700-plus raw items to roughly 100. Then one Claude call sees all 100 candidates and picks and annotates the final 20 in a single pass.

That pre-filter step had a non-obvious constraint. Early tests sent all raw items (sometimes 700-plus) in a single call without any cap. The context limit wasn't the bottleneck. Attention degradation was. Picks from the bottom of a 700-item JSON array weren't as sharp as picks from a 100-item one.

Capping at 18 per category is a heuristic, not a derived number. The underlying principle: reduce the candidate pool to something the model can reason across coherently before asking it to rank. That constraint made a visible difference in output quality.

The single-call approach does something per-item scoring can't: catch relationships between items. The curation prompt asks the model to flag connections between selected items: same threat actor, same technology, same underlying event. That cross-item annotation only works when everything is in context at once.

One call per day. The whole run takes about 90 seconds from cron fire to published post.

## LinkedIn Post

Scoring 800 news items one at a time to find 20 worth reading sounds like the obvious approach. The problem is that relevance isn't absolute. A paper on LLM red-teaming is a clear pick if it's the only one this week, and a clear skip if three similar papers landed in the same batch. Per-item scoring can't see any of that — each call is blind to the rest of the batch.

The Purplelink Daily Digest uses a different design: a pre-filter that collapses 700-plus raw candidates to roughly 100, then a single AI call that sees the full set and picks and annotates the final 20 at once. It turns out this matters not just for economics (one API call vs. 800) but for quality — cross-item comparisons produce sharper selections, and the model can flag when two picks connect to the same underlying story.

There was also a non-obvious constraint: sending all 700-plus items in one call without pre-filtering degraded quality. The context window wasn't full. Attention was just spread too thin.

https://purplelink.llc/blog/one-curation-call-per-day/
