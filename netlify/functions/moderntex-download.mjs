/**
 * Netlify Function — ModernTex delivery. Two doors, one private Blobs store.
 *
 *   Purchase (browser, after Stripe Checkout):
 *     GET /.netlify/functions/moderntex-download?session_id=cs_…            -> JSON {files:[…]}
 *     GET /.netlify/functions/moderntex-download?session_id=cs_…&file=<dmg> -> the DMG
 *
 *   Updates (Sparkle inside the app, never a browser):
 *     GET /.netlify/functions/moderntex-download?feed=1                       -> appcast.xml
 *     GET /.netlify/functions/moderntex-download?update=<dmg>                 -> the DMG
 *     Both require the header  X-ModernTex-Channel: <MODERNTEX_UPDATE_TOKEN>,
 *     which build.sh compiles into the app and UpdaterService sends on every
 *     Sparkle request. The token is a shared secret in a shipped binary, so it
 *     keeps the update channel off the open web rather than defeating a
 *     determined reverse-engineer; the purchase door is what the paywall rests on.
 *
 * The DMGs and appcast are NOT part of the published site. They live only in the
 * private `moderntex-files` Blobs store (scripts/release.sh in the ModernTex repo
 * uploads them). Responses stream straight from Blobs, which keeps a 13 MB disk
 * image clear of the 6 MB buffered-response limit.
 */
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
const FILE_STORE = "moderntex-files";
const PRODUCT_KEY = "moderntex";
const DMG_NAME = /^ModernTex-\d+\.\d+\.\d+\.dmg$/;

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
  if ((session.metadata?.product || "") !== PRODUCT_KEY) {
    return { error: json(403, { error: "not_entitled", detail: "This order is for a different product." }) };
  }
  return { session };
}

/** The newest DMG in the store, by semantic version in the filename. */
async function latestDmgName(store) {
  const { blobs } = await store.list();
  const names = blobs.map((b) => b.key).filter((k) => DMG_NAME.test(k));
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

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });
  const url = new URL(request.url);
  const store = getStore(FILE_STORE);

  // --- Update channel (Sparkle) -------------------------------------------------
  const wantsFeed = url.searchParams.get("feed") === "1";
  const updateFile = url.searchParams.get("update") || "";
  if (wantsFeed || updateFile) {
    const expected = Netlify.env.get("MODERNTEX_UPDATE_TOKEN") || "";
    const presented = request.headers.get("x-moderntex-channel") || "";
    if (!expected || !timingSafeEqual(presented, expected)) {
      return json(403, { error: "forbidden", detail: "Updates are delivered inside ModernTex." });
    }
    if (wantsFeed) return streamBlob(store, "appcast.xml", "application/rss+xml; charset=utf-8", null);
    if (!DMG_NAME.test(updateFile)) return json(400, { error: "bad_file" });
    return streamBlob(store, updateFile, "application/x-apple-diskimage", `attachment; filename="${updateFile}"`);
  }

  // --- Purchase door (Stripe Checkout session as bearer token) --------------------
  const sessionId = url.searchParams.get("session_id") || "";
  const fileKey = url.searchParams.get("file") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }
  const { error } = await loadSession(sessionId);
  if (error) return error;

  const latest = await latestDmgName(store);
  if (!latest) return json(500, { error: "file_unavailable", detail: "No release is staged. Contact ben@purplelink.llc." });

  if (!fileKey) {
    const version = latest.match(/\d+\.\d+\.\d+/)[0];
    return json(200, {
      product: PRODUCT_KEY,
      files: [{
        key: latest,
        label: `ModernTex ${version} for macOS (disk image)`,
        url: `/.netlify/functions/moderntex-download?session_id=${encodeURIComponent(sessionId)}&file=${encodeURIComponent(latest)}`,
      }],
    });
  }
  // A buyer may fetch any released version, not only the newest — an older Mac may need it.
  if (!DMG_NAME.test(fileKey)) return json(404, { error: "unknown_file" });
  return streamBlob(store, fileKey, "application/x-apple-diskimage", `attachment; filename="${fileKey}"`);
}
