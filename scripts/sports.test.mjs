import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// browser scripts (UMD): load in a sandbox so the repo's module settings do not matter
function load(file) { const mod = { exports: {} }; vm.runInThisContext("(function (module) {" + readFileSync("site/games/" + file, "utf8") + "\n})")(mod); return mod.exports; }
const S = load("sports.js");
globalThis.PLSports = S;
const SE = load("season.js");

const raw = JSON.parse(readFileSync("site/games/data/sports-nba.json", "utf8"));
raw.cfg.groupOf = S.GROUPS.nba;
const d = S.prepare(raw);
const P = (n) => d.byName[n];

test("teammates need the same franchise and an overlapping season", () => {
  assert.ok(S.areTeammates(d, P("LeBron James"), P("Anthony Davis")));
  assert.ok(S.areTeammates(d, P("Anthony Davis"), P("Cooper Flagg")));
  assert.ok(!S.areTeammates(d, P("LeBron James"), P("Cooper Flagg")));
  assert.ok(!S.areTeammates(d, P("Bill Russell"), P("Larry Bird")), "same team, no common season");
});

test("shortest chains", () => {
  assert.equal(S.path(d, P("LeBron James"), P("Cooper Flagg")).length, 3);
  const p = S.path(d, P("Bill Russell"), P("Jaylen Brown"));
  assert.ok(p && p.length >= 3, "any era to any era is connected");
});

test("every player in the pool is connected to every other", () => {
  const dist = S.distances(d, d.players[0]);
  assert.equal(Object.keys(dist).length, d.players.length);
});

test("every daily puzzle names players in the pool, and every grid cell has two answers", () => {
  assert.ok(d.tl.length >= 200 && d.gr.length >= 200);
  d.tl.forEach(([a, b]) => { assert.ok(P(a) && P(b)); assert.notEqual(a, b); });
  d.gr.slice(0, 120).forEach((g) => {
    const R = g.r.map((c) => S.crit(d, c)), C = g.c.map((c) => S.crit(d, c));
    R.forEach((r) => C.forEach((c) => assert.ok(S.cellAnswers(d, r, c).length >= 2, g.r + " x " + g.c)));
  });
});

test("season text", () => {
  assert.equal(S.span(d, 1978, 1978), "1978-79");
  assert.equal(S.span(d, 1970, 1973), "1970-74");
  assert.equal(S.span({ cfg: { split: false } }, 2005, 2010), "2005-10");
});

test("a stronger roster wins more, and the same seed gives the same season", () => {
  const slots = d.cfg.slots;
  const pick = (min) => { const used = new Set(); return slots.map((g) => { const p = d.players.filter((x) => x.g === g && x.tier >= min && !used.has(x.n))[0]; used.add(p.n); return p; }); };
  const strong = { starters: pick(5), bench: [] }, weak = { starters: pick(1), bench: [] };
  assert.ok(SE.strength(d, strong).rating > SE.strength(d, weak).rating);
  assert.deepEqual(SE.simulate(d, strong, "a"), SE.simulate(d, strong, "a"));
  const w = (r) => { let t = 0; for (let i = 0; i < 40; i++) t += SE.simulate(d, r, "s" + i).wins; return t; };
  assert.ok(w(strong) > w(weak));
});

test("daily rules: the weekday rule filters players", () => {
  const throwback = SE.constraint(d, 2), modern = SE.constraint(d, 3);
  assert.ok(throwback.ok(P("Bill Russell")) && !throwback.ok(P("Stephen Curry")));
  assert.ok(modern.ok(P("Stephen Curry")) && !modern.ok(P("Michael Jordan")));
  assert.ok(SE.constraint(d, 4).ok(P("Kobe Bryant")) === false);
});

for (const sport of ["nba", "nfl", "mlb", "nhl"]) {
  const r = JSON.parse(readFileSync(`site/games/data/sports-${sport}.json`, "utf8"));
  r.cfg.groupOf = S.GROUPS[sport];
  const dd = S.prepare(r);
  test(`${sport}: pool is connected and every slot can be filled`, () => {
    assert.equal(Object.keys(S.distances(dd, dd.players[0])).length, dd.players.length);
    dd.cfg.slots.forEach((g) => assert.ok(dd.players.filter((p) => p.g === g).length >= 8, g));
    dd.players.forEach((p) => assert.ok(p.st.length && p.tier >= 1 && p.tier <= 5, p.n));
  });
  test(`${sport}: daily puzzles are valid`, () => {
    dd.tl.forEach(([a, b]) => { assert.ok(dd.byName[a] && dd.byName[b] && a !== b); });
    dd.gr.slice(0, 80).forEach((g) => {
      const R = g.r.map((c) => S.crit(dd, c)), C = g.c.map((c) => S.crit(dd, c));
      R.forEach((x) => C.forEach((y) => assert.ok(S.cellAnswers(dd, x, y).length >= 2, g.r + " x " + g.c)));
    });
  });
  test(`${sport}: a season runs and the budget leaves room for a full roster`, () => {
    const cheap = dd.cfg.slots.map((g) => dd.players.filter((p) => p.g === g).sort((a, b) => SE.cost(a) - SE.cost(b))[0]);
    assert.ok(cheap.reduce((a, p) => a + SE.cost(p), 0) <= dd.cfg.cap - 4);
    const res = SE.simulate(dd, { starters: dd.cfg.slots.map((g, i) => dd.players.filter((p) => p.g === g)[i % 3]), bench: [] }, "t");
    assert.equal(res.wins + res.losses, dd.cfg.games);
  });
}
