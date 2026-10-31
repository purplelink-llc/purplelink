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
 * GET ...stats?section=signals&weeks=8 returns only the count-only answers signal.mjs stores (why-not and
 * trial-download poll), per ISO week, newest first. No analytics records are read for it.
 *
 * GET ...stats?section=tools&weeks=8 returns, per ISO week (newest first) and per free tool, the counts tool-counts stores
 * (runs, ok, error, limit, offerViews, offerClicks; see lib/tool-counts.mjs), plus what visitors whose first touch was that
 * tool's offer link went on to do (page views, daily visitors, trial downloads, buy clicks, read from the event records).
 *
 * Gated by STATS_TOKEN (set it on the Netlify site). Scale note: this
 * lists+reads one blob per event, fine at early-stage volume; if daily events
 * reach the thousands, switch to pre-aggregated counters.
 */

import { getStore } from "@netlify/blobs";
import { ownerToken, safeEqual } from "../lib/auth.mjs";
import { readSignals, recentWeeks, isoWeek } from "../lib/signals.mjs";
import { TOOL_SLUGS, COUNT_FIELDS, emptyCounts, readToolCounts } from "../lib/tool-counts.mjs";

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
function bump(obj, key, n = 1) { if (key) obj[key] = (obj[key] || 0) + n; }

