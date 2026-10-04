// Tests for games-api.mjs and games-logic.mjs. Blobs and Resend are in-memory stand-ins.
// Run with: node --test netlify/tests/games-api.test.mjs

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHandler } from "../functions/games-api.mjs";
import { mergeData, cleanData, percentile, cleanName, dayIndexUTC } from "../lib/games-logic.mjs";

function memoryStores() {
  const data = new Map();
  return {
    getStore: (name) => ({
      get: async (k, opts) => { const v = data.get(`${name}/${k}`); return v === undefined ? null : opts?.type === "json" ? JSON.parse(v) : v; },
      set: async (k, v) => { data.set(`${name}/${k}`, String(v)); },
      setJSON: async (k, v) => { data.set(`${name}/${k}`, JSON.stringify(v)); },
      delete: async (k) => { data.delete(`${name}/${k}`); },
    }),
    data,
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
