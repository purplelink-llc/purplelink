# Social poster (PR 219), retired as a poster

`scripts/social/poster.py` used to turn new guides, releases and videos into queue items and post them. On 2026-10-18
that was consolidated into one posting path: `backend/scripts/social.py` and its adapters (`docs/social-posting.md`).

What remains here:

- `scripts/social/events.py` and `core.py`: detection of new guides, releases and videos from the live site, HTTP,
  wording and house-voice helpers. The daily pipeline (`backend/socialpost/daily/`) imports them as a library.
- `scripts/social/poster.py scan`: a read-only count of what is live. Every other command (`run`, `status`,
  `whoami`, `refresh`) exits 2 with a pointer. It writes no queue, holds no tokens and posts nothing.
- No launchd job or scheduled task runs `poster.py` (checked 2026-10-18).
- The short-link redirects in `netlify.toml` (`/li/`, `/bs/`, `/th/`, `/x/`, `/md/`, `/dev/`) are unchanged and harmless.

Tests: `site-tests/test_social_poster.py` (detection, limits, and proof that it no longer posts).