// LinkedIn arrives under several names: any linkedin.com host, lnkd.in, the Android app referrer
// (android-app://com.linkedin.android, or com.linkedin.android as a bare host) and utm_source=linkedin in any
// case. They are one channel, "linkedin". Only the host is read, so a label that merely contains "linkedin"
// in a path or query does not match. This mirrors isLinkedin() in site/analytics.js; it is applied here when
// records are read, so history stored under the separate labels is counted too and no stored record changes.
export function isLinkedin(v) {
  const h = String(v || "").toLowerCase().replace(/^[a-z][a-z0-9+.\-]*:\/\//, "").split(/[/?#]/)[0].replace(/:\d+$/, "");
  return h === "linkedin" || h === "lnkd.in" || /(^|\.)linkedin\.com$/.test(h) || /^com\.linkedin\.android(\.[a-z]+)?$/.test(h);
}
// The social poster's other channels (scripts/social, docs/social-poster.md), each one label however it arrives: the
// utm_source its short links carry (/bs/ bluesky, /th/ threads, /x/ x, /md/ mastodon, /dev/ devto) or the referring
// host. Host match only, the same way as isLinkedin. Folded here at read time, so site/analytics.js is unchanged
// and records stored under a host label are counted too. Mastodon servers vary: the common ones are listed and every
// poster link carries utm_source=mastodon anyway.
const SOCIAL = [
  ["bluesky", /^(bluesky|bsky|bsky\.app|bsky\.social|go\.bsky\.app)$/],
  ["threads", /^(threads|(www\.|l\.)?threads\.(net|com))$/],
  ["x", /^(x|twitter|t\.co|(www\.|mobile\.)?(x|twitter)\.com)$/],
  ["mastodon", /^(mastodon|mastodon\.(social|online|world)|mas\.to|mstdn\.social|fosstodon\.org|hachyderm\.io|infosec\.exchange|sigmoid\.social|scholar\.social)$/],
  ["devto", /^(devto|(www\.)?dev\.to)$/],
];
export function socialChannel(v) {
  const h = String(v || "").toLowerCase().replace(/^[a-z][a-z0-9+.\-]*:\/\//, "").split(/[/?#]/)[0].replace(/:\d+$/, "");
  for (const [name, re] of SOCIAL) if (re.test(h)) return name;
  return "";
}
export const foldChannel = (v) => (isLinkedin(v) ? "linkedin" : socialChannel(v) || v);

// The free tool pages tag their offer link utm_source=tool-<slug>. That is channel "tool" with the slug as detail, written
// "tool:<slug>". Only a campaign source or a first-touch label is folded, never a referrer host, so a referring site with
// "tool" in its name keeps its own label (a host has a dot; the pattern has none). This mirrors toolChannel() in
// site/analytics.js, which writes "tool:<slug>" for new visits; this fold also catches a cached older script's "tool-<slug>".
export function toolChannel(v) {
  const m = /^tool-([a-z0-9][a-z0-9-]{0,39})$/i.exec(String(v || ""));
  return m ? `tool:${m[1].toLowerCase()}` : "";
}
export const foldSource = (v) => toolChannel(v) || foldChannel(v);

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

// Journeys (analytics backlog AB-20261020-3): of the visitors whose first page of the day was a guide, a tool or
// anything else, how many viewed a product page later that day, and which one. Built from the daily-salted visitor
// hash already on every record, so a journey never spans two days and nothing new is stored.
export const PRODUCT_PAGES = ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "panely", "summonly", "suite", "vitae", "batterymeter"];
const PRODUCT_RE = new RegExp(`^/(${PRODUCT_PAGES.join("|")})/`);
export const entryKind = (path) => (/^\/guides\//.test(path) ? "guide" : /^\/tools\//.test(path) ? "tool" : PRODUCT_RE.test(path) ? "product" : "other");
export const productOf = (path) => { const m = PRODUCT_RE.exec(path || ""); return m ? m[1] : ""; };
/** visits: Map of vid -> [{ ts, path }] for one day. Returns { guide|tool|product|other: { visitors, reachedProduct, byProduct } }. */
export function journeysOf(visits) {
  const out = {};
  for (const views of visits.values()) {
    views.sort((a, b) => a.ts - b.ts);
    const kind = entryKind(views[0].path);
    const o = out[kind] || (out[kind] = { visitors: 0, reachedProduct: 0, byProduct: {} });
    o.visitors++;
    if (kind === "product") continue;
    const reached = new Set(views.slice(1).map((v) => productOf(v.path)).filter(Boolean));
    if (reached.size) o.reachedProduct++;
    for (const pr of reached) o.byProduct[pr] = (o.byProduct[pr] || 0) + 1;
  }
  return out;
}
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

const TOOL_SET = new Set(TOOL_SLUGS);

/**
 * The ?section=tools answer. Counts come from the tool-counts store (the day-and-tool records track.mjs writes). The
 * attribution columns come from the event records: pageviews whose first-touch label folds to tool:<slug>, the distinct
 * daily visitors among them (a visitor id is a per-day hash, so a person on two days counts twice), and the trial
 * downloads and buy clicks that carry the same label. Orders are not here: the Stripe order's first-touch metadata is
 * read by the dashboard's ledger, not by this function.
 */
async function toolsSection(weeks) {
  const now = Date.now();
  const days = Array.from({ length: weeks * 7 }, (_, i) => new Date(now - i * 86400000).toISOString().slice(0, 10));
  const weekOf = (day) => isoWeek(new Date(`${day}T12:00:00Z`));
  // The weeks the last weeks*7 days touch, newest first; the oldest may be only partly covered.
  const weekLabels = [...new Set(days.map(weekOf))];

  const out = {};   // week -> slug -> counts + attributed
  const row = (week, slug) => {
    const w = out[week] || (out[week] = {});
    return w[slug] || (w[slug] = { ...emptyCounts(), attributed: { pageviews: 0, dayVisitors: 0, trialDownloads: 0, checkoutClicks: 0 } });
  };

  const counts = await readToolCounts(getStore("tool-counts"), days);
  for (const [day, bySlug] of Object.entries(counts)) {
    const week = weekOf(day);
    for (const [slug, c] of Object.entries(bySlug)) {
      const r = row(week, slug);
      for (const f of COUNT_FIELDS) r[f] += c[f];
    }
  }

  const events = getStore("analytics");
  await mapLimit(days, 6, async (day) => {
    const week = weekOf(day);
    let blobs = [];
    try { blobs = ((await events.list({ prefix: `ev/${day}/` })) || {}).blobs || []; } catch (_) { return; }
    const seen = {};
    const recs = await mapLimit(blobs, 64, async (b) => {
      try { return await events.get(b.key, { type: "json" }); } catch (_) { return null; }
    });
    for (const rec of recs) {
      if (!rec || !rec.ft || String(rec.meta || "").startsWith("__")) continue;
      if (EXTERNAL_HOSTS.includes(normalizeHost(rec.host))) continue;
      const ch = foldSource(rec.ft);
      if (!ch.startsWith("tool:")) continue;
      const slug = ch.slice(5);
      const key = TOOL_SET.has(slug) ? slug : "(other)";
      const a = row(week, key).attributed;
      if (rec.type === "pageview") {
        a.pageviews++;
        const set = seen[key] || (seen[key] = new Set());
        if (rec.vid && !set.has(rec.vid)) { set.add(rec.vid); a.dayVisitors++; }
      } else if (/_?trial_download$/.test(rec.type)) a.trialDownloads++;
      else if (rec.type === "checkout_click") a.checkoutClicks++;
    }
  });

  return {
    generatedAt: new Date().toISOString(),
    weeks: weekLabels,
    tools: Object.fromEntries(weekLabels.filter((w) => out[w]).map((w) => [w, Object.fromEntries(Object.entries(out[w]).sort())])),
    notes: [
      "runs counts tool_use beacons; ok, error and limit count how a backend run ended and are only sent by tools that call the compile and convert API, so they can sum to less than runs.",
      "The oldest week listed may be only partly covered. offerViews counts a page view once when half the offer card was on screen; offerClicks counts clicks on its link.",
      "attributed.* reads visitors whose first touch was utm_source=tool-<slug>. Orders are not included: read them from the Stripe checkout metadata (attr_first) in the dashboard ledger.",
    ],
  };
}

export default async function handler(request) {
  const url = new URL(request.url);
  const expected = Netlify.env.get("STATS_TOKEN");
  if (!expected) return json(500, { error: "misconfigured", detail: "Set STATS_TOKEN on this site." });
  if (!safeEqual(ownerToken(request, url), expected)) return json(401, { error: "unauthorized" });

  if (url.searchParams.get("section") === "signals") {
    let weeks = parseInt(url.searchParams.get("weeks") || "8", 10);
    if (!Number.isFinite(weeks) || weeks < 1) weeks = 8;
    if (weeks > 52) weeks = 52;
    try {
      return json(200, { generatedAt: new Date().toISOString(), signals: await readSignals(getStore("signals"), recentWeeks(weeks)) });
    } catch (_) {
      return json(502, { error: "signals_unavailable" });
    }
  }

  if (url.searchParams.get("section") === "tools") {
    let weeks = parseInt(url.searchParams.get("weeks") || "8", 10);
    if (!Number.isFinite(weeks) || weeks < 1) weeks = 8;
    if (weeks > 16) weeks = 16;
    try {
      return json(200, await toolsSection(weeks));
    } catch (_) {
      return json(502, { error: "tools_unavailable" });
    }
  }

  // ?host=<host> returns only that host's records; without it, EXTERNAL_HOSTS are left out.
  const hostFilter = normalizeHost(url.searchParams.get("host"));
  if (url.searchParams.has("host") && !/^[a-z0-9.-]{1,80}$/.test(hostFilter)) return json(400, { error: "bad_host" });

  let days = parseInt(url.searchParams.get("days") || "30", 10);
  if (!Number.isFinite(days) || days < 1) days = 30;
  if (days > 120) days = 120;

  const store = getStore("analytics");
  const now = Date.now();
  const s = {
    totals: { pageviews: 0, toolRuns: 0, checkoutClicks: 0, trialDownloads: 0, ovTrialDownloads: 0, lgTrialDownloads: 0, kfTrialDownloads: 0, tfTrialDownloads: 0, pnTrialDownloads: 0, smTrialDownloads: 0, guideTrialClicks: 0, guidePageClicks: 0, events: 0 },
    byPath: {}, byReferrer: {}, byUtm: {}, byHost: {}, toolRuns: {},
    checkoutByProduct: {}, checkoutByPath: {},
    otherEvents: {}, otherEventDetail: {},
    guideTrialByPlacement: {}, guidePageByPlacement: {},
    byDay: {},
    funnelByChannel: {},
    funnelByContent: {},
    excludedHosts: {},
    journeysByDay: {},
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
      s.byDay[day] = { pageviews: 0, uniques: 0, toolRuns: 0, checkoutClicks: 0, trialDownloads: 0, ovTrialDownloads: 0, lgTrialDownloads: 0, kfTrialDownloads: 0, tfTrialDownloads: 0, pnTrialDownloads: 0, smTrialDownloads: 0, guideTrialClicks: 0, guidePageClicks: 0 };
      if (hostFilter) for (const f of Object.values(HOST_EVENT_FIELDS)) s.byDay[day][f] = 0;
    }
    if (!uniquesPerDay[day]) uniquesPerDay[day] = new Set();
    const visits = new Map();

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
        const ft = foldSource(rec.ft);
        const fc = s.funnelByChannel[ft] || (s.funnelByChannel[ft] = { pageviews: 0, pageviewsByPath: {}, trial: {}, checkout: {}, os: {} });
        // Operating-system family of the channel's pageviews (records before 2026-10-31 have none and are not counted).
        if (rec.type === "pageview") { fc.pageviews++; bump(fc.pageviewsByPath, rec.path); if (rec.os) bump(fc.os, rec.os); }
        else if (rec.type === "checkout_click") bump(fc.checkout, rec.meta || "unknown");
        else if (/_?trial_download$/.test(rec.type)) bump(fc.trial, rec.meta || rec.type);
        else if (rec.type === "guide_mtx_trial") bump(fc.trial, "guide_mtx_trial");
        // The same counts by the first-touch link tag (utm_content), so one placement can be read on its own.
        if (rec.fc) {
          const fk = String(rec.fc).slice(0, 60);
          const fx = s.funnelByContent[fk] || (s.funnelByContent[fk] = { channel: ft, pageviews: 0, pageviewsByPath: {}, trial: {}, checkout: {}, os: {} });
          if (rec.type === "pageview") { fx.pageviews++; bump(fx.pageviewsByPath, rec.path); if (rec.os) bump(fx.os, rec.os); }
          else if (rec.type === "checkout_click") bump(fx.checkout, rec.meta || "unknown");
          else if (/_?trial_download$/.test(rec.type)) bump(fx.trial, rec.meta || rec.type);
          else if (rec.type === "guide_mtx_trial") bump(fx.trial, "guide_mtx_trial");
        }
      }

      if (rec.type === "pageview") {
        if (rec.vid && !hostFilter && typeof rec.path === "string") {
          const v = visits.get(rec.vid) || visits.set(rec.vid, []).get(rec.vid);
          v.push({ ts: Number(rec.ts) || 0, path: rec.path });
        }
        s.totals.pageviews++; s.byDay[day].pageviews++;
        bump(s.byPath, rec.path);
        if (rec.refHost) bump(s.byReferrer, foldChannel(rec.refHost));
        if (rec.utm) bump(s.byUtm, foldSource(rec.utm));
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
      } else if ((rec.type === "guide_mtx_trial" || rec.type === "guide_mtx_click") && !String(rec.meta || "").startsWith("__")) {
        // ModernTex cards in the guides (2026-10-15): "guide_mtx_trial" is the card's trial button, which downloads the
        // DMG directly and so is not a trial_download (that keeps the /moderntex/ hero test clean); "guide_mtx_click"
        // goes to the product page. meta is the placement, e.g. "editors-guide:top-page".
        const trial = rec.type === "guide_mtx_trial";
        const f = trial ? "guideTrialClicks" : "guidePageClicks";
        s.totals[f]++; s.byDay[day][f]++;
        bump(trial ? s.guideTrialByPlacement : s.guidePageByPlacement, String(rec.meta || "unknown").slice(0, 80));
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
    if (!hostFilter) s.journeysByDay[day] = journeysOf(visits);
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
    // ModernTex cards in the guides, by placement (see the guide_mtx_* branch above).
    guideTrialByPlacement: topN(s.guideTrialByPlacement, 40),
    guidePageByPlacement: topN(s.guidePageByPlacement, 40),
    otherEvents: topN(s.otherEvents, 50),
    otherEventDetail: topN(s.otherEventDetail, 60),
    byDay: Object.fromEntries(Object.entries(s.byDay).sort()),
    ...(hostFilter ? {} : { journeysByDay: Object.fromEntries(Object.entries(s.journeysByDay).sort()) }),
    funnelByChannel: Object.fromEntries(Object.entries(s.funnelByChannel).map(([ch, v]) => [ch, {
      pageviews: v.pageviews, pageviewsByPath: Object.fromEntries(topN(v.pageviewsByPath, 40).map((x) => [x.key, x.count])),
      trial: v.trial, checkout: v.checkout, os: v.os,
    }])),
    funnelByContent: Object.fromEntries(Object.entries(s.funnelByContent).map(([k, v]) => [k, {
      channel: v.channel, pageviews: v.pageviews,
      pageviewsByPath: Object.fromEntries(topN(v.pageviewsByPath, 20).map((x) => [x.key, x.count])),
      trial: v.trial, checkout: v.checkout, os: v.os,
    }])),
  });
}
