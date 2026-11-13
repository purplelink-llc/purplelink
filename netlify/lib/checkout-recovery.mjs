/**
 * Checkout recovery (experiment moderntex-checkout-recovery, approved by Ben 2026-10-20; every one-time product since
 * 2026-11-05, docs/designs/buyer-revenue-program.md, piece 3).
 *
 * checkout.mjs asks Stripe for promotional-email consent and enables `after_expiration.recovery` on the session.
 * Stripe does not email anyone itself: when an unpaid session expires (24 hours after it was created) it sends
 * `checkout.session.expired` with a recovery URL that reopens a copy of the same checkout, valid 30 days.
 * stripe-webhook.mjs then sends one plain email, only when all of these hold:
 *   - the product is in RECOVERY_PRODUCTS,
 *   - the buyer ticked Stripe's consent box (consent.promotions === "opt_in"; Stripe only offers it to US buyers),
 *   - the session has an email address and a recovery URL,
 *   - the address has not bought the product, has not unsubscribed from purchase follow-ups, and was not sent a
 *     recovery email (for any product) in the last QUIET_DAYS.
 * Same price, no extra discount, no promotion code. CHECKOUT_RECOVERY=off in the Netlify environment stops the emails
 * (the Stripe parameters stay, so consent is still recorded). Addresses are never logged.
 *
 * Not here: subscriptions (Stripe offers no recovery URL for them) and ModernTex seats (the price depends on the
 * seat count, so one stated price would be wrong).
 */
import { POSTAL_ADDRESS, FROM_ADDRESS, REPLY_TO, emailHash, unsubscribeUrl } from "./followup.mjs";

/**
 * Product key -> the name and price the email states. `kind: "app"` adds "with updates included" (a Mac app whose
 * updates come free); everything else is a one-time purchase. Every price must match what checkout charges: a test
 * compares each one with checkout.mjs's inline amount, Modal's PAID_PRODUCTS or the product page.
 */
