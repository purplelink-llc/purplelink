# Design: Undershelf waitlist sign-up

Status: revision 2 after Goldfish review (codebase accuracy, design, comprehension), 2026-11-01. Waiting for Ben's
approval. Branch: `undershelf-waitlist` (not pushed).

## 1. Purpose and scope

Undershelf is a printed under-desk mount for the Mac mini that Purplelink is considering selling. Before spending on a
printer or stock, a **demand test** runs: the page `site/undershelf/` (already drafted on this branch) collects
waitlist sign-ups for 14 days from the first announcement to Purplelink's own audience, and the count decides what
happens next.

**Stop rule** (full version in the private brief `docs/growth-briefs/undershelf-waitlist-stop-rule-2026-11-01.md`):
confirmed sign-ups in the 14 days decide.

| Confirmed sign-ups | Decision |
|---|---|
| Fewer than 15 | Stop. Delete the list, archive the page. |
| 15 to 39 | One more test step (a hang test and a temperature run published), then decide again at 40. |
| 40 or more | Go: buy a printer, make 10 units, offer them to the list first. |

The test's start and end dates are written into the brief and into this doc's section 4.6 on the day of the first
announcement.

**This design covers** the sign-up function, confirmation, unsubscribe, storage, the count for the decision, retention
and deletion, the launch-email data path, and tests. **Out of scope:** payment or pre-orders, the launch email's
wording, any public count.

**Terms.**
- **Double opt-in:** nothing is stored until the person clicks a link in a confirmation email.
- **Resend:** the email provider the site already sends with.
- **Blobs:** Netlify's key-value storage.
- **`SUBSCRIBE_SECRET`:** the existing secret that signs confirmation links.
- **Version:** the reader's choice on the form: `standard` (PETG, about $29), `carbon` (PET-CF with walnut, about
  $49) or `unsure`.
- **Honeypot:** a hidden field named `website`. People leave it empty; bots fill it in.

## 2. Requirements

1. Store nothing until the address confirms.
2. Keep only what the test needs: email, version, the page path, the visit's `utm_content` if any, and the confirmed
   time.
3. Send one confirmation email. After that, nothing until the launch email, then delete the list. Hard deletion
   date: test end plus 60 days, launch or not.
4. Every email can be unsubscribed from with one click (RFC 8058). An unsubscribed address is never mailed again,
   even if it signs up later without confirming.
5. Abuse limits per IP and per address per day. Responses never reveal whether an address is on the list.
6. The decision needs the confirmed count, the count per version and the count per `utm_content`.
7. No change in behaviour for the three existing lists: the Daily Digest (retired), the researcher checklist and
   the RubbleFront list.

## 3. Options

**A. A new function, reusing the shared library pieces.**
- Add `netlify/functions/undershelf-waitlist.mjs`, plus one token kind in `confirm-signup.mjs`.
- Reuse `netlify/lib/confirm-token.mjs`, `netlify/lib/ratelimit.mjs` (`clientIp`, `overDailyLimit`),
  `netlify/lib/fn-page.mjs` (`page`, `escapeHtml`) and `netlify/lib/auth.mjs` (`bearerMatches`).
- Copy only the Resend send and the origin check, about 60 lines, from `checklist-signup.mjs`, where those are local
  functions.
- For: the live lists are untouched apart from three small changes to `confirm-signup.mjs`.
- Against: some copied code.

**B. Generalise the researcher-checklist function** into one module for every list.
- For: one place for this logic.
- Against: it changes a live list to run a 14-day test, and RubbleFront already has its own module.

**Decision: A.** Revisit B only if the test leads to a product line with its own lists.

## 4. Design

### 4.1 Files

| File | Change |
|---|---|
| `netlify/functions/undershelf-waitlist.mjs` | Create |
| `netlify/functions/confirm-signup.mjs` | Modify: third token kind, its page text, its completion branch |
| `site/undershelf/undershelf.js` | Modify: send `utm`; one success message whatever the server says |
| `site/privacy/index.html` | Modify: one paragraph (4.6) |
| `scripts/undershelf_list.py` | Create: on-demand counts and the launch send, run on Ben's Mac with a Blobs API token |
| `netlify/tests/undershelf-waitlist.test.mjs` | Create |

### 4.2 Sign-up request

`POST /.netlify/functions/undershelf-waitlist`. The JSON body is `{ email, version, website, page, utm }`.
`OPTIONS` gets the same CORS answer as the checklist function; any other method gets 405.

| Check, in order | Response |
|---|---|
| `Origin` present and not purplelink.llc, www, or a Netlify preview of this site | 403 `forbidden_origin` |
| Body is not JSON | 400 `invalid_json` |
| Honeypot filled | 200 `{ ok: true }`; nothing sent |
| Email fails the site's email pattern (the one in `checklist-signup.mjs`) | 400 `invalid_email` |
| Over 20 a day for this IP, or 3 a day for this address (`overDailyLimit`, prefix `undershelf`) | 429 `rate_limited` |
| The address is on the suppression list or already confirmed | 200 `{ ok: true }`; nothing sent |
| Otherwise | sign the token, send the confirmation email, 200 `{ ok: true }` |
| Resend refuses | 502 `send_failed` |

- **Server-side cleaning:** a `version` outside the three values becomes `unsure`; a `utm` that doesn't match
  `^[a-z0-9_-]{0,64}$` becomes empty; `page` must start with `/` and is cut to 120 characters.
- **No-reveal responses:** every accepted request gets the same `{ ok: true }`, so the response never tells anyone
  whether an address is on the list.
- **Rate-limit store down:** `overDailyLimit` fails open. That is accepted for a waitlist, and the test sets it to
  fail open on purpose.
