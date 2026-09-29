# Spreadsheet products: what's built, which niches to sell into, which subscriptions are worth building

Researched 2026-09-28. Etsy figures come from the first page of search results (about 65 listings per query), viewed logged out. Etsy hides total result counts. Prices and terms were checked on primary pages unless marked otherwise.

## Built (source in `kit-src/spreadsheets/`, gitignored; files in `dist/`)

| Product | File | For | Suggested price |
|---|---|---|---|
| Muscle-on-GLP-1 Tracker, spreadsheet edition | `muscle-on-glp1-tracker.xlsx` | MuscleOnGLP buyers; Etsy | $12 (the PDF version is $9) |
| Journal Submission & R&R Tracker | `journal-submission-tracker.xlsx` | Pre-tenure faculty, postdocs | $12 |
| Tenure & Promotion Dossier Tracker | `tenure-dossier-tracker.xlsx` | Assistant professors | $12, as a cheap test |
| Grant Budget Builder (NSF/NIH) | `grant-budget-builder.xlsx` | Faculty writing proposals | Sell only in the bundle |

Rebuild with `python3 <name>.py`, then recalculate with the xlsx skill's `recalc.py`. All four recalculate with zero formula errors. The results were checked by hand:
- GLP-1 tracker: 210 lb gives 152 g/day at 1.6 g/kg.
- Tenure tracker: at 52% of the clock, a target of 8 articles should be at 4.2 by now.
- Grant budget, NSF year 1: $126,700 direct, $102,200 base, $56,210 F&A.
- Grant budget, NIH mode: salary capped at $19,000/month, 0% escalation, only $25,000 of each subaward in the base, and the graduate compensation limit flagged when exceeded.

The grant rules are all input cells with their source beside them ([`rules.py`](../kit-src/spreadsheets/rules.py)):
- **NIH salary cap:** $228,000 from 2026-01-01 (NOT-OD-26-034 / 26-038). It changes every January.
- **Subaward amount included in MTDC:** NSF $50,000 (2 CFR 200.1). NIH $25,000, because NIH still applies 45 CFR 75 (NOT-OD-26-072, P.L. 119-75).
- **NIH escalation:** none (NOT-OD-12-036).
- **NIH graduate compensation limit:** $63,480 (NOT-OD-26-044).
- **NSF senior personnel:** 2 months a year (PAPPG 24-1 II.D.2.f.(i)(a)).
- **Equipment threshold:** $10,000.
- **15% indirect-cost caps:** both the NSF and NIH caps were blocked in court, so the F&A rate stays an input.
- **In flux:** OMB proposed rewriting 2 CFR 200 on 2026-05-29, and it is blocked from being finalized until at least 2026-12-11. Recheck `rules.py` each January.

## Niches, ranked

