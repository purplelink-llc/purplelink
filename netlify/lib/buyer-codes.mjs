/**
 * Cross-sell code for buyers (docs/designs/buyer-revenue-program.md, part 1; Ben, 2026-11-05).
 *
 * After a paid one-time order, the buyer gets one code: 30% off one other Purplelink product, good once, for 30
 * days. It is shown on the success page (buyer-offers.mjs) and in the delivery email. Nothing is sent to past
 * buyers and no new email exists for it.
 *
 * The code is a Stripe coupon (percent_off 30, duration once, max_redemptions 1, redeem_by = purchase + 30 days),
 * not a promotion code, so it cannot be typed into Stripe's own box: only checkout.mjs applies it, after checking
 * it here. Stripe allows one discount per session, so it never stacks with a promotion code.
 *
 * Rules:
 * - Not for bundles, seat packs or subscriptions (EXCLUDED, and any entry with mode "subscription").
 * - Not for the same product family as the order that earned it (all Paper Review tiers and packs are one family,
 *   photo licenses one, calendars one; everything else is its own).
 * - Not for an app the buyer already owns through a bundle (owned_parts).
 * - Not earned by an order that already had a discount, so a code cannot chain into 30% off every later order.
 * The cheapest discounted Paper Review is Standard at $6.30, above its compute cost (about $3.88).
 *
 * Blobs store "buyer-codes":
 *   code/<CODE>     -> { coupon, source_product, family, owned_parts, email_hash, created, expires, used? }
 *   session/<cs_id> -> CODE (the order that earned it; makes issuing idempotent)
 */
import { createHmac } from "node:crypto";
import { entitledParts } from "./bundles.mjs";
import { emailHash } from "./followup.mjs";
import { RECOVERY_PRODUCTS } from "./checkout-recovery.mjs";

export const STORE = "buyer-codes";
export const PERCENT_OFF = 30;
export const VALID_DAYS = 30;
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";
export const CODE_RE = /^PL-[2-9A-HJKMNP-Z]{8}$/;

export const EXCLUDED = new Set([
  "bundle-2", "bundle-3", "app-suite", "moderntex-seats", "sheet-bundle", "photo-calendar-bundle", "kit-bundle",
]);

export function familyOf(product) {
  if (typeof product !== "string") return "";
  if (product.startsWith("paper-review-")) return "paper-review";
  if (product.startsWith("photo-license-")) return "photo-license";
  if (product.startsWith("photo-calendar-")) return "photo-calendar";
  return product;
}

/** Can a code be used on this product? `entry` is the checkout catalog entry (for its mode). */
export function eligibleProduct(product, entry) {
  if (!product || EXCLUDED.has(product)) return false;
  if (entry && entry.mode === "subscription") return false;
  return true;
}

/** The code for an order, the same every time for the same session (HMAC of the session id). */
export function makeCode(sessionId, secret) {
  const mac = createHmac("sha256", String(secret || "buyer-codes")).update(`xs:${sessionId}`).digest();
  let out = "";
  for (let i = 0; i < 8; i++) out += ALPHABET[mac[i] % ALPHABET.length];
  return `PL-${out}`;
}

export function normalizeCode(value) {
  if (typeof value !== "string") return "";
  const c = value.trim().toUpperCase();
  return CODE_RE.test(c) ? c : "";
}

/** Does this completed session earn a code? Paid one-time orders with no discount already on them. */
export function earnsCode(session) {
  if (!session || session.mode === "subscription") return false;
  if (session.payment_status !== "paid") return false;
  if (!(Number(session.amount_total) > 0)) return false;
  if (Number(session.total_details?.amount_discount) > 0) return false;
  if (session.metadata?.buyer_code) return false;
  return true;
}

const stripeForm = (obj) => new URLSearchParams(obj).toString();

/** Blob values are stored as JSON strings (works with the real store and the test stubs). */
export async function readRecord(store, code) {
  try {
    const raw = await store.get(`code/${code}`);
    return raw ? (typeof raw === "string" ? JSON.parse(raw) : raw) : null;
  } catch (_) { return null; }
}
const writeRecord = (store, code, rec) => store.set(`code/${code}`, JSON.stringify(rec));

/**
 * Create the code for a paid order: the Stripe coupon, then the Blob records. Returns { code, expires } or null.
 * Safe to call twice for one session: the second call returns the stored code without touching Stripe.
 */
