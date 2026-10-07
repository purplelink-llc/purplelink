# Where to spend about $300 of ad money: research, 2026-10-07

Scope: research only. Nothing was bought, posted, signed up for or changed. Prepared 2026-10-07.

## How to read this report

- **[S]** means a sourced figure, with the URL and the date of the source (or the date I read it, when the page is undated).
- **[E]** means my estimate. Estimates are built from sourced figures plus stated assumptions. They are not data.
- **not found** means I looked and could not get a number. I did not fill the gap.
- Source quality is uneven. Most 2026 ad-cost benchmarks come from agencies and ad vendors who sell the thing they are benchmarking. Where I could only read a search-result summary and not the page itself, I say so.
- Keyword-level CPCs for the specific phrases you asked about are **not available for free**. Google Keyword Planner needs an account, and Ahrefs, Semrush and SpyFu pages returned no data to my fetches (JavaScript or HTTP 403). Section 1 therefore gives sourced category benchmarks, your own observed CPC, and labelled estimates per keyword group. The first week of the Google test is the real measurement.

## 0. Local context (read, not repeated)

Read: PRODUCT.md, docs/reddit-notes-2026-09-29.md, the docs/growth-briefs/ file names, and the docstring of scripts/traffic-dashboard/ads_optimizer.py. The ad tooling that exists:

- `ads_optimizer.py` is advisory only and covers Apple Search Ads keywords for GlobePin. Nothing equivalent exists for Google Ads.
- `record_google_ads.py` copies ModernTex Google Ads totals from the signed-in Google Ads page into `~/.purplelink/traffic/manual-ads.json`.
- `docs/growth-briefs/experiments.json` already holds a rule: fewer than 5 conversions is weak evidence, so no spend increase. `docs/growth-briefs/product-screen.md` says no ad budget for products that fail its screening tests. I follow both rules below.

Local figures that matter (all [S], from `~/.purplelink/traffic/manual-ads.json` and the dashboard text, read 2026-10-07):

| Figure | Value |
|---|---|
| ModernTex Google Ads, last 7 days | $4.31, 329 impressions, 8 clicks, average CPC $0.54 |
| ModernTex Google Ads, all time | $15.69, 1,789 impressions, 48 clicks. The file stores the all-time CPC as 0.0 (a bug), so the true figure is $15.69 / 48 = about $0.33 [E, simple division] |
| Click-through rate, all time | 48 / 1,789 = 2.7% [E, division] |
| GlobePin Apple Search Ads, last 7 days to 2026-10-05 | $40.47, 49 taps, 15 installs, $2.70 per install, 0 paid Pro |

**Correction to the "5 sales on $4.31" figure.** The dashboard says its Google Ads comparison "compares total ad spend against all ModernTex purchases in the window, not just ones Google Ads attributes to a click." Eight clicks cannot plausibly produce five sales. Treat the Google Ads result as: cheap clicks (about $0.33 to $0.54), sales not yet attributed. The 5-sales number is not evidence about ad conversion. The first job of the test is to attribute sales to ads (gclid or UTM stored on the Stripe Checkout Session).

## 1. Google Ads Search

### 1a. Sourced cost and conversion benchmarks

