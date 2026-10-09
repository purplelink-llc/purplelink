/**
 * Netlify Function — sales reader, owner-only.
 *
 * GET /.netlify/functions/sales?token=SECRET&days=30
 *
 * Both sites sell through the same Stripe account and tag every Checkout
 * Session (and every subscription) with metadata.product, so one pass gives
 * revenue for purplelink.llc and getmuscleonglp.com at once, split by product.
 * The traffic dashboard renders this above the traffic cards.
 *
 * Gated by STATS_TOKEN, the same owner-only token the stats function uses, so
 * the dashboard needs no second credential.
 *
 * Revenue is paid Checkout Sessions plus paid subscription renewals. Every
 * order in `ledger` carries its Stripe fee, net and refunded amount, so the
 * dashboard can report gross and net the way an app-store revenue tool does.
 * Customers appear in the ledger only as a salted hash of their email: enough
 * to count new vs. returning buyers, never the address itself. The emails in
 * `recent` are unchanged from before, for the owner's own "Recent" table.
 */

import { createHash } from "node:crypto";

const STRIPE_API = "https://api.stripe.com/v1";
// Pinned so invoice.subscription / invoice.charge keep the shape this code reads,
// whatever the account's default API version becomes.
const STRIPE_VERSION = "2024-06-20";
const LIFECYCLE_STATS_URL = "https://ben-ampel--purplelink-latextools-web.modal.run/lifecycle/stats";
const PAGE_SIZE = 100;
const MAX_PAGES = 10; // 1000 rows per list; `truncated` says when that was not enough

// Product key -> which site sold it. Derived from netlify/functions/checkout.mjs
// and muscleonglp-site/netlify/functions/lib/products.mjs; a key missing here
// still shows up, under "unknown", rather than being dropped.
const SITE_OF_PRODUCT = new Map(Object.entries({
  "paper-review-standard": "purplelink", "paper-review-journal": "purplelink",
  "paper-review-deep": "purplelink", "paper-review-pack-5": "purplelink",
  "paper-review-pack-20": "purplelink", "cover-letter": "purplelink",
  "anonymity-check": "purplelink", "citation-gap": "purplelink",
  "revision-review": "purplelink", "response-review": "purplelink",
  "resume-review": "purplelink", "kit-faceless": "purplelink",
  "kit-monetization": "purplelink", "kit-bundle": "purplelink",
  "kit-clip": "purplelink", "moderntex": "purplelink", "outbound-veil": "purplelink", "legroom": "purplelink", "keyfeel": "purplelink", "tapefolio": "purplelink", "freeboard": "purplelink", "app-suite": "purplelink",
  "vitae-plus-monthly": "purplelink", "vitae-plus-annual": "purplelink",
  "digest-monthly": "purplelink", "digest-annual": "purplelink",
  "sheet-submission": "purplelink", "sheet-tenure": "purplelink", "sheet-jobmarket": "purplelink", "sheet-grantpipeline": "purplelink", "sheet-reviewmatrix": "purplelink", "sheet-bundle": "purplelink",
  "live-scholar": "purplelink", "live-funding": "purplelink",
  "tracker-sheet": "muscleonglp",

  "muscleonglp-guide": "muscleonglp", "protein-playbook": "muscleonglp",
  "complete-pack": "muscleonglp", "creatine-glp1": "muscleonglp",
  "no-gym-plan": "muscleonglp", "off-ramp": "muscleonglp",
  "tracker": "muscleonglp", "workbook": "muscleonglp",
}));

const SITE_LABEL = { purplelink: "purplelink.llc", muscleonglp: "getmuscleonglp.com", unknown: "unattributed" };

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

const bump = (o, k, n = 1) => { if (k) o[k] = (o[k] || 0) + n; };
const isoDay = (ts) => new Date(ts * 1000).toISOString().slice(0, 10);

