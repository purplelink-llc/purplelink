# /kits/ activation — owner steps

The two digital kits (Faceless Content Pipeline $79, Monetization Stack $39,
bundle $99) are fully built and deployed: landing page, two product pages, a
delivery-gated success page, and a paid-download function. Two owner-only steps
remain before checkout works, matching the pending-Stripe state of the other
paid tools.

## 1. Create the three Stripe prices and set the env vars

Create one Stripe Price per kit, then set these on the purplelink Netlify site
(production context), same as the other `STRIPE_PRICE_*` vars:

| Env var | Product | Price |
|---|---|---|
| `STRIPE_PRICE_KIT_FACELESS` | Faceless Content Pipeline | $79 |
| `STRIPE_PRICE_KIT_MONETIZATION` | Monetization Stack | $39 |
| `STRIPE_PRICE_KIT_BUNDLE` | Both kits | $99 |

`STRIPE_SECRET_KEY` is already shared with the rest of checkout. Until these are
set, the buy buttons return "misconfigured", exactly like the other paid tools.

## 2. Upload the two PDFs to the private `kit-files` Blobs store

The paid PDFs are **not** in the repo (it is public). They live locally at
`kits-delivery/*.pdf` and must be uploaded once to a private Netlify Blobs store
that `netlify/functions/kit-download.mjs` reads from:

```
NETLIFY_AUTH_TOKEN=... node kits-delivery/upload-to-blobs.mjs
```

That is the only place the files exist; `kit-download.mjs` streams them only
after verifying a paid Stripe session that includes the matching product.

## What is NOT done yet (future scope)

- The deliverable today is the **setup guide PDF**. If you want to also ship the
  genericized skill/code as a downloadable archive, add it to `kit-files` and to
  the `FILES` map in `kit-download.mjs` (the structure already supports it).
- Consider a license-acceptance checkbox at checkout for the software license
  (the paper-review flow has a TOS-store pattern to copy if you want it).

## Files

- Pages: `site/kits/{index,faceless-content-pipeline,monetization-stack,success}/`
- Delivery: `site/kits/success.js`, `netlify/functions/kit-download.mjs`
- Catalog: `netlify/functions/checkout.mjs` (`kit-faceless`, `kit-monetization`, `kit-bundle`)
- CSS: `.kit-*` block appended to `site/styles.css`
- Source PDFs + uploader: `kits-delivery/` (gitignored)
- PDF/LaTeX sources: session scratchpad `kitpdf/` (fonts, `purplekit.sty`, `kit-a.tex`, `kit-b.tex`)
