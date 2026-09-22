/**
 * Netlify Function — Vitae delivery. Same shape as moderntex-download.mjs: the DMG
 * lives only in a private Blobs store and every download passes through here so it
 * can be counted. Vitae is free, so there is no purchase door.
 *
 *   GET /.netlify/functions/vitae-download                     -> newest Vitae DMG
 *   GET /.netlify/functions/vitae-download?file=Vitae-0.1.dmg  -> that DMG if staged,
 *                                                                  else the newest
 *   GET /.netlify/functions/vitae-download?stats=1             -> counts (JSON)
 *       requires header  X-Vitae-Stats: <VITAE_STATS_TOKEN>
 *
 * netlify.toml rewrites /vitae/download and every /vitae/Vitae-*.dmg URL here, so the
 * site button, old links, and the downloadURL that installed copies read from
 * /vitae/version.json all land on the counter without changing.
 *
 * Counts are requests we decided to serve (GET, non-crawler User-Agent), not
 * confirmed completions or unique machines. Crawlers are served but not counted:
 * the page's structured data advertises the download URL, so Googlebot fetches it.
 */
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";

const FILE_STORE = "vitae-files";
const STATS_STORE = "vitae-stats";
const DMG_NAME = /^Vitae-\d+\.\d+(\.\d+)?\.dmg$/;
const DAILY_LIMIT = 20;
const BOT_UA = /bot|crawl|spider|slurp|preview|facebookexternalhit|curl|wget|python-requests|httpclient|headless/i;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" },
  });
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function bump(stats, key) {
  const n = parseInt((await stats.get(key)) || "0", 10) || 0;
  await stats.set(key, String(n + 1));
}

async function latestDmgName(store) {
  const { blobs } = await store.list();
  const names = blobs.map((b) => b.key).filter((k) => DMG_NAME.test(k));
  const ver = (n) => n.match(/\d+/g).map(Number);
  names.sort((a, b) => {
    const va = ver(a), vb = ver(b);
    for (let i = 0; i < 3; i++) if ((va[i] || 0) !== (vb[i] || 0)) return (vb[i] || 0) - (va[i] || 0);
    return 0;
  });
  return names[0] || null;
}

async function streamBlob(store, key) {
  let r;
  try {
    r = await store.getWithMetadata(key, { type: "stream" });
  } catch (err) {
    return json(500, { error: "file_unavailable", detail: "The download is temporarily unavailable. Contact ben@purplelink.llc." });
  }
  if (!r) return json(404, { error: "file_unavailable", detail: "That file is not available. Contact ben@purplelink.llc." });
  const headers = {
    "Content-Type": "application/x-apple-diskimage",
    "Content-Disposition": `attachment; filename="${key}"`,
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (r.metadata?.size) headers["Content-Length"] = String(r.metadata.size);
  return new Response(r.data, { status: 200, headers });
}

async function serveStats() {
  const stats = getStore(STATS_STORE);
  const downloads = {}, byDay = {};
  for (const [prefix, out] of [["downloads:", downloads], ["day:", byDay]]) {
    const { blobs } = await stats.list({ prefix });
    for (const b of blobs) out[b.key.slice(prefix.length)] = parseInt((await stats.get(b.key)) || "0", 10) || 0;
  }
  return json(200, { downloads, byDay });
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });
  const url = new URL(request.url);

  if (url.searchParams.get("stats") === "1") {
    const expected = Netlify.env.get("VITAE_STATS_TOKEN") || "";
    const presented = request.headers.get("x-vitae-stats") || "";
    if (!expected || !timingSafeEqual(presented, expected)) return json(403, { error: "forbidden" });
    return serveStats();
  }

  const store = getStore(FILE_STORE);
  const wanted = url.searchParams.get("file") || "";
  let name = null;
  if (DMG_NAME.test(wanted) && (await store.getMetadata(wanted))) name = wanted;
  if (!name) name = await latestDmgName(store);
  if (!name) return json(404, { error: "no_release", detail: "No Vitae build is available right now." });

  if (request.method === "HEAD") {
    return new Response(null, { status: 200, headers: { "Content-Type": "application/x-apple-diskimage" } });
  }

  const ua = request.headers.get("user-agent") || "";
  if (ua && !BOT_UA.test(ua)) {
    // Bandwidth guard, same as the ModernTex trial door: a generous per-address cap.
    const ip = request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
    const day = new Date().toISOString().slice(0, 10);
    const rl = getStore("rate-limits");
    const rlKey = `rl:vitae:${day}:${createHash("sha256").update(ip).digest("hex").slice(0, 16)}`;
    const n = parseInt((await rl.get(rlKey)) || "0", 10) || 0;
    if (n >= DAILY_LIMIT) return json(429, { error: "rate_limited", detail: "Too many downloads from this address today." });
    await rl.set(rlKey, String(n + 1));

    const stats = getStore(STATS_STORE);
    await bump(stats, `downloads:${name}`);
    await bump(stats, `day:${day}`);
  }

  return streamBlob(store, name);
}
