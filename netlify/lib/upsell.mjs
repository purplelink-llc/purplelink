// Thank-you page upsell (docs/designs/buyer-revenue-program.md, part 4; Ben, 2026-11-05).
//
// The success page shows at most two products next to the buyer's 30% cross-sell code, each with its normal price
// and the price with the code, linking to the product page with ?code= filled in (site.js applies it). The pairs are
// hand-picked: sales data has no per-buyer link yet. Names and prices come from RECOVERY_PRODUCTS, which a test
// keeps equal to what checkout charges, so no price is written twice.
//
// A suggestion is skipped when the code could not be used on it: the same product family as the order, an app the
// order already includes (a bundle's parts), or a product codes never apply to (bundles, seats, subscriptions).

import { RECOVERY_PRODUCTS } from "./checkout-recovery.mjs";
import { EXCLUDED, PERCENT_OFF, familyOf } from "./buyer-codes.mjs";

export const MAX_SUGGESTIONS = 2;

// Product key -> its page. Only products listed here can be suggested.
export const PAGES = Object.freeze({
  "moderntex": "/moderntex/",
  "outbound-veil": "/outbound-veil/",
  "legroom": "/legroom/",
  "keyfeel": "/keyfeel/",
  "tapefolio": "/tapefolio/",
  "lenscrib": "/lenscrib/",
  "lenses": "/lenses/",
  "nee": "/nee/",
  "panely": "/panely/",
  "summonly": "/summonly/",
  "paper-review-standard": "/tools/paper-review/",
  "response-review": "/tools/response-review/",
  "sheet-submission": "/sheets/submission-tracker/",
});

// Short names for the page (RECOVERY_PRODUCTS names are written for an email sentence).
const TITLES = Object.freeze({
  "paper-review-standard": "Paper Review (Standard)",
  "response-review": "Response letter review",
  "sheet-submission": "Journal Submission & R&R Tracker",
});

const ACADEMIC = ["paper-review-standard", "moderntex", "response-review", "sheet-submission"];
const MAC_UTILITIES = ["legroom", "keyfeel", "panely", "summonly"];

// Source product (or family) -> candidates in order; the first MAX_SUGGESTIONS that pass the rules are shown.
export const UPSELL = Object.freeze({
  "moderntex": ["paper-review-standard", "sheet-submission", "tapefolio"],
  "paper-review": ["moderntex", "response-review", "sheet-submission"],
  "response-review": ["paper-review-standard", "moderntex"],
  "response-draft": ["paper-review-standard", "moderntex"],
  "revision-review": ["response-review", "paper-review-standard", "moderntex"],
  "cover-letter": ["paper-review-standard", "moderntex"],
  "anonymity-check": ["paper-review-standard", "moderntex"],
  "journal-check": ["moderntex", "response-review"],
  "citation-gap": ["paper-review-standard", "moderntex"],
  "resume-review": ["paper-review-standard", "moderntex"],
  "sheet-submission": ["moderntex", "paper-review-standard"],
  "sheet-tenure": ["moderntex", "sheet-submission"],
  "sheet-jobmarket": ["moderntex", "paper-review-standard"],
  "sheet-grantpipeline": ["moderntex", "sheet-submission"],
  "sheet-reviewmatrix": ["moderntex", "paper-review-standard"],
  "tapefolio": ["moderntex", "paper-review-standard"],
  "outbound-veil": ["legroom", "keyfeel", "panely"],
  "legroom": ["keyfeel", "panely", "summonly"],
  "keyfeel": ["legroom", "summonly", "panely"],
  "panely": ["summonly", "legroom", "keyfeel"],
  "summonly": ["panely", "keyfeel", "legroom"],
  "nee": ["summonly", "legroom", "panely"],
  "lenses": ["legroom", "keyfeel", "panely"],
  "lenscrib": ["nee", "keyfeel", "legroom"],
  "bundle-2": [...ACADEMIC, ...MAC_UTILITIES, "nee"],
  "bundle-3": [...ACADEMIC, ...MAC_UTILITIES, "nee"],
  "app-suite": ACADEMIC,
});

export const money = (cents) => `$${(cents / 100).toFixed(2)}`;

/** The price after a percent-off coupon, rounded to the cent as Stripe does. */
export const discounted = (cents, percent = PERCENT_OFF) => cents - Math.round((cents * percent) / 100);

/**
 * Suggestions for a buyer-code record ({source_product, family, owned_parts}). Each is
 * { product, name, path, price, price_with_code }. Never throws; an unknown product gets none.
 */
export function suggestionsFor(rec) {
  const source = rec && typeof rec.source_product === "string" ? rec.source_product : "";
  if (!source) return [];
  const list = UPSELL[source] || UPSELL[familyOf(source)] || [];
  const family = (rec && rec.family) || familyOf(source);
  const owned = new Set(Array.isArray(rec.owned_parts) ? rec.owned_parts : []);
  const out = [];
  for (const product of list) {
    if (out.length >= MAX_SUGGESTIONS) break;
    const p = RECOVERY_PRODUCTS[product];
    if (!p || !PAGES[product] || EXCLUDED.has(product)) continue;
    if (familyOf(product) === family || owned.has(product) || out.some((s) => s.product === product)) continue;
    out.push({
      product,
      name: TITLES[product] || p.name,
      path: PAGES[product],
      price: money(p.cents),
      price_with_code: money(discounted(p.cents)),
    });
  }
  return out;
}
