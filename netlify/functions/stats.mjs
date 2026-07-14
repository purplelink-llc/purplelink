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
    totals: { pageviews: 0, toolRuns: 0, events: 0 },
    byPath: {}, byReferrer: {}, byUtm: {}, byHost: {}, toolRuns: {},
    byDay: {},
  };
  const uniquesPerDay = {};

  for (let i = 0; i < days; i++) {
    const day = new Date(now - i * 86400000).toISOString().slice(0, 10);
    let listing;
    try { listing = await store.list({ prefix: `ev/${day}/` }); } catch (_) { continue; }
    const blobs = (listing && listing.blobs) || [];
    if (!s.byDay[day]) s.byDay[day] = { pageviews: 0, uniques: 0, toolRuns: 0 };
    if (!uniquesPerDay[day]) uniquesPerDay[day] = new Set();

    for (const b of blobs) {
      let rec;
      try { rec = await store.get(b.key, { type: "json" }); } catch (_) { continue; }
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
      }
    }
    s.byDay[day].uniques = uniquesPerDay[day].size;
  }

  return json(200, {
    generatedAt: new Date().toISOString(),
    totals: s.totals,
    toolRuns: topN(s.toolRuns),
    topPaths: topN(s.byPath),
    topReferrers: topN(s.byReferrer),
    topUtm: topN(s.byUtm),
    byHost: topN(s.byHost),
    byDay: Object.fromEntries(Object.entries(s.byDay).sort()),
  });
}