| # | Niche | Competition on Etsy | Price | Verdict |
|---|---|---|---|---|
| 1 | GLP-1 muscle log (protein, strength, weight) | Medium. Generic GLP-1 trackers are crowded (median $7.31), but the protein-and-strength angle is held by small PDF shops with 11 reviews or fewer. [MyGLP1Journey](https://www.etsy.com/shop/MyGLP1Journey) has 1,999 sales, which shows the category buys | $9–12 | **Built. List first.** |
| 2 | Journal submission and R&R tracker | Medium-low. Real ones sell for $5.85–8.95 with no reviews | $9–12 | **Built** |
| 3 | Academic job market tracker | Low. 5 of 65 listings relevant | $9 | **Build next.** The season runs Aug–Dec |
| 4 | Grant pipeline and PI effort tracker | Medium, mostly nonprofit-oriented. [DrTrackerPhD](https://www.etsy.com/shop/DrTrackerPhD) has 317 sales across ~30 listings | $12–15 | Bundle |
| 5 | Systematic review screening matrix (PRISMA counts, two independent screeners, extraction codebook) | Medium (median $6.99) | $10–14 | Build. Uses your interrater-reliability workflow |
| 6 | Tenure dossier tracker | None found. That may mean no demand | $12 | **Built.** Cheap test |
| 7 | Multi-platform sales tracker (Etsy/Stripe/App Store) | Low | $12 | Own site only |
| 8 | Grant budget builder | Low on Etsy, but every sponsored-programs office gives one away ([Utah](https://osp.utah.edu/_xls/NSF_Budget_Template.xlsx), [Harvard](https://research.fas.harvard.edu/templates)) | — | **Built. Bundle only** |
| — | Dissertation planners, Etsy/LLC bookkeeping, generic protein or workout logs, tax calculators | High. Shops with 5k–12k reviews, prices of $1–5, and tax-advice exposure | — | Skip |

**Proposed packaging:** a "Researcher Bundle" at $24–29 (submission tracker, grant budget builder, tenure tracker, and the job market and review matrix once built), plus the GLP-1 tracker sold on its own. Sell Google Sheets and Excel versions together. Most competitors do, and some buyers filter by format.

**Rules for the GLP-1 listing:**
- No dosing advice.
- No claim that it prevents muscle loss.
- Name Ozempic, Wegovy and Zepbound only descriptively ("for people on GLP-1 medications"), never implying endorsement.
- No reviews or ratings until real ones exist (FTC 16 CFR 465; see the MuscleOnGLP rule).

## Subscriptions (live data flowing into a sheet)

| Idea | Data | Terms | Competitors | Verdict |
|---|---|---|---|---|
| **Publication and citation dashboard** | OpenAlex + Crossref | OpenAlex is CC0; a free key covers $1/day of usage, and filtered lists cost $0.10 per 1k ([pricing](https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing)). Crossref is free | Google Scholar profiles are free; Dimensions and Scopus are institutional | **Build: $39/yr** |
| **Funding feed matched to keywords** | Grants.gov search2, NSF Awards, NIH RePORTER (no more than 1 request/sec) | Open | Instrumentl $299–999/mo ([pricing](https://www.instrumentl.com/pricing)); Pivot-RP is institution-only | **Build: $59/yr** |
| Submission tracker with journal stats | OpenAlex source stats (2-year mean citedness, h-index). Not the Impact Factor, which is Clarivate's | CC0 | Litmaps and ResearchRabbit, $10–12.50/mo | **Bundle with the dashboard: "Academic Sheets," $49/yr** |
| Seller P&L in Sheets (Stripe, App Store) | The buyer's own API keys | Holding other people's keys raises security obligations | ChartMogul is free under $120K ARR; Coupler.io from $24/mo | Maybe later |
| Bank-feed budgeting | Plaid / Teller / SimpleFIN | Plaid hides pricing and puts production access behind security reviews. Teller is free for 100 connections, then $0.30 per connection per month. Consumer-data rules (CFPB 1033) are being rewritten | Tiller $99/yr, Monarch, Copilot $95/yr | **No-go** |
| Fantasy football | Sleeper, FantasyPros, Yahoo | All require a commercial license or restrict commercial use | — | **No-go** |
| Mortgage rates | FRED / Freddie Mac PMMS | Free everywhere | — | **No-go:** nothing to charge for |
| GLP-1 tracker synced with Apple Health | HealthKit | Only works inside an iOS app. Apple bans using the data for other purposes (guideline 5.1.3). Also brings in the FTC Health Breach Notification Rule | — | **No-go** |

**Data sources to avoid:**
- ORCID's free Public API bans revenue-generating use ([terms](https://info.orcid.org/public-client-terms-of-service/)). Look people up by ORCID iD through OpenAlex instead.
- Semantic Scholar's license forbids selling or repackaging the data ([license](https://www.semanticscholar.org/product/api/license)).
- Google Scholar has no API, and its robots.txt disallows `/scholar`.

**How to deliver into Google Sheets:**
- Use the `drive.file` permission (only files the app creates), which needs just basic verification.
- The full `spreadsheets` permission is sensitive: it needs a demo video and a written justification.
- Full `drive` access is restricted and requires a yearly paid security assessment (CASA), reportedly $540–1,800 [secondary source].
- A template with Apps Script avoids the Marketplace review altogether.

**First steps:**
1. **Dashboard:** a Modal endpoint takes an ORCID iD, pulls works and citation counts from OpenAlex, and writes them into a new sheet using `drive.file`. Run it on your own record and log the OpenAlex cost.
2. **Funding feed:** a weekly Modal job queries grants.gov with your keywords, removes duplicates by opportunity ID, and Claude scores relevance. Compare it against your own inbox for 4 weeks before charging anyone.

## Open steps for Ben
- **Open an Etsy shop:** creating the account is yours to do. Listing fees are $0.20 per listing plus about 10% per sale.
- **Decide on MuscleOnGLP:** whether to sell the spreadsheet next to the $9 PDF there too. It needs a Stripe Price, and download.mjs has to serve an .xlsx file.
