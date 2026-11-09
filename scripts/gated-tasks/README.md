# Gated scheduled tasks

Four jobs that used to start a full Claude desktop session on every run, even when there was nothing to do, now run from
launchd. Each wrapper does the cheap checks in plain shell and calls `claude -p` (Sonnet or Haiku, with a turn cap and a
dollar cap) only for the step that needs a model. Added 2026-11-04 (token-efficiency brief, recommendation 8).

| launchd job | schedule (US Eastern) | replaces desktop task | model use |
|---|---|---|---|
| `com.purplelink.p1-coding-gate` | every 4 h at :17 | `p1-blind-coding` | none unless `p1_coding_prep.py` says BATCH READY; then Sonnet, same prompt |
| `com.purplelink.dashboard-live-gate` | 05:40, 11:40, 15:40, 19:40 | (watchdog for `dashboard-live-publish`) | none; notifies when a staged build missed its slot or nothing published for 30 h |
| `com.purplelink.dashboard-refresh` | 04:33 | `refresh-purplelink-dashboard` | Haiku (Gmail counts), Sonnet (2b drafts); export, build and staging are shell |
| `com.purplelink.cost-console-refresh` | 04:42 | (builds for `cost-console-refresh`) | none; parse and build are shell |

- Installed copies live in `~/.purplelink/bin/` (plists in `~/Library/LaunchAgents/`); this folder is the source.
- Logs: `~/Library/Logs/purplelink-<job>.log`. A failure shows one banner notification; success is silent.
- `GATE_DRYRUN=1 bash ~/.purplelink/bin/<script>` logs the claude command instead of running it.
- The prompts are the desktop tasks' own `~/.claude/scheduled-tasks/<id>/SKILL.md` files, so editing one still changes
  behaviour. To go back to a desktop task: re-enable it and `launchctl bootout gui/$(id -u) <plist>`.
- `claude -p` never uses Opus. Publishes never use force.

## Artifact publishes stay in the desktop app (2026-11-07)

Headless `claude -p` has no Artifact tool, so the launchd publish steps never published: the dashboard and the cost
console went stale while the jobs logged "done". Publishing is back in two desktop scheduled tasks:

- `dashboard-live-publish` (05:00, 11:00, 15:00, 19:00) publishes whatever `dashboard_stage.py stage` left in
  `~/.purplelink/traffic/live-build`. The nightly refresh and the hourly `forecast_watch.py` both stage through it:
  build into `.live-build.new`, check every dataset file parses, swap it in under `.export.lock`, then write
  `publish-pending.json` with a hash of the whole tree. The task runs `dashboard_stage.py prep <scratchpad>/dash`
  (copy under the lock, hash checked), publishes, then `dashboard_stage.py record` (bookkeeping, status file, and
  clears the pending flag only if no newer build arrived meanwhile).
- `cost-console-refresh` (04:55) publishes `~/.purplelink/cost-console/index.html` built at 04:42 and writes
  `published-at`; the 04:42 job notifies when that is more than 30 hours old.
- `dashboard-live-gate.sh` is now a watchdog (`dashboard_stage.py watchdog`), one notification per problem per day.
- `run_claude` refuses an empty prompt: under launchd stdin is `/dev/null`, so a call without `< prompt-file` used to
  run with nothing (the 2b drafts step until 2026-11-07).
