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
 *   set_reminder  {on}           (session) Turns the optional "your streak ends tonight" email on or off.
 *   remind_off    {acct,token}   (anonymous) The one-click unsubscribe link in that email.
 *   logout                       (session) Ends this session.
 *   delete_account               (session) Deletes the account, its progress and every session.
 *   score         {game,idx,score}   (anonymous) Adds one score to that day's histogram, returns the percentile.
 *   leaderboard   {game,board}       (anonymous; a session adds your own rank) The top 100 for "chess" or "sudoku",
 *                                    board "all" (rating) or "week" (rating gained this week). Only players who opted in appear.
 *   ratings                          (session) Your chess and Sudoku ratings and whether you are on the leaderboards.
 *   rating_report {game,id,result,ms,seed}  (session) One finished rated puzzle. The service checks it against the puzzle
 *                                    list, recomputes the Elo itself and returns the new rating. The browser never sends a rating.
 *   set_public    {on}               (session) Opt in or out of the leaderboards; needs a display name.
 *
 * A session is sent as `Authorization: Bearer <token>`. Tokens are 256-bit random values; only their SHA-256
 * is stored. The account key is the SHA-256 of the lowercased email. Progress is whitelisted and size-capped.
 * Env: RESEND_API_KEY (the key the order and recovery emails already use).
 */

import { createHash, randomBytes } from "node:crypto";
import { cleanData, cleanName, mergeData, percentile, dayIndexUTC, MAX_DATA_BYTES, SCORE_LIMITS } from "../lib/games-logic.mjs";
import { applyResult, boardRow, checkReport, DAILY_REPORT_CAP, SPORTS_GAMES, emptyRecord, publicNameOk, upsertRow, weekOf } from "../lib/ratings.mjs";
import CHESS_INDEX from "../lib/chess-index.json" with { type: "json" };
import SPORTS_DAYS from "../lib/sports-days.json" with { type: "json" };
import SPORTS_POOL from "../lib/sports-pool.json" with { type: "json" };

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

const RATED = ["chess", "sudoku", ...SPORTS_GAMES];

