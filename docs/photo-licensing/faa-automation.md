# FAA Batch Upload — Automation

`scripts/faa-upload.py` uploads the staged batch to Fine Art America by driving a
Chrome you're already signed into. It never sees or handles your password.

## Why it works this way

FAA has no artist upload API, no FTP, and no CSV import — their multi-image
uploader tops out at 5 files. The only route to automation is browser control.
The script attaches to a running Chrome over the DevTools protocol, so
authentication is something you do once, by hand, in that browser.

## One-time setup

1. **Quit Chrome completely** (Cmd-Q — not just closing windows).
2. Start Chrome with the debug port open:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.faa-chrome"
```

3. In that window, sign in to fineartamerica.com. The profile persists, so later
   runs skip this step.

A separate `--user-data-dir` is required: since Chrome 136, the debug port is
ignored on the default profile. That's why this is a dedicated profile rather
than your normal one.

## Running it

Dry run first — fills the form, verifies metadata populated, saves nothing:

```bash
python3 scripts/faa-upload.py --limit 3 --dry-run
```

Then a small real batch before committing to the rest:

```bash
python3 scripts/faa-upload.py --limit 5
```

The full first batch:

```bash
python3 scripts/faa-upload.py --dir photo-licensing-workspace/faa-upload/batch-01-first25
```

The remaining 242 (Premium membership required — free tier caps at 25):

```bash
python3 scripts/faa-upload.py --dir photo-licensing-workspace/faa-upload/batch-02-remaining
```

Progress at any time:

```bash
python3 scripts/faa-upload.py --status
```

## Behavior worth knowing

- **Resumable.** Every success is journaled to
  `photo-licensing-workspace/faa-upload-state.json`. Re-running skips finished
  images, so an interrupted run costs nothing.
- **Rate limited.** Randomized 6–14 second gaps between uploads. FAA has a
  documented history of closing accounts that look automated; this keeps the
  pace human. Adjust with `--min-delay` / `--max-delay` — raising is safer than
  lowering.
- **Metadata fallback.** FAA auto-fills title, description, and keywords from
  embedded IPTC. If any field comes back empty, the script writes it from the
  queue CSV, so nothing publishes bare.
- **Leading-comma fix.** FAA prepends a stray comma to ingested keywords; the
  script strips it.
- **Fails fast on a dead session.** If Chrome isn't signed in, it aborts
  immediately rather than grinding through every image failing the same way.
- **Ordered by priority.** Uploads follow the queue's ranking, so the strongest
  work goes up first — which matters if you stop partway.

## Before the full run

- Confirm the dry run reports `title auto-filled: True` and a keyword count in
  the hundreds of characters. If keywords come back near zero, stop and tell me.
- Spot-check the first few images on your public profile.
- Check whether the per-image page has product enable/disable controls, so
  apparel and phone cases can be turned off for landscape work.
