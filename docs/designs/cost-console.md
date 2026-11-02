# Cost console: what each Claude session costs

Status: reviewed by three Goldfish reviewers on Sonnet (design, zoom-out, implementation readiness),
2026-11-02; findings resolved in section 11; built. Owner: Ben.

## 1. Problem

Ben runs 30+ linked Claude Code sessions, scheduled tasks and subagents. Nobody can say today which of
them cost the most, whether a session is looping, whether a Fable call slipped through (his rule is no
Fable calls), or how much the idle "heartbeat" traffic between sessions costs. Ruflo has a cost view and
a run replay; we borrow those two ideas without installing Ruflo or adding any hook.

## 2. Goals and non-goals

Goals:

- Per-session cost from data that already exists on disk, read-only.
- Views: sessions (sortable), per day and week, top spenders, the spawn tree, per model, flags, and a
  per-session run replay.
- Refreshed nightly, and on demand with one command.
- Private to Ben.

Non-goals:

- No new logging, hooks, settings changes or plugins.
- No cash accounting. Ben's Claude usage runs on a subscription plan; every dollar figure here is
  **API-equivalent cost** (what the same tokens would cost at public API rates), and the page says so.
- No live streaming; a nightly snapshot is enough.

## 3. Data sources (all read-only)

| Source | What it gives | Notes |
|---|---|---|
| `~/.claude/projects/<project>/<cli-session>.jsonl` | One line per event. `type: "assistant"` lines carry `message.id`, `message.model`, `message.usage`, `timestamp`, `requestId`. `type: "user"` lines carry `turnOrigin` (`human`, `scheduled`, `peer`, `task_notification`, `system`, `sdk`). `custom-title` lines carry the title. | Measured: 16 GB in the last 14 days, 4,035 files. A streaming scan with a substring prefilter reads 1.3 GB in 1.8 s, so a full 14-day rescan takes well under a minute. No cache. |
| `~/.claude/projects/<project>/<cli-session>/subagents/agent-*.jsonl` + `.meta.json` | Subagent turns; meta gives `agentType`, `description`, `model`. | 1,949 files in 14 days. Counted under their parent session and shown as a separate row in the replay. |
| `~/Library/Application Support/Claude/claude-code-sessions/*/*/local_*.json` | App session: `title`, `cliSessionId`, `priorCliSessionIds`, `spawnedFrom.sessionId` (who started whom), `scheduledTaskId`, `createdAt`, `lastActivityAt`, `isArchived`, `model`. | 576 files. Gives titles and the tree. Transcripts with no app record (terminal `claude`, cron SDK runs) fall back to the `custom-title` line, then to the first user prompt's first 60 characters. |
| `~/.claude/metrics/costs.jsonl` (ECC `stop:cost-tracker`) | A cumulative per-session estimate. | Not used for numbers: it prices a whole session at one model and has no per-turn detail. Used only as a cross-check in the tests' sanity report. |

The ECC skills `cost-report`, `cost-tracking` and `token-budget-advisor` all read that ECC metrics log or
estimate budgets in conversation; none parses transcripts per turn, so nothing there is reusable beyond
the cross-check.

### 3.1 Counting rules (the parts that are easy to get wrong)

1. **One API response is split across several lines.** Each content block (thinking, text, each
   tool_use) is its own `assistant` line with the same `message.id`. Count usage once per `message.id`,
   taking the per-field maximum across its lines (identical on all 19,337 multi-line ids measured; the
   maximum guards against partial counts on early lines). 52% of assistant lines are such repeats.
   Lines without a `message.id` are skipped.
2. **Forks, resumes and compaction copy history into a new file.** The same `message.id` then appears in
   two transcripts. Dedupe globally by `message.id`, subagent files in the same pool. Files are processed
   in order of first timestamp, then file creation time (copied lines keep their timestamps, so a fork
   can start at the same instant as its original), then path; the first file owns the id. Measured:
   about 12% of the first 14-day total was copied history.
