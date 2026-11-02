# Send to my Mac: email capture for non-Mac visitors on the Mac-app pages

Status: reviewed (EGM Goldfish review, five Sonnet reviewers, 2026-11-02) and built in the same change. Owner: Ben.
First page: `/moderntex/`. The review log is at the end.

## Concepts brief

**Problem.** The ModernTex Reddit ads bring many visitors who are not on a Mac. On one ad only 9% of visitors were on
a Mac. ModernTex is Mac-only, so for the rest the page's main action (a `.dmg` download) leads nowhere. Before this
change the only help was hidden: if a phone or PC visitor clicked the trial button, `site/site.js` cancelled the
download and revealed the trial-email form with Mac wording. Nothing on the page said so before the click.

**Hypothesis.** A plain offer shown up front to visitors who are clearly not on a Mac ("On Windows or a phone?
ModernTex runs on a Mac, so I can email you the download link to open there.") turns some of those visits into a trial
started later on the Mac. The funnel for an ad then reads visit, send-to-Mac, trial, order.

**Success measure.** Read after 28 days from the first scheduled build that publishes it, on `paid:reddit`:
- `send_to_mac` events per non-Mac ModernTex pageview (the `os` field on pageviews gives the denominator);
- `trial_download` events with meta `moderntex-s2m` (trials on a Mac whose first touch was the email);
- orders whose first-touch campaign (`attr_first` in Stripe) is `send-to-mac`.

Keep the block if at least one `moderntex-s2m` trial arrives per 20 sends. Remove it (one line in `PAGES`) if there
are fewer than 10 sends in the 28 days, or no `moderntex-s2m` trial at all.

**What the visitor gets.** One email with the ModernTex page link and the trial terms. If they also tick the unticked
news box, the same email carries a confirm link; nothing is stored unless they press Confirm.

**Boundaries.** Mac visitors see the page exactly as before. With JavaScript off, the page is exactly as before. The
block is one shared include: Legroom, Outbound Veil, Keyfeel, Tapefolio and the other Mac-app pages turn it on with one
`PAGES` entry and one email template. Only ModernTex is on in this change.

## What existed before (and what this change touches)

- `site/site.js`, "ModernTex trial": on a non-Mac (UA test, iPad told apart by touch points), a click on a
  `moderntex-download?trial=1` link is cancelled and the nearest `[data-trial-signup]` form is shown with Mac copy and
  a "Download it here anyway" link. The form posts to the Modal backend (`/lifecycle/trial`, a three-email sequence).
- `site/analytics.js` counts `trial_download` on every trial-link click in a capture-phase listener on `document`, and
  `site/reddit-pixel.js` fires Reddit `Lead` the same way (only for visitors who qualify for the pixel: first arrival
  from a Reddit ad, no Do Not Track). Both run before `site.js` cancels the click, so a cancelled non-Mac click counted
  as a trial download and, for Reddit-ad visitors, a Lead; a following "anyway" click counted again.
- `netlify/lib/trial-reminder.mjs`: the Mac-app trial-email engine (Resend, sender `Benjamin Ampel
  <orders@purplelink.llc>`, reply-to `ben@purplelink.llc`, origin check, `website` honeypot, hashed per-day counters in
  the `rate-limits` Blobs store). Its helpers are private to a closure; only `SITE_ORIGIN` and `POSTAL_ADDRESS` are
  exported and reused here.
- `netlify/lib/confirm-token.mjs` and `netlify/functions/confirm-signup.mjs`: stateless double opt-in (a signed,
  3-day link; a GET shows a button, only the POST stores). Used by the checklist and the Undershelf waitlist.
- `scripts/apply_support_box.py`: the site's include mechanism for static pages (one markup definition stamped between
  markers, `--check` in site-tests).
- `netlify/functions/track.mjs` and `stats.mjs`: first-party events. Funnel events (the `FUNNEL` regex in
  `analytics.js`) carry the first-touch channel `ft` and link tag `fc`; the server adds `os`, the OS family read from
  the User-Agent. `stats.mjs` returns `funnelByChannel` and `funnelByContent`.
- `netlify/lib/attr-cookie.mjs`: the trial link carries `ach`, `arc`, `atg`, `ad`; the download turns them into the
  first-party `pl_attr` cookie, and `reddit-capi.mjs` reports a later ModernTex purchase to Reddit with the click id.
- Two running experiments on `/moderntex/`: `site/exp-moderntex-hero.js` (2026-10-19 to 2026-12-13; metric
  `trial_download` per ModernTex pageview by day) and `site/exp-trial-link.js` (header "Free trial" link).

