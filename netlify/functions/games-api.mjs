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

 *   rank          {game?}            (session) Your all-time rank and percentile for wins (w), best streak (s) and average
 *                                    percentile (p) in one daily game, or in every game you have played.
 *   leaderboard   {game,board:"day",idx}  (anonymous; a session adds your own result) Who did best on one day's puzzle, among players who opted in.
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
import { cleanData, cleanName, mergeData, percentile, dayIndexUTC, MAX_DATA_BYTES, SCORE_LIMITS, COMPLETION_GAMES, RANK_KEYS, BOARD_KEYS, boardKey, metricsOf, bucketMove, rankOf, upsertValueRow, upsertDayRow, histGet, DAY_BOARD_SIZE } from "../lib/games-logic.mjs";
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
const SESSION_RENEW_AFTER_MS = 7 * 24 * 60 * 60 * 1000;
const MAX_SESSIONS = 8;
const PER_EMAIL_DAILY = 5;
const PER_IP_DAILY = 30;
const SCORE_SEEN_CAP = 4000;
const PER_IP_SCORES_DAILY = 2000;
const DAILY_BOARD_SIZE = 100;

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
  const ranks = () => getStore("games-rank");
  const weekNow = () => weekOf(dayIndexUTC(new Date(now())));

  async function loadRatings(acct) {
    const recs = (await ratings().get(`r:${acct}`, { type: "json" })) || {};
    for (const [old, now_] of [["teamlink", "lockerlink"], ["unbeaten", "under-the-cap"]]) if (recs[old] && !recs[now_]) { recs[now_] = recs[old]; delete recs[old]; }       // the sports games were launched as Teamlink and Unbeaten
    return recs;
  }

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

  // ---- all-time ranking for the daily games ----
  // `account.rk` holds the values this account is currently counted at in each game's histograms, so a sync moves
  // it from the old bucket to the new one instead of recounting anyone.
  const rkSame = (a, b) => !!a && !!b && RANK_KEYS.every((k) => (a[k] ?? null) === (b[k] ?? null));

  async function updateRanks(acct, account, data) {
    const today = dayIndexUTC(new Date(now()));
    const prev = account.rk || {}, next = {}, changed = [];
    for (const g of COMPLETION_GAMES) {
      const m = metricsOf(data[g], today);
      if (m) next[g] = m;
      if (rkSame(prev[g], m) || (!prev[g] && !m)) continue;
      changed.push(g);
      for (const k of RANK_KEYS) {
        const from = prev[g] ? (prev[g][k] ?? null) : null, to = m ? (m[k] ?? null) : null;
        if (from === to) continue;
        const key = `h:${g}:${k}`;
        const cur = (await ranks().get(key, { type: "json" })) || { buckets: {} };
        await ranks().setJSON(key, { buckets: bucketMove(cur.buckets, from, to) });
      }
    }
    account.rk = next;
    return changed;
  }

  // Keep this account's rows on the daily boards in step with its values, name and opt-in. `games` limits the work.
  async function syncDailyBoards(acct, account, games) {
    const listed = account.public && publicNameOk(account.name);
    for (const g of games) {
      const key = `lbd:${g}`;
      const cur = (await boards().get(key, { type: "json" })) || {};
      const m = account.rk && account.rk[g];
      const n = (account.data && account.data[g] && account.data[g].stats && account.data[g].stats.played) || 0;
      let touched = false;
      for (const [board, k] of Object.entries(BOARD_KEYS)) {
        const rows = cur[board] || [];
        const had = rows.some((x) => x.a === acct);
        if (listed && m && m[k] !== null && m[k] !== undefined && (m[k] > 0 || k === "p")) { cur[board] = upsertValueRow(rows, { a: acct, name: account.name, v: m[k], n }).slice(0, DAILY_BOARD_SIZE); touched = true; }
        else if (had) { cur[board] = rows.filter((x) => x.a !== acct); touched = true; }
      }
      if (touched) await boards().setJSON(key, cur);
    }
  }

  async function removeFromRanks(acct, account) {
    for (const [g, m] of Object.entries(account.rk || {})) {
      for (const k of RANK_KEYS) {
        if (m[k] === null || m[k] === undefined) continue;
        const key = `h:${g}:${k}`;
        const cur = (await ranks().get(key, { type: "json" })) || { buckets: {} };
        await ranks().setJSON(key, { buckets: bucketMove(cur.buckets, m[k], null) });
      }
    }
  }

  async function rankFor(account, g) {
    const m = account.rk && account.rk[g];
    if (!m) return null;
    const out = {};
    for (const [name, k] of [["w", "w"], ["s", "s"], ["p", "p"]]) {
      if (m[k] === null || m[k] === undefined) continue;
      const cur = (await ranks().get(`h:${g}:${k}`, { type: "json" })) || { buckets: {} };
      out[name] = { v: m[k], ...rankOf(cur.buckets, m[k]) };
    }
    return out;
  }


  // Overlapping syncs (two devices at once) can make a histogram count one account twice or miss it. This recomputes
  // every histogram and daily board from the accounts themselves, so drift never lasts longer than a week.
  async function rebuildRanks() {
    const today = dayIndexUTC(new Date(now()));
    const hists = {}, rows = {};
    let accountsSeen = 0, repaired = 0;
    const { blobs } = await accounts().list({ prefix: "acct:" });
    for (const { key } of blobs) {
      const account = await accounts().get(key, { type: "json" });
      if (!account) continue;
      accountsSeen++;
      const acct = key.slice(5), listed = account.public && publicNameOk(account.name), rk = {};
      for (const g of COMPLETION_GAMES) {
        const m = metricsOf((account.data || {})[g], today);
        if (!m) continue;
        rk[g] = m;
        for (const k of RANK_KEYS) if (m[k] !== null) { const h = (hists[`${g}:${k}`] ||= {}); h[m[k]] = (h[m[k]] || 0) + 1; }
        const n = account.data[g].stats.played;
        for (const [board, k] of Object.entries(BOARD_KEYS)) {
          if (listed && m[k] !== null && (m[k] > 0 || k === "p")) { const r = (rows[g] ||= {}); r[board] = upsertValueRow(r[board] || [], { a: acct, name: account.name, v: m[k], n }); }
        }
      }
      if (JSON.stringify(rk) !== JSON.stringify(account.rk || {})) { account.rk = rk; await accounts().setJSON(key, account); repaired++; }
    }
    for (const g of COMPLETION_GAMES) {
      for (const k of RANK_KEYS) {
        const buckets = hists[`${g}:${k}`];
        if (buckets) await ranks().setJSON(`h:${g}:${k}`, { buckets });
        else await ranks().delete(`h:${g}:${k}`);
      }
      if (rows[g]) await boards().setJSON(`lbd:${g}`, rows[g]); else await boards().delete(`lbd:${g}`);
    }
    return { accounts: accountsSeen, repaired };
  }

  // ---- the daily board: who did best on one day's puzzle ----
  // Rows come from each opted-in account's own day-by-day history, so a result shows up when the player's browser syncs.
  // A day's board lives under lbday:<game>:<puzzle number> and is dropped four days later.
  const dayKey = (g, idx) => `lbday:${g}:${idx}`;
  const lowerThan = (buckets, v) => Object.entries(buckets || {}).reduce((n, [k, c]) => n + (Number(k) < v ? c : 0), 0);
  async function syncDayRows(acct, account, games) {
    const today = dayIndexUTC(new Date(now()));
    const listed = !!account.public && publicNameOk(account.name);
    const days = listed ? [today - 1, today, today + 1] : [today - 3, today - 2, today - 1, today, today + 1];
    for (const g of games) {
      const hist = account.data && account.data[g] ? account.data[g].hist : null;
      for (const idx of days) {
        const v = listed ? histGet(hist, idx) : null;
        if (listed && v === null) continue;
        const cur = (await boards().get(dayKey(g, idx), { type: "json" })) || { rows: [] };
        if (v !== null) {
          await boards().setJSON(dayKey(g, idx), { rows: upsertDayRow(cur.rows || [], { a: acct, name: account.name, s: v }) });
          try { await boards().delete(dayKey(g, idx - 4)); } catch (_) { /* old boards expire on a later write */ }
        } else if ((cur.rows || []).some((x) => x.a === acct)) {
          await boards().setJSON(dayKey(g, idx), { rows: cur.rows.filter((x) => x.a !== acct) });
        }
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
    // A session in use keeps renewing, so a player who comes back every few weeks stays signed in on that device.
    if (rec.exp - now() < SESSION_TTL_MS - SESSION_RENEW_AFTER_MS) {
      try { await auth().setJSON(`sess:${sha(m[1])}`, { acct: rec.acct, exp: now() + SESSION_TTL_MS }); } catch (_) { /* renew next time */ }
    }
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
        if (!Object.hasOwn(SCORE_LIMITS, game) || !Number.isInteger(idx) || !Number.isInteger(score) || score < 0 || score > SCORE_LIMITS[game]) {
          return json(400, { error: "bad_score" }, origin);
        }
        if (Math.abs(idx - dayIndexUTC(new Date(now()))) > 1) return json(400, { error: "not_today" }, origin);
        if (await overLimit("score", clientIpOf(request), PER_IP_SCORES_DAILY)) return json(429, { error: "rate_limited" }, origin);
        // One result per person per puzzle. A signed-in player counts once by account, anyone else once by the random
        // id their browser made, so people sharing a connection are all counted. Without either, one per connection.
        const viewer = await sessionOf(request);
        const vid = /^[a-f0-9]{32}$/.test(String(b.vid || "")) ? String(b.vid) : "";
        const who = viewer ? `a:${viewer.acct}` : vid ? `v:${vid}` : `i:${clientIpOf(request)}`;
        const key = `score:${game}:${idx}`;
        const rec = (await scores().get(key, { type: "json" })) || { buckets: {}, seen: [] };
        const voter = sha(`${who}|${game}|${idx}`).slice(0, 12);
        if (!rec.seen.includes(voter)) {
          rec.buckets[score] = (rec.buckets[score] || 0) + 1;
          if (rec.seen.length < SCORE_SEEN_CAP) rec.seen.push(voter);
          await scores().setJSON(key, rec);
        }
        return json(200, percentile(rec.buckets, score), origin);
      }

      if (action === "leaderboard" && b.board === "day" && COMPLETION_GAMES.includes(String(b.game || ""))) {
        const game = String(b.game), idx = Number(b.idx), today = dayIndexUTC(new Date(now()));
        if (!Number.isInteger(idx) || Math.abs(idx - today) > 2) return json(400, { error: "not_recent" }, origin);
        const cur = (await boards().get(dayKey(game, idx), { type: "json" })) || { rows: [] };
        const hist = (await scores().get(`score:${game}:${idx}`, { type: "json" })) || { buckets: {} };
        const finishers = rankOf(hist.buckets, -1).total;
        const live = Object.keys(hist.buckets).map(Number).filter((k) => k < 99).sort((x, y) => x - y);
        const list = cur.rows || [];
        const viewer = await sessionOf(request);
        const out = {
          board: "day", game, idx, finishers, best: live.length ? { v: live[0], n: hist.buckets[live[0]] } : null,
          // A rank counts everyone who finished with a better result, named or not, so a row and the viewer's own line agree.
          rows: list.map((x) => ({ rank: 1 + Math.max(lowerThan(hist.buckets, x.s), list.filter((y) => y.s < x.s).length), name: x.name, v: x.s, ...(viewer && x.a === viewer.acct ? { me: true } : {}) })),
        };
        if (viewer) {
          const acc = await loadAccount(viewer.acct);
          const mine = acc && acc.data && acc.data[game] ? histGet(acc.data[game].hist, idx) : null;
          if (mine !== null && mine !== undefined) out.you = { v: mine, rank: 1 + Math.max(lowerThan(hist.buckets, mine), list.filter((y) => y.s < mine).length), total: finishers, listed: list.some((x) => x.a === viewer.acct) };
        }
        return json(200, out, origin);
      }

      if (action === "leaderboard" && boardKey(b.board) && COMPLETION_GAMES.includes(String(b.game || ""))) {
        const game = String(b.game), board = String(b.board), k = boardKey(board);
        const cur = (await boards().get(`lbd:${game}`, { type: "json" })) || {};
        const hist = (await ranks().get(`h:${game}:${k}`, { type: "json" })) || { buckets: {} };
        const viewer = await sessionOf(request);
        // Players tied on a value share a rank ("1, 1, 3"), the same rule the histogram uses for "you".
        const list = (cur[board] || []).slice(0, DAILY_BOARD_SIZE);
        const out = { board, game, total: rankOf(hist.buckets, 0).total, rows: list.map((x) => ({ rank: list.findIndex((y) => y.v === x.v) + 1, name: x.name, v: x.v, n: x.n, ...(viewer && x.a === viewer.acct ? { me: true } : {}) })) };
        if (viewer) {
          const acc = await loadAccount(viewer.acct);
          const v = acc && acc.rk && acc.rk[game] ? acc.rk[game][k] : null;
          if (v !== null && v !== undefined) out.you = { v, ...rankOf(hist.buckets, v), listed: (cur[board] || []).some((x) => x.a === viewer.acct) };
        }
        return json(200, out, origin);
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
        const legacy = (o) => { for (const [old, now_] of [["teamlink", "lockerlink"], ["unbeaten", "under-the-cap"]]) if (o && o[old] && !o[now_]) { o[now_] = o[old]; delete o[old]; } return o; };   // renamed games
        const incoming = cleanData(legacy(b.data));
        const before = legacy(account.data || {});
        const merged = mergeData(before, incoming);
        if (JSON.stringify(merged).length > MAX_DATA_BYTES) return json(413, { error: "too_large" }, origin);
        const histChanged = COMPLETION_GAMES.filter((g) => JSON.stringify((merged[g] || {}).hist || null) !== JSON.stringify((before[g] || {}).hist || null));
        account.data = merged;
        account.updated = now();
        const changed = await updateRanks(sess.acct, account, merged);
        await accounts().setJSON(`acct:${sess.acct}`, account);
        if (changed.length && account.public) await syncDailyBoards(sess.acct, account, changed);
        if (histChanged.length && account.public) await syncDayRows(sess.acct, account, histChanged);
        return json(200, { data: merged, rank: account.rk || {}, name: account.name, email: account.email, remind: !!account.remind, public: !!account.public }, origin);
      }
      if (action === "set_name") {
        const name = cleanName(b.name);
        if (!name) return json(400, { error: "invalid_name" }, origin);
        const wasPublic = !!account.public;
        account.name = name;
        if (account.public && !publicNameOk(name)) account.public = false;
        await accounts().setJSON(`acct:${sess.acct}`, account);
        const recs = await loadRatings(sess.acct);
        if (account.public || RATED.some((g) => recs[g])) await syncBoards(sess.acct, account, recs);
        if (wasPublic || account.public) { await syncDailyBoards(sess.acct, account, Object.keys(account.rk || {})); await syncDayRows(sess.acct, account, COMPLETION_GAMES.filter((g) => account.data && account.data[g] && account.data[g].hist)); }
        return json(200, { ok: true, name, public: !!account.public }, origin);
      }
      if (action === "rank") {
        const only = String(b.game || "");
        const list = only ? [only] : Object.keys(account.rk || {});
        const games = {};
        for (const g of list) { if (!COMPLETION_GAMES.includes(g)) continue; const r = await rankFor(account, g); if (r) games[g] = r; }
        return json(200, { games }, origin);
      }
      if (action === "set_reminder") {
        account.remind = !!b.on;
        if (!account.remindToken) account.remindToken = randomBytes(16).toString("hex");
        await accounts().setJSON(`acct:${sess.acct}`, account);
        return json(200, { ok: true, remind: account.remind }, origin);
      }
      if (action === "ratings") {
        const recs = await loadRatings(sess.acct);
        return json(200, { chess: recs.chess || null, sudoku: recs.sudoku || null, lockerlink: recs.lockerlink || null, gridlink: recs.gridlink || null, "under-the-cap": recs["under-the-cap"] || null, public: !!account.public, name: account.name || "" }, origin);
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
        await syncDailyBoards(sess.acct, account, Object.keys(account.rk || {}));
        await syncDayRows(sess.acct, account, COMPLETION_GAMES.filter((g) => account.data && account.data[g] && account.data[g].hist));
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
        await syncDailyBoards(sess.acct, account, Object.keys(account.rk || {}));
        await syncDayRows(sess.acct, account, COMPLETION_GAMES.filter((g) => account.data && account.data[g] && account.data[g].hist));
        await removeFromRanks(sess.acct, account);
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
  handler.rebuild = rebuildRanks;
  return handler;
}

export default async function (request) {
  const { getStore } = await import("@netlify/blobs");
  return createHandler({ getStore, env: (k) => Netlify.env.get(k) })(request);
}
