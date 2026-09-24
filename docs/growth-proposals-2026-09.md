# Growth proposals: more first purchases, more second purchases (2026-09)

Scope: product, pricing, retention and site changes that would lead a visitor to buy once and then buy again. This is a proposal only. No code was changed.

Sources read: `CLAUDE.md`, `docs/site-audit-2026-09-24.md`, `docs/paper-review-runbook.md`, `docs/products/*`, `docs/vitae-sponsors.md`, `docs/zotero-plugin-and-directory-scoping.md`, every function in `netlify/functions/`, the Paper Review parts of `backend/app.py` and `backend/latextools/delivery.py`, and the homepage, `/products/`, `/tools/paper-review/`, `/tools/paper-review/packs/`, `/moderntex/`, `/vitae/plus/` and `/privacy/`.

Market context: WebSearch worked, but WebFetch to competitor sites (reviewer3.com, texifier.com) was blocked by the sandbox proxy. The competitor prices below come from search-result snippets, mostly third-party aggregators, as of September 2026. Check them before quoting any of them on the site.

| Competitor | Price seen | What it tells us |
|---|---|---|
| Overleaf | Free; Standard about $21/mo ($199/yr); Student about $10/mo | ModernTex at $10 once is far below any LaTeX subscription. |
| Texifier (Mac) | $44.99 on the Mac App Store | The nearest native Mac rival costs 4.5 times as much. |
| Paperpal Prime | $25/mo or $144/yr | Academic writing tools sell as subscriptions. |
| Writefull Premium | $21/mo or $150/yr | Same. Many universities license it for their staff. |
| Reviewer3 | Free first review, $19 per review, $29/mo unlimited, institutional | The closest match to Paper Review. It charges twice as much per review. |
| Paper-Wizard | $42 per review, 10 for $299 | Paper Review packs cost a quarter of that per review. |
| AJE / Editage (human editing) | from about $38 (AJE); from about $0.06 per word (Editage) | Human editing of a 7,000-word paper costs about $400. |

The prices are not the problem. Paper Review costs a half to a fifth of what the AI reviewers charge, and ModernTex costs a quarter of Texifier. Most of the proposals below therefore deal with trust, remembering the customer, and a reason to come back, not with discounts.

---

## 0. What already exists (reuse it rather than rebuild it)

Several of the things the brief asks about are partly built:

- **Paper Review lifecycle email.** `lifecycle_email_sweep` in `backend/app.py` (daily Modal cron) sends tips on day 3, "how did it hold up" on day 14 and "still writing?" on day 90 to every paid-tool buyer, with signed one-click unsubscribe (`lifecycle_optout_dict`). Templates: `backend/latextools/delivery.py`.
- **A referral loop.** Each report's footer carries a personal code; `checkout.mjs` passes `ref` to Stripe; a `.edu` buyer using a live code earns both sides a $2 promotion code (`_credit_referral`). Digest subscribers also get codes (`subscribe.mjs`) that nothing reads yet.
- **Invoices.** `POST /paper-review/invoice` builds a Stripe invoice for a past session.
- **Passwordless email flows.** `vitae-license.mjs` `recover` and `manage` (HMAC-signed 24-hour portal link), and `subscription-portal.mjs` for the digest. A magic-link account is this pattern plus a session cookie.
- **An in-app cross-sell channel.** Vitae's sidebar card reads `site/vitae/promos.json` (`docs/vitae-sponsors.md`).
- **Analytics.** Cloudflare Web Analytics; first-party `analytics.js` → `track.mjs` (`pageview`, `tool_use`, `checkout_click`, `trial_download`); owner-only `stats.mjs` and `sales.mjs`. `/moderntex/` and its success page carry a Google **Ads** conversion tag (`AW-18464618488`); I found no GA4 ID (`G-…`) anywhere in `site/`.
- **A benchmark harness.** `backend/benchmark/run_benchmark.py` (Citation Gap on real arXiv papers), built and deliberately never run.

## 0.1 Fix before growing: two promises the code does not keep

**A. Paper Review pack tokens expire after 7 days, but five pages say they never expire.**

- `register-token` in `backend/app.py` (around line 2106) sets `expires_at = now + PAPER_TOKEN_TTL_SECONDS`, and `PAPER_TOKEN_TTL_SECONDS` is 7 days. Every product gets this, packs included.
- `sweep_expired_paper_tokens` (around line 3299) runs daily and deletes the whole entry once that time passes. `redeem-session` returns `410 expired`.
- Meanwhile `/tools/paper-review/packs/` (meta description, both tier cards and the FAQ "No. Pack tokens have no expiry date."), `/packs/success/` and `/products/` all promise no expiry.
- So a lab that buys the $150 20-pack and uses three tokens in the first week loses the other seventeen.
- The comment on `_expire_token_entry` also says Modal Dicts evict idle entries after about 7 days. If that is true, Modal Dict cannot hold a long-lived balance even once the TTL is removed.

