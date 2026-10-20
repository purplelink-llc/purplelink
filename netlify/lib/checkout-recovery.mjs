/**
 * Checkout recovery for ModernTex (experiment moderntex-checkout-recovery, approved by Ben 2026-10-20).
 *
 * checkout.mjs asks Stripe for promotional-email consent and enables `after_expiration.recovery` on the session.
 * Stripe does not email anyone itself: when an unpaid session expires (24 hours after it was created) it sends
 * `checkout.session.expired` with a recovery URL that reopens a copy of the same checkout, valid 30 days.
 * stripe-webhook.mjs then sends one plain email, only when all of these hold:
 *   - the product is in RECOVERY_PRODUCTS,
 *   - the buyer ticked Stripe's consent box (consent.promotions === "opt_in"; Stripe only offers it to US buyers),
 *   - the session has an email address and a recovery URL,
 *   - the address has not bought the product, has not unsubscribed from purchase follow-ups, and was not sent a
 *     recovery email in the last QUIET_DAYS.
 * Same price, no discount, no promotion code. CHECKOUT_RECOVERY=off in the Netlify environment stops the emails
 * (the Stripe parameters stay, so consent is still recorded). Addresses are never logged.
 */
import { POSTAL_ADDRESS, FROM_ADDRESS, REPLY_TO, emailHash, unsubscribeUrl } from "./followup.mjs";

/** Product key -> the name and price the email states. The price must match checkout.mjs (a test compares them). */
export const RECOVERY_PRODUCTS = Object.freeze({
  moderntex: { name: "ModernTex", price: "$19.99", cents: 1999 },
});
export const QUIET_DAYS = 30;
export const STORE = "checkout-recovery";

/** The Checkout Session parameters that turn recovery on, or {} for a product without it. */
export function recoveryParams(product) {
  if (!Object.hasOwn(RECOVERY_PRODUCTS, product)) return {};
  return {
    "consent_collection[promotions]": "auto",
    "after_expiration[recovery][enabled]": "true",
    "after_expiration[recovery][allow_promotion_codes]": "false",
  };
}

/** True when a Stripe error is about the recovery parameters, so checkout can retry without them. */
export function isRecoveryParamError(data) {
  const e = data && data.error;
  if (!e) return false;
  const where = `${e.param || ""} ${e.message || ""}`;
  return /consent_collection|after_expiration|promotional|recovery/i.test(where);
}

/** The recovery email for one address. */
export function recoveryEmail({ to, product, url, secret }) {
  const p = RECOVERY_PRODUCTS[product];
  if (!p || !url) return null;
  const unsub = unsubscribeUrl(to, secret);
  const paragraphs = [
    `You started buying ${p.name} on purplelink.llc, and the checkout closed before payment, so nothing was charged.`,
    `If you still want it, this link reopens the same checkout at the same price (${p.price}, once, with updates included). It works for 30 days: ${url}`,
    "If something on the page stopped you (a payment method, a licensing question, a problem with the trial), reply and tell me. I read every reply myself.",
    "Ben Ampel",
  ];
  const text = `${paragraphs.join("\n\n")}\n\n--\nYou are getting this once because you agreed to emails at checkout. To get no more email from me, reply "stop" or use this link: ${unsub}\n${POSTAL_ADDRESS}`;
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const html = paragraphs.map((s) => `<p>${esc(s).replace(esc(url), `<a href="${esc(url)}">${esc(url)}</a>`)}</p>`).join("") +
    `<p style="font-size: 13px; color: #666;">You are getting this once because you agreed to emails at checkout. To get no more email from me, reply "stop" or <a href="${esc(unsub)}">use this link</a>.<br>${POSTAL_ADDRESS}</p>`;
  return {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject: `Your ${p.name} checkout`,
    text,
    html,
    headers: { "List-Unsubscribe": `<${unsub}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  };
}

/**
 * Decide and send for one expired session. `store` and `suppressed` are Blobs stores; `send` posts the email and
 * returns true on success. Returns a short status string for the webhook response (never the address).
 */
export async function handleExpired(session, { store, suppressed, send, secret, enabled, nowS = Math.floor(Date.now() / 1000) }) {
  const product = session?.metadata?.product || "";
  if (!Object.hasOwn(RECOVERY_PRODUCTS, product)) return "not_recovery_product";
  const url = session?.after_expiration?.recovery?.url || "";
  if (!url) return "no_recovery_url";
  if (session?.consent?.promotions !== "opt_in") return "no_consent";
  const email = (session?.customer_details?.email || session?.customer_email || "").trim();
  if (!email) return "no_email";
  if (await store.get(`session:${session.id}`)) return "duplicate";
  const h = emailHash(email);
  if (await store.get(`bought:${product}:${h}`)) { await store.set(`session:${session.id}`, "bought"); return "already_bought"; }
  if (await suppressed.get(h)) { await store.set(`session:${session.id}`, "suppressed"); return "suppressed"; }
  const last = await store.get(`email:${h}`);
  if (last && nowS - Number(last) < QUIET_DAYS * 86400) { await store.set(`session:${session.id}`, "quiet"); return "quiet"; }
  if (!enabled) { await store.set(`session:${session.id}`, "off"); return "off"; }
  const mail = recoveryEmail({ to: email, product, url, secret });
  const ok = mail ? await send(mail) : false;
  if (!ok) return "send_failed";
  await store.set(`session:${session.id}`, String(nowS));
  await store.set(`email:${h}`, String(nowS));
  return "sent";
}

/** Record a completed purchase so a later expired session from the same address never gets a recovery email. */
export async function markBought(store, product, email) {
  if (!Object.hasOwn(RECOVERY_PRODUCTS, product) || !email) return;
  await store.set(`bought:${product}:${emailHash(email.trim())}`, new Date().toISOString());
}
