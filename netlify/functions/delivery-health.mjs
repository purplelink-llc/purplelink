/**
 * Netlify Function — order-delivery health, owner-only and read-only.
 *
 * GET /.netlify/functions/delivery-health?days=14
 *   header  x-stats-token: <STATS_TOKEN>      (?token= also works, but URLs get logged)
 *
 * Delivery here depends on Stripe's webhook reaching stripe-webhook.mjs. If it
 * stops, a buyer pays, lands on a page that waits forever, and nothing tells
 * anyone. This answers one question from Stripe's own records: did every paid
 * Checkout Session produce a `checkout.session.completed` event that Stripe
 * confirms was delivered?
 *
 *   1. The webhook endpoint exists, is enabled and listens for that event.
 *   2. Every paid session older than a short grace period has an event.
 *   3. Every such event has `pending_webhooks === 0`, meaning each endpoint
 *      answered 2xx. A positive count on an old event is a failed or still
 *      retrying delivery. Stripe retries for about three days, so past that
 *      the retries are used up and the order needs handling by hand.
 *
 * It cannot see past the webhook (the licence email, the Blobs file, the Modal
 * token). A delivered event whose handler then failed is the job of the
 * operator alert email in stripe-webhook.mjs, not this function.
 *
 * Uses the same STATS_TOKEN and STRIPE_SECRET_KEY as sales.mjs; the key only
 * needs read access to Checkout Sessions, Events and Webhook Endpoints.
 * Nothing about a buyer is returned: no email, name or full session id.
 */

import { timingSafeEqual } from "node:crypto";

const STRIPE_API = "https://api.stripe.com/v1";
const STRIPE_VERSION = "2024-06-20";   // pinned, as in sales.mjs
const WEBHOOK_PATH = "/.netlify/functions/stripe-webhook";
const EVENT_TYPE = "checkout.session.completed";
const GRACE_SECS = 15 * 60;            // a fresh order may still be mid-delivery
const RETRY_WINDOW_SECS = 72 * 3600;   // Stripe's live-mode retry horizon
const EVENT_RETENTION_DAYS = 30;       // the Events API forgets older ones
const PAGE_SIZE = 100;
const MAX_PAGES = 10;
const MAX_LISTED = 8;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function sameToken(given, expected) {
  const a = Buffer.from(String(given || ""));
  const b = Buffer.from(String(expected || ""));
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b);
}

async function stripeGet(path, params, key) {
  const qs = params.toString();
  const resp = await fetch(`${STRIPE_API}${path}${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${key}`, "Stripe-Version": STRIPE_VERSION },
  });
  if (!resp.ok) throw new Error(`stripe ${path} ${resp.status}: ${(await resp.text()).slice(0, 160)}`);
  return resp.json();
}

async function stripeList(path, pairs, key) {
  const rows = [];
  let startingAfter = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    for (const [k, v] of pairs) params.append(k, v);
    if (startingAfter) params.set("starting_after", startingAfter);
    const body = await stripeGet(path, params, key);
    const data = body.data || [];
    rows.push(...data);
    if (!body.has_more || !data.length) return { rows, truncated: false };
    startingAfter = data[data.length - 1].id;
  }
  return { rows, truncated: true };
}

const shortId = (id) => `…${String(id || "").slice(-6)}`;
const money = (cents, cur) => `${(cents / 100).toFixed(2)} ${String(cur || "usd").toUpperCase()}`;
const ageText = (secs) => (secs >= 172800 ? `${Math.floor(secs / 86400)} days` : secs >= 7200 ? `${Math.floor(secs / 3600)} hours` : `${Math.max(1, Math.round(secs / 60))} minutes`);
const worst = (a, b) => ({ ok: 0, warn: 1, bad: 2 }[b] > { ok: 0, warn: 1, bad: 2 }[a] ? b : a);

/**
 * Pure decision logic, exported for tests.
 * sessions: Checkout Session objects; events: checkout.session.completed events;
 * endpoints: webhook endpoint objects or null when they could not be read.
 */
