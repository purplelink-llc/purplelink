# GitHub Org — `purplelink-llc`

**Target:** `github.com/purplelink-llc` · **Alt names if taken:** `purplelinkhq`, `getpurplelink`

## Setup checklist

- [ ] Sign in to GitHub (personal account)
- [ ] https://github.com/account/organizations/new — create an org
- [ ] **Name:** `purplelink-llc`
- [ ] **Plan:** Free
- [ ] **Avatar:** `Social Media/assets/profile-light-1000.png` (already generated)
- [ ] **Description** (max 200 chars): `One-person software studio in Atlanta. Native macOS & iOS apps + free academic tools.`
- [ ] **Website:** `https://purplelink.llc`
- [ ] **Email:** `ben@purplelink.llc`
- [ ] **Twitter/X:** (your handle if you have one)

## Initial repo seed plan

You don't need to open-source the whole site to make the org useful as an identity signal. Three repos is enough:

### Repo 1: `.github` (org-level profile README)

Create a public repo literally named `.github` — the README inside it becomes the org's public profile page. Paste this README:

```markdown
## Purplelink LLC

One-person software studio in Atlanta, Georgia. Native macOS and iOS apps, applied AI tools, and free web utilities for academic writing.

**Website:** https://purplelink.llc
**Founder:** Benjamin Ampel
**Atlanta · Est. 2026**

### Products in development

- **[ModernTex](https://purplelink.llc/moderntex/)** — native macOS LaTeX studio for researchers (2026)
- **[Haea](https://purplelink.llc/haea/)** — on-device iOS health analytics (2026)
- **[GlobePin](https://purplelink.llc/globepin/)** — travel mapping for iOS with a 3D globe (2026)

### Free tools

Compile LaTeX to PDF, convert to/from Word, validate BibTeX, render equations, and more. All run in your browser; nothing is stored.

→ https://purplelink.llc/tools/

### Free guides

How-to guides for the academic LaTeX workflow plus topic hubs for [LaTeX](https://purplelink.llc/guides/latex/) and [BibTeX](https://purplelink.llc/guides/bibtex/).

→ https://purplelink.llc/guides/

### Philosophy

Making software that lasts. Privacy as an architectural constraint, not a marketing position.
```

### Repo 2: `scholar-utility-belt` (the Chrome extension)

If the source is available, transfer it from the personal account to the org. If not, mirror or skip.

### Repo 3: `purplelink-llc` (the marketing-site repo — optional)

Push the existing site repo here. Risk: any secrets in the repo become public. **Audit first** — check for the Cloudflare token (which is publicly fine, it's in the HTML), any Modal auth tokens, any local-only config. Use `git-secrets` or a manual scan.

If you'd rather not open-source the site, that's fine — just have the empty repo or skip this entirely. The `.github` README alone is enough for the identity signal.

## After registering — give me the URL

Paste it back to me and I'll add `https://github.com/purplelink-llc` to the homepage Organization `sameAs` JSON-LD array.
