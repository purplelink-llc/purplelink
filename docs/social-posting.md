# Social posting: scheduled posts to the company accounts

`backend/scripts/social.py` is one front for posting to Purplelink's own accounts: the LinkedIn company page,
Bluesky @purplelink.llc, Threads, Mastodon and X. Ben writes and approves a post; a launchd job sends approved posts at
their scheduled time. Decided by Ben on 2026-10-18. The code is public; the queue, the config and every secret are not.

## Not the same as `scripts/social/poster.py`

`docs/social-poster.md` describes a different tool: it watches the live site for new guides, releases and videos and
writes one queue item per event. This tool posts items a person wrote and approved, at a time that person chose, with
images and alt text. They do not share a queue, state or config. Until Ben decides which one owns a platform, do not
enable both for the same account: each checks the account it posts as, but neither knows about the other's posts.

## Rules (hard)

- Company accounts only. Every adapter reads the identity of the account it is signed in as (handle, user id or page)
  and compares it with the `expected` block of `~/.config/purplelink/social.json`. A mismatch, or an empty expected
  value, means the post is refused: nothing is created, exit code 4, a macOS notification, and no retry. LinkedIn is
  company page 120183926 only (`backend/scripts/linkedin_post.py` keeps its own checks, unchanged).
- Nothing goes out without approval. The scheduler posts an item only if its front matter has `status: approved`,
  `approved_by: ben`, an `approved_at`, and an `approved_hash` that matches the item's current content. Only
  `social.py approve <id>` writes that hash, so typing the fields into a draft does nothing, and editing a post
  after approval voids it (the item goes back to draft). A Claude session runs `approve` only when Ben says so in chat.
- Kill switch: if `~/.purplelink/social/PAUSE` exists, nothing posts (`social.py pause` / `resume`).
- Secrets live in the macOS login keychain, service `purplelink-social-<platform>`, one account per field. They are
  never printed, logged, committed or put in a URL. There is no Bluesky API credential at all.
- Reddit, Hacker News and Product Hunt are not channels here. Reddit stays manual.
- Playwright runs headless and never types into Ben's session.

## Files

| What | Where |
|---|---|
| Queue (one Markdown file per post) | `~/.purplelink/social/queue/` |
| Config, no secrets | `~/.config/purplelink/social.json` (mode 600) |
| Log | `~/Library/Logs/purplelink-social.log` |
| Kill switch | `~/.purplelink/social/PAUSE` |
| Scheduler | launchd `com.purplelink.social-scheduler`, every 10 minutes, runs `~/.purplelink/bin/social-run-due.sh` (a copy of `backend/scripts/run_social.sh`) |
| Bluesky session | `~/.purplelink/bluesky-profile` |

## A queue item

Front matter is one `key: <JSON value>` per line (valid YAML). The body holds the text, one `## <platform>` section
per platform and a `## default` for the rest. `{link}` is replaced by that platform's tagged link; without it the link
goes on its own last line.

```
---
id: "20261022-vitae-140"
created: "2026-10-18T15:05:30-04:00"
scheduled_at: "2026-10-22T09:30:00-04:00"
status: "draft"
approved_by: null
approved_at: null
platforms: ["bluesky", "threads"]
campaign: "vitae-140"
link: "https://purplelink.llc/vitae/"
images: [{"path": "/path/card.png", "alt": "What the picture shows", "platforms": ["threads"]}]
text_only: []
experiment_note: "what this post is compared with"
results: {}
---

Notes, not posted.

## default
Text for every platform. {link}

## threads
Text only for Threads. {link}
```

- `status`: draft, approved, posted, failed, cancelled, or stale (set by the scheduler).
- `scheduled_at` needs a timezone offset.
- UTM: the link in `link` must be bare. Each platform gets `utm_source=<platform>&utm_medium=social&utm_campaign=<campaign>`.
- `images[].platforms` is optional; without it the image goes to every platform that takes images.
- `text_only`: platforms that post without the images (LinkedIn cannot attach images yet; it can attach a PDF
  `document: {"path": "deck.pdf", "title": "..."}`).
- `results` is written back per platform: `status`, `url`, `id`, `posted_at`, `error`, `attempts`, `verified`.

## Commands

```
python3 backend/scripts/social.py new <slug> [--platforms a,b] [--link URL] [--campaign c] [--at ISO]
python3 backend/scripts/social.py validate [<id>|--all]
python3 backend/scripts/social.py preview <id> [--platform p]
python3 backend/scripts/social.py approve <id>
python3 backend/scripts/social.py cancel <id>
python3 backend/scripts/social.py post <id> [--platform p] [--dry-run]
python3 backend/scripts/social.py run-due
python3 backend/scripts/social.py status
python3 backend/scripts/social.py whoami [platform]
python3 backend/scripts/social.py setup threads|mastodon|x|bluesky
python3 backend/scripts/social.py refresh threads|x
python3 backend/scripts/social.py pause | resume
```