3. `model: "<synthetic>"` lines are local placeholders with zero usage; skip them.
4. Cache writes come split by TTL in `usage.cache_creation.ephemeral_5m_input_tokens` and
   `ephemeral_1h_input_tokens`; price them separately (1.25x and 2x input). If the split is missing,
   treat all of `cache_creation_input_tokens` as 5-minute.
5. `usage.speed == "fast"` doubles the rates (Opus fast mode).
6. A turn's **origin** is the `turnOrigin` of the nearest preceding `user` line in the same file whose
   origin is set (tool_result lines carry none and leave it unchanged); before any, `unknown`; every turn
   in a subagent file is `subagent`. Claude Code writes `sdk` for everything the desktop app injects, so
   `sdk` is split by the message's first words: `<side-sessions-event>` to `side_session_event`,
   `<cross-session-message` to `peer`, `<ci-monitor-event>` to `ci_event`, "The app was quit" to
   `app_resume`, a side-session brief to `side_session_task`, the summary prompt to `compaction`, "This
   session is being continued" to `after_compaction`, entrypoint `sdk-cli` to `headless`, else
   `app_other`.
7. **Window:** the last N whole US Eastern calendar days ending today (today partial), filtered per turn
   by timestamp; files are scanned when modified since one day before the window starts.
8. **Sessions:** one app session owns its `cliSessionId` and every `priorCliSessionIds` transcript, and
   its subagents. A transcript with no app record is its own session (`cli:<id>`). Title: the app title,
   else the last `custom-title` line, else the agent name, else the first prompt (system reminders
   removed, quoted), else `untitled <id>`.

## 4. Pricing

One editable table, `scripts/cost_console/pricing.json`, with its source and date at the top:

| Model id prefix | Input | Output | Cache read | 5m write | 1h write |
|---|---|---|---|---|---|
| claude-fable-5-1 | 10.00 | 50.00 | 0.25 | 12.50 | 20.00 |
| claude-fable-5 | 10.00 | 50.00 | 1.00 | 12.50 | 20.00 |
| claude-opus-5-5 | 4.00 | 20.00 | 0.20 | 5.00 | 8.00 |
| claude-opus-5, -4-8, -4-7, -4-6 | 5.00 | 25.00 | 0.50 | 6.25 | 10.00 |
| claude-sonnet-5-5, -5 | 2.00 | 10.00 | 0.20 | 2.50 | 4.00 |
| claude-sonnet-4-6 | 3.00 | 15.00 | 0.30 | 3.75 | 6.00 |
| claude-haiku-5-5 | 0.10 | 0.50 | 0.01 | 0.125 | 0.20 |
| claude-haiku-4-5 | 1.00 | 5.00 | 0.10 | 1.25 | 2.00 |

USD per million tokens. Source: the `claude-api` skill's model table (cached 2026-10-06) and its
prompt-caching economics (writes 1.25x / 2x input; reads 0.1x input except Fable 5.1 $0.25, Opus 5.5
$0.20, Sonnet 5.5 $0.20, Fable 5 $1.00). Sonnet 5 cache read is taken as 0.1x = $0.20. Haiku 5.5 is the
under-100K-prompt rate. Unknown models are priced at the most expensive row and flagged, so a gap
over-reports rather than hides cost.

## 5. Architecture

```
transcripts + app session JSON ──► scripts/cost_console/parse.py ──► ~/.purplelink/cost-console/data.json
                                   scripts/cost_console/build_page.py ──► ~/.purplelink/cost-console/index.html
                                   scripts/cost_console/run.sh  (both steps; the one on-demand command)
```

- **parse.py** (stdlib only, Python 3.11+): streams files modified in the window, dedupes, prices, and
  writes one aggregate JSON with a replay for the top 25 sessions by cost plus every flagged session
  (loops and Fable calls are often cheap and would miss a cost-only cut). It also prints a cross-check
  against ECC's cost tracker (section 11).
