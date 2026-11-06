// Referrals for every product (docs/designs/buyer-revenue-program.md, part 2; Ben, 2026-11-05).
//
// Every buyer's purchase email carries https://purplelink.llc/?ref=<code>, where <code> is the 10-hex referral code
// Modal makes from their email (backend/latextools/referrals.py). site.js remembers a ?ref= code for 30 days and adds
// it to checkout requests. checkout.mjs applies the shared Stripe coupon `purplelink-friend-20` (20% off, once) when:
//   - the order carries no buyer cross-sell code (one discount per order; the buyer code wins),
//   - the product is not a bundle, seat pack or subscription, and lists at $7 or more,
//   - the code belongs to a real buyer (the Blobs mirror below, else Modal /referral/check).
// The referrer's reward (a free Standard Paper Review 14 days later) is decided by Modal, never here.
//
// Blobs store "buyer-codes" (shared with buyer-codes.mjs):
//   ref/<code>            {at}  a code Modal has confirmed belongs to a buyer (written by stripe-webhook)
//   referral/<session>    {code, link}  the buyer's own link, for the success page (buyer-offers.mjs)

import { EXCLUDED } from "./buyer-codes.mjs";

export const FRIEND_PERCENT = 20;
export const FRIEND_COUPON = "purplelink-friend-20";
export const REF_RE = /^[0-9a-f]{10}$/;
export const MIN_LIST_CENTS = 700;
export const MODAL_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run";

// List prices for catalog entries that name only an env Price (checkout.mjs has no amount for them).
export const LIST_CENTS = {
  "paper-review-standard": 900, "paper-review-journal": 1100, "paper-review-deep": 1500,
  "paper-review-pack-5": 3800, "paper-review-pack-20": 15000,
  "cover-letter": 200, "anonymity-check": 200, "citation-gap": 300, "revision-review": 200,
  "response-review": 600, "resume-review": 500,
  "kit-faceless": 4900, "kit-monetization": 2900, "kit-clip": 1000,
  "outbound-veil": 2999, "legroom": 999,
};

export function listCents(product, entry) {
  if (Object.hasOwn(LIST_CENTS, product)) return LIST_CENTS[product];
  return entry && Number.isInteger(entry.amount) ? entry.amount : 0;
}

/** Can the friend discount apply to this product? */
export function friendEligible(product, entry) {
  if (!product || EXCLUDED.has(product)) return false;
  if (!entry || entry.mode === "subscription" || entry.seats || entry.bundle) return false;
  return listCents(product, entry) >= MIN_LIST_CENTS;
}

/** Is `code` a real buyer's referral code? Never throws; any failure means no discount. */
export async function checkRef(store, code, { secret, fetchImpl = fetch, timeoutMs = 2500 } = {}) {
  if (!REF_RE.test(code || "")) return false;
  try {
    if (store && (await store.get(`ref/${code}`))) return true;
  } catch (_) { /* fall through to Modal */ }
  if (!secret) return false;
  try {
    const r = await fetchImpl(`${MODAL_BASE}/referral/check?code=${code}`, {
      headers: { "x-webhook-secret": secret },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) return false;
    const d = await r.json();
    if (d && d.valid === true) {
      try { await store?.set(`ref/${code}`, JSON.stringify({ at: Date.now() })); } catch (_) { /* mirror only */ }
      return true;
    }
  } catch (_) { /* timeout or network: full price */ }
  return false;
}

/** Create the shared coupon (idempotent: its id is fixed). Returns true when it exists afterwards. */
export async function ensureFriendCoupon(stripeKey, { fetchImpl = fetch, api = "https://api.stripe.com/v1" } = {}) {
  try {
    const r = await fetchImpl(`${api}/coupons`, {
      method: "POST",
      headers: { Authorization: `Bearer ${stripeKey}`, "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        id: FRIEND_COUPON, percent_off: String(FRIEND_PERCENT), duration: "once",
        name: "Referred by a Purplelink buyer (20% off)",
      }).toString(),
    });
    if (r.ok) return true;
    const d = await r.json().catch(() => null);
    return d?.error?.code === "resource_already_exists";
  } catch (_) {
    return false;
  }
}

/** Tell Modal about a paid order: ledger, the buyer's own link, a pending reward if it was referred. */
export async function registerBuyer({ secret, sessionId, email, product, amountPaid, referralCode,
                                      fetchImpl = fetch, timeoutMs = 5000 }) {
  if (!secret || !sessionId || !email) return null;
  try {
    const r = await fetchImpl(`${MODAL_BASE}/referral/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-webhook-secret": secret },
      body: JSON.stringify({
        session_id: sessionId, email, product: product || "",
        amount_paid: Number.isInteger(amountPaid) ? amountPaid : 0,
        referral_code: REF_RE.test(referralCode || "") ? referralCode : "",
      }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) return null;
    const d = await r.json();
    return d && typeof d === "object" ? d : null;
  } catch (_) {
    return null;
  }
}

/** Store what the success page needs; never throws. */
export async function saveReferral(store, sessionId, reg) {
  if (!store || !reg || !REF_RE.test(reg.code || "") || typeof reg.link !== "string") return;
  try {
    await store.set(`referral/${sessionId}`, JSON.stringify({ code: reg.code, link: reg.link }));
    await store.set(`ref/${reg.code}`, JSON.stringify({ at: Date.now() }));
  } catch (_) { /* the email still carries the link */ }
}

export async function referralFor(store, sessionId) {
  try {
    const raw = await store.get(`referral/${sessionId}`);
    const d = raw ? JSON.parse(raw) : null;
    return d && typeof d.link === "string" && d.link.startsWith("https://purplelink.llc/") ? d : null;
  } catch (_) {
    return null;
  }
}

export function referralText(link) {
  if (!link) return { text: "", html: "" };
  const line = "A friend who makes their first Purplelink purchase through it gets 20% off, and two weeks later you get a free Standard Paper Review.";
  return {
    text: `Your referral link: ${link}\n${line}`,
    html: `<p>Your referral link: <a href="${link}">${link}</a>. ${line}</p>`,
  };
}
