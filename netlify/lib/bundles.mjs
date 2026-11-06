/**
 * Custom bundles of the Mac Suite: pick any 2 parts for 25% off their combined price, or any 3 for 40% off, whichever
 * parts are chosen. One source of truth for checkout, delivery, keys and recovery; site/suite/bundle.js carries the
 * same tables for the live price display, and a test keeps them equal.
 *
 * The ten parts are the nine Mac apps and a lifetime Vitae Plus key. The whole Suite (all ten) stays its own
 * product, "app-suite", and is what four or more parts are sent to. The client chooses only WHICH parts; the price
 * is computed here from PART_CENTS and the tier, never taken from the request. A bundle's session carries
 * metadata.product ("bundle-2" or "bundle-3") and metadata.apps (the chosen part slugs, comma-separated, in the
 * canonical order below), and every entitlement check reads them back.
 *
 * Tiers: decided 2026-11-06 (percent off the parts' own prices, replacing the fixed $34.99 and $44.99 of
 * docs/growth-briefs/custom-bundle-pricing-2026-10-11.md).
 */
export const BUNDLE_PARTS = [
  { slug: "moderntex",     label: "ModernTex" },
  { slug: "outbound-veil", label: "Outbound Veil" },
  { slug: "legroom",       label: "Legroom" },
  { slug: "keyfeel",       label: "Keyfeel" },
  { slug: "tapefolio",     label: "Tapefolio" },
  { slug: "panely",      label: "Panely" },
  { slug: "summonly",      label: "Summonly" },
  { slug: "nee",           label: "Née" },
  { slug: "lenses",        label: "Lenses" },
  { slug: "vitae-plus",    label: "Vitae Plus for life" },
];
export const BUNDLE_SLUGS = BUNDLE_PARTS.map((p) => p.slug);

/** What each part costs on its own, in cents (Vitae Plus is its first year, as in the Suite's own price stack). */
export const PART_CENTS = {
  "moderntex": 1999, "outbound-veil": 2999, "legroom": 999, "keyfeel": 999, "tapefolio": 2999,
  "panely": 999, "summonly": 999, "nee": 1499, "lenses": 499, "vitae-plus": 2399,
};

export const BUNDLES = {
  "bundle-2": { count: 2, percent: 25 },
  "bundle-3": { count: 3, percent: 40 },
};

/** The product key for a number of parts (2 or 3), or null. */
export function bundleProductFor(count) {
  return Object.keys(BUNDLES).find((k) => BUNDLES[k].count === count) || null;
}

/**
 * The price in cents of a bundle of these parts (an array of slugs, in any order): the parts' own prices added up,
 * less the tier's percent, rounded to the nearest cent. Returns null unless it is exactly 2 or 3 different known parts.
 */
export function bundleCents(parts) {
  if (!Array.isArray(parts)) return null;
  const product = bundleProductFor(parts.length);
  if (!product) return null;
  const slugs = parseBundleParts(parts, parts.length);
  if (!slugs) return null;
  const sum = slugs.reduce((t, slug) => t + PART_CENTS[slug], 0);
  return Math.round((sum * (100 - BUNDLES[product].percent)) / 100);
}

export function isBundleProduct(product) {
  return Object.prototype.hasOwnProperty.call(BUNDLES, product);
}

/**
 * Parse the chosen parts from untrusted input (an array, or a comma-separated string). Returns the canonical,
 * de-duplicated list when it is exactly `count` known parts, otherwise null.
 */
export function parseBundleParts(value, count) {
  const raw = Array.isArray(value) ? value : typeof value === "string" ? value.split(",") : null;
  if (!raw) return null;
  const chosen = new Set();
  for (const item of raw) {
    if (typeof item !== "string") return null;
    const slug = item.trim();
    if (!BUNDLE_SLUGS.includes(slug)) return null;
    chosen.add(slug);
  }
  if (chosen.size !== count || raw.length !== count) return null;
  return BUNDLE_SLUGS.filter((s) => chosen.has(s));
}

/** The parts a paid bundle session contains, from its Stripe metadata; [] when the metadata is not a valid bundle. */
export function bundlePartsOf(metadata) {
  const product = metadata?.product || "";
  if (!isBundleProduct(product)) return [];
  return parseBundleParts(metadata?.apps || "", BUNDLES[product].count) || [];
}

/**
 * The parts a purchase entitles, as a Set of slugs: the whole Suite is all ten, a bundle is its chosen parts,
 * a single app is itself (seat packs are ModernTex). Anything else entitles nothing.
 */
export function entitledParts(product, metadata) {
  if (product === "app-suite") return new Set(BUNDLE_SLUGS);
  if (isBundleProduct(product)) return new Set(bundlePartsOf({ ...(metadata || {}), product }));
  if (product === "moderntex-seats") return new Set(["moderntex"]);
  if (BUNDLE_SLUGS.includes(product)) return new Set([product, ...addonPartsOf(product, metadata)]);
  return new Set();
}

/**
 * The parts that can be added to a single-app purchase at checkout (netlify/lib/addons.mjs): every part except the
 * lifetime Vitae Plus key. Lenscrib is not a part, so it is never one.
 */
export const ADDON_SLUGS = BUNDLE_SLUGS.filter((s) => s !== "vitae-plus");

/**
 * The second app a single-app purchase carries, from `metadata.addons` (comma-separated slugs). Only a single Mac app
 * has add-ons; anything else (a bundle, the Suite, seats, a part that is already the main app, an unknown slug) gives
 * []. The value is written server-side from the paid line items, never taken from the buyer.
 */
export function addonPartsOf(product, metadata) {
  if (!ADDON_SLUGS.includes(product)) return [];
  const raw = typeof metadata?.addons === "string" ? metadata.addons.split(",") : [];
  const out = [];
  for (const item of raw) {
    const slug = item.trim();
    if (ADDON_SLUGS.includes(slug) && slug !== product && !out.includes(slug)) out.push(slug);
  }
  return out.slice(0, 2);
}

/** Does this purchase contain the part beyond a plain single-product match: a bundle's parts, or a single app's add-ons? The Suite and the single product itself are handled by the caller. */
export function bundleHasPart(product, metadata, slug) {
  if (isBundleProduct(product)) return bundlePartsOf({ ...(metadata || {}), product }).includes(slug);
  return addonPartsOf(product, metadata).includes(slug);
}

/** "ModernTex and Legroom", "ModernTex, Legroom and Keyfeel". */
export function partsSentence(slugs) {
  const names = slugs.map((s) => BUNDLE_PARTS.find((p) => p.slug === s)?.label || s);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
