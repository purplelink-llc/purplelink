/**
 * Netlify Function: Lenses delivery. One private Blobs store, one door: the purchase.
 *
 * Lenses is a paid download only. No license key, no trial, no public download, no update channel.
 *
 *   GET /.netlify/functions/lenses-download?session_id=cs_...            -> JSON {product, files:[{key,label,url}]}
 *   GET /.netlify/functions/lenses-download?session_id=cs_...&file=<dmg> -> the DMG
 *
 * The Stripe Checkout session id is the bearer token, as for the other apps. The session must be paid, not
 * refunded or disputed (netlify/lib/refunds.mjs), and must be a Lenses order, a Mac Suite order, or a custom bundle whose
 * chosen parts include Lenses (since 2026-11-06).
 *
 * The DMGs are NOT part of the published site. They live only in the private `lenses-files` Blobs store (see
 * docs/products/lenses.md). Responses stream straight from Blobs, which keeps a large disk image clear of the
 * 6 MB buffered-response limit.
 */
import { getStore } from "@netlify/blobs";
import { revocationFor, REVOKED_DETAIL } from "../lib/refunds.mjs";
import { bundleHasPart } from "../lib/bundles.mjs";
import { SESSION_EXPAND, withAddons } from "../lib/addons.mjs";

const STRIPE_API = "https://api.stripe.com/v1";
const FILE_STORE = "lenses-files";
const PRODUCT_KEY = "lenses";
const SUITE_KEY = "app-suite";
const DMG_NAME = /^Lenses-\d+\.\d+\.\d+\.dmg$/;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" },
  });
}

async function loadSession(sessionId) {
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return { error: json(500, { error: "misconfigured", detail: "STRIPE_SECRET_KEY not set." }) };
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions/${sessionId}?${SESSION_EXPAND}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
  } catch (err) {
    console.error("lenses-download: stripe request failed:", err?.name, err?.message);
    return { error: json(502, { error: "stripe_unreachable", detail: "Could not reach the payment processor. Try again in a minute." }) };
  }
  if (!resp.ok) return { error: json(403, { error: "session_not_found", detail: "That download link is not valid for this store." }) };
  // A second app added at checkout is read from the paid line items (netlify/lib/addons.mjs), so its download unlocks too.
  const session = withAddons(await resp.json());
  if (session.payment_status !== "paid") return { error: json(403, { error: "not_paid", detail: "This order has not been paid." }) };
  // A fully refunded or disputed order no longer gets the file (netlify/lib/refunds.mjs).
  if (await revocationFor(session)) return { error: json(403, { error: "refunded", detail: REVOKED_DETAIL }) };
  // Lenses itself, the whole Mac Suite, or a custom bundle that names Lenses.
  const bought = session.metadata?.product || "";
  if (bought !== PRODUCT_KEY && bought !== SUITE_KEY && !bundleHasPart(bought, session.metadata, "lenses")) {
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
  const sessionId = url.searchParams.get("session_id") || "";
  const fileKey = url.searchParams.get("file") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }
  const { error } = await loadSession(sessionId);
  if (error) return error;

  const store = getStore(FILE_STORE);
  const latest = await latestDmgName(store);
  if (!latest) return json(500, { error: "file_unavailable", detail: "No release is staged. Contact ben@purplelink.llc." });

  if (!fileKey) {
    const version = latest.match(/\d+\.\d+\.\d+/)[0];
    return json(200, {
      product: PRODUCT_KEY,
      files: [{
        key: latest,
        label: `Lenses ${version} for macOS (disk image)`,
        url: `/.netlify/functions/lenses-download?session_id=${encodeURIComponent(sessionId)}&file=${encodeURIComponent(latest)}`,
      }],
    });
  }
  // A buyer may fetch any released version, not only the newest: an older Mac may need it.
  if (!DMG_NAME.test(fileKey)) return json(404, { error: "unknown_file" });
  return streamBlob(store, fileKey, "application/x-apple-diskimage", `attachment; filename="${fileKey}"`);
}
