# Purplelink LLC — Project Instructions

## Design Context

This project uses the **impeccable** design skill. Before any frontend or
design work, read the two root context files:

- **`PRODUCT.md`** — strategic context: register (`brand`), audiences
  (academic researchers + Apple-platform users), product purpose, brand
  personality (calm · craftsmanlike · trustworthy), anti-references, and the
  5 design principles.
- **`DESIGN.md`** — the visual system captured from `site/styles.css`: OKLCH
  purple palette (hue 310), Fraunces display + Plus Jakarta Sans body, pill
  buttons, radius scale, dark-mode behavior, motion rules.

**Hard constraints (from DESIGN.md — never violate):**

- **Strict CSP: `style-src 'self'` — no inline styles, ever.** All styling in
  external stylesheets. New external origins must be added to `netlify.toml`'s
  CSP header first.
- **No emojis** in UI copy (the site was deliberately de-emoji'd).
- **No AI-tell prose / marketing buzzwords / em-dash tics.** Voice is calm,
  plain, specific. Say what the product literally does.
- **WCAG 2.1 AA** contrast minimums; keyboard nav; `prefers-reduced-motion`
  honored on all motion.
- Self-host fonts and scripts; no third-party CDN loads.

**AdSense exception (explicit, owner-authorized, 2026-07-03):** the CSP hard
constraint above is deliberately relaxed sitewide — `style-src 'self'
'unsafe-inline'` plus the Google/AdSense origins
(`pagead2.googlesyndication.com`, `googleads.g.doubleclick.net`,
`www.google.com`, `www.gstatic.com`, `www.googletagservices.com`,
`tpc.googlesyndication.com`) in `img-src`/`script-src`/`connect-src`/
`frame-src` — so Google AdSense can render. This was reverted once by an
automated security sweep for contradicting the "never violate" wording above;
the site owner (Ben) explicitly re-authorized it and said this specific
policy may be violated for AdSense. Do not silently revert this again — if a
future audit flags it, surface this note rather than reverting.

Invoke design work with the impeccable skill (e.g. `/impeccable critique
/tools/word-counter/`, `/impeccable audit`, `/impeccable polish`).

## Deploy

- Frontend: `bash scripts/deploy.sh` (Netlify `--prod` + IndexNow ping).
- Backend (Modal): `bash scripts/deploy.sh --backend`.
- The site is live at https://purplelink.llc.

## Paid tools status

Paid manuscript tools (Paper Review + adjacent) are built but **checkout is
disabled** ("Coming soon" buttons) pending Stripe activation. Modal secrets
are placeholders — set real values before enabling. See
`docs/paper-review-runbook.md` and `docs/security-paper-review.md`.
