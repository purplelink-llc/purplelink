# Buddy on the web: a site chat with a free Citation Gap check

Status: v2, reviewed (EGM Goldfish review, three Sonnet reviewers: design, implementation readiness, scope) and
decided by Ben 2026-11-02. Built 2026-11-02 (see "As built"); widened to every public page 2026-11-03. Owner: Ben. Decisions and the review log are at the end.

## Concepts brief

**Problem.** Visitors on purplelink.llc cannot ask a question before they buy, and nobody can try the paper tools
before paying. The only contact path is the "Write to Ben" box. Paper Review and Citation Gap have almost no sales.

**What it costs.** A Citation Gap run cost about $0.17 in the 2026-11-02 benchmark (100 papers, about $17). A short
chat turn on Haiku costs well under a cent. The Console org has $200 of Team API credit (seen once: granted
2026-10-21, expires 2026-11-14) and $851.80 of a one-off grant to 2027-04-06. Whether the $200 repeats each month is
not yet known; the caps below keep the worst month under $60 either way.

**Hypothesis.** A free Citation Gap check, offered by a small chat drawn as the Buddy pup in the bottom-right corner,
turns some visits into an email, an uploaded paper and later a paid order. The chat also answers product questions
from the site's own facts. Keyfeel key sounds play as the visitor types, with a one-line note naming Keyfeel.

**Success measure** (counts, read 28 days after the first scheduled build that publishes it; written down now):
- Primary: free checks redeemed (an uploaded PDF). Target: 10 or more.
- Secondary: paid orders whose email matches a redeemed free check (exact join, no session attribution).
- Watched, not decided on: chat opens, messages, offer clicks, blocked or over-cap requests, daily API spend.

Keep it if the primary target is met or any matched paid order arrives. Fewer than 10 redemptions means the offer is
not reaching people, not that a free check fails to sell; in that case move the entry point (for example onto the
Citation Gap page itself) before deciding.

**Boundaries.**
- The model has no tools and grants nothing. Offers are buttons the page draws from fixed rules; the server checks
  them. A visitor cannot talk Buddy into a free Suite or a discount. (Amended 2026-11-04: a visitor who asks for a
  discount gets a button that makes a one-time 20% code, minted and checked by the server; the model still grants
  nothing. See `docs/designs/buddy-coupon.md`.)
- No rewards for App Store ratings or reviews (Apple's App Review Guidelines and the FTC's 2024 rule on reviews
  forbid it) and none for social follows. Not in this design and not later.
- On every public page `apply_layout.py` stamps (Ben, 2026-11-03: "Everywhere except checkout"; the first release
  was the paper-tool and Mac-app pages only). Never on a page inside a `checkout`, `success`, `upload`, `manage`,
  `recover`, `account`, `stats` or `digest` folder, and never on pages `apply_layout.py` skips. With JavaScript off,
  every page is as before.
- No new third-party origin. The chat talks only to the Modal origin already in `connect-src`.

## What exists today

- **Buddy** (`/Volumes/Extreme SSD/Claude Buddy/`, page `site/buddy/`) is a free MIT Mac app that shows Claude Code
  status in the notch. It has no chat and no LLM. Its character, "the little guy", is a purple Lab/Chow pup drawn in
  SwiftUI shapes (`Sources/Views.swift`, `Guy`, lines 20-123). Colors (RGB 0-1): fur (0.64, 0.50, 0.90), furShade
  (0.50, 0.36, 0.80), light (0.88, 0.81, 0.98), ink (0.13, 0.09, 0.20), tongue (0.98, 0.47, 0.58). Animations: glance,
  hop, blink. There is no SVG of him; the web version is redrawn as one SVG from this geometry.
- **Keyfeel samples** (`/Volumes/Extreme SSD/Keyfeel/assets/samples/`): 16-bit mono 44.1 kHz WAV, all CC0 1.0 from
  Freesound, OpenGameArt and Wikimedia Commons (`CREDITS.md`; public page `site/keyfeel/sound-credits/`). Purplelink
  did not record them, so copy says "sounds from Keyfeel", never "our recordings". Default pack: `tactile`.