export function evaluate({ sessions, events, endpoints, now, days, truncated = false }) {
  const checks = [];
  let status = "ok";
  const add = (check, s, detail) => { checks.push({ n: checks.length + 1, check, status: s, detail }); status = worst(status, s); };

  // 1. the endpoint
  if (endpoints == null) {
    add("Stripe webhook endpoint", "warn", "Could not read the webhook endpoints. The Stripe key may lack read access to them.");
  } else {
    const ours = endpoints.filter((e) => String(e.url || "").includes(WEBHOOK_PATH));
    const enabled = ours.filter((e) => e.status === "enabled");
    const listening = enabled.filter((e) => (e.enabled_events || []).some((t) => t === "*" || t === EVENT_TYPE));
    if (!ours.length) add("Stripe webhook endpoint", "bad", `No webhook endpoint points at ${WEBHOOK_PATH}. No order is being delivered.`);
    else if (!enabled.length) add("Stripe webhook endpoint", "bad", "The webhook endpoint is disabled in Stripe. No order is being delivered.");
    else if (!listening.length) add("Stripe webhook endpoint", "bad", `The webhook endpoint does not listen for ${EVENT_TYPE}.`);
    else {
      // Both sites sell through this Stripe account, each with its own endpoint. A disabled one that
      // listens for checkouts is a site whose buyers get nothing.
      const off = endpoints.filter((e) => e.status !== "enabled" && (e.enabled_events || []).some((t) => t === "*" || t === EVENT_TYPE));
      if (off.length) add("Stripe webhook endpoint", "warn", `Purplelink's endpoint is fine, but ${off.length} other endpoint(s) that listen for checkouts are disabled: ${off.map((e) => new URL(e.url).host).join(", ")}.`);
      else add("Stripe webhook endpoint", "ok", "Enabled and listening for completed checkouts.");
    }
  }

  // 2 and 3. each paid session against its event
  const paid = sessions.filter((s) => s.payment_status === "paid" || s.payment_status === "no_payment_required");
  const byId = new Map();
  for (const ev of events) {
    const id = ev?.data?.object?.id;
    if (!id) continue;
    const prev = byId.get(id);
    if (!prev || (ev.pending_webhooks || 0) > (prev.pending_webhooks || 0)) byId.set(id, ev);
  }
  const settled = paid.filter((s) => now - s.created > GRACE_SECS);
  const fresh = paid.length - settled.length;
  const missing = [];
  const stuck = [];
  for (const s of settled) {
    const ev = byId.get(s.id);
    const row = { session: shortId(s.id), product: s.metadata?.product || "unknown", amount: money(s.amount_total ?? 0, s.currency), ageSecs: now - s.created };
    if (!ev) missing.push(row);
    else if ((ev.pending_webhooks || 0) > 0) stuck.push({ ...row, pending: ev.pending_webhooks, retriesUsed: now - ev.created > RETRY_WINDOW_SECS });
  }
  const list = (rows) => rows.slice(0, MAX_LISTED).map((r) => `${r.session} ${r.product} ${r.amount}, ${ageText(r.ageSecs)} old${r.retriesUsed ? ", retries used up" : ""}`).join("; ");

  if (!paid.length) {
    add("Paid orders with a webhook event", "ok", `No paid orders in the last ${days} days.`);
    add("Webhook deliveries confirmed", "ok", "Nothing to deliver.");
  } else {
    if (missing.length) add("Paid orders with a webhook event", "bad", `${missing.length} of ${settled.length} paid orders have no ${EVENT_TYPE} event, so nothing was sent to the site: ${list(missing)}.`);
    else add("Paid orders with a webhook event", "ok", `All ${settled.length} paid orders in the last ${days} days have an event${fresh ? `; ${fresh} newer than 15 minutes not yet counted` : ""}.`);
    if (stuck.length) {
      const used = stuck.filter((r) => r.retriesUsed).length;
      add("Webhook deliveries confirmed", "bad", `${stuck.length} order(s) were not acknowledged by the site: ${list(stuck)}.${used ? " Those with retries used up will not retry again; handle them by hand." : " Stripe is still retrying."}`);
    } else add("Webhook deliveries confirmed", "ok", `Stripe confirms the site acknowledged all ${settled.length - missing.length} delivered events.`);
  }
  if (truncated) add("Check coverage", "warn", "More orders than one read could cover. The oldest are not checked.");

  return {
    status,
    windowDays: days,
    paidOrders: paid.length,
    notYetCounted: fresh,
    missingEvent: missing.map(({ ageSecs, ...r }) => ({ ...r, ageHours: Math.round(ageSecs / 360) / 10 })),
    notAcknowledged: stuck.map(({ ageSecs, ...r }) => ({ ...r, ageHours: Math.round(ageSecs / 360) / 10 })),
    checks,
  };
}

export default async function handler(request) {
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });
  const expected = Netlify.env.get("STATS_TOKEN");
  if (!expected) return json(500, { error: "misconfigured", detail: "Set STATS_TOKEN on this site." });
  const url = new URL(request.url);
  const given = request.headers.get("x-stats-token") || url.searchParams.get("token");
  if (!sameToken(given, expected)) return json(401, { error: "unauthorized" });
  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!key) return json(500, { error: "misconfigured", detail: "STRIPE_SECRET_KEY not set." });

  let days = parseInt(url.searchParams.get("days") || "14", 10);
  if (!Number.isFinite(days) || days < 1) days = 14;
  days = Math.min(days, EVENT_RETENTION_DAYS);
  const now = Math.floor(Date.now() / 1000);
  const since = String(now - days * 86400);

  try {
    const [sessions, events, endpoints] = await Promise.all([
      stripeList("/checkout/sessions", [["created[gte]", since]], key),
      stripeList("/events", [["type", EVENT_TYPE], ["created[gte]", since]], key),
      stripeGet("/webhook_endpoints", new URLSearchParams({ limit: "100" }), key).then((b) => b.data || []).catch(() => null),
    ]);
    const result = evaluate({
      sessions: sessions.rows,
      events: events.rows,
      endpoints,
      now,
      days,
      truncated: sessions.truncated || events.truncated,
    });
    return json(200, { generatedAt: new Date(now * 1000).toISOString(), ...result });
  } catch (err) {
    return json(502, { error: "stripe_unreachable", detail: String(err?.message || err).slice(0, 200) });
  }
}
