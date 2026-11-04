# Gated scheduled tasks

Four jobs that used to start a full Claude desktop session on every run, even when there was nothing to do, now run from
launchd. Each wrapper does the cheap checks in plain shell and calls `claude -p` (Sonnet or Haiku, with a turn cap and a
dollar cap) only for the step that needs a model. Added 2026-11-04 (token-efficiency brief, recommendation 8).

| launchd job | schedule (US Eastern) | replaces desktop task | model use |
|---|---|---|---|
| `com.purplelink.p1-coding-gate` | every 4 h at :17 | `p1-blind-coding` | none unless `p1_coding_prep.py` says BATCH READY; then Sonnet, same prompt |
| `com.purplelink.dashboard-live-gate` | 11:00, 15:00, 19:00 | `dashboard-live-publish` | none unless a build is staged and matches; then Haiku publishes |
| `com.purplelink.dashboard-refresh` | 04:33 | `refresh-purplelink-dashboard` | Haiku (Gmail counts), Sonnet (2b drafts), Haiku (publish); export and build are shell |
| `com.purplelink.cost-console-refresh` | 04:42 | `cost-console-refresh` | Haiku for the publish only; parse and build are shell |

- Installed copies live in `~/.purplelink/bin/` (plists in `~/Library/LaunchAgents/`); this folder is the source.
- Logs: `~/Library/Logs/purplelink-<job>.log`. A failure shows one banner notification; success is silent.
- `GATE_DRYRUN=1 bash ~/.purplelink/bin/<script>` logs the claude command instead of running it.
- The prompts are the desktop tasks' own `~/.claude/scheduled-tasks/<id>/SKILL.md` files, so editing one still changes
  behaviour. To go back to a desktop task: re-enable it and `launchctl bootout gui/$(id -u) <plist>`.
- `claude -p` never uses Opus. Publishes never use force.