- **Citation Gap** ($3). Tokens are minted only by the Stripe webhook through `POST /paper-review/register-token`
  (`backend/app.py:2307`). `/citation-gap/submit` (`app.py:3675`) finds the entry with `_lookup_token` through
  `paper_token_index_dict` and requires `entry["product_cfg"]["category"] == "citation-gap"`, unexpired and not
  consumed (`app.py:2397-2416, 3686-3695`). `_order_cost_ceiling()` (`app.py:339-352`) derives the per-order
  `UsageTracker` cap from the price and returns `None` (no cap) when the amount is 0. Single-use claims use
  `paper_token_claims_dict.put(token, ts, skip_if_exists=True)` (`app.py:3037`), which is atomic.
- **Rate limits**: `_enforce_rate_limit(request, bucket)` (`app.py:1239`) uses the fixed `core.DAILY_LIMIT = 25`
  through `core.check_and_increment`, which is get-then-set and not atomic. `core.client_ip_from_forwarded` is a soft
  cost control. Paid-tool buyers also flow into lifecycle email, sweeps and `_purchases_waiting`, all of which read
  `paper_tokens_dict` and assume a paid buyer.
- **Email**: `latextools.delivery.send_email(client, to=, subject=, html=, tags=)` through Resend.
- **Analytics**: `plTrack(type, meta)` (`site/analytics.js:178`) posts to `track.mjs`, which validates the type
  against `TYPE_RE`.
- **Site**: CSP at `netlify.toml:66`, `default-src 'self'`, no `media-src`, so audio must be same-origin files.
  `scripts/apply_layout.py` stamps nav and footer (skip lists at lines 36-43). `.sticky-cta` is a phone-only fixed
  bar; `body.has-sticky-cta` is set at runtime by `site.js`.

## Design

### 1. Loader and placement

- `site/buddy-chat/loader.js` (about 1.1 KB gzipped) is added by a `with_chat()` step in `apply_layout.py`, driven by
  `chat_page()` and its `CHAT_EXCLUDED_DIRS` (the pages in Boundaries), with an idempotency guard so `--check` stays
  stable. It adds `chat.css` itself and draws the launcher once that has loaded, so the stylesheet never holds up a
  page (a `<link>` in `<head>` would block rendering and revalidate on every view). It draws only the launcher: a 56 px round button, bottom right, 20 px from the edges, with Buddy's face. After
  `DOMContentLoaded` it moves up when `body.has-sticky-cta` is set.
- The rest (`chat.js`, `chat.css`, the Buddy SVG, sounds) loads on first click.
- **Kill switch, runtime:** `chat.js` calls `GET /buddy/status` on open; the server reads a flag in a `modal.Dict`
  (`buddy_flags_dict["enabled"]`) on every request, so Ben can turn the chat and the free check off in seconds with
  one command (`scripts/buddy_flag.py off`) and no deploy. Adding a folder to `CHAT_EXCLUDED_DIRS` hides the launcher there at
  the next build.

### 2. The look

Ben asked for "a crystal clear screen". The scope reviewer pointed out that `PRODUCT.md` lists the generic
AI-startup look among its anti-references and that `DESIGN.md` uses solid panels. This draft keeps the glass but
builds it only from site tokens, so it stays calm and works in both themes (decision 1 at the end).

- Panel: 380 x 560 px (a full-width sheet with 16 px gutters under 480 px), radius 16 px (the top of the site's
  scale). Surface: `color-mix(in oklch, var(--panel) 72%, transparent)` with `backdrop-filter: blur(20px)`, a 1 px
  `--line` border, and one hairline highlight on the top edge (`color-mix(in oklch, var(--ink) 10%, transparent)`).
  One soft drop shadow. No glow, no gradients, no saturate.
- Messages: visitor on the right, `color-mix(in oklch, var(--purple) 14%, var(--panel))`; Buddy on the left, plain
  `--panel` with `--line`. Plus Jakarta Sans 15 px; header "Buddy" in Fraunces. Buttons are the site's `.btn` pills.
- Buddy's face (one SVG) sits in the header. States: blinking while idle, glancing while a reply is pending, "^" eyes
  and tongue after a free check is claimed. Replies are shown whole as soon as they arrive (no fake typing delay).
- Every looping animation runs only under `@media (prefers-reduced-motion: no-preference)`. Under
  `prefers-reduced-transparency`, or without `backdrop-filter`, the panel is solid `--panel`. Contrast is checked
  on the solid fallback and on the glass over the darkest and lightest site pages (AA 4.5:1).