## Goals and non-goals

Goals:
1. Visitors clearly not on macOS see the offer in the hero at first paint, with no layout shift, in both hero arms.
2. One transactional email per request from a fixed template and the existing Resend sender; it cannot carry
   anything a visitor writes except the recipient address.
3. Store nothing per request but hashed counters; keep an address only after its owner confirms product news.
4. A `send_to_mac` funnel event, counted as its own stage by channel and by link tag.
5. A trial or purchase made later on the Mac is credited to the same first-touch channel and Reddit ad, and trials
   started from the email can be counted on their own.
6. A trial click that the block turns into a pointer is no longer a Reddit Lead and is counted apart from real
   downloads, while the hero experiment's metric keeps its definition.

Non-goals: trial reminders for these visitors (the Mac page still offers them after the download); sending product
news (consent only, no sender exists yet); other apps; the old intercept on the guide and translated ModernTex pages.

## Design

### 1. Detection (before first paint)

`site/send-to-mac.js` is a plain `<script src>` in `<head>`, right after `theme.js` and before the stylesheets, on the
pages that carry the block. It decides once and, for a clear non-Mac, adds the class `s2m` to `<html>`; CSS shows the
block in the first paint. Order of evidence:

1. User-Agent Client Hints (`navigator.userAgentData.platform`) when present and not `"Unknown"`: `"macOS"` is a Mac,
   any other value is not.
2. The User-Agent string: `iPhone|iPad|iPod` is not a Mac; `Macintosh` with `maxTouchPoints > 1` is an iPad (iPadOS
   Safari reports a Mac UA) and not a Mac; `Macintosh` otherwise is a Mac; `Windows|Android|CrOS|Linux|X11` is not.
3. Anything else counts as a Mac: the block appears only on a clear answer. A thrown error counts as a Mac too.

Cost: one small render-blocking request on every visit to a page with the block (Mac included); it is fingerprinted
and cached under the same rules as `theme.js`, the other render-blocking head script. The alternatives (a deferred reveal, or detection at the edge) are below.

### 2. Markup and the include

`scripts/apply_send_to_mac.py` holds the one markup definition and `PAGES` (`page -> (slug, name, trial link)`). It
stamps the block between `<!-- send-to-mac:start -->` and `<!-- send-to-mac:end -->` after the hero's buttons and the
lines that belong to them (after `.buy-suite` when present, which `trial-buy-path.test.mjs` keeps directly under the
buttons), and the head tag after `theme.js`. `--check` runs in site-tests. The block:

- a `<form hidden novalidate>` labelled by its heading, so with scripting off or on a Mac it is out of view and out of
  the accessibility tree; `:root.s2m .send-to-mac[hidden] { display: block; }` shows it, and the script then removes
  the attribute;
- a visible label "Your email", an email input described by the note and the status;
- the honeypot inside a `display: none` wrapper (out of the accessibility tree and the tab order);
- an unticked checkbox "Also send me news about new Purplelink apps, a few emails a year at most.";
- a note: "One email with the link and the trial terms. Your address is not kept. The news box sends a confirm link
  first, and only a confirmed address is kept.";
- a status paragraph with `role="status"` and `aria-live="polite"`;
- "Download the disk image here anyway" with the real trial `href` in the markup, and a Privacy link.

### 3. Look

Reuses `.trial-remind-row` and `.trial-remind-note` (pill input with the `--field-line` border, which meets 3:1 in both
themes; purple focus ring; muted note). New rules only for the container (same panel and border as the trial form),
the label, the 44px checkbox row, the status colour, `aria-invalid` (`--danger`) and `aria-disabled`. All colours are
tokens, so dark (the default) and light both follow without theme-gated rules. Arm B of the hero experiment flattens
the hero copy and orders each child (`site/buy.css`); the block gets `order: 5` there, after the Suite sentence.

### 4. Behaviour

- Submit with a malformed address: `aria-invalid="true"` on the field, a status message, focus back on the field.
- Sending: the button gets `aria-disabled` (not `disabled`, so focus stays), status "Sending…".
- 200: status "Sent. Open the email on your Mac. If it is not in your inbox in a few minutes, look in spam." (plus a
  line about the confirm link when the box was ticked); the field becomes read-only; focus does not move, the status
  region announces. Then `plTrack("send_to_mac", product)`.
- 429: "This network has asked several times today. Try again tomorrow, or email ben@purplelink.llc." Any other
  failure (400, 502, 503, network): "That did not go through. Try again in a minute, or email ben@purplelink.llc."
