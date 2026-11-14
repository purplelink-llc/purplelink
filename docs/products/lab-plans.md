# Lab plans and the Publication Pack

Backend for the Lab subscription plans and the one-time Publication Pack. Code: `backend/latextools/lab.py`, routes in
`backend/app.py` (search "Lab plan endpoints"), tests in `backend/tests/test_lab_plan.py`, `test_lab_endpoints.py` and
`test_publication_pack.py`. All customer-facing wording in the emails is placeholder text marked `# COPY:`.

## Switches

`LAB_PLANS_OPEN` and `PUBLICATION_PACK_OPEN` are Netlify environment variables. They stay closed until Ben opens them.
Nothing in the backend reads them. The backend accepts registrations whenever the Netlify side calls it.

## Products

| Key | Price | Reviews per grant | Billing |
| --- | --- | --- | --- |
| `lab-monthly` | $199 | 20 | monthly |
| `lab-annual` | $1,990 | 20 a month | yearly |
| `lab-plus-monthly` | $349 | 40 | monthly |
| `lab-plus-annual` | $3,490 | 40 a month | yearly |
| `publication-pack` | $59 | 1 Deep, 1 Revision Review, 1 response draft | once |

`register-token` refuses the four `lab-*` keys (400 `use_lab_register`). They go through `/lab/register`.

## Routes

All are POST with JSON and the `x-webhook-secret` header (500 `misconfigured`, 401 `unauthorized`).

- `/lab/register` `{subscription_id, product, email, session_id?, amount_paid?, amount_subtotal?, customer?}`. Reads the
  subscription from Stripe, requires a paid latest invoice (a $0 invoice counts as paid), creates the plan, and mints
  nothing. 200 `registered` or `exists`; 400 `unknown_product`, `missing_subscription_id`, `amount_mismatch`; 409 `unpaid`
  or `in_progress` (another call holds the claim, retry); 502 `stripe_unreadable`. The checkout path sends `session_id`,
  which becomes the root key. The invoice or purchase-order path sends no amounts and uses the root `lab-<subscription_id>`.
- `/lab/sync` `{subscription_id}`. Re-reads Stripe, applies status, cancel mark and period, and issues every due grant.
  200 `{ok, status: synced|unknown_plan, minted}`; 502 `stripe_unreadable`. Safe to call from the webhook, the plan page
  and the sweep: grants take an atomic claim.
- `/lab/revoke` `{subscription_id, reason: refund|dispute, dispute_id?}` and `/lab/restore` `{subscription_id, dispute_id}`.
  Revoke sets the plan flag only; the term check refuses every grant and follow-up through the plan id. A refund is never
  restored. A dispute is restored when the last open one is won.
- `/lab/plan`, `/lab/cancel`, `/lab/undo` `{token}`. The plan page. `plan` syncs lazily and falls back to the stored plan
  when Stripe cannot be read. Cancel and undo set `cancel_at_period_end` at Stripe, rotate the link, email a
  confirmation and return the view plus the new `token`. 404 `invalid`, 410 `replaced`, 409 `plan_over`, 502 `stripe_failed`.
- `/lab/rotate-group-link` `{token}`. Lab Plus only (409 `not_plus`). Replaces the group key; the old one stops resolving.
- `/lab/link` `{email}`. Always 200. Rotates the link and emails a new one when a live plan matches.
- `/lab/group-view` `{k}` and `/lab/member-claim` `{k}`. The Lab Plus group page. Keys look like `lg_...`.
  `member-claim` hands one unused review to a member (409 `none_left` with `next_grant`, 410 `plan_over`).
- `/paper-review/revoke-order` `{session_id, reason, dispute_id?}` and `/paper-review/restore-order`. One-time orders,
  including all three Publication Pack entries by their fixed keys.

## Records

Everything lab lives in `annual_plans_dict` next to annual plans, with different keys, so neither code path sees the other.

- `lab_<id>`: the plan. `labsub:<subscription_id>` and `labgroup:<key>` point at it. Annual uses `pl_` and `sub:` only.
- The plan link token is `lab_<id>.<expiry>.<nonce>.<sig>`, signed under its own label, 60 day expiry, at most 400 characters.
- Each grant is an entry in `paper_tokens_dict`. The first sits at the root key, later ones at `<root>#g<period>.<n>`.
  Entries carry `plan_id`, `lab_plan: true`, `term_ends_at` and never `expires_at`.
- Follow-ups (`fu-rev:<hash>`, `fu-resp:<hash>`) are created when a review from a batch is submitted, once per original
  token, and last 365 days. They are listed on the plan's grant (`fu`), so they are not re-created if the grant entry was swept.
- Publication Pack: `<session>` (Deep), `<session>#revision`, `<session>#draft`. The root lists the siblings and keeps
  the pack price; the product key stays `publication-pack`, so no review-spend row is written.

## How grants work

A plan grants its reviews at the start of each month of the paid period. A monthly plan gets one grant per paid invoice.
A yearly plan gets twelve, one a month, and each is claimed as `lab:<subscription>:<period end>:<n>`. Each grant lasts two
months. A grant needs an active subscription and a paid latest invoice. Per-grant `amount_paid` is the list price divided
by the months billed (a refund of one review is its share). The daily sweep (inside `lifecycle_email_sweep`, no new
schedule) re-reads each live plan from Stripe, issues grants that are due, and sends the 30 and 7 day reminder to yearly
plans.

## Invoice and purchase-order plans

A university paying by invoice has a Stripe subscription created by hand. Call `/lab/register` with only
`subscription_id`, `product`, `email`. The plan and root key are `lab-<subscription_id>`. Then call `/lab/sync`. The first
grant is issued once the invoice is marked paid.

## Mid-period upgrade

If the subscription's `metadata.product` changes (Lab to Lab Plus in the billing portal), sync moves the plan to the new
product from the next grant. Grants already issued stay as they are. A group link is created on the first Plus grant.

## When a grant fails

1. Call `/lab/sync` for the subscription. If it returns `minted: 0`, check the Stripe invoice is paid and the subscription
   is active.
2. A claim is released when minting raises, so a repeat sync retries. Check the Modal logs for "lab:".
3. A grant email that did not send does not undo the grant. The customer can reach the tokens from the plan page, and
   `/lab/link` mails a new link.
4. Never delete `lab:` claim rows by hand unless the matching grant is missing from the plan's `grants` list.

## Known follow-up

`_keep_pack_alive` keeps a Publication Pack root while a sibling exists, but it still writes back the entry it read, as it
does for every pack. A re-read before the write-back would close a small race with a concurrent submit.
