# Social poster

`scripts/social/poster.py` turns three events into one approval-queue item each, with one variant per channel, and
posts those items as the company account only. Decided by Ben on 2026-10-18.

## What it does

| Event kind | Detected from (live only) | Facts read from the live site |
|---|---|---|
| `guide_live` | a new `/guides/<slug>/` URL in https://purplelink.llc/sitemap.xml that answers 200 | og:title, meta description, first paragraphs |
| `release_published` | a product page's JSON-LD `softwareVersion` changes and https://purplelink.llc/changelog/ has `<h2>App X.Y.Z</h2>` | name, version, price (JSON-LD), release notes (changelog) |
| `video_published` | a new entry in the Purplelink channel's public RSS feed that is not a Short (`/shorts/<id>` does not answer 200) | title (oEmbed, public videos only), first paragraph of the description |

The first scan records everything already live as seen and announces nothing. Builds are batched (06:00 and 17:00
Eastern), so a merged page produces an event only after it is built.

| Channel | Limit | Carries | Link |
|---|---|---|---|
| LinkedIn (company page 120183926) | 3,000 characters | all three | `/li/g/<slug>`, `/li/<app>` |
| Bluesky | 300 graphemes, link card | all three | `/bs/...` |
| Threads | 500 characters, at most 5 links | all three | `/th/...` |
| X | 280 (a URL counts 23) | all three | `/x/...` |
| Mastodon | 500 (a URL counts 23) | all three | `/md/...` |
| dev.to | full article, `canonical_url` = the purplelink.llc page | guides only | `/dev/g/<slug>` and tagged links in the body |
| Email release list (Resend broadcast) | none | releases only | the product page with `utm_source=email-release` |

Video posts link to the YouTube watch page directly: UTM tags on youtube.com reach none of our analytics, and YouTube
Studio already splits traffic by referring site. The short links are 302s in `netlify.toml`
(`site-tests/test_social_redirects.py`), and `netlify/functions/stats.mjs` folds each channel into one label.

## Standing approval (2026-10-18)

Only for these three kinds, only for items the poster wrote and nobody edited. The item moves from `pending/` to
`approved/` (queue actor `standing-approval`) when all of these pass:

- the item has not expired (7 days, 5 for videos);
- the page answers 200 on the live site (a 404 waits and is retried on the next run, never posted);
- title, version and price read again from the live page match the item;
- every variant is inside its channel's limit and the house voice (no emoji, em dash or hype).

Each channel then also checks, before it posts:

- the identity check passes twice (below);
- the tracked short link answers 200;
- at most 1 post on that channel that day (Eastern) and 3 in 7 days;
- no post of the same event or the same text on that channel within 30 days.

Anything else (another kind, an edited item, a manual draft, any failed check) waits in `pending/` for Ben's
`approval_queue.py approve`. An item Ben approved still goes through every per-channel check.

## Identity

Each channel posts only if the account behind the token is the pinned company account. The id and handle are
constants in `scripts/social/core.py` (`PINS`, changed only by a reviewed commit) and also in the channel's
mode-600 config file. The account is read before anything is created and again right before publishing:

| Channel | How the account is read |
|---|---|
| Threads | `GET /me` (and the published post read back) |
| Bluesky | the session DID from `createSession`, then `getSession` DID and handle |
| X | `GET /2/users/me` |
| Mastodon | `verify_credentials`; the server must be the pinned one |
| dev.to | `GET /api/users/me` |
| Email | the Resend segment id and name; the sender must be an @purplelink.llc address |
| LinkedIn | `backend/scripts/linkedin_post.py`, unchanged: the company admin page URL and the composer's "Purplelink LLC" |

Any mismatch means REFUSED: exit 4, a macOS notification, a `REFUSED` line in `~/.purplelink/social/log.jsonl`,
nothing posted, and that channel is not tried again until the next day. A world-readable config is refused too.

## Running it

Dry run is the default. `--live` is required to write queue items or post.

```bash
python3 scripts/social/poster.py status
```

```bash
python3 scripts/social/poster.py scan --live --seed
```

```bash
python3 scripts/social/poster.py scan --live
```

```bash
python3 scripts/social/poster.py run --live
```

There is no launchd job yet. If one is added, it runs only `scan --live` then `run --live`, at most twice a day after
the 06:00 and 17:00 builds, and never with anything that skips the checks.

Files: `~/.purplelink/social/state.json` (seen events, posts, refusals), `~/.purplelink/social/log.jsonl`, the queue
at `~/.purplelink/queue/`, configs in `~/.config/purplelink/social/<channel>.json` (mode 600, never committed, never
printed).

## Ben's one-time setup

Every channel stays disabled until both steps are done for it: its config file exists, and its id and handle are
pinned in `core.PINS` by a commit. Do these by hand; no agent creates an account or signs in.

1. **Seed the baseline once:** `python3 scripts/social/poster.py scan --live --seed`.
2. **Bluesky:** make or choose the company account, create an app password (Settings, Privacy and security, App
   passwords), write `bluesky.json` with `id` (the DID), `handle`, `app_password`, then `chmod 600` it.
3. **Threads:** create the company Threads profile. On your own Meta app, add it under App roles as a Threads
   Tester and accept the invite. Get a long-lived token with `threads_basic` and `threads_content_publish`, then
   write `threads.json` with `id`, `handle`, `access_token` and `expires_at` (ISO date). Run
   `poster.py refresh threads` at least every 60 days; a token has to be 24 hours old before it can be refreshed.
4. **X:** posting is pay-per-use (docs.x.com pricing, read 2026-10-18): $0.015 a post, $0.20 for a post with a
   link, and about $0.01 per identity read, so about $0.22 per announcement. It stays off until you buy credits and
   set `"paid_posting_ok": true`. The config needs an OAuth 2.0 user token with `tweet.read tweet.write users.read
   offline.access`: `id`, `handle`, `access_token`, `refresh_token`, `client_id`, `expires_at`.
5. **Mastodon:** pick a server, make the account, and create an application token with `read:accounts
   write:statuses` only. Write `mastodon.json` with `id`, `handle` (the acct), `instance` (`https://server`) and
   `access_token`.
6. **dev.to:** make the company account and create an API key under Settings, Extensions. Write `devto.json` with
   `id`, `handle` and `api_key`.
7. **Email release list:** build the double opt-in signup first (the RubbleFront list in
   `netlify/lib/rubblefront-list.mjs` is the pattern), backed by one Resend segment. Write `email.json` with
   `id` (segment id), `handle` (segment name), `api_key`, `from` (an @purplelink.llc sender) and
   `"double_opt_in": true`.
8. **LinkedIn:** write `linkedin.json` with `{"enabled": true}`. The browser session from
   `backend/scripts/linkedin_login.py` is reused.
9. **Pin each account:** run `poster.py whoami <channel> --unpinned`. It prints only the id and handle. Put those in
   `PINS` in `scripts/social/core.py` through a pull request, then check with `poster.py whoami <channel>`.
10. **Test before going live:** `poster.py run` (a dry run) shows what each channel would post.

Reddit, Hacker News and Product Hunt are not channels here and must not be added: those stay drafts posted by hand.
