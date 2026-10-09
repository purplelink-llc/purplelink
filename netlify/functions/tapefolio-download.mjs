/**
 * Netlify Function — Tapefolio delivery. One private Blobs store, three doors: public download, purchase, update channel.
 *
 * There is ONE app. It runs free for 7 days and a license key (TFL1-…, see netlify/lib/tapefolio-license.mjs) keeps
 * it unlocked, the way ModernTex does. So the download is public and the same file serves trial users, buyers and
 * Sparkle.
 *
 *   Public download (the trial; no session):
 *     GET /.netlify/functions/tapefolio-download?download=1   -> newest Tapefolio-x.y.z.dmg   (?trial=1 is the same, kept for old links)
 *
 *   Purchase (browser, after Stripe Checkout):
 *     GET /.netlify/functions/tapefolio-download?session_id=cs_…            -> JSON {license, files:[…]}
 *     GET /.netlify/functions/tapefolio-download?session_id=cs_…&file=<dmg> -> the DMG
 *     `license` is the buyer's key, derived from their address, so it matches the receipt email.
 *
 *   Updates (Sparkle inside the app, never a browser):
 *     GET /.netlify/functions/tapefolio-download?feed=1                       -> appcast.xml
 *     GET /.netlify/functions/tapefolio-download?update=<dmg>                 -> the DMG
 *     GET /.netlify/functions/tapefolio-download?stats=1                      -> download counts (JSON)
 *     All three require the header  X-Tapefolio-Channel: <TAPEFOLIO_UPDATE_TOKEN>, which the app is built with
 *     and sends on every Sparkle request. It keeps the update channel off the open web; it is not a license check.
 *
 * The DMGs and appcast are NOT part of the published site. They live only in the private `tapefolio-files` Blobs
 * store (the release script in the Tapefolio repo uploads them; see docs/products/tapefolio.md). Responses stream
 * straight from Blobs, which keeps a large disk image clear of the 6 MB buffered-response limit. Each served `update=<dmg>` also
 * increments a plain counter in the `tapefolio-stats` store — requests, not confirmed completions.
 */
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { issueTapefolioLicense } from "../lib/tapefolio-license.mjs";

const STRIPE_API = "https://api.stripe.com/v1";
const FILE_STORE = "tapefolio-files";
const STATS_STORE = "tapefolio-stats";
const PRODUCT_KEY = "tapefolio";
const SUITE_KEY = "app-suite";
const DMG_NAME = /^Tapefolio-\d+\.\d+\.\d+\.dmg$/;
const TRIAL_DAILY_LIMIT = 20;

/** Durable per-file download count, in the same Blobs-as-counter style already used
 *  for the trial rate limit below — a plain string integer, read-increment-write. */
async function incrementDownloadCount(fileName) {
  const stats = getStore(STATS_STORE);
  const key = `downloads:${fileName}`;
  const n = parseInt((await stats.get(key)) || "0", 10) || 0;
  await stats.set(key, String(n + 1));
}

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

async function loadSession(sessionId) {
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return { error: json(500, { error: "misconfigured", detail: "STRIPE_SECRET_KEY not set." }) };
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
  } catch (err) {
    return { error: json(502, { error: "stripe_unreachable", detail: String(err) }) };
  }
  if (!resp.ok) return { error: json(403, { error: "session_not_found", detail: "That download link is not valid for this store." }) };
  const session = await resp.json();
  if (session.payment_status !== "paid") return { error: json(403, { error: "not_paid", detail: "This order has not been paid." }) };
  // The Mac Suite bundle includes this app, so its session unlocks the same download.
  const bought = session.metadata?.product || "";
  if (bought !== PRODUCT_KEY && bought !== SUITE_KEY) {
    return { error: json(403, { error: "not_entitled", detail: "This order is for a different product." }) };
  }
  return { session };
}

/** The newest DMG in the store, by semantic version in the filename. */
async function latestDmgName(store, pattern = DMG_NAME) {
  const { blobs } = await store.list();
  const names = blobs.map((b) => b.key).filter((k) => pattern.test(k));
  names.sort((a, b) => {
    const va = a.match(/\d+/g).map(Number), vb = b.match(/\d+/g).map(Number);
    for (let i = 0; i < 3; i++) if (va[i] !== vb[i]) return vb[i] - va[i];
    return 0;
  });
  return names[0] || null;
}

