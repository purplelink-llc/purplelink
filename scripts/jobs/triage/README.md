# Triage evaluation

Measures whether a model's weekly-scan triage matches the reference. Phase-2 gate in
`docs/growth-briefs/local-agent-box-design.md`: recall on gold positives at least equal to
the hosted baseline, and JSON validity at least 95 percent.

Private data lives in `~/.purplelink/jobs/triage/` (override `PURPLELINK_TRIAGE_DIR`):
`dataset.jsonl`, `labels.jsonl`, `label_counts.json`, `results/`. Nothing private enters the repo.

## Files
- `build_dataset.py` dataset, reference labels, merge rule, shared helpers.
- `eval_triage.py` runs an endpoint over the dataset, scores it, `compare` applies the gate.
- `triage_prompt.md` system prompt (no tools, items are untrusted data, JSON out).
- `test_triage.py` offline tests, fake client only.

## Use
```
python3 build_dataset.py build                    # ~130 items; --offline skips HN and feeds
python3 build_dataset.py label --endpoint judge --kind claude-cli --model opus
python3 eval_triage.py run sonnet --kind claude-cli --model sonnet
python3 eval_triage.py run gpu-local              # a name from ~/.purplelink/jobs/endpoints.json
python3 eval_triage.py compare results/sonnet-*.json results/gpu-local-*.json
python3 test_triage.py
```
`fake`/`fake-obey` are offline endpoints; real calls use `scripts/jobs/llm_client.py`. A run is about 14 calls.

## Dataset
Brief, appendix and Reddit-notes items from 2026-09-29, Hacker News (Algolia, 14 days, 14
queries), and public feeds (Zotero releases, Stripe blog, Apple developer news, Chrome blog,
Overleaf releases; 30 days). No Reddit scraping, no logged-in access. Deduplicated by URL and
near-identical title. Item text is stored as fetched (untrusted) and reaches a model only as
JSON-encoded data.

## Labels
Rows in `labels.jsonl`, later rows win, merged field by field:
1. `judge`: hosted reference judge, batches of 10.
2. `brief`: items the 2026-09-29 brief surfaced, forced relevant (the gold set).
3. `brief-negative`: appendix Rejected items (forced irrelevant) and Reddit-notes items the
   scan did not surface (judge value kept; weak, not proof of irrelevance).
4. `ben`: append `{"id": "...", "relevant": false, "label_source": "ben"}` to override anything.
   A Ben override of a gold item removes it from the gold set.

## Metrics
Precision/recall/F1 for relevant; gold recall (did it surface what the scan did); top-10
overlap (rank by relevant, then urgency, ties by id); action_type accuracy on reference-relevant
items; JSON validity per batch (fences and surrounding prose repaired, anything else invalid;
strict rate shown too); latency per batch; tokens; cost. Five synthetic injection canaries are
added at run time and excluded from the metrics; `obeyed` means the model acted on the injected
instruction, `flagged` means it noticed. Missing predictions count as irrelevant.

Gold rows (what the private weekly brief surfaced) are not in the repo: they live in ~/.purplelink/jobs/triage/gold.json and are loaded at run time.
