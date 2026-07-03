# Paper Review — Setup Runbook

End-to-end checklist for launching the paid Paper Review tool. Work through
this in order. Steps marked **manual** require you to do something in a
third-party dashboard; everything else is a CLI command.

---

## Prerequisites

- Anthropic API key (you have one)
- Modal CLI authenticated (`modal token new` if not)
- Netlify CLI authenticated (`netlify login` if not)
- A Stripe account (will set up below if you don't have one)

---

## 1. Stripe — create account, product, price (manual)

1. Sign up at <https://dashboard.stripe.com/register> (use ben@purplelink.llc).
2. Keep the dashboard in **test mode** for setup — toggle is top-right.
3. Activate the account when ready for live payments. Stripe will ask for
   bank details and Purplelink's EIN; you can defer this until after a
   test-mode end-to-end works.
4. **Create all paid-product prices.** Each is a separate Stripe Price
   under a single Product (or under separate Products — either works).
   Use Products → **+ Add product** and add each price below as a
   **one-off** payment, not recurring:

   | Product key (used in code)        | Display name                              | Price  |
   |-----------------------------------|-------------------------------------------|--------|
   | `paper-review-standard`           | Paper Review — Standard (+ free Anonymity Check) | $9 |
   | `paper-review-journal`            | Paper Review — Standard + Journal Pack    | $11    |
   | `paper-review-deep`               | Paper Review — Deep (2-pass, all bundled) | $15    |
   | `paper-review-pack-5`             | Paper Review — 5-pack                     | $38    |
   | `paper-review-pack-20`            | Paper Review — 20-pack                    | $150   |
   | `cover-letter`                    | Cover Letter Generator                    | $2     |
   | `anonymity-check`                 | Anonymity Check                           | $2     |
   | `citation-gap`                    | Citation Gap Analysis                     | $3     |
   | `revision-review`                 | Revision Review                           | $2     |
   | `response-review`                 | Response to Reviewers                     | $6     |

   Repriced 2026-07-03 for the Sonnet 4.5 -> Fable 5 model upgrade — see
   the margin-rationale comment above `PAID_PRODUCTS` in `backend/app.py`.

   Note: `paper-review-anonymity` (the previous $6 +Anonymity tier) was
   removed — Anonymity Check is now bundled free with every Paper Review
   tier. Do NOT create a Stripe Price for that SKU.

5. Copy each **Price ID** (starts with `price_…`) — you'll set them as
   per-product env vars in Netlify in step 3 below.
6. Copy your **test mode Secret key** from Developers → API keys
   (starts with `sk_test_…`). Don't expose it in any file.

---

## 2. Modal — create secrets and deploy (CLI)

Generate a shared webhook secret first (used by Stripe webhook → Modal):

    BACKEND_WEBHOOK_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    echo "Save this: $BACKEND_WEBHOOK_SECRET"

Create the Modal secrets:

    modal secret create anthropic-secret \
        ANTHROPIC_API_KEY="sk-ant-…YOUR_KEY…"

    modal secret create paper-review-shared \
        BACKEND_WEBHOOK_SECRET="$BACKEND_WEBHOOK_SECRET"

    # Stripe key — only used for invoice generation. Use sk_test_ to start.
    modal secret create stripe-secret \
        STRIPE_SECRET_KEY="sk_test_…YOUR_KEY…"

    # Resend transactional email — get an API key at resend.com AND verify a
    # sending domain (e.g. mail.purplelink.llc) in the Resend dashboard.
    # These are two separate steps. Domain verification is NOT checked by
    # this codebase before sending: if the key is set but the domain isn't
    # verified yet, every send fails (Resend 403, surfaced by send_email()
    # as {"status": "error", "reason": "domain_not_verified"}), silently for
    # end users, until you complete the DNS/domain verification step.
    modal secret create resend-secret \
        RESEND_API_KEY="re_…YOUR_KEY…"

Deploy the backend (image will pick up pdfplumber / pdf2image / pillow / pypdf):

    (cd backend && modal deploy app.py)

The deploy logs will show the live URL. It should be
`https://ben-ampel--purplelink-latextools-web.modal.run` — same as today.

---

## 3. Netlify — environment variables (CLI)

Set the env vars on the production context. Use the same
`BACKEND_WEBHOOK_SECRET` you generated above:

    netlify env:set STRIPE_SECRET_KEY      "sk_test_…YOUR_KEY…" --context production
    netlify env:set BACKEND_WEBHOOK_SECRET "$BACKEND_WEBHOOK_SECRET" --context production
    # STRIPE_WEBHOOK_SECRET — leave empty for now, set after step 5.

    # One env var per Stripe Price ID created in step 1.4. The names below
    # are the env-var keys the checkout function looks up.
    netlify env:set STRIPE_PRICE_PAPER_REVIEW_STANDARD   "price_…"  --context production
    # paper-review-anonymity removed — anonymity now bundled free with Standard.
    netlify env:set STRIPE_PRICE_PAPER_REVIEW_JOURNAL    "price_…"  --context production
    netlify env:set STRIPE_PRICE_PAPER_REVIEW_DEEP       "price_…"  --context production
    netlify env:set STRIPE_PRICE_PAPER_REVIEW_PACK_5     "price_…"  --context production
    netlify env:set STRIPE_PRICE_PAPER_REVIEW_PACK_20    "price_…"  --context production
    netlify env:set STRIPE_PRICE_COVER_LETTER            "price_…"  --context production
    netlify env:set STRIPE_PRICE_ANONYMITY_CHECK         "price_…"  --context production
    netlify env:set STRIPE_PRICE_CITATION_GAP            "price_…"  --context production
    netlify env:set STRIPE_PRICE_REVISION_REVIEW         "price_…"  --context production
    netlify env:set STRIPE_PRICE_RESPONSE_REVIEW         "price_…"  --context production

Deploy the frontend so the new functions are live:

    bash scripts/deploy.sh   # or: netlify deploy --prod --dir site

---

## 4. End-to-end test (test-mode)

Visit the live site and test at least the Paper Review Standard tier and
one adjacent tool (e.g. Anonymity Check) — the 10 SKUs share the same
`checkout.mjs` / webhook / redemption code path, so two products is enough
to prove the plumbing, not all ten:

1. <https://purplelink.llc/tools/paper-review/> — click **Start review —
   $9** (Standard tier; price shown must match step 1's table).
2. Use Stripe's test card: `4242 4242 4242 4242`, any future expiry,
   any CVC, any ZIP.
3. After payment you should be redirected to
   `/tools/paper-review/upload/?session_id=…`
4. The upload page will show "Waiting on payment confirmation…" — the
   webhook needs to be wired up (next step) before this resolves.
5. Repeat against <https://purplelink.llc/tools/anonymity-check/> ($2) to
   confirm a second product key resolves through the same webhook.

---

## 5. Stripe webhook — wire it up (manual)

In the Stripe dashboard:

1. Developers → Webhooks → **+ Add endpoint**
2. Endpoint URL: `https://purplelink.llc/.netlify/functions/stripe-webhook`
3. Listen to: select event `checkout.session.completed` only.
4. Click **Add endpoint**.
5. On the new endpoint's page, reveal the **Signing secret** (`whsec_…`).

Set it in Netlify:

    netlify env:set STRIPE_WEBHOOK_SECRET "whsec_…YOUR_SECRET…" --context production

Re-deploy so the function picks up the new env var:

    netlify deploy --prod --dir site

---

## 6. End-to-end test (test-mode, with webhook)

1. Repeat step 4. After payment, the webhook should fire within ~1 second.
2. The upload page should resolve to **"Payment verified. Upload your
   manuscript below."**
3. Drag in any PDF (a short one is fine for testing — a single-page paper
   completes in ~3 minutes).
4. Pick a domain profile and click **Submit for review**.
5. You should be redirected to the status page, which polls every 5
   seconds. The 4 stage chips should light up in order.
6. Once done, the Markdown report renders inline. Download it.
7. Refresh the page — the result should be gone (one-shot retrieval).

If anything stalls or errors:
- Modal logs: `modal app logs purplelink-latextools` (look for
  `paper_review_pipeline` invocations).
- Netlify function logs: <https://app.netlify.com/projects/purplelink/logs/functions>
- Stripe webhook delivery log: dashboard → Developers → Webhooks → the
  endpoint → recent deliveries.

---

## 7. Going live (manual)

Once the test flow passes end-to-end:

1. Stripe dashboard → toggle to **Live mode**.
2. Re-create all 10 Products + Prices from step 1's table in live mode
   (test and live data don't share — every `price_…` from test mode is
   invalid in live mode).
3. Re-create the webhook endpoint in live mode (same URL).
4. Set the **live** keys in Netlify — one `STRIPE_SECRET_KEY` plus all 10
   per-product price-id vars from step 1:

       netlify env:set STRIPE_SECRET_KEY                   "sk_live_…"        --context production
       netlify env:set STRIPE_PRICE_PAPER_REVIEW_STANDARD  "price_…live" --context production
       netlify env:set STRIPE_PRICE_PAPER_REVIEW_JOURNAL   "price_…live" --context production
       netlify env:set STRIPE_PRICE_PAPER_REVIEW_DEEP      "price_…live" --context production
       netlify env:set STRIPE_PRICE_PAPER_REVIEW_PACK_5    "price_…live" --context production
       netlify env:set STRIPE_PRICE_PAPER_REVIEW_PACK_20   "price_…live" --context production
       netlify env:set STRIPE_PRICE_COVER_LETTER           "price_…live" --context production
       netlify env:set STRIPE_PRICE_ANONYMITY_CHECK        "price_…live" --context production
       netlify env:set STRIPE_PRICE_CITATION_GAP           "price_…live" --context production
       netlify env:set STRIPE_PRICE_REVISION_REVIEW        "price_…live" --context production
       netlify env:set STRIPE_PRICE_RESPONSE_REVIEW        "price_…live" --context production
       netlify env:set STRIPE_WEBHOOK_SECRET                "whsec_…live" --context production
       netlify deploy --prod --dir site

5. Activate the Stripe account if not already (Settings → Account →
   Activate) — this is also where you connect Mercury as the payout bank
   account (routing/account number entry happens here; do this step
   yourself, not via an agent).
6. Smoke-test the live flow with a real card against the cheapest SKU
   ($2 Anonymity Check or Cover Letter). Refund yourself afterward from
   the dashboard.

---

## Cost & margin tracking

Every completed (or errored) job writes a permanent record to the
`paper-review-usage-ledger` Modal Dict (`usage_ledger_dict` in `app.py`,
written by `_write_usage_ledger`), independent of `paper_jobs_dict` which is
deleted on first status read. Each record has: `product_key`, `status`,
`price_charged_usd`, `input_tokens`, `output_tokens`, `cost_usd` (computed
from `MODEL_PRICING_PER_MTOK` in `latextools/papercheck.py`), and `models`
(which model(s) actually served the job — relevant once the Fable ->
Opus 4.8 fallback starts firing). Records are also emitted as a structured
`usage_ledger {...}` log line, queryable via `modal app logs
purplelink-latextools`.

Pull real per-SKU COGS from that ledger (`modal dict items
paper-review-usage-ledger` or iterate via the Modal SDK) rather than
estimating. The prices in `PAID_PRODUCTS` (`backend/app.py`) were set
2026-07-03 off comment-estimated token counts, targeting a modest ~15-30%
net margin after Stripe fees on the Fable 5 model — treat them as
provisional until enough real ledger data exists to confirm actual COGS per
product key. If a SKU's real average COGS erodes that margin, the repricing
dial is two changes: the SKU's `STRIPE_PRICE_*` env var (point at a new,
higher-priced Stripe Price) and the visible price copy on that tool's
landing page — keep both in sync (see the price-mismatch note at the top of
`netlify/functions/checkout.mjs`).

## Refund + abuse playbook

- Refund requests come to ben@purplelink.llc — refund within 14 days of
  purchase, full amount, via the Stripe dashboard.
- If a customer disputes a charge, accept the chargeback (don't fight a
  $5 dispute — the dispute fee is higher than the charge).
- If a single email / IP submits >3 reviews in 24 hours and any look like
  abuse, manually invalidate the redemption tokens by deleting the
  matching entries from the Modal Dict:

      modal dict delete paper-review-tokens <session_id>

## Future work (out of v1 scope)

- Recovery flow for the rare case where the Stripe webhook doesn't reach
  Modal (currently the user must email; v1.1 should add a
  redeem-by-email fallback).
- A "review history" account for repeat customers.
- Tiered pricing — Quick (single layer) / Standard / Premium.