export function createHandler({ getStore, env, fetchFn = (...a) => fetch(...a), now = () => Date.now(), chessIndex = CHESS_INDEX, sportsDays = SPORTS_DAYS, sportsPool = SPORTS_POOL }) {
  const accounts = () => getStore("games-accounts");
  const auth = () => getStore("games-auth");
  const scores = () => getStore("games-scores");
  const limits = () => getStore("rate-limits");
  const ratings = () => getStore("games-ratings");
  const boards = () => getStore("games-lb");
  const weekNow = () => weekOf(dayIndexUTC(new Date(now())));

  async function loadRatings(acct) { return (await ratings().get(`r:${acct}`, { type: "json" })) || {}; }

  // Keep one account's rows on the public boards in step with its ratings, name and opt-in.
  async function syncBoards(acct, account, recs) {
    const wk = weekNow();
    for (const game of RATED) {
      for (const board of ["all", "week"]) {
        const key = `lb:${game}:${board}`;
        const cur = (await boards().get(key, { type: "json" })) || { rows: [] };
        let rows = board === "week" && cur.week !== wk ? [] : cur.rows;
        const rec = recs[game];
        if (account.public && rec && publicNameOk(account.name)) rows = upsertRow(rows, boardRow(game, rec, account.name, acct, board), board);
        else rows = rows.filter((x) => x.a !== acct);
        await boards().setJSON(key, { week: wk, rows });
      }
    }
  }

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
        const isNew = !account;
        if (!account) account = { email: rec.email, name: "", created: now(), data: {}, sessions: [] };
        const session = randomBytes(32).toString("hex");
        await auth().setJSON(`sess:${sha(session)}`, { acct, exp: now() + SESSION_TTL_MS });
        account.sessions = [...(account.sessions || []), sha(session)];
        while (account.sessions.length > MAX_SESSIONS) await auth().delete(`sess:${account.sessions.shift()}`);
        await accounts().setJSON(`acct:${acct}`, account);
        return json(200, { session, email: account.email, name: account.name, data: account.data, remind: !!account.remind, public: !!account.public, isNew }, origin);
      }

      if (action === "remind_off") {
        const acct = String(b.acct || ""), token = String(b.token || "");
        if (!/^[a-f0-9]{64}$/.test(acct) || !/^[a-f0-9]{32}$/.test(token)) return json(400, { error: "invalid_link" }, origin);
        const rec = await loadAccount(acct);
        if (!rec || rec.remindToken !== token) return json(400, { error: "invalid_link" }, origin);
        rec.remind = false;
        await accounts().setJSON(`acct:${acct}`, rec);
        return json(200, { ok: true }, origin);
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

      if (action === "leaderboard") {
        const game = String(b.game || ""), board = b.board === "week" ? "week" : "all";
        if (!RATED.includes(game)) return json(400, { error: "unknown_game" }, origin);
        const wk = weekNow();
        const cur = (await boards().get(`lb:${game}:${board}`, { type: "json" })) || { rows: [] };
        const rows = board === "week" && cur.week !== wk ? [] : cur.rows;
        const out = { board, game, rows: rows.slice(0, 100).map((x, i) => ({ rank: i + 1, name: x.name, r: x.r, n: x.n, g: x.g })) };
        const viewer = await sessionOf(request);
        if (viewer) {
          const at = rows.findIndex((x) => x.a === viewer.acct);
          if (at >= 0) out.you = { rank: at + 1, r: rows[at].r, g: rows[at].g };
        }
        return json(200, out, origin);
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
        return json(200, { data: merged, name: account.name, email: account.email, remind: !!account.remind, public: !!account.public }, origin);
      }
      if (action === "set_name") {
        const name = cleanName(b.name);
        if (!name) return json(400, { error: "invalid_name" }, origin);
        account.name = name;
        if (account.public && !publicNameOk(name)) account.public = false;
        await accounts().setJSON(`acct:${sess.acct}`, account);
        const recs = await loadRatings(sess.acct);
        if (account.public || RATED.some((g) => recs[g])) await syncBoards(sess.acct, account, recs);
        return json(200, { ok: true, name, public: !!account.public }, origin);
      }
      if (action === "set_reminder") {
        account.remind = !!b.on;
        if (!account.remindToken) account.remindToken = randomBytes(16).toString("hex");
        await accounts().setJSON(`acct:${sess.acct}`, account);
        return json(200, { ok: true, remind: account.remind }, origin);
      }
      if (action === "ratings") {
        const recs = await loadRatings(sess.acct);
        return json(200, { chess: recs.chess || null, sudoku: recs.sudoku || null, teamlink: recs.teamlink || null, gridlink: recs.gridlink || null, unbeaten: recs.unbeaten || null, public: !!account.public, name: account.name || "" }, origin);
      }
      if (action === "rating_report") {
        const game = String(b.game || "");
        const checked = checkReport(game, b, chessIndex, sportsDays, dayIndexUTC(new Date(now())), sportsPool);
        if (!checked.ok) return json(400, { error: checked.error }, origin);
        const recs = await loadRatings(sess.acct);
        let rec = recs[game];
        if (!rec) {
          rec = emptyRecord();
          const seed = b.seed && typeof b.seed === "object" ? b.seed : null;
          if (seed && Number.isFinite(seed.r)) { rec.r = rec.peak = rec.wr0 = Math.min(1500, Math.max(400, Math.round(seed.r))); rec.n = Math.min(40, Math.max(0, Math.trunc(Number(seed.n) || 0))); }
        }
        const rid = String(checked.id || b.id);
        if (rec.lastId === rid || (rec.ids || []).includes(rid)) return json(200, { r: rec.r, delta: 0, n: rec.n, streak: rec.streak, peak: rec.peak, repeat: true }, origin);
        const today = new Date(now()).toISOString().slice(0, 10);
        if (rec.day === today && rec.dn >= DAILY_REPORT_CAP) return json(429, { error: "daily_limit" }, origin);
        const out = applyResult(rec, { puzzleRating: checked.puzzleRating, score: checked.score, solved: checked.solved, dayIdx: dayIndexUTC(new Date(now())), dayKey: today });
        out.rec.lastId = rid;
        if (SPORTS_GAMES.includes(game)) out.rec.ids = [...(rec.ids || []), rid].slice(-40);       // one rated result per daily puzzle
        recs[game] = out.rec;
        await ratings().setJSON(`r:${sess.acct}`, recs);
        if (account.public) await syncBoards(sess.acct, account, recs);
        return json(200, { r: out.rec.r, delta: out.delta, n: out.rec.n, streak: out.rec.streak, peak: out.rec.peak, public: !!account.public }, origin);
      }
      if (action === "set_public") {
        const on = !!b.on;
        if (on && !publicNameOk(account.name)) return json(400, { error: "name_needed" }, origin);
        account.public = on;
        await accounts().setJSON(`acct:${sess.acct}`, account);
        await syncBoards(sess.acct, account, await loadRatings(sess.acct));
        return json(200, { ok: true, public: on }, origin);
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
        account.public = false;
        await syncBoards(sess.acct, account, {});
        await ratings().delete(`r:${sess.acct}`);
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
