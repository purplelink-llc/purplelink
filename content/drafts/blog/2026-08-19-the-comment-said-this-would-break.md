# The comment said this would break

The comment in the code said "fine at early-stage volume." I read it when I wrote it and thought: yes, that will need to be replaced eventually. Then I shipped it.

On August 14, the Purplelink dashboard started falling back to archived figures for purplelink.llc. The stats endpoint was returning 502. The function had timed out.

The stats endpoint powers the traffic dashboard: it reads event blobs from object storage, aggregates them across a 30-day window, and returns totals per page. Each blob is one JSON record, one page view. The original implementation awaited each read in sequence: fetch the day's event listing, then for each event on that day, await the individual blob read. Serial. One at a time.

Fine when there are 50 events. At 670 events over 30 days, total wall-clock time hit 21 seconds. The function timeout is 10 seconds. The comment was correct.

What I got wrong wasn't the prediction. I expected volume to be the trigger. At some point there would be enough page views that sequential reads couldn't keep up, and I'd be forced to fix it before the dashboard fell over. What actually happened was that the reads got slower individually, not just collectively. Network latency jitter, small variations in blob read time, nothing dramatic on any single request. Just 670 of them, each slightly slower than expected, stacking up to 21 seconds.

The fix is bounded concurrency: 10 day listings in flight at a time, 64 event reads. Not an unconstrained `Promise.all`, because the number of events in a month is unbounded in principle and dispatching them all at once trades a slow response for a flaky one. Bounded concurrency, preserved order, counting logic untouched.

The dashboard also stopped surrendering on the first bad response. A single 502 had been enough to drop a whole site's live stats for the day, falling back to figures from the previous run. It now retries three times with backoff for transient failures only. A 401 means the token is wrong; retrying it just confirms the same thing more slowly.

The actual long-term fix is pre-aggregated counters: compute the totals incrementally as events arrive, so the 30-day read never happens. The parallel version still hits the same ceiling if volume grows, but it buys time to build that deliberately rather than on a Friday morning with a broken dashboard.

The lesson I keep relearning: writing "this will break" is not the same as scheduling when to fix it. The comment was a note to myself that I treated as sufficient. It was not.

## LinkedIn Post

For about three months, the Purplelink stats endpoint read event blobs one at a time. The code even had a comment: "fine at early-stage volume."

At 670 events over 30 days, total wall-clock time hit 21 seconds. The function timeout is 10 seconds. The dashboard started returning 502s and fell back to stale figures.

The failure arrived through latency rather than the traffic spike I expected. Nothing dramatic on any single blob read. Just 670 of them, each slightly slower than expected, stacking up.

The fix is bounded concurrency: 10 day listings in flight, 64 event reads, preserved order. Pre-aggregated counters are the real long-term answer. The parallel version buys time to build that deliberately.

The lesson: "this will break" written in a comment is not the same as scheduling when to fix it.

https://purplelink.llc/blog/the-comment-said-this-would-break/
