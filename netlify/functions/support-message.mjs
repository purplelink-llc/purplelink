/**
 * "Write to Ben": the support box on /support/ and the app pages. One message in,
 * one plain-text email to ben@purplelink.llc out, with Reply-To set to the visitor.
 *
 * POST /.netlify/functions/support-message
 *   body: { email, message, topic?, page?, website?, t }
 *     topic    allowlisted key (see TOPICS); only its label reaches the subject
 *     page     site path the form was on; path only, clipped
 *     website  honeypot, must be empty (a filled one is answered 204 and dropped)
 *     t        milliseconds between the form rendering and Send; under 3000 is refused
 *   204                                           sent
 *   400 { error, field }                          invalid_json | invalid_email | message_short |
 *                                                 message_long | invalid_topic | too_fast
 *   403 { error: "forbidden_origin" }             Origin header present and not this site
 *   405 { error: "method_not_allowed" }
 *   429 { error: "rate_limited" }                 per IP (5 an hour, 20 a day) or the daily cap
 *   502 { error: "send_failed" }                  Resend refused, or the limiter was unavailable
 *
 * Nothing is stored: the message and the address go to Resend and nowhere else. The only
 * Blobs writes are counters in the shared "rate-limits" store, keyed by a salted one-way
 * hash of the IP (never the address, never the text). Logs carry a status code only.
 *
 * The counters are read, add one, write, like the other limiters in this repo; Blobs here
 * has no atomic increment, so two requests in the same instant can count once. The caps
 * are a flood guard, not an exact meter. If the limiter cannot be read the request is
 * refused (502), so a Blobs outage cannot become an open mail relay; the page then shows
 * the mailto fallback.
 *
 * Env: RESEND_API_KEY (the key the order and recovery emails use), SIGNAL_SALT (optional,
 * the salt signal.mjs already uses for its IP hash).
 */

import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";

const SITE_ORIGIN = "https://purplelink.llc";
const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const TO_ADDRESS = "ben@purplelink.llc";

export const PER_IP_HOURLY = 5;
export const PER_IP_DAILY = 20;
export const GLOBAL_DAILY = 200;
export const MIN_FILL_MS = 3000;
export const MIN_MESSAGE = 10;
export const MAX_MESSAGE = 5000;
const MAX_BODY_CHARS = 20000;

export const TOPICS = {
  general: "General",
  moderntex: "ModernTex",
  "outbound-veil": "Outbound Veil",
  legroom: "Legroom",
  keyfeel: "Keyfeel",
  tapefolio: "Tapefolio",
  panely: "Panely",
  summonly: "Summonly",
  vitae: "Vitae",
  batterymeter: "BatteryMeter",
  haea: "haea",
  "paper-review": "Paper Review",
  refund: "Refund",
  bug: "Bug report",
};

const EMAIL_PATTERN = /^[^\s@<>(),;:"\\[\]]{1,64}@[^\s@<>(),;:"\\[\]]{1,190}\.[^\s@<>(),;:"\\[\]]{2,}$/;
// Every control character except tab and newline, plus the Unicode line and paragraph separators.
// eslint-disable-next-line no-control-regex
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u2028\u2029]/g;

function allowedOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return SITE_ORIGIN; // curl and some same-origin posts send none
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  // A deploy preview posts from its own address.
  const preview = [Netlify.env.get("DEPLOY_PRIME_URL"), Netlify.env.get("DEPLOY_URL")];
  return preview.includes(origin) ? origin : null;
}

function json(status, body, origin = SITE_ORIGIN) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": origin,
      "Vary": "Origin",
      "Cache-Control": "no-store",
    },
  });
}

function fail(code, field, origin) {
  return json(400, { error: code, field }, origin);
}

function clientIpOf(request) {
  const forwarded = request.headers.get("x-forwarded-for");
  return request.headers.get("x-nf-client-connection-ip") || (forwarded ? forwarded.split(",")[0].trim() : "") || "unknown";
}

