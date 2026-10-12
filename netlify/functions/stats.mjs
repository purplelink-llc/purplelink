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
 * Other sites send their beacons to the same collector (track.mjs stores the host each event came from). Hosts in
 * EXTERNAL_HOSTS are kept OUT of the default aggregation, so Purplelink's own totals, paths, referrers and days never
 * include them, and are read on their own with ?host=<host>, which returns only that host's records in the same shape
 * plus per-day counts of the event types in HOST_EVENT_FIELDS and the breakdowns byCountry, device, scrollDepth and
 * engagedTime (never in the default response). Without the filter the response says how many records
 * it left out, in `excludedHosts`.
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

// Sites other than purplelink.llc that beacon to this collector. Their records are never mixed into the default numbers.
export const EXTERNAL_HOSTS = ["rubblefront.com"];
// Event types counted per day in a ?host= response (the host's own funnel), keyed to the byDay / totals field they feed.
export const HOST_EVENT_FIELDS = {
  steam_click: "steamClicks",
  outbound_click: "outboundClicks",
  download: "downloads",
  newsletter_submit: "newsletterSubmits",
};
// Values the rubblefront beacon sends as meta. Anything else is ignored by the ?host= breakdowns.
export const DEVICE_CLASSES = ["mobile", "tablet", "desktop"];
export const SCROLL_BUCKETS = ["0", "25", "50", "75", "100"];
export const ENGAGED_BUCKETS = ["0-10s", "10-30s", "30-60s", "1-3m", "3m-plus"];
const zeroed = (keys) => Object.fromEntries(keys.map((k) => [k, 0]));
/** A record's host, lower-cased without a leading "www.", so "RubbleFront.com" and "www.rubblefront.com" match. */
export function normalizeHost(h) {
  return String(h || "").trim().toLowerCase().replace(/^www\./, "");
}

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

  // ?host=<host> returns only that host's records; without it, EXTERNAL_HOSTS are left out.
  const hostFilter = normalizeHost(url.searchParams.get("host"));
  if (url.searchParams.has("host") && !/^[a-z0-9.-]{1,80}$/.test(hostFilter)) return json(400, { error: "bad_host" });

  let days = parseInt(url.searchParams.get("days") || "30", 10);
  if (!Number.isFinite(days) || days < 1) days = 30;
  if (days > 120) days = 120;

  const store = getStore("analytics");
  const now = Date.now();
  const s = {
    totals: { pageviews: 0, toolRuns: 0, checkoutClicks: 0, trialDownloads: 0, ovTrialDownloads: 0, lgTrialDownloads: 0, kfTrialDownloads: 0, tfTrialDownloads: 0, pnTrialDownloads: 0, smTrialDownloads: 0, events: 0 },
    byPath: {}, byReferrer: {}, byUtm: {}, byHost: {}, toolRuns: {},
    checkoutByProduct: {}, checkoutByPath: {},
    otherEvents: {}, otherEventDetail: {},
    byDay: {},
    funnelByChannel: {},
    excludedHosts: {},
  };
  if (hostFilter) for (const f of Object.values(HOST_EVENT_FIELDS)) s.totals[f] = 0;
  const uniquesPerDay = {};
  // ?host= only: country, device, scroll depth and engaged time. Read-only side tallies; they feed no total above.
  const geo = { countries: {}, unknown: 0 };
  const device = zeroed(DEVICE_CLASSES), scrollDepth = zeroed(SCROLL_BUCKETS), engagedTime = zeroed(ENGAGED_BUCKETS);

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
    if (!s.byDay[day]) {
      s.byDay[day] = { pageviews: 0, uniques: 0, toolRuns: 0, checkoutClicks: 0, trialDownloads: 0, ovTrialDownloads: 0, lgTrialDownloads: 0, kfTrialDownloads: 0, tfTrialDownloads: 0, pnTrialDownloads: 0, smTrialDownloads: 0 };
      if (hostFilter) for (const f of Object.values(HOST_EVENT_FIELDS)) s.byDay[day][f] = 0;
    }
    if (!uniquesPerDay[day]) uniquesPerDay[day] = new Set();

    const records = await mapLimit(blobs, 64, async (b) => {
      try { return await store.get(b.key, { type: "json" }); } catch (_) { return null; }
    });

    for (const rec of records) {
      if (!rec) continue;
      const recHost = normalizeHost(rec.host);
      if (hostFilter) {
        if (recHost !== hostFilter) continue;
      } else if (EXTERNAL_HOSTS.includes(recHost)) {
        bump(s.excludedHosts, recHost);
        continue;
      }
      if (hostFilter && !String(rec.meta || "").startsWith("__")) {
        const meta = String(rec.meta || "");
        if (rec.type === "pageview") {
          const cc = /^[A-Z]{2}$/.test(rec.cc || "") ? rec.cc : "";
          if (cc) bump(geo.countries, cc); else geo.unknown++;
          if (DEVICE_CLASSES.includes(meta)) device[meta]++;
        } else if (rec.type === "scroll_depth" && SCROLL_BUCKETS.includes(meta)) scrollDepth[meta]++;
        else if (rec.type === "engaged_time" && ENGAGED_BUCKETS.includes(meta)) engagedTime[meta]++;
      }
      s.totals.events++;
      if (rec.vid) uniquesPerDay[day].add(rec.vid);
      if (rec.host) bump(s.byHost, rec.host);
      // Funnel by first-touch channel (analytics.js sends ft on pageviews, trial downloads and buy clicks only).
      // Product-page views are the denominator for a channel's trial and buy rates; the path is kept for pageviews
      // so the dashboard can restrict them to product pages.
      if (rec.ft && !String(rec.meta || "").startsWith("__")) {
        const fc = s.funnelByChannel[rec.ft] || (s.funnelByChannel[rec.ft] = { pageviews: 0, pageviewsByPath: {}, trial: {}, checkout: {} });
        if (rec.type === "pageview") { fc.pageviews++; bump(fc.pageviewsByPath, rec.path); }
        else if (rec.type === "checkout_click") bump(fc.checkout, rec.meta || "unknown");
        else if (/_?trial_download$/.test(rec.type)) bump(fc.trial, rec.meta || rec.type);
      }

      if (rec.type === "pageview") {
        s.totals.pageviews++; s.byDay[day].pageviews++;
        bump(s.byPath, rec.path);
        if (rec.refHost) bump(s.byReferrer, rec.refHost);
        if (rec.utm) bump(s.byUtm, rec.utm);
      } else if (rec.type === "tool_use") {
        s.totals.toolRuns++; s.byDay[day].toolRuns++;
        bump(s.toolRuns, toolName(rec));
      } else if (rec.type === "trial_download") {
        // ModernTex trial DMG downloads (2026-09-11). The funnel this exists to
        // measure is trial_download -> checkout_click -> a paid session.
        s.totals.trialDownloads++; s.byDay[day].trialDownloads++;
      } else if (rec.type === "ov_trial_download") {
        // Outbound Veil trial DMG downloads (2026-10-04). A separate event type, not a second meta on
        // trial_download, so the ModernTex trial funnel above keeps counting only ModernTex.
        s.totals.ovTrialDownloads++; s.byDay[day].ovTrialDownloads++;
      } else if (rec.type === "lg_trial_download") {
        // Legroom trial DMG downloads. Its own event type for the same reason as Outbound Veil's.
        s.totals.lgTrialDownloads++; s.byDay[day].lgTrialDownloads++;
      } else if (rec.type === "kf_trial_download") {
        // Keyfeel trial DMG downloads. Its own event type, for the same reason.
        s.totals.kfTrialDownloads++; s.byDay[day].kfTrialDownloads++;
      } else if (rec.type === "tf_trial_download") {
        // Tapefolio trial DMG downloads. Its own event type, for the same reason.
        s.totals.tfTrialDownloads++; s.byDay[day].tfTrialDownloads++;
      } else if (rec.type === "pn_trial_download") {
        // Panely trial DMG downloads. Its own event type, for the same reason.
        s.totals.pnTrialDownloads++; s.byDay[day].pnTrialDownloads++;
      } else if (rec.type === "sm_trial_download") {
        // Summonly trial DMG downloads. Its own event type, for the same reason.
        s.totals.smTrialDownloads++; s.byDay[day].smTrialDownloads++;
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
        // Where the press happened. The dashboard's checkout rate divides by
        // views of pages that carry a buy button, and that list is maintained
        // by hand; recording the path makes it checkable instead of trusted.
        bump(s.checkoutByPath, rec.path || "unknown");
      } else if (hostFilter && HOST_EVENT_FIELDS[rec.type] && !String(rec.meta || "").startsWith("__")) {
        // This host's own funnel events (steam_click, outbound_click, download, newsletter_submit): a per-day count,
        // and the same type and type-plus-meta counts every other event gets.
        const f = HOST_EVENT_FIELDS[rec.type];
        s.totals[f]++; s.byDay[day][f]++;
        bump(s.otherEvents, rec.type);
        if (rec.meta) bump(s.otherEventDetail, `${rec.type}: ${String(rec.meta).slice(0, 80)}`);
      } else if (rec.type && !String(rec.meta || "").startsWith("__")) {
        // Every other first-party event (deadline_signup, feedback_rating,
        // checkout_canceled, search, tool_next, sticky_cta, ...) was stored
        // but never counted. Count by type, and by type plus its meta, so a
        // new event shows up here without another change to this file.
        bump(s.otherEvents, rec.type);
        if (rec.meta) bump(s.otherEventDetail, `${rec.type}: ${String(rec.meta).slice(0, 80)}`);
      }
    }
    s.byDay[day].uniques = uniquesPerDay[day].size;
  }

  return json(200, {
    generatedAt: new Date().toISOString(),
    ...(hostFilter ? { host: hostFilter } : { excludedHosts: s.excludedHosts }),
    totals: s.totals,
    ...(hostFilter ? {
      byCountry: {
        top: topN(geo.countries, 15),
        other: Object.values(geo.countries).reduce((a, n) => a + n, 0) - topN(geo.countries, 15).reduce((a, x) => a + x.count, 0),
        unknown: geo.unknown,
      },
      device, scrollDepth, engagedTime,
    } : {}),
    toolRuns: topN(s.toolRuns),
    checkoutByProduct: topN(s.checkoutByProduct),
    checkoutByPath: topN(s.checkoutByPath),
    // Full path list, not the default top-N. The dashboard derives its
    // checkout rate by summing views of pages that carry a buy button,
    // and truncation silently zeroed any product page outside the top
    // slice -- which is precisely the low-traffic product pages the
    // metric exists to measure. Both sites are well under 200 pages.
    topPaths: topN(s.byPath, 200),
    topReferrers: topN(s.byReferrer),
    topUtm: topN(s.byUtm),
    byHost: topN(s.byHost),
    otherEvents: topN(s.otherEvents, 50),
    otherEventDetail: topN(s.otherEventDetail, 60),
    byDay: Object.fromEntries(Object.entries(s.byDay).sort()),
    funnelByChannel: Object.fromEntries(Object.entries(s.funnelByChannel).map(([ch, v]) => [ch, {
      pageviews: v.pageviews, pageviewsByPath: Object.fromEntries(topN(v.pageviewsByPath, 40).map((x) => [x.key, x.count])),
      trial: v.trial, checkout: v.checkout,
    }])),
  });
}
