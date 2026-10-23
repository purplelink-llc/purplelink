/**
 * Netlify Function — Stripe Checkout session creator (all paid products).
 *
 * POST /.netlify/functions/checkout
 *   body: { product: "paper-review-standard" | "paper-review-deep" | ... }
 *
 * Maps the product key to a Stripe price_id via per-product env vars, then
 * creates a Checkout Session (one-time payment, or a subscription for the
 * entries marked mode: "subscription"). Returns the hosted URL.
 *
 * The Stripe success URL routes the user to the right post-payment page
 * based on the product category (paper-review goes to /upload/, cover-letter
 * to /tools/cover-letter/compose/, etc.).
 *
 * Required env vars per product key — each is the corresponding price_id.
 * These dollar amounts are the source of truth; the Stripe Price objects
 * created at launch must match them exactly, and so must the visible copy
 * on each tool's landing page. Repriced 2026-07-03 for the Fable 5 model
 * upgrade (see backend/app.py PAID_PRODUCTS for the margin rationale):
 *   STRIPE_PRICE_PAPER_REVIEW_STANDARD     (paper-review-standard, $9)
 *   STRIPE_PRICE_PAPER_REVIEW_JOURNAL      (paper-review-journal, $11)
 *   STRIPE_PRICE_PAPER_REVIEW_DEEP         (paper-review-deep, $15)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_5       (paper-review-pack-5, $38)
 *   STRIPE_PRICE_PAPER_REVIEW_PACK_20      (paper-review-pack-20, $150)
 *   STRIPE_PRICE_COVER_LETTER              (cover-letter, $2)
 *   STRIPE_PRICE_ANONYMITY_CHECK           (anonymity-check, $2)
 *   STRIPE_PRICE_CITATION_GAP              (citation-gap, $3)
 *   STRIPE_PRICE_REVISION_REVIEW           (revision-review, $2)
 *   STRIPE_PRICE_RESPONSE_REVIEW           (response-review, $6)
 *   STRIPE_PRICE_RESUME_REVIEW             (resume-review, $5) — first non-academic product
 *   STRIPE_PRICE_VITAE_PLUS_MONTHLY        (vitae-plus-monthly, $2.99/month subscription, 7-day trial)
 *   STRIPE_PRICE_VITAE_PLUS_ANNUAL         (vitae-plus-annual, $23.99/year subscription, 7-day trial)
 *   STRIPE_SECRET_KEY (shared, sk_test_… or sk_live_…)
 */

import { MAX_SEATS, parseSeats, seatUnitCents } from "../lib/seats.mjs";
import { BUNDLES, parseBundleParts, partsSentence } from "../lib/bundles.mjs";
import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { managedPaymentsOn, applyManagedPayments } from "../lib/managed-payments.mjs";
import { recoveryParams, isRecoveryParamError } from "../lib/checkout-recovery.mjs";

const STRIPE_API = "https://api.stripe.com/v1";

// success_url/cancel_url are handed back to the browser as part of a real
// Stripe Checkout URL, so the Origin header must be checked against a fixed
// allowlist rather than trusted verbatim — otherwise an attacker can point a
// victim's post-payment redirect (with the live session_id) at a domain they
// control. Mirrors backend/app.py's ALLOWED_ORIGINS.
const ALLOWED_ORIGINS = new Set([
  "https://purplelink.llc",
  "https://www.purplelink.llc",
]);
const DEFAULT_ORIGIN = "https://purplelink.llc";

// Idempotency window: retries of the *same* checkout click (e.g. after a
// timed-out/lost response) within this many milliseconds collapse into the
// same Stripe Checkout Session instead of creating a duplicate one.
const IDEMPOTENCY_WINDOW_MS = 5 * 60 * 1000;

// "How did you first hear about us?" answers. Values are stored, labels shown.
// Stripe allows only letters and digits in a dropdown value.
const HEARD_OPTIONS = [
  ["Search engine", "search"],
  ["AI assistant (ChatGPT and others)", "ai"],
  ["Reddit", "reddit"],
  ["A directory or app list", "directory"],
  ["An email from Purplelink", "email"],
  ["A friend or colleague", "friend"],
  ["A university or library page", "library"],
  ["Other", "other"],
];