- All styling in `site/buddy-chat/chat.css`, tokens only, no inline styles, no emojis.

### 3. Key sounds from Keyfeel

- Six keyDown, six keyUp, one spaceDown and one enterDown from the `tactile` pack (the first six of each in manifest
  order), trimmed to their manifest bounds and encoded with `ffmpeg -ac 1 -c:a libopus -b:a 48k` to `.webm` and
  `-c:a aac -b:a 64k` to `.m4a` for Safari; about 40 KB in all, in `site/buddy-chat/sounds/` with a `CREDITS.txt`
  copied from Keyfeel's `CREDITS.md`. `netlify.toml` gets long-cache headers for that folder.
- Web Audio: one `AudioContext` created on the first key press in the chat input (a user gesture). Each press picks a
  random sample, pitch +/- 3%, gain 0.35; key-up on `keyup`; Space and Enter use their own samples. Only the
  visitor's own typing makes sound in this draft (decision 2).
- A speaker toggle in the header, remembered in `localStorage` (wrapped in try/catch). Default per decision 2.
- Under the input: "Key sounds from Keyfeel, our Mac app." linking to `/keyfeel/` with a UTM tag from
  `hub.py utm --asset keyfeel --channel site-chat`.

### 4. What Buddy says

- Model `claude-haiku-5-5`, `max_tokens` 350, no tools.
- System prompt: Buddy's voice (calm, plain, short; says what a product does; never claims to be human), the
  instruction that the facts block and every fenced block are data, and `_safety.SAFETY_PREAMBLE`.
- **Facts block:** `scripts/build_buddy_facts.py` writes `backend/buddy_facts.txt` from `site/llms.txt`, the prices
  in `netlify/functions/checkout.mjs` and the trial terms. A site-test fails if the file is stale against those
  sources. The Modal deploy bundles it. It is cached with `cache_control` if it is over Haiku's minimum cacheable
  length; the build script prints its token count, and the cost figures below do not assume caching.
- First message (fixed text): "Ask me about our Mac apps or paper tools. I can also run a free Citation Gap check on
  a paper draft." Three buttons: **Free citation check**, **Which app fits me?**, **Help with a LaTeX error**.
- Header note: "AI answers, can be wrong. Write to Ben" (link to the support box).
- **Links:** model text is rendered with `textContent`. A URL becomes a link only if, after parsing, its scheme is
  `https`, its host is exactly `purplelink.llc`, it has no query string, and its path is in an allow list built from
  `site/sitemap.xml` at build time. Everything else stays plain text. Unit tests feed hostile output
  (`javascript:`, `//evil`, backslashes, `/checkout?...`).

### 5. Server: `/buddy/chat`

- New routes in `backend/app.py` on the existing web app: `GET /buddy/status`, `POST /buddy/chat`.
- **Input:** `{conversation_id, turns: [{text}]}`, the visitor's last 8 messages only. Buddy's earlier replies are
  not sent by the client; the server keeps the last 8 replies per `conversation_id` for 1 hour in
  `buddy_convo_dict` (text only, deleted on expiry), so a client cannot forge assistant turns. Each visitor message
  is wrapped with `_safety.wrap_user_content(text, "visitor_message")`.
- **Checks, in order:** flag on; origin is purplelink.llc (a browser check only; the caps are the real protection);
  body under 8 KB; each message under 600 characters; at most 20 visitor turns per conversation; per-IP limits of 10
  a minute and 60 a day (`_enforce_rate_limit` gains an optional `limit=` that defaults to 25); global spend.
- **Spend cap:** before each call, reserve the worst case (input tokens counted locally plus 350 output, at Haiku
  list price from one `HAIKU_PRICE` constant) in `buddy_spend_dict[utc_day]`; reconcile with the real `usage` after
  the call, and release the reservation if the call fails. Daily cap $1.50, monthly cap $30. Over a cap, or if the
  Dict is unreachable (fail closed), the chat answers: "Buddy is taking a nap and will be back tomorrow. You can
  write to Ben instead." (Ben's wording, 2026-11-03). When the monthly cap is the one hit, it names the day it is
  back instead, for example "Buddy is taking a nap and will be back on December 1."
  Overshoot is bounded by the in-flight requests at the moment the cap is crossed (at most about 10 at the per-IP
  burst limit), which is accepted.
