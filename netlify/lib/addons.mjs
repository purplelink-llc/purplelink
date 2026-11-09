/**
 * Optional second app at 25% off, inside Stripe Checkout (Ben, 2026-11-06).
 *
 * Someone buying ONE Mac app alone sees one or two optional rows ("Outbound Veil, 25% off") that nothing preselects.
 * They are Stripe Checkout `optional_items`, which need saved Prices, so scripts/stripe_addon_prices.mjs makes one
 * one-time USD Price per app at 75% of the app's own price, with lookup_key `addon_<slug>_25` and
 * metadata.addon_slug. This module finds those Prices by lookup key at runtime (short in-memory cache, no env vars
 * to keep in step) and, after payment, reads the add-ons back from the PAID LINE ITEMS of the session.
 *
 * Why line items and not metadata: Checkout cannot stamp metadata for an item the buyer adds on the payment page, so
 * the paid session is the only record. Every reader (webhook, download pages, license pages, recovery) expands
 * line_items and calls addonsFromSession(); the result is written to metadata.addons in memory only, so a buyer can
 * never forge it and the 25%-off Prices are never trusted from the request.
 *
 * Left out (the checkout is then exactly what it was): bundles, the Suite, seat packs, Paper Review and other
 * tools, kits, sheets, photos, subscriptions, Stripe Managed Payments (no tax code on the add-on products, so Stripe
 * could refuse the session), and any order with a buyer code or friend discount (they must not stack with 25% off).
 * The promotion-code box stays. Any lookup failure sends the checkout without add-ons.
 */
import { ADDON_SLUGS, BUNDLE_PARTS, PART_CENTS } from "./bundles.mjs";
import { UPSELL } from "./upsell.mjs";

export const ADDON_PERCENT = 25;
export const MAX_ADDON_ROWS = 2;
const LOOKUP_RE = /^addon_([a-z0-9-]+)_25$/;
const CACHE_MS = 5 * 60 * 1000;

export const addonLookupKey = (slug) => `addon_${slug}_25`;
/** The add-on price in cents: 75% of the app's own price, rounded to the cent. */
export const addonCents = (slug) => Math.round(PART_CENTS[slug] * (100 - ADDON_PERCENT) / 100);
export const addonLabel = (slug) => BUNDLE_PARTS.find((p) => p.slug === slug)?.label || slug;

/** Can this product carry add-ons at all: a single Mac app with a key (not Vitae Plus). */
export function addonEligibleProduct(product) {
  return ADDON_SLUGS.includes(product);
}

/** The apps to offer next to a product, in the order of the upsell pairings, at most two. */
export function addonSuggestions(product) {
  if (!addonEligibleProduct(product)) return [];
  const out = [];
  for (const candidate of UPSELL[product] || []) {
    if (out.length >= MAX_ADDON_ROWS) break;
    if (ADDON_SLUGS.includes(candidate) && candidate !== product && !out.includes(candidate)) out.push(candidate);
  }
  return out;
}

let cache = { at: 0, map: null };
export function resetAddonPriceCache() { cache = { at: 0, map: null }; }

/**
 * { slug: priceId } for the active add-on Prices, looked up by lookup key. Returns {} on any failure; never throws.
 * `fetchFn` is injectable for tests.
 */
export async function addonPriceIds(secretKey, slugs, { fetchFn = fetch, now = Date.now() } = {}) {
  try {
    if (!secretKey || !slugs.length) return {};
    if (!cache.map || now - cache.at > CACHE_MS) {
      const q = new URLSearchParams();
      for (const slug of ADDON_SLUGS) q.append("lookup_keys[]", addonLookupKey(slug));
      q.set("limit", "20");
      const r = await fetchFn(`https://api.stripe.com/v1/prices?${q}`, {
        headers: { Authorization: `Bearer ${secretKey}` },
        signal: AbortSignal.timeout(3000),
      });
      if (!r.ok) return {};
      const list = await r.json();
      const map = {};
      for (const price of list?.data || []) {
        const m = LOOKUP_RE.exec(price?.lookup_key || "");
        if (!m || !ADDON_SLUGS.includes(m[1])) continue;
        if (price.active !== true || price.currency !== "usd" || price.type !== "one_time" || price.unit_amount !== addonCents(m[1])) continue;
        map[m[1]] = price.id;
      }
      cache = { at: now, map };
    }
    const out = {};
    for (const slug of slugs) if (cache.map[slug]) out[slug] = cache.map[slug];
    return out;
  } catch (_) {
    return {};
  }
}

/**
 * The rows to offer: [[slug, priceId], ...] ([] = none). `ctx`: { product, entry, managed, discounted, secretKey, fetchFn }.
 * Decided before the idempotency key is made, because the key must change with the rows (Stripe refuses a reused key
 * with different parameters).
 */
export async function pickAddons(ctx) {
  const { product, entry, managed, discounted, secretKey, fetchFn } = ctx;
  if (managed || discounted) return [];
  if (!entry || (entry.mode || "payment") !== "payment" || entry.seats || entry.bundle || entry.trialDays || entry.interval) return [];
  const wanted = addonSuggestions(product);
  if (!wanted.length) return [];
  const prices = await addonPriceIds(secretKey, wanted, { fetchFn });
  return wanted.filter((s) => prices[s]).map((s) => [s, prices[s]]);
}

/** Put the picked rows on the Checkout Session params. Nothing is preselected: optional_items start unchecked. */
export function setOptionalItems(params, picked) {
  picked.forEach(([, priceId], i) => {
    params[`optional_items[${i}][price]`] = priceId;
    params[`optional_items[${i}][quantity]`] = "1";
  });
}

/**
 * The add-on slugs a paid session contains, from its expanded line_items: a line whose Price carries
 * metadata.addon_slug or an `addon_<slug>_25` lookup key, for a known app other than the main product. [] when
 * line_items are not expanded, the product cannot carry add-ons, or nothing was added.
 */
export function addonsFromSession(session) {
  const product = session?.metadata?.product || "";
  if (!addonEligibleProduct(product)) return [];
  const items = session?.line_items?.data;
  if (!Array.isArray(items)) return [];
  const out = [];
  for (const item of items) {
    const price = item?.price;
    const m = LOOKUP_RE.exec(price?.lookup_key || "");
    const slug = price?.metadata?.addon_slug || (m ? m[1] : "");
    if (ADDON_SLUGS.includes(slug) && slug !== product && !out.includes(slug)) out.push(slug);
  }
  return out.slice(0, MAX_ADDON_ROWS);
}

/** Write the derived add-ons onto session.metadata (in memory), replacing anything already there. Returns the session. */
export function withAddons(session) {
  if (!session || typeof session !== "object") return session;
  const slugs = addonsFromSession(session);
  session.metadata = { ...(session.metadata || {}) };
  if (slugs.length) session.metadata.addons = slugs.join(",");
  else delete session.metadata.addons;
  return session;
}

/** The query string that makes a Stripe session retrieve carry its line items with their Prices. */
export const SESSION_EXPAND = "expand[]=line_items";
