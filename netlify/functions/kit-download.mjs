/**
 * Netlify Function — gated download for the /kits/ digital products.
 *
 *   GET /.netlify/functions/kit-download?session_id=cs_…            -> JSON list
 *   GET /.netlify/functions/kit-download?session_id=cs_…&file=key   -> the PDF
 *
 * The kit files (setup guide PDF + full source ZIP) are NOT part of the
 * published site. They live only in a private Netlify Blobs store, so the sole
 * way to get one is through a paid Stripe Checkout Session. We verify the
 * session exists on our account, is paid, and grants the requested file (via the
 * product key checkout.mjs wrote into session metadata). The session id is a
 * bearer token for the file the buyer paid for; we send no-store so shared
 * caches drop it.
 */
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
// Private Blobs store the owner uploads the deliverables into (see docs). The
// files are NOT in the (public) repo, so this store is the only place they exist.
const FILE_STORE = "kit-files";

// The deliverable files, and which product keys entitle a buyer to each. Every
// kit ships two files: the setup guide (PDF) and the full source code (ZIP).
const FILES = {
  "faceless-guide": {
    name: "faceless-content-pipeline-guide.pdf",
    label: "The Faceless Content Pipeline — setup guide (PDF)",
    type: "application/pdf",
    grants: new Set(["kit-faceless", "kit-bundle"]),
  },
  "faceless-source": {
    name: "faceless-content-pipeline-source.zip",
    label: "The Faceless Content Pipeline — full source code (ZIP)",
    type: "application/zip",
    grants: new Set(["kit-faceless", "kit-bundle"]),
  },
  "monetization-guide": {
    name: "monetization-stack-guide.pdf",
    label: "The Monetization Stack — setup guide (PDF)",
    type: "application/pdf",
    grants: new Set(["kit-monetization", "kit-bundle"]),
  },
  "monetization-source": {
    name: "monetization-stack-source.zip",
    label: "The Monetization Stack — full source code (ZIP)",
    type: "application/zip",
    grants: new Set(["kit-monetization", "kit-bundle"]),
  },
};

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
    resp = await fetch(`${STRIPE_API}/checkout/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
  } catch (err) {
    return { error: json(502, { error: "stripe_unreachable", detail: String(err) }) };
  }
  if (!resp.ok) return { error: json(403, { error: "session_not_found", detail: "That download link is not valid for this store." }) };
  const session = await resp.json();
  if (session.payment_status !== "paid") return { error: json(403, { error: "not_paid", detail: "This order has not been paid." }) };
  return { session };
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });

  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id") || "";
  const fileKey = url.searchParams.get("file") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }

  const { session, error } = await loadSession(sessionId);
  if (error) return error;
  const product = session.metadata?.product || "";

  // List mode: tell the success page which files this order can download.
  if (!fileKey) {
    const files = Object.entries(FILES)
      .filter(([, f]) => f.grants.has(product))
      .map(([key, f]) => ({ key, label: f.label,
        url: `/.netlify/functions/kit-download?session_id=${encodeURIComponent(sessionId)}&file=${key}` }));
    if (!files.length) return json(404, { error: "unknown_product", detail: "We could not match this order to a kit. Contact ben@purplelink.llc." });
    return json(200, { product, files });
  }

  // File mode: stream the entitled file (PDF guide or source ZIP).
  const entry = FILES[fileKey];
  if (!entry) return json(404, { error: "unknown_file" });
  if (!entry.grants.has(product)) return json(403, { error: "not_entitled", detail: "This order does not include that file." });

  let bytes;
  try {
    const blob = await getStore(FILE_STORE).get(entry.name, { type: "arrayBuffer" });
    if (!blob) throw new Error(`missing blob ${entry.name}`);
    bytes = new Uint8Array(blob);
  } catch (err) {
    return json(500, { error: "file_unavailable", detail: "The file is temporarily unavailable. Contact ben@purplelink.llc." });
  }

  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": entry.type,
      "Content-Disposition": `attachment; filename="${entry.name}"`,
      "Content-Length": String(bytes.length),
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