| Benchmark | Value | Source and date |
|---|---|---|
| All-industry search CPC | $5.42 | WordStream/LocaliQ 2026 data (Apr 2025 to Mar 2026), as quoted at https://megadigital.ai/en/blog/google-ads-benchmarks/ (2026-06-26) [S]. WordStream's own page returned 403 to me. |
| All-industry search CTR and conversion rate (lead-type) | 6.64% CTR, 8.18% conversion | Same page [S] |
| Education and Instruction | CPC $4.81, CTR 7.56%, conversion 13.14%, cost per lead $77.48 | https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry (updated 2026-09-22) [S] |
| Business Services | CPC $5.87, conversion 4.85%, cost per lead $93.69 | Same page [S] |
| Method caveat | The WordStream sample blends Google and Microsoft Ads and is its own clients, not the whole market. No separate software or consumer-software category is published. | Same page [S] |
| B2B/SaaS CPC, Google vs Microsoft | $3.33 vs $2.10 | https://theadspend.com/blog/google-ads-vs-microsoft-ads-2026 (2026), read only through a search-result summary [S, weak] |
| Average CPC, Microsoft vs Google | $1.54 vs $2.69; cost per conversion $31 vs $45 | Same summary, searchlab.nl and others (2026) [S, weak] |
| Cybersecurity category CPC | $16 to $22 on category terms; $8 to $14 for small-ACV (under $25k) vendors; $80 to $200+ on vendor-comparison queries | https://www.growthspreeofficial.com/blogs/google-ads-cybersecurity-saas-high-cpc-2026 (published 2026-05-14, Q1 2026 data). Publisher is a B2B SaaS ad agency [S, weak] |
| SaaS trial-signup conversion from search | about 2% to 5% | Search-result summary of opascope.com and similar (2026); not opened [S, weak] |
| Opt-in free trial to paid, median | 8.9% (ChartMogul via fungies.io, 2026) to 18.5% (other summaries) | https://fungies.io/?p=38262 and search summaries (2026) [S, weak]. Your own ModernTex figure is about 15% (given). |
| Conversion rate of search clicks to a $10 to $30 one-time Mac software purchase | **not found** | No published benchmark exists that I could find. |

### 1b. Keyword groups: what to expect

No keyword-level CPC could be sourced. The ranges below are **[E]** and are anchored on: your observed $0.33 to $0.54 on ModernTex keywords, the cybersecurity benchmarks above, and the general rule that CPC tracks how much the advertisers on that query earn per customer. For example, CleanMyMac sells subscriptions from $34.95 a year and one-time licenses from $89.95 (https://cleanmymac.com/blog/mac-disk-space-analyzer, read 2026-10-07 via search summary [S]), so those advertisers can afford higher bids than a $9.99 app can.

| Keyword group | CPC estimate [E] | Intent | Verdict for $5 to $10 a day |
|---|---|---|---|
| "latex editor mac", "mac latex editor", "texstudio mac", "latex for mac" | $0.20 to $0.80 | High: person wants an editor on a Mac now | Cheap and high intent. Start here. Your live campaign is already near this range. |
| "texshop alternative", "texpad alternative", "texifier alternative", "texstudio alternative" | $0.20 to $1.00 | High: person is leaving a specific tool | Cheap, small volume. Good for exact match. |
| "overleaf alternative", "overleaf offline", "overleaf alternative mac" | $0.50 to $2.00 | High but wider: price, compile timeout and privacy pushers. Reddit notes show the Overleaf compile timeout drives people local (r/LaTeX, 2026-09-23). | Worth a test with "mac" or "offline" in the phrase. Overleaf's own brand terms are brand-dominated; do not bid on "overleaf" alone. |
| "latex editor" (no "mac") | $0.50 to $1.50 | Mixed: Windows, Linux, online editors; most clicks cannot use a Mac app | Wasteful. Skip, or add "mac" phrase-match only. |
| "pii redaction software", "data redaction tool" | $8 to $22 | Enterprise and API buyers | Too expensive. A $29.99 app needs a CPC under about $0.60 to break even. |
| "prevent sending sensitive data email", "data loss prevention software" | $8 to $22 | Enterprise IT buyers | Too expensive. Same reason. |
| Long-tail consumer phrasing ("warn before pasting social security number mac", "stop sending SSN in email") | $0.30 to $2.00, but very low volume | Real problem, few people searching it | Only worth a small test. Volume may read "low search volume". |
| "disk space analyzer mac" | $0.50 to $2.00 | High, but the field is DaisyDisk, CleanMyMac and others | Hard at $9.99. |
| "mac cleaner" | $1.00 to $4.00 | Broad, crowded with security and cleaner vendors | Too expensive for $9.99. |
| "mechanical keyboard sound app mac", "keyboard click sound mac" | $0.20 to $0.80, volume probably in the tens per month | Niche, curious rather than urgent | Cheap but too small to learn from. |
| Academic CV, grant, tenure, "submission tracker" terms | $0.30 to $1.50 | Low commercial intent; the product is free | Do not advertise a free product with a $2.99 optional plan. |

### 1c. What to expect per click, trial and sale (all [E])

Assumptions: product page to checkout click is 4.4% (your figure). Checkout-click to paid is unknown; I assume 40% to 70%, midpoint 50%. Stripe's standard US card fee is 2.9% plus $0.30 [S, from memory of Stripe's public pricing; verify in your account]. Ad traffic may convert better or worse than your organic search traffic.

