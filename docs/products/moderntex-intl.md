# ModernTex in other languages and currencies

Public note on what purplelink.llc localizes for ModernTex, and the rules that keep the claims true. Written
2026-10-29.

## What is localized

- Product pages: `/de/moderntex/`, `/fr/moderntex/`, `/ja/moderntex/`, `/zh-cn/moderntex/`, each with one how-to under
  `/de/guides/`, `/fr/guides/`, `/ja/guides/`, `/zh-cn/guides/`. Hreflang in the page head and in `sitemap.xml`, a language switcher at the top of the five
  product pages, and a "ModernTex in Deutsch, Français, 日本語, 简体中文" line in the footer of every English page
  (`scripts/apply_layout.py`, styled by `.footer-langs` in `site/styles.css`).
- The English `/moderntex/` has a "Languages and currency" section and two FAQ entries. `/suite/`, `/outbound-veil/` and
  `/legroom/` carry the currency line by the buy button, and `/pricing/` has a FAQ entry.
- Translated head, nav, footer and FAQ. The terms, privacy policy and changelog exist only in English, and the pages say so.
- `site/llms.txt` and `site/llms-full.txt` (`scripts/gen_llms_full.py`) state the page languages, the interface languages
  and the local-currency checkout.
- The Chinese pages load nothing from Google (its services are blocked in mainland China).

## Rule: interface-language claims follow shipped releases

A page may say the ModernTex interface is in a language only when a published release has it.

- Shipped: English, and German (beta) since ModernTex 2.0.
- Not shipped: French, Japanese and Simplified Chinese (the Japanese and Chinese ones are open pull requests moderntex #117
  and #118). The French, Japanese and Chinese pages say the interface is English, and no page may claim otherwise.
- What is true today regardless: ModernTex compiles Chinese and Japanese documents with XeLaTeX (ctex) and LuaLaTeX
  (luatexja, jlreq) when the user's TeX installation has those packages. upLaTeX support is not released.

When #117 or #118 ships: edit the page text (the "interface is English" notes and FAQ answers on `/ja/moderntex/` or
`/zh-cn/moderntex/`, the English "Languages and currency" row, the JSON-LD `inLanguage` list on the app, `llms.txt`,
`gen_llms_full.py`), then update `InterfaceClaimsFollowReleases` in `site-tests/test_intl_advertise.py`. The test fails on
purpose until both agree.

## Local-currency checkout (Stripe Adaptive Pricing)

Adaptive Pricing is on for the Stripe account (2026-10-29). Stripe shows the buyer the price converted into a local
currency chosen from the buyer's location, and the buyer can switch back to USD. The base price stays USD; ModernTex is
19.99. Stripe's exchange rate includes a conversion fee of 2 to 4 percent, paid by the buyer. Payment methods are card
(with Apple Pay and Google Pay) and Link; the pages do not claim Alipay, WeChat Pay or any other method.

It applies to every Checkout Session that `netlify/functions/checkout.mjs` creates for the Mac apps, because those
sessions are plain: `mode: payment`, one line item priced in USD (an inline `price_data` amount, or a Stripe Price for
Outbound Veil and Legroom), no `currency_options`, no manual capture. Do not add any of these, and do not set
`adaptive_pricing` in the session, without rethinking the pages:

- `currency_options` on a Stripe Price turns Adaptive Pricing off for that price
- `payment_intent_data[capture_method]=manual` turns it off

`netlify/tests/checkout-adaptive-pricing.test.mjs` fails if a Mac-app session stops being compatible, and checks the
amounts against `PRODUCT_CATALOG` and `netlify/lib/seats.mjs`. `site-tests/test_intl_advertise.py` checks that every
ModernTex price on the site (19.99 or 19,99) equals the catalog and that every ModernTex page states the currency fact.

The studio rule that no price, trial or discount changes before 2027-01-12 is unchanged: the pages describe the existing
price and the currency display, nothing else.

## Monitoring

`scripts/uptime-checks.txt` (run every 15 minutes by `.github/workflows/uptime.yml`) probes `/moderntex/`,
`/de/moderntex/`, `/fr/moderntex/`, `/ja/moderntex/` and `/zh-cn/moderntex/` for a 200. The daily indexing job reads every `<loc>` in the
live sitemap, so the localized URLs are included; `site-tests/test_intl_advertise.py` checks that they are in it.