async function stripeGet(path, params, key) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`${STRIPE_API}${path}${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${key}`, "Stripe-Version": STRIPE_VERSION },
  });
  if (!resp.ok) throw new Error(`stripe ${path} ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  return resp.json();
}

/** Every row of a Stripe list endpoint, up to MAX_PAGES pages. `extra` may carry
 *  repeated keys (expand[]) as [key, value] pairs. */
async function stripeList(path, extra, key) {
  const rows = [];
  let startingAfter = null, pages = 0;
  for (; pages < MAX_PAGES; pages++) {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    for (const [k, v] of extra) params.append(k, v);
    if (startingAfter) params.set("starting_after", startingAfter);
    const page = await stripeGet(path, params, key);
    const data = page.data || [];
    rows.push(...data);
    if (!page.has_more || !data.length) return { rows, truncated: false };
    startingAfter = data[data.length - 1].id;
  }
  return { rows, truncated: true };
}

/** Monthly value of one subscription item, in cents. */
function monthlyCents(item) {
  const price = item.price || {};
  const r = price.recurring;
  if (!r) return 0;
  const amount = (price.unit_amount || 0) * (item.quantity || 1);
  const every = r.interval_count || 1;
  const perMonth = { day: 365 / 12, week: 52 / 12, month: 1, year: 1 / 12 }[r.interval] ?? 0;
  return Math.round((amount * perMonth) / every);
}

export default async function handler(request) {
  const url = new URL(request.url);
  const expected = Netlify.env.get("STATS_TOKEN");
  if (!expected) return json(500, { error: "misconfigured", detail: "Set STATS_TOKEN on this site." });
  if (url.searchParams.get("token") !== expected) return json(401, { error: "unauthorized" });

  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!key) return json(500, { error: "misconfigured", detail: "STRIPE_SECRET_KEY not set." });

  let days = parseInt(url.searchParams.get("days") || "30", 10);
  if (!Number.isFinite(days) || days < 1) days = 30;
  const now = Math.floor(Date.now() / 1000);
  const cutoff = now - days * 86400;

  // The owner's own end-to-end test purchases are real Stripe charges and would
  // otherwise pad the order count and revenue. Kept out of every total and
  // reported separately, so the headline number is money other people paid.
  // Set SALES_EXCLUDE_EMAILS on the site rather than naming addresses here.
  const ownerEmails = new Set(
    (Netlify.env.get("SALES_EXCLUDE_EMAILS") || "")
      .split(",").map((e) => e.trim().toLowerCase()).filter(Boolean),
  );
  const isOwner = (email) => ownerEmails.has((email || "").toLowerCase());
  // Salted with the stats token so the hash can't be matched against a list of
  // addresses by anyone who only sees the dashboard archive.
  const custKey = (email) => email
    ? createHash("sha256").update(`${expected}:${email.trim().toLowerCase()}`).digest("hex").slice(0, 16)
    : "";

  // --- pull everything in parallel ---------------------------------------------
  let sessions, invoices, subs, fees;
  try {
    [sessions, invoices, subs, fees] = await Promise.all([
      stripeList("/checkout/sessions", [["expand[]", "data.payment_intent.latest_charge"]], key),
      stripeList("/invoices", [["status", "paid"], ["expand[]", "data.charge"]], key),
      stripeList("/subscriptions", [["status", "all"], ["expand[]", "data.customer"]], key),
      stripeList("/balance_transactions", [["type", "charge"]], key),
    ]);
  } catch (err) {
    return json(502, { error: "stripe_unreachable", detail: String(err).slice(0, 300) });
  }
  const truncated = sessions.truncated || invoices.truncated || subs.truncated;

  // Stripe fee and net per charge, from Stripe's own ledger.
  const feeOf = new Map(fees.rows.map((t) => [t.source, { fee: t.fee || 0, net: t.net || 0 }]));
  const chargeFacts = (charge) => {
    if (!charge || typeof charge !== "object") return { fee: null, net: null, refunded: 0, disputed: false };
    const f = feeOf.get(charge.id);
    return {
      fee: f ? f.fee : null,
      net: f ? f.net : null,
      refunded: charge.amount_refunded || 0,
      disputed: !!charge.disputed,
    };
  };

  // Subscription id -> product key, for mapping renewal invoices.
  const productOfSub = new Map(subs.rows.map((s) => [s.id, (s.metadata && s.metadata.product) || "unknown"]));

  // Channel attribution that checkout.mjs stored as metadata (first and last
  // touch, compact JSON). Absent on orders from before 2026-09-28 and for
  // buyers with Do Not Track or blocked storage.
  const touch = (v) => {
    if (typeof v !== "string" || !v) return null;
    try { const t = JSON.parse(v); return t && typeof t === "object" ? t : null; } catch (_) { return null; }
  };
  const attrOf = (md) => {
    const first = touch(md && md.attr_first), last = touch(md && md.attr_last);
    return first || last ? { first, last } : null;
  };
  const attrOfSub = new Map(subs.rows.map((s) => [s.id, attrOf(s.metadata)]));

  // --- one ledger: first purchases and subscription renewals --------------------
  const paid = [];
  for (const s of sessions.rows) {
    if (s.payment_status !== "paid") continue; // trials start at "no_payment_required"
    const product = (s.metadata && s.metadata.product) || "unknown";
    const pi = s.payment_intent && typeof s.payment_intent === "object" ? s.payment_intent : null;
    paid.push({
      id: s.id, kind: "purchase", created: s.created, product,
      site: SITE_OF_PRODUCT.get(product) || "unknown",
      amount: s.amount_total || 0, currency: s.currency || "usd",
      email: (s.customer_details && s.customer_details.email) || "",
      attr: attrOf(s.metadata),
      ...chargeFacts(pi && pi.latest_charge),
    });
  }
  for (const inv of invoices.rows) {
    // The first invoice of a paid (non-trial) subscription is already the
    // Checkout Session above; everything after it is a renewal. A trial's first
    // charge is a "subscription_cycle" invoice, so trial conversions land here.
    if (!["subscription_cycle", "subscription_update"].includes(inv.billing_reason)) continue;
    if (!(inv.amount_paid > 0)) continue;
    const product = productOfSub.get(inv.subscription) || "unknown";
    paid.push({
      id: inv.id, kind: "renewal", created: inv.created, product,
      site: SITE_OF_PRODUCT.get(product) || "unknown",
      amount: inv.amount_paid, currency: inv.currency || "usd",
      email: inv.customer_email || "",
      attr: attrOfSub.get(inv.subscription) || null,
      ...chargeFacts(inv.charge),
    });
  }
  paid.sort((a, b) => b.created - a.created);

  const selfTests = paid.filter((p) => isOwner(p.email));
  const customer = paid.filter((p) => !isOwner(p.email));

  // --- aggregate (same shape as before, renewals now included) -----------------
  const allTime = { orders: customer.length, gross: customer.reduce((n, p) => n + p.amount, 0) };
  const inWindow = customer.filter((p) => p.created >= cutoff);
  const windowTotals = { days, orders: inWindow.length, gross: inWindow.reduce((n, p) => n + p.amount, 0) };

  const siteOrders = {}, siteGross = {}, winOrders = {}, winGross = {};
  const prodOrders = {}, prodGross = {}, prodLast = {}, byDay = {};
  for (const p of customer) {
    bump(siteOrders, p.site); bump(siteGross, p.site, p.amount);
    bump(prodOrders, p.product); bump(prodGross, p.product, p.amount);
    if (!prodLast[p.product] || p.created > prodLast[p.product]) prodLast[p.product] = p.created;
    if (p.created >= cutoff) {
      bump(winOrders, p.site); bump(winGross, p.site, p.amount);
      const day = isoDay(p.created);
      byDay[day] = byDay[day] || { orders: 0, gross: 0 };
      byDay[day].orders += 1;
      byDay[day].gross += p.amount;
    }
  }

  const bySite = Object.keys(siteOrders)
    .map((k) => ({
      key: k, label: SITE_LABEL[k] || k,
      orders: siteOrders[k], gross: siteGross[k],
      windowOrders: winOrders[k] || 0, windowGross: winGross[k] || 0,
    }))
    .sort((a, b) => b.gross - a.gross);

  const byProduct = Object.keys(prodOrders)
    .map((k) => ({
      key: k, site: SITE_OF_PRODUCT.get(k) || "unknown",
      orders: prodOrders[k], gross: prodGross[k],
      lastOrder: isoDay(prodLast[k]),
    }))
    .sort((a, b) => b.gross - a.gross);

  const refunds = {
    orders: customer.filter((p) => p.refunded > 0).length,
    amount: customer.reduce((n, p) => n + p.refunded, 0),
    disputes: customer.filter((p) => p.disputed).length,
  };

  // --- subscriptions: MRR, active, trials, churn --------------------------------
  const subRows = subs.rows.filter((s) => {
    const c = s.customer && typeof s.customer === "object" ? s.customer : null;
    return !isOwner(c && c.email);
  });
  const liveStatus = new Set(["active", "past_due"]);
  const perProduct = {};
  let mrr = 0, active = 0, trialing = 0, cancelScheduled = 0;
  let newInWindow = 0, trialsStarted = 0, trialsEnded = 0, trialsConverted = 0, churned = 0;
  for (const s of subRows) {
    const product = (s.metadata && s.metadata.product) || "unknown";
    const row = perProduct[product] || (perProduct[product] = { active: 0, trialing: 0, mrr: 0 });
    const itemsMrr = ((s.items && s.items.data) || []).reduce((n, it) => n + monthlyCents(it), 0);
    if (liveStatus.has(s.status)) { active++; row.active++; mrr += itemsMrr; row.mrr += itemsMrr; }
    if (s.status === "trialing") { trialing++; row.trialing++; }
    if (s.cancel_at_period_end && (liveStatus.has(s.status) || s.status === "trialing")) cancelScheduled++;
    if (s.created >= cutoff) newInWindow++;
    if (s.trial_start && s.trial_start >= cutoff) trialsStarted++;
    if (s.trial_end && s.trial_end >= cutoff && s.trial_end <= now) {
      trialsEnded++;
      if (liveStatus.has(s.status) || (s.status === "canceled" && s.ended_at && s.ended_at > s.trial_end + 86400)) {
        trialsConverted++;
      }
    }
    const endedAfterPaying = s.ended_at && (!s.trial_end || s.ended_at > s.trial_end + 86400);
    if (s.status === "canceled" && s.ended_at >= cutoff && endedAfterPaying) churned++;
  }
  const subscriptions = {
    mrr, active, trialing, cancelScheduled,
    window: { days, new: newInWindow, trialsStarted, trialsEnded, trialsConverted, churned },
    byProduct: perProduct,
  };

  let balance = null;
  try {
    const b = await stripeGet("/balance", {}, key);
    const sum = (rows) => (rows || []).reduce((n, r) => n + r.amount, 0);
    balance = { available: sum(b.available), pending: sum(b.pending) };
  } catch {
    /* balance is a nicety; sales still render without it */
  }

  // Follow-up email counts from the backend (trial sign-ups and how many
  // bought, reminders waiting, unsubscribes). Optional, like the balance.
  let lifecycle = null;
  const backendSecret = Netlify.env.get("BACKEND_WEBHOOK_SECRET");
  if (backendSecret) {
    try {
      const r = await fetch(LIFECYCLE_STATS_URL, {
        headers: { "x-webhook-secret": backendSecret },
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) lifecycle = await r.json();
    } catch {
      /* the sales figures stand on their own */
    }
  }

  return json(200, {
    generatedAt: new Date().toISOString(),
    lifecycle,
    currency: "usd",
    allTime,
    window: windowTotals,
    bySite,
    byProduct,
    byDay,
    recent: customer.slice(0, 12).map((p) => ({
      date: new Date(p.created * 1000).toISOString().slice(0, 16).replace("T", " "),
      product: p.product, site: p.site, amount: p.amount, email: p.email,
    })),
    // Every customer order, newest first. No emails: `cust` is a salted hash.
    ledger: customer.map((p) => ({
      id: p.id, kind: p.kind, ts: p.created, product: p.product, site: p.site,
      gross: p.amount, fee: p.fee, net: p.net, refunded: p.refunded, disputed: p.disputed,
      cust: custKey(p.email), attr: p.attr,
    })),
    refunds,
    subscriptions,
    balance,
    truncated,
    selfTests: {
      orders: selfTests.length,
      gross: selfTests.reduce((n, p) => n + p.amount, 0),
      note: "Owner test purchases, excluded from every figure above.",
    },
  });
}