| App | Price | Net after Stripe | Click to sale | Break-even CPC (net x click-to-sale) |
|---|---|---|---|---|
| ModernTex | $19.99 | about $19.11 | 1.8% to 3.1% (mid 2.2%) | $0.34 to $0.59 (mid $0.42) |
| Outbound Veil | $29.99 | about $28.82 | 1.5% to 2.2% [E, assumed lower: newer, less specific traffic] | $0.43 to $0.63 |
| Legroom, Keyfeel | $9.99 | about $9.40 | 1.8% to 3.1% | $0.17 to $0.29 |
| Mac Suite | $54.99 | about $53.10 | 0.8% to 1.5% [E, higher price, lower rate] | $0.42 to $0.80 |

Cost per sale = CPC / click-to-sale rate. For ModernTex at 2.2%:

| CPC | Cost per sale | Against $19.11 net |
|---|---|---|
| $0.33 (your all-time) | about $15 | Small profit |
| $0.54 (your last 7 days) | about $25 | Loss on the first purchase |
| $0.80 | about $36 | Loss |
| $1.50 | about $68 | Large loss |

Cost per trial: if 5% to 15% of ad clicks start a trial [E, no data; unknown until the download event is tracked], then at $0.33 to $0.54 CPC a trial costs about $2 to $11. At your 15% trial-to-paid, that is about $15 to $73 per sale via trials. This is wider than the direct estimate and the two paths overlap, so do not add them.

Reading: ModernTex ad economics sit right at break-even at your current CPC. They work only if the CPC stays near $0.35 to $0.50 and the page keeps converting. Every other app is worse on paper (section 4).

