# Template-tier activation (Tracker $12 + Workbook $19)

**STATUS: LIVE (2026-07-16).** Both products are fully activated and selling on
getmuscleonglp.com/guides. Live Stripe prices were created, env vars set on the
muscleonglp production context, PDFs uploaded to the `guide-files` Blobs store,
and the site deployed. Both checkouts were verified returning live `cs_live_`
sessions. Live price IDs (same shared Stripe account as purplelink):

- `STRIPE_PRICE_TRACKER`  = `price_1TtziNJkzNxf3fKqnSGdrNLN` ($12.00)
- `STRIPE_PRICE_WORKBOOK` = `price_1TtziNJkzNxf3fKqXjjhKmX6` ($19.00)

The steps below are retained as the reference procedure (e.g. to change a price
or re-upload a regenerated PDF). Do NOT recreate the Stripe prices.

---

Owner checklist (historical) to switch on the two new MuscleOnGLP products.
These are the account-side steps that only the owner can do (create Stripe
Prices, set env vars, upload the PDFs). Until all three are done, the Buy buttons
return a checkout error.

The two products follow the exact same single-file download/webhook path as the
existing guides. The single source of truth is
`muscleonglp-site/netlify/functions/lib/products.mjs`, which now contains:

| Product key | envKey                  | file (Blobs key)               | successPath          | price |
|-------------|-------------------------|--------------------------------|----------------------|-------|
| `tracker`   | `STRIPE_PRICE_TRACKER`  | `muscle-on-glp1-tracker.pdf`   | `/success/tracker/`  | $12   |
| `workbook`  | `STRIPE_PRICE_WORKBOOK` | `muscle-on-glp1-workbook.pdf`  | `/success/workbook/` | $19   |

The PDFs are staged (not deployed) at:

- `muscleonglp-site/private/muscle-on-glp1-tracker.pdf`  (12 pages)
- `muscleonglp-site/private/muscle-on-glp1-workbook.pdf` (20 pages)

Regenerate them any time with:

```
python3 muscleonglp-site/private/generate_template_tier.py
```

---

## 1. Create the two Stripe Prices

In the Stripe Dashboard (the same account/mode — live vs. test — that the
existing `STRIPE_PRICE_*` values use), create two one-time Prices:

- **The Muscle-on-GLP-1 Tracker** — one-time, **USD 12.00**.
- **The Muscle-on-GLP-1 Workbook** — one-time, **USD 19.00**.

Copy each Price ID (looks like `price_1AbC...`). Use the **Price** ID, not the
Product ID.

## 2. Set the two environment variables

The checkout function reads the Price ID from a Netlify environment variable
per product. Set both on the MuscleOnGLP Netlify site.

Run from inside `muscleonglp-site/` so the Netlify CLI targets the right site
(the monorepo has a per-directory `.netlify` link — do not run these from the
repo root, or they may hit the purplelink site):

```
cd muscleonglp-site
netlify env:set STRIPE_PRICE_TRACKER  price_XXXXXXXXXXXX
netlify env:set STRIPE_PRICE_WORKBOOK price_YYYYYYYYYYYY
```

(Or set them in the Netlify UI: Site settings → Environment variables. Match
the deploy context of the other `STRIPE_PRICE_*` vars.)

## 3. Upload the two PDFs to the `guide-files` Blobs store

The purchasable PDFs are never deployed with the site; `download.mjs` streams
them from the `guide-files` Netlify Blobs store after verifying a paid session
and a recorded Terms acceptance. The Blobs key must match the `file` value in
`products.mjs` exactly.

Run from inside `muscleonglp-site/` (same per-directory link reason as above):

```
cd muscleonglp-site
netlify blobs:set guide-files muscle-on-glp1-tracker.pdf  --input private/muscle-on-glp1-tracker.pdf
netlify blobs:set guide-files muscle-on-glp1-workbook.pdf --input private/muscle-on-glp1-workbook.pdf
```

If you prefer to run from the repo root, point `--input` at the full path
instead (the Blobs key — the second argument — must stay the bare filename):

```
netlify blobs:set guide-files muscle-on-glp1-tracker.pdf  --input muscleonglp-site/private/muscle-on-glp1-tracker.pdf
netlify blobs:set guide-files muscle-on-glp1-workbook.pdf --input muscleonglp-site/private/muscle-on-glp1-workbook.pdf
```

## 4. Deploy and smoke-test

Deploy the site (the product pages, success pages, listing links, cover images,
sitemap, and `products.mjs` change are all in the tree). Then:

1. Visit `/guides/tracker/` and `/guides/workbook/`; confirm the cover images
   load and the Buy button is present.
2. Tick the Terms checkbox and click Buy; confirm it opens Stripe Checkout at
   the right price ($12 / $19).
3. Complete a test purchase (Stripe test mode) and confirm the success page
   serves the correct PDF and that the confirmation email links to it.

---

## Notes

- **Cover images** (`assets/cover-muscle-on-glp1-tracker.png`,
  `assets/cover-muscle-on-glp1-workbook.png`) are generated from the PDF cover
  pages and are deployed with the site (they are referenced by the product
  pages and the og:image/twitter:image tags). Re-render them if the PDF covers
  change:
  `python3 -c "import fitz; [fitz.open(s)[0].get_pixmap(dpi=150).save(d) for s,d in [('muscleonglp-site/private/muscle-on-glp1-tracker.pdf','muscleonglp-site/assets/cover-muscle-on-glp1-tracker.png'),('muscleonglp-site/private/muscle-on-glp1-workbook.pdf','muscleonglp-site/assets/cover-muscle-on-glp1-workbook.png')]]"`
- No new Netlify redirect is needed: `/success/tracker/` and
  `/success/workbook/` are static directories, and the `download-link.js` on
  each success page builds the download URL from the Stripe `session_id`.
- Content is sourced entirely from the site's existing `learn/` articles; every
  figure in both PDFs is cited on the workbook's References page. Both carry a
  visible "educational, not medical advice" disclaimer.
