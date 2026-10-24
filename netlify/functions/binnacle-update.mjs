/**
 * Netlify Function — Binnacle's in-app update channel (Sparkle). Binnacle is Ben's private bookkeeping app: there is no
 * public download, no page and no purchase door, only the two requests Sparkle makes from inside an installed copy.
 *
 *   GET /.netlify/functions/binnacle-update?feed=1                      -> appcast.xml
 *   GET /.netlify/functions/binnacle-update?update=Binnacle-0.2.42.dmg  -> that DMG
 *
 * Both require the header  X-Binnacle-Channel: <BINNACLE_UPDATE_TOKEN>; anything else gets 403. The token is a shared
 * secret built into the app, so it keeps the channel off the open web rather than standing in for authentication; what
 * protects an install is Sparkle's EdDSA signature on every update and the app's Developer ID signature.
 *
 * The files live only in the private Blobs store "binnacle-files", uploaded by scripts/publish-update.sh in the Binnacle
 * (helm) repo. Responses stream from Blobs, which keeps a disk image clear of the buffered-response size limit.
 */
import { getStore } from "@netlify/blobs";

const FILE_STORE = "binnacle-files";
const DMG_NAME = /^Binnacle-\d+\.\d+\.\d+\.dmg$/;
const DOOR = "https://purplelink.llc/.netlify/functions/binnacle-update";

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

/** The appcast, with every enclosure pointed at this door (generate_appcast can collapse a query-string prefix). */
async function serveFeed(store) {
  let xml = null;
  try {
    xml = await store.get("appcast.xml", { type: "text" });
  } catch (err) {
    xml = null;
  }
  if (!xml) return json(404, { error: "file_unavailable", detail: "No update feed is staged." });
  const fixed = xml.replace(/url="[^"]*\/(Binnacle-\d+\.\d+\.\d+\.dmg)"/g, (_m, name) => `url="${DOOR}?update=${name}"`);
  return new Response(fixed, {
    status: 200,
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function serveDmg(store, key, method) {
  let r;
  try {
    r = await store.getWithMetadata(key, { type: "stream" });
  } catch (err) {
    return json(500, { error: "file_unavailable" });
  }
  if (!r) return json(404, { error: "file_unavailable" });
  const headers = {
    "Content-Type": "application/x-apple-diskimage",
    "Content-Disposition": `attachment; filename="${key}"`,
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (r.metadata?.size) headers["Content-Length"] = String(r.metadata.size);
  return new Response(method === "HEAD" ? null : r.data, { status: 200, headers });
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });
  const expected = Netlify.env.get("BINNACLE_UPDATE_TOKEN") || "";
  const presented = request.headers.get("x-binnacle-channel") || "";
  if (!expected || !timingSafeEqual(presented, expected)) return json(403, { error: "forbidden" });

  const url = new URL(request.url);
  const store = getStore(FILE_STORE);
  if (url.searchParams.get("feed") === "1") return serveFeed(store);
  const file = url.searchParams.get("update");
  if (file !== null) {
    if (!DMG_NAME.test(file)) return json(400, { error: "bad_file" });
    return serveDmg(store, file, request.method);
  }
  return json(404, { error: "not_found" });
}
