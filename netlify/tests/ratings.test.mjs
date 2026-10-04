// Tests for the rating maths and the rated-puzzle actions of games-api.mjs.
// Run with: node --test netlify/tests/ratings.test.mjs
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createHandler } from "../functions/games-api.mjs";
import { applyResult, checkReport, emptyRecord, expected, kFactor, nextRating, publicNameOk, sudokuScore, upsertRow, weekOf } from "../lib/ratings.mjs";

const INDEX = { aaaaa: [1200, 4], bbbbb: [1800, 6], ccccc: [900, 4] };

test("elo basics: equal ratings expect 0.5, a win against a stronger puzzle gains more", () => {
  assert.equal(expected(1500, 1500), 0.5);
  const rec = { ...emptyRecord(), r: 1500, n: 100 };
  const easy = nextRating(rec, 1300, 1).delta, hard = nextRating(rec, 1700, 1).delta;
  assert.ok(hard > easy && easy > 0);
  assert.ok(nextRating(rec, 1300, 0).delta < -10);
  assert.equal(kFactor(0, 1000), 48);
  assert.equal(kFactor(100, 2500), 16);
  assert.equal(nextRating({ r: 400, n: 100 }, 3000, 0).r, 400);   // floor
});

test("sudoku score steps down with time and help", () => {
  assert.equal(sudokuScore("clean", 100, 1), 0.95);
  assert.equal(sudokuScore("clean", 300, 1), 0.8);
  assert.equal(sudokuScore("clean", 590, 1), 0.6);
  assert.equal(sudokuScore("clean", 2000, 1), 0.5);
  assert.equal(sudokuScore("help", 100, 3), 0.35);
  assert.equal(sudokuScore("skip", 100, 3), 0);
});

test("applyResult tracks streaks, the week and the day", () => {
  let rec = emptyRecord();
  for (let i = 0; i < 3; i++) rec = applyResult(rec, { puzzleRating: 1000, score: 1, solved: true, dayIdx: 10, dayKey: "2026-10-14" }).rec;
  assert.equal(rec.streak, 3); assert.equal(rec.best, 3); assert.equal(rec.wn, 3); assert.equal(rec.dn, 3);
  assert.ok(rec.r > 1000);
  const wk = rec.wk;
  rec = applyResult(rec, { puzzleRating: 1000, score: 0, solved: false, dayIdx: 10, dayKey: "2026-10-14" }).rec;
  assert.equal(rec.streak, 0); assert.equal(rec.best, 3);
  rec = applyResult(rec, { puzzleRating: 1000, score: 1, solved: true, dayIdx: 20, dayKey: "2026-10-24" }).rec;
  assert.notEqual(rec.wk, wk); assert.equal(rec.wn, 1); assert.equal(rec.dn, 1);
  assert.equal(weekOf(0), 0); assert.equal(weekOf(1), 1); assert.equal(weekOf(7), 1); assert.equal(weekOf(8), 2);   // weeks run Monday to Sunday; day 0 is a Sunday
});

test("checkReport: unknown ids, bad results and impossible times are refused", () => {
  assert.equal(checkReport("chess", { id: "zzzzz", result: "solved", ms: 9000 }, INDEX).error, "unknown_puzzle");
  assert.equal(checkReport("chess", { id: "aaaaa", result: "maybe", ms: 9000 }, INDEX).error, "bad_result");
  assert.equal(checkReport("chess", { id: "aaaaa", result: "solved", ms: 200 }, INDEX).error, "too_fast");
  assert.equal(checkReport("chess", { id: "aaaaa", result: "failed", ms: 200 }, INDEX).ok, true);
  const ok = checkReport("chess", { id: "bbbbb", result: "solved", ms: 9000 }, INDEX);
  assert.deepEqual([ok.puzzleRating, ok.score], [1800, 1]);
  assert.equal(checkReport("sudoku", { id: "9-1", result: "clean", ms: 99999 }, INDEX).error, "unknown_puzzle");
  assert.equal(checkReport("sudoku", { id: "3-12", result: "clean", ms: 5000 }, INDEX).error, "too_fast");
  assert.equal(checkReport("sudoku", { id: "3-12", result: "clean", ms: 400000 }, INDEX).puzzleRating, 1600);
  assert.equal(checkReport("sudoku", { id: "3-12", result: "skip", ms: 10 }, INDEX).score, 0);
  assert.equal(checkReport("go", { id: "x", ms: 1 }, INDEX).error, "unknown_game");
});