Fix now:
- Give `qty > 1` entries no `expires_at`.
- Check in Stripe for any pack sold more than 7 days ago and re-issue its unused tokens by hand.
- In the longer term, move pack balances into the Blobs ledger described in §1.

This is the same class of failure as the webhook incident in the runbook: a customer pays and is left holding nothing.

**B. The privacy page promises a win-back rule the code does not enforce.** `/privacy/` says the win-back email goes out "only if you haven't purchased again". `lifecycle_email_sweep` never checks for a later purchase. It also says "We do not send newsletters, marketing emails…". Every lifecycle idea in §2 has to start by adding the repeat-purchase check and updating that page. (Smaller: `manuscript_title` in the lifecycle record is always blank, because it is seeded at purchase time and never updated once the report exists.)

---

## Priority summary

| # | Proposal | Effort | Why it ranks here |
|---|---|---|---|
| 0 | Fix pack expiry and the privacy page's win-back promise | S | Paid customers are losing value today |
| 1 | Next step on every success page and in every delivery email | S | Cheapest second purchase there is |
| 2 | Client-side preferences | S | Faster repeat use of the free tools, no privacy cost |
| 3 | Lifecycle email v2 (ModernTex, Revision/Response timing) | M | Uses a sequence that is already running |
| 4 | Submission and Revision bundles, gift tokens | M | Higher order value, and a way into labs |
| 5 | Funnel events and a repeat-purchase dashboard | S–M | Without it none of the rest can be judged |
| 6 | Testimonials, sample outputs, report of the month | S–M | The audit's biggest conversion gap |
| 7 | My Purplelink (magic-link account) v1 | M–L | Durable relationship, pack balance, re-download |
| 8 | LaTeX template gallery by venue | M | Search traffic into ModernTex |
| 9 | Lab licences, institutional purchase path | M | Larger orders from people who already buy |
| 10 | Setapp listing, SUB upsell path, Zotero companion | M | New distribution |
| 11 | Purplelink Pass (annual) | M | Only once 5 and 7 exist |
| 12 | Vitae ↔ Paper Review bridge, camera-ready check, iPad | M–L | Real fit, but later |

---

## 1. Accounts: "My Purplelink"

**What.** An optional sign-in at `/account/`. You enter an email, get a one-time link, click it and you are signed in. No password, and no account is needed to buy anything. The page shows:

- **Purchases:** every Checkout Session paid with that email, with receipt and invoice links.
- **ModernTex:** the current DMG download and a "show my licence key" button. ModernTex keys are Ed25519 signatures over a random nonce (`issueModernTexLicense` in `stripe-webhook.mjs`), so any validly signed key unlocks the app. The account can mint a fresh key for a verified buyer, and the old one never has to be stored. Today the key is emailed once and never kept, so a lost email means a lost key.
- **Paper Review balance:** unused pack tokens, with "start a review" next to each, and single-use tokens that were bought but never redeemed.
- **Vitae Plus:** plan, renewal date, and "manage billing", which reuses the portal-token code in `vitae-license.mjs`.
- **Email preferences:** lifecycle emails on or off, product news on or off.
- **Referral code and credits:** reuse `_paper_referral_code`.
- **Report archive:** off unless the customer turns it on (see the privacy notes below).

**Why it increases purchases.**
1. Pack balances become visible. A balance you can see gets spent, and spent packs get re-bought.
2. Every return visit for a download or a key goes through a page that can also offer the next step.
3. Labs can hold one balance and hand tokens to students.
4. It is the identity layer that the Pass (§3), gifts and preferences that follow you between devices all need.
5. It closes support gaps: lost keys, lost pack emails, lost ModernTex download links.

**Data model (Netlify Blobs, no new vendor).**

```
store "accounts"        key = sha256(lower(email))  (the "account id"; the raw email is kept inside)
  { email, created_at, stripe_customer_ids: [], prefs: {...},
    consent: { lifecycle: true, news: false, archive: false, updated_at },
    referral_code, deleted_at? }

store "purchases"       key = `${accountId}/${checkoutSessionId}`   (written by stripe-webhook.mjs)
  { product, amount, currency, created_at, mode, subscription_id?, refunded? }

store "entitlements"    key = `${accountId}/${entitlementId}`
  { kind: "paper-token" | "moderntex" | "vitae-plus" | "gift",
    product, source_session, remaining?, tokens?: [...], created_at }

store "login-nonces"    key = nonce   { account_id, exp, used_at? }
```

