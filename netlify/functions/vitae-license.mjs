/**
 * Netlify Function — Vitae Plus subscription license keys.
 *
 * Vitae Plus is a subscription (vitae-plus-monthly, vitae-plus-annual in
 * checkout.mjs). The app holds a short-lived signed key, verifies it offline
 * against the matching Ed25519 public key, and refreshes it about once a month.
 * Four modes: issue and refresh are GET, recover and manage are POST:
 *
 *   ?session_id=cs_…   Issue. Called by /vitae/plus/success/ after Checkout.
 *     -> 200 { key: "VP2-…", email: "<Stripe receipt address>" | null }
 *     -> 400 bad_session_id · 402 not_paid · 404 not_found · 410 { status } · 429 · 500/502
 *     Retrieves the session with the subscription expanded, requires
 *     metadata.product to start with "vitae-plus-", and stores
 *     { subscription, plan } in the "vitae-plus" Blobs store under the key's id
 *     so a later refresh can find the subscription. The email is only shown on
 *     the page and is never logged or stored.
 *
 *   ?refresh=<id>       Refresh. Called by the app; <id> is the 16-hex id from
 *     the key it already holds, and nothing else is sent.
 *     -> 200 { key: "VP2-…", status } · 400 bad_id · 404 not_found · 410 { status } · 429 · 500/502
 *     active / trialing -> exp = current period end + 7 days
 *     past_due          -> exp = now + 7 days (grace while the card is retried)
 *     anything else     -> 410 { status }
 *
 *   POST { "recover": "<email>" }   Recover. From /vitae/plus/recover/. Finds the Stripe
 *     customers with that email and their live Vitae Plus subscriptions, and emails a
 *     current key for each to that address (never to anyone else). The answer is the
 *     same whether or not anything matched, so it cannot be used to learn who subscribes.
 *     -> 200 { status: "sent_if_found" } · 400 bad_email · 429 · 500/502
 *     At most 3 requests per address per day, on top of the per-IP limit.
 *
 *   POST { "manage": "<id>" }   Manage. Sent by the app's "Manage Subscription"
 *     button (a POST, so the id never lands in a browser URL, history or logs).
 *     Creates a Stripe billing portal session for the subscription's customer, using a
 *     portal configuration limited to invoices, the card, and cancelling at the end of
 *     the paid period (no email, address or plan changes). The configuration is created
 *     once and its id kept in Blobs, or set with STRIPE_PORTAL_CONFIG_VITAE_PLUS.
 *     -> 200 { url: "<portal url>" } · 400 bad_id · 404 not_found · 429 · 500/502
 *     On any failure the app opens /vitae/plus/manage/, which explains how to
 *     cancel by email instead.
 *
 * Key format v2 (must match the app's verifier byte for byte):
 *   payload = UTF-8 JSON.stringify({ exp, iat, id, p: "vitae-plus", plan, v: 2 })
 *             key order exactly: exp, iat, id, p, plan, v
 *     exp  = unix seconds (see above)
 *     iat  = now, unix seconds
 *     id   = first 16 hex chars of sha256(subscription.id)
 *     plan = "monthly" | "annual"
 *   sig     = Ed25519 signature over payload
 *   key     = "VP2-" + base64url(payload) + "." + base64url(sig)   (no padding)
 *
 * No name or email goes into the key or the Blobs mapping.
 *
 * Env vars:
 *   STRIPE_SECRET_KEY          shared with checkout.mjs
 *   VITAE_LICENSE_PRIVATE_KEY  Ed25519 PKCS#8 PEM; literal "\n" sequences are accepted
 *   RESEND_API_KEY             shared with stripe-webhook.mjs; sends recovery emails
 *   STRIPE_PORTAL_CONFIG_VITAE_PLUS  optional: an existing bpc_… portal configuration id
 */