export async function issueCode({ store, stripeKey, secret, session, product, email, nowMs = Date.now(), fetchImpl = fetch }) {
  if (!store || !stripeKey || !session?.id || !earnsCode(session)) return null;
  const existing = await store.get(`session/${session.id}`);
  if (existing) {
    const rec = await readRecord(store, existing);
    return rec ? { code: existing, expires: rec.expires } : null;
  }
  const code = makeCode(session.id, secret);
  const expires = Math.floor(nowMs / 1000) + VALID_DAYS * 86400;
  const coupon = `xs-${code.toLowerCase()}`;
  const resp = await fetchImpl("https://api.stripe.com/v1/coupons", {
    method: "POST",
    headers: { Authorization: `Bearer ${stripeKey}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: stripeForm({
      id: coupon,
      percent_off: String(PERCENT_OFF),
      duration: "once",
      max_redemptions: "1",
      redeem_by: String(expires),
      name: `${PERCENT_OFF}% off one Purplelink product`,
      "metadata[buyer_code]": code,
      "metadata[source_session]": session.id,
      "metadata[source_product]": product,
    }),
  });
  if (!resp.ok) {
    let err = null;
    try { err = (await resp.json())?.error; } catch (_) { err = null; }
    // A webhook retry after the coupon was made but before the Blob write: the same id already exists.
    if (err?.code !== "resource_already_exists") throw new Error(`coupon create failed: ${err?.code || resp.status}`);
  }
  const owned = [...entitledParts(product, session.metadata || {})];
  await writeRecord(store, code, {
    coupon, source_product: product, family: familyOf(product), owned_parts: owned,
    email_hash: email ? emailHash(String(email).trim()) : "", created: Math.floor(nowMs / 1000), expires,
  });
  await store.set(`session/${session.id}`, code);
  return { code, expires };
}

const nameOf = (product) => RECOVERY_PRODUCTS[product]?.short || RECOVERY_PRODUCTS[product]?.name || "that product";

/** Check a code for a product at checkout. { ok: true, coupon } or { ok: false, detail } with a plain reason. */
export async function checkCode(store, code, product, entry, nowMs = Date.now()) {
  const c = normalizeCode(code);
  if (!c) return { ok: false, detail: "That code is not one of ours. Check it against your receipt email." };
  if (!eligibleProduct(product, entry)) {
    return { ok: false, detail: "Your code works on single products, not bundles, seat packs or subscriptions." };
  }
  const rec = await readRecord(store, c);
  if (!rec) return { ok: false, detail: "That code is not one of ours. Check it against your receipt email." };
  if (rec.used) return { ok: false, detail: "That code has already been used." };
  if (Number(rec.expires) * 1000 <= nowMs) return { ok: false, detail: "That code has expired." };
  if (rec.family && rec.family === familyOf(product)) {
    return { ok: false, detail: `Your code is for a different product than ${nameOf(rec.source_product)}, the one you bought.` };
  }
  if (Array.isArray(rec.owned_parts) && rec.owned_parts.includes(product)) {
    return { ok: false, detail: `You already own ${nameOf(product)} through your purchase.` };
  }
  return { ok: true, coupon: rec.coupon, code: c };
}

/** A session that used a code completed: mark the code used (Stripe also stops it at one redemption). */
export async function markUsed(store, session) {
  const c = normalizeCode(session?.metadata?.buyer_code || "");
  if (!c || !store) return false;
  const rec = await readRecord(store, c);
  if (!rec || rec.used) return false;
  await writeRecord(store, c, { ...rec, used: session.id, used_at: Math.floor(Date.now() / 1000) });
  return true;
}

/** "December 5, 2026" from a Unix time, in US Eastern (the time the site's other dates use). */
export function expiryText(expires) {
  return new Date(Number(expires) * 1000).toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric", timeZone: "America/New_York",
  });
}

/** Paragraph for the delivery email. Empty when there is no code. */
export function crossSellOffer(buyerCode) {
  if (!buyerCode?.code) return { text: "", html: "" };
  const url = `https://purplelink.llc/products/?code=${buyerCode.code}`;
  const when = expiryText(buyerCode.expires);
  const line = `Your code ${buyerCode.code} takes ${PERCENT_OFF}% off one other Purplelink product, once, until ${when}. It is applied at checkout when you open the link below.`;
  return {
    text: `${line}\n${url}\n\n`,
    html: `<p>Your code <strong>${buyerCode.code}</strong> takes ${PERCENT_OFF}% off one other Purplelink product, once, until ${when}. <a href="${url}">See the products</a>; the code is applied at checkout.</p>`,
  };
}
