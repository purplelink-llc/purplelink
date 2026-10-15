/**
 * Netlify Function — BatteryMeter delivery. BatteryMeter is free, so there is no session, token or license check.
 * The Sparkle appcast and every release zip live in the private `batterymeter-files` Blobs store, not in site/,
 * so a BatteryMeter release (scripts/publish-release.sh in the BatteryMeter repo) needs no site build.
 *
 *   GET|HEAD /batterymeter/appcast.xml                -> the appcast (application/xml, 5-minute cache)
 *   GET|HEAD /batterymeter/BatteryMeter-<version>.zip -> that release zip (versioned name, long cache)
 *
 * netlify.toml rewrites both URL shapes here (status 200, force; ?file=<name>), so the URLs installed copies and the product
 * page already use do not change. Only those two shapes are served; anything else is a 404, which also rules
 * out path traversal (the name is matched against a strict pattern before it is used as a store key).
 *
 * Zip downloads are counted in the `batterymeter-stats` store as plain integers (downloads:<file>, day:<date>).
 * Counts only: no IP address, no User-Agent, nothing personal. Crawlers and HEAD requests are not counted, and
 * a failure to count never blocks the download. Counts are requests served, not confirmed completions.
 */
import { getStore } from "@netlify/blobs";

const FILE_STORE = "batterymeter-files";
const STATS_STORE = "batterymeter-stats";
const ZIP_NAME = /^BatteryMeter-[0-9]+(\.[0-9]+){1,3}\.zip$/;
const APPCAST = "appcast.xml";
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

/**
 * The file name the request is for, or null. The rewrite rules pass it as ?file=, and the function also
 * understands the original /batterymeter/<name> path, so it works whichever URL the runtime reports.
 * Whatever the source, the name must match a strict pattern before it is used as a store key.
 */
function requestedName(url) {
  let name = url.searchParams.get("file");
  if (name === null) {
    const prefix = "/batterymeter/";
    let path;
    try {
      path = decodeURIComponent(url.pathname);
    } catch {
      return null;
    }
    if (!path.startsWith(prefix)) return null;
    name = path.slice(prefix.length);
  }
  if (name === APPCAST || ZIP_NAME.test(name)) return name;
  return null;
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  const url = new URL(request.url);
  const name = requestedName(url);
  if (!name) return notFound();

  const store = getStore(FILE_STORE);
  const isFeed = name === APPCAST;
  let body;
  try {
    // Buffered, not streamed: the files are about a megabyte and an exact Content-Length matters to Sparkle.
    body = await store.get(name, { type: "arrayBuffer" });
  } catch {
    return new Response("Temporarily unavailable", { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  if (!body) return notFound();

  const headers = isFeed
    ? { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=300, must-revalidate" }
    : {
        "Content-Type": "application/zip",
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": `attachment; filename="${name}"`,
      };
  headers["Content-Length"] = String(body.byteLength);
  headers["X-Content-Type-Options"] = "nosniff";

  if (request.method === "HEAD") return new Response(null, { status: 200, headers });
  if (!isFeed) await countDownload(request, name);
  return new Response(body, { status: 200, headers });
}
