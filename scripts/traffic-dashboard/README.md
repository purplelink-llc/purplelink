# Traffic dashboard

A daily read on traffic across both properties — `purplelink.llc` and
`getmuscleonglp.com` — from each site's own first-party analytics. No GA4, no
third-party vendor, no login.

## Use it

```bash
python3 scripts/traffic-dashboard/traffic_dashboard.py --open
```

It prints a summary to the terminal and writes the dashboard to
`~/.purplelink/traffic/dashboard.html`. Open that file any time — bookmark it:

```
file:///Users/benampel/.purplelink/traffic/dashboard.html
```

Flags: `--open` opens it when done, `--no-fetch` re-renders from the local
archive without hitting the network.

## It runs itself

A launchd agent refreshes it every day at 9:00am:

- Job: `~/Library/LaunchAgents/com.benampel.purplelink-traffic.daily.plist`
- Entry point: `~/.purplelink/traffic/run.sh`
- Logs: `~/.purplelink/traffic/run.log` and `run.err.log`

`run.sh` copies the latest script from this repo when the external volume is
mounted, and falls back to its cached copy when it is not, so an unplugged drive
does not silently skip a day.

```bash
# check it is registered / fire it manually
launchctl list | grep purplelink-traffic
launchctl kickstart -k gui/$(id -u)/com.benampel.purplelink-traffic.daily
```

## Config

Tokens live outside this repo (which is public), in
`~/.config/purplelink/traffic.env`, mode 600:

```
PURPLELINK_STATS_TOKEN=...
MUSCLEONGLP_STATS_TOKEN=...
```

Both are each site's `STATS_TOKEN` Netlify environment variable. Environment
variables of the same name override the file.

## What it does with the data

Each run merges the fetched daily figures into `~/.purplelink/traffic/history.json`.
That archive is the point: the stats endpoints aggregate by reading one stored
record per event, so a long window is slow and only as complete as what is still
in the store. Snapshotting daily builds a durable series that outlives it. A day
already recorded is never overwritten with a smaller number, so a partial read
cannot erase history.

## Reading it honestly

- Counts are **conservative**. The beacon is cookieless and honours Do Not
  Track, so opted-out visitors are never recorded.
- "Visitors" are rough. The per-visitor id is a daily-rotating hash, so it
  cannot link someone across days — treat the trend as the signal, not any
  single day's number.
- Week-over-week is **suppressed** when the prior week predates the first day of
  tracking. Otherwise the dashboard would report huge growth that only measures
  when the beacon was installed.
- Today's bar is always partial — it is drawn faded for that reason.
