/**
 * Netlify Function — first-party, cookieless analytics collector (purplelink).
 *
 * POST /.netlify/functions/track
 *   body: { t: "pageview"|"tool_use"|..., p: path, h: host, r: referrer-host,
 *           u: utm_source, m: meta (e.g. the tool's API path),
 *           ft: first-touch channel label, funnel events only }
 *
 * Complements the existing Cloudflare Web Analytics (which gives sampled
 * pageviews but no custom events) by recording which LaTeX tools are actually
 * *run* and which articles are read. Stores one small JSON record per event in
 * the `analytics` Netlify Blobs store, keyed by day. No cookies, no
 * fingerprinting; the only per-visitor value is a daily-salted hash of the IP
 * (rotates every day, can't be reversed or linked across days). stats.mjs
 * aggregates on read. Each record also carries `cc`, a two-letter country code from Netlify's geolocation (no city,
 * region, coordinates or IP), empty when unavailable. Honors Do Not Track. Best-effort: returns 204 even on an
 * internal hiccup so analytics never breaks a page.
 */

import { getStore } from "@netlify/blobs";
import { createHash, randomUUID } from "node:crypto";

const BOT_RE = /bot|spider|crawl|slurp|bingpreview|headless|lighthouse|preview|facebookexternalhit|embedly/i;

function clip(v, n) {
  return String(v == null ? "" : v).slice(0, n);
}

/**
 * Two-letter country code of the request, from Netlify's own geolocation, or "" when it is not there or not exactly two
 * letters. Only the country is ever read: city, region, coordinates and the IP never reach the record. Netlify Functions
 * v2 passes it as context.geo.country.code (ISO 3166-1 alpha-2); the x-nf-geo header (base64 JSON, same shape) is the
 * fallback for a runtime that does not pass the context.
 */
export function countryCode(request, context) {
  let code = context && context.geo && context.geo.country && context.geo.country.code;
  if (code == null) {
    try {
      const h = request.headers.get("x-nf-geo");
      if (h) code = JSON.parse(Buffer.from(h, "base64").toString("utf8"))?.country?.code;
    } catch (_) { /* malformed header: treat as absent */ }
  }
  code = typeof code === "string" ? code.trim() : "";
  return /^[A-Za-z]{2}$/.test(code) ? code.toUpperCase() : "";
}

export default async function handler(request, context) {
  if (request.method !== "POST") {
    return new Response("", { status: 405 });
  }
  if (request.headers.get("dnt") === "1") {
    return new Response(null, { status: 204 });
  }
  const ua = request.headers.get("user-agent") || "";
  if (BOT_RE.test(ua)) {
    return new Response(null, { status: 204 });
  }

  let b;
  try {
    b = await request.json();
  } catch (_) {
    return new Response(null, { status: 204 });
  }

  const type = clip(b.t || "pageview", 32);
  const path = clip(b.p || "/", 200);
  const host = clip(b.h, 80);
  const refHost = clip(b.r, 120);   // host only, set client-side (no full URL, no query)
  const utm = clip(b.u, 60);
  const meta = clip(b.m, 120);
  // First-touch channel label, sent only with pageviews, trial downloads and buy clicks (analytics.js).
  const ft = clip(String(b.ft || "").replace(/[^\w.\-:\/ ]/g, ""), 40);

  const ip =
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const vid = createHash("sha256").update(`${day}|pl|${ip}`).digest("hex").slice(0, 16);

  // Country only (see countryCode). Always present; "" when Netlify gave none. Older records have no cc at all.
  const rec = { type, path, host, refHost, utm, meta, vid, ts: Date.now(), cc: countryCode(request, context) };
  if (ft) rec.ft = ft;

  try {
    await getStore("analytics").setJSON(`ev/${day}/${Date.now()}-${randomUUID().slice(0, 8)}`, rec);
  } catch (_) {
    // Never let analytics failure surface to the visitor.
  }
  return new Response(null, { status: 204 });
}