import { createHash, createPrivateKey, sign } from "node:crypto";
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
const PAYLOAD_PRODUCT = "vitae-plus";
const PRODUCT_PREFIX = "vitae-plus-";
const MAPPING_STORE = "vitae-plus";
const GRACE_SECONDS = 7 * 24 * 60 * 60;
const LICENSE_DAILY_LIMIT = 60;
const SESSION_ID = /^cs_[A-Za-z0-9_]{10,200}$/;
const LICENSE_ID = /^[0-9a-f]{16}$/;
const SITE_ORIGIN = "https://purplelink.llc";
const MANAGE_FALLBACK = `${SITE_ORIGIN}/vitae/plus/manage/`;
const RESEND_API_URL = "https://api.resend.com/emails";
const ORDER_FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const ORDER_REPLY_TO = "ben@purplelink.llc";
const RECOVER_PER_EMAIL_DAILY = 3;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const PORTAL_CONFIG_BLOB = "_portal_config";

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function redirect(location) {
  return new Response(null, {
    status: 302,
    headers: { Location: location, "Cache-Control": "no-store" },
  });
}

/** Per-IP, per-UTC-day counter in the shared rate-limits store (same pattern as checkout.mjs). */
async function rateLimited(clientIp) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(clientIp).digest("hex").slice(0, 16);
  const key = `rl:vitae-license:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= LICENSE_DAILY_LIMIT) return true;
  await store.set(key, String(current + 1));
  return false;
}

/** Accepts a PEM whose newlines arrived escaped as the two characters "\n". */
export function loadPrivateKey(pem) {
  return createPrivateKey(String(pem).replace(/\\n/g, "\n"));
}

/** The key's id and the Blobs mapping key: first 16 hex chars of sha256(subscription id). */
export function licenseId(subscriptionId) {
  return createHash("sha256").update(String(subscriptionId), "utf8").digest("hex").slice(0, 16);
}

/**
 * current_period_end moved from the subscription to its items in newer Stripe
 * API versions; accept either.
 */
export function periodEnd(sub) {
  if (Number.isInteger(sub?.current_period_end)) return sub.current_period_end;
  const itemEnd = sub?.items?.data?.[0]?.current_period_end;
  return Number.isInteger(itemEnd) ? itemEnd : null;
}

/** "monthly" or "annual" from the price's billing interval, else the fallback. */
export function planOf(sub, fallback) {
  const interval = sub?.items?.data?.[0]?.price?.recurring?.interval;
  if (interval === "month") return "monthly";
  if (interval === "year") return "annual";
  return fallback === "monthly" || fallback === "annual" ? fallback : null;
}

/**
 * The exp a key for this subscription should carry right now, or null when the
 * subscription no longer entitles the holder to Plus.
 */
export function expiryFor(sub, now) {
  if (sub?.status === "active" || sub?.status === "trialing") {
    const end = periodEnd(sub);
    return end === null ? null : end + GRACE_SECONDS;
  }
  if (sub?.status === "past_due") return now + GRACE_SECONDS;
  return null;
}

/** Pure key builder. The field order of the payload is part of the format. */
export function buildLicenseKey({ subscriptionId, plan, exp, iat, privateKey }) {
  const payload = Buffer.from(
    JSON.stringify({ exp, iat, id: licenseId(subscriptionId), p: PAYLOAD_PRODUCT, plan, v: 2 }),
    "utf8",
  );
  const sig = sign(null, payload, privateKey);
  return "VP2-" + payload.toString("base64url") + "." + sig.toString("base64url");
}

async function stripeGet(path, secretKey) {
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}${path}`, { headers: { Authorization: `Bearer ${secretKey}` } });
  } catch (_) {
    return { error: json(502, { error: "stripe_unreachable", detail: "Could not reach the payment processor." }) };
  }
  if (resp.status === 404) return { notFound: true };
  if (!resp.ok) {
    return { error: json(502, { error: "stripe_error", detail: "The payment processor did not answer as expected." }) };
  }
  try {
    return { data: await resp.json() };
  } catch (_) {
    return { error: json(502, { error: "stripe_bad_response" }) };
  }
}

/** Looks up the { subscription, plan } mapping for a license id; null if unknown. */
async function readMapping(id) {
  const raw = await getStore(MAPPING_STORE).get(id);
  if (!raw) return null;
  try {
    const record = JSON.parse(raw);
    return typeof record?.subscription === "string" ? record : null;
  } catch (_) {
    return null;
  }
}

