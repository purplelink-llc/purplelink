/**
 * Refunded and disputed purchases.
 *
 * The site's refund terms say a refunded order's download links stop working and its keys are no longer
 * licensed. Keys are verified offline (Ed25519), so a key already issued cannot be revoked; what we can do is
 * stop handing out links and keys again. stripe-webhook.mjs records a full refund (charge.refunded with
 * `refunded: true`) or a dispute (charge.dispute.created) here, keyed on the payment intent, which every
 * paid Checkout Session in payment mode carries. The download doors, purchase-license, vitae-license and
 * purchases-recover read it back through revocationFor(session).
 *
 * A partial refund is not recorded, so access stays. A dispute closed in our favour (charge.dispute.closed with
 * status "won") clears a dispute record; a refund record is never cleared by a dispute event.
 *
 * Reads fail open: if Blobs cannot be read, the purchase is served as before and the error is logged, so a
 * storage hiccup never locks out a buyer who paid.
 */
import { getStore } from "@netlify/blobs";

export const REFUND_STORE = "refunds";

export const REVOKED_DETAIL =
  "This order was refunded or disputed, so its download links and license keys are no longer available. " +
  "If you think this is a mistake, reply to your order email or write to ben@purplelink.llc.";

const keyFor = (paymentIntentId) => `pi:${paymentIntentId}`;

/** The payment intent id of a Checkout Session (or charge, or dispute), whether expanded or not. */
export function paymentIntentOf(obj) {
  const pi = obj?.payment_intent;
  if (typeof pi === "string" && pi.startsWith("pi_")) return pi;
  if (pi && typeof pi === "object" && typeof pi.id === "string" && pi.id.startsWith("pi_")) return pi.id;
  return null;
}

async function readRecord(store, paymentIntentId) {
  const raw = await store.get(keyFor(paymentIntentId));
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return { reason: "refund" }; }
}

/** Record a full refund or a dispute. `reason` is "refund" or "dispute". A refund record is never downgraded. */
export async function recordRevocation(paymentIntentId, { reason, chargeId = null, disputeId = null, eventId = null } = {}) {
  if (!paymentIntentId) return false;
  const store = getStore(REFUND_STORE);
  const existing = await readRecord(store, paymentIntentId);
  if (existing?.reason === "refund" && reason !== "refund") return true;
  await store.set(keyFor(paymentIntentId), JSON.stringify({
    reason, payment_intent: paymentIntentId, charge: chargeId, dispute: disputeId, event: eventId,
    recorded_at: new Date().toISOString(),
  }));
  return true;
}

/** Clear a dispute record after the dispute is won. Leaves a refund record alone. */
export async function clearDispute(paymentIntentId) {
  if (!paymentIntentId) return false;
  const store = getStore(REFUND_STORE);
  const existing = await readRecord(store, paymentIntentId);
  if (!existing || existing.reason !== "dispute") return false;
  await store.delete(keyFor(paymentIntentId));
  return true;
}

/** The revocation record for a Checkout Session, or null when it was not refunded or disputed (or on a read error). */
export async function revocationFor(session) {
  const pi = paymentIntentOf(session);
  if (!pi) return null;
  try {
    return await readRecord(getStore(REFUND_STORE), pi);
  } catch (err) {
    console.error("refunds: lookup failed, serving the purchase", err?.name, err?.message);
    return null;
  }
}
