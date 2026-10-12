/**
 * Custom bundles of the Mac Suite: pick any 2 or any 3 of the eight parts for one fixed price, whichever parts
 * are chosen. One source of truth for checkout, delivery, keys and recovery; site/suite/bundle.js carries the
 * same table for the live price display, and a test keeps the two equal.
 *
 * The eight parts are the seven Mac apps and a lifetime Vitae Plus key. The whole Suite (all eight) stays its own
 * product, "app-suite". The client chooses only WHICH parts; the price comes from this table, never from the
 * request. A bundle's session carries metadata.product ("bundle-2" or "bundle-3") and metadata.apps (the chosen
 * part slugs, comma-separated, in the canonical order below), and every entitlement check reads them back.
 *
 * Prices: docs/growth-briefs/custom-bundle-pricing-2026-10-11.md.
 */
export const BUNDLE_PARTS = [
  { slug: "moderntex",     label: "ModernTex" },
  { slug: "outbound-veil", label: "Outbound Veil" },
  { slug: "legroom",       label: "Legroom" },
  { slug: "keyfeel",       label: "Keyfeel" },
  { slug: "tapefolio",     label: "Tapefolio" },
  { slug: "panely",      label: "Panely" },
  { slug: "summonly",      label: "Summonly" },
  { slug: "vitae-plus",    label: "Vitae Plus for life" },
];
export const BUNDLE_SLUGS = BUNDLE_PARTS.map((p) => p.slug);

export const BUNDLES = {
  "bundle-2": { count: 2, cents: 3499 },
  "bundle-3": { count: 3, cents: 4499 },
};

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
 * The parts a purchase entitles, as a Set of slugs: the whole Suite is all eight, a bundle is its chosen parts,
 * a single app is itself (seat packs are ModernTex). Anything else entitles nothing.
 */
export function entitledParts(product, metadata) {
  if (product === "app-suite") return new Set(BUNDLE_SLUGS);
  if (isBundleProduct(product)) return new Set(bundlePartsOf({ ...(metadata || {}), product }));
  if (product === "moderntex-seats") return new Set(["moderntex"]);
  return BUNDLE_SLUGS.includes(product) ? new Set([product]) : new Set();
}

/** Does this bundle (and only a bundle) contain the part? The Suite and single products are handled by the caller. */
export function bundleHasPart(product, metadata, slug) {
  return isBundleProduct(product) && bundlePartsOf({ ...(metadata || {}), product }).includes(slug);
}

/** "ModernTex and Legroom", "ModernTex, Legroom and Keyfeel". */
export function partsSentence(slugs) {
  const names = slugs.map((s) => BUNDLE_PARTS.find((p) => p.slug === s)?.label || s);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
