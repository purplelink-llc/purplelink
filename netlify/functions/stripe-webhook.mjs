/**
 * Netlify Function — Paper Review Stripe webhook receiver.
 *
 * POST /.netlify/functions/stripe-webhook
 *
 * Stripe POSTs `checkout.session.completed` here when a Paper Review payment
 * succeeds. We verify the Stripe signature, extract session_id + customer
 * email + amount, then forward to the Modal backend's
 * /paper-review/register-token endpoint (authenticated by a shared secret
 * header) so the backend can mint a redemption token for that session.
 *
 * Required env vars:
 *   STRIPE_WEBHOOK_SECRET    — whsec_… signing secret from the Stripe webhook config
 *   BACKEND_WEBHOOK_SECRET   — same value as the Modal secret `paper-review-shared`
 *
 * Optional env vars:
 *   RESEND_API_KEY  — same Resend key used by backend/latextools/delivery.py.
 *                     If set (along with ALERT_EMAIL_TO), a best-effort alert
 *                     email is sent to the operator whenever forwarding to
 *                     Modal fails, so a fully-exhausted Stripe retry window
 *                     (Modal down for the full ~3 days) doesn't strand a paid
 *                     session with no token minted and nobody notified.
 *   ALERT_EMAIL_TO  — operator address to receive that alert.
 *
 * Webhook endpoint to register in the Stripe dashboard:
 *   https://purplelink.llc/.netlify/functions/stripe-webhook
 *   subscribed to event: checkout.session.completed
 */

import { createHmac, timingSafeEqual, randomBytes, sign as edSign, createPrivateKey } from "node:crypto";
import { getStore } from "@netlify/blobs";

const MODAL_REGISTER_URL =
  "https://ben-ampel--purplelink-latextools-web.modal.run/paper-review/register-token";
// Seeds the follow-up emails for a purchase this function delivers itself
// (ModernTex). Best effort: a failure here never fails the webhook.
const MODAL_LIFECYCLE_URL =
  "https://ben-ampel--purplelink-latextools-web.modal.run/lifecycle/register";
const LIFECYCLE_PRODUCTS = new Set(["moderntex"]);
const RESEND_API_URL = "https://api.resend.com/emails";
// Resend verifies domains exactly: send from `purplelink.llc`, never a
// subdomain. RESEND_API_KEY is the "purplelink-netlify" key (sending access,
// purplelink.llc only); until 2026-09-04 the value in Netlify was a
// placeholder, so every alert before then failed silently.
const ALERT_FROM_ADDRESS = "Purplelink Alerts <alerts@purplelink.llc>";

const MAX_SIG_AGE_SECONDS = 5 * 60;   // reject replays older than 5 min

// Products whose delivery is a Modal redemption token. Anything else on this
// Stripe account (e.g. muscleonglp.com's guides) belongs to a different site's
// webhook and must not be forwarded to Modal. Keep in step with
// checkout.mjs's PRODUCT_CATALOG together with BLOB_DELIVERED_PRODUCTS below.
const PURPLELINK_PRODUCTS = new Set([
  "paper-review-standard",
  "paper-review-journal",
  "paper-review-deep",
  "paper-review-pack-5",
  "paper-review-pack-20",
  "cover-letter",
  "anonymity-check",
  "citation-gap",
  "revision-review",
  "response-review",
  "resume-review",
  "digest-monthly",
  "digest-annual",
]);

// Products this site sells whose delivery needs nothing from this webhook: the
// success page hands the buyer a file from a private Blobs store after checking
// the session is paid (kit-download.mjs, moderntex-download.mjs). They are
// listed so a ModernTex or kit sale reads as "delivered" in the function log
// rather than as a foreign product.
const BLOB_DELIVERED_PRODUCTS = new Map([
  ["kit-faceless",      { name: "The Faceless Content Pipeline kit", successPath: "/kits/success/" }],
  ["kit-monetization",  { name: "The Monetization Stack kit",        successPath: "/kits/success/" }],
  ["kit-bundle",        { name: "the kit bundle",                    successPath: "/kits/success/" }],
  ["kit-clip",          { name: "The Clip Pipeline kit",             successPath: "/kits/success/" }],
  ["moderntex",         { name: "ModernTex for macOS",               successPath: "/moderntex/success/" }],
]);

