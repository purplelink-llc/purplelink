/**
 * Netlify Function — sales reader, owner-only.
 *
 * GET /.netlify/functions/sales?token=SECRET&days=30
 *
 * Both sites sell through the same Stripe account and tag every Checkout
 * Session with metadata.product, so one pass over the sessions gives revenue
 * for purplelink.llc and getmuscleonglp.com at once, split by product. The
 * traffic dashboard renders this above the traffic cards.
 *
 * Gated by STATS_TOKEN, the same owner-only token the stats function uses, so
 * the dashboard needs no second credential.
 *
 * Counts paid Checkout Sessions. Refunds and disputes are NOT deducted — the
 * Stripe balance at the bottom of the response is the authority on money that
 * actually landed.
 */

const STRIPE_API = "https://api.stripe.com/v1";
const PAGE_SIZE = 100;
const MAX_PAGES = 10; // 1000 sessions; `truncated` says when that was not enough

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
  "kit-clip": "purplelink", "moderntex": "purplelink",

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

async function stripeGet(path, params, key) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`${STRIPE_API}${path}${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!resp.ok) throw new Error(`stripe ${path} ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  return resp.json();
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
  const cutoff = Math.floor(Date.now() / 1000) - days * 86400;

  // The owner's own end-to-end test purchases are real Stripe charges and would
  // otherwise pad the order count and revenue. Kept out of every total and
  // reported separately, so the headline number is money other people paid.
  // Set SALES_EXCLUDE_EMAILS on the site rather than naming addresses here.
  const ownerEmails = new Set(
    (Netlify.env.get("SALES_EXCLUDE_EMAILS") || "")
      .split(",").map((e) => e.trim().toLowerCase()).filter(Boolean),
  );

  // --- collect paid sessions --------------------------------------------------
  const paid = [];
  let startingAfter = null, pages = 0, truncated = false;
  try {
    for (; pages < MAX_PAGES; pages++) {
      const params = { limit: String(PAGE_SIZE) };
      if (startingAfter) params.starting_after = startingAfter;
      const page = await stripeGet("/checkout/sessions", params, key);
      const rows = page.data || [];
      for (const s of rows) {
        if (s.payment_status !== "paid") continue;
        const product = (s.metadata && s.metadata.product) || "unknown";
        paid.push({
          created: s.created,
          product,
          site: SITE_OF_PRODUCT.get(product) || "unknown",
          amount: s.amount_total || 0,
          currency: s.currency || "usd",
          email: (s.customer_details && s.customer_details.email) || "",
        });
      }
      if (!page.has_more || !rows.length) break;
      startingAfter = rows[rows.length - 1].id;
    }
    truncated = pages >= MAX_PAGES;
  } catch (err) {
    return json(502, { error: "stripe_unreachable", detail: String(err).slice(0, 300) });
  }

  paid.sort((a, b) => b.created - a.created);

  const selfTests = paid.filter((p) => ownerEmails.has(p.email.toLowerCase()));
  const customer = paid.filter((p) => !ownerEmails.has(p.email.toLowerCase()));

  // --- aggregate --------------------------------------------------------------
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
      const day = new Date(p.created * 1000).toISOString().slice(0, 10);
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
      lastOrder: new Date(prodLast[k] * 1000).toISOString().slice(0, 10),
    }))
    .sort((a, b) => b.gross - a.gross);

  let balance = null;
  try {
    const b = await stripeGet("/balance", {}, key);
    const sum = (rows) => (rows || []).reduce((n, r) => n + r.amount, 0);
    balance = { available: sum(b.available), pending: sum(b.pending) };
  } catch {
    /* balance is a nicety; sales still render without it */
  }

  return json(200, {
    generatedAt: new Date().toISOString(),
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
    balance,
    truncated,
    selfTests: {
      orders: selfTests.length,
      gross: selfTests.reduce((n, p) => n + p.amount, 0),
      note: "Owner test purchases, excluded from every figure above.",
    },
  });
}
