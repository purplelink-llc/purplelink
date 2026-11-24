/**
 * A fixed Stripe product for each single Mac app whose price is set inline in checkout (Black Friday 2026).
 *
 * Inline prices (`price_data[product_data]`) make a new Stripe product on every session, so a coupon cannot be limited
 * to "the Mac apps": there is no product id to list in `applies_to`. scripts/black_friday_promo_code.mjs makes one
 * product per app (tax code txcd_10202000 on the product, for Managed Payments) and one Price on it with lookup_key
 * `app_<slug>` at the app's own price. Checkout finds those Prices by lookup key (short in-memory cache, as
 * addons.mjs does) and sends `price_data[product]` instead of `price_data[product_data]`. The amount still comes from
 * the catalog in checkout.mjs; the Price only names the product, and it must match that amount to be used.
 *
 * Apps with an env Price (Outbound Veil, Legroom, Lenses) already have a fixed product and are not listed here.
 * Any lookup failure, a missing Price or an amount mismatch gives null, and the checkout is exactly what it was.
 */
export const APP_PRODUCT_SLUGS = Object.freeze(["moderntex", "keyfeel", "tapefolio", "lenscrib", "nee", "panely", "summonly"]);
const LOOKUP_RE = /^app_([a-z0-9-]+)$/;
const CACHE_MS = 5 * 60 * 1000;

export const appLookupKey = (slug) => `app_${slug}`;

let cache = { at: 0, key: "", map: null };
export function resetAppProductCache() { cache = { at: 0, key: "", map: null }; }

/**
 * The fixed Stripe product id for a single Mac app sold at `cents`, or null. Never throws. `fetchFn` is injectable
 * for tests. The cache is per secret key, so a switch between Stripe accounts never reuses the other account's ids.
 */
export async function appProductId(secretKey, slug, cents, { fetchFn = fetch, now = Date.now() } = {}) {
  try {
    if (!secretKey || !APP_PRODUCT_SLUGS.includes(slug) || !Number.isInteger(cents) || cents <= 0) return null;
    if (!cache.map || cache.key !== secretKey || now - cache.at > CACHE_MS) {
      const q = new URLSearchParams();
      for (const s of APP_PRODUCT_SLUGS) q.append("lookup_keys[]", appLookupKey(s));
      q.set("limit", "20");
      const r = await fetchFn(`https://api.stripe.com/v1/prices?${q}`, {
        headers: { Authorization: `Bearer ${secretKey}` },
        signal: AbortSignal.timeout(3000),
      });
      if (!r.ok) return null;
      const list = await r.json();
      const map = {};
      for (const price of list?.data || []) {
        const m = LOOKUP_RE.exec(price?.lookup_key || "");
        if (!m || !APP_PRODUCT_SLUGS.includes(m[1])) continue;
        const product = typeof price.product === "string" ? price.product : price.product?.id;
        if (price.active !== true || price.currency !== "usd" || price.type !== "one_time" || !/^prod_/.test(product || "")) continue;
        map[m[1]] = { product, cents: price.unit_amount };
      }
      cache = { at: now, key: secretKey, map };
    }
    const hit = cache.map[slug];
    return hit && hit.cents === cents ? hit.product : null;
  } catch (_) {
    return null;
  }
}