// Vitae Plus subscriptions (checkout.mjs: vitae-plus-monthly, vitae-plus-annual).
// The success page gets the key from vitae-license.mjs, and the app's refresh reads the
// subscription's live status from Stripe, so a renewal, failed payment or cancellation needs
// no webhook action. On checkout the buyer is emailed the success link (which issues a
// current key whenever it is opened) and the recovery page, so closing the tab loses nothing.
const VITAE_PLUS_PREFIX = "vitae-plus-";
const SITE_ORIGIN = "https://purplelink.llc";
const ORDER_FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const ORDER_REPLY_TO = "ben@purplelink.llc";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Verify a Stripe signature header against the raw body.
 * Stripe signs `${timestamp}.${rawBody}` with HMAC-SHA256 using the
 * webhook signing secret. The `Stripe-Signature` header looks like:
 *   t=1657123456,v1=abcdef…,v1=…   (multiple v1 entries allowed during rotation)
 */
function verifyStripeSignature(rawBody, header, secret) {
  if (!header || !secret) return false;
  const parts = header.split(",").map((p) => p.trim());
  let timestamp = null;
  const candidates = [];
  for (const part of parts) {
    const [k, v] = part.split("=");
    if (k === "t") timestamp = v;
    if (k === "v1") candidates.push(v);
  }
  if (!timestamp || candidates.length === 0) return false;

  const ts = parseInt(timestamp, 10);
  if (!Number.isFinite(ts)) return false;
  const ageSeconds = Math.floor(Date.now() / 1000) - ts;
  if (ageSeconds > MAX_SIG_AGE_SECONDS) return false;

  const signedPayload = `${timestamp}.${rawBody}`;
  const expected = createHmac("sha256", secret).update(signedPayload).digest("hex");
  const expectedBuf = Buffer.from(expected, "utf8");

  for (const sig of candidates) {
    const sigBuf = Buffer.from(sig, "utf8");
    if (sigBuf.length === expectedBuf.length && timingSafeEqual(sigBuf, expectedBuf)) {
      return true;
    }
  }
  return false;
}

/**
 * Best-effort alert email so a paid session that can't be forwarded to Modal
 * doesn't go unnoticed. Never throws — a failure here must not affect the
 * webhook's response to Stripe (which controls retry behavior).
 */
async function alertOperator(subject, detail) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  const to = Netlify.env.get("ALERT_EMAIL_TO");
  if (!apiKey || !to) return;

  try {
    await fetch(RESEND_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        from: ALERT_FROM_ADDRESS,
        to: [to],
        subject: `[purplelink.llc] ${subject}`,
        text: detail,
      }),
    });
  } catch (_) {
    // Swallow — alerting is best-effort and must never break the webhook.
  }
}

// ModernTex license keys: `MTX1-` + Crockford-Base32(4-byte nonce ‖ 64-byte Ed25519
// signature over "ModernTexLicenseV1" + nonce). Verified entirely offline in the app against
// the matching public key baked into LicenseKey.swift — this MUST stay byte-for-byte
// identical to that file's scheme, since it is the only issuer of a real key. The private key
// lives only in MODERNTEX_LICENSE_PRIVATE_KEY (Netlify production env) and this Mac's login
// Keychain; it is never logged, returned, or committed.
const MTX_LICENSE_PUBLIC_KEY_B64 = "2bJapUgUz0FhlnCVgEnPUGOdr6TE8swfvdqHkB/6cBM=";
const MTX_LICENSE_DOMAIN = Buffer.from("ModernTexLicenseV1", "utf8");
const CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

function crockfordBase32Encode(buf) {
  let bits = 0n, bitCount = 0, out = "";
  for (const byte of buf) {
    bits = (bits << 8n) | BigInt(byte);
    bitCount += 8;
    while (bitCount >= 5) {
      bitCount -= 5;
      out += CROCKFORD_ALPHABET[Number((bits >> BigInt(bitCount)) & 0x1fn)];
    }
  }
  if (bitCount > 0) out += CROCKFORD_ALPHABET[Number((bits << BigInt(5 - bitCount)) & 0x1fn)];
  return out;
}

