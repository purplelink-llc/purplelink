import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import vm from "node:vm";

// core.js is a browser script (UMD); load it in a sandbox so the repo's module settings do not matter.
const mod = { exports: {} };
vm.runInThisContext("(function (module, Buffer) {" + readFileSync("site/games/core.js", "utf8") + "\n})")(mod, Buffer);
const G = mod.exports;

test("score: plain cases", () => {
  assert.deepEqual(G.score("crane", "crane"), ["c", "c", "c", "c", "c"]);
  assert.deepEqual(G.score("xxxxx", "crane"), ["a", "a", "a", "a", "a"]);
  assert.deepEqual(G.score("nacre", "crane"), ["p", "p", "p", "p", "c"]);
});

test("score: a repeated guess letter is present only as often as the answer has it", () => {
  assert.deepEqual(G.score("geese", "creak"), ["a", "a", "c", "a", "a"]);
  assert.deepEqual(G.score("llama", "hello"), ["p", "p", "a", "a", "a"]);
  assert.deepEqual(G.score("speed", "abide"), ["a", "a", "p", "a", "p"]);
  assert.deepEqual(G.score("eerie", "there"), ["p", "a", "p", "a", "c"]);
  assert.deepEqual(G.score("sleep", "geese"), ["p", "a", "c", "p", "a"]);
});

test("dayIndex counts calendar days and ignores daylight saving", () => {
  assert.equal(G.dayIndex(new Date(2026, 9, 5), "2026-10-05"), 0);
  assert.equal(G.dayIndex(new Date(2026, 9, 6, 23, 59), "2026-10-05"), 1);
  assert.equal(G.dayIndex(new Date(2026, 10, 2, 0, 5), "2026-10-05"), 28); // clocks go back Nov 1 2026
  assert.equal(G.dayIndex(new Date(2027, 0, 1), "2026-10-05"), 88);
  assert.equal(G.dayIndex(new Date(2026, 9, 4), "2026-10-05"), -1);
});

test("pick wraps in both directions", () => {
  assert.equal(G.pick(["a", "b", "c"], 4), "b");
  assert.equal(G.pick(["a", "b", "c"], -1), "c");
});

test("decode round-trips the generator's encoding", () => {
  const enc = (w) => Buffer.from(w.split("").reverse().join("")).toString("base64");
  assert.equal(G.decode(enc("point")), "point");
});

test("decodeText handles accents and symbols", () => {
  const enc = (s) => Buffer.from(s, "utf8").toString("base64");
  assert.equal(G.decodeText(enc("Erwin Schrödinger")), "Erwin Schrödinger");
  assert.equal(G.decodeText(enc("9π")), "9π");
});

test("mergeKeys keeps the best state per letter", () => {
  const k = {};
  G.mergeKeys(k, "crane", ["a", "p", "a", "a", "c"]);
  G.mergeKeys(k, "react", ["c", "a", "a", "a", "a"]);
  assert.equal(k.r, "c"); // present first, then correct
  assert.equal(k.e, "c"); // stays correct after an absent mark
  assert.equal(k.c, "a");
  assert.equal(k.t, "a");
});

test("shareRow uses plain shapes, no emoji", () => {
  const row = G.shareRow(["c", "p", "a"]);
  assert.equal(row, "■▣□");
  assert.ok(!/\p{Extended_Pictographic}/u.test(row));
});

test("recordResult: streaks, losses and distribution", () => {
  let s = G.recordResult(null, 10, true, 4);
  assert.equal(s.streak, 1);
  s = G.recordResult(s, 11, true, 3);
  assert.equal(s.streak, 2);
  assert.equal(s.max, 2);
  s = G.recordResult(s, 13, true, 5); // skipped a day
  assert.equal(s.streak, 1);
  s = G.recordResult(s, 14, false, 6);
  assert.equal(s.streak, 0);
  assert.equal(s.played, 4);
  assert.equal(s.won, 3);
  assert.deepEqual(s.dist, { 3: 1, 4: 1, 5: 1 });
});

test("rankFor climbs the ladder", () => {
  assert.deepEqual(G.rankFor(0), { name: "Newcomer", next: "Reader", toNext: 5 });
  assert.equal(G.rankFor(5).name, "Reader");
  assert.equal(G.rankFor(29).name, "Scribe");
  assert.deepEqual(G.rankFor(150), { name: "Sage", next: null, toNext: 0 });
});

test("weekProgress follows Monday to Sunday weeks", () => {
  // epoch is a Sunday (dow 0): day 0 Sun, day 1 Mon ... day 7 Sun, day 8 Mon
  const wins = [1, 2, 3, 4, 5, 6, 7, 9, 10];
  let p = G.weekProgress(wins, 10, 0); // Wednesday of the second week (days 8..14)
  assert.deepEqual(p.days, [false, true, true, false, false, false, false]);
  assert.equal(p.today, 2);
  assert.equal(p.fullWeeks, 1);
  p = G.weekProgress(wins, 3, 0); // Wednesday of the first week (days 1..7)
  assert.equal(p.count, 7);
  assert.equal(G.weekNo(0, 0), 0);
  assert.equal(G.weekNo(1, 0), 1);
  assert.equal(G.weekNo(7, 0), 1);
  assert.equal(G.weekNo(8, 0), 2);
});

test("recordResult keeps the list of won days", () => {
  let s = G.recordResult(null, 5, true, 3);
  s = G.recordResult(s, 6, false, 6);
  s = G.recordResult(s, 7, true, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(s.wins)), [5, 7]);
});

test("hardModeError enforces known letters", () => {
  const hist = [{ guess: "crane", score: G.score("crane", "trace") }]; // c a e present, r correct? trace: t r a c e
  assert.equal(G.hardModeError("trace", hist), null);
  assert.match(G.hardModeError("stout", hist), /second letter must be R|must contain/);
  // a present letter must be reused
  const h2 = [{ guess: "slate", score: G.score("slate", "tower") }]; // t, e present
  assert.match(G.hardModeError("brick", h2), /must contain/);
  assert.equal(G.hardModeError("tower", h2), null);
});

test("generated data: deterministic, stable prefix, valid words", () => {
  const out = (args) => execFileSync("python3", ["scripts/gen_games.py", ...args], { encoding: "utf8" });
  assert.match(out(["--check"]), /up to date/);
  const valid = new Set(readFileSync("site/games/data/valid5.txt", "utf8").split("\n").filter(Boolean));
  const linkle = JSON.parse(readFileSync("site/games/data/linkle.json", "utf8"));
  const quad = JSON.parse(readFileSync("site/games/data/quadlink.json", "utf8"));
  assert.equal(linkle.answers.length, 730);
  for (const a of linkle.answers) assert.ok(valid.has(G.decode(a)), G.decode(a));
  for (const day of quad.days) {
    const w = day.map(G.decode);
    assert.equal(new Set(w).size, 4);
    for (const x of w) assert.ok(valid.has(x), x);
  }
});

test("crossword grids and clues are structurally sound", () => {
  const out = execFileSync("python3", ["scripts/check_crossword.py"], { encoding: "utf8" });
  assert.match(out, /0 problem/);
});