Useful price anchor for ad copy: Overleaf Standard is $16.75 a month or $199 a year, Professional $42 a month or $399 a year (https://www.overleaf.com/user/subscription/plans, search summary, 2026 [S]). ModernTex is a one-time $19.99.

## 2. Other channels

"Sub-$300 realistic" means a test that produces a readable result for under $300 total.

| Channel | Minimum and price [S unless marked] | Source and date | Fit by app | Sub-$300 test realistic? |
|---|---|---|---|---|
| **Reddit Ads** | Platform minimum $5 a day. CPC reported anywhere from $0.20 to $3.00, depending on the source: $0.44 (daily.dev, 2026-05-22); $0.20 to $0.60 retail (webtonic.io, updated 2026-10-04); $0.50 to $2.50 broad, $1.50 to $4.00 tech and SaaS communities, CPM $6 to $12 (stackmatix.com, 2026-09-11); $1.80 tech average, $2.00 SaaS average (benly.ai, 2026-03-24). Niche subreddits run 30% to 50% below median CPM (affectgroup.com, updated 2026-06-22). Vendors suggest $500 to $5,000 test budgets, but the platform minimum is $5 a day. | URLs as named | ModernTex: good topical fit (r/LaTeX, r/PhD, r/GradSchool, r/AskAcademia; the reddit notes show live Overleaf frustration). Outbound Veil: weak. Legroom, Keyfeel: r/macapps fits but price is too low. Vitae: free app, so no. | Yes, as a learning test. At 2.2% click-to-sale, break-even CPC is about $0.42, below most Reddit CPC figures. Expect it to lose money and use it to measure trial starts. |
| **EthicalAds** | $1,000 minimum ad buy. CPM $3.00 (all developers, run of network) to $7.50 (custom niche, US/Canada/UK/ANZ/Ireland); security/privacy $6.95. Not fully self-serve. | https://www.ethicalads.io/advertisers/pricing/ (Q3 2026, read 2026-10-07) | Developer audience. Poor for all five apps. Outbound Veil is the only nearby fit, via the security/privacy topic. | No. Minimum is above the whole budget. |
| **Carbon Ads** | CPM about $6 (rest-of-world blend); the interactive Carbon Cover unit needs $5,000 a month; 1,000,000 monthly impressions recommended; prepayment. The FAQ states no general minimum. | https://carbonads.net/more-info and /faq (search summaries, read 2026-10-07) | Developers and designers. Poor fit. | No. |
| **BuySellAds** | not found | | | not found |
| **daily.dev** | CPM $35 to $60, CPC $2 to $8 (vendor's own benchmark page, so biased). | https://business.daily.dev/resources/developer-paid-media-benchmarks-2026-cpm-cpc-ctr-by-channel/ (2026-05-22) | Developers. Poor fit. | No, CPC far above break-even. |
| **Daring Fireball sponsorship** | $12,000 a week, one sponsor, RSS post plus sidebar. About 150,000 weekday visitors and 200,000 RSS subscribers claimed. | https://daringfireball.net/sponsors (read 2026-10-07) | Mac audience, all consumer apps. | No. |
| **MacStories** | Rates not published; homepage weekly sponsor, Shortcuts Archive monthly, podcast spots. Contact required. | https://macstories.net/advertise (read 2026-10-07) | Mac and iOS power users. | Price not found; almost surely above $300 for the homepage slot [E]. |
| **TidBITS** | Rates not published. Audience claimed: 200,000 page views a month, 24,500 weekly email subscribers, 3,000 daily RSS subscribers. 12-week commitment gets a welcome article. | https://tidbits.com/about/advertise/ (read 2026-10-07) | Older, general Mac readers. Plausible for Legroom or Outbound Veil. | Price not found. Worth one inquiry email, which costs nothing. |
| **Hacker Newsletter** | $850 to $1,000 per issue about 50,000 subscribers; classified $150. The figure is from an Indie Hackers post of unknown date, now 60,000+ subscribers per the same source. | Search-result summary of indiehackers.com posts (undated) [S, weak] | Developers. Fit for ModernTex only if code and LaTeX users overlap. | The $150 classified is under budget but the audience fit is thin. Price may be stale. |
| **Indie Hackers newsletter** | Price not found. 99,096 subscribers, 35% open rate claimed. | Search summary of indiehackers.com listing | Founders, not buyers of these apps. | Not found; poor fit anyway. |
| **Mac podcasts** | Specific shows' rates not found. General: $15 to $40 CPM; host-read $25 to $50; small shows (under 5,000 downloads) about $18 to $25 CPM, $90 to $250 per episode. | Search summaries of podderapp.com and talks.co (2026) [S, weak] | Keyfeel, Legroom (Mac enthusiasts), but both are $9.99. | Possible for one small show at $90 to $250, but one episode will not give a readable result. |
| **Apple Search Ads / Apple Ads** | **Not available for Mac-only apps.** Account setup requires an iPhone or iPad app on the App Store. Ads run on the iOS and iPadOS App Store. A developer forum thread from November 2025 asking about macOS App Store apps had no replies. | https://developer.apple.com/forums/thread/806737 (2025-11, read 2026-10-07) [S, weak: unanswered thread plus search summaries; confirm in app-ads.apple.com] | None of the five Mac apps. Also: ModernTex, Outbound Veil, Legroom and Keyfeel are sold direct, not through the Mac App Store. | No. GlobePin's own $2.70 per install did not pay back. US CPT benchmark for reference: $1.58 (https://adapty.io/blog/apple-ads-benchmarks-2026/, updated 2026-07-13). |
| **Microsoft Advertising** | No hard minimum found [not found]. CPC about 30% to 40% below Google ($1.54 vs $2.69 all-industry; $2.10 vs $3.33 B2B/SaaS). Can import Google Ads campaigns [S from memory, not verified in this session]. | https://theadspend.com/blog/google-ads-vs-microsoft-ads-2026 (2026, search summary) [S, weak] | Same keywords as Google. Audience skews to Windows and Edge, so Mac-intent keywords will have small volume [E]. | Yes. Cheap to run beside Google. |
| **X / Twitter Ads** | Practical minimum $50 a day, $1,500 a month for a real test (vendor claim, not X's own). CPM $5 to $9, CPC $0.30 to $2.50. daily.dev claims CPM $25 to $45 for developer targeting, a conflict I cannot resolve. | https://www.autotweet.io/questions/how-much-do-x-ads-cost (updated 2026-05-17) [S, weak] | Weak. | No. |
| **TikTok Ads** | Platform minimum: campaign over $50 a day, ad group over $20 a day; lifetime ad group minimum is $20 x days ($620 for 31 days). CPM $4.20 to $9.00, CPC $0.17 to $1.00 (vendor). | https://ads.tiktok.com/help/article/budget (official, read 2026-10-07) | Poor fit for all five apps. | No. One ad group for 30 days is over $300. |
| **YouTube creator sponsorships** | Nano (1,000 to 10,000 subscribers): $25 to $500 per sponsorship; integration $50 to $250. Micro (10,000 to 100,000): $200 to $5,000. Tech reviews: CPM $25 to $45 per 1,000 views. Affiliate deals 10% to 30%. Vendor data. | https://alpha.outlierkit.com/resources/youtube-nano-influencer-sponsorship-rates/ (updated 2026-09-13); https://outlierkit.com/resources/youtube-sponsorship-rates/ (2026) | ModernTex through small LaTeX, academic-workflow or Mac-productivity channels. Keyfeel through keyboard channels. Specific channel prices: not found. | Yes: one to three nano integrations, or a free-license-for-review offer. Results are lumpy. Needs hand-picked channels; I did not identify specific channels. |
| **Product Hunt** | Free to launch. Promoted posts: $4,000 to $6,000 retail, $2,800 on a 6-month commitment, in 2019. That campaign produced about $1,500 per paid subscriber. Current rates: not found. | https://www.gmass.co/blog/product-hunt-promoted-posts/ (article dated 2019-10-04, stale) | Any app, as a free launch, not as an ad. | The free launch, yes. Paid promotion, no. |
| **Academic and LaTeX newsletters** | Specific rates not found. One university graduate-student e-newsletter of about 15,000 students quoted $90 to $110 per issue (https://omc.osu.edu/sites/default/files/documents/2024/01/On%20Campus%20ad%20sheet_revised.pdf, 2024 [S]). Chronicle of Higher Education and Times Higher Education require sales contact. | Same | Local graduate-student newsletters could suit ModernTex, but each has a small, single-university audience. | Possible but unproven, and each is a one-off. |

## 3. Affiliate and referral programs

| Program | What it takes or pays | Fit | Source and date |
|---|---|---|---|
| **Setapp (developer)** | Setapp shares 70% of each user's fee among the apps that user opens, by usage. Join requirements: fully functional app (no demo or light versions), integrate the Setapp framework, disable your own licensing and update frameworks, change the bundle ID, about one year minimum commitment, no listing fee. You may keep selling elsewhere. Cross-promotion of your other apps inside the Setapp build is prohibited. | Fits a Mac suite audience, but it is a subscription revenue pool, not a $19.99 sale. Expect a smaller, usage-based payout per user [E]. Engineering effort to ship a second build. | https://docs.setapp.com/docs/faq and /distributing-revenue (undated, read 2026-10-07) [S] |
| **Setapp Partner Program** | You get 20% of the monthly fee of each Setapp user you refer, for as long as they subscribe, after their 7-day trial. Requires a Setapp developer account. | Only useful if the apps are on Setapp. Referral value depends on Setapp pricing; not found. | https://docs.setapp.com/docs/about-partner-program (undated, read 2026-10-07) [S] |
| **AppSumo** | Per third-party summaries: sellers keep 95% on new customers they bring (minus 5% processing), 70% on AppSumo's returning customers; no listing fee; payout about 60 days after month end; products must be deeply discounted lifetime deals. | Poor fit. A $19.99 app discounted 60% to 80% leaves very little, and lifetime-deal buyers expect long support. Possibly a Suite promotion later. | Search summaries of freemius.com, mysignature.io and indiehackers.com posts (dates 2024 to 2026) [S, weak]. AppSumo's own terms page was not opened. |
| **Lemon Squeezy affiliates** | 3% fee on affiliate-referred orders, added to the normal platform fee (5% plus $0.50 per a competitor's review). Seller sets the commission. | Requires moving checkout off Stripe Checkout. Not worth it for this. | https://docs.lemonsqueezy.com/help/affiliates-for-merchants/fees (official, read 2026-10-07); fee comparison at dodopayments.com (2026, competitor) [S] |
| **Gumroad / Paddle** | Gumroad 10% plus $0.50; Paddle 5% plus $0.50, both merchant of record. Both have affiliate features (detail not found). | Same objection as Lemon Squeezy: replaces your current Stripe flow, and the delivery chain in `netlify/functions` is built on Stripe. | https://fungies.io/gumroad-vs-paddle (2026, competitor of both) [S, weak] |
| **Stripe-native affiliate tools** (Rewardful, FirstPromoter, Tolt) | Rewardful: free to $1,000 a month tracked revenue, $29 a month to $15,000, $99 a month to $50,000. FirstPromoter from $49 a month, Tolt $69 to $199 a month. You choose the commission. | Best match for a Stripe setup with no marketplace to join. Commission of 20% to 30% [E, borrowed from Setapp's 20% and the 10% to 30% creator range] means about $4 to $6 on a $19.99 sale. Pay only on a sale, no upfront risk. Needs the referral ID passed into the Checkout Session created by `checkout.mjs` [E: small engineering task, not verified]. | https://costbench.com/compare/firstpromoter-vs-rewardful/ and https://www.referly.so/pricing/compare (2026, search summaries, vendors) [S, weak] |
| **Mac bundle sites (MacHeist, MacUpdate Promo, StackSocial)** | Historical terms: flat fees early on, later small percentages; current terms not found. | Poor fit for a $19.99 app. Current terms not found. | tidbits.com and tla.systems posts, 2009 to 2010 (stale) |
| **YouTube creator affiliate** | 10% to 30% commission is typical (outlierkit, 2026-09-13) [S] | Cheapest creator route: pay on sale only. | https://alpha.outlierkit.com/resources/youtube-nano-influencer-sponsorship-rates/ |

Note: Chess.com forbids paid ads on its affiliate links (docs/growth-briefs/chess-affiliates.md). Check each affiliate program's rules before pointing any ad at an affiliate link; the relevant point for this report is that none of the above is a source of ad inventory.

## 4. Recommended 30-day plan for about $300

### Which app first, and which not yet

- **Advertise ModernTex first.** It is the only app where I can show break-even on paper (about $0.42 break-even CPC against an observed $0.33 to $0.54), the only one with real search intent that costs cents (Mac LaTeX editor queries), and it has a clear price anchor (Overleaf at $199 a year). It also has the most pain evidence in your reddit notes (Overleaf compile timeout, TeXstudio deprecated on Homebrew for Apple Silicon).
- **Outbound Veil: a tiny test only.** The obvious keywords are enterprise DLP terms at $8 to $22 a click. The only affordable route is long-tail consumer phrasing with very low volume. Expect zero to two sales. If Google reports "low search volume" or CPC above $2, stop and put the money in the ModernTex test.
- **Legroom and Keyfeel ($9.99): do not advertise.** Break-even CPC is about $0.17 to $0.29. The keywords that matter ("mac cleaner", "disk space analyzer mac") are crowded with advertisers who earn more per customer. The keyboard-sound keywords are cheap but have too little volume to learn from. These two are better served by organic search and the Suite.
- **Vitae (free, optional $2.99 a month): do not advertise.** There is no one-time sale to pay back the click. The experiments rule already says signups that do not turn into payers mean stop, not spend.
- **Mac Suite ($54.99): not yet.** Wait until ModernTex shows a cost per sale, then point a second ad group at the Suite page. Break-even CPC is about $0.42 to $0.80 only if the click-to-sale rate holds at 0.8% to 1.5%, which is untested.
- **Apple Search Ads: not an option** for these Mac apps (section 2).

### Budget split ($300 total, 30 days)

| Test | Budget | Expected cost per sale [E] | Hypothesis | Scale rule | Stop rule |
|---|---|---|---|---|---|
| **1. Google Search, ModernTex** | $150 ($5 a day) | $15 to $40 | Exact and phrase match on "mac" and alternative keywords keeps average CPC at or below $0.60, and click-to-sale reaches at least 2%. US only, search network only, no display. Negatives: windows, linux, free, download, online, login, overleaf login. | At least 5 sales attributed to ad clicks and cost per sale at or below $15: raise to $10 a day. $15 to $19: hold. | $60 spent and at least 100 clicks but zero checkout-click or trial events attributed: pause and fix the landing page. At $150 with 1 or fewer sales: stop. |
| **2. Microsoft Advertising, ModernTex** | $40 | $12 to $35 | The same keywords cost 30% to 40% less, because Microsoft's CPC is lower. | Cost per sale below Google's with at least 2 sales: add $20. | $25 spent with fewer than 20 clicks (volume too low) or zero sales: stop. |
| **3. Reddit Ads, ModernTex** | $50 ($5 a day for 10 days) | $30 to $100 | Promoted posts in r/LaTeX, r/PhD, r/GradSchool and r/AskAcademia reach people already complaining about Overleaf. At best it produces trial starts at a CPC at or below $1.00. | Only if cost per trial is at or below $5 and at least 2 sales come from it: extend 10 more days. | $25 spent with CPC above $1.50 or fewer than 15 clicks: stop. |
| **4. Google Search, Outbound Veil (long-tail only)** | $45 | $60 to $200+ | Long-tail consumer phrasing finds a few people who need this today, at CPC at or below $1.00. | One attributed sale at cost per sale below $30: add $30. | $20 spent with CPC above $2 or "low search volume": stop. |
| **Reserve** | $15 | n/a | Hold for correcting tracking mistakes or one-off creative fixes. Keep unspent if not needed. | n/a | n/a |

Two of the four sit in the "may not pay back" class by design. That is deliberate: tests 3 and 4 buy information at a capped price. If you would rather make fewer bets, fold their $95 into test 1 and run it at $8 a day.

### Rules that apply to every test

1. **Fix attribution before spending.** Store gclid or UTM on the Stripe Checkout Session and report sales by it. Without that, the dashboard cannot tell an ad sale from an organic one (see the correction in section 0).
2. **Use your own existing rule:** fewer than 5 attributed conversions is weak evidence. Do not scale, and do not call a channel dead, on 1 to 4 sales.
3. **Do not run all four at once if tracking is not ready.** Start test 1 alone for the first 7 days at $5 a day, read the search-terms report, then add the rest.
4. **Count refunds and trial-only users separately.** Cost per sale means a paid license after the refund window, not a trial start.
5. **Do not buy a sponsorship slot** (Daring Fireball, MacStories, TidBITS, newsletters) inside this budget. A single slot costs more than the whole plan or has no published price.

### Cheaper alternatives outside this $300

- Free launch posts: r/macapps (direct-download apps use the Tier 2 route or the monthly App Pile megathread, per the 2026-09-29 reddit notes), Show HN, Product Hunt (free launch).
- A Stripe-native affiliate program or free licences to two or three small LaTeX or Mac YouTubers on a 20% to 30% commission. Pay only on a sale.
- One inquiry email to TidBITS and MacStories for rates. Costs nothing and fills the "not found" cells.

## 5. What I could not find

- Keyword-level CPCs and volumes for any of the phrases you listed. Google Keyword Planner access is needed.
- A conversion-rate benchmark for $10 to $30 one-time Mac software bought from search ads.
- Rates for MacStories, TidBITS, BuySellAds, the Indie Hackers newsletter, specific Mac podcasts, specific LaTeX or academic YouTubers, and a current Product Hunt promoted-post price.
- Whether Microsoft Advertising has a minimum daily budget, and its US Mac audience share.
- Confirmation from Apple (not a forum thread) that Apple Ads excludes Mac-only apps.
- Whether a paid Mac-bundle site would take Purplelink apps today.

## 6. Source list

Dates are source dates where shown, otherwise the date I read the page (2026-10-07). Pages marked "summary" were seen only as search-engine summaries, not opened.

- Local: `~/.purplelink/traffic/manual-ads.json`, `~/.purplelink/traffic/dashboard.html`, `docs/growth-briefs/experiments.json` (2026-10-07).
- https://megadigital.ai/en/blog/google-ads-benchmarks/ (2026-06-26)
- https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry (2026-09-22)
- https://www.growthspreeofficial.com/blogs/google-ads-cybersecurity-saas-high-cpc-2026 (2026-05-14)
- https://theadspend.com/blog/google-ads-vs-microsoft-ads-2026 (2026, summary)
- https://stackmatix.com/blog/reddit-ads-cost-guide-2026 (2026-09-11)
- https://benly.ai/learn/reddit-ads/reddit-ads-cost-benchmarks (2026-03-24)
- https://affectgroup.com/blog/reddit-ads-cpm-in-the-us-benchmarks-by-campaign-goal-and-community-type/ (2026-06-22)
- https://www.webtonic.io/blog/phone-tech-retail-reddit-ads-statistics (2026-10-04)
- https://business.daily.dev/resources/developer-paid-media-benchmarks-2026-cpm-cpc-ctr-by-channel/ (2026-05-22)
- https://www.ethicalads.io/advertisers/pricing/ and /advertisers/ (Q3 2026)
- https://carbonads.net/faq and https://carbonads.net/more-info (summary)
- https://daringfireball.net/sponsors, https://macstories.net/advertise, https://tidbits.com/about/advertise/
- https://ads.tiktok.com/help/article/budget
- https://www.autotweet.io/questions/how-much-do-x-ads-cost (2026-05-17)
- https://alpha.outlierkit.com/resources/youtube-nano-influencer-sponsorship-rates/ (2026-09-13)
- https://www.gmass.co/blog/product-hunt-promoted-posts/ (2019-10-04)
- https://developer.apple.com/forums/thread/806737 (2025-11); https://adapty.io/blog/apple-ads-benchmarks-2026/ (2026-07-13)
- https://docs.setapp.com/docs/faq, /distributing-revenue, /about-partner-program
- https://docs.lemonsqueezy.com/help/affiliates-for-merchants/fees
- https://fungies.io/gumroad-vs-paddle, https://dodopayments.com/blogs/lemonsqueezy-review (competitor-authored, 2026)
- https://costbench.com/compare/firstpromoter-vs-rewardful/, https://www.referly.so/pricing/compare (2026)
- https://www.overleaf.com/user/subscription/plans (summary, 2026)
- https://cleanmymac.com/blog/mac-disk-space-analyzer (summary, 2026)
- https://omc.osu.edu/sites/default/files/documents/2024/01/On%20Campus%20ad%20sheet_revised.pdf (2024)