/**
 * Signs one new, unique license key, or null if the private key isn't configured (never
 * throws — a signing failure must not break checkout delivery of the download itself).
 */
function issueModernTexLicense() {
  const privB64 = Netlify.env.get("MODERNTEX_LICENSE_PRIVATE_KEY");
  if (!privB64) return null;
  try {
    const privateKey = createPrivateKey({
      key: { kty: "OKP", crv: "Ed25519", d: privB64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
             x: MTX_LICENSE_PUBLIC_KEY_B64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "") },
      format: "jwk",
    });
    const nonce = randomBytes(4);
    const signature = edSign(null, Buffer.concat([MTX_LICENSE_DOMAIN, nonce]), privateKey);
    const body = crockfordBase32Encode(Buffer.concat([nonce, signature]));
    const groups = body.match(/.{1,5}/g) ?? [];
    return "MTX1-" + groups.join("-");
  } catch (err) {
    return null;
  }
}

/**
 * Email the buyer the link that reopens their download page. Stripe's own
 * receipt carries no such link, so a buyer who closed the success tab before
 * it loaded would otherwise hold only a charge and no way back to the file.
 * The session id in the URL is the same bearer token the success page uses;
 * the download function re-checks payment on every request, so the link is
 * safe to keep. Returns true on send. Never throws — a failure here must not
 * change the response to Stripe — but it does alert the operator, because a
 * paid buyer with neither the page nor the email is exactly what the alert
 * exists for.
 */
async function emailDownloadLink(to, sessionId, productKey) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  const entry = BLOB_DELIVERED_PRODUCTS.get(productKey);
  if (!apiKey || !to || !entry) return false;
  const link = `${SITE_ORIGIN}${entry.successPath}?session_id=${encodeURIComponent(sessionId)}`;
  // ModernTex only: a license key that unlocks the app permanently, offline, no account.
  // A signing failure here (misconfigured key, transient error) must not block the download
  // email — the buyer still gets their download link either way.
  const license = productKey === "moderntex" ? issueModernTexLicense() : null;
  const licenseTextBlock = license
    ? `\nYour license key (paste into ModernTex's "Have a license key?"):\n${license}\n\n` +
      `This unlocks the app permanently — no account, no further steps.\n`
    : "";
  const licenseHtmlBlock = license
    ? `<p>Your license key (paste into ModernTex's "Have a license key?"):</p>` +
      `<p style="font-family: ui-monospace, monospace; font-size: 14px; letter-spacing: 0.5px;">${license}</p>` +
      `<p>This unlocks the app permanently — no account, no further steps.</p>`
    : "";
  const text =
    `Thanks for buying ${entry.name}.\n\n` +
    `Your download page:\n${link}\n\n` +
    licenseTextBlock +
    `Keep this email: the link keeps working and always hands you the newest version.\n\n` +
    `Questions or trouble downloading: reply to this email.\n\n` +
    `Purplelink LLC, Atlanta, Georgia`;
  const html =
    `<p>Thanks for buying ${entry.name}.</p>` +
    `<p><a href="${link}">Open your download page</a></p>` +
    licenseHtmlBlock +
    `<p>Keep this email: the link keeps working and always hands you the newest version.</p>` +
    `<p>Questions or trouble downloading: reply to this email.</p>` +
    `<p>Purplelink LLC, Atlanta, Georgia</p>`;
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        from: ORDER_FROM_ADDRESS,
        reply_to: ORDER_REPLY_TO,
        to: [to],
        subject: `Your ${entry.name} download`,
        text,
        html,
      }),
    });
    if (resp.ok) return true;
    await alertOperator(
      "Download email failed for a paid order",
      `session_id=${sessionId}\nproduct=${productKey}\nemail=${to}\nresend_status=${resp.status}\n` +
        `Send the buyer this link by hand: ${link}`,
    );
  } catch (err) {
    await alertOperator(
      "Download email failed for a paid order",
      `session_id=${sessionId}\nproduct=${productKey}\nemail=${to}\nerror=${String(err)}\n` +
        `Send the buyer this link by hand: ${link}`,
    );
  }
  return false;
}

/**
 * Email a Vitae Plus buyer the success link and the recovery page. The session id in the
 * link is the same bearer token the success page uses; vitae-license.mjs re-checks the
 * subscription every time it issues a key, so the link is safe to keep. Never throws.
 */