**Endpoints (new `netlify/functions/account.mjs`, routed at `/api/account/*`).**

| Method and path | What it does |
|---|---|
| `POST /api/account/login {email}` | Always returns `200 {status:"sent_if_found"}`, answers first and emails after, like `vitae-license.mjs` recover. Rate-limited per IP and per address with the existing `rate-limits` store. Emails `https://purplelink.llc/account/verify/<token>`, valid 15 minutes, single use. |
| `GET /account/verify/<token>` | The token is `accountId.exp.nonce.HMAC(ACCOUNT_SECRET)` and goes in the path, not the query string, because of the Netlify redirect behaviour noted in `vitae-license.mjs`. Marks the nonce used, sets `pl_session` (signed `{sub, exp: +30d}`, `HttpOnly; Secure; SameSite=Lax`) and redirects to `/account/`. |
| `GET /api/account/me` | Account, purchases and entitlements. On first sign-in it backfills history from Stripe with `GET /v1/checkout/sessions?customer_details[email]=…`, plus `/v1/customers?email=` for subscriptions. |
| `GET /api/account/moderntex` | DMG list plus a freshly minted key. Moves the list and stream logic of `moderntex-download.mjs` into a shared module. |
| `POST /api/account/tokens` | Pack balance. The server calls a new Modal endpoint `/paper-review/tokens-for-sessions`, authenticated with the existing `BACKEND_WEBHOOK_SECRET`. |
| `POST /api/account/prefs`, `POST /api/account/consent` | Settings. |
| `POST /api/account/logout`, `POST /api/account/delete` | Delete removes the account, purchases index and archive. Stripe keeps its own records, which it has to for tax. |

Code touched:
- `stripe-webhook.mjs`: also write `purchases/` and `entitlements/`.
- `checkout.mjs`: change `customer_creation: "if_required"` to `"always"` for payment mode, so every buyer has a Stripe Customer and invoices and history hang off one ID. If a signed-in buyer is detected, set `customer`.
- `backend/app.py`: a token-listing endpoint, and pack balances moved to Blobs or at least never expired.
- New files: `site/account/` (HTML, `account.js`, CSS), and `netlify.toml` redirects for `/api/account/*` and `/account/verify/*`.
- CSP: nothing to change, since everything is same-origin.

**Effort.**
- **v1 (M):** login, history, ModernTex re-download and key, pack balance, Vitae manage.
- **v2 (M):** consent centre, referral credits.
- Report archive: separate, see below.

**Privacy trade-offs, stated plainly.**
- Today the site can say "no account, nothing kept". With accounts it will keep an email address and a list of what that address bought. Stripe already holds exactly this, so the new exposure is a second copy in Netlify Blobs. Keep it minimal: no names, no manuscript titles, no IP addresses.
- Magic links are only as secure as the inbox. That is acceptable because the account never shows card data, and billing changes still go through Stripe's portal.
- A logged-in session cookie is the site's first first-party cookie. It is strictly necessary, so no consent banner is needed. Say so on `/privacy/`.
- Accounts must stay optional. Every checkout keeps working without one. "No account needed" is part of what sells Paper Review, so keep saying it.
- **Report archive.** The current promise is that a report "is deleted from our servers the moment you retrieve it", and it is repeated in schema, FAQ, emails and `/products/`. Options, from most to least private:
  1. **On this device only (recommended first).** The status page saves the Markdown to IndexedDB after delivery. `/account/` lists the reports stored on this device. Nothing reaches the server, and the promise stays true.
  2. **Encrypted before it leaves the browser (opt-in).** The browser encrypts the report with a key derived from a passphrase the customer chooses, and the server stores only ciphertext. The promise changes to "we store only an encrypted copy we cannot read, and only if you ask". Costs: a lost passphrase means a lost report, and the crypto code has to be audited.
  3. **Server-side archive (opt-in).** Simplest, and it breaks the promise for anyone who opts in. It also creates a store of unpublished research findings, which makes the site a target. Don't do this.

  Ship option 1, and build option 2 only if customers ask for it.

**Measure.**
- Sign-ins per week.
- Share of pack buyers who sign in.
- Pack tokens redeemed within 30 days, before and after launch.
- Repeat purchase rate of signed-in buyers against others (keep in mind people who sign in are self-selected).
- Support emails about lost keys or tokens, which should fall to near zero.

---

## 2. Retention and lifecycle email