/** Signs a key for the subscription, or returns the 410 response when it has lapsed. */
function keyResponse(sub, plan, pem, extra) {
  const now = Math.floor(Date.now() / 1000);
  const exp = expiryFor(sub, now);
  if (exp === null) {
    return json(410, { status: typeof sub?.status === "string" ? sub.status : "unknown" });
  }
  if (!plan) return json(502, { error: "stripe_bad_response" });
  let key;
  try {
    key = buildLicenseKey({ subscriptionId: sub.id, plan, exp, iat: now, privateKey: loadPrivateKey(pem) });
  } catch (_) {
    return json(500, { error: "signing_failed", detail: "The key could not be issued." });
  }
  return json(200, { key, ...extra });
}

async function issue(sessionId, secretKey, pem) {
  const got = await stripeGet(
    `/checkout/sessions/${encodeURIComponent(sessionId)}?expand[]=subscription`,
    secretKey,
  );
  if (got.error) return got.error;
  if (got.notFound) return json(404, { error: "not_found", detail: "No order matches this link." });
  const session = got.data;

  const product = session?.metadata?.product || "";
  if (!product.startsWith(PRODUCT_PREFIX) || session.mode !== "subscription") {
    return json(404, { error: "not_found", detail: "No Vitae Plus order matches this link." });
  }
  const sub = session.subscription;
  if (session.status !== "complete" || !sub || typeof sub !== "object" || sub.status === "incomplete") {
    return json(402, { error: "not_paid", detail: "The payment has not cleared yet." });
  }
  if (typeof sub.id !== "string") return json(502, { error: "stripe_bad_response" });

  const plan = planOf(sub, product.slice(PRODUCT_PREFIX.length));
  if (plan) {
    try {
      await getStore(MAPPING_STORE).set(licenseId(sub.id), JSON.stringify({ subscription: sub.id, plan }));
    } catch (_) {
      // Without the mapping the app could never refresh this key.
      return json(500, { error: "storage_failed", detail: "The key could not be issued." });
    }
  }
  return keyResponse(sub, plan, pem, { email: session.customer_details?.email || null });
}

async function refresh(id, secretKey, pem) {
  const mapping = await readMapping(id);
  if (!mapping) return json(404, { error: "not_found" });
  const got = await stripeGet(`/subscriptions/${encodeURIComponent(mapping.subscription)}`, secretKey);
  if (got.error) return got.error;
  if (got.notFound) return json(404, { error: "not_found" });
  const sub = got.data;
  if (typeof sub?.id !== "string" || licenseId(sub.id) !== id) return json(502, { error: "stripe_bad_response" });
  return keyResponse(sub, planOf(sub, mapping.plan), pem, { status: sub.status });
}

/**
 * The id of a portal configuration that only allows invoices, the card, and cancelling at the
 * end of the paid period. Created on first use; null if it cannot be made (the caller then
 * refuses rather than opening an unrestricted portal).
 */
