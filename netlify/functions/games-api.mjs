/**
 * Netlify Function: accounts, sync and anonymous percentiles for /games/.
 *
 * POST /.netlify/functions/games-api   body: { action, ... }   (JSON)
 *
 *   login_request {email}        Emails a one-time sign-in link (15 minutes). Always answers { ok: true }
 *                                for a well-formed address, so it cannot be used to probe who has an account.
 *   login_verify  {token}        Spends the link, creates the account on first use, returns a session.
 *   sync          {data}         (session) Merges the browser's saved progress with the account's and returns the result.
 *   set_name      {name}         (session) Display name, 2 to 24 characters.
 *   logout                       (session) Ends this session.
 *   delete_account               (session) Deletes the account, its progress and every session.
 *   score         {game,idx,score}   (anonymous) Adds one score to that day's histogram, returns the percentile.
 *
 * A session is sent as `Authorization: Bearer <token>`. Tokens are 256-bit random values; only their SHA-256
 * is stored. The account key is the SHA-256 of the lowercased email. Progress is whitelisted and size-capped.
 * Env: RESEND_API_KEY (the key the order and recovery emails already use).
 */

import { createHash, randomBytes } from "node:crypto";
import { cleanData, cleanName, mergeData, percentile, dayIndexUTC, MAX_DATA_BYTES, SCORE_LIMITS } from "../lib/games-logic.mjs";

const SITE_ORIGIN = "https://purplelink.llc";
const ALLOWED_ORIGINS = new Set([SITE_ORIGIN, "https://www.purplelink.llc"]);
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
const LOGIN_TTL_MS = 15 * 60 * 1000;
const SESSION_TTL_MS = 90 * 24 * 60 * 60 * 1000;
const MAX_SESSIONS = 8;
const PER_EMAIL_DAILY = 5;
const PER_IP_DAILY = 30;
const SCORE_SEEN_CAP = 4000;

const sha = (s) => createHash("sha256").update(s).digest("hex");
const clientIpOf = (r) => r.headers.get("x-nf-client-connection-ip") || r.headers.get("x-forwarded-for") || "unknown";

function allowedOrigin(request, env) {
  const origin = request.headers.get("origin");
  if (!origin) return SITE_ORIGIN;
  if (ALLOWED_ORIGINS.has(origin)) return origin;
  return [env("DEPLOY_PRIME_URL"), env("DEPLOY_URL"), env("GAMES_DEV_ORIGIN")].includes(origin) ? origin : null;
}

function json(status, body, origin = SITE_ORIGIN) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": origin, Vary: "Origin", "Cache-Control": "no-store" },
  });
}

