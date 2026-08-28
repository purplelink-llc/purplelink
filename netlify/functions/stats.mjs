/**
 * Netlify Function — analytics reader/aggregator (purplelink), owner-only.
 *
 * GET /.netlify/functions/stats?token=SECRET&days=30
 *
 * Aggregates the per-event records track.mjs wrote into a JSON summary:
 * pageviews + rough uniques per day, top paths (articles + tool pages), top
 * referrers, UTM sources, per-host split, and — the reason this exists —
 * `tool_use` runs grouped by tool page, so you can finally see which LaTeX
 * tools have actually been used and how often.
 *
 * Gated by STATS_TOKEN (set it on the Netlify site). Scale note: this
 * lists+reads one blob per event, fine at early-stage volume; if daily events
 * reach the thousands, switch to pre-aggregated counters.
 */

import { getStore } from "@netlify/blobs";

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
function bump(obj, key, n = 1) { if (key) obj[key] = (obj[key] || 0) + n; }

/* Run fn over items with at most `limit` in flight, preserving input order.
   Bounded rather than a bare Promise.all: a month of events is unbounded in
   principle, and firing every read at once risks throttling or exhausting
   sockets, which would trade a slow response for a flaky one. */
async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    for (let i = next++; i < items.length; i = next++) out[i] = await fn(items[i]);
  });
  await Promise.all(workers);
  return out;
}
function topN(obj, n = 25) {
  return Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([k, v]) => ({ key: k, count: v }));
}
// Turn a tool API path or page path into a readable tool name.
function toolName(rec) {
  const p = rec.path || "";
  const m = p.match(/\/tools\/([a-z0-9-]+)/i);
  if (m) return m[1];
  if (rec.meta) return rec.meta.replace(/^\//, "").split("?")[0];
  return p || "(unknown)";
}

export default async function handler(request) {
  const url = new URL(request.url);
  const expected = Netlify.env.get("STATS_TOKEN");
  if (!expected) return json(500, { error: "misconfigured", detail: "Set STATS_TOKEN on this site." });
  if (url.searchParams.get("token") !== expected) return json(401, { error: "unauthorized" });

  let days = parseInt(url.searchParams.get("days") || "30", 10);
  if (!Number.isFinite(days) || days < 1) days = 30;
  if (days > 120) days = 120;

  const store = getStore("analytics");
  const now = Date.now();
  const s = {
    totals: { pageviews: 0, toolRuns: 0, checkoutClicks: 0, events: 0 },
    byPath: {}, byReferrer: {}, byUtm: {}, byHost: {}, toolRuns: {},
    checkoutByProduct: {},
    byDay: {},
  };
  const uniquesPerDay = {};

  // Every blob read used to be awaited one at a time, so the wall clock was
  // (number of events) x (one round trip). At ~670 events over 30 days that
  // reached 21s and started returning 502 once it crossed the function
  // timeout: the 2026-08-14 dashboard run fell back to archived figures for
  // this reason. The work is entirely IO-bound, so issuing the reads
  // concurrently removes the problem without changing what is counted. The
  // scale note at the top of this file still stands: pre-aggregated counters
  // are the real answer once daily volume gets large enough that even the
  // parallel version is slow.
  const dayKeys = Array.from({ length: days },
    (_, i) => new Date(now - i * 86400000).toISOString().slice(0, 10));

  const listings = await mapLimit(dayKeys, 10, async (day) => {
    try {
      const listing = await store.list({ prefix: `ev/${day}/` });
      return { day, blobs: (listing && listing.blobs) || [] };
    } catch (_) {
      return { day, blobs: null };   // null means "could not read", not "no events"
    }
  });

  for (const { day, blobs } of listings) {
    if (!blobs) continue;            // preserves the old behaviour: skip the day entirely
    if (!s.byDay[day]) s.byDay[day] = { pageviews: 0, uniques: 0, toolRuns: 0, checkoutClicks: 0 };
    if (!uniquesPerDay[day]) uniquesPerDay[day] = new Set();

    const records = await mapLimit(blobs, 64, async (b) => {
      try { return await store.get(b.key, { type: "json" }); } catch (_) { return null; }
    });

    for (const rec of records) {
      if (!rec) continue;
      s.totals.events++;
      if (rec.vid) uniquesPerDay[day].add(rec.vid);
      if (rec.host) bump(s.byHost, rec.host);

      if (rec.type === "pageview") {
        s.totals.pageviews++; s.byDay[day].pageviews++;
        bump(s.byPath, rec.path);
        if (rec.refHost) bump(s.byReferrer, rec.refHost);
        if (rec.utm) bump(s.byUtm, rec.utm);
      } else if (rec.type === "tool_use") {
        s.totals.toolRuns++; s.byDay[day].toolRuns++;
        bump(s.toolRuns, toolName(rec));
      } else if (rec.type === "checkout_click" && !String(rec.meta || "").startsWith("__")) {
        // Product keys are dunder-prefixed only by the self-test that verifies
        // the beacon actually fires end to end. Real keys never look like this,
        // and two synthetic clicks would badly distort a counter whose honest
        // value is currently zero.
        // Buy-button presses, counted at intent rather than at payment, and
        // split by product so a page with traffic but no clicks is
        // distinguishable from one with clicks that never reach Stripe.
        s.totals.checkoutClicks++; s.byDay[day].checkoutClicks++;
        bump(s.checkoutByProduct, rec.meta || "unknown");
      }
    }
    s.byDay[day].uniques = uniquesPerDay[day].size;
  }

  return json(200, {
    generatedAt: new Date().toISOString(),
    totals: s.totals,
    toolRuns: topN(s.toolRuns),
    checkoutByProduct: topN(s.checkoutByProduct),
    topPaths: topN(s.byPath),
    topReferrers: topN(s.byReferrer),
    topUtm: topN(s.byUtm),
    byHost: topN(s.byHost),
    byDay: Object.fromEntries(Object.entries(s.byDay).sort()),
  });
}