- **build_page.py** inlines `data.json` into a single static HTML page (no external scripts; sorting,
  tabs and the replay picker are a few hundred lines of vanilla JS). A replay keeps the first 60 and
  last 140 turns, says how many it skipped, and shows up to 4 tool calls per turn cut to 120
  characters. The first real page is 2.9 MB; the build refuses anything over 8 MB.
- Publishing goes through the Artifact tool, which uploads the file from its path; the page never
  passes through a model's context, so its size costs no tokens.
- Output lives outside the repo (`~/.purplelink/cost-console/`), never committed. The repo holds only
  code, the pricing table, tests with synthetic transcripts, and this doc. The repo is public, so no
  real titles, paths or numbers go into it.

### 5.1 Where it lives: a separate private artifact

Two options: a new tab in the dashboard artifact (9ipzFZUBAci9n2Y4hRpWGx) or a small separate private
artifact. **Choice: separate artifact.**

- The dashboard build is owned by the Analytics session, its refresh task forbids running anything not
  named in REFRESH.md and editing `page/`, and its publish is guarded by `check_live.py`. A tab means
  changing that pipeline and its rules for a page that has nothing to do with traffic.
- Session titles and prompts are more sensitive than traffic numbers; a separate artifact keeps them in
  one place with its own sharing (private, never shared).
- A separate page can be replaced or dropped without touching the dashboard.

The dashboard can link to it later if Ben wants one entry point; that is a one-line change for the
Analytics session, not part of this work.

### 5.2 Refresh

- **Nightly:** a new scheduled task `cost-console-refresh` at 04:35 (just after the 04:30 dashboard
  refresh, so they do not compete), on Sonnet at low effort: run `bash scripts/cost_console/run.sh`
  from the jobs worktree, read the artifact, publish `index.html` to its URL, finish with one line. No
  force publishes. The task cost itself shows up in the console.
- **On demand:** `bash scripts/cost_console/run.sh` builds the page; publishing it needs a Claude session
  (the Artifact tool), so "refresh the cost console" in any session runs the same two steps.

## 6. Views

1. **Summary strip:** 14-day API-equivalent total, today, yesterday, 7-day average, share by model.
2. **Sessions table** (sortable on every column): title, project, model mix (share of cost), turns,
   input/output/cache tokens, cost, subagent cost, duration (first to last turn), last active, flags.
3. **Per day and per week:** stacked by model; table under the chart.
4. **Top spenders:** top 10 sessions and top 10 scheduled tasks (grouped by `scheduledTaskId`).
5. **Spawn tree:** parent plus every session it started (`spawnedFrom`), with own cost and subtree
   cost. Roots sorted by subtree cost.
6. **By model:** tokens and cost per model; cost split into input, output, cache read, cache write.
7. **Flags:**
   - *Over daily threshold:* a session that costs more than $50 API-equivalent in one Eastern day
     (editable in `pricing.json`, `thresholds.session_day_usd`).
   - *Runaway loop:* 30 or more consecutive API responses in one transcript, each under 100 output
     tokens, with some 30 of them inside 60 minutes (first to last timestamp). 200 tokens flagged 152
     sessions on real data, mostly headless research runs that are tiny by design; under 100 tokens is
     4% of all turns.
   - *Same call repeated:* the identical set of tool calls (compared on the full input, before
     truncation) in 5 or more consecutive turns; usually a polling wait.
   - *Fable use:* any turn on a `claude-fable-*` model, with the session and the cost. Ben's rule is no
     Fable calls, so every hit is listed.
   - *Woken by others:* more than half of a session's cost in the window (strictly) comes from turns
     whose origin is `peer`, `side_session_event`, `ci_event` or `system`, and that cost is at least $1.
     `task_notification` is left out: it is the session's own background work finishing.
   - *Unknown model:* priced at the top rate.
8. **Run replay:** pick a session; see each turn in order: time, origin, model, tokens, cost, the tool
   calls it made (name plus a truncated input), and failures (`tool_result` with `is_error: true`,
   `stop_reason` of `max_tokens` or `refusal`). A running cost line on top.

## 7. Privacy