async function sendLoginEmail(to, link, env, fetchFn) {
  const apiKey = env("RESEND_API_KEY");
  if (!apiKey) return "no_api_key";
  const mail = {
    from: FROM_ADDRESS, reply_to: REPLY_TO, to: [to],
    subject: "Your Purplelink games sign-in link",
    text: `Use this link to sign in to Purplelink Games. It works once and expires in 15 minutes:\n\n${link}\n\n` +
      `If you did not ask for it, ignore this email and nothing happens.\n\nPurplelink LLC, Atlanta, Georgia`,
    html: `<p>Use this link to sign in to Purplelink Games. It works once and expires in 15 minutes:</p>` +
      `<p><a href="${link}">Sign in to Purplelink Games</a></p>` +
      `<p>If you did not ask for it, ignore this email and nothing happens.</p><p>Purplelink LLC, Atlanta, Georgia</p>`,
  };
  try {
    const resp = await fetchFn(RESEND_API_URL, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` }, body: JSON.stringify(mail) });
    return resp.ok ? null : `resend_${resp.status}`;
  } catch (_) {
    return "resend_unreachable";
  }
}

export function createHandler({ getStore, env, fetchFn = (...a) => fetch(...a), now = () => Date.now() }) {
  const accounts = () => getStore("games-accounts");
  const auth = () => getStore("games-auth");
  const scores = () => getStore("games-scores");
  const limits = () => getStore("rate-limits");

  async function overLimit(kind, value, limit) {
    const day = new Date(now()).toISOString().slice(0, 10);
    const key = `rl:games-${kind}:${day}:${sha(value).slice(0, 16)}`;
    const store = limits();
    const current = parseInt((await store.get(key)) || "0", 10) || 0;
    if (current >= limit) return true;
    await store.set(key, String(current + 1));
    return false;
  }

  async function sessionOf(request) {
    const m = /^Bearer ([a-f0-9]{64})$/.exec(request.headers.get("authorization") || "");
    if (!m) return null;
    const rec = await auth().get(`sess:${sha(m[1])}`, { type: "json" });
    if (!rec || rec.exp < now()) return null;
    return { hash: sha(m[1]), acct: rec.acct };
  }

  async function loadAccount(acct) {
    return (await accounts().get(`acct:${acct}`, { type: "json" })) || null;
  }

  async function handler(request) {
    const origin = allowedOrigin(request, env);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": origin || SITE_ORIGIN, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, Authorization", Vary: "Origin" } });
    }
    if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
    if (!origin) return json(403, { error: "forbidden_origin" });
    let b;
    try { b = await request.json(); } catch (_) { return json(400, { error: "bad_json" }, origin); }
    const action = String(b.action || "");

    try {
      if (action === "login_request") {
        const email = String(b.email || "").trim().toLowerCase();
        if (!EMAIL_PATTERN.test(email)) return json(400, { error: "invalid_email" }, origin);
        if ((await overLimit("email", email, PER_EMAIL_DAILY)) || (await overLimit("ip", clientIpOf(request), PER_IP_DAILY))) {
          return json(429, { error: "too_many_requests" }, origin);
        }
        const token = randomBytes(24).toString("hex");
        await auth().setJSON(`login:${sha(token)}`, { email, exp: now() + LOGIN_TTL_MS });
        const base = origin === SITE_ORIGIN || origin === "https://www.purplelink.llc" ? SITE_ORIGIN : origin;
        const err = await sendLoginEmail(email, `${base}/games/account/?t=${token}`, env, fetchFn);
        if (err) return json(502, { error: "send_failed" }, origin);
        return json(200, { ok: true }, origin);
      }

      if (action === "login_verify") {
        const token = String(b.token || "");
        if (!/^[a-f0-9]{48}$/.test(token)) return json(400, { error: "invalid_token" }, origin);
        const key = `login:${sha(token)}`;
        const rec = await auth().get(key, { type: "json" });
        if (!rec || rec.exp < now()) return json(400, { error: "expired_or_used" }, origin);
        await auth().delete(key);
        const acct = sha(rec.email);
        let account = await loadAccount(acct);
        if (!account) account = { email: rec.email, name: "", created: now(), data: {}, sessions: [] };
        const session = randomBytes(32).toString("hex");
        await auth().setJSON(`sess:${sha(session)}`, { acct, exp: now() + SESSION_TTL_MS });
        account.sessions = [...(account.sessions || []), sha(session)];
        while (account.sessions.length > MAX_SESSIONS) await auth().delete(`sess:${account.sessions.shift()}`);
        await accounts().setJSON(`acct:${acct}`, account);
        return json(200, { session, email: account.email, name: account.name, data: account.data }, origin);
      }

      if (action === "score") {
        const game = String(b.game || "");
        const idx = Number(b.idx), score = Number(b.score);
        if (!(game in SCORE_LIMITS) || !Number.isInteger(idx) || !Number.isInteger(score) || score < 0 || score > SCORE_LIMITS[game]) {
          return json(400, { error: "bad_score" }, origin);
        }
        if (Math.abs(idx - dayIndexUTC(new Date(now()))) > 1) return json(400, { error: "not_today" }, origin);
        const key = `score:${game}:${idx}`;
        const rec = (await scores().get(key, { type: "json" })) || { buckets: {}, seen: [] };
        const voter = sha(`${clientIpOf(request)}|${game}|${idx}`).slice(0, 12);
        if (!rec.seen.includes(voter)) {
          rec.buckets[score] = (rec.buckets[score] || 0) + 1;
          if (rec.seen.length < SCORE_SEEN_CAP) rec.seen.push(voter);
          await scores().setJSON(key, rec);
        }
        return json(200, percentile(rec.buckets, score), origin);
      }

      // everything below needs a session
      const sess = await sessionOf(request);
      if (!sess) return json(401, { error: "not_signed_in" }, origin);
      const account = await loadAccount(sess.acct);
      if (!account) return json(401, { error: "not_signed_in" }, origin);

      if (action === "sync") {
        const incoming = cleanData(b.data);
        const merged = mergeData(account.data || {}, incoming);
        if (JSON.stringify(merged).length > MAX_DATA_BYTES) return json(413, { error: "too_large" }, origin);
        account.data = merged;
        account.updated = now();
        await accounts().setJSON(`acct:${sess.acct}`, account);
        return json(200, { data: merged, name: account.name, email: account.email }, origin);
      }
      if (action === "set_name") {
        const name = cleanName(b.name);
        if (!name) return json(400, { error: "invalid_name" }, origin);
        account.name = name;
        await accounts().setJSON(`acct:${sess.acct}`, account);
        return json(200, { ok: true, name }, origin);
      }
      if (action === "logout") {
        await auth().delete(`sess:${sess.hash}`);
        account.sessions = (account.sessions || []).filter((h) => h !== sess.hash);
        await accounts().setJSON(`acct:${sess.acct}`, account);
        return json(200, { ok: true }, origin);
      }
      if (action === "delete_account") {
        for (const h of account.sessions || []) await auth().delete(`sess:${h}`);
        await auth().delete(`sess:${sess.hash}`);
        await accounts().delete(`acct:${sess.acct}`);
        return json(200, { ok: true }, origin);
      }
      return json(400, { error: "unknown_action" }, origin);
    } catch (_) {
      return json(500, { error: "server_error" }, origin);
    }
  }
  return handler;
}

export default async function (request) {
  const { getStore } = await import("@netlify/blobs");
  return createHandler({ getStore, env: (k) => Netlify.env.get(k) })(request);
}