test("boards: rows replace by account, sort by rating, and the weekly board needs three puzzles", () => {
  let rows = [];
  rows = upsertRow(rows, { a: "x", name: "Xa", r: 1200, n: 9, g: 30, wn: 5 }, "all");
  rows = upsertRow(rows, { a: "y", name: "Yo", r: 1300, n: 9, g: 10, wn: 5 }, "all");
  rows = upsertRow(rows, { a: "x", name: "Xa", r: 1400, n: 10, g: 230, wn: 6 }, "all");
  assert.deepEqual(rows.map((r) => r.a), ["x", "y"]);
  assert.equal(upsertRow([], { a: "z", name: "Zz", r: 1000, n: 1, g: 5, wn: 2 }, "week").length, 0);
  assert.equal(upsertRow([], { a: "z", name: "Zz", r: 1000, n: 3, g: 5, wn: 3 }, "week").length, 1);
  assert.ok(publicNameOk("Quinn")); assert.ok(!publicNameOk("x")); assert.ok(!publicNameOk("Big Hitler"));
});

// ---- the API ----
function memoryStores() {
  const data = new Map();
  return { getStore: (name) => ({
    get: async (k, o) => { const v = data.get(`${name}/${k}`); return v === undefined ? null : o?.type === "json" ? JSON.parse(v) : v; },
    set: async (k, v) => { data.set(`${name}/${k}`, String(v)); },
    setJSON: async (k, v) => { data.set(`${name}/${k}`, JSON.stringify(v)); },
    delete: async (k) => { data.delete(`${name}/${k}`); },
  }), data };
}
let stores, mails, clock, handler;
const env = (k) => (k === "RESEND_API_KEY" ? "test" : null);
beforeEach(() => {
  stores = memoryStores(); mails = []; clock = Date.parse("2026-10-14T12:00:00Z");
  handler = createHandler({ getStore: stores.getStore, env, now: () => clock, chessIndex: INDEX,
    fetchFn: async (_u, init) => { mails.push(JSON.parse(init.body)); return { ok: true }; } });
});
const call = async (body, session) => {
  const headers = { "Content-Type": "application/json", Origin: "https://purplelink.llc" };
  if (session) headers.Authorization = `Bearer ${session}`;
  const res = await handler(new Request("https://purplelink.llc/.netlify/functions/games-api", { method: "POST", headers, body: JSON.stringify(body) }));
  return { status: res.status, body: await res.json() };
};
async function signIn(email) {
  await call({ action: "login_request", email });
  const token = /t=([a-f0-9]{48})/.exec(mails.at(-1).text)[1];
  return (await call({ action: "login_verify", token })).body.session;
}

