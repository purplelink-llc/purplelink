# Both bugs had the same symptom: zero

The GlobePin traffic dashboard pulls data from several sources: my server logs, App Store Connect sales figures, and Apple's analytics reports for discovery and engagement. I built the analytics pull in late July. Apple takes a few weeks to generate reports for a new property, so when I checked and saw nothing, I assumed the data wasn't there yet.

The data started arriving in early September. My dashboard still showed nothing.

The diagnostic problem with a missing-data bug is that missing data looks like missing data. I could see real reports in the App Store Connect web UI. But I couldn't easily tell whether my pipeline was failing to fetch them, failing to parse them, or succeeding but aggregating incorrectly. I started with authentication.

Apple's analytics API returns pre-signed S3 URLs for the actual report segments. You authenticate with Apple first, get a URL, then download the file directly from S3. My function sent the Apple bearer token on every request, including those S3 fetches. S3 rejects that with a 400 error: "only one auth mechanism allowed." The error was caught by an `if response.status != 200: continue` guard I'd written for legitimately absent reports. So every segment fetch failed, got treated as absent, and the code moved on. No exception. No log entry. Just nothing.

The second bug would have produced the same result even without the first. Apple's report segments are tab-separated, the same format as the sales reports handled correctly elsewhere in the same file. But for the analytics pull I called `csv.DictReader` without `delimiter="\t"`. The entire header line would have parsed as one field, no column names would have matched, and every row would have returned zero values.

Two independent bugs, each enough to produce empty output on its own. I fixed both at the same time, so I can't confirm which was the live failure path. The auth bug probably came first, since S3 was rejecting the fetches before any parsing happened, but I can't be certain. When I reprocessed after patching, the archive came back with five impressions and one product page view from early September. Small numbers, but they were the real thing.

What I got wrong was treating six weeks of silence as confirmation. "No data" and "broken fetch" looked identical from where I sat: both showed up as empty rows in the dashboard. The guard that handled missing files handled broken requests with exactly the same behavior, and I never logged which case I was in.

One extra line, logging the response body on any non-200, would have shown me "only one auth mechanism allowed" on the first real run. The file existed. S3 just rejected my credentials because I was presenting two auth mechanisms at once. That's a fixable error, visible immediately, rather than a mystery I had to wait for real data to even see.

## LinkedIn Post

For six weeks, a code path returned zero and I assumed that was correct. Apple's App Store analytics take a few weeks to generate reports for a new property, so "no data" matched what I expected. Then real reports arrived in September and the dashboard still showed nothing.

There were two bugs, each independently enough to return empty output. One sent auth credentials to pre-signed S3 URLs that already carried their own auth -- S3 rejected that silently, swallowed by an error guard meant for legitimately absent files. The other parsed tab-separated files without specifying the tab delimiter. Both bugs had the same symptom, so neither was visible until data existed to make the silence suspicious.

One logging line would have caught the first bug immediately. I wrote the code to handle absent files gracefully and got a guard that also hid broken requests without distinction.

https://purplelink.llc/blog/both-bugs-had-the-same-symptom-zero/
