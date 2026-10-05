// Tests for games-api.mjs and games-logic.mjs. Blobs and Resend are in-memory stand-ins.
// Run with: node --test netlify/tests/games-api.test.mjs

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHandler } from "../functions/games-api.mjs";
import { mergeData, cleanData, percentile, cleanName, dayIndexUTC } from "../lib/games-logic.mjs";

function memoryStores() {
  const data = new Map(), calls = [];
  return {
    getStore: (opt) => { const name = typeof opt === "string" ? opt : opt.name; calls.push(opt); return {
      get: async (k, opts) => { const v = data.get(`${name}/${k}`); return v === undefined ? null : opts?.type === "json" ? JSON.parse(v) : v; },
      set: async (k, v) => { data.set(`${name}/${k}`, String(v)); },
      setJSON: async (k, v) => { data.set(`${name}/${k}`, JSON.stringify(v)); },
      delete: async (k) => { data.delete(`${name}/${k}`); },
      list: async ({ prefix = "" } = {}) => ({ blobs: [...data.keys()].filter((k) => k.startsWith(`${name}/${prefix}`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
    }; },
    data, calls,
  };
}

let stores, mails, clock, handler;
beforeEach(() => {
  stores = memoryStores();
  mails = [];
  clock = Date.UTC(2026, 9, 6, 12);
  const env = (k) => ({ RESEND_API_KEY: "re_test" })[k];
  const fetchFn = async (url, opts) => { mails.push(JSON.parse(opts.body)); return new Response("{}", { status: 200 }); };
  handler = createHandler({ getStore: stores.getStore, env, fetchFn, now: () => clock });
});

const call = (body, headers = {}) =>
  handler(new Request("https://purplelink.llc/.netlify/functions/games-api", {
    method: "POST", headers: { "content-type": "application/json", "x-nf-client-connection-ip": "1.2.3.4", ...headers }, body: JSON.stringify(body),
  }));
const tokenFromMail = () => /t=([a-f0-9]{48})/.exec(mails.at(-1).text)[1];
async function signIn(email = "a@example.com") {
  assert.equal((await call({ action: "login_request", email })).status, 200);
  const r = await call({ action: "login_verify", token: tokenFromMail() });
  assert.equal(r.status, 200);
  return (await r.json()).session;
}
const bearer = (s) => ({ authorization: `Bearer ${s}` });

test("login link is emailed, works once, and creates a session", async () => {
  const session = await signIn();
  assert.match(session, /^[a-f0-9]{64}$/);
  assert.match(mails[0].text, /https:\/\/purplelink\.llc\/games\/account\/\?t=/);
  const again = await call({ action: "login_verify", token: tokenFromMail() });
  assert.equal(again.status, 400);
});

test("an expired link is refused", async () => {
  await call({ action: "login_request", email: "a@example.com" });
  clock += 16 * 60 * 1000;
  assert.equal((await call({ action: "login_verify", token: tokenFromMail() })).status, 400);
});

test("bad addresses and a flood of requests are refused", async () => {
  assert.equal((await call({ action: "login_request", email: "nope" })).status, 400);
  for (let i = 0; i < 5; i++) assert.equal((await call({ action: "login_request", email: "b@example.com" })).status, 200);
  assert.equal((await call({ action: "login_request", email: "b@example.com" })).status, 429);
});

test("only the site's own origin may call it", async () => {
  const r = await call({ action: "login_request", email: "a@example.com" }, { origin: "https://evil.example" });
  assert.equal(r.status, 403);
});

test("sync merges progress from two devices and never loses any", async () => {
  const s = await signIn();
  const phone = { linkle: { stats: { played: 3, won: 3, streak: 3, max: 3, last: 3, dist: { 3: 3 }, wins: [1, 2, 3] } } };
  const laptop = { linkle: { stats: { played: 2, won: 2, streak: 1, max: 1, last: 5, dist: { 4: 2 }, wins: [4, 5] } }, ach: { "first-link": 4 } };
  await call({ action: "sync", data: phone }, bearer(s));
  const r = await call({ action: "sync", data: laptop }, bearer(s));
  const { data } = await r.json();
  assert.deepEqual(data.linkle.stats.wins, [1, 2, 3, 4, 5]);
  assert.equal(data.linkle.stats.streak, 5);
  assert.equal(data.linkle.stats.max, 5);
  assert.equal(data.ach["first-link"], 4);
});

test("sync, name and delete need a session", async () => {
  for (const action of ["sync", "set_name", "delete_account", "logout"]) {
    assert.equal((await call({ action })).status, 401);
    assert.equal((await call({ action }, bearer("0".repeat(64)))).status, 401);
  }
});

test("names are checked", async () => {
  const s = await signIn();
  assert.equal((await call({ action: "set_name", name: "<script>" }, bearer(s))).status, 400);
  assert.equal((await call({ action: "set_name", name: "a" }, bearer(s))).status, 400);
  const ok = await call({ action: "set_name", name: "Ada L." }, bearer(s));
  assert.equal((await ok.json()).name, "Ada L.");
});

test("delete_account removes the account and every session", async () => {
  const s1 = await signIn();
  const s2 = await signIn();
  assert.equal((await call({ action: "delete_account" }, bearer(s1))).status, 200);
  assert.equal((await call({ action: "sync", data: {} }, bearer(s1))).status, 401);
  assert.equal((await call({ action: "sync", data: {} }, bearer(s2))).status, 401);
  assert.equal([...stores.data.keys()].filter((k) => k.startsWith("games-accounts/")).length, 0);
});

test("logout ends only that session", async () => {
  const s1 = await signIn();
  const s2 = await signIn();
  await call({ action: "logout" }, bearer(s1));
  assert.equal((await call({ action: "sync", data: {} }, bearer(s1))).status, 401);
  assert.equal((await call({ action: "sync", data: {} }, bearer(s2))).status, 200);
});

test("scores: percentile from the day's histogram, one vote per visitor", async () => {
  const idx = dayIndexUTC(new Date(clock));
  const vote = (score, ip) => call({ action: "score", game: "linkle", idx, score }, { "x-nf-client-connection-ip": ip });
  await vote(3, "10.0.0.1"); await vote(4, "10.0.0.2"); await vote(4, "10.0.0.3"); await vote(99, "10.0.0.4");
  const r = await (await vote(3, "10.0.0.5")).json();
  assert.equal(r.total, 5);
  assert.equal(r.worse, 3);     // two 4s and the loss
  assert.equal(r.same, 2);
  assert.equal(r.percentile, 80);
  const dup = await (await vote(3, "10.0.0.5")).json();   // same visitor again: not counted
  assert.equal(dup.total, 5);
});

test("scores: bad input and wrong days are refused", async () => {
  const idx = dayIndexUTC(new Date(clock));
  assert.equal((await call({ action: "score", game: "nope", idx, score: 1 })).status, 400);
  assert.equal((await call({ action: "score", game: "linkle", idx, score: -1 })).status, 400);
  assert.equal((await call({ action: "score", game: "daily-five", idx, score: 9 })).status, 400);
  assert.equal((await call({ action: "score", game: "linkle", idx: idx + 40, score: 3 })).status, 400);
});

test("cleanData drops unknown keys and bounds values", () => {
  const d = cleanData({ evil: 1, linkle: { stats: { played: -5, won: 1e12, wins: [1, 1, "x"], dist: { 3: 2, bad: 9 } }, extra: "x" }, ach: { "ok-id": 3, "BAD ID": 1 } });
  assert.equal(d.evil, undefined);
  assert.equal(d.linkle.extra, undefined);
  assert.equal(d.linkle.stats.played, 0);
  assert.equal(d.linkle.stats.won, 1e7);
  assert.deepEqual(d.linkle.stats.dist, { 3: 2 });
  assert.deepEqual(d.ach, { "ok-id": 3 });
});

test("mergeData: today's finished game wins, crossword best time takes the minimum", () => {
  const a = { linkle: { today: { idx: 5, done: false, guesses: ["crane"] } }, crossword: { best: { Monday: 300 } } };
  const b = { linkle: { today: { idx: 5, done: true, won: true, guesses: ["crane", "slate"] } }, crossword: { best: { Monday: 240, Tuesday: 500 } } };
  const m = mergeData(a, b);
  assert.equal(m.linkle.today.done, true);
  assert.deepEqual(m.crossword.best, { Monday: 240, Tuesday: 500 });
});

test("percentile and cleanName basics", () => {
  assert.deepEqual(percentile({}, 3), { total: 0, worse: 0, same: 0, percentile: 0 });
  assert.equal(cleanName("  Grace   Hopper "), "Grace Hopper");
  assert.equal(cleanName("x".repeat(30)), null);
});

// ---- streak reminder ----
import { createReminder, reminderMail } from "../functions/games-reminder.mjs";
import { streakAtRisk } from "../lib/games-logic.mjs";

test("streakAtRisk: alive, not yet played today, streak of two or more", () => {
  const data = {
    linkle: { stats: { streak: 4, last: 9 }, today: { idx: 9, done: true } },          // played yesterday only
    "daily-five": { stats: { streak: 3, last: 9 } },
    quadlink: { stats: { streak: 1, last: 9 } },                                         // too short
    crossword: { stats: { streak: 5, last: 10 }, today: { idx: 10, done: true } },       // already played today
    "daily-photo": { stats: { streak: 6, last: 7 } },                                    // streak already broken
  };
  assert.deepEqual(streakAtRisk(data, 10).map((r) => r.game), ["linkle", "daily-five"]);
});

test("reminder emails go only to opted-in accounts with a live streak, once a day", async () => {
  const idxNow = dayIndexUTC(new Date(Date.UTC(2026, 9, 6, 0, 5) - 6 * 3600 * 1000));   // 00:05 UTC Oct 6 is still Oct 5 in the US
  const live = { linkle: { stats: { streak: 4, last: idxNow - 1 } } };
  const accounts = {
    ["acct:" + "a".repeat(64)]: { email: "yes@example.com", remind: true, remindToken: "b".repeat(32), data: live },
    ["acct:" + "c".repeat(64)]: { email: "off@example.com", remind: false, remindToken: "d".repeat(32), data: live },
    ["acct:" + "e".repeat(64)]: { email: "nostreak@example.com", remind: true, remindToken: "f".repeat(32), data: { linkle: { stats: { streak: 1, last: idxNow - 1 } } } },
  };
  const getStore = () => ({
    list: async () => ({ blobs: Object.keys(accounts).map((key) => ({ key })) }),
    get: async (k) => accounts[k] ?? null,
    setJSON: async (k, v) => { accounts[k] = v; },
  });
  const sent = [];
  const run = createReminder({ getStore, env: () => "re_test", fetchFn: async (u, o) => { sent.push(JSON.parse(o.body)); return new Response("{}"); }, now: () => Date.UTC(2026, 9, 6, 0, 5) });
  assert.equal((await run()).sent, 1);
  assert.equal(sent[0].to[0], "yes@example.com");
  assert.match(sent[0].subject, /4-day Linkle streak/);
  assert.match(sent[0].headers["List-Unsubscribe"], /\/games\/account\/\?off=a{64}\.b{32}/);
  assert.equal((await run()).sent, 0);   // not twice in one day
});

test("reminder unsubscribe link switches it off; wrong token does not", async () => {
  const s = await signIn();
  await call({ action: "set_reminder", on: true }, bearer(s));
  const acct = [...stores.data.keys()].find((k) => k.startsWith("games-accounts/acct:"));
  const rec = JSON.parse(stores.data.get(acct));
  assert.equal(rec.remind, true);
  const hash = acct.split("acct:")[1];
  assert.equal((await call({ action: "remind_off", acct: hash, token: "0".repeat(32) })).status, 400);
  assert.equal((await call({ action: "remind_off", acct: hash, token: rec.remindToken })).status, 200);
  assert.equal(JSON.parse(stores.data.get(acct)).remind, false);
});

test("chess and sudoku progress survives cleanData; junk is dropped", () => {
  const cells = "5".repeat(40) + ".".repeat(41);
  const out = cleanData({
    sudoku: { today: { idx: 3, cells, notes: [0, 5, 7], elapsed: 90, done: false } },
    "daily-chess": { today: { idx: 3, ply: 2, mistakes: 1, hints: 0, done: false } },
  });
  assert.equal(out.sudoku.today.cells, cells);
  assert.equal(out["daily-chess"].today.mistakes, 1);
  const bad = cleanData({ sudoku: { today: { idx: 3, cells: "<script>", done: false } } });
  assert.ok(!bad.sudoku.today.cells);
});

test("goals sync: whitelisted, bounded, merged without losing XP", () => {
  const a = cleanData({ goals: { d: { 5: { t: 2, q: 5 }, "x": { t: 9 } }, w: { 0: 1 }, banked: 30 } });
  assert.deepEqual(Object.keys(a.goals.d), ["5"]);
  const b = cleanData({ goals: { d: { 5: { t: 3, q: 2 }, 6: { t: 1, q: 0 } }, w: { 1: 1 }, banked: 10 } });
  const m = mergeData(a, b);
  assert.deepEqual(m.goals.d["5"], { t: 3, q: 7 });
  assert.equal(m.goals.d["6"].t, 1);
  assert.deepEqual(Object.keys(m.goals.w).sort(), ["0", "1"]);
  assert.equal(m.goals.banked, 30);
  assert.equal(cleanData({ goals: { d: { 1: { t: 99, q: 99 } } } }).goals.d["1"].t, 3);
});

test("a session in use renews itself, so an active device stays signed in for years", async () => {
  const s = await signIn();
  const DAY = 86400000;
  clock += 360 * DAY;                                  // 5 days left on the original year
  assert.equal((await call({ action: "sync", data: {} }, bearer(s))).status, 200);   // use it: renews to a full year
  clock += 360 * DAY;                                  // 720 days after sign-in, long past the original expiry
  assert.equal((await call({ action: "sync", data: {} }, bearer(s))).status, 200);
  clock += 366 * DAY;                                  // unused for more than a year: signed out
  assert.equal((await call({ action: "sync", data: {} }, bearer(s))).status, 401);
});

test("every store is opened with strong consistency, so a new session is readable at once", async () => {
  await signIn("a@example.com");
  const opened = stores.calls.filter((o) => typeof o === "object");
  assert.ok(opened.length > 0 && opened.length === stores.calls.length);               // no store is opened by bare name
  assert.ok(opened.every((o) => o.consistency === "strong"));
  assert.ok(["games-auth", "games-accounts"].every((n) => opened.some((o) => o.name === n)));
});

test("signing in on a second device leaves the first one signed in", async () => {
  const phone = await signIn("mom@example.com");
  const laptop = await signIn("mom@example.com");
  assert.notEqual(phone, laptop);
  assert.equal((await call({ action: "sync", data: {} }, bearer(phone))).status, 200);
  assert.equal((await call({ action: "sync", data: {} }, bearer(laptop))).status, 200);
});

// ---- per-day history, all-time ranks and the daily boards ----
const statsOf = (wins, played = wins.length, extra = {}) => ({ played, won: wins.length, streak: 0, max: 0, last: wins.at(-1) ?? -1, dist: {}, wins, freezes: [], ...extra });
const syncGame = async (s, game, rec) => (await call({ action: "sync", data: { [game]: rec } }, bearer(s))).json();
const rankOfGame = async (s, game) => (await (await call({ action: "rank", game }, bearer(s))).json()).games[game];

test("scores count once per account, once per browser id, and once per connection when neither is sent", async () => {
  const idx = 2;
  const post = async (extra, headers = {}) => (await call({ action: "score", game: "linkle", idx, score: 4, ...extra }, headers)).json();
  assert.equal((await post({})).total, 1);                                  // anonymous, by connection
  assert.equal((await post({})).total, 1);                                  // the same connection again: not counted twice
  assert.equal((await post({ vid: "a".repeat(32) })).total, 2);             // a browser on the same connection: counted
  assert.equal((await post({ vid: "b".repeat(32) })).total, 3);             // a second browser in the same home
  assert.equal((await post({ vid: "b".repeat(32) })).total, 3);             // that browser again: once
  const s = await signIn();
  assert.equal((await post({}, bearer(s))).total, 4);                       // signed in: by account
  assert.equal((await post({ vid: "c".repeat(32) }, bearer(s))).total, 4);  // same account, different browser: still once
  assert.equal((await post({ vid: "not-hex" })).total, 4);                  // a malformed id falls back to the connection, already counted
});

test("sync stores a day-by-day history and merges it across devices", async () => {
  const s = await signIn();
  await syncGame(s, "linkle", { stats: statsOf([0, 1]), hist: { s: 0, c: "0300" + "04" } });       // days 0:3 1:0 2:4 (ignoring wins)
  const out = await syncGame(s, "linkle", { stats: statsOf([5]), hist: { s: 4, c: "zz" + "05" } }); // another device: day 5 scored 5
  const h = out.data.linkle.hist;
  assert.equal(h.s, 0);
  assert.equal(h.c, "030004zz" + "zz05");
  const bad = await syncGame(s, "linkle", { hist: { s: 0, c: "ABC" } });                         // malformed: ignored, existing history kept
  assert.equal(bad.data.linkle.hist.c, h.c);
});

test("all-time rank follows wins, moves when a player's numbers change, and never counts anyone twice", async () => {
  const a = await signIn("a@example.com"), b = await signIn("b@example.com"), c = await signIn("c@example.com");
  await syncGame(a, "quadlink", { stats: statsOf([0, 1, 2]) });
  await syncGame(b, "quadlink", { stats: statsOf([0]) });
  await syncGame(c, "quadlink", { stats: statsOf([0, 1]) });
  let r = await rankOfGame(a, "quadlink");
  assert.deepEqual([r.w.v, r.w.rank, r.w.total, r.w.pct], [3, 1, 3, 83]);
  r = await rankOfGame(b, "quadlink");
  assert.deepEqual([r.w.rank, r.w.total, r.w.pct], [3, 3, 17]);
  await syncGame(a, "quadlink", { stats: statsOf([0, 1, 2]) });          // same data again: no double count
  await syncGame(a, "quadlink", { stats: statsOf([0, 1, 2]) });
  assert.equal((await rankOfGame(c, "quadlink")).w.total, 3);
  await syncGame(b, "quadlink", { stats: statsOf([0, 1, 2], 3) });       // b catches up on wins (day 1 and 2 added)
  r = await rankOfGame(c, "quadlink");
  assert.deepEqual([r.w.rank, r.w.total], [3, 3]);                       // now behind both
  assert.equal(r.s.v, 2);
});

test("wins and streaks cannot exceed the number of days since launch", async () => {
  const s = await signIn();
  const wins = Array.from({ length: 400 }, (_, i) => i);                 // 400 wins on day 2 of the site
  await syncGame(s, "linkle", { stats: statsOf(wins, 400, { max: 9999, won: 9999 }) });
  const r = await rankOfGame(s, "linkle");
  assert.equal(r.w.v, 3);                                                // today is day 2, so at most 3 days exist (0, 1, 2)
  assert.equal(r.s.v, 3);
});

test("average percentile is ranked only after 20 days with a real crowd", async () => {
  const s = await signIn();
  await syncGame(s, "linkle", { stats: statsOf([0]), pct: { sum: 1900, count: 19, best: 100, last: 90 } });
  assert.equal((await rankOfGame(s, "linkle")).p, undefined);
  await syncGame(s, "linkle", { stats: statsOf([0]), pct: { sum: 2000, count: 20, best: 100, last: 90 } });
  assert.equal((await rankOfGame(s, "linkle")).p.v, 100);
});

test("daily boards list only players who opted in with a name, and removal is complete", async () => {
  const a = await signIn("a@example.com"), b = await signIn("b@example.com");
  await syncGame(a, "riverlink", { stats: statsOf([0, 1, 2]) });
  await syncGame(b, "riverlink", { stats: statsOf([0]) });
  const board = async (viewer) => (await call({ action: "leaderboard", game: "riverlink", board: "wins" }, viewer ? bearer(viewer) : {})).json();
  assert.equal((await board()).rows.length, 0);                          // nobody has opted in
  assert.equal((await call({ action: "set_public", on: true }, bearer(a))).status, 400);   // needs a name first
  await call({ action: "set_name", name: "Ada" }, bearer(a));
  await call({ action: "set_name", name: "Bo" }, bearer(b));
  assert.equal((await call({ action: "set_public", on: true }, bearer(a))).status, 200);
  assert.equal((await call({ action: "set_public", on: true }, bearer(b))).status, 200);
  let out = await board(b);
  assert.deepEqual(out.rows.map((x) => [x.rank, x.name, x.v]), [[1, "Ada", 3], [2, "Bo", 1]]);
  assert.deepEqual([out.you.rank, out.you.total, out.you.listed], [2, 2, true]);
  await syncGame(b, "riverlink", { stats: statsOf([0, 1, 2, 3], 4) });  // not possible by day 2, so capped: ties Ada at 3, fewer games first? same played count
  out = await board();
  assert.equal(out.rows.length, 2);
  await call({ action: "set_public", on: false }, bearer(a));
  out = await board(a);
  assert.deepEqual(out.rows.map((x) => x.name), ["Bo"]);
  assert.equal(out.you.listed, false);                                   // still ranked, not listed
  assert.equal(out.you.rank, 1);                                         // b is capped at 3 wins and ties a: rank counts only players strictly ahead
  await call({ action: "delete_account" }, bearer(a));
  out = await board();
  assert.equal(out.total, 1);                                            // a is out of the histogram too
});

test("a name change updates the daily boards, and a blocked name drops the player", async () => {
  const a = await signIn("a@example.com");
  await syncGame(a, "wildlink", { stats: statsOf([0, 1]) });
  await call({ action: "set_name", name: "Ada" }, bearer(a));
  await call({ action: "set_public", on: true }, bearer(a));
  await call({ action: "set_name", name: "Ada L" }, bearer(a));
  const out = await (await call({ action: "leaderboard", game: "wildlink", board: "streak" })).json();
  assert.deepEqual(out.rows.map((x) => x.name), ["Ada L"]);
});

test("unknown games and boards are refused", async () => {
  assert.equal((await call({ action: "leaderboard", game: "nope", board: "wins" })).status, 400);
  assert.equal((await call({ action: "leaderboard", game: "linkle", board: "bogus" })).status, 400);   // falls through to the rated-board path, which refuses unrated games
  const s = await signIn();
  assert.deepEqual((await (await call({ action: "rank", game: "nope" }, bearer(s))).json()).games, {});
});

test("players tied on a daily board share a rank and only the viewer's own row is marked", async () => {
  const a = await signIn("a@example.com"), b = await signIn("b@example.com"), c = await signIn("c@example.com");
  for (const [s, name, wins] of [[a, "Ada", [0, 1, 2]], [b, "Bo", [0, 1, 2]], [c, "Cy", [0]]]) {
    await syncGame(s, "citylink", { stats: statsOf(wins) });
    await call({ action: "set_name", name }, bearer(s));
    await call({ action: "set_public", on: true }, bearer(s));
  }
  const out = await (await call({ action: "leaderboard", game: "citylink", board: "wins" }, bearer(b))).json();
  assert.deepEqual(out.rows.map((x) => [x.rank, x.name, !!x.me]), [[1, "Ada", false], [1, "Bo", true], [3, "Cy", false]]);
  assert.deepEqual([out.you.rank, out.you.total], [1, 3]);
});

test("hostile or odd names cannot reach inherited properties or junk storage", async () => {
  for (const game of ["constructor", "__proto__", "toString", "hasOwnProperty"]) {
    assert.equal((await call({ action: "score", game, idx: 2, score: 3 })).status, 400);
    assert.equal((await call({ action: "leaderboard", game: "linkle", board: game })).status, 400);
    assert.equal((await call({ action: "leaderboard", game, board: "wins" })).status, 400);
  }
  assert.ok(![...stores.data.keys()].some((k) => k.includes("constructor") || k.includes("__proto__")));
});

test("a player with no wins is ranked but never listed on a wins or streak board", async () => {
  const a = await signIn("a@example.com");
  await syncGame(a, "codelink", { stats: statsOf([], 3, { last: 1 }) });
  await call({ action: "set_name", name: "Ada" }, bearer(a));
  await call({ action: "set_public", on: true }, bearer(a));
  const out = await (await call({ action: "leaderboard", game: "codelink", board: "wins" }, bearer(a))).json();
  assert.equal(out.rows.length, 0);
  assert.deepEqual([out.you.v, out.you.rank, out.you.total, out.you.listed], [0, 1, 1, false]);
});

test("a hostile history span stays bounded and keeps the most recent days", async () => {
  const s = await signIn();
  await syncGame(s, "linkle", { stats: statsOf([2]), hist: { s: 100000, c: "05" } });
  const t0 = Date.now();
  const out = await syncGame(s, "linkle", { hist: { s: 0, c: "03" } });
  assert.ok(Date.now() - t0 < 1500);
  const h = out.data.linkle.hist;
  assert.ok(h.c.length <= 1460);
  assert.equal(h.s + h.c.length / 2, 100001);                 // ends on the latest day
  assert.ok(h.c.endsWith("05"));                              // and keeps that day's score
});

test("a weekly rebuild repairs ranks that overlapping syncs left wrong, and changes nothing when they are right", async () => {
  const a = await signIn("a@example.com"), b = await signIn("b@example.com");
  await syncGame(a, "peaklink", { stats: statsOf([0, 1, 2]) });
  await syncGame(b, "peaklink", { stats: statsOf([0]) });
  for (const [s, name] of [[a, "Ada"], [b, "Bo"]]) { await call({ action: "set_name", name }, bearer(s)); await call({ action: "set_public", on: true }, bearer(s)); }
  const before = JSON.stringify([...stores.data.entries()].filter(([k]) => k.startsWith("games-rank/") || k.startsWith("games-lb/lbd:")));
  assert.deepEqual(await handler.rebuild(), { accounts: 2, repaired: 0 });
  assert.equal(JSON.stringify([...stores.data.entries()].filter(([k]) => k.startsWith("games-rank/") || k.startsWith("games-lb/lbd:"))), before);
  stores.data.set("games-rank/h:peaklink:w", JSON.stringify({ buckets: { 3: 2, 1: 5, 99: 1 } }));     // drift
  stores.data.delete("games-lb/lbd:peaklink");
  await handler.rebuild();
  const out = await (await call({ action: "leaderboard", game: "peaklink", board: "wins" }, bearer(b))).json();
  assert.deepEqual([out.total, out.you.rank, out.rows.map((x) => x.name)], [2, 2, ["Ada", "Bo"]]);
});

// ---- the daily board ----
const histOf = (s, v) => ({ s, c: v.map((x) => (x === null ? "zz" : x.toString(36).padStart(2, "0"))).join("") });
const dayBoard = async (game, idx, viewer) => (await call({ action: "leaderboard", game, board: "day", idx }, viewer ? bearer(viewer) : {})).json();
async function listed(email, name, game, hist, wins = [2]) {
  const s = await signIn(email);
  await call({ action: "set_name", name }, bearer(s));
  await call({ action: "set_public", on: true }, bearer(s));
  await syncGame(s, game, { stats: statsOf(wins), hist });
  return s;
}

test("the daily board lists opted-in players by score, shares ranks on a tie, and marks only the viewer", async () => {
  const today = 2;                                                    // the test clock is puzzle day 2
  const a = await listed("a@example.com", "Ada", "linkle", histOf(today, [3]));
  const b = await listed("b@example.com", "Bo", "linkle", histOf(today, [3]));
  const c = await listed("c@example.com", "Cy", "linkle", histOf(today, [5]));
  const d = await signIn("d@example.com");                             // plays, never opts in
  await syncGame(d, "linkle", { stats: statsOf([2]), hist: histOf(today, [2]) });
  const out = await dayBoard("linkle", today, b);
  assert.deepEqual(out.rows.map((x) => [x.rank, x.name, x.v, !!x.me]), [[1, "Ada", 3, false], [1, "Bo", 3, true], [3, "Cy", 5, false]]);
  assert.deepEqual([out.you.v, out.you.rank, out.you.listed], [3, 1, true]);
  assert.equal((await dayBoard("linkle", today, d)).you.listed, false);   // d can see their own result, unlisted
  assert.equal((await dayBoard("linkle", today - 1)).rows.length, 0);    // yesterday's board is separate
  assert.equal((await dayBoard("wildlink", today)).rows.length, 0);      // and so is each game's
});

test("the daily board follows name changes and opting out, and the anonymous tally supplies the best score", async () => {
  const today = 2;
  await call({ action: "score", game: "citylink", idx: today, score: 2 }, { "x-nf-client-connection-ip": "9.9.9.9" });
  const a = await listed("a@example.com", "Ada", "citylink", histOf(today, [4]));
  await call({ action: "set_name", name: "Ada L" }, bearer(a));
  let out = await dayBoard("citylink", today);
  assert.deepEqual(out.rows.map((x) => x.name), ["Ada L"]);
  assert.deepEqual([out.finishers, out.best], [1, { v: 2, n: 1 }]);
  await call({ action: "set_public", on: false }, bearer(a));
  assert.equal((await dayBoard("citylink", today)).rows.length, 0);
});

test("a result only appears once the player has opted in, including one finished earlier today", async () => {
  const today = 2;
  const s = await signIn("a@example.com");
  await syncGame(s, "riverlink", { stats: statsOf([2]), hist: histOf(today, [1]) });     // finished before opting in
  assert.equal((await dayBoard("riverlink", today)).rows.length, 0);
  await call({ action: "set_name", name: "Ada" }, bearer(s));
  await call({ action: "set_public", on: true }, bearer(s));
  assert.deepEqual((await dayBoard("riverlink", today)).rows.map((x) => [x.name, x.v]), [["Ada", 1]]);
});

test("daily boards refuse puzzle numbers far from today, and a deleted account leaves nothing behind", async () => {
  assert.equal((await call({ action: "leaderboard", game: "linkle", board: "day", idx: 99 })).status, 400);
  assert.equal((await call({ action: "leaderboard", game: "linkle", board: "day", idx: "x" })).status, 400);
  assert.equal((await call({ action: "leaderboard", game: "nope", board: "day", idx: 2 })).status, 400);
  const a = await listed("a@example.com", "Ada", "peaklink", histOf(2, [3]));
  assert.equal((await dayBoard("peaklink", 2)).rows.length, 1);
  await call({ action: "delete_account" }, bearer(a));
  assert.equal((await dayBoard("peaklink", 2)).rows.length, 0);
});

test("old daily boards are dropped when a newer day is written", async () => {
  await listed("a@example.com", "Ada", "codelink", histOf(2, [3]));
  stores.data.set("games-lb/lbday:codelink:-2", JSON.stringify({ rows: [{ a: "z", name: "Old", s: 1 }] }));
  const s = await signIn("b@example.com");
  await call({ action: "set_name", name: "Bo" }, bearer(s)); await call({ action: "set_public", on: true }, bearer(s));
  await syncGame(s, "codelink", { stats: statsOf([2]), hist: histOf(2, [4]) });
  assert.equal(stores.data.has("games-lb/lbday:codelink:-2"), false);      // 4 days before day 2 is day -2: removed by the write
});

test("daily ranks count everyone who finished ahead, named or not", async () => {
  const today = 2;
  for (const [ip, score] of [["1.1.1.1", 2], ["1.1.1.2", 2], ["1.1.1.3", 4]]) await call({ action: "score", game: "gridlink", idx: today, score }, { "x-nf-client-connection-ip": ip });
  const a = await listed("a@example.com", "Ada", "gridlink", histOf(today, [4]));
  await call({ action: "score", game: "gridlink", idx: today, score: 4 }, bearer(a));
  const out = await dayBoard("gridlink", today, a);
  assert.deepEqual([out.rows[0].rank, out.you.rank, out.finishers], [3, 3, 4]);          // two anonymous finishers did better
});