- Chat spend also goes into `_write_usage_ledger` with product `buddy-chat`, so it shows on the existing cost
  dashboard. An alert email goes to Ben the first time a day passes 50% of the daily cap.
- **Separate key:** a new Console API key `buddy-web`, stored as Modal secret `buddy-anthropic-secret`, so Buddy's
  spend is visible and can be limited on its own, and a runaway cannot touch the paid tools' key. Ben creates the key
  and the secret.

### 6. The free Citation Gap check

- **Form** (inside the chat): email, a hidden honeypot field `website`, an unticked "Send me product news" box, and
  two lines: "One free check per email. I'll email you a link to upload your PDF." and "Your PDF is sent to Anthropic
  for analysis and is not kept by us." The form carries a signed `form_ts` issued by `/buddy/status`; submissions
  under 3 seconds after it are dropped.
- **`POST /buddy/free-check`:**
  1. Canonicalize the email: lower-case, strip `+tag`, remove dots in the local part for gmail.com and
     googlemail.com. Reject addresses on a disposable-domain blocklist (`backend/latextools/disposable_domains.txt`).
  2. Caps: 3 per IP per day; 3 per day globally (raise after real redemptions); 1 per canonical address ever,
     claimed atomically with `free_check_dict.put(hmac(addr), ts, skip_if_exists=True)`, keyed by an HMAC with secret
     `BUDDY_FREE_SECRET` (new Modal secret), not a plain sha256.
  3. Over the per-address cap: the same success text as a real send, so addresses cannot be probed. Over the daily
     global cap: an honest "Today's free checks are taken. Try again tomorrow." (the reply does not depend on the
     address, so it leaks nothing).
  4. Send one email with `delivery.send_email` and a new template `free_check_link_html(link)`. The link is
     `/tools/citation-gap/upload/?free=<payload>.<sig>`, payload `hmac(addr)|nonce|exp` with `exp` 3 days, signed
     with `BUDDY_FREE_SECRET`.
- **`POST /buddy/free-check/redeem`** (called by new code in the Citation Gap upload page, which then removes `free`
  from the address bar with `history.replaceState`; the page keeps `Referrer-Policy: same-origin`):
  - Checks the signature and expiry, then claims the nonce with `put(nonce, token, skip_if_exists=True)`. A repeat
    call with the same link returns the same token, so a reload never loses the check and a link never mints two.
  - Mints an entry shaped like a paid one: `session_id` `buddy-free:<nonce>`, `tokens [token]`,
    `product_key "citation-gap"`, `product_cfg` copied from `PAID_PRODUCTS["citation-gap"]`, `email` the address,
    `amount_paid 0`, `source "buddy-free"`, `redeemed true`, `consumed_tokens []`, `created_at` now, `expires_at` now
    plus 7 days (the token TTL wins over the 3-day link once redeemed). Writes `paper_token_index_dict[token]`.
  - **Cost ceiling:** `_order_cost_ceiling()` gains a branch for `source == "buddy-free"` that returns $0.60. A test
    fails if a free entry ever gets `None`.
- **Paid-buyer paths skip free entries:** lifecycle and win-back email, the sweeps, `_purchases_waiting`, the stats
  revenue count and the referral credit all check `source != "buddy-free"`. One test per path.
- **Upsell:** when `entry["source"] == "buddy-free"` (carried into `_start_adjacent`), the result page and the
  delivery email add one line: "Paper Review checks the whole manuscript, from $9." with a tagged link.
- **Worst case:** 3 free checks a day at the $0.60 ceiling is $1.80 a day; with chat at $1.50 the worst day is $3.30
  and the worst month about $60 (chat capped at $30 a month).

### 7. Measurement and privacy

- Events through `plTrack` (stored, not count-only; names match `TYPE_RE`): `chat_open` (meta: page path),
  `chat_message` (no text), `chat_offer` (meta: `free_check`, `app_fit` or `latex`), `free_check_requested`,
  `free_check_redeemed`. Each is added to `track.mjs`'s allow list with a test.
- The matched-order count joins `free_check_dict` (HMAC of the canonical address) with paid orders' emails by the
  same HMAC, in a small `scripts/buddy_report.py`.