/** The page the form was on: a site path only, no query string, no fragment. */
function sourcePath(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) return "";
  return value.split(/[?#]/)[0].replace(/[^\w\-./]/g, "").slice(0, 120);
}

function cleanMessage(value) {
  return value.replace(/\r\n?/g, "\n").replace(CONTROL, "").replace(/\n{4,}/g, "\n\n\n").trim();
}

/**
 * Count this request against the per-IP hour, per-IP day and global day counters.
 * Returns true when any is full. Nothing is counted once one of them says no.
 */
async function overLimit(ip) {
  const now = new Date();
  const day = now.toISOString().slice(0, 10);
  const hour = now.toISOString().slice(0, 13);
  const salt = Netlify.env.get("SIGNAL_SALT") || "pl-signal";
  const digest = createHash("sha256").update(`${day}|${salt}|${ip}`).digest("hex").slice(0, 16);
  const store = getStore("rate-limits");
  const keys = {
    hour: `rl:support-hour:${hour}:${digest}`,
    day: `rl:support-day:${day}:${digest}`,
    all: `rl:support-all:${day}`,
  };
  const read = async (key) => parseInt((await store.get(key)) || "0", 10) || 0;
  const [h, d, a] = [await read(keys.hour), await read(keys.day), await read(keys.all)];
  if (h >= PER_IP_HOURLY || d >= PER_IP_DAILY || a >= GLOBAL_DAILY) return true;
  await store.set(keys.hour, String(h + 1));
  await store.set(keys.day, String(d + 1));
  await store.set(keys.all, String(a + 1));
  return false;
}

/** Plain text only. The visitor's words sit in the body; the subject carries just the topic label. */
function buildMail({ email, message, topic, page }) {
  const lines = [
    `From: ${email}`,
    `Topic: ${TOPICS[topic]}`,
    ...(page ? [`Page: ${page}`] : []),
    "",
    message,
    "",
    "--",
    "Sent from the support box on purplelink.llc. Reply to this email to answer the sender.",
  ];
  return {
    from: FROM_ADDRESS,
    to: [TO_ADDRESS],
    reply_to: email,
    subject: `Support: ${TOPICS[topic]}`,
    text: lines.join("\n"),
  };
}

async function send(mail) {
  const apiKey = Netlify.env.get("RESEND_API_KEY");
  if (!apiKey) return "no_api_key";
  try {
    const resp = await fetch(RESEND_API_URL, {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(mail),
    });
    return resp.ok ? null : `resend_${resp.status}`;
  } catch (_) {
    return "network";
  }
}

export default async function handler(request) {
  const origin = allowedOrigin(request);
  if (request.method === "OPTIONS") {
    if (!origin) return new Response(null, { status: 403 });
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
      },
    });
  }
  if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
  if (!origin) return json(403, { error: "forbidden_origin" });

  let body = null;
  try {
    const raw = await request.text();
    if (raw.length > MAX_BODY_CHARS) return fail("message_long", "message", origin);
    body = JSON.parse(raw);
  } catch (_) {
    body = null;
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return fail("invalid_json", "form", origin);

  // Honeypot: a filled "website" field is a bot. Answer as if it worked; send nothing.
  if (typeof body.website === "string" && body.website.trim()) return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });

  const elapsed = body.t;
  if (typeof elapsed !== "number" || !Number.isFinite(elapsed) || elapsed < MIN_FILL_MS) return fail("too_fast", "form", origin);

  const email = typeof body.email === "string" ? body.email.trim() : "";
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return fail("invalid_email", "email", origin);

  const topic = body.topic === undefined || body.topic === "" ? "general" : body.topic;
  if (typeof topic !== "string" || !Object.hasOwn(TOPICS, topic)) return fail("invalid_topic", "topic", origin);

  if (typeof body.message !== "string") return fail("message_short", "message", origin);
  const message = cleanMessage(body.message);
  if (message.length < MIN_MESSAGE) return fail("message_short", "message", origin);
  if (message.length > MAX_MESSAGE) return fail("message_long", "message", origin);

  try {
    if (await overLimit(clientIpOf(request))) return json(429, { error: "rate_limited" }, origin);
  } catch (_) {
    console.error("support-message: limiter unavailable");
    return json(502, { error: "send_failed" }, origin);
  }

  const failure = await send(buildMail({ email, message, topic, page: sourcePath(body.page) }));
  if (failure) {
    console.error("support-message: send failed", failure);
    return json(502, { error: "send_failed" }, origin);
  }
  return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": origin, "Vary": "Origin", "Cache-Control": "no-store" } });
}