- The page holds session titles, the first characters of prompts and tool inputs. It is published only
  as a private artifact, never shared, and nothing it shows is copied into the repo, a commit message,
  a PR or a public page.
- Strings that look like secrets (`sk-`, `gh?_`, `xox?-`, `AKIA`, `-----BEGIN`, `Bearer`,
  `password=`/`token=`/`api_key=` and similar, and any 40+ character run mixing letters and digits) are
  replaced with `[redacted]` first, then the text is cut, so a secret split by the cut cannot slip
  through.
- The output folder is mode 0700 and its files 0600. Publishing uploads the page to claude.ai as a
  private artifact; that is the one place the data leaves the Mac.
- The parser opens transcripts read-only and never writes, moves or deletes anything under
  `~/.claude/projects/` or the app's session folder.

## 8. Testing

`scripts/cost_console/test_parse.py` (pytest, synthetic transcripts in `tmp_path`, 36 tests, run in CI by
`.github/workflows/cost-console-tests.yml`):

- multi-block response counted once; same id across two files counted once;
- 5m/1h cache split priced separately; missing split falls back to 5m; fast mode doubles;
- `<synthetic>` skipped; unknown model priced at the top rate and flagged;
- origin attribution from `turnOrigin`; compaction origin;
- subagent file rolled up into the parent; `spawnedFrom` builds the tree;
- each flag fires on a minimal case and stays quiet on a near miss;
- Eastern day boundary;
- redaction of secret-looking strings.

## 9. Done means

Design doc approved; parser with tests; pricing table; the console live with real 14-day numbers; a
findings note for Ben (five most expensive sessions and why, loops, savings available); a screenshot.

## 10. Open questions

- The $50 session-day threshold flags 22 sessions in the first window; Ben may want it higher.
- Whether Ben wants the dashboard to link to this page.

## 11. Review findings and how they were resolved

| Finding (reviewer) | Resolution |
|---|---|
| Dedupe ownership undefined; streaming conflicts with "first by timestamp" (readiness, blocker) | Files sorted by first timestamp, creation time, path before the scan; one global pool including subagents (3.1 rule 2). A test caught the same-timestamp fork case. |
| Repeated lines may carry partial usage (readiness, design) | Checked on real data: identical on 19,337 ids. Per-field maximum kept as a guard, with a test. |
| Origin rules open: default, tool results, subagents, compaction predicate (readiness) | Defined in 3.1 rule 6. Real data showed `sdk` hides the pings themselves, so it is split by prefix. |
| Page too large for a nightly model to re-emit (design, blocker) | Not the case: the Artifact tool uploads by file path. Replays cut anyway to keep the page near 3 MB. |
| Loops and Fable calls are cheap and miss a top-40 replay cut (design) | Replays are the top 25 plus every flagged session. |
| Redact after truncate can leak; patterns too narrow (design, readiness) | Redact first, wider patterns, folder 0700, files 0600, tests. |
| Window and DST undefined (readiness, design) | Eastern calendar days via `zoneinfo`, per-turn filter (3.1 rule 7), tests on the boundary. |
| Longest-prefix pricing, fast mode, stale prices (readiness, design) | Longest prefix with tests; fast doubles every rate; a banner when prices are over 45 days old. |
| No stale-page warning when the Mac sleeps through the run (design) | The page shows a banner when it is more than 36 hours old. |
| Cross-check buried in tests (zoom-out) | Printed by every run and shown on the Models tab. Result: 1.20 against ECC transcript by transcript, which ECC's own pricing of one-hour cache writes at the five-minute rate explains. |
| Drop the replay and half the views; publish locally instead of an artifact; drop the screenshot (zoom-out) | Kept: the brief asks for each of these. The page loads views on first open, so the extra tabs cost nothing until used. |
| Spawn tree: missing parents, cycles (design) | Parents without turns appear as $0 stubs; a guard stops cycles; tests for both. |
| Haiku 5.5 and long-context price tiers (design) | Haiku 5.5 is priced at the under-100K rate; it was about 0.1% of the first window, so the gap is noted, not modelled. |