`validate` checks, per platform: text length (Bluesky counts graphemes; X and Mastodon count every link as 23),
image count, format, size and magic bytes, alt text present and within its limit, an https link on an allowed host,
and the campaign name. `approve` refuses an item that fails validation or is more than 48 hours past its time.
`post --dry-run` builds everything and sends nothing (Bluesky and LinkedIn fill the composer headless and stop).

## What the scheduler does

`run-due` runs every 10 minutes. For each approved item whose `scheduled_at` has passed:

1. PAUSE present: stop. Another `run-due` running: stop (file lock).
2. Approval hash no longer matches, or the item no longer validates: back to draft, notification.
3. More than 48 hours late: status `stale`, notification, needs a new `approve`.
4. Outside the posting window (`windows` in config, in `timezone`): wait.
5. For each platform not yet final: skip if disabled in config; check the account; post; write the result to the
   file at once; verify; later passes never touch a platform that already succeeded.
6. A failure is retried at most 3 times in all (backoff 10, 40, 120 minutes), then marked failed. A failure that may
   have posted (a timeout on the final publish call) is never retried: it is marked failed with `ambiguous` and a
   person checks the account. A run that died mid-post is treated the same way.
7. When every platform is final: status posted or failed, one notification with all URLs, one row per platform
   appended to `Outreach/OUTREACH-LOG.md`, and `log_change.py add --area outreach ...` with the item's
   `experiment_note` as the comparison.

## Platforms (facts read 2026-10-18; sources in the private research brief)

| Platform | Auth | Text | Images | Alt text |
|---|---|---|---|---|
| LinkedIn | saved browser session | 3,000 | none (PDF document only) | n/a |
| Bluesky | saved browser session | 300 graphemes | 4, file chooser, thumbnails de-duplicated | per image through the ALT dialog |
| Threads | long-lived token (60 days), `threads_basic` + `threads_content_publish` | 500 | 20 in a carousel, JPEG or PNG, 8 MB, public URL | `alt_text` on each container |
| Mastodon | app token, `read:accounts write:statuses write:media` | 500 (server's limit) | 4, 16 MB | `description` on `POST /api/v2/media` |
| X | OAuth 2.0 user token, refresh token | 280 | 4, `POST /2/media/upload` | `POST /2/media/metadata` |

- Threads publishes a container with `POST /{user-id}/threads`, waits for `FINISHED`, then `threads_publish`; 250
  posts a day per profile. The token is refreshed by `run-due` after 30 days (24 hours minimum age).
- Threads fetches images from a public URL. `social.py` uploads each image to the `social-media` Netlify Blobs store
  (`netlify blobs:set`, key `<40 hex of sha256>.png|jpg`) and `netlify/functions/social-media.mjs` serves it read-only
  at `https://purplelink.llc/social-media/<key>`: GET and HEAD only, no listing, strict key pattern, content sniffed.
  Until the function is deployed (next 06:00 or 17:00 Eastern build), Threads posts with images fail cleanly.
- Mastodon: recommended server mastodon.social (open registration, no advertising or bot rule). fosstodon.org and
  mas.to are invitation-only and ban promotion; techhub.social needs approval, bans direct advertising and requires
  silent-mode bots. Set the account's automated flag. Keep posts informational.
- X is pay-per-use only (docs.x.com pricing): $0.015 a post, $0.20 for a post with a link in the text, $0.005 for alt
  text. Every Purplelink post has a link, so about $0.20 each. It stays disabled until `enabled` and
  `paid_posting_ok` are both true in the config.
- Bluesky has no standing file input; the photo button creates one on click, so the poster uses Playwright's file
  chooser. The signed-in account is read from the web app's stored session (or the left-nav Profile link) and
  resolved on the public AppView to a DID. Posts are found and verified on `public.api.bsky.app` `getAuthorFeed`.
- LinkedIn shows no public permalink for a company post here, so the result URL is the company's posts page and
  success is confirmed by finding the text on that page.

## Ben's setup, per platform

Everything below is run in your own terminal. No agent creates accounts, developer apps or tokens.

- **LinkedIn**: nothing; the saved session works (`social.py whoami linkedin`). If it expires:
  `python3 backend/scripts/linkedin_login.py`.
- **Bluesky**: `python3 backend/scripts/social.py setup bluesky`. A window opens; log in as @purplelink.llc and press
  Enter. Check with `social.py whoami bluesky`.
- **Threads**: `social.py setup threads` prints the Meta app steps, then asks (hidden) for the token and optional app
  secret, shows which profile the token belongs to, and pins it only if you type `yes`.
- **Mastodon**: `social.py setup mastodon`: create the account, tick the automated flag, create an application token
  with the three scopes, paste the server URL and token.
- **X**: `social.py setup x` (buy credits first). It runs the authorization on 127.0.0.1:8765. It leaves X disabled.

After each setup run `social.py whoami`; the first real post of each platform should be a dry run followed by a
post you watch.

## Tests

`backend/tests/test_social_*.py` (mocked HTTP, fake browser pages, no keychain) and
`netlify/tests/social-media.test.mjs`. CI runs them with the backend and Netlify test jobs.