// ModernTex only: two more optional dropdowns, so an order says who bought and in which field. With the
// "heard" question above that is Stripe's maximum of three custom fields. Stripe limits: label.custom up to
// 50 characters, option label and value up to 100, up to 200 options; values here are lowercase letters and digits.
// The answers stay in Stripe (dashboard and exports); sales.mjs reads them back as counts only.
export const ROLE_FIELD = {
  key: "role",
  label: "Which best describes you?",
  options: [
    ["Graduate student", "gradstudent"],
    ["Faculty or researcher", "faculty"],
    ["Industry researcher", "industry"],
    ["Other", "other"],
  ],
};
export const FIELD_FIELD = {
  key: "field",
  label: "Your main field?",
  options: [
    ["Computer science or engineering", "cseng"],
    ["Mathematics, statistics or physics", "mathstatphys"],
    ["Economics or finance", "econfin"],
    ["Social sciences", "socsci"],
    ["Humanities", "humanities"],
    ["Life sciences", "lifesci"],
    ["Other", "other"],
  ],
};
const ROLE_FIELD_PRODUCTS = new Set(["moderntex"]);

// The trial day the app's Buy link carries (?td=): a whole number of days 0 to 30, or the word "unknown".
// Anything else is dropped. Returns the string to store, or "".
export function cleanTrialDay(v) {
  if (typeof v === "number") v = Number.isInteger(v) ? String(v) : "";
  if (typeof v !== "string") return "";
  return /^(?:[0-9]|[12][0-9]|30|unknown)$/.test(v) ? v : "";
}
// The utm_source of the visit that opened the Buy page, kept only in a short safe charset ("moderntex-app").
export function cleanAppSource(v) {
  if (typeof v !== "string") return "";
  return /^[a-z0-9_-]{1,40}$/.test(v) ? v : "";
}

// Refund line shown beside the Pay button (Stripe custom_text.submit). Each string is the
// "Refunds." sentence of that product's section on /terms/, word for word (a test compares
// them against site/terms/index.html). Only products whose terms carry a no-reason 14-day
// refund are listed; the others (reviews, kits, Vitae Plus, seats, bundles) get no line
// rather than a paraphrase of a different policy.
const REFUND_EMAIL = "Email ben@purplelink.llc within 14 days of purchase and we will refund";
const REFUND_TEXT = {
  "moderntex": `${REFUND_EMAIL} the full $19.99 to the original payment method. You don't need to give a reason. A refunded purchase's license key is no longer licensed for use.`,
  "outbound-veil": `${REFUND_EMAIL} the full $29.99 to the original payment method. You don't need to give a reason. A refunded purchase's license key is no longer licensed for use.`,
  "legroom": `${REFUND_EMAIL} the full $9.99 to the original payment method. You don't need to give a reason. A refunded purchase's license key is no longer licensed for use.`,
  "keyfeel": `${REFUND_EMAIL} the full $9.99 to the original payment method. You don't need to give a reason. A refunded purchase's download link stops working.`,
  "tapefolio": `${REFUND_EMAIL} the full $29.99 to the original payment method. You don't need to give a reason. A refunded purchase's download link stops working.`,
  "panely": `${REFUND_EMAIL} the full $9.99 to the original payment method. You don't need to give a reason. A refunded purchase's download link stops working.`,
  "summonly": `${REFUND_EMAIL} the full $9.99 to the original payment method. You don't need to give a reason. A refunded purchase's download link stops working.`,
  "app-suite": `${REFUND_EMAIL} the full amount you paid to the original payment method. You don't need to give a reason. A refunded Suite's download links stop working, and its ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio, Panely and Summonly license keys and its Vitae Plus key are no longer licensed for use.`,
};

// Defense-in-depth: cap how many Checkout Sessions one IP can spin up per
// day. This costs the attacker nothing directly, but unbounded creation
// pollutes the Stripe dashboard and can trip Stripe's own abuse detection
// on the account, so it's worth throttling even though it's not a direct
// financial exposure. Mirrors backend/latextools/core.py's DAILY_LIMIT
// pattern (per-IP, per-bucket, per-UTC-day counter).
const CHECKOUT_DAILY_LIMIT = 25;