export const RECOVERY_PRODUCTS = Object.freeze({
  "moderntex":                  { name: "ModernTex", price: "$19.99", cents: 1999, kind: "app" },
  "outbound-veil":              { name: "Outbound Veil", price: "$29.99", cents: 2999, kind: "app" },
  "legroom":                    { name: "Legroom", price: "$9.99", cents: 999, kind: "app" },
  "keyfeel":                    { name: "Keyfeel", price: "$9.99", cents: 999, kind: "app" },
  "tapefolio":                  { name: "Tapefolio", price: "$29.99", cents: 2999, kind: "app" },
  "lenscrib":                   { name: "Lenscrib", price: "$19.99", cents: 1999, kind: "app" },
  "lenses":                     { name: "Lenses", price: "$4.99", cents: 499, kind: "once" },
  "nee":                        { name: "Née", price: "$14.99", cents: 1499, kind: "app" },
  "panely":                     { name: "Panely", price: "$9.99", cents: 999, kind: "app" },
  "summonly":                   { name: "Summonly", price: "$9.99", cents: 999, kind: "app" },
  "app-suite":                  { name: "the Purplelink Mac Suite", price: "$59.99", cents: 5999, kind: "app" },
  // A bundle's price depends on the apps chosen (netlify/lib/bundles.mjs), so it has no fixed price here: the email
  // states the session's own amount when it has one, else the percent off.
  "bundle-2":                   { name: "a custom bundle of two Purplelink Mac apps", short: "Purplelink bundle", percent: 25, kind: "app" },
  "bundle-3":                   { name: "a custom bundle of three Purplelink Mac apps", short: "Purplelink bundle", percent: 40, kind: "app" },
  "paper-review-standard":      { name: "a Paper Review (Standard)", price: "$14.00", cents: 1400, kind: "once" },
  "paper-review-journal":       { name: "a Paper Review (Journal check)", price: "$24.00", cents: 2400, kind: "once" },
  "paper-review-deep":          { name: "a Paper Review (Deep)", price: "$39.00", cents: 3900, kind: "once" },
  "paper-review-pack-5":        { name: "a lab pack of 5 Journal reviews", price: "$99.00", cents: 9900, kind: "once" },
  "paper-review-pack-20":       { name: "a lab pack of 20 Journal reviews", price: "$349.00", cents: 34900, kind: "once" },
  "cover-letter":               { name: "the cover letter tool", price: "$2.00", cents: 200, kind: "once" },
  "anonymity-check":            { name: "the anonymity check", price: "$2.00", cents: 200, kind: "once" },
  "journal-check":              { name: "the journal check", price: "$10.00", cents: 1000, kind: "once" },
  "citation-gap":               { name: "the citation gap check", price: "$3.00", cents: 300, kind: "once" },
  "revision-review":            { name: "the revision review", price: "$5.00", cents: 500, kind: "once" },
  "response-review":            { name: "the response letter review", price: "$12.00", cents: 1200, kind: "once" },
  "response-draft":             { name: "the response letter draft", price: "$24.00", cents: 2400, kind: "once" },
  "publication-pack":           { name: "the Publication Pack", price: "$59.00", cents: 5900, kind: "once" },
  "resume-review":              { name: "the resume review", price: "$5.00", cents: 500, kind: "once" },
  "kit-faceless":               { name: "the Faceless Content Pipeline kit", price: "$49.00", cents: 4900, kind: "once" },
  "kit-monetization":           { name: "the Monetization Stack kit", price: "$29.00", cents: 2900, kind: "once" },
  "kit-clip":                   { name: "the Clip Pipeline kit", price: "$10.00", cents: 1000, kind: "once" },
  "kit-bundle":                 { name: "all three kits", short: "kit bundle", price: "$59.00", cents: 5900, kind: "once" },
  "sheet-submission":           { name: "the Journal Submission & R&R Tracker", price: "$12.00", cents: 1200, kind: "once" },
  "sheet-tenure":               { name: "the Tenure & Promotion Dossier Tracker", price: "$12.00", cents: 1200, kind: "once" },
  "sheet-jobmarket":            { name: "the Academic Job Market Tracker", price: "$9.00", cents: 900, kind: "once" },
  "sheet-grantpipeline":        { name: "the Grant Pipeline & PI Effort Tracker", price: "$12.00", cents: 1200, kind: "once" },
  "sheet-reviewmatrix":         { name: "the Systematic Review Screening Matrix", price: "$14.00", cents: 1400, kind: "once" },
  "sheet-bundle":               { name: "the Researcher Spreadsheet Bundle", price: "$39.00", cents: 3900, kind: "once" },
  "photo-license-web":          { name: "a photograph license (web and social)", price: "$29.00", cents: 2900, kind: "once" },
  "photo-license-commercial":   { name: "a photograph license (commercial)", price: "$79.00", cents: 7900, kind: "once" },
  "photo-license-extended":     { name: "a photograph license (extended)", price: "$199.00", cents: 19900, kind: "once" },
  "photo-calendar-iceland":     { name: "the 2027 Iceland calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-japan":       { name: "the 2027 Japan calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-switzerland": { name: "the 2027 Switzerland calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-european-cities": { name: "the 2027 European Cities calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-arizona-desert": { name: "the 2027 Arizona Desert calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-hawaii":      { name: "the 2027 Hawaii calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-best-of":     { name: "the 2027 Best Of calendar", price: "$7.00", cents: 700, kind: "once" },
  "photo-calendar-bundle":      { name: "all seven 2027 calendars", price: "$19.00", cents: 1900, kind: "once", short: "2027 calendars" },
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

/** "a Paper Review (Standard)" -> "Paper Review (Standard)", for the subject line. */
function stripArticle(name) {
  return name.replace(/^(a|the) /, "").replace(/^./, (c) => c.toUpperCase());
}

/** The recovery email for one address. */
export function recoveryEmail({ to, product, url, secret, cents }) {
  const p = RECOVERY_PRODUCTS[product];
  if (!p || !url) return null;
  const priceText = p.price || (Number.isInteger(cents) && cents > 0
    ? `$${(cents / 100).toFixed(2)}`
    : `${p.percent}% off the apps' own prices`);
  const unsub = unsubscribeUrl(to, secret);
  const paragraphs = [
    `You started buying ${p.name} on purplelink.llc, and the checkout closed before payment, so nothing was charged.`,
    `If you still want it, this link reopens the same checkout at the same price (${priceText}, once${p.kind === "app" ? ", with updates included" : ""}). It works for 30 days: ${url}`,
    "If something on the page stopped you (a payment method, a licensing question, something unclear), reply and tell me. I read every reply myself.",
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
    subject: `Your ${p.short || stripArticle(p.name)} checkout`,
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
  const mail = recoveryEmail({ to: email, product, url, secret, cents: Number(session?.amount_total) || undefined });
  const ok = mail ? await send(mail) : false;
  if (!ok) return "send_failed";
  await store.set(`session:${session.id}`, String(nowS));
  await store.set(`email:${h}`, String(nowS));
  return "sent";
}

/**
 * Record a completed purchase so a later expired session from the same address never gets a recovery email.
 * `also` lists more product keys the order covers (the apps in a bundle or the Suite).
 */
export async function markBought(store, product, email, also = []) {
  if (!email) return;
  const h = emailHash(email.trim());
  const at = new Date().toISOString();
  for (const key of new Set([product, ...also])) {
    if (Object.hasOwn(RECOVERY_PRODUCTS, key)) await store.set(`bought:${key}:${h}`, at);
  }
}
