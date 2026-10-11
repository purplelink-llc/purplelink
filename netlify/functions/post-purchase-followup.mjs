// Daily at 14:30 UTC: the day-14 follow-up to people who bought a Mac app. See netlify/lib/followup.mjs.
//
// OFF until POST_PURCHASE_FOLLOWUP is set to "on" in the Netlify environment. While off it only counts who would
// be emailed and sends nothing. When on: one email per address (never again for QUIET_DAYS), skipping refunded
// or disputed orders and anyone who unsubscribed. Addresses are never logged; the log holds counts only.
import { getStore } from "@netlify/blobs";
import {
  FOLLOWUP_PRODUCTS, MAX_PER_RUN, QUIET_DAYS, emailHash, followupEmail, windowFor,
} from "../lib/followup.mjs";

const STRIPE_API = "https://api.stripe.com/v1";
const RESEND_API_URL = "https://api.resend.com/emails";
const MAX_PAGES = 5;

/** Paid, delivered orders in the window, as [{ id, product, email, seats }], newest last. Refunded or disputed ones are left out. */
export async function dueOrders(nowS, secretKey) {
  const { gte, lte } = windowFor(nowS);
  const out = [];
  let after = "";
  for (let page = 0; page < MAX_PAGES; page++) {
    const qs = new URLSearchParams({ "created[gte]": String(gte), "created[lte]": String(lte), limit: "100" });
    qs.append("expand[]", "data.payment_intent.latest_charge");
    if (after) qs.set("starting_after", after);
    const resp = await fetch(`${STRIPE_API}/checkout/sessions?${qs}`, { headers: { Authorization: `Bearer ${secretKey}` } });
    if (!resp.ok) return { error: `stripe_${resp.status}` };
    const data = await resp.json().catch(() => null);
    const rows = data?.data ?? [];
    for (const s of rows) {
      const product = s?.metadata?.product || "";
      if (!FOLLOWUP_PRODUCTS[product] || s.payment_status !== "paid" || typeof s.id !== "string") continue;
      const email = (s.customer_details?.email || s.customer_email || "").trim();
      if (!email) continue;
      const charge = s.payment_intent && typeof s.payment_intent === "object" ? s.payment_intent.latest_charge : null;
      if (charge && typeof charge === "object" && (charge.refunded || charge.amount_refunded > 0 || charge.disputed)) continue;
      out.push({ id: s.id, product, email, seats: parseInt(s.metadata?.seats || "0", 10) || 0 });
    }
    if (!data?.has_more || rows.length === 0) break;
    after = rows[rows.length - 1].id;
  }
  return { orders: out };
}

export async function runFollowups({ nowS = Math.floor(Date.now() / 1000), send } = {}) {
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const resendKey = Netlify.env.get("RESEND_API_KEY");
  const secret = Netlify.env.get("FOLLOWUP_UNSUBSCRIBE_SECRET") || Netlify.env.get("STRIPE_WEBHOOK_SECRET");
  if (!secretKey || !secret) return { ok: false, reason: "misconfigured" };
  const enabled = Netlify.env.get("POST_PURCHASE_FOLLOWUP") === "on";
  const found = await dueOrders(nowS, secretKey);
  if (found.error) return { ok: false, reason: found.error };

  const sent = getStore("followup-sent");
  const suppressed = getStore("followup-suppressed");
  const counts = { considered: found.orders.length, sent: 0, would_send: 0, already: 0, suppressed: 0, quiet: 0, failed: 0, enabled };
  const seenNow = new Set();
  for (const o of found.orders) {
    if (counts.sent + counts.would_send >= MAX_PER_RUN) break;
    const h = emailHash(o.email);
    if (await sent.get(`session:${o.id}`)) { counts.already++; continue; }
    if (await suppressed.get(h)) { counts.suppressed++; continue; }
    const last = await sent.get(`email:${h}`);
    if (seenNow.has(h) || (last && nowS - Number(last) < QUIET_DAYS * 86400)) { counts.quiet++; await sent.set(`session:${o.id}`, "quiet"); continue; }
    if (!enabled) { counts.would_send++; seenNow.add(h); continue; }
    const mail = followupEmail({ to: o.email, product: o.product, seats: o.seats, secret });
    if (!mail || !resendKey) { counts.failed++; continue; }
    let ok = false;
    try {
      const resp = await (send || fetch)(RESEND_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${resendKey}` },
        body: JSON.stringify(mail),
      });
      ok = resp.ok;
    } catch (_) { ok = false; }
    if (!ok) { counts.failed++; continue; }
    await sent.set(`session:${o.id}`, String(nowS));
    await sent.set(`email:${h}`, String(nowS));
    seenNow.add(h);
    counts.sent++;
  }
  return { ok: true, ...counts };
}

export default async function handler() {
  const result = await runFollowups();
  console.log("post-purchase-followup", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "30 14 * * *" };
