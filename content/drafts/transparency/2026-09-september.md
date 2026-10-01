# Purplelink — September 2026 Transparency Report

## What Shipped

**ModernTex became a real paid product.** It had been a free trial through the summer. On September 4 it went paid: a $10 Stripe checkout, a license key issued by the webhook, gated delivery, a private Sparkle update channel. Two releases followed — 1.2.0 on the 12th (TikZ Designer, a live TikZ preview, a user guide) and 1.3.0 on the 13th (a Table Editor). ([e5fd842c](https://github.com/purplelink-llc/purplelink/commit/e5fd842c), [e54d518f](https://github.com/purplelink-llc/purplelink/commit/e54d518f))

**Two new subscription products**: Vitae Plus got subscription checkout with offline-verified license keys; Daily Digest got a paid tier with its own Stripe Customer Portal for billing.

**Two new free tools** — Thesis Format Checker and Abstract Checker (word limits for 25 venues) — bringing the tools count to 26.

**Revenue outside the core software.** A `/sheets/` store opened with four paid spreadsheets ($9–$39). The stock-photo side business got real automation: per-sale ledgers and collectors across eight platforms, mostly scraped over a browser connection since most have no usable API. Three waitlist pages went up for products that don't exist yet, to see if anyone asks before anything gets built.

**A site-wide quality pass found things that had been wrong for a while.** Dark mode became the sitewide default (light is now the opt-out). Three audits late in the month — a "day-one" pass, a simulated lab-buyer walkthrough, a customer-eyes review — found dead nav links on 226 pages, stretched screenshots, dark-mode contrast failures, 69 literal `[SCREENSHOT: ...]` placeholders in published guides, and 25 wrong factual claims about the products. All live before anyone looked. ([c94fd105](https://github.com/purplelink-llc/purplelink/commit/c94fd105), [35b42f0a](https://github.com/purplelink-llc/purplelink/commit/35b42f0a))

**Content**: 7 blog posts, 10 guides, 28 Daily Digest issues (#69–#96), 4 LinkedIn posts.

---

## What We Decided (and Why)

**Dark as the sitewide default, not an opt-in.** The alternative was leaving it a toggle most visitors never find — the same mistake July's report described for the Kits nav link. Making it the default meant every page had to hold up in dark mode, which is exactly what the audit then found wasn't true everywhere. The decision came first; its cost showed up two weeks later as bug fixes.

**Write up the webhook failure as a documented incident, not a quiet patch.** On September 5 the Stripe webhook rejected every delivery over a wrong signing secret, and four ModernTex buyers never got their download email. I wrote a full account into the runbook instead of just fixing the secret: the same failure on Paper Review, whose entitlement is written by that webhook with no fallback, would leave a paying customer with no product and no refund.

**Expand into stock photography and spreadsheets instead of only deepening Paper Review.** A deliberate choice to diversify with mostly-automated work, and not spend the whole month on one funnel. The tradeoff is real: every new income stream is a new dashboard and a new thing that can silently break.

---

## What Didn't Work

**The webhook failure cost four buyers their email, and nothing noticed.** The alert code sits past the signature check, so a rejected delivery can't trigger it. Netlify's function logs showed zero invocations for the affected sales — simply wrong, and it sent the first hour of investigation nowhere. The sales themselves weren't lost; only the buyers' way back in for a reinstall or update.

**The audits found things that should not have shipped at all.** Retention copy across every paid-tool page said results are deleted "the moment you retrieve it." The code keeps them 30 minutes after first opening, or 24 hours unopened — a false claim about data handling, not a typo, that sat live for weeks until a simulated customer review caught it.

**No August transparency report.** This file is a month late. The report that should have covered August and published September 1 simply didn't happen, dropped in the middle of the ModernTex launch push, no better reason than that.

**PRODUCT.md and DESIGN.md still don't exist.** Our own process docs have instructed every design session to read these two root files before frontend work. Neither has ever existed in this repository. Design decisions have been running on a remembered summary, not the source documents.

---

## By the Numbers

- **636 commits** since September 1 (July had 50)
- **639 files changed, 76,796 insertions, 5,138 deletions**, excluding the automated daily digest
- **120 feat, 70 fix commits** — nearly two fixes for every three features, tracking how much of the month was audit-driven cleanup
- **28 Daily Digest issues** (#69–#96); **7 blog posts, 10 guides**
- **ModernTex: free trial to paid**, 2 feature releases inside the month
- **4 new paid spreadsheets, 1 new subscription tier, 2 new free tools, 3 waitlist pages, 26 tools total**
- **Revenue**: [INSERT: September revenue by product, Stripe dashboard]
- **Traffic**: [INSERT: September unique visitors from analytics]
- **ModernTex trial-to-paid conversion**: [INSERT: from the trial funnel in the owner dashboard]

---

## What We Learned

**A site-wide quality pass finds the same bug class a single-product audit finds, just at scale.** July's lesson was that holding someone else's money changes how carefully you read your own work. September showed stale screenshots, wrong retention claims, and dead nav links accumulate anywhere nobody is deliberately re-reading as a stranger — on a growing site, that's most of it, most of the time.

**A failure with no alarm is worse than a louder one.** The webhook bug wasn't hard to find once someone looked at the Stripe dashboard. The problem was nothing routed attention there — and tooling that actively says "nothing happened" when something did is worse than tooling that says nothing at all.

**Diversifying revenue is cheap to start and expensive to keep running.** Adding a stock-photo collector or a spreadsheet listing takes an afternoon. Keeping five of them correct — ledgers, dashboards, credentials, platform quirks — is a standing cost that shows up later, as drift.

---

## What's Next

**Put a real alert on webhook health.** Done means a scheduled check reads the Stripe deliveries data and sends an alert within the hour if an endpoint starts failing, tested by deliberately rotating a secret in a test environment and confirming the alert fires. September 5 was caught by luck.

**Write PRODUCT.md and DESIGN.md for real.** Done means both files exist at the repo root, DESIGN.md reflects the current `site/styles.css` rather than a remembered version of it, and design work reads them instead of working from memory.

**Close the transparency-report gap for good.** Done means the October report runs on November 1 without a note like this one explaining why a month got skipped.