export async function portalConfiguration(secretKey) {
  const fromEnv = Netlify.env.get("STRIPE_PORTAL_CONFIG_VITAE_PLUS");
  if (fromEnv) return fromEnv;
  const store = getStore(MAPPING_STORE);
  const cached = await store.get(PORTAL_CONFIG_BLOB);
  if (cached) return cached;
  const params = new URLSearchParams({
    "business_profile[headline]": "Vitae Plus from Purplelink LLC",
    "business_profile[privacy_policy_url]": `${SITE_ORIGIN}/privacy/`,
    "business_profile[terms_of_service_url]": `${SITE_ORIGIN}/terms/`,
    default_return_url: `${SITE_ORIGIN}/vitae/plus/`,
    "features[invoice_history][enabled]": "true",
    "features[payment_method_update][enabled]": "true",
    "features[subscription_cancel][enabled]": "true",
    "features[subscription_cancel][mode]": "at_period_end",
    "features[subscription_cancel][proration_behavior]": "none",
    "features[customer_update][enabled]": "false",
    "features[subscription_update][enabled]": "false",
    "metadata[product]": "vitae-plus",
  });
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/billing_portal/configurations`, {
      method: "POST",
      headers: { Authorization: `Bearer ${secretKey}`, "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
  } catch (_) {
    return null;
  }
  if (!resp.ok) {
    console.error("vitae-license: portal configuration error", resp.status);
    return null;
  }
  const config = await resp.json().catch(() => null);
  if (typeof config?.id !== "string") return null;
  await store.set(PORTAL_CONFIG_BLOB, config.id);
  return config.id;
}

async function manage(id, secretKey) {
  const mapping = await readMapping(id);
  if (!mapping) return json(404, { error: "not_found" });
  const got = await stripeGet(`/subscriptions/${encodeURIComponent(mapping.subscription)}`, secretKey);
  if (got.error) return got.error;
  if (got.notFound) return json(404, { error: "not_found" });
  const customer = typeof got.data?.customer === "string" ? got.data.customer : got.data?.customer?.id;
  if (!customer) return json(502, { error: "stripe_bad_response" });
  const configuration = await portalConfiguration(secretKey);
  if (!configuration) return json(502, { error: "portal_unavailable" });

  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/billing_portal/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ customer, configuration, return_url: `${SITE_ORIGIN}/vitae/plus/` }),
    });
  } catch (_) {
    return json(502, { error: "stripe_unreachable" });
  }
  if (!resp.ok) {
    console.error("vitae-license: billing portal error", resp.status);
    return json(502, { error: "stripe_error" });
  }
  const portal = await resp.json().catch(() => null);
  if (typeof portal?.url !== "string" || !portal.url.startsWith("https://billing.stripe.com/")) {
    return json(502, { error: "stripe_bad_response" });
  }
  return json(200, { url: portal.url });
}

/** Per-address, per-UTC-day counter so one inbox cannot be flooded with recovery emails. */
async function emailRateLimited(email) {
  const day = new Date().toISOString().slice(0, 10);
  const digest = createHash("sha256").update(email).digest("hex").slice(0, 16);
  const key = `rl:vitae-recover:${day}:${digest}`;
  const store = getStore("rate-limits");
  const current = parseInt((await store.get(key)) || "0", 10) || 0;
  if (current >= RECOVER_PER_EMAIL_DAILY) return true;
  await store.set(key, String(current + 1));
  return false;
}

/**
 * Current keys for every live Vitae Plus subscription of the Stripe customers with this
 * email. Also restores the id-to-subscription mapping, so the recovered keys refresh.
 */
export async function keysForEmail(email, secretKey, pem, now = Math.floor(Date.now() / 1000)) {
  const privateKey = loadPrivateKey(pem);
  const seen = new Set();
  const keys = [];
  // Stripe matches the email exactly as stored; try it as typed and in lower case.
  for (const address of [...new Set([email, email.toLowerCase()])]) {
    const customers = await stripeGet(`/customers?email=${encodeURIComponent(address)}&limit=10`, secretKey);
    if (customers.error) return { error: customers.error };
    for (const customer of customers.data?.data ?? []) {
      if (typeof customer?.id !== "string" || seen.has(customer.id)) continue;
      seen.add(customer.id);
      const subs = await stripeGet(
        `/subscriptions?customer=${encodeURIComponent(customer.id)}&status=all&limit=20`, secretKey);
      if (subs.error) return { error: subs.error };
      for (const sub of subs.data?.data ?? []) {
        const product = sub?.metadata?.product || "";
        if (!product.startsWith(PRODUCT_PREFIX) || typeof sub.id !== "string") continue;
        const exp = expiryFor(sub, now);
        const plan = planOf(sub, product.slice(PRODUCT_PREFIX.length));
        if (exp === null || !plan) continue;
        await getStore(MAPPING_STORE).set(licenseId(sub.id), JSON.stringify({ subscription: sub.id, plan }));
        keys.push({ key: buildLicenseKey({ subscriptionId: sub.id, plan, exp, iat: now, privateKey }), plan });
      }
    }
  }
  return { keys };
}

async function sendRecoveryEmail(to, keys) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return false;
  const plural = keys.length > 1;
  const list = keys.map((k) => `${k.plan === "annual" ? "Annual" : "Monthly"} plan:\n${k.key}`).join("\n\n");
  const htmlList = keys
    .map((k) => `<p>${k.plan === "annual" ? "Annual" : "Monthly"} plan:<br><code>${k.key}</code></p>`)
    .join("");
  const steps = "In Vitae, open Settings, then Vitae Plus, paste the key and click Activate.";
  const text =
    `Here ${plural ? "are your current Vitae Plus keys" : "is your current Vitae Plus key"}, as requested.\n\n${list}\n\n` +
    `${steps} Vitae renews the key by itself while the subscription is active.\n\n` +
    `If you did not ask for this, you can ignore it; nothing has changed.\n\n` +
    `Purplelink LLC, Atlanta, Georgia`;
  const html =
    `<p>Here ${plural ? "are your current Vitae Plus keys" : "is your current Vitae Plus key"}, as requested.</p>${htmlList}` +
    `<p>${steps} Vitae renews the key by itself while the subscription is active.</p>` +
    `<p>If you did not ask for this, you can ignore it; nothing has changed.</p>` +
    `<p>Purplelink LLC, Atlanta, Georgia</p>`;
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        from: ORDER_FROM_ADDRESS,
        reply_to: ORDER_REPLY_TO,
        to: [to],
        subject: plural ? "Your Vitae Plus keys" : "Your Vitae Plus key",
        text,
        html,
      }),
    });
    return resp.ok;
  } catch (_) {
    return false;
  }
}

async function recover(email, secretKey, pem) {
  const found = await keysForEmail(email, secretKey, pem);
  if (found.error) return found.error;
  if (found.keys.length > 0 && !(await sendRecoveryEmail(email, found.keys))) {
    return json(502, { error: "email_failed", detail: "The email could not be sent. Please try again later." });
  }
  // Same answer whether or not anything matched.
  return json(200, { status: "sent_if_found" });
}

function clientIpOf(request) {
  return (
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown"
  );
}

async function handlePost(request) {
  const body = await request.json().catch(() => null);
  if (typeof body?.recover === "string") {
    const email = body.recover.trim();
    if (!EMAIL_PATTERN.test(email)) {
      return json(400, { error: "bad_email", detail: "Enter the email address you used at checkout." });
    }
    if ((await rateLimited(clientIpOf(request))) || (await emailRateLimited(email.toLowerCase()))) {
      return json(429, { error: "rate_limited", detail: "Too many requests today. Please try again tomorrow." });
    }
    const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
    const pem = Netlify.env.get("VITAE_LICENSE_PRIVATE_KEY");
    if (!secretKey || !pem) return json(500, { error: "misconfigured", detail: "The license service is not set up yet." });
    return recover(email, secretKey, pem);
  }
  const id = typeof body?.manage === "string" ? body.manage : "";
  if (!LICENSE_ID.test(id)) {
    return json(400, { error: "bad_id", detail: "The key id must be 16 lowercase hex characters." });
  }
  if (await rateLimited(clientIpOf(request))) {
    return json(429, { error: "rate_limited", detail: "Too many requests from this address today." });
  }
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return json(500, { error: "misconfigured", detail: "The license service is not set up yet." });
  return manage(id, secretKey);
}

export default async function handler(request) {
  if (request.method === "POST") return handlePost(request);
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });

  const params = new URL(request.url).searchParams;
  const sessionId = params.get("session_id");
  const refreshId = params.get("refresh");

  // The old GET ?manage=<id> link put the id in browser history; send it to the help page.
  if (params.get("manage") !== null) return redirect(MANAGE_FALLBACK);
  if (refreshId !== null && !LICENSE_ID.test(refreshId)) {
    return json(400, { error: "bad_id", detail: "The key id must be 16 lowercase hex characters." });
  }
  if (refreshId === null && !SESSION_ID.test(sessionId || "")) {
    return json(400, { error: "bad_session_id", detail: "That link is missing its order reference." });
  }

  if (await rateLimited(clientIpOf(request))) {
    return json(429, { error: "rate_limited", detail: "Too many requests from this address today." });
  }

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const pem = Netlify.env.get("VITAE_LICENSE_PRIVATE_KEY");
  if (!secretKey || !pem) {
    return json(500, { error: "misconfigured", detail: "The license service is not set up yet." });
  }
  if (refreshId !== null) return refresh(refreshId, secretKey, pem);
  return issue(sessionId, secretKey, pem);
}