async function emailVitaePlusLink(to, sessionId) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey || !to || !sessionId) return false;
  const link = `${SITE_ORIGIN}/vitae/plus/success/?session_id=${encodeURIComponent(sessionId)}`;
  const recover = `${SITE_ORIGIN}/vitae/plus/recover/`;
  const text =
    `Thanks for subscribing to Vitae Plus.\n\n` +
    `Your key is on this page, and the page gives you a current key whenever you open it:\n${link}\n\n` +
    `In Vitae, open Settings, then Vitae Plus, paste the key and click Activate. Vitae renews the key by itself while the subscription is active.\n\n` +
    `Lost the key later, or moving to a new Mac? Ask for it again at ${recover}\n\n` +
    `To cancel, use Manage Subscription in Settings > Vitae Plus, or reply to this email.\n\n` +
    `Purplelink LLC, Atlanta, Georgia`;
  const html =
    `<p>Thanks for subscribing to Vitae Plus.</p>` +
    `<p><a href="${link}">Open the page with your key</a>. It gives you a current key whenever you open it.</p>` +
    `<p>In Vitae, open Settings, then Vitae Plus, paste the key and click Activate. Vitae renews the key by itself while the subscription is active.</p>` +
    `<p>Lost the key later, or moving to a new Mac? <a href="${recover}">Ask for it again</a>.</p>` +
    `<p>To cancel, use Manage Subscription in Settings &gt; Vitae Plus, or reply to this email.</p>` +
    `<p>Purplelink LLC, Atlanta, Georgia</p>`;
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        from: ORDER_FROM_ADDRESS,
        reply_to: ORDER_REPLY_TO,
        to: [to],
        subject: "Your Vitae Plus key",
        text,
        html,
      }),
    });
    if (resp.ok) return true;
    await alertOperator("Vitae Plus email failed", `session_id=${sessionId}\nemail=${to}\nresend_status=${resp.status}\nSend the buyer: ${link}`);
  } catch (err) {
    await alertOperator("Vitae Plus email failed", `session_id=${sessionId}\nemail=${to}\nerror=${String(err)}\nSend the buyer: ${link}`);
  }
  return false;
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const stripeSecret = Netlify.env.get("STRIPE_WEBHOOK_SECRET");
  const backendSecret = Netlify.env.get("BACKEND_WEBHOOK_SECRET");
  if (!stripeSecret || !backendSecret) {
    return jsonResponse(500, {
      error: "misconfigured",
      detail: "STRIPE_WEBHOOK_SECRET or BACKEND_WEBHOOK_SECRET not set.",
    });
  }

  // Stripe signature verification requires the raw request body.
  const rawBody = await request.text();
  const signature = request.headers.get("stripe-signature");
  if (!verifyStripeSignature(rawBody, signature, stripeSecret)) {
    return jsonResponse(400, { error: "invalid_signature" });
  }

  let event;
  try {
    event = JSON.parse(rawBody);
  } catch (_) {
    return jsonResponse(400, { error: "invalid_json" });
  }

  if (event.type === "customer.subscription.deleted") {
    const deletedProduct = event.data?.object?.metadata?.product || "";
    if (deletedProduct.startsWith(VITAE_PLUS_PREFIX)) {
      console.log("stripe-webhook: vitae plus subscription ended", deletedProduct);
      return jsonResponse(200, { status: "vitae_plus_acknowledged", product: deletedProduct, type: event.type });
    }
    const store = getStore("subscribers");
    const subscriptionId = event.data && event.data.object && event.data.object.id;
    // store.list() pages results; following the cursor matters once the
    // subscriber count crosses one page, or a downgrade-on-cancel for anyone
    // past page 1 would silently never fire (found 2026-09-21 CSP/backend audit).
    let cursor;
    let downgraded = false;
    do {
      const { blobs, cursor: nextCursor } = await store.list({ cursor });
      for (const b of blobs) {
        const raw = await store.get(b.key);
        if (!raw) continue;
        const record = JSON.parse(raw);
        if (record.stripe_subscription_id === subscriptionId) {
          record.tier = "free";
          await store.set(b.key, JSON.stringify(record));
          downgraded = true;
          break;
        }
      }
      cursor = nextCursor;
    } while (cursor && !downgraded);
    return jsonResponse(200, { status: downgraded ? "processed" : "subscriber_not_found", type: event.type });
  }

  // We only care about a completed Checkout session beyond this point.
  if (event.type !== "checkout.session.completed") {
    // 200-OK every other event type so Stripe doesn't retry indefinitely.
    return jsonResponse(200, { status: "ignored", type: event.type });
  }

  const session = event.data && event.data.object;
  if (!session || !session.id) {
    return jsonResponse(400, { error: "missing_session" });
  }
  // Checked before payment_status: a checkout that starts a free trial completes
  // with payment_status "no_payment_required", and it is still ours.
  const sessionProduct = (session.metadata && session.metadata.product) || "";
  if (sessionProduct.startsWith(VITAE_PLUS_PREFIX)) {
    console.log("stripe-webhook: vitae plus checkout completed", sessionProduct, session.payment_status);
    const to = (session.customer_details && session.customer_details.email) || session.customer_email || "";
    const emailed = session.status === "complete" && to ? await emailVitaePlusLink(to, session.id) : false;
    return jsonResponse(200, { status: "vitae_plus_acknowledged", product: sessionProduct, emailed });
  }
  if (session.payment_status !== "paid") {
    return jsonResponse(200, { status: "not_paid", payment_status: session.payment_status });
  }

  const sessionId = session.id;
  const email =
    (session.customer_details && session.customer_details.email) ||
    session.customer_email ||
    "";
  const amountPaid = session.amount_total || 0;   // in cents
  // The checkout function stamps the product key into metadata so we can
  // dispatch on it here without needing a separate price_id → product map.
  const rawProduct = (session.metadata && session.metadata.product) || "";

  // This Stripe account also serves muscleonglp.com, whose webhook endpoint is
  // separate but which shares the account's event stream: Stripe fans every
  // checkout.session.completed out to BOTH endpoints, signing each with that
  // endpoint's own secret, so the signature check above passes for a purchase
  // that has nothing to do with Paper Review. Forwarding one of those to Modal
  // asks it to mint a redemption token for a product it has never heard of; it
  // fails, we return 502, and Stripe retries for ~3 days while alerting the
  // operator each time. Ignore anything that is not ours.
  if (BLOB_DELIVERED_PRODUCTS.has(rawProduct)) {
    // Stripe explicitly warns a webhook event can be delivered more than
    // once. Without a dedupe, a duplicate delivery here would call
    // emailDownloadLink() again, which for ModernTex mints and emails a
    // brand-new, permanently-valid license key with no link back to the
    // first — a confusing, untracked second key for one purchase (found
    // 2026-09-21 backend audit).
    const dedupeStore = getStore("webhook-events");
    const dedupeKey = `blob-delivery:${event.id || sessionId}`;
    if (await dedupeStore.get(dedupeKey)) {
      return jsonResponse(200, { status: "duplicate_event_ignored", product: rawProduct, event_id: event.id || null });
    }
    await dedupeStore.set(dedupeKey, new Date().toISOString());
    const emailed = await emailDownloadLink(email, sessionId, rawProduct);
    if (LIFECYCLE_PRODUCTS.has(rawProduct) && email) {
      // Day-3 tips and a day-21 note, sent by the backend's daily sweep with
      // an unsubscribe link. The buyer already has the key and download, so
      // a failure is logged, not alerted, and Stripe is not asked to retry.
      try {
        const r = await fetch(MODAL_LIFECYCLE_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-webhook-secret": backendSecret },
          body: JSON.stringify({ session_id: sessionId, email, product: rawProduct }),
        });
        if (!r.ok) console.warn("stripe-webhook: lifecycle register failed", r.status);
      } catch (err) {
        console.warn("stripe-webhook: lifecycle register unreachable", String(err));
      }
    }
    return jsonResponse(200, { status: "delivered_by_blobs", product: rawProduct, emailed });
  }
  if (!PURPLELINK_PRODUCTS.has(rawProduct)) {
    // Covers both "unrecognized product key" and "no metadata.product at
    // all". The latter used to fall through and default to Paper Review, on
    // the assumption that a blank rawProduct meant an old, pre-metadata
    // Purplelink session — true only back when this Stripe account sold one
    // thing. It now also serves muscleonglp.com,
    // which shares this account's event stream but stamps no matching
    // metadata, so a blank rawProduct is the ordinary case for a foreign-site
    // sale landing on this webhook, not evidence of an old Purplelink order:
    // every real purchase through this site's own checkout.mjs has always
    // stamped metadata.product. Treating it as "not ours" instead of
    // guessing closes a silent misattribution (found 2026-09-21 backend
    // audit: a blank-metadata session was being forwarded to Modal and
    // credited as a Paper Review purchase nobody made).
    return jsonResponse(200, { status: "ignored_foreign_product", product: rawProduct || null });
  }

  if (rawProduct === "digest-monthly" || rawProduct === "digest-annual") {
    const store = getStore("subscribers");
    const digestEmail = email.toLowerCase().trim();
    if (!digestEmail) {
      // Stripe Checkout normally always populates customer_details.email for
      // a completed session, so this should be unreachable — but if it ever
      // happens, the buyer has paid and there is no subscriber record to
      // create from this event alone. Retrying won't help (Stripe resends
      // the same session with the same missing email), so alert instead of
      // returning a 200 that looks like success (found 2026-09-21 backend
      // audit).
      await alertOperator(
        "Paid digest subscription has no email to add",
        `session_id=${sessionId}\nproduct=${rawProduct}\ncustomer=${session.customer}\nsubscription=${session.subscription}\n\n` +
          `Stripe paid this session but customer_details.email was blank, so no subscriber record was created. ` +
          `Find the buyer's email from the Stripe dashboard for this session and add them manually.`,
      );
      return jsonResponse(200, { status: "digest_subscribe_failed_no_email", product: rawProduct });
    }
    const existing = await store.get(digestEmail);
    const record = existing ? JSON.parse(existing) : {
      email: digestEmail,
      subscribedAt: new Date().toISOString(),
    };
    record.tier = "paid";
    record.stripe_customer_id = session.customer;
    record.stripe_subscription_id = session.subscription;
    await store.set(digestEmail, JSON.stringify(record));
    return jsonResponse(200, { status: "digest_subscribed", product: rawProduct, email: digestEmail });
  }

  // Every remaining rawProduct is a confirmed PURPLELINK_PRODUCTS member at
  // this point (checked above) — digest and Blobs-delivered products already
  // returned earlier, so what's left is a genuine Paper Review price key.
  const product = rawProduct;
  // See checkout.mjs — passed through unchanged so the backend can credit
  // the referral loop (task: "co-author exposure referral loop"). Validated
  // server-side against referral_dict there, not trusted here.
  const referralCode = (session.metadata && session.metadata.referral_code) || "";

  // Forward to the Modal backend so a redemption token is minted.
  let registerResp;
  try {
    registerResp = await fetch(MODAL_REGISTER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-webhook-secret": backendSecret,
      },
      body: JSON.stringify({
        session_id: sessionId,
        email,
        amount_paid: amountPaid,
        product,
        referral_code: referralCode,
      }),
    });
  } catch (err) {
    await alertOperator(
      "Modal unreachable while registering a paid session",
      `session_id=${sessionId}\nemail=${email}\nerror=${String(err)}\n\n` +
        `Stripe will retry this webhook on its standard backoff schedule. ` +
        `If Modal stays down for the full retry window (~3 days), this ` +
        `session's token will never be minted and must be registered manually.`
    );
    return jsonResponse(502, { error: "modal_unreachable", detail: String(err) });
  }

  if (!registerResp.ok) {
    const detail = await registerResp.text().catch(() => "");
    await alertOperator(
      "Modal register-token failed for a paid session",
      `session_id=${sessionId}\nemail=${email}\nmodal_status=${registerResp.status}\n` +
        `detail=${detail.slice(0, 300)}\n\n` +
        `Stripe will retry this webhook on its standard backoff schedule. ` +
        `If Modal stays down for the full retry window (~3 days), this ` +
        `session's token will never be minted and must be registered manually.`
    );
    return jsonResponse(502, {
      error: "modal_register_failed",
      modal_status: registerResp.status,
      detail: detail.slice(0, 300),
    });
  }

  return jsonResponse(200, { status: "registered", session_id: sessionId });
}