- One `log_change.py` entry on the day it ships.
- Privacy policy, new "Chat" paragraph: chat messages and uploaded PDFs are sent to Anthropic through our server;
  Buddy's last replies are held for an hour to keep the conversation going; request logs at Modal and Anthropic hold
  message text for their normal retention; for free checks we keep an HMAC of the email, not the address, plus the
  address on the order record for 7 days.

## Build order

1. Static mock page (no server): Buddy SVG, panel, both themes, reduced motion and transparency, phone. Screenshots
   to Ben before going on.
2. Sounds: extract, encode, Web Audio player, toggle.
3. `/buddy/status` and `/buddy/chat`: flag, caps, spend reservation, facts block and its stale check, link allow list;
   tests for caps, forged turns, hostile links and fail-closed.
4. `/buddy/free-check` and redeem: canonicalization, atomic claims, entry shape, cost ceiling, the paid-path guards,
   upload-page code; tests for each.
5. `with_chat()` in `apply_layout.py`, analytics events, privacy paragraph, `log_change.py`, CI tests, PR. Ben
   creates `buddy-web`, `buddy-anthropic-secret` and `BUDDY_FREE_SECRET` before the backend deploy.

## Decisions (Ben, 2026-11-02, and later)

1. **Look:** token-built glass as in section 2 (not the full "crystal" look, not a solid panel).
2. **Sounds:** on once the chat is open, the visitor's own typing only; Buddy's replies are silent.
3. **Phasing:** chat and free check together, on the paper-tool and Mac-app pages first.
4. **Caps:** 3 free checks a day globally, chat $1.50 a day and $30 a month.
5. **Pages (2026-11-03):** "Everywhere except checkout". The launcher goes from 18 paper-tool and Mac-app pages to
   398 of the 417 pages `apply_layout.py` stamps: the homepage, every product page (Née and GlobePin among them), the
   guides, the converters and other free tools, the blog, the games, the latex-errors pages and the localized pages.
   The 19 without it are the success, upload, recover and account pages. Checks made for this change:
   - **Caps stay as they are.** Over the 28 days to 2026-11-02 the whole site averaged 90 visitors a day (peak 212 on
     2026-11-02). A turn costs about $0.0027 uncached, so $1.50 a day is about 550 messages and $30 a month about
     11,000 (370 a day). If 5% of all visitors opened the chat and sent 5 messages each, an average day is about 22
     messages ($0.06) and the peak day about 53 ($0.14). The daily cap trips only on a day near ten times the peak
     at that rate, and it is the guard meant for that day. The free check's 3-a-day cap bounds its cost whatever the
     audience. After a week, read the real spend (product `buddy-chat` on the cost dashboard) and the `chat_message` events, and
     raise caps only on that evidence.
   - **Page speed:** the launcher is one deferred 1.1 KB script; `chat.css` moved out of `<head>` into the loader
     (Chrome reports both as non-blocking), and `chat.js` loads only on the first click.
   - **In-browser tools:** the launcher binds only its own button. The converters' and the metadata cleaner's
     document-level paste handlers ignore text inputs, so pasting into the chat cannot start a conversion; a PNG to
     JPG run with the launcher on the page converted as before. The games' achievement toast shared the corner and
     now sits above the launcher (`chat.css`).
   - **Embeds:** one sitewide CSP and no page-level policy; the only third-party frame (Focus Radio's YouTube
     player) is inline and unaffected. AdSense auto-ads load on 138 of these pages; whether a mobile anchor ad is on
     is a console setting, so look at a guide on a phone once ads serve.

## As built (2026-11-02), where it differs from the sections above

- **One Modal secret, `buddy-secret`,** holds `BUDDY_ANTHROPIC_API_KEY` (the `buddy-web` key) and `BUDDY_FREE_SECRET`
  (signs free-check links and form stamps, and keys the email hashes). It is mounted on the web function only.
- **The `buddy-web` key lives in its own Console workspace** with a monthly spend limit; the Default workspace cannot
  carry limits (research pass, below). The server caps stay as the first line.
- **Replies are screened in code** (`buddy.screen_reply`): a canary string in the system prompt, any link off
  purplelink.llc, any email address other than Ben's, or a reply over 1,500 characters becomes a fixed error line.
