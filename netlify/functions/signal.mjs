/**
 * Netlify Function: count-only answers (signal).
 *
 * POST /.netlify/functions/signal
 *   body: { kind: "whynot" | "trialpoll", value: <allowlisted for that kind>, td?: 0..30 | "unknown" }
 *   whynot values:   price, feature, other-tool, deciding, other
 *   trialpoll values: paper, thesis, coauthors, replace-overleaf, course-notes, looking, other
 *
 * Stores ONLY aggregate counters in the "signals" Netlify Blobs store, keyed by ISO week + kind + value (+ a trial-day
 * bucket "0-3", "4-7", "8+" or "unknown" for whynot). No IP, user agent, timestamp or identifier is stored. The only
 * per-sender value is a salted hash of the IP in the shared "rate-limits" store, keyed by day, to cap answers per
 * address per day; the address itself is never written.
 *
 * Responses: 204 counted (also for bots, which are not counted), 400 bad kind, value, td or JSON, 405 not POST,
 * 413 body over 2 KB, 429 over the daily limit. Read the counts with stats.mjs?section=signals (owner token).
 *
 * The counter update is read, add one, write, like the other counters in this repo; Blobs in this client version has no
 * atomic increment. Two answers landing in the same millisecond can count once; at a few answers a week that is
 * negligible, and the rate limit keeps one sender from skewing a bucket.
 */
import { getStore } from "@netlify/blobs";
import { createHash } from "node:crypto";
import { ALLOWLIST, parseTd, tdBucket, isoWeek, counterKey } from "../lib/signals.mjs";

export const MAX_BODY_BYTES = 2048;
export const DAILY_LIMIT = 10;
const BOT_RE = /bot|spider|crawl|slurp|bingpreview|headless|lighthouse|preview|facebookexternalhit|embedly/i;

function res(status) {
  return new Response(status === 204 ? null : JSON.stringify({ error: status }), {
    status,
    headers: status === 204 ? {} : { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

export default async function handler(request) {
  if (request.method !== "POST") return res(405);

  const declared = parseInt(request.headers.get("content-length") || "0", 10);
  if (declared > MAX_BODY_BYTES) return res(413);
  let b;
  try {
    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) return res(413);
    b = JSON.parse(raw);
  } catch (_) {
    return res(400);
  }
  if (!b || typeof b !== "object" || Array.isArray(b)) return res(400);

  const kind = b.kind;
  if (typeof kind !== "string" || !Object.hasOwn(ALLOWLIST, kind)) return res(400);
  if (typeof b.value !== "string" || !ALLOWLIST[kind].includes(b.value)) return res(400);
  const td = parseTd(b.td);
  if (td === "bad") return res(400);

  if (BOT_RE.test(request.headers.get("user-agent") || "")) return res(204);

  const ip = request.headers.get("x-nf-client-connection-ip") || request.headers.get("x-forwarded-for") || "unknown";
  const day = new Date().toISOString().slice(0, 10);
  try {
    const salt = Netlify.env.get("SIGNAL_SALT") || "pl-signal";
    const rl = getStore("rate-limits");
    const key = `rl:signal:${day}:${createHash("sha256").update(`${day}|${salt}|${ip}`).digest("hex").slice(0, 16)}`;
    const count = parseInt((await rl.get(key)) || "0", 10) || 0;
    if (count >= DAILY_LIMIT) return res(429);
    await rl.set(key, String(count + 1));
  } catch (_) { /* limiter unavailable: count the answer */ }

  try {
    const store = getStore("signals");
    const key = counterKey(isoWeek(), kind, b.value, kind === "whynot" ? tdBucket(td) : "");
    const n = parseInt((await store.get(key)) || "0", 10) || 0;
    await store.set(key, String(n + 1));
  } catch (_) { /* never surface a storage hiccup to the visitor */ }
  return res(204);
}
