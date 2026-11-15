# Sparkle beta channel (all Mac apps, added 2026-11-14)

Every Purplelink Mac app that updates through Sparkle has an opt-in beta channel. A user turns on
"Get beta updates" in the app's settings (next to "Check for updates automatically"; off by default, stored in
UserDefaults under `getBetaUpdates`). The app's updater delegate then returns `["beta"]` from
`allowedChannels(for:)`, so Sparkle also offers appcast items tagged `<sparkle:channel>beta</sparkle:channel>`.
Items without a channel reach everyone, so a beta user still gets every regular release. Turning the box off takes
the user back to regular releases from the next one (Sparkle never downgrades).

The feed URL does not change. The Setapp and Mac App Store editions compile Sparkle out and have no checkbox.

## Publishing a beta

Before the first beta of any app, purplelink-llc/purplelink PR 741 must be **live** (merged and through the next 06:00
or 17:00 build). Without it, the download functions treat the beta as the newest release and hand it to every
buyer and trial downloader.

In the app repo, build and stage as usual, then:

    scripts/publish-release.sh <version> --dry-run --beta   # check: preflight says "BETA channel"
    scripts/publish-release.sh <version> --beta

- The script records the DMG in `releases/beta-builds.txt` (beside the DMGs, not in git) and regenerates the
  appcast in two passes: the regular DMGs first, then the betas with `generate_appcast --channel beta`. The XML is
  never hand-edited, so signed feeds stay valid. Two passes are needed because the scripts delete the appcast
  before regenerating and `generate_appcast --channel` tags every item that is new to the feed.
- For a beta the appcast is uploaded before the DMG, so the site never sees an unmarked beta DMG.
- The site (`netlify/lib/release-pick.mjs`) leaves any version whose appcast item has a channel out of
  "newest DMG" for the buyer page and the public trial download, paid and trial names alike. Opted-in installs
  still fetch it through the update door.
- To promote a beta to a regular release, publish a higher version without `--beta`. Once a regular release is
  newer, `generate_appcast` retires the old beta like any older item.
- `--rollback` removes the version from the beta list too.

Née (repo `Lenses`) and Barroom differ: a beta publish reads the live feed, fetches its newest regular DMG from the
store, checks it against the live signature and writes it in a plain pass before the beta pass, so installs without
the setting keep seeing the regular release. Lenses stages with `scripts/stage-appcast.sh --beta`; its
`publish-release.sh` sees the channel tag and uploads the appcast first. Details in each repo's README or runbook.

## Per app

| App | PR(s), all squash-merged 2026-11-14/15 | Carried by |
| --- | --- | --- |
| Barroom | barroom 3, 4, 5 | next release |
| FormRing | formring 1 | next release |
| Keyfeel | keyfeel 33 (34: de/ja draft fixes, still `needs_review`) | next release |
| Legroom | legroom 69 (70: test compile fix) | next release after 1.13.1 |
| Lenscrib | lenscrib 13 | next release |
| ModernTex | moderntex 224 | first release after 3.2.0 |
| Née | Lenses 7, 8 | next release |
| Outbound Veil | outbound-veil 29 | next release |
| Panely | panely 35 | next release |
| Summonly | summonly 39 | next release |
| Tapefolio | tapefolio 63 | next release |
| Vitae | vitae 98 (99: l10n lint cleanup) | next release |

The setting lives next to "Check for updates automatically" in each app (Née: its menu bar menu). Not covered:
CinemaApp (no remote), Claude Buddy and BatteryMeter (personal, hand-written appcasts), CursorRing (no Sparkle),
Scholar Belt (Chrome extension), Watchlight (no app yet).

These app repos have no CI; each PR was tested locally through the heavy queue. The two-pass appcast has been run
only against a fake `generate_appcast`, so dry-run (`--dry-run --beta`) the first real beta of any app and read the
staged appcast before publishing.
