/**
 * Netlify Function — the free Mac wallpaper pack (/photography/wallpapers/). Free, so there is no session, token or
 * license check. The JPEGs and zips live in the private `wallpaper-files` Blobs store (scripts/photo_wallpapers.py
 * renders and uploads them), not in site/, so the repo does not carry about 30 MB of full-size images.
 *
 *   GET|HEAD /photography/wallpapers/files/purplelink-<slug>-<6k|macbook>.jpg     -> one wallpaper
 *   GET|HEAD /photography/wallpapers/files/purplelink-wallpapers-<6k|macbook>.zip -> all five at one size
 *
 * netlify.toml rewrites /photography/wallpapers/files/* here (status 200, force; ?file=<name>). Only those two name
 * shapes are served; anything else is a 404, which also rules out path traversal (the name is matched against a
 * strict pattern before it is used as a store key). Responses stream from Blobs: the 6K zip is about 18 MB, past the
 * 6 MB buffered-response limit.
 *
 * Downloads are counted in the `wallpaper-stats` store as plain integers: downloads:<file> and day:<date>. That is
 * what the 30-day stop rule reads (under 50 downloads means no paid pack). Counts only: no IP address, no
 * User-Agent, nothing personal. Crawlers and HEAD requests are not counted, and a failure to count never blocks the
 * download. Counts are requests served, not confirmed completions.
 */
import { getStore } from "@netlify/blobs";

const FILE_STORE = "wallpaper-files";
const STATS_STORE = "wallpaper-stats";
const IMAGE_NAME = /^purplelink-[a-z0-9]+(-[a-z0-9]+){0,5}-(6k|macbook)\.jpg$/;
const ZIP_NAME = /^purplelink-wallpapers-(6k|macbook)\.zip$/;
const PREFIX = "/photography/wallpapers/files/";
const BOT_UA = /bot|crawl|spider|slurp|preview|facebookexternalhit|curl|wget|python-requests|httpclient|headless/i;

function notFound() {
  return new Response("Not found", {
    status: 404,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=60" },
  });
}

async function bump(stats, key) {
  const n = parseInt((await stats.get(key)) || "0", 10) || 0;
  await stats.set(key, String(n + 1));
}

async function countDownload(request, name) {
  try {
    const ua = request.headers.get("user-agent") || "";
    if (!ua || BOT_UA.test(ua)) return;
    const stats = getStore(STATS_STORE);
    await bump(stats, `downloads:${name}`);
    await bump(stats, `day:${new Date().toISOString().slice(0, 10)}`);
  } catch {
    // Counting is best effort.
  }
}

/** The file name the request is for, or null. Same two sources as batterymeter-download: ?file= or the path. */
function requestedName(url) {
  let name = url.searchParams.get("file");
  if (name === null) {
    let path;
    try {
      path = decodeURIComponent(url.pathname);
    } catch {
      return null;
    }
    if (!path.startsWith(PREFIX)) return null;
    name = path.slice(PREFIX.length);
  }
  if (IMAGE_NAME.test(name) || ZIP_NAME.test(name)) return name;
  return null;
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  const name = requestedName(new URL(request.url));
  if (!name) return notFound();

  let found;
  try {
    found = await getStore(FILE_STORE).getWithMetadata(name, { type: "stream" });
  } catch {
    return new Response("Temporarily unavailable", { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  if (!found) return notFound();

  const headers = {
    "Content-Type": name.endsWith(".zip") ? "application/zip" : "image/jpeg",
    "Cache-Control": "public, max-age=86400",
    "Content-Disposition": `attachment; filename="${name}"`,
    "X-Content-Type-Options": "nosniff",
  };
  const size = found.metadata && found.metadata.size;
  if (size) headers["Content-Length"] = String(size);

  if (request.method === "HEAD") return new Response(null, { status: 200, headers });
  await countDownload(request, name);
  return new Response(found.data, { status: 200, headers });
}
