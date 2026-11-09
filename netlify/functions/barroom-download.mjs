/**
 * Netlify Function — Barroom update channel (Sparkle inside the app, never a browser).
 *
 *   GET /.netlify/functions/barroom-download?feed=1             -> appcast.xml
 *   GET /.netlify/functions/barroom-download?update=<dmg>       -> the DMG
 *   GET /.netlify/functions/barroom-download?stats=1            -> download counts (JSON)
 *
 * All three need the header  X-Barroom-Channel: <BARROOM_UPDATE_TOKEN>,  which the Barroom build compiles into the
 * app and sends on every Sparkle request (same scheme as lenses-download.mjs). The token keeps the channel off the
 * open web; it is not a paywall.
 *
 * Barroom is not on sale yet: there is no purchase door and no public trial door. Those come with the product page,
 * Stripe key and price, which are Ben's call. The DMGs and appcast live only in the private `barroom-files` Blobs
 * store; scripts/publish-release.sh in the Barroom repo uploads them.
 */
import { getStore } from "@netlify/blobs";

const FILE_STORE = "barroom-files";
const STATS_STORE = "barroom-stats";
const DMG_NAME = /^Barroom-\d+\.\d+\.\d+\.dmg$/;
const UPDATE_DOOR = "https://purplelink.llc/.netlify/functions/barroom-download?update=";

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

async function incrementDownloadCount(fileName) {
  const stats = getStore(STATS_STORE);
  const key = `downloads:${fileName}`;
  const n = parseInt((await stats.get(key)) || "0", 10) || 0;
  await stats.set(key, String(n + 1));
}

async function streamBlob(store, key) {
  let r;
  try {
    r = await store.getWithMetadata(key, { type: "stream" });
  } catch {
    return json(500, { error: "file_unavailable", detail: "The file is temporarily unavailable." });
  }
  if (!r) return json(404, { error: "file_unavailable", detail: "That file is not available." });
  const headers = {
    "Content-Type": "application/x-apple-diskimage",
    "Content-Disposition": `attachment; filename="${key}"`,
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (r.metadata?.size) headers["Content-Length"] = String(r.metadata.size);
  return new Response(r.data, { status: 200, headers });
}

/** The appcast. An unsigned feed has its enclosures pointed at the update door (the EdDSA signature covers the DMG,
 *  not the URL); a signed feed is served byte for byte. */
async function serveFeed(store) {
  let xml = null;
  try { xml = await store.get("appcast.xml", { type: "text" }); } catch { xml = null; }
  if (!xml) return json(404, { error: "file_unavailable", detail: "No update feed is staged." });
  const body = xml.includes("<!-- sparkle-signatures:")
    ? xml
    : xml.replace(/url="[^"]*\/(Barroom-\d+\.\d+\.\d+\.dmg)"/g, (_m, name) => `url="${UPDATE_DOOR}${name}"`);
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });
  const url = new URL(request.url);
  const wantsFeed = url.searchParams.get("feed") === "1";
  const updateFile = url.searchParams.get("update") || "";
  const wantsStats = url.searchParams.get("stats") === "1";
  if (!wantsFeed && !updateFile && !wantsStats) return json(404, { error: "not_found" });

  const expected = Netlify.env.get("BARROOM_UPDATE_TOKEN") || "";
  const presented = request.headers.get("x-barroom-channel") || "";
  if (!expected || !timingSafeEqual(presented, expected)) {
    return json(403, { error: "forbidden", detail: "Updates are delivered inside Barroom." });
  }
  const store = getStore(FILE_STORE);
  if (wantsFeed) return serveFeed(store);
  if (wantsStats) {
    const stats = getStore(STATS_STORE);
    const { blobs } = await stats.list({ prefix: "downloads:" });
    const counts = {};
    for (const b of blobs) counts[b.key.slice("downloads:".length)] = parseInt((await stats.get(b.key)) || "0", 10) || 0;
    return json(200, { downloads: counts });
  }
  if (!DMG_NAME.test(updateFile)) return json(400, { error: "bad_file" });
  await incrementDownloadCount(updateFile);
  return streamBlob(store, updateFile);
}