Provider: Resend is already wired up. The Netlify side uses `RESEND_API_KEY` (the "purplelink-netlify" key, `orders@purplelink.llc`) and the Modal side uses `resend-secret`. Modal allows only 5 scheduled functions on this account, which is why the sweeps were merged into `lifecycle_email_sweep`. New sequences should either add stages to that function or run as a Netlify Scheduled Function.

Rules for every sequence:
- At most one lifecycle email per address per 7 days, across all products, enforced by a shared `last_sent_at` per address.
- One-click unsubscribe on every email.
- Transactional emails stay separate from anything promotional.
- The privacy page describes each sequence before it ships.
- No email to anyone who hasn't bought something or explicitly asked for it.

**2a. ModernTex buyers (M).**
- **Timing:** day 0 is the existing receipt with the key. Add a day 3 tips email (three compile modes, the submission check, BibTeX autocomplete) and a day 21 "before you submit" email mentioning Paper Review once.
- **Why:** tips cut refunds and help people actually use the app. The day-21 email is the natural bridge from the editor to the paid checks.
- **Code:** `stripe-webhook.mjs` writes `lifecycle/<sessionId>` to Blobs, and a new Netlify scheduled function `lifecycle-mtx.mjs` sends from it. Templates go in a new `netlify/functions/lib/emails.mjs`.
- **Measure:** refund rate, and Paper Review purchases from the `?from=mtx-d21` UTM.

**2b. ModernTex trial day 1 / 5 / 7 (M, only with consent).**
- **The gap:** the trial is a public `?trial=1` download and collects no email, so there is no one to write to.
- **Proposal:** an optional field next to the trial button, "Email me a setup guide and a reminder before the trial ends". Send day 1 (setup, TeX distribution check), day 5 (features) and day 7 (trial ends today, $10).
- **Why:** a trial that ends silently loses the people who meant to buy.
- **Risk:** a required email would lower trial downloads, so keep it optional.
- **Measure:** trial-to-paid conversion for people who gave an email against people who didn't. Count `trial_download` against `moderntex` sessions in `sales.mjs`.

**2c. Paper Review → Revision Review and Response Review, when they are likely to be needed (M).**
- **What:** on the upload page, ask optionally "When do you expect a decision?" (4, 8 or 12 weeks, or "don't remind me"). At that point send one email: "If you got reviews back: Response Review ($6) checks your letter against every comment, and Revision Review ($2) checks the revision against your original findings."
- **Why:** right now the win-back goes out at a fixed 90 days whatever is happening. A reminder tied to the actual decision arrives when the customer needs the tool.
- **Code:** add `remind_at` to `customer_lifecycle_dict`, a new stage in `LIFECYCLE_STAGES`, and a template in `delivery.py`.
- **Also:** skip the win-back if the address has bought again. That is required by §0.1B anyway.
- **Measure:** Revision Review and Response Review purchases within 14 days of the reminder, and unsubscribe rate per stage.

**2d. Rejections and Vitae Plus trials (S).** When a submission is marked rejected, Vitae's sidebar card can suggest an anonymity and format check for the new venue, a local rule with no email. For Vitae Plus, turn on Stripe's reminder 3 days before a trial ends; it is honest practice and cuts chargebacks.

---

## 3. Bundles and pricing