- **`/buddy/status` is a POST**, because the web app's CORS allows POST and OPTIONS only.
- **Facts block:** `backend/latextools/buddy_build.py` copies all of `site/llms.txt` into
  `backend/latextools/buddy_facts.py` (the Modal image bundles Python sources only). Since 2026-11-04 that file is
  build output and git-ignored: `backend/app.py` writes it whenever it runs locally (every `modal deploy`, every test
  run), so facts always match the llms.txt being deployed. `scripts/build_buddy_assets.py` writes it too and writes
  `site/buddy-chat/links.json` from `site/sitemap.xml`; `test_generated_assets_are_current` fails when either is stale.
  At about 24,000 tokens and Haiku's $0.10 per million, an uncached turn costs about $0.0025.
- **The "send me product news" box was dropped** from the free-check form until it is wired to the double opt-in.
- **Free-check caps use atomic slots** (`take_slot`, put-if-absent on numbered keys) and an atomic per-address claim.
  Modal Dict entries expire after 7 days with no reads or writes, so each `claim:` key also has a durable copy on the
  `paper-review-durable` Volume (`_buddy_claims()`, `latextools/durable_dict.py`, PR 533 and its follow-up): "one per
  inbox" holds for good. The Dict's put-if-absent still decides between racing requests. The global 3-a-day cap is
  what bounds cost.
- **Disposable mail:** a short list of the common services in `latextools/buddy_disposable.py`, not the full list.
- **Kill switch:** `scripts/buddy_flag.py off|on|status`. At half the daily cap the server emails Ben once.
- **Deploy order:** Ben creates the workspace, key and `buddy-secret`; then `bash scripts/deploy.sh --backend`; only
  then may the site change publish, or the launcher would talk to routes that do not exist yet.

## Guard rails, second pass (Ben, 2026-11-02: "double down on guard rails")