- **Spoofable IP:** `clientIp` falls back to `x-forwarded-for` when Netlify's header is missing. Accepted at this
  scale.
- **Counter race:** the counter is read and then written, not atomic. Accepted at this scale.

**Page script.** `undershelf.js` reads `utm_content` from the landing URL into `sessionStorage`
(key `pl_undershelf_utm`) on the guide and the waitlist page, and sends it as `utm`. On `{ ok: true }` it shows
"Check your email and click the link to confirm." It never says "already on the list".

### 4.3 Confirmation (`confirm-signup.mjs`)

- New token kind `undershelf-confirm` in `confirm-token.mjs`.
  - Payload: `{ e: email, v: version, p: page, u: utm }`.
  - Expiry: 3 days. Signed with `SUBSCRIBE_SECRET`.
  - The kind is part of the signature, so this token can't be used as a digest or checklist confirmation.
- `identify()` gains a third branch after the checklist one.
- The `what` and button text become a three-way choice ("the Undershelf waitlist").
- POST calls `completeUndershelfSignup(email, version, page, utm)`, exported from the new function file, the same
  way the checklist's completion is imported today.
  - It writes the record unless the address is suppressed.
  - It sends no email.
  - Confirming twice changes nothing and shows the same success page.
- Success page text: "You're on the Undershelf waitlist. One email when it's ready to order, and then this list is
  deleted."
- An expired link gets the existing "past that or not valid" page, with a link back to `/undershelf/`.

### 4.4 Storage (Blobs)

| Store | Key | Value |
|---|---|---|
| `undershelf-waitlist` | lowercase email | `{ email, version, page, utm, confirmedAt }` |
| `undershelf-suppressed` | hex SHA-256 of the lowercase email | `{ at }` (no address kept) |
| `rate-limits` | the shared store, with the `undershelf` prefix so counts are not shared with other lists | |

There is no unsubscribe-token store. The unsubscribe token is
`HMAC-SHA256(SUBSCRIBE_SECRET, "undershelf-unsub:" + email)`, so it needs no lookup. It also works from the
confirmation email before any record exists: it adds the suppression entry anyway.

### 4.5 Unsubscribe

- **GET `?u=<token>&e=<email>`** shows a page with one button and changes nothing, so link scanners can't
  unsubscribe anyone.
- **POST** (the button, or RFC 8058 one-click with `List-Unsubscribe=One-Click`) checks the HMAC, deletes the
  record and writes the suppression entry. A wrong token gets a neutral page.
- Both emails carry `List-Unsubscribe` and `List-Unsubscribe-Post` headers, and a postal-address line like the
  checklist email ("Purplelink LLC, Atlanta, Georgia").

### 4.6 Counts, launch email, retention

- **Counts.** `scripts/undershelf_list.py counts` reads the store with a Blobs API token on Ben's Mac. It prints
  the confirmed total, the count per version and the count per `utm_content`. No web endpoint exposes these, so no
  public URL ever returns addresses or counts. The dashboard can run the script daily if Ben wants a tile.
- **Launch email.** `scripts/undershelf_list.py send --dry-run`, then a real run, sends one Resend email per
  recipient. Each email carries its own unsubscribe link and headers, and suppressed addresses are skipped. Then
  `scripts/undershelf_list.py purge` deletes the list. The suppression store stays, holding hashes only.
- **Retention.** The list is purged after the launch send, or 7 days after a stop decision, and in any case by the
  test end plus 60 days. Ben writes that date into the brief and a calendar item when the test starts.
- **Resend logs** keep recipient addresses for the plan's log period. The privacy line says so.
- **Privacy policy paragraph:** "Undershelf waitlist: if you join, we keep your email address and the version you
  chose until we send one email when it is ready to order, then delete them, and in any case within 60 days of
  the test ending. Unsubscribing deletes them at once. Our email provider keeps delivery logs for a limited time."
- **Decided:** a stopped test is deleted quietly, with no "not going ahead" email. The confirmation email is one
  sentence and a link.

### 4.7 Emails

- **Sender:** `Purplelink LLC <orders@purplelink.llc>`, reply-to `ben@purplelink.llc`, the existing sender.
- **Confirmation subject:** "Confirm your place on the Undershelf waitlist".
- **Format:** plain text plus a simple HTML version, one link, no images.

### 4.8 Accepted risk

Disposable inboxes can confirm and inflate the count. For a 14-day test sent only to our own audience this is
accepted. If the count looks odd, the counts script also reports the number of distinct email domains.

## 5. Tests

`netlify/tests/undershelf-waitlist.test.mjs`. It reuses the Blobs and fetch mocks from `confirm-signup.test.mjs`
and runs with `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`.

- Each row of the 4.2 table, including the honeypot and the identical success response.
- Cleaning of `version`, `utm` and `page`.
- The token round trip, a wrong kind rejected, and expiry.
- Nothing stored before confirmation; confirming twice is idempotent; a suppressed address is never stored.
- Unsubscribe: GET changes nothing; POST deletes and suppresses; a wrong token is harmless; it works before
  confirmation.
- Regression: digest and checklist confirmations still work and show their own text.

## 6. Open trade-offs for Ben

1. **Option A** (a new function reusing library pieces) or **option B** (one generic list module now).
   Recommendation: A.
2. **Counts on demand or on the dashboard.** The script runs on demand either way. Should the dashboard collector
   run it daily for a tile? Recommendation: on demand. It's a 14-day test.
3. **Keep the `utm_content` tracking?** It answers which announcement brought sign-ups, at the cost of one script
   change and one cleaned field. Recommendation: keep it.