- The request body is `{ email, product, news, website, ft, fc, rdt }`; `ft fc rdt` come from
  `window.plAttribution()` in `analytics.js`, which does not exist under Do Not Track, so those visitors send empty
  values and their link carries no channel.
- Trial links on the page (`*-download?trial=1` or `?download=1`, except the block's own "anyway" link) get
  `data-s2m-intercept="1"`. A click is cancelled and focus moves to the email field, which is in the hero. `site.js`
  skips its old intercept for these links. `reddit-pixel.js` fires no Lead for them. `analytics.js` still sends
  `trial_download`, with meta `moderntex-not-mac`, and does not tag the link.

### 5. The function: `netlify/functions/send-to-mac.mjs`

Contract (the file header has the full list of answers):
- `POST` JSON at most 2 KB `{ email, product, news?, website?, ft?, fc?, rdt? }` answers 200, or 400
  `invalid_json | invalid_email | invalid_product`, 403 `forbidden_origin`, 413, 429 `rate_limited`, 502
  `send_failed`, 503 `unavailable`.
- `GET ?u=<hmac>&e=<email>` shows a page with one "Stop product news" button; `POST` to the same URL deletes the
  record (RFC 8058 one-click too). A GET never deletes, so link-scanning mail filters cannot unsubscribe anyone.

Order of checks:
1. Origin: required, and it must be purplelink.llc, www, or the deploy's own URL. Browsers send Origin on every POST,
   so only scripts are refused here.
2. Size, then JSON shape.
3. Honeypot: a filled `website` answers 200 before any counter is touched.
4. Validation: trimmed address of at most 254 characters, no control characters, the trial emails' pattern; `product`
   must be an own key of `PRODUCTS`; `news` counts only when it is exactly `true`.
5. Counters, per UTC day, keys `sha256(value)[:16]`. Per IP: 5, answering 429. Per lowercase address: 2, answering a
   silent 200 with nothing sent, so the answer never tells anyone whether an address was used. All sends: 150,
   answering 429. Each counter is incremented as it passes. They are a read-then-write in Blobs, so a burst can
   overshoot by the number of requests in flight; acceptable at this scale. A store error answers 503 (fail closed,
   unlike `lib/ratelimit.mjs`, which fails open for buyers).
6. Send through Resend. A failed send keeps its counts, so retries cannot hammer Resend.

Template: `PRODUCTS.moderntex.email(link)` states only what the page states. That is the full app for seven days from
first launch with no account; then $19.99 once with updates; a refund within 14 days; macOS 14 or later on Apple
silicon or Intel. It links the first-ten-minutes guide, and leaves out version and file size, which change with
releases. The footer says who asked and that nothing was kept. With news ticked, it adds the confirm link
(`confirm-signup?t=…`, kind `news-confirm`, signed with `SUBSCRIBE_SECRET`, valid 3 days). Links always point at
`https://purplelink.llc`, also when sent from a deploy preview.

Storage: none per request. On Confirm, `confirm-signup.mjs` calls `completeNewsSignup`, which writes `product-news`
(key: lowercase email; value `{ email, products, source: "send-to-mac", confirmedAt }`). The unsubscribe token is an
HMAC of the address (`product-news-unsub:` prefix), so no token store exists. The address is never logged.

### 6. Attribution across the two devices

The Mac is a new browser with no first touch, no `pl_rdt` and no `pl_attr`. The email's links carry the checked
attribution so the Mac visit starts with the same channel in `analytics.js`:

| `ft` from the page | Link query | Read back on the Mac as |
|---|---|---|
| `paid:<src>` | `utm_source=<src>&utm_medium=paid` | `paid:<src>` |
| `tool:<slug>` | `utm_source=tool-<slug>&utm_medium=send-to-mac` | `tool:<slug>` |
| another label, not `direct` | `utm_source=<label>&utm_medium=send-to-mac` | `<label>` |
| empty or `direct` | `utm_source=send-to-mac&utm_medium=email` | `send-to-mac` |

Always `utm_campaign=send-to-mac`; `utm_content=<fc>` and `rdt_cid=<rdt>` when present. `rdt_cid` on the URL loads the
Reddit pixel on the Mac (the pixel's own rule) and is stored as `pl_rdt`, so the trial link is tagged and a purchase
reaches the Conversions API with the visitor's own click id. Validation: `ft` `^[\w.\-:+/ ]{1,40}$`, `fc`
`^[\w.\-]{1,60}$`, `rdt` `^[\w.\-:=]{1,128}$`; a value that fails is dropped, never an error. The first-seen day is not
sent (less data; the Mac's own day starts the 90-day window).

Forged values: anyone can already open `/moderntex/?rdt_cid=…` with any value, so a POST here adds no new way to forge
attribution; the email only ever links purplelink.llc.

Cost: the Mac visit is a second funnel pageview for the same channel, on `os = mac`. The inflation is at most one
pageview per email opened on a Mac.

### 7. The event and the dashboard stage

- `analytics.js`: `send_to_mac` is in `FUNNEL` (carries `ft`, `fc`); `track.mjs` adds `os` as for every funnel
  event. `os` comes from the server's UA reading, so an iPad with a Mac UA records `mac`; it is not a check of the
  page's decision.
- `stats.mjs`: `totals.sendToMac`, `byDay[day].sendToMac`, and `sendToMac: { <app>: n }` in every `funnelByChannel`
  and `funnelByContent` entry (initialised, counted and returned in both maps). `trial` maps keep counting by meta, so
  `moderntex` (real downloads), `moderntex-s2m` (real, after the email) and `moderntex-not-mac` (pointer clicks, not
  downloads) stay apart; `totals.trialDownloads` still counts all three, as before, and `totals.trialNotMac` /
  `byDay[day].trialNotMac` count the pointer clicks so a reader can subtract them per day (the revenue forecast does).
- `scripts/hub/hub.py` counts a product's trials as `<app>` plus `<app>-s2m` and never `-not-mac` (`trial_count`,
  `trial_total`).
- The traffic dashboard and the Reddit cost-per-trial view are owned by the Analytics session, which is sent the
  event name, fields and trial keys. This change ships the API fields only.

### 8. Reddit pixel Lead: no

No Reddit event fires for a send. `Lead` means a trial download; the emailed link carries `rdt_cid`, so the pixel
loads on the Mac and the real download there is the Lead. A Lead at the send would count one person twice and teach
Reddit's delivery to favour phone visitors who leave an address. Pointer clicks no longer fire Lead either, which
lowers the Lead count Reddit sees on the ModernTex campaign from the day this goes live: expect a short-term rise in
reported cost per Lead that is a correction, not a change in results. A Reddit `Custom` event for sends is possible
later; not built.

### 9. Privacy policy

A paragraph `#send-to-mac` under "How we use it" says what is sent: the address, the app, the box, and how the
visitor first arrived (channel, link tag, Reddit click id). It also covers the one Resend email; that arrival details
only go into the link; that nothing is stored except hashed per-day counters; the two-a-day cap per address; and the
3-day confirm link, with storage only after Confirm and how to stop it. The ModernTex trial-email paragraph now scopes
its "in place of the download" clause to the guide and translated pages. Effective date moves to 2026-11-02.

### 10. The running experiments

- Hero switchback (`exp-moderntex-hero.js`): the block shows on both arms, so it does not bias the comparison. Its
  metric keeps its definition: pointer clicks still send `trial_download` (with a different meta), so the daily count
  is comparable before and after. The block can change how often non-Mac visitors click the trial button at all, on
  both arms alike. The analysis should also be read on `os = mac` pageviews and on the `moderntex` meta only, which
  this change leaves untouched. Arm B layout: see section 3; CLS measured 0 on a phone viewport.
- Header-link switchback (`exp-trial-link.js`): its link is a trial link, so on non-Mac visits it now points at the
  block instead of downloading, on both arms alike.
- The change is logged with `log_change.py`.

## Alternatives considered

- **Reveal from a deferred script**: shifts the hero on non-Mac visits. Rejected.
- **Detect at the edge** (Edge Function or `Vary: User-Agent`): splits the CDN cache by UA and runs a function on
  every ModernTex request. Rejected.
- **Reuse the Modal `/lifecycle/trial` sequence**: three emails and a stored address for one link. Rejected.
- **Reuse `createTrialReminder`**: it always stores the address and schedules a reminder; its helpers are private.
  Extracting them into a shared lib is a reasonable later clean-up; not done here to keep the trial emails untouched.
- **Single opt-in for news**: rejected in review for double opt-in, which already exists and stores less.
- **Drop the news box, the include, or the click-id relay** (zoom-out review): each is an explicit requirement of the
  request, so kept; see the review log.

## Risks

1. **Sending to strangers.** Fixed template, Origin required, 2 per address (silent), 5 per IP, 150 a day, fail
   closed. A botnet can still make the site send one ModernTex email to up to 150 addresses a day from
   `orders@purplelink.llc`, the sender that also carries receipts. Moving these sends to their own subdomain or Resend
   stream would isolate complaints; open trade-off.
2. **Consent before a sender exists.** Only confirmed addresses are kept; the copy promises "a few emails a year".
3. **Bots with mobile UAs** render the block; its text is accurate, so acceptable.
4. **Copy drift**: the email states only terms the page states, without version or size.

## Detailed Implementation Plan

Built in this change; each step names its test.

1. `site/send-to-mac.js`: detection, block reveal, form, trial-link pointers.
   Tests: `netlify/tests/send-to-mac-detect.test.mjs`, which covers UA-CH, UA, iPad touch points, unknown and
   throwing navigators.
2. `site/styles.css` and the `order` rule in `site/buy.css`. Tests: `site-tests/test_send_to_mac.py` checks that
   display is set only under `:root.s2m` and that the arm-B order rule exists.
3. `scripts/apply_send_to_mac.py` stamped onto `site/moderntex/index.html`. Tests: site-tests check `--check`, the
   head tag between `theme.js` and the stylesheets with no `defer`, the hidden form, the visible label, the unticked
   box, the status role, the real anyway `href`, no inline style or emoji, absence from other pages, and that `PAGES`
   matches `PRODUCTS`.
4. `site/analytics.js` (`plAttribution`, `FUNNEL`, `-not-mac` and `-s2m` metas), `site/reddit-pixel.js` (no Lead for
   pointers), `site/site.js` (skip pointers). Tests: `send-to-mac-analytics.test.mjs`, `reddit-pixel.test.mjs`.
5. `netlify/functions/send-to-mac.mjs` and the `news` kind in `confirm-signup.mjs`. Tests: `send-to-mac.test.mjs`
   covers the fixed email, honeypot, validation, origin, all three limits, fail closed, 502, news off unless exactly
   `true`, confirm GET then POST, unsubscribe GET and POST, attribution shapes, and no address in logs.
6. `netlify/functions/stats.mjs`. Tests: `track-funnel.test.mjs`, where `send_to_mac` is its own stage and pointer
   clicks are kept apart.
7. `site/privacy/index.html`.
8. Pre-PR: `fingerprint_assets.py`, then `python3 -m pytest -q site-tests` and the node tests. PR 512 made
   `search-index.json` and `llms-full.txt` build output, so they are not committed. Log the change.
9. PR, green checks, squash merge without `[deploy now]`. Then one real send to ben@purplelink.llc from a
   non-production deploy.

## Review log (EGM, 2026-11-02)

Reviewers (Sonnet, fresh context): zoom-out, comprehension, design critic, implementation readiness, codebase
details. Applied:

- Double opt-in through `confirm-token.mjs` instead of a stored single opt-in. This removed the token store and the
  pre-confirmation record.
- Origin required. The per-address cap answers silently (no enumeration). Unsubscribe deletes only on POST. The global
  cap is 150. The order of checks is defined. `fd` is dropped. `tool:` channels are mapped. The `ft` charset is wider.
- Accessibility: `role="status"` with no focus move on success, `aria-invalid`, and `aria-disabled` while sending. The
  honeypot is out of the accessibility tree. The anyway link has a real `href`.
- Arm-B layout: an `order` rule (found again in the browser: without it the block rendered above the app name).
- Experiments: pointer clicks keep `trial_download` with a `-not-mac` meta instead of disappearing, so the hero metric
  keeps its definition. `exp-trial-link.js` is named.
- Success measure and the `-s2m` trial meta, so the hypothesis can be read.
- Corrected claims: the `os` field is not a check of the detection; Lead inflation applied only to pixel-qualified
  visitors; the anyway link double-counted; all `stats.mjs` places are listed.

Contested:

- Cut the news box, the include generator and the click-id relay (zoom-out). Kept: each is an explicit requirement.
  The generator follows the existing `apply_support_box.py` pattern.
- Split the counting fix into its own PR (zoom-out). Kept together because the new block creates the pointer clicks;
  the metric definition is preserved instead (above).
- Signed page token or proof of work against scripted sends (design). Not built: Origin, the caps and fail-closed
  bound the damage at this scale. Revisit if the 150 cap is hit.
- CAPI freshness check for click ids relayed by email (design). Not needed: the relay creates no forging path that a
  plain URL does not already offer.
- Dashboard UI changes in this PR (readiness). The view belongs to the Analytics session; this PR ships the API.
