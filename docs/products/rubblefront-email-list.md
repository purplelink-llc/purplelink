# RubbleFront email list (double opt-in, on Resend)

Built 2026-10-12. Code: `netlify/lib/rubblefront-list.mjs` (shared), `netlify/functions/rubblefront-{subscribe,confirm,unsubscribe,broadcast}.mjs`,
`scripts/rubblefront-broadcast.py`. Tests: `netlify/tests/rubblefront-list.test.mjs`. Site side: `Frontlink/web/rubblefront.com/assets/signup.js`.

## Flow
1. rubblefront.com form (JS) POSTs `{email, source, website}` to `/.netlify/functions/rubblefront-subscribe` (CORS for rubblefront.com, www and purplelink.llc).
   A pending record is stored and a confirmation email goes out from `RubbleFront <news@purplelink.llc>`. Every outcome (new, pending, already confirmed, honeypot) answers `200 {ok:true}`.
2. The link `.../rubblefront-confirm?t=<token>` marks the record confirmed and redirects to `https://rubblefront.com/confirmed/` (`?error=1` for a bad or expired token; pending records expire after 7 days).
3. `.../rubblefront-unsubscribe?u=<token>`: GET redirects to `/unsubscribed/`, POST is RFC 8058 one-click (200). It deletes the record and writes only a sha256 suppression marker.
4. The list is the only signup path. Without JS the forms post (urlencoded) straight to `rubblefront-subscribe`, which answers 303 to `/thanks/` (or `/thanks/?error=1`). With JS, `signup.js` uses fetch and shows an inline error if it fails; it does not fall back to Netlify Forms. Old Netlify Forms entries (before 2026-10-12) are unconfirmed and are not on this list.
5. The footer link in every email is the page `https://rubblefront.com/unsubscribe/?u=<token>` (one button, POSTs to the function). A GET on the function only redirects to that page and changes nothing, so mail scanners cannot unsubscribe anyone. The `List-Unsubscribe` header keeps the function URL for RFC 8058 one-click POSTs.

Blobs (new): `rf-list` (email -> record), `rf-list-tokens` (`c:`/`u:` token -> email), `rf-list-suppressed` (sha256(email)), `rf-broadcast-sent` (`<broadcastId>:<sha256>`), plus the shared `rate-limits`. The academic digest's `subscribers` store is untouched.
Limits: 3 per address and 20 per IP per UTC day.

## Env vars (names only, set in Netlify production)
- `RESEND_API_KEY` (already set)
- `RUBBLEFRONT_BROADCAST_SECRET` (new, any long random string; also exported locally when running the broadcast script)

## Postal address
One constant, `POSTAL_ADDRESS` in `netlify/lib/rubblefront-list.mjs`, used in confirmation and broadcast footers (text and HTML).

## Sending a broadcast (never automatic)
    export RUBBLEFRONT_BROADCAST_SECRET=...
    python3 scripts/rubblefront-broadcast.py --subject "..." --body news.md                 # dry run, prints a count
    python3 scripts/rubblefront-broadcast.py --subject "..." --body news.md --test-to ben@purplelink.llc
    python3 scripts/rubblefront-broadcast.py --subject "..." --body news.md --send          # type the count to confirm
The server sends via Resend in batches of 50 and records who got broadcast id X, so `--resume <id>` after an interruption never double-sends.
Send the `--test-to` copy first and check the unsubscribe link in it is present (the test link is inert).

Python note: the python.org build of Python has no CA roots; the script falls back to `/etc/ssl/cert.pem` (or `SSL_CERT_FILE`) by itself and never disables verification.

First contact may land in Junk: iCloud, Gmail and Outlook often file the first confirmation email from a new sender in spam. The thanks page tells people to check there; marking one message "not junk" helps the next. Expect that when testing with a new mailbox.

## Export or delete a subscriber
Blobs only, no admin UI. With the Netlify CLI against site b264591f-fbbe-4048-9d9d-7051cf497823: `netlify blobs:get rf-list <lowercase email>` to read;
to delete, unsubscribing via their link does it; manually, delete `rf-list/<email>` plus the `rf-list-tokens` keys `c:<confirmToken>` and `u:<unsubscribeToken>` from the record,
and write `rf-list-suppressed/<sha256 of email>` if they should be blocked from future broadcasts.

## Deploy and end-to-end test (after a production-context build of origin/main, see feedback_netlify-deploy-safety)
1. Set `RUBBLEFRONT_BROADCAST_SECRET`, build, deploy rubblefront.com separately.
2. Sign up with ben@purplelink.llc on rubblefront.com, click the emailed link, expect `/confirmed/`.
3. `--test-to ben@purplelink.llc`, then a real `--send` to a list that holds only that address, then use the unsubscribe link and confirm the count drops to 0.

## Known limits
- Netlify Blobs has no transactions: two simultaneous signups for one new address can send two confirmation emails (both links work).
- The suppression marker is an unsalted sha256, so it is guessable for a known address. It only blocks mail; it holds no address.
- A mail scanner that follows the unsubscribe GET link will unsubscribe the person (same trade-off as the other products).
- Other products' libs (`trial-reminder.mjs`, `followup.mjs`) still carry the older postal line; not touched here.
