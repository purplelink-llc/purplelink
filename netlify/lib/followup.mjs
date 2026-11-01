/**
 * Day-14 follow-up for people who bought a Mac app: one plain email with one question, sent once per address.
 * Pure builders and the unsubscribe token live here; the scheduled sender is functions/post-purchase-followup.mjs
 * and the unsubscribe endpoint is functions/followup-unsubscribe.mjs.
 *
 * The question ("what do you use it for?") gives a testimonial the buyer chooses to write, and a reply is the
 * cheapest way to learn what the app is for. No link, no tracking, no pitch.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

export const SITE_ORIGIN = "https://purplelink.llc";
export const POSTAL_ADDRESS = "Purplelink LLC, 8735 Dunwoody Place #12398, Atlanta, GA 30350";
export const FROM_ADDRESS = "Benjamin Ampel <orders@purplelink.llc>";
export const REPLY_TO = "ben@purplelink.llc";
export const FOLLOW_UP_AFTER_DAYS = 14;
/** A run covers sessions this old; two days of slack so one missed run still catches everyone (sent sessions are remembered). */
export const WINDOW_DAYS = 16;
export const MAX_PER_RUN = 40;
/** An address that already got one is not emailed again for this long, even for a second purchase. */
export const QUIET_DAYS = 90;
const DAY_S = 86400;

/**
 * Checkout product key to the app's name as the buyer knows it. The Suite is one email, named for what it is.
 * A single ModernTex copy is deliberately absent: those buyers already get the backend's day-3 and day-21 emails,
 * whose opt-outs live in a private Modal store this function cannot read, and the privacy page promises one
 * unsubscribe stops every purchase follow-up. Add "moderntex" here once that opt-out can be checked.
 */
export const FOLLOWUP_PRODUCTS = {
  "moderntex-seats": "ModernTex",
  "outbound-veil": "Outbound Veil",
  legroom: "Legroom",
  keyfeel: "Keyfeel",
  tapefolio: "Tapefolio",
  lenscrib: "Lenscrib",
  panely: "Panely",
  summonly: "Summonly",
  "app-suite": "the Mac Suite",
  "bundle-2": "your Mac Suite bundle",
  "bundle-3": "your Mac Suite bundle",
};

/**
 * Where to ask for a public review, per product. Left empty until a listing is live and checked; an app with no
 * entry gets the question only. Add an entry as { label: "MacUpdate", url: "https://..." }.
 */
export const REVIEW_LINKS = {};

/** Stripe `created` bounds for a run at `nowS` (epoch seconds): sessions at least 14 days old, at most WINDOW_DAYS. */
export function windowFor(nowS) {
  return { gte: nowS - WINDOW_DAYS * DAY_S, lte: nowS - FOLLOW_UP_AFTER_DAYS * DAY_S };
}

export function emailHash(email) {
  return createHmac("sha256", "followup-email").update(email.trim().toLowerCase()).digest("hex").slice(0, 24);
}

/** An unsubscribe token for an address: HMAC of the address under a secret, so nothing is stored to make a link. */
export function unsubscribeToken(email, secret) {
  const e = email.trim().toLowerCase();
  const mac = createHmac("sha256", secret).update(`followup-unsub|${e}`).digest("hex").slice(0, 32);
  return `${Buffer.from(e).toString("base64url")}.${mac}`;
}

/** The address a valid token names, or null. */
export function verifyUnsubscribeToken(token, secret) {
  if (typeof token !== "string" || token.length > 400) return null;
  const [encoded, mac] = token.split(".");
  if (!encoded || !mac) return null;
  let email;
  try { email = Buffer.from(encoded, "base64url").toString("utf8"); } catch { return null; }
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/.test(email)) return null;
  const expected = unsubscribeToken(email, secret).split(".")[1];
  const a = Buffer.from(mac), b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b) ? email : null;
}

export function unsubscribeUrl(email, secret) {
  return `${SITE_ORIGIN}/.netlify/functions/followup-unsubscribe?u=${encodeURIComponent(unsubscribeToken(email, secret))}`;
}

/** The email for one buyer. `seats` is the seat count for a seat order (0 otherwise). */
export function followupEmail({ to, product, seats = 0, secret }) {
  const app = FOLLOWUP_PRODUCTS[product];
  if (!app) return null;
  const seatNote = seats > 1 ? ` (${seats} copies for your lab or department)` : "";
  const review = REVIEW_LINKS[product];
  const unsub = unsubscribeUrl(to, secret);
  const paragraphs = [
    `You bought ${app}${seatNote} two weeks ago, so I have one question: what do you use it for? A single sentence is plenty.`,
    `If it is working well and you are happy for me to quote your sentence on the ${app === "the Mac Suite" || app === "your Mac Suite bundle" ? "product" : app} page, say so and tell me the first name and field to use. I will not quote anything without a yes.`,
    "If something is not working, reply and tell me. I read every reply myself.",
    ...(review ? [`If you would rather leave a public review, ${review.label} is here: ${review.url}`] : []),
    "Ben Ampel",
  ];
  const text = `${paragraphs.join("\n\n")}\n\n--\nTo get no more email from me, reply "stop" or use this link: ${unsub}\n${POSTAL_ADDRESS}`;
  const html = paragraphs.map((p, i) => (i === 0 ? `<p>${p}</p>` : `<p>${p.replace(/(https:\/\/\S+)/, '<a href="$1">$1</a>')}</p>`)).join("") +
    `<p style="font-size: 13px; color: #666;">To get no more email from me, reply "stop" or <a href="${unsub}">use this link</a>.<br>${POSTAL_ADDRESS}</p>`;
  return {
    from: FROM_ADDRESS,
    reply_to: REPLY_TO,
    to: [to],
    subject: `How is ${app} working out?`,
    text,
    html,
    headers: { "List-Unsubscribe": `<${unsub}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  };
}
