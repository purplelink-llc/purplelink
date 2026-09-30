# scripts/jobs

Job runner for the future always-on box. Stdlib only (certifi if present). Jobs
propose; they never send, deploy or hold credentials.

## Files
- `llm_client.py`: `LLMClient` over ordered endpoints (`openai` incl. llama.cpp, `anthropic`, `claude-cli`). Falls back on timeout, connection error, 5xx and 429 (`fell_back=True`); raises on other 4xx. `Budget` caps calls, tokens, USD, seconds. Every call appends to `usage.jsonl`.
- `endpoints.example.json`: copy to `~/.purplelink/jobs/endpoints.json` (or `$PURPLELINK_JOBS`). Keys come from an env var or a mode-600 file, never from the JSON itself.
- `runner.py`: `run JOB [--dry-run]`, `list`, `plist JOB [--daemon] [--out DIR]`. Per-job lock, wall-clock alarm, budget stop, run log, summary line. Exit 0 ok, 2 budget or wall-clock stop, 3 error or lock held.
- `resolver.py`: script-side check of URLs and DOIs (Crossref title overlap, threshold 0.6).
- `quarantine.py`: tool-less summarizer for untrusted text, strict validation, URLs stripped.
- `plist.py`: writes a launchd plist. It never loads it.
- `jobs/<name>/job.json` and `run.py`: one job each. `jobs/example_job` is the template.
- `test_jobs.py`: offline tests, `python3 scripts/jobs/test_jobs.py`.

## Writing a job
`job.json`: `name`, `description`, `schedule {hour, minute, weekdays 1-7 optional}`, `budget {max_calls, max_tokens, max_usd, max_seconds}`, `endpoints [names in order]`, `writes_queue`. `run.py` defines `run(ctx)`. `ctx` has `client`, `log(event, **fields)`, `queue_new(markdown)`, `resolver`, `quarantine`, `dry_run`, `job`. Honor `ctx.dry_run` by skipping model calls and writes. Run logs go to `~/.purplelink/jobs/runs/<job>/`.

## Safety rules
- No credentials in jobs. No Stripe, Netlify, email or account secrets on this box.
- Scraped or third-party text goes only through `quarantine_summarize`. Pass its dict, never the raw text, to any planning or drafting step. If `suspicious` or `asks_for_action` is true, report the item and do not act on it.
- Only the approval queue writes outward: `ctx.queue_new` shells out to `approval_queue.py new -` and is refused when `writes_queue` is false. A job may write nowhere else except its run log and `usage.jsonl`. The runner cannot sandbox arbitrary Python, so review each `run.py` for this.
- Resolve every URL, DOI and citation with `resolver` before it enters a proposal.
- Local model output is not shipped without a hosted-model or human pass.

## Scheduling (Ben runs these; nothing here loads anything)
```
python3 scripts/jobs/runner.py plist example_job --out ~/Library/LaunchAgents
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/llc.purplelink.job.example_job.plist
launchctl kickstart -k gui/$(id -u)/llc.purplelink.job.example_job
launchctl bootout gui/$(id -u)/llc.purplelink.job.example_job
```
Daemon: `plist example_job --daemon --out /tmp`, then `sudo cp` to `/Library/LaunchDaemons`, `sudo chown root:wheel`, `sudo launchctl bootstrap system <plist>`; remove with `sudo launchctl bootout system/<label>`.