**3a. Submission bundle (M).**
- **What:** Paper Review Standard ($9, Anonymity Check already included), Citation Gap ($3) and Cover Letter ($2) together for **$12**, instead of $14 bought separately. (The brief's version, Paper Review plus Cover Letter plus Anonymity, would double up, because Anonymity Check is already free with every Paper Review tier.)
- **Revision bundle:** Response Review ($6) and Revision Review ($2) for **$7**.
- **Why:** it raises average order value, turns three decisions into one, and gets the $2–3 tools used by people who would never go looking for them.
- **Code:**
  - `checkout.mjs` `PRODUCT_CATALOG`: new keys.
  - `backend/app.py` `PAID_PRODUCTS`: a `components` list. `register-token` mints one token per component, each carrying its own `product_cfg`, and `redeem-session` routes each token to its own upload page.
  - A bundle success page modelled on `packs/success/`.
  - `sales.mjs` `SITE_OF_PRODUCT`.
  - New Stripe prices and env vars.
- **Risks:** more SKUs to keep in sync. The amount cross-check in `register-token` has to know the bundle amounts.
- **Measure:** attach rate (bundle sales divided by Paper Review sales), and average order value.

**3b. Gift tokens and gifts from an advisor (S).**
- **What:** Paper Review tokens are already bearer credentials, so a gift is a single-token "pack" whose email says "forward this to your student".
- **For ModernTex:** a gift purchase emails a licence key and download link meant for forwarding. `issueModernTexLicense` can mint any number of keys.
- **Why:** advisors pay for students, and the gift carries the brand into a new lab.
- **Code:** `checkout.mjs` (`gift-paper-review`, `gift-moderntex`), `stripe-webhook.mjs`, and new copy in `delivery.py`.
- **Measure:** gift sales, and later purchases by the people who received gifts. Check the gift's referral code on their checkout.

**3c. Lab and department licences (M).**
- **ModernTex lab licence:** 5 keys for $40 or 20 keys for $120, all emailed to the buyer. The code already exists: loop `issueModernTexLicense`.
- **Paper Review:** the 20-pack is already the lab product. Rename it "Lab pack", and let a signed-in PI see which tokens are used (§1).
- **Department:** "Buy by invoice or purchase order" for orders of $300 or more, handled manually at first through a contact form. `/paper-review/invoice` already creates invoices, so extend it to create a `send_invoice`, net-30 invoice before payment rather than after.
- **Also needed:** a vendor page with the W-9, a sole-source letter template, and a page on accessibility and data handling. University purchasing offices ask for these.
- **Measure:** number of orders of $100 or more, and time from inquiry to paid invoice.

**3d. Education pricing: don't.** ModernTex at $10 is already a quarter of Texifier, and Paper Review is a fraction of Reviewer3 and Paper-Wizard. A student discount on $2–$10 items adds friction (verification) for pennies. The `.edu`-gated referral credit already favours academics. Revisit only for the Pass.

**3e. ModernTex 2.x upgrade pricing (S now, the decision comes later).**
- The page says "$10 once, updates included", and one variant says "1.x update included".
- Before 2.0 is announced, change every instance to "every 1.x update included". Buyers from before the change get 2.0 free. The keys are nonce-only and carry no purchase date, so grandfathering means checking the Stripe session date through the account page or by email.
- 2.0 pricing: $19 new, $9 upgrade for 1.x owners. The upgrade is verified by signing in (§1) or by pasting the 1.x key.
- Even at $19, ModernTex is well under Texifier.
- **Risk:** the biggest trust risk in this document. A 2.0 that feels like a paywall on software people already bought would cost more goodwill than it earns.

**3f. Purplelink Pass (M, day 90 or later).**
- **What:** a $59/year subscription. It includes Vitae Plus annual ($24), 6 Standard Paper Reviews, unlimited Cover Letter, Anonymity, Citation Gap and Revision checks under a fair-use cap, and ModernTex (a key, if they don't have one).
- **Why:** it matches how researchers already buy Paperpal and Writefull, and it turns a buyer who purchases once a year into recurring revenue.
- **Preconditions:**
  - Accounts (§1), so there is an identity to hold the entitlement.
  - The real per-job model cost from `usage_ledger_dict` (the runbook's cost and margin section), since the price has to cover six Deep-length jobs at worst.
- **Risk:** cannibalising the 5-pack, and subscription fatigue. Price it after reading 90 days of repeat-purchase data from §8.

---

## 4. Preferences without an account (client-side)

**What:** a `pl:prefs` object in `localStorage`, read and written by `site/site.js`, with a "Clear saved preferences" link in the footer. Every read and write goes in `try/catch`, so a blocked storage falls back to defaults. Fields:
- `citationStyle` (Citation Generator, Reference Converter, BibTeX Builder output)
- `compiler` (pdfLaTeX, XeLaTeX or LuaLaTeX, for LaTeX to PDF)
- `recentTools` (last 5 tool paths): a "Recently used" row at the top of `/tools/` and on the homepage tools section
- `venue` (one key from `backend/latextools/journals.py`, the 25 journal specs, or a `/format/` venue): format pages highlight it, and the Paper Review upload page preselects the Journal Pack venue and domain
- `domain` (ML, biomed, psych, chem, general): the Paper Review upload default

**Why:** repeat visitors to the free tools get to their result faster. Remembering the venue makes a paid check look tailored to them. A saved venue also lets the tool pages show one relevant product card ("Submitting to MISQ? The journal pack checks MISQ's format, $11") instead of a generic one.

**Effort:** S. Code: `site/site.js`, `site/tools/tools.js`, the per-tool JS for the citation, reference, BibTeX and LaTeX-to-PDF tools, `site/tools/paper-review/upload.js`, and `site/format/*`. No CSP change and no server.

**Risks:** almost none. Say on `/privacy/` that preferences stay in the browser. Don't sync them to accounts until someone asks.

**Measure:** a `pref_saved` event, and a `tool_use` flag for whether a saved preference was applied. Watch Paper Review Journal-tier share among visitors with a saved venue.

---

## 5. New apps and features that fit

**5a. LaTeX template gallery by venue (M, high).**
- **What:** `/templates/<venue>/` pages, each with the official class file link, a clean starter `.tex` and `.bib` as a ZIP, the venue's page and anonymity rules, and "open in ModernTex". The last needs a `moderntex://` URL scheme in the app. Until then, "download, then File › Open".
- Start with the 8 venues that already have `/format/` pages and the ML venues in `journals.py` (NeurIPS, ICML, ICLR).
- **Why:** "<venue> LaTeX template" is a high-intent search made by people who are about to write in LaTeX, which is the ModernTex buyer at the moment they need an editor. It also feeds the Journal tier and the Anonymity Check.
- **Code:** new `site/templates/`, a sitemap entry, and a "Next step" block linking the template, the format page, ModernTex and Paper Review Journal.
- **Risks:**
  - Class-file licences. Link to official sources rather than rehosting them unless the licence allows it (the LPPL usually does).
  - Keeping them current. Date every page.
  - The audit notes the format pages already overlap 28–56%. Every template page needs venue-specific content.
- **Measure:** organic entrances to `/templates/*`, template downloads, `trial_download` with `from=templates`.

**5b. Camera-ready check (M).**
- **What:** a $3 check on the final PDF:
  - fonts embedded and no Type 3 fonts
  - page count against the venue limit
  - anonymisation removed (the opposite of Anonymity Check)
  - PDF/A and PDF-eXpress style issues
  - leftover `\todo` and `??` references
  - figure resolution
- **Why:** it sits at the one point in the cycle no current product covers, just after acceptance, when authors are happy and short of time.
- **Code:** it can reuse `backend/latextools/pdf_structure.py`, `journals.check_compliance` and `manuscript_checks`, mostly deterministic with little LLM cost. New `PAID_PRODUCTS` key, `site/tools/camera-ready/`.
- **Measure:** sales, and the share of buyers who had bought Paper Review before.

**5c. Vitae ↔ Paper Review bridge, a "submission tracker" (M, mostly in the Vitae repo).**
- **What:** on a submission in Vitae, a "Check before submitting" button opens `/tools/paper-review/?venue=…&domain=…&from=vitae`. When the user marks a decision, Vitae offers Response Review or Revision Review from that submission.
- **Why:** Vitae already knows the venue, the dates and the decision. That is exactly the timing information §2c has to ask for, and it lives on the user's Mac with no server copy.
- **This repo:** `upload.js` and `paper-review.js` read `venue` and `domain` from the query string. `promos.json` rules can target on submission state if the app exposes it.
- **Measure:** paid sessions with `from=vitae`.

**5d. Response drafting tool (M, later).** A point-by-point response skeleton built from the decision letter would pair with Response Review ($6), and the Vitae Plus revision workspace already splits decision letters. Keep it to structure and never write scientific claims; it may fit better as a Vitae Plus feature than as a paid web tool.

**5e. Zotero / BibTeX companion (M).** Already scoped in `docs/zotero-plugin-and-directory-scoping.md`: a free Zotero plugin running the BibTeX Validator's checks on a collection. Its value is distribution (awesome-zotero lists, the in-app plugin market) and a link to ModernTex. Measure with `from=zotero`.

**5f. Mac App Store vs Setapp for ModernTex (M).**
- **Mac App Store:** requires sandboxing. ModernTex runs the user's TeX distribution in `/Library/TeX`, which the sandbox blocks without user-granted access or a bundled engine, and Apple keeps 15% on the Small Business Program. That is a lot of engineering and support for a $10 app.
- **Setapp:** does not require the sandbox and pays developers 70% of subscription revenue by usage, with a partner bonus for referred users (per Setapp's developer docs as summarised in search results).
- **Recommendation:** apply to Setapp first, as extra reach with little cannibalisation, since Setapp users rarely buy apps directly. Skip the Mac App Store unless ModernTex ever bundles its own engine.
- **Code:** in the ModernTex repo (Setapp framework, a separate build flavour), not here.

**5g. Scholar Utility Belt upsell path (S).** 1,000 users and 4.5 stars, and it currently sends nobody anywhere.
- Add a quiet "More from the maker" section in the popup or options page.
- Add a post-update "what's new" page on purplelink.llc that lists one product card.
- On a journal's badge tooltip, a small "Submitting here? Format and anonymity checks" link, off by default or dismissible for good.
- Tag every link `?from=sub`.
- **Risk:** Chrome Web Store policy and reviews punish anything that feels injected. Never put promotions inside Google Scholar results by default.
- **Measure:** sessions and sales with `from=sub`, and whether the rating moves.

**5h. ModernTex for iPad (L, not in the next 90 days).** iPadOS cannot spawn a TeX engine, so it needs an embedded engine or remote compile, and remote compile breaks "your files stay on your device". Ask about demand in the day-21 email first.

---

## 6. Referrals and affiliates

**6a. Referral credits across products (S–M).**
- Today the loop only runs Paper Review to Paper Review, only for `.edu` buyers, and only through a footer in the report.
- Extend it:
  - Show the code on `/account/` and in the ModernTex receipt.
  - A referred ModernTex purchase earns the referrer a free $2–3 check token, which costs little in model spend, rather than cash.
  - Keep the `.edu` gate for credits, so it can't be farmed.
- **Code:** `checkout.mjs` (already passes `ref`), `stripe-webhook.mjs`, `_credit_referral` in `backend/app.py`.
- **Measure:** the share of paid sessions with `metadata.referral_code`. `sales.mjs` can count them.

**6b. The Amazon "research desk" page at `/desk/` (S, low revenue, handle with care).**
- **Economics:** Associates pays low single digits on the likely categories. Search results cite about 3% for office products and 3–5% for computers; confirm the current schedule in Associates Central. A $300 monitor arm earns about $10. Treat the page as content that brings in search traffic, not as a revenue line.
- **Rules:**
  - List only things Ben uses, with a first-person line on each.
  - Put the disclosure at the top, as the FTC and Amazon's operating agreement both require.
  - No affiliate links on product, paid-tool, checkout or status pages.
  - Not in the primary nav.
  - Track outbound clicks with `plTrack("affiliate_click")`.
- A good version is also a natural place to link ModernTex ("the editor I write in") and Vitae.
- An "Amazon storefront" (Influencer shop) needs a qualifying social following and adds another brand surface. Not worth it.

**6c. LibGuides and research-office outreach (S, manual).** Pitch the free tools and Scholar Utility Belt to librarians, never the paid tools; one short email per library. The same contacts lead to department purchases (§3c). Tag links `?from=libguide-<school>`.

**6d. Paying affiliates: not yet.** It needs payout tracking Stripe Checkout alone does not provide, and invites hype content. Revisit if 6a works.

---

## 7. Trust and social proof

**7a. Collect testimonials properly (S).**
- The day-14 `review_request` email already asks how the review held up. Add one question: "May I quote you? Name and role, or initials only."
- Store the answer through a small Netlify function (`testimonial.mjs`, a Blobs store). Ben approves each one by hand before it appears.
- Also ask the 16 Chrome Web Store raters and the early ModernTex buyers, as the audit suggests.
- Show 1–2 quotes under each Buy button. Never edit a quote, and never invent one.
- **Measure:** conversion rate on the page before and after.

**7b. Show the output (S).** From the audit: sample report open by default, samples for the $2–3 tools, Vitae screenshots, a short ModernTex recording.

**7c. Report of the month (S–M).**
- Run Paper Review on one of Ben's own published papers, or on a CC-BY preprint whose authors have agreed. Publish the report with a short note on what it caught, what it missed and what the reviewers actually said.
- **Why:** it is proof that is honest about the tool's limits, and it gives the blog something new each month.
- **Risk:** publishing a critique of someone else's paper without consent. Don't.

**7d. An open benchmark (M, budgeted).**
- Run `backend/benchmark/run_benchmark.py` once with a fixed budget, and add a Paper Review comparison against public OpenReview reviews (ICLR) where the terms allow it: how many issues the human reviewers raised that Paper Review also found, and the reverse.
- Publish the method, the raw per-paper results and the misses.
- **Why:** the audit's GEO section says original data is what language models cite, and no competitor publishes this.
- **Risk:** the numbers may be unflattering. Publish them anyway and say what changed as a result.

**7e. Per-product changelog feeds (S).** Add a "last updated" date to each product page; regular visible releases answer "will this be maintained?".

---

## 8. Analytics: what to measure

**Current sources:**
- Cloudflare Web Analytics (sampled pageviews)
- `track.mjs` events
- `sales.mjs` (Stripe revenue by product)
- the Google Ads conversion tag on ModernTex

The daily-salted IP hash in `track.mjs` means a visitor can't be followed across days. That is fine: repeat purchase should be computed from Stripe, not from the browser.

**Events to add to `analytics.js`** (all first-party, cookieless, DNT respected):
- `product_view` (with `m` = product)
- `checkout_complete`, fired on each success page
- `upload_started` and `review_delivered`, on the status page
- `cross_sell_click` (with `m` = from→to)
- `pref_saved`
- `login_sent` and `login_ok`
- `affiliate_click`
- `trial_email_optin`

**Funnels for the `/stats/` dashboard** (extend `stats.mjs` and `sales.mjs`; one page, owner-only):

| Funnel | Steps |
|---|---|
| ModernTex | `/moderntex/` views → `trial_download` → buy `checkout_click` → paid `moderntex` sessions (→ refunds) |
| Paper Review | tool page views → `checkout_click` → paid sessions → `upload_started` → `review_delivered` |
| Cross-sell | success-page views → `cross_sell_click` → paid sessions with `from=` |
| Vitae Plus | `/vitae/plus/` views (split `ref=vitae-card`) → trial starts → first charge → month-3 retention |

**The one number to watch:** repeat purchase rate, meaning the share of buyers in a month who buy anything again within 90 days. Compute it in `sales.mjs` by grouping paid sessions on a salted hash of `customer_details.email`, held in memory and never shown or stored. Also show average order value and the refund rate by product.

**Google tags:** keep the Ads conversion tag limited to the ModernTex pages it is on now. Adding GA4 across the site would mean a consent banner in the EU and would clash with the "no tracking" wording. The first-party events cover what is needed.

---

## 30 / 60 / 90 days

**Days 1–30 (fixes, and quick revenue from existing traffic)**
- Pack tokens never expire. Re-issue tokens to any affected buyers. Update the privacy page and add the repeat-purchase check to the win-back (§0.1).
- Set `customer_creation: "always"` in `checkout.mjs`.
- A next step on every success page and delivery email (audit §2): ModernTex success → Paper Review, Paper Review status → Submission bundle, Vitae Plus success → ModernTex.
- Client-side preferences v1 (§4).
- The new analytics events and the funnel and repeat-purchase view (§8).
- The testimonial question in the day-14 email. Samples on the paid tool pages.
- Change ModernTex's wording to "every 1.x update included".
- The ModernTex day-3 and day-21 emails (§2a).

**Days 31–60 (accounts and bundles)**
- My Purplelink v1: login, purchase history, ModernTex re-download and key, pack balance, Vitae manage (§1). Reports saved on the device only.
- The Submission and Revision bundles, and gift tokens and keys (§3a, §3b).
- The decision-date reminder for Revision and Response (§2c). The optional trial email (§2b).
- The first 5 venue template pages (§5a).
- Apply to Setapp. Add the "More from the maker" section to Scholar Utility Belt (§5f, §5g).
- `/desk/` goes live with its disclosure and click tracking (§6b).

**Days 61–90 (bigger buyers and authority)**
- Lab licences, the invoice or purchase-order path, and the vendor page (§3c).
- Referral credits across products, shown in the account (§6a).
- The benchmark post, and the first report of the month (§7c, §7d).
- A camera-ready check prototype (§5b).
- The Vitae bridge in the next Vitae release (§5c).
- A decision on the Pass, based on 90 days of repeat-purchase and cost-ledger data (§3f).
- 10 LibGuides and research-office emails (§6c).

---

## Things not to do

- **No fake urgency.** No countdown timers, no "only 3 left", no "was $X" price without an end date. The kits' "launch price, rising to $79" with no date already falls short of this rule.
- **Never require an account to buy,** and never make one the default. "No account" is part of why people trust Paper Review.
- **Don't store manuscripts or reports on the server by default,** and never quietly weaken "deleted when you retrieve it". Any archive is opt-in and described on the page where the customer turns it on.
- **Don't put buyers on the Daily Digest or any list they didn't ask for.** The digest also covers cybersecurity and AI news, a different audience from researchers checking a manuscript, so don't cross-promote it in purchase flows.
- **No ads or affiliate links on money pages** (product, checkout, upload, status, account). Don't put an "Amazon storefront" in the navigation.
- **Don't turn ModernTex into a subscription,** and don't charge 1.x buyers for 2.0 without a clear, dated promise that says so.
- **Don't overclaim the AI.** No "senior-reviewer-level", no "no more desk rejections", no invented accuracy numbers. The founder already turned down estimated statistics; only publish benchmarks that were actually run.
- **Don't publish critiques of other people's papers without their consent,** including as marketing examples.
- **No testimonials that are edited, paid for or made up,** and no marking up of Chrome Web Store ratings as `aggregateRating`.
- **Don't inject promotions into Google Scholar** through the extension.
- **Don't let the Kits (faceless content, clip reposting) share navigation or email lists with the academic products.**
- **Don't add GA4 or other third-party trackers site-wide** just to get dashboards that the first-party events already provide.