test("rated puzzles: report, rating, opt-in, leaderboard, removal", async () => {
  const s = await signIn("a@example.com");
  assert.equal((await call({ action: "ratings" })).status, 401);
  const r1 = await call({ action: "rating_report", game: "chess", id: "aaaaa", result: "solved", ms: 9000 }, s);
  assert.equal(r1.status, 200); assert.ok(r1.body.delta > 0); assert.equal(r1.body.n, 1);
  assert.equal((await call({ action: "rating_report", game: "chess", id: "aaaaa", result: "solved", ms: 9000 }, s)).body.repeat, true);   // same puzzle twice is ignored
  assert.equal((await call({ action: "rating_report", game: "chess", id: "bbbbb", result: "solved", ms: 100 }, s)).body.error, "too_fast");
  const mine = (await call({ action: "ratings" }, s)).body;
  assert.equal(mine.chess.n, 1); assert.equal(mine.sudoku, null); assert.equal(mine.public, false);
  // not listed until the player opts in, and opting in needs a name
  assert.equal((await call({ action: "leaderboard", game: "chess", board: "all" })).body.rows.length, 0);
  assert.equal((await call({ action: "set_public", on: true }, s)).body.error, "name_needed");
  await call({ action: "set_name", name: "Quinn" }, s);
  assert.equal((await call({ action: "set_public", on: true }, s)).body.public, true);
  const lb = (await call({ action: "leaderboard", game: "chess", board: "all" }, s)).body;
  assert.equal(lb.rows.length, 1); assert.equal(lb.rows[0].name, "Quinn"); assert.equal(lb.you.rank, 1);
  assert.ok(!("a" in lb.rows[0]));                       // no account id leaves the server
  assert.equal((await call({ action: "leaderboard", game: "chess", board: "week" })).body.rows.length, 0);   // needs three puzzles this week
  await call({ action: "rating_report", game: "chess", id: "ccccc", result: "failed", ms: 4000 }, s);
  await call({ action: "rating_report", game: "chess", id: "bbbbb", result: "failed", ms: 4000 }, s);
  assert.equal((await call({ action: "leaderboard", game: "chess", board: "week" })).body.rows.length, 1);
  // a second player outranks the first
  const t = await signIn("b@example.com");
  await call({ action: "set_name", name: "Robin" }, t);
  await call({ action: "set_public", on: true }, t);
  for (const id of ["bbbbb"]) await call({ action: "rating_report", game: "chess", id, result: "solved", ms: 9000 }, t);
  const lb2 = (await call({ action: "leaderboard", game: "chess", board: "all" })).body.rows;
  assert.deepEqual(lb2.map((r) => r.name), ["Robin", "Quinn"]);
  // sudoku rates on its own scale
  const sd = await call({ action: "rating_report", game: "sudoku", id: "2-5", result: "clean", ms: 200000 }, s);
  assert.equal(sd.status, 200); assert.ok(sd.body.delta > 0);
  // leaving removes the rows
  await call({ action: "set_public", on: false }, s);
  assert.deepEqual((await call({ action: "leaderboard", game: "chess", board: "all" })).body.rows.map((r) => r.name), ["Robin"]);
  await call({ action: "delete_account" }, t);
  assert.equal((await call({ action: "leaderboard", game: "chess", board: "all" })).body.rows.length, 0);
});

test("a first report can seed the rating from the browser, capped", async () => {
  const s = await signIn("c@example.com");
  const r = await call({ action: "rating_report", game: "chess", id: "ccccc", result: "failed", ms: 3000, seed: { r: 2900, n: 80 } }, s);
  assert.ok(r.body.r <= 1500 && r.body.r > 1300);
  assert.equal(r.body.n, 41);
});

test("the browser copy of the formulas matches the service", async () => {
  const { readFileSync } = await import("node:fs"), vm = await import("node:vm");
  const mod = { exports: {} };
  vm.runInThisContext("(function (module) {" + readFileSync("site/games/ratings.js", "utf8") + "\n})")(mod);   // a browser script (UMD)
  const C = mod.exports;
  const { kFactor: kS, nextRating: nS, sudokuScore: sS, LEVEL_RATING: LS, PAR_SECONDS } = await import("../lib/ratings.mjs");
  assert.deepEqual(C.LEVEL_RATING, LS); assert.deepEqual(C.PAR, PAR_SECONDS);
  for (const n of [0, 19, 20, 59, 60, 400]) for (const r of [500, 1500, 2399, 2400, 3000]) assert.equal(C.kFactor(n, r), kS(n, r));
  for (const r of [400, 1000, 1700, 2600]) for (const p of [600, 1200, 2000]) for (const s of [0, 0.35, 1]) for (const n of [0, 30, 99]) {
    assert.deepEqual(C.nextRating({ r, n }, p, s), nS({ r, n }, p, s));
  }
  for (const res of ["clean", "help", "skip"]) for (const t of [10, 200, 500, 900, 5000]) for (const l of [1, 2, 3, 4, 5]) assert.equal(C.sudokuScore(res, t, l), sS(res, t, l));
  assert.equal(C.tierFor(1000), "Learner"); assert.equal(C.tierFor(2450), "Grandmaster");
});