async function streamBlob(store, key, type, disposition) {
  let stream, meta;
  try {
    const r = await store.getWithMetadata(key, { type: "stream" });
    if (!r) return json(404, { error: "file_unavailable", detail: "That file is not available. Contact ben@purplelink.llc." });
    stream = r.data; meta = r.metadata || {};
  } catch (err) {
    return json(500, { error: "file_unavailable", detail: "The file is temporarily unavailable. Contact ben@purplelink.llc." });
  }
  const headers = {
    "Content-Type": type,
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  if (disposition) headers["Content-Disposition"] = disposition;
  if (meta.size) headers["Content-Length"] = String(meta.size);
  return new Response(stream, { status: 200, headers });
}

/**
 * The appcast, with every enclosure URL rewritten to the canonical update door.
 *
 * Sparkle's `generate_appcast --download-url-prefix` resolves each filename as a
 * relative URL against the prefix, so a prefix carrying a query string
 * (`…/tapefolio-download?update=`) collapses to `…/functions/Tapefolio-1.0.0.dmg`,
 * which 404s and breaks in-app updates. publish-release.sh now post-processes its own
 * output, but the feed is rewritten here too so a stale or hand-uploaded appcast
 * in the store can never ship a dead download link to installed copies.
 * The EdDSA signature covers the DMG, not the URL, so rewriting is safe.
 */
async function serveFeed(store) {
  let xml;
  try {
    xml = await store.get("appcast.xml", { type: "text" });
  } catch (err) {
    xml = null;
  }
  if (!xml) return json(404, { error: "file_unavailable", detail: "No update feed is staged." });
  const fixed = xml.replace(
    /url="[^"]*\/(Tapefolio-\d+\.\d+\.\d+\.dmg)"/g,
    (_m, name) => `url="https://purplelink.llc/.netlify/functions/tapefolio-download?update=${name}"`,
  );
  return new Response(fixed, {
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
  const store = getStore(FILE_STORE);

  // --- Public download (the 7-day trial) --------------------------------------------
  // No session, no token: anyone may take the app. The only thing worth guarding
  // is bandwidth, so one address gets a generous daily cap rather than none.
  if (url.searchParams.get("download") === "1" || url.searchParams.get("trial") === "1") {
    const ip = request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
    const day = new Date().toISOString().slice(0, 10);
    const rl = getStore("rate-limits");
    const key = `rl:trial:${day}:${createHash("sha256").update(ip).digest("hex").slice(0, 16)}`;
    const n = parseInt((await rl.get(key)) || "0", 10) || 0;
    if (n >= TRIAL_DAILY_LIMIT) return json(429, { error: "rate_limited", detail: "Too many downloads from this address today." });
    await rl.set(key, String(n + 1));
    const name = await latestDmgName(store);
    if (!name) return json(404, { error: "no_release", detail: "No download is available right now." });
    return streamBlob(store, name, "application/x-apple-diskimage", `attachment; filename="${name}"`);
  }

  // --- Update channel (Sparkle) -------------------------------------------------
  const wantsFeed = url.searchParams.get("feed") === "1";
  const updateFile = url.searchParams.get("update") || "";
  const wantsStats = url.searchParams.get("stats") === "1";
  if (wantsFeed || updateFile || wantsStats) {
    const expected = Netlify.env.get("TAPEFOLIO_UPDATE_TOKEN") || "";
    const presented = request.headers.get("x-tapefolio-channel") || "";
    if (!expected || !timingSafeEqual(presented, expected)) {
      return json(403, { error: "forbidden", detail: "Updates are delivered inside Tapefolio." });
    }
    if (wantsFeed) return serveFeed(store);
    if (wantsStats) {
      // Same shared secret as the update channel gates this too — it's read-only
      // and non-sensitive (just counts), but there's no reason to expose it wider
      // than the channel that already requires the token, e.g. to curl -H.
      const stats = getStore(STATS_STORE);
      const { blobs } = await stats.list({ prefix: "downloads:" });
      const counts = {};
      for (const b of blobs) counts[b.key.slice("downloads:".length)] = parseInt((await stats.get(b.key)) || "0", 10) || 0;
      return json(200, { downloads: counts });
    }
    if (!DMG_NAME.test(updateFile)) return json(400, { error: "bad_file" });
    // Counted as a download the moment we decide to serve it — matching the trial
    // counter above, this does not confirm the client received every byte, only
    // that Sparkle asked for this exact file and was handed it.
    await incrementDownloadCount(updateFile);
    return streamBlob(store, updateFile, "application/x-apple-diskimage", `attachment; filename="${updateFile}"`);
  }

  // --- Purchase door (Stripe Checkout session as bearer token) --------------------
  const sessionId = url.searchParams.get("session_id") || "";
  const fileKey = url.searchParams.get("file") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }
  const { error, session } = await loadSession(sessionId);
  if (error) return error;

  const latest = await latestDmgName(store);
  if (!latest) return json(500, { error: "file_unavailable", detail: "No release is staged. Contact ben@purplelink.llc." });

  if (!fileKey) {
    const version = latest.match(/\d+\.\d+\.\d+/)[0];
    return json(200, {
      product: PRODUCT_KEY,
      // The same key the receipt email carries; it comes from the buyer's address, so it never changes.
      license: issueTapefolioLicense(session.customer_details?.email || session.customer_email),
      files: [{
        key: latest,
        label: `Tapefolio ${version} for macOS (disk image)`,
        url: `/.netlify/functions/tapefolio-download?session_id=${encodeURIComponent(sessionId)}&file=${encodeURIComponent(latest)}`,
      }],
    });
  }
  // A buyer may fetch any released version, not only the newest — an older Mac may need it.
  if (!DMG_NAME.test(fileKey)) return json(404, { error: "unknown_file" });
  return streamBlob(store, fileKey, "application/x-apple-diskimage", `attachment; filename="${fileKey}"`);
}