- **Proof-of-work sessions.** `/buddy/status` hands out a signed challenge; the browser finds a nonce whose
  sha256 has 19 leading zero bits (0.1 to 1.2 s measured in the app's browser) and trades it at `/buddy/session` for
  a signed one-hour session. Each challenge works once (put-if-absent), and an address gets 15 sessions a day. The
  session id is the conversation key, so a client can no longer pick conversation ids to reset the 20-turn limit.
  This is the self-hosted challenge the research pass named (ALTCHA-style), with no third-party script.
- **Strikes.** A visitor message that matches the paper tools' injection patterns (`safety.sanitize_user_text`), a
  reply that fails the screen, or an off-topic refusal (the model starts those with a fixed sentence) is a strike.
  Three strikes in a UTC day close the chat and the free check for that address until the next day.
- **No deals in replies.** A reply that mentions coupons, promo or discount codes, vouchers, "N% off", a free licence,
  key, copy, Suite or upgrade becomes a fixed line; so does a reply with more than one code block or 25 lines.
- **Global cap.** 3,000 chat messages a day site-wide, besides the spend caps.
- **Tighter prompt.** No personas, no rule changes, no stories or games, no code beyond a few LaTeX lines.

## Research pass: keeping it locked down (2026-11-02)

A Sonnet research agent checked the design against OWASP's Top 10 for LLM Applications (2025), Anthropic's
guardrail and usage-policy pages, Modal's Dict reference and Cloudflare's Turnstile CSP page. Taken into the build:
the dedicated workspace with a spend limit (LLM10), server-held assistant turns (LLM01), text-only rendering with a
link allow list (LLM05), a canary and output screen (LLM07), facts-only answers with a fixed refusal (LLM09),
atomic put-if-absent caps, the AI disclosure in the panel header (Anthropic usage policy, California's bot
disclosure law, EU AI Act Article 50) and the privacy paragraphs. Deferred: a self-hosted proof-of-work challenge
(ALTCHA, MIT) in place of the form stamp if bots get through, Turnstile (needs a CSP exception), a classifier
pre-screen, and the full CC0 disposable-domain list.

## Review log (2026-11-02)

Three Sonnet Goldfish reviewers read v1 with no other context.

- **Design (10 findings, 2 blockers).** Fixed: free tokens had no cost ceiling (now $0.60, with a test); counters were
  not atomic (atomic `put(..., skip_if_exists=True)` claims, spend reserved before the call); forged assistant turns
  (server keeps Buddy's replies); email farming (canonicalization, disposable list, HMAC key); redeem idempotency and
  the reverse index; free entries leaking into lifecycle email and revenue (guards on each path); link allow list
  rules; slow kill switch (runtime flag); shared key (separate `buddy-web` key); unsalted hash (HMAC); privacy text.
  Deferred: Turnstile, because it needs a new third-party origin.
- **Implementation readiness (10 findings, 3 blockers).** Fixed: exact token entry shape; `_enforce_rate_limit`
  limit parameter; facts block generation and delivery; `apply_layout.py` step and allow list; spend pricing source;
  form fields, secret names and email template; exact metric join; event names and allow list; `wrap_user_content`
  signature and tag; upload-page code; Paper Review price ($9).
- **Scope (8 findings).** Fixed: success measure is now counts with a written target; caps lowered to a worst month
  near $60; pages limited to paper-tool and Mac-app pages; fake typing delay removed; every loop gated by reduced
  motion; plain copy instead of mascot lines; data use stated next to the email field. Left to Ben as decisions 1-3:
  cutting the glass, the sounds and the chat itself for a first test, because Ben asked for them.

## Conversion pass (v2, 2026-11-04)

Ben asked for a review of the peer-reviewed literature on site chatbots and conversion, then approved acting on it
("Go ahead implement your findings accordingly, I approve"). v1 of this section went to three Sonnet Goldfish
reviewers (design, implementation readiness, scope); the review log is at the end of the section.

What the evidence says, and how much weight each piece carries:

- **Disclosure costs sales through perceived competence.** Disclosing a bot before an outbound sales call cut
  purchases about 80%, because customers judged it less knowledgeable and less empathetic (Luo, Tong, Fang and Qu,
  *Marketing Science* 2019, a field experiment; outbound calls, not inbound site chat, so the transfer is an
  assumption). Disclosure stays (Anthropic usage policy, California's bot law, EU AI Act Article 50). Wording it to
  name where the answers come from is a hypothesis drawn from that mechanism, not a tested finding.
- **Human-like framing raises expectations the bot then misses**, and telling people what it cannot do removes the
  penalty (Crolic, Thomaz, Hadi and Stephen, *Journal of Marketing* 2022). In a field experiment a moderately
  human-like bot (humor, delays, a name) converted worse than a plain one (Schanke, Burtch and Ray, *Information
  Systems Research* 2021). Buddy keeps its pup face and name (Ben asked for them), but no humor, persona or fake
  delays, and the opening line now states a limit.
- **Pre-sale questions are where a chat lifts conversion.** A pre-sale chatbot raised conversion 21.7% against no
  chat in randomized field experiments, through more buyers rather than bigger carts (Fang, Yuan, Zhang, Donati and
  Sarvary, CESifo working paper 2026; not yet peer-reviewed).
- **Proactive pop-ups**: scenario studies only; not adopted. **A visible typing state** reduces the latency penalty
  (already there: "Buddy is thinking" and the glancing eyes). **A route to a human** helps in survey evidence (already
  there: "Write to Ben").
- **Novelty fades** for one-off purchases (*Journal of Retailing and Consumer Services* 2025, a field experiment).

### 1. Wording (`site/buddy-chat/chat.js`)

- Header note: "AI answers from what's on this site. It can be wrong." followed by the existing "Write to Ben" link
  (was "AI, can be wrong.").
- Opening line: "I answer questions about our Mac apps and paper tools from what's on this site, and I can run a free
  Citation Gap check on a paper draft. I can't give discounts or look up an order." (was "Ask me about our Mac apps
  or paper tools. I can also run a free Citation Gap check on a paper draft.")
- Neither string is repeated in the facts block or the server prompt; no test pinned the old ones.

### 2. Pre-sale buttons on the paid Mac-app pages (`site/buddy-chat/chat.js`)

- `APPS` maps the page's first path segment, after dropping a locale prefix (`de`, `fr`, `ja`, `pt-br`, `zh-cn`), to
  a display name: moderntex ModernTex, outbound-veil Outbound Veil, legroom Legroom, keyfeel Keyfeel, tapefolio
  Tapefolio, panely Panely, summonly Summonly, lenscrib Lenscrib, nee Née, suite the Mac Suite.
- On those pages the buttons are "What does <name> cost?", "How does the free trial work?", "Which Macs does it run
  on?" and "Free citation check" (kept, so the free-check entry point stays on the pages it started on). They track
  `chat_offer` with `price`, `trial`, `macs` and `free_check`. The first three are sent as visitor messages, so they
  count toward the per-IP and spend caps like typed ones.
- Every other page keeps the current three buttons.
- The "no deals" screen (`screen_reply`) is tested against honest price and trial answers ("one-time license key",
  "free 7-day trial", "updates are free") so they are not replaced by the fixed line.
- The buttons do not depend on any experiment arm, so they change the ModernTex hero test's level (more questions on
  `/moderntex/` in both arms) but not its comparison. That date goes into the change log.

### 3. Holdout from 2026-12-28 (Ben, 2026-11-04: "yes, start the holdout on 12-28")

Built in v2's plan and shipped dormant; it switches itself on at 00:00 UTC on 2026-12-28.

- **Switch:** `site/buddy-chat/loader.js` holds `START = "2026-12-28"` and a 56-day `SCHEDULE` (to 2027-02-21). On
  A days it returns before adding the stylesheet or the launcher; on B days, outside the window, with a malformed
  schedule or on any error in the schedule code it draws the chat as before. The arm is read once per page load from
  the UTC date and written to `<html data-exp-buddy-chat>` ("A", "B", "off"); nothing is sent or stored.
- **Draw:** `scripts/draw_buddy_schedule.py`: days 1+2, 3+4, ... are pairs, one `random.Random(seed)` coin per pair
  (`rng.random() < 0.5` puts B first), seeds from 20261228 up, first draw with 3 to 5 B days on every UTC weekday.
  Seed 20261228 (the first tried) met it: B days Mon..Sun 3, 5, 3, 5, 5, 3, 4. `--check` fails if the loader holds
  anything else; a site test runs it (an all-B schedule, meaning stopped, also passes).
- **Data:** `stats.mjs` adds `appPageviews` and `appConversions` to each `byDay` row: views of the ten Mac-app pages
  (localized ModernTex included, success and buy pages excluded), and trial downloads plus checkout clicks made on
  those pages (a "send to my Mac" pointer click, meta ending `-not-mac`, is not a conversion). The daily dashboard
  archives every numeric `byDay` field into `history.json`, so the series builds itself from the next build on.
- **Read-out:** `scripts/buddy_holdout_report.py` pairs each A day with its B day, takes B minus A of
  appConversions / appPageviews per pair, and reports the mean with a two-sided sign-flip randomization test. The
  rule: "remove or rethink" only if B is lower with p < 0.05; otherwise keep Buddy. A lift is reported, not
  required. Review date: 2027-02-22.
- **What it compares** is the whole chat (launcher, wording, buttons) against no chat. The 20% coupon Ben asked for
  on 2026-11-04 would, if it starts inside the window, become part of the B arm from that day; the coupon design
  says how that is handled.
- **Stop or keep for good:** set `SCHEDULE` to all `B`. Tests: `netlify/tests/buddy-holdout.test.mjs` (every day of
  the window, UTC boundaries, fallbacks, all-B), `netlify/tests/stats-buddy-holdout.test.mjs`, and the schedule and
  report tests in `site-tests/test_buddy_chat_pages.py`.

### Review log, conversion pass

- **Scope:** the holdout was disproportionate at this traffic and overlapped two tests (deferred, section 3); the
  wording changes are hypotheses (now labelled); the opening line was long (two sentences); keep the original
  redemption target (kept).
- **Implementation readiness:** the schedule draw, loader error paths, dashboard pickup and tests were unspecified
  (moot for now: the holdout is deferred and will be specified in full before it starts); the button strings, name
  table, locale handling and tracking values are now exact (section 2).
- **Design:** the free-check button would have vanished from the Mac-app pages (kept as a fourth button); "Will it
  run on my Mac?" cannot be answered (now "Which Macs does it run on?"); "from our product pages" was inaccurate (now
  "what's on this site"); "support for an order" contradicted the LaTeX button (now "look up an order"); the deals
  screen could hit honest answers (now tested); localized pages lost the buttons (locale prefix dropped); the Luo
  transfer and the kept avatar are now stated plainly.
