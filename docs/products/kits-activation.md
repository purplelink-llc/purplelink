# /kits/ — live status and pricing

Both kits are **live and fully activated** on purplelink.llc/kits: landing page,
two product pages, delivery-gated success page, paid-download function, Stripe
prices, and gated file delivery. Each kit now ships **full source code plus the
typeset setup guide** (not the guide alone).

## Launch pricing (current)

Honest introductory pricing: the launch prices are the real Stripe prices being
charged, and the pages state a genuine upcoming increase (no fabricated "was"
reference price).

| Kit | Product key | Launch price | Regular (rises to) |
|---|---|---|---|
| Faceless Content Pipeline | `kit-faceless` | **$49** | $79 |
| Monetization Stack | `kit-monetization` | **$29** | $39 |
| Both-kits bundle | `kit-bundle` | **$59** | $99 |

Bundle is always the best value: buying the two at launch prices is $78, the
bundle is $59.

### Stripe price IDs (live mode)

Env vars on the purplelink Netlify site (production context) point at the
**launch** prices. The regular prices already exist on the same Stripe products;
to end the launch, repoint each env var back to the regular price ID and redeploy.

| Env var | Launch price ID (current) | Regular price ID (revert target) |
|---|---|---|
| `STRIPE_PRICE_KIT_FACELESS` | `price_1TtzmDJkzNxf3fKqorp62MHv` ($49) | `price_1TtzGMJkzNxf3fKqU8ahKYsH` ($79) |
| `STRIPE_PRICE_KIT_MONETIZATION` | `price_1TtzmDJkzNxf3fKqZLhAa6yv` ($29) | `price_1TtzGNJkzNxf3fKqCDlXwo8x` ($39) |
| `STRIPE_PRICE_KIT_BUNDLE` | `price_1TtzmDJkzNxf3fKqKFuooKsO` ($59) | `price_1TtzGNJkzNxf3fKqdC9TclsT` ($99) |

To end the launch: repoint the three env vars to the regular IDs, then update the
displayed prices in `site/kits/` (the `.kit-price`, `.kit-launch-note`, the
`kit-price-strike`, the CTA buttons, the meta descriptions, and the JSON-LD
`offers.price`), and remove the `.kit-launch-note` lines. All three checkouts were
verified returning live `cs_live_` sessions at the launch prices.

## Delivery

`netlify/functions/kit-download.mjs` streams four files from the private
`kit-files` Netlify Blobs store after verifying a paid session, one guide PDF and
one source ZIP per kit:

- `faceless-content-pipeline-guide.pdf` + `faceless-content-pipeline-source.zip`
- `monetization-stack-guide.pdf` + `monetization-stack-source.zip`

The bundle grants all four. The success page lists whatever the function returns,
so no page change is needed when files change. The source archives and PDFs live
only locally at `kits-delivery/` (gitignored) and in the Blobs store; they are
never in the public repo. Re-upload after regenerating with:

```
node kits-delivery/upload-to-blobs.mjs   # needs NETLIFY_AUTH_TOKEN; skips missing files
```

## Source packages (what buyers download)

The genericized, de-branded source lives at `kit-src/` (gitignored):

- `kit-src/faceless-pipeline/` — the compliance-safe faceless video pipeline
  (fetch → curate → render → drip-post), config-driven, no brand/keys. Zipped to
  `faceless-content-pipeline-source.zip`.
- `kit-src/monetization-stack/` — cookieless analytics (beacon + two functions +
  dashboard), affiliate auto-tagger, AdSense config templates, README. Zipped to
  `monetization-stack-source.zip`.

Both passed a brand/PII/secret leak scan (zero hits) and compile/parse cleanly.

## Files

- Pages: `site/kits/{index,faceless-content-pipeline,monetization-stack,success}/`
- Delivery: `site/kits/success.js`, `netlify/functions/kit-download.mjs`
- Catalog: `netlify/functions/checkout.mjs` (`kit-faceless`, `kit-monetization`, `kit-bundle`)
- CSS: `.kit-*` block in `site/styles.css`
- Source (gitignored): `kit-src/`; deliverables + uploader (gitignored): `kits-delivery/`
