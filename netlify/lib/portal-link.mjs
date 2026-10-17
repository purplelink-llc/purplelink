/**
 * Short-lived, signed links to a Stripe billing portal.
 *
 * Why: the old digest footer link carried a permanent HMAC of the subscriber's address, so anyone who
 * received a forwarded digest could open that subscriber's billing portal, and the live-sheet portal
 * action returned a portal URL to anyone holding the Checkout session id. Now a portal opens only from
 * a link that was emailed to the subscriber's own address and expires after 30 minutes.
 *
 * Token: base64url(subject) "." expiry (unix seconds) "." hex HMAC-SHA256(SUBSCRIBE_SECRET,
 * "<kind>:<subject>:<expiry>"). The kind ("digest-portal", "live-portal") namespaces the signature, so
 * these tokens can never be replayed as the permanent unsubscribe token (an HMAC of the bare address)
 * or against the other flow. The subject is an email (digest) or a Stripe customer id (live sheets).
 *
 * The portal itself uses a restricted configuration (invoices, card, cancel at period end; no email,
 * address or plan changes), created once and kept in Blobs, or set with STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS.
 * If it cannot be made, no portal opens.
 *
 * Env: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY, RESEND_API_KEY.
 */
import { createHmac, timingSafeEqual } from "node:crypto";
import { getStore } from "@netlify/blobs";

export const SITE_ORIGIN = "https://purplelink.llc";
export const PORTAL_LINK_SECONDS = 30 * 60;
const STRIPE_API = "https://api.stripe.com/v1";
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM = "Purplelink LLC <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const CONFIG_STORE = "billing-portal";
const CONFIG_KEY = "subscriptions-config";

const b64 = (s) => Buffer.from(s, "utf8").toString("base64url");
const unb64 = (s) => Buffer.from(s, "base64url").toString("utf8");
const mac = (secret, kind, subject, exp) => createHmac("sha256", secret).update(`${kind}:${subject}:${exp}`).digest("hex");

export function signPortalToken(kind, subject, secret, now = Math.floor(Date.now() / 1000)) {
  const exp = now + PORTAL_LINK_SECONDS;
  return `${b64(subject)}.${exp}.${mac(secret, kind, subject, exp)}`;
}

/** The subject of a valid, unexpired token of this kind, or null. */
export function verifyPortalToken(kind, token, secret, now = Math.floor(Date.now() / 1000)) {
  if (!secret || typeof token !== "string" || token.length > 600) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [enc, expStr, sig] = parts;
  if (!/^\d{1,12}$/.test(expStr) || !/^[0-9a-f]{64}$/.test(sig)) return null;
  const exp = Number(expStr);
  if (exp < now) return null;
  let subject;
  try { subject = unb64(enc); } catch { return null; }
  if (!subject) return null;
  const expected = mac(secret, kind, subject, exp);
  return timingSafeEqual(Buffer.from(expected), Buffer.from(sig)) ? subject : null;
}

export async function portalConfiguration(secretKey) {
  const fromEnv = process.env.STRIPE_PORTAL_CONFIG_SUBSCRIPTIONS;
  if (fromEnv) return fromEnv;
  const store = getStore(CONFIG_STORE);
  try {
    const cached = await store.get(CONFIG_KEY);
    if (cached) return cached;
  } catch { /* fall through and create one */ }
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/billing_portal/configurations`, {
      method: "POST",
      headers: { Authorization: `Bearer ${secretKey}`, "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        "business_profile[headline]": "Subscriptions from Purplelink LLC",
        "business_profile[privacy_policy_url]": `${SITE_ORIGIN}/privacy/`,
        "business_profile[terms_of_service_url]": `${SITE_ORIGIN}/terms/`,
        default_return_url: SITE_ORIGIN + "/",
        "features[invoice_history][enabled]": "true",
        "features[payment_method_update][enabled]": "true",
        "features[subscription_cancel][enabled]": "true",
        "features[subscription_cancel][mode]": "at_period_end",
        "features[subscription_cancel][proration_behavior]": "none",
        "features[customer_update][enabled]": "false",
        "features[subscription_update][enabled]": "false",
        "metadata[purpose]": "emailed-portal-link",
      }),
    });
  } catch { return null; }
  if (!resp.ok) {
    console.error("portal-link: configuration error", resp.status);
    return null;
  }
  const config = await resp.json().catch(() => null);
  if (typeof config?.id !== "string") return null;
  try { await store.set(CONFIG_KEY, config.id); } catch { /* next call creates another; harmless */ }
  return config.id;
}

/** A Stripe billing portal URL for this customer, or null on any failure. */
export async function createPortalSession(customer, returnUrl, secretKey) {
  const configuration = await portalConfiguration(secretKey);
  if (!configuration) return null;
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/billing_portal/sessions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${secretKey}`, "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ customer, configuration, return_url: returnUrl }),
    });
  } catch { return null; }
  if (!resp.ok) {
    console.error("portal-link: session error", resp.status);
    return null;
  }
  const session = await resp.json().catch(() => null);
  return typeof session?.url === "string" && session.url.startsWith("https://billing.stripe.com/") ? session.url : null;
}

/** Emails the link; returns true when Resend accepted it. */
export async function sendPortalEmail(to, link, what) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return false;
  const minutes = PORTAL_LINK_SECONDS / 60;
  const text = `Someone, probably you, asked to manage ${what} at this address. Use this link to open the billing page:\n\n${link}\n\nThe link works for ${minutes} minutes. If you did not ask, ignore this email; nothing has changed and the link opens nothing for anyone else.\n\nPurplelink LLC, Atlanta, Georgia`;
  const html = `<p>Someone, probably you, asked to manage ${what} at this address. Use this link to open the billing page:</p><p><a href="${link}">Manage my subscription</a></p><p>The link works for ${minutes} minutes. If you did not ask, ignore this email; nothing has changed and the link opens nothing for anyone else.</p><p>Purplelink LLC, Atlanta, Georgia</p>`;
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ from: FROM, reply_to: REPLY_TO, to: [to], subject: "Your billing link from Purplelink", text, html }),
    });
    return resp.ok;
  } catch { return false; }
}
