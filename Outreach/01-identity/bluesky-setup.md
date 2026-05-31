# Bluesky — `@purplelink.llc`

Bluesky lets you use a custom domain as your handle, which is the strongest identity signal of any social platform. We're going to use `@purplelink.llc` directly.

## Setup checklist

### Account
- [ ] https://bsky.app — sign up with `ben@purplelink.llc`
- [ ] Pick a temporary handle (e.g. `@purplelink.bsky.social`) — we'll replace it
- [ ] Verify email

### Profile
- [ ] **Display name:** `Purplelink`
- [ ] **Bio** (max 256 chars):
  > One-person software studio in Atlanta. Native macOS & iOS apps + free academic tools — LaTeX, BibTeX, citations, conversions. Privacy as architecture. Making software that lasts.
  >
  > purplelink.llc
- [ ] **Avatar:** `Social Media/assets/profile-light-1000.png`
- [ ] **Banner:** `Social Media/assets/cover-x-1500x500.png` (the X cover works at Bluesky's 1500×500 banner size too)

### Custom domain handle (the actual identity signal)

This is the move. After your account is created:

- [ ] In Bluesky: Settings → Account → Change Handle → "I have my own domain"
- [ ] Bluesky gives you a TXT record to add to DNS
- [ ] Add it to your purplelink.llc DNS (Netlify DNS panel)
- [ ] Verify in Bluesky; handle becomes `@purplelink.llc`

Detailed walkthrough: https://bsky.social/about/blog/4-28-2023-domain-handle-tutorial

The custom-domain handle is verifiable: anyone who sees `@purplelink.llc` on a post can be confident the account is genuinely the entity that controls the domain. No blue checkmark required.

## First 5 posts (post one per week, Tuesdays at noon ET)

### Post 1 — Intro
> Hello Bluesky. I'm Benjamin, building Purplelink LLC — a one-person software studio in Atlanta.
>
> Native macOS and iOS apps are on the way: ModernTex (LaTeX), Haea (on-device health), GlobePin (travel maps).
>
> Plus a growing set of free academic tools at purplelink.llc/tools.
>
> Hopefully I can be useful here.

### Post 2 — Anti-hallucinated-citations tool
> If you ever cite a paper that ChatGPT made up, your reader's reference manager will quietly fail to resolve it.
>
> Built a BibTeX validator that checks every entry against CrossRef + Semantic Scholar and flags low-title-match scores as likely hallucinations. Runs in your browser.
>
> purplelink.llc/tools/bib-validator

### Post 3 — Privacy commitment
> Haea (our on-device iOS health analytics app) cannot leak your data because the code that would leak it doesn't exist. No cloud sync, no third-party SDKs, no analytics calls.
>
> That's the architectural form of "we don't track you" — verifiable, not promised.
>
> purplelink.llc/haea

### Post 4 — On Mac LaTeX editors
> Published a comparison of the LaTeX editors that actually work on Mac in 2026 (TeXShop / Texifier / Octree / VS Code / Overleaf, plus what I'm building).
>
> Honest take: most academics should pick TeXShop. Polished and modern? Texifier. The waitlist version of my own answer is at purplelink.llc/moderntex.
>
> Full comparison: purplelink.llc/guides/best-mac-latex-editors

### Post 5 — Behind the build
> Why one person, building three apps and a tools site?
>
> Because every decision is a craft decision. No growth team optimizing for engagement; no investor clock forcing the next pivot. The software gets to last longer than any quarterly OKR.
>
> Curious whether others building solo feel the same trade-offs.

## After registering — give me the URL

`https://bsky.app/profile/purplelink.llc` once the custom handle is set up. I'll add it to the homepage Organization `sameAs`.
