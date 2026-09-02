# monthly_guide — MuscleOnGLP monthly research-review mini-guide

A Modal monthly cron that synthesizes the just-ended month's weekly research
roundups into a **new paid $1 PDF mini-guide** and auto-lists it for sale on
getmuscleonglp.com.

This is money-handling automation. Read this whole file before deploying or
running it live.

## What it does (once per month, 1st at 13:00 UTC)

1. Clones the private site repo `purplelink-llc/muscleonglp`.
2. Reads `research/index.json` + each `research/<slug>/index.html`, selects the
   roundups whose date falls in the just-ended month, and extracts the papers.
3. Synthesizes them into one cohesive, academic-voice guide
   (`synthesize.draft_monthly_guide`). **Iron rule:** it may only use facts,
   numbers, papers, and journals that appear in those already-vetted roundups.
4. Runs the same 4-pass red team as the flagship guide
   (`muscleonglp.redteam.run_redteam_passes`) and typesets to PDF
   (`muscleonglp.typeset.render_guide_pdf`).
5. Creates a Stripe Product + one-time **$1** Price (idempotent by
   `metadata[monthly_guide_slug]`).
6. Sets the site's `STRIPE_PRICE_*` env var so `checkout.mjs` can charge it.
7. Uploads the PDF to the `guide-files` Netlify Blobs store.
8. Appends the product to `lib/products.mjs`, writes the landing + success
   pages, adds a hub card to `guides/index.html`, and adds the sitemap URL.
9. Commits, pushes, `npm install`, `netlify deploy --prod`.
10. Emails Ben a review copy flagging that a **new paid guide is now live**.

Naming for month `YYYY-MM` (e.g. 2026-07):
- product key / slug: `research-review-2026-07`
- title: `GLP-1 & Muscle: Research Review, July 2026`
- Netlify env var: `STRIPE_PRICE_RESEARCH_REVIEW_2026_07`
- PDF blob key + filename: `research-review-2026-07.pdf`
- landing: `/guides/research-review-2026-07/`, success: `/success/research-review-2026-07/`

## Secrets / config the owner MUST add before the first run

### Modal secrets

Four of the five already exist (the weekly `research_digest` cron uses them):
`anthropic-secret`, `github`, `netlify`, `resend`.

The **only new Modal secret** this package needs is the Stripe key. An existing
Modal secret already exposes it: **`stripe-secret`** → `STRIPE_SECRET_KEY`
(used by `backend/setup_resume_review_price.py`). This package reuses that same
secret name, so **no new secret is required if `stripe-secret` already holds the
correct key**.

- **Which key:** it must be the **LIVE** `STRIPE_SECRET_KEY` for the same Stripe
  account that backs the muscleonglp site's Netlify `STRIPE_SECRET_KEY`. The
  Price this cron creates must be in the **same mode** (test vs live) as the key
  the site's `checkout.mjs` uses, or checkout fails with "No such price". Verify
  `stripe-secret` holds the live key before running live:
  `modal secret list` / re-create with `modal secret create stripe-secret STRIPE_SECRET_KEY=sk_live_...`.

### Modal scheduled-function cap (IMPORTANT)

Modal's free/starter tier allows **5 scheduled functions**. This cron is the
**5th and last** slot. Existing scheduled functions in this account include the
weekly roundup (`muscleonglp-research`) and the daily research digest, plus
others in `backend/app.py`. Before `modal deploy`-ing this app, confirm you are
not over the cap (`modal app list`), or a schedule will silently fail to
register. If you are at the cap, free a slot first.

### Netlify

- No new Netlify secret. The cron sets `STRIPE_PRICE_RESEARCH_REVIEW_YYYY_MM`
  itself via the Netlify env API (`netlify_api.set_env_var`) using the existing
  `NETLIFY_AUTH_TOKEN`. The token's account must have permission to edit env
  vars and write Blobs on site `c6201581-69ed-4da9-b982-c71c94d30260`.

### Stripe

- Nothing to pre-create — the cron creates the Product and Price. But confirm
  the account is in **live** mode and the webhook (`stripe-webhook.mjs`) is
  configured, since the new product is fulfilled the same way as the others.

## Testing (no charges)

`run_monthly_guide` supports `dry_run` (defaulted **on** in the local
entrypoint). A dry run clones the repo, synthesizes, red-teams, and renders the
PDF, then **stops before any Stripe / Netlify / commit / push / deploy / email**
and returns the in-container PDF path and the synthesized text.

```bash
# from backend/
modal run monthly_guide/app.py                    # dry run, just-ended month
modal run monthly_guide/app.py --month 2026-07    # dry run, a specific month
modal run monthly_guide/app.py --dry-run False     # LIVE: creates a paid product
```

Deploy the schedule (only when you are ready for it to run live monthly):

```bash
modal deploy monthly_guide/app.py
```

## Idempotency

Re-running for the same month does not duplicate anything:
- Stripe: product is looked up by `metadata[monthly_guide_slug]`; an existing
  active price is reused.
- Registry / hub card / sitemap: skipped if the slug is already present.
- Env var: updated in place if it exists.
- PDF blob and pages: overwritten with identical content.

## Files

- `roundups.py` — read the manifest + parse roundup post HTML into text.
- `synthesize.py` — `draft_monthly_guide(client, month_label, roundup_texts)`.
- `stripe_api.py` — `create_monthly_product(secret_key, title, slug) -> price_id`.
- `netlify_api.py` — `set_env_var(...)` and `blobs_set(...)`.
- `publish.py` — naming helpers + all filesystem edits (`list_monthly_guide`).
- `mailer.py` — `notify_new_guide(...)` review email.
- `app.py` — the Modal cron orchestration + local entrypoint.
