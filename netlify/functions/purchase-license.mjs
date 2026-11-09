/**
 * Netlify Function: the license keys a paid purchase is entitled to, for the success pages.
 *
 *   GET /.netlify/functions/purchase-license?session_id=cs_...
 *     -> 200 { keys: [{ product, label, key }] }
 *
 * The Stripe Checkout session id is the bearer token, exactly as for the download pages. Keys are derived
 * from the session id (see netlify/lib/license.mjs and licenseKeysForSession), so this returns the same keys
 * the purchase email carried; nothing is stored. Only paid sessions for a product that has a key are answered.
 * A custom bundle also returns `parts`, the part slugs it contains, so its success page can hide the rest. A missing signing secret yields an empty list, never an error page, so a download page still works.
 */
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { licenseKeysForSession } from "./stripe-webhook.mjs";
import { addonPartsOf, entitledParts, isBundleProduct } from "../lib/bundles.mjs";
import { SESSION_EXPAND, withAddons } from "../lib/addons.mjs";
import { revocationFor, REVOKED_DETAIL } from "../lib/refunds.mjs";
import { stripeFetchAny } from "../lib/stripe-account.mjs";

const STRIPE_API = "https://api.stripe.com/v1";
const KEYED_PRODUCTS = new Set(["moderntex", "moderntex-seats", "outbound-veil", "legroom", "keyfeel", "tapefolio", "lenscrib", "nee", "lenses", "panely", "summonly", "app-suite", "bundle-2", "bundle-3"]);
const DAILY_LIMIT = 120;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" },
  });
}

export default async function handler(request) {
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }

  const ip = request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const limits = getStore("rate-limits");
  const rlKey = `rl:license:${day}:${createHash("sha256").update(ip).digest("hex").slice(0, 16)}`;
  const used = parseInt((await limits.get(rlKey)) || "0", 10) || 0;
  if (used >= DAILY_LIMIT) return json(429, { error: "rate_limited", detail: "Too many requests from this address today." });
  await limits.set(rlKey, String(used + 1));

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return json(500, { error: "misconfigured" });
  let resp;
  try {
    resp = await stripeFetchAny(`${STRIPE_API}/checkout/sessions/${sessionId}?${SESSION_EXPAND}`, { headers: { Authorization: `Bearer ${secretKey}` } });
  } catch {
    return json(502, { error: "stripe_unreachable" });
  }
  if (!resp.ok) return json(403, { error: "session_not_found", detail: "That link is not valid for this store." });
  // A second app added at checkout is derived from the paid line items; see netlify/lib/addons.mjs.
  const session = withAddons(await resp.json());
  if (session.payment_status !== "paid") return json(403, { error: "not_paid", detail: "This order has not been paid." });
  // Keys verify offline and cannot be revoked, but a fully refunded or disputed order is not handed them again.
  if (await revocationFor(session)) return json(403, { error: "refunded", detail: REVOKED_DETAIL });
  const product = session.metadata?.product || "";
  const addons = session.metadata?.addons || "";
  const addonParts = addonPartsOf(product, { addons });
  // Lenses has no key of its own, but an order that added a keyed app is owed that app's key.
  if (!KEYED_PRODUCTS.has(product) && !addonParts.length) return json(403, { error: "not_entitled", detail: "This order has no license key." });

  const seats = parseInt(session.metadata?.seats || "0", 10) || 0;
  const apps = session.metadata?.apps || "";
  const keys = licenseKeysForSession(product, sessionId, { seats, apps, addons }).map((k) => ({ product: k.slug, label: k.label, key: k.key }));
  // The success page of a custom bundle shows only the parts that were chosen; it reads them here, from Stripe's
  // own record, rather than trusting anything in the URL. Other products answer without `parts`.
  if (isBundleProduct(product)) {
    const parts = [...entitledParts(product, { apps })];
    if (!parts.length) return json(403, { error: "not_entitled", detail: "This order has no license key." });
    return json(200, { keys, parts });
  }
  // A single app with a second one added at checkout: the success pages send it to the page that shows both, which
  // reads the two parts from here.
  if (addonParts.length) return json(200, { keys, parts: [...entitledParts(product, { addons })] });
  return json(200, { keys });
}