async function checkoutRateLimited(clientIp) {
  const day = new Date().toISOString().slice(0, 10); // YYYY-MM-DD (UTC)
  const digest = createHash("sha256").update(clientIp).digest("hex").slice(0, 16);
  const key = `rl:checkout:${day}:${digest}`;
  const store = getStore("rate-limits");
  const raw = await store.get(key);
  const current = raw ? parseInt(raw, 10) || 0 : 0;
  if (current >= CHECKOUT_DAILY_LIMIT) {
    return true;
  }
  await store.set(key, String(current + 1));
  return false;
}

// product key -> {env var name for price_id, success path}
const PRODUCT_CATALOG = {
  "paper-review-standard":   { envKey: "STRIPE_PRICE_PAPER_REVIEW_STANDARD",   successPath: "/tools/paper-review/upload/" },
  "paper-review-journal":    { envKey: "STRIPE_PRICE_PAPER_REVIEW_JOURNAL",    successPath: "/tools/paper-review/upload/" },
  "paper-review-deep":       { envKey: "STRIPE_PRICE_PAPER_REVIEW_DEEP",       successPath: "/tools/paper-review/upload/" },
  "paper-review-pack-5":     { envKey: "STRIPE_PRICE_PAPER_REVIEW_PACK_5",     successPath: "/tools/paper-review/packs/success/" },
  "paper-review-pack-20":    { envKey: "STRIPE_PRICE_PAPER_REVIEW_PACK_20",    successPath: "/tools/paper-review/packs/success/" },
  "cover-letter":            { envKey: "STRIPE_PRICE_COVER_LETTER",            successPath: "/tools/cover-letter/compose/" },
  "anonymity-check":         { envKey: "STRIPE_PRICE_ANONYMITY_CHECK",         successPath: "/tools/anonymity-check/upload/" },
  "citation-gap":            { envKey: "STRIPE_PRICE_CITATION_GAP",            successPath: "/tools/citation-gap/upload/" },
  "revision-review":         { envKey: "STRIPE_PRICE_REVISION_REVIEW",         successPath: "/tools/paper-review/revision/upload/" },
  "response-review":         { envKey: "STRIPE_PRICE_RESPONSE_REVIEW",         successPath: "/tools/response-review/upload/" },
  "resume-review":           { envKey: "STRIPE_PRICE_RESUME_REVIEW",           successPath: "/tools/resume-review/upload/" },
  // Digital "kits" (downloadable products). Delivery is a token-gated PDF from
  // the kits-delivery Blobs store; see download.mjs. Success page lists the links.
  "kit-faceless":            { envKey: "STRIPE_PRICE_KIT_FACELESS",            successPath: "/kits/success/" },
  "kit-monetization":        { envKey: "STRIPE_PRICE_KIT_MONETIZATION",        successPath: "/kits/success/" },
  "kit-bundle":              { envKey: "STRIPE_PRICE_KIT_BUNDLE",              successPath: "/kits/success/" },
  "kit-clip":                { envKey: "STRIPE_PRICE_KIT_CLIP",                successPath: "/kits/success/" },
  // ModernTex for macOS: $19.99 one-time. Delivery is the session-gated DMG from the
  // moderntex-files Blobs store; see moderntex-download.mjs.
  "moderntex":               { amount: 1999, name: "ModernTex for macOS", successPath: "/moderntex/success/" },
  // ModernTex for labs and departments: 5 or more seats, one license key per seat, priced by seat count in
  // netlify/lib/seats.mjs (never from the client). The same delivery page as a single copy; it lists every key.
  "moderntex-seats":         { seats: true, name: "ModernTex for macOS, license seats", successPath: "/moderntex/success/" },
  // Outbound Veil for macOS: $29.99 one-time (price set in the Stripe Price that
  // STRIPE_PRICE_OUTBOUND_VEIL points at; keep it equal to the copy on /outbound-veil/).
  // Delivery is the session-gated DMG from the outbound-veil-files Blobs store; see
  // outbound-veil-download.mjs.
  "outbound-veil":           { envKey: "STRIPE_PRICE_OUTBOUND_VEIL",           successPath: "/outbound-veil/success/" },
  // Legroom for macOS: $9.99 one-time (price set in the Stripe Price that
  // STRIPE_PRICE_LEGROOM points at; keep it equal to the copy on /legroom/).
  // Delivery is the session-gated DMG from the legroom-files Blobs store; see
  // legroom-download.mjs.
  "legroom":                 { envKey: "STRIPE_PRICE_LEGROOM",                 successPath: "/legroom/success/" },
  // Keyfeel for macOS: $9.99 one-time, priced inline (no Stripe Price to create), like ModernTex.
  // Delivery is the session-gated DMG from the keyfeel-files Blobs store; see keyfeel-download.mjs.
  "keyfeel":                 { amount: 999, name: "Keyfeel for macOS", successPath: "/keyfeel/success/" },
  // Tapefolio for macOS: $29.99 one-time, priced inline (no Stripe Price to create), like Keyfeel.
  // Delivery is the session-gated DMG from the tapefolio-files Blobs store; see tapefolio-download.mjs.
  // Product page and success page: /tapefolio/ and /tapefolio/success/. See docs/products/tapefolio.md.
  "tapefolio":               { amount: 2999, name: "Tapefolio for macOS", successPath: "/tapefolio/success/" },
  // Panely (window manager) and Summonly (launcher and file search): $9.99 one-time each, priced inline like Keyfeel.
  // Delivery is the session-gated DMG from the panely-files / summonly-files Blobs stores. Pages: /panely/ and /summonly/.
  "panely":                { amount: 999, name: "Panely for macOS", successPath: "/panely/success/" },
  "summonly":                { amount: 999, name: "Summonly for macOS", successPath: "/summonly/success/" },
  // Purplelink Mac Suite: ModernTex + Outbound Veil + Legroom + Keyfeel + Tapefolio + Panely + Summonly + Vitae Plus for life,
  // $59.99 one-time (was $54.99 until 2026-10-12 and $54 until 2026-10-07; $49 with four apps, $39 before Legroom; Tapefolio
  // joined 2026-10-09 at the same price, Panely and Summonly joined 2026-10-12 with this price). Priced inline (no Stripe
  // Price to create). One session unlocks all eight: the ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio, Panely and
  // Summonly download functions accept it, and vitae-license.mjs signs a 100-year Vitae Plus key from it. See
  // docs/products/app-suite.md.
  "app-suite":               { amount: 5999, name: "Purplelink Mac Suite: ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio, Panely, Summonly and Vitae Plus for life", successPath: "/suite/success/" },
  // Custom bundles of the Mac Suite: pick any 2 for $34.99 or any 3 for $44.99, the same price whichever parts are
  // chosen (the eight parts are the seven apps and a lifetime Vitae Plus key; all eight is the Suite above). The client sends
  // only `apps`; the price is the table in netlify/lib/bundles.mjs. Delivery reuses /suite/success/ and the per-app
  // download functions, which read metadata.apps back. See docs/growth-briefs/custom-bundle-pricing-2026-10-11.md.
  "bundle-2":                { amount: BUNDLES["bundle-2"].cents, bundle: true, name: "Purplelink Mac Suite custom bundle (any 2)", successPath: "/suite/success/" },
  "bundle-3":                { amount: BUNDLES["bundle-3"].cents, bundle: true, name: "Purplelink Mac Suite custom bundle (any 3)", successPath: "/suite/success/" },
  // Vitae Plus: optional subscription for the free Vitae app ($2.99/month or
  // $23.99/year, 7-day trial). The success page asks vitae-license.mjs for a
  // signed key; the app refreshes it from the same function about monthly.
  // cancel_url below maps /vitae/plus/success/ back to /vitae/plus/.
  "vitae-plus-monthly": {
    envKey: "STRIPE_PRICE_VITAE_PLUS_MONTHLY",
    successPath: "/vitae/plus/success/",
    mode: "subscription",
    trialDays: 7,
  },
  "vitae-plus-annual": {
    envKey: "STRIPE_PRICE_VITAE_PLUS_ANNUAL",
    successPath: "/vitae/plus/success/",
    mode: "subscription",
    trialDays: 7,
  },
  // Spreadsheet templates (/sheets/). These carry their price inline
  // (`amount`, `name`) instead of an env-var Price id: Checkout builds the price
  // from price_data, so a new product needs no Stripe dashboard setup and the
  // price shown on the page and the one charged live side by side here.
  // Delivery: kit-download.mjs streams the .xlsx from the kit-files store.
  "sheet-submission": { amount: 1200, name: "Journal Submission & R&R Tracker (spreadsheet)", successPath: "/sheets/success/" },
  "sheet-tenure":     { amount: 1200, name: "Tenure & Promotion Dossier Tracker (spreadsheet)", successPath: "/sheets/success/" },
  "sheet-jobmarket":  { amount: 900,  name: "Academic Job Market Tracker (spreadsheet)", successPath: "/sheets/success/" },
  "sheet-grantpipeline": { amount: 1200, name: "Grant Pipeline & PI Effort Tracker (spreadsheet)", successPath: "/sheets/success/" },
  "sheet-reviewmatrix": { amount: 1400, name: "Systematic Review Screening Matrix (spreadsheet)", successPath: "/sheets/success/" },
  "sheet-bundle":     { amount: 3900, name: "Researcher Spreadsheet Bundle (six spreadsheets)", successPath: "/sheets/success/" },
  // Live-data sheets: yearly subscriptions whose feed live-sheet.mjs serves as
  // CSV for Google Sheets' IMPORTDATA or Excel's From Web. The setup page turns
  // the session into a private feed key.
  "live-scholar": { amount: 3900, name: "Live Citation Dashboard (yearly)", interval: "year", successPath: "/sheets/live/setup/", mode: "subscription", trialDays: 7 },
  "live-funding": { amount: 5900, name: "Live Funding Feed (yearly)", interval: "year", successPath: "/sheets/live/setup/", mode: "subscription", trialDays: 7 },
  // Photograph licenses (/photography/license/). The request carries `photo`
  // (a DSC_ stem from site/photography/hub-data.json); it is copied into the
  // session metadata so photo-download.mjs knows which original to stream.
  // Tiers are non-exclusive; terms are on the page and in the delivered
  // license text. The agencies' contributor terms are non-exclusive too, so
  // selling the same file here is allowed; price parity is not required.
  "photo-license-web":        { amount: 2900,  name: "Photograph license: web and social (one site)", successPath: "/photography/license/success/", photo: true },
  "photo-license-commercial": { amount: 7900,  name: "Photograph license: commercial (one business)", successPath: "/photography/license/success/", photo: true },
  "photo-license-extended":   { amount: 19900, name: "Photograph license: extended (print, editorial, products)", successPath: "/photography/license/success/", photo: true },
  // 2027 printable calendars (/photography/calendars/). PDFs in the photo-files store.
  "photo-calendar-iceland":         { amount: 700,  name: "2027 Iceland calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-japan":           { amount: 700,  name: "2027 Japan calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-switzerland":     { amount: 700,  name: "2027 Switzerland calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-european-cities": { amount: 700,  name: "2027 European Cities calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-arizona-desert":  { amount: 700,  name: "2027 Arizona Desert calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-hawaii":          { amount: 700,  name: "2027 Hawaii calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-best-of":         { amount: 700,  name: "2027 Best Of calendar (PDF)", successPath: "/photography/calendars/success/" },
  "photo-calendar-bundle":          { amount: 1900, name: "2027 calendars, all seven (PDF)", successPath: "/photography/calendars/success/" },
};

// A photo stem as hub-data.json names it: DSC_1326, DSC_6629-Edit, DSC_7559-Pano-Edit.
const PHOTO_RE = /^DSC_[A-Za-z0-9-]{1,40}$/;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function formEncode(params) {
  const parts = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
  }
  return parts.join("&");
}

// Channel attribution sent by analytics.js: how the buyer first and most
// recently arrived (campaign tags, referring site, a Google-ad-click flag,
// landing page, date, and t: the utm_content tag naming the one link, so the
// marketing hub can credit an order to a single placement). Untrusted and
// optional. Each field is clipped to a short safe charset; sales.mjs reads it
// back to report revenue by channel.
const ATTR_FIELDS = { s: 60, m: 40, c: 80, r: 80, l: 120, d: 10, t: 60 };
// Stripe allows 500 characters per metadata value. With every field at its cap
// the JSON would be a little over, so the landing path (the least useful field)
// is shortened first, then the campaign, until it fits.
const ATTR_MAX = 500;
function cleanTouch(t) {
  if (!t || typeof t !== "object") return null;
  const out = {};
  for (const [k, n] of Object.entries(ATTR_FIELDS)) {
    if (typeof t[k] !== "string") continue;
    const v = t[k].replace(/[^\w.\-:/ ]/g, "").slice(0, n);
    if (v) out[k] = v;
  }
  if (t.g === 1 || t.g === true) out.g = 1;
  if (!Object.keys(out).length) return "";
  for (const k of ["l", "c"]) {
    const over = JSON.stringify(out).length - ATTR_MAX;
    if (over > 0 && out[k]) out[k] = out[k].slice(0, Math.max(0, out[k].length - over));
    if (out[k] === "") delete out[k];
  }
  return JSON.stringify(out);
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const clientIp =
    request.headers.get("x-nf-client-connection-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown";

  if (await checkoutRateLimited(clientIp)) {
    return jsonResponse(429, { error: "rate_limited" });
  }

  let body;
  try {
    body = await request.json();
  } catch (_) {
    return jsonResponse(400, { error: "invalid_request" });
  }
  if (!body || typeof body !== "object" || Array.isArray(body) || typeof body.product !== "string" || !body.product) {
    return jsonResponse(400, { error: "invalid_request" });
  }
  const product = body.product;
  const entry = Object.hasOwn(PRODUCT_CATALOG, product) ? PRODUCT_CATALOG[product] : undefined;
  if (!entry) {
    return jsonResponse(400, { error: "unknown_product", detail: product });
  }
  // Referral code from a shared report's footer link (?ref=...), passed
  // through as Stripe metadata so stripe-webhook.mjs can forward it to
  // the backend's register-token endpoint. Untrusted input — just a short
  // opaque string, validated server-side against referral_dict, not used
  // for anything here.
  const referralCode = typeof body?.ref === "string" ? body.ref.trim().slice(0, 32) : "";
  const attrFirst = cleanTouch(body?.attr?.first);
  const attrLast = cleanTouch(body?.attr?.last);
  // ModernTex Buy page opened from the app's expired-trial screen: trial day and utm_source, as metadata.
  const trialDay = product === "moderntex" ? cleanTrialDay(body?.td) : "";
  const appSource = product === "moderntex" ? cleanAppSource(body?.src) : "";
  // Photograph licenses need the photo; anything else ignores it.
  const photo = entry.photo && typeof body?.photo === "string" && PHOTO_RE.test(body.photo) ? body.photo : "";
  if (entry.photo && !photo) {
    return jsonResponse(400, { error: "missing_photo", detail: "Choose a photograph first." });
  }

  // Seat packs: the count is the only thing the client chooses; the unit price comes from the table.
  let seats = 0;
  let seatUnit = 0;
  if (entry.seats) {
    seats = parseSeats(body.seats);
    const unit = seatUnitCents(seats);
    if (unit === null) {
      return jsonResponse(400, {
        error: "invalid_seats",
        detail: `Choose 5, 10, 15 or 20 seats, or any number from 25 to ${MAX_SEATS}. For one to four copies, buy ModernTex at $19.99 each.`,
      });
    }
    seatUnit = unit;
  }

  // Custom bundles: the count is fixed by the product, so the client must name exactly that many known parts.
  let bundleParts = [];
  if (entry.bundle) {
    bundleParts = parseBundleParts(body.apps, BUNDLES[product].count) || [];
    if (!bundleParts.length) {
      return jsonResponse(400, {
        error: "invalid_apps",
        detail: `Choose exactly ${BUNDLES[product].count} different parts of the Mac Suite.`,
      });
    }
  }

  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const priceId = entry.amount || entry.seats ? null : Netlify.env.get(entry.envKey);
  if (!secretKey || (!entry.amount && !entry.seats && !priceId)) {
    return jsonResponse(500, {
      error: "misconfigured",
      detail: `Set STRIPE_SECRET_KEY and ${entry.envKey} on this site.`,
    });
  }

  const requestOrigin = request.headers.get("origin");
  const origin = ALLOWED_ORIGINS.has(requestOrigin) ? requestOrigin : DEFAULT_ORIGIN;

  // Derive a stable Idempotency-Key from the buyer's client + the product
  // they're buying, bucketed into a short time window. A client retry (lost
  // response, timeout, double-click) for the same buyer+product within the
  // window reuses the same key, so Stripe returns the original Checkout
  // Session instead of creating a second, independently payable one. A
  // genuinely new purchase attempt after the window (or by a different
  // client) still gets a fresh session.
  // Pages that send a per-page-load `attempt` nonce (Vitae Plus) keep two buyers behind one
  // campus NAT apart; the referral code and attribution are included so
  // differing tags never collide (Stripe rejects a reused key with new params).
  const attempt = typeof body?.attempt === "string" && /^[A-Za-z0-9_-]{8,64}$/.test(body.attempt) ? body.attempt : "";
  // Stripe as merchant of record for this product (off unless STRIPE_MANAGED_PAYMENTS names it); see
  // netlify/lib/managed-payments.mjs. Part of the idempotency key, because Stripe rejects a reused key with new params.
  const managed = managedPaymentsOn(product, Netlify.env.get("STRIPE_MANAGED_PAYMENTS"));
  const timeBucket = Math.floor(Date.now() / IDEMPOTENCY_WINDOW_MS);
  const idempotencyKey = createHash("sha256")
    .update(`v6:${managed ? "mp:" : ""}${clientIp}:${product}:${timeBucket}:${attempt}:${referralCode}:${attrFirst}:${attrLast}:${trialDay}:${appSource}:${photo}:${seats}:${bundleParts.join("+")}`)
    .digest("hex");

  // Attach the product key as Stripe metadata so the webhook can route
  // correctly without re-deriving from price_id.
  const mode = entry.mode || "payment";
  const params = {
    mode,
    // Instant methods only. Card also carries Apple Pay and Google Pay; Link
    // is Stripe's saved-card wallet. Delayed methods (bank debits) would
    // complete with payment_status "unpaid", and stripe-webhook only delivers
    // on "paid" and never handles checkout.session.async_payment_succeeded.
    "payment_method_types[0]": "card",
    "payment_method_types[1]": "link",
    // Lets a buyer enter a promotion code created in the Stripe dashboard.
    allow_promotion_codes: "true",
    ...(entry.amount || entry.seats
      ? {
          "line_items[0][price_data][currency]": "usd",
          "line_items[0][price_data][unit_amount]": String(entry.seats ? seatUnit : entry.amount),
          "line_items[0][price_data][product_data][name]": photo ? `${entry.name}: ${photo}` : entry.bundle ? `${entry.name}: ${partsSentence(bundleParts)}` : entry.name,
          ...(entry.interval ? { "line_items[0][price_data][recurring][interval]": entry.interval } : {}),
        }
      : { "line_items[0][price]": priceId }),
    "line_items[0][quantity]": String(entry.seats ? seats : 1),
    success_url: `${origin}${entry.successPath}?session_id={CHECKOUT_SESSION_ID}`,
    // Strips the terminal path segment to send a canceled checkout back to
    // the product's own landing page instead of the paid confirmation page.
    // "subscribed" (digest-monthly/digest-annual's successPath is
    // /blog/digest/subscribed/) was missing until 2026-09-21: nothing matched,
    // so a canceled — unpaid — digest checkout landed on the "You're
    // subscribed" page.
    // ?checkout=canceled lets the page say plainly that nothing was charged.
    cancel_url: `${origin}${entry.successPath.replace(/\/(upload|compose|packs\/success|success|subscribed|setup)\/$/, "/")}?checkout=canceled`,
    "metadata[product]": product,
  };
  // customer_creation is only valid in "payment" mode -- Stripe always
  // creates a Customer automatically for "subscription" mode sessions, and
  // rejects the param outright if it's present there.
  if (mode === "payment") {
    params.customer_creation = "if_required";
  }
  // One optional question at checkout, so an order says how the buyer first
  // heard of us even when the browser record only says "from:trial" or nothing.
  // One-time purchases only (not photo licences); sales.mjs reads the answer
  // code back from the session. Stripe allows up to three fields per session.
  if (mode === "payment" && !photo) {
    params["custom_fields[0][key]"] = "heard";
    params["custom_fields[0][label][type]"] = "custom";
    params["custom_fields[0][label][custom]"] = "How did you first hear about us?";
    params["custom_fields[0][type]"] = "dropdown";
    params["custom_fields[0][optional]"] = "true";
    HEARD_OPTIONS.forEach(([label, value], i) => {
      params[`custom_fields[0][dropdown][options][${i}][label]`] = label;
      params[`custom_fields[0][dropdown][options][${i}][value]`] = value;
    });
  }
  if (mode === "payment" && !photo && ROLE_FIELD_PRODUCTS.has(product)) {
    [ROLE_FIELD, FIELD_FIELD].forEach((f, n) => {
      const i = n + 1;
      params[`custom_fields[${i}][key]`] = f.key;
      params[`custom_fields[${i}][label][type]`] = "custom";
      params[`custom_fields[${i}][label][custom]`] = f.label;
      params[`custom_fields[${i}][type]`] = "dropdown";
      params[`custom_fields[${i}][optional]`] = "true";
      f.options.forEach(([label, value], j) => {
        params[`custom_fields[${i}][dropdown][options][${j}][label]`] = label;
        params[`custom_fields[${i}][dropdown][options][${j}][value]`] = value;
      });
    });
  }
  if (REFUND_TEXT[product]) params["custom_text[submit][message]"] = REFUND_TEXT[product];
  if (entry.seats) params["metadata[seats]"] = String(seats);
  if (entry.bundle) params["metadata[apps]"] = bundleParts.join(",");
  if (referralCode) {
    params["metadata[referral_code]"] = referralCode;
  }
  if (photo) {
    params["metadata[photo]"] = photo;
  }
  if (trialDay) params["metadata[trial_day]"] = trialDay;
  if (appSource) params["metadata[app_source]"] = appSource;
  if (attrFirst) params["metadata[attr_first]"] = attrFirst;
  if (attrLast) params["metadata[attr_last]"] = attrLast;
  if (mode === "subscription") {
    // Copy the product key onto the Subscription too, so customer.subscription.*
    // events and the dashboard can tell a Vitae Plus subscription from a digest one.
    params["subscription_data[metadata][product]"] = product;
    if (attrFirst) params["subscription_data[metadata][attr_first]"] = attrFirst;
    if (attrLast) params["subscription_data[metadata][attr_last]"] = attrLast;
    if (entry.trialDays) {
      params["subscription_data[trial_period_days]"] = String(entry.trialDays);
    }
  }

  if (managed) applyManagedPayments(params, product);

  // Checkout recovery (netlify/lib/checkout-recovery.mjs): consent box plus a recovery link when the session
  // expires unpaid. If Stripe ever rejects those parameters, the session is created again without them, so the
  // experiment can never block a sale.
  const recovery = mode === "payment" ? recoveryParams(product) : {};
  const post = async (p, key) => {
    const r = await fetch(`${STRIPE_API}/checkout/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/x-www-form-urlencoded",
        "Idempotency-Key": key,
      },
      body: formEncode(p),
    });
    let d = null;
    try { d = await r.json(); } catch (_) { d = null; }
    return { resp: r, data: d };
  };

  let resp, data;
  try {
    ({ resp, data } = await post({ ...params, ...recovery }, idempotencyKey));
    if (!resp.ok && Object.keys(recovery).length && isRecoveryParamError(data)) {
      console.error("checkout: recovery parameters rejected, retrying without them:", data?.error?.param || data?.error?.code);
      ({ resp, data } = await post(params, `${idempotencyKey}:norecovery`));
    }
  } catch (err) {
    console.error("checkout: stripe request failed:", err?.name, err?.message);
    return jsonResponse(502, { error: "stripe_unreachable", detail: "Could not reach the payment processor. Try again in a minute." });
  }

  if (data === null) {
    return jsonResponse(502, { error: "stripe_bad_response" });
  }

  if (!resp.ok) {
    const detail =
      (data && data.error && (data.error.message || data.error.code)) ||
      "Stripe rejected the request.";
    return jsonResponse(502, { error: "stripe_error", detail });
  }

  if (!data.url) {
    return jsonResponse(502, { error: "no_redirect_url" });
  }

  return jsonResponse(200, { url: data.url, id: data.id, product });
}
