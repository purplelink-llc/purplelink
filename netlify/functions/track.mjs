/**
 * Netlify Function — first-party, cookieless analytics collector (purplelink).
 *
 * POST /.netlify/functions/track
 *   body: { t: "pageview"|"tool_use"|..., p: path, h: host, r: referrer-host,
 *           u: utm_source, m: meta (e.g. the tool's API path) }
 *
 * Complements the existing Cloudflare Web Analytics (which gives sampled
 * pageviews but no custom events) by recording which LaTeX tools are actually
 * *run* and which articles are read. Stores one small JSON record per event in
 * the `analytics` Netlify Blobs store, keyed by day. No cookies, no
 * fingerprinting; the only per-visitor value is a daily-salted hash of the IP
 * (rotates every day, can't be reversed or linked across days). stats.mjs
 * aggregates on read. Honors Do Not Track. Best-effort: returns 204 even on an
 * internal hiccup so analytics never breaks a page.
 */

import { getStore } from "@netlify/blobs";
import { createHash, randomUUID } from "node:crypto";

const BOT_RE = /bot|spider|crawl|slurp|bingpreview|headless|lighthouse|preview|facebookexternalhit|embedly/i;

function clip(v, n) {
  return String(v == null ? "" : v).slice(0, n);
}

export default async function handler(request) {
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

  const ip =
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const vid = createHash("sha256").update(`${day}|pl|${ip}`).digest("hex").slice(0, 16);

  const rec = { type, path, host, refHost, utm, meta, vid, ts: Date.now() };

  try {
    await getStore("analytics").setJSON(`ev/${day}/${Date.now()}-${randomUUID().slice(0, 8)}`, rec);
  } catch (_) {
    // Never let analytics failure surface to the visitor.
  }
  return new Response(null, { status: 204 });
}
