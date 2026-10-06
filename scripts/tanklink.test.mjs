import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// tanklink.js is a browser script; its engine half exports through `module` when there is one. Load it in a sandbox.
const src = readFileSync("site/games/tanklink.js", "utf8");
const mod = { exports: {} };
vm.runInThisContext("(function (module) {" + src + "\n})")(mod);
const E = mod.exports;

const DAY0 = 2;   // 2026-10-06, the first day this game could ship
const WINNER = [];

// ---- a solver for the tests: aim exactly at each enemy, with a few angles and all weapons, and search the turns ----
function candidates(state, limit) {
  const out = [];
  state.tanks.forEach((t, i) => {
    if (i === 0 || t.armor <= 0) return;
    for (const w of ["heavy", "cluster", "shell"]) {
      if (E.ammoLeft(state, w) <= 0) continue;
      for (const elev of [45, 62, 78]) {
        const r = E.aimPower(state, 0, elev, t.x, w);
        if (r.err <= 14) out.push({ angle: elev, power: r.power, weapon: w, err: r.err });
      }
    }
  });
  out.sort((a, b) => a.err - b.err);
  return out.slice(0, limit);
}
function solve(state, depth = 0) {
  if (state.status === "won") return [];
  if (state.status === "lost" || depth >= E.MAX_SHOTS) return null;
  for (const c of candidates(state, 4)) {
    const next = E.clone(state);
    E.fire(next, c.angle, c.power, c.weapon);
    const rest = solve(next, depth + 1);
    if (rest) return [[c.angle, c.power, c.weapon]].concat(rest);
  }
  return null;
}

test("the engine does not read the clock or Math.random", () => {
  const engine = src.slice(0, src.indexOf("// ================================================================ page")).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.ok(!/Math\.random/.test(engine));
  assert.ok(!/\bDate\b|performance\.now|setTimeout|requestAnimationFrame/.test(engine));
});

test("the same day gives the same terrain, wind and tank positions", () => {
  const a = E.createRound(7), b = E.createRound(7), c = E.createRound(8);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a.h, c.h);
  assert.equal(a.h.length, E.W);
  assert.ok(a.h.every((v) => Number.isInteger(v) && v >= 0 && v < E.H));
});

test("sine series is accurate and angles are exact at the quarter turns", () => {
  assert.ok(Math.abs(E.sinDeg(30) - 0.5) < 1e-9);
  assert.ok(Math.abs(E.cosDeg(60) - 0.5) < 1e-9);
  assert.ok(Math.abs(E.sinDeg(90) - 1) < 1e-12);
  assert.ok(Math.abs(E.cosDeg(90)) < 1e-12);
  assert.ok(Math.abs(E.cosDeg(180) + 1) < 1e-12);
});

test("weekday twists set enemies, wind and gravity", () => {
  const want = { 0: 1, 1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 3 };
  for (let k = 0; k < 140; k++) {
    const idx = DAY0 + k, dow = E.dowOf(idx), s = E.createRound(idx, dow);
    assert.equal(s.tanks.length - 1, want[dow], "enemies on dow " + dow);
    assert.ok(s.tanks[0].x >= 60 && s.tanks[0].x <= 240, "you are in the left third");
    s.tanks.slice(1).forEach((t) => assert.ok(t.x >= 330 && t.x <= 750, "enemies are in the right two thirds"));
    if (dow === 5) assert.ok(s.wind >= 1 && s.wind <= 5, "tailwind blows toward the enemy");
    else if (dow === 2) assert.ok(Math.abs(s.wind) >= 4 && Math.abs(s.wind) <= 10, "strong wind");
    else assert.ok(s.wind >= -5 && s.wind <= 5);
    assert.equal(s.grav, dow === 3 ? 0.1 * 0.6 : 0.1);
  }
  // weekday 0 of the epoch week is the Sunday ridge: the middle is far higher than the tank pads
  const sun = E.createRound(0);
  assert.equal(E.dowOf(0), 0);
  const mid = Math.max(...sun.h.slice(340, 460));
  assert.ok(mid > Math.max(...sun.tanks.map((t) => sun.h[t.x])) + 60, "mountain day has a tall ridge");
});

test("tanks start on gentle ground", () => {
  for (let k = 0; k < 60; k++) {
    const s = E.createRound(DAY0 + k);
    s.tanks.forEach((t) => {
      for (let x = t.x - 18; x <= t.x + 18; x++) assert.ok(Math.abs(s.h[x] - s.h[t.x]) <= 2, "flat pad under a tank");
    });
  }
});

test("the damage formula: direct hits, falloff and the edge of the reach", () => {
  const s = E.createRound(DAY0);
  const t = s.tanks[1], c = E.tankCenter(s.h, t);
  const at = (dx, r) => E.blastFactor({ x: c.x + dx, y: c.y }, r, t, s.h);
  assert.equal(at(0, 26).f, 1);
  assert.equal(at(15, 26).f, 1);
  assert.equal(at(41, 26).hit, false);                 // reach = 26 + 15
  assert.ok(Math.abs(at(28, 26).f - 0.5) < 1e-9);       // halfway between 15 and 41
  assert.equal(Math.round(60 * at(0, 26).f), 60);       // shell, direct
  assert.equal(Math.round(100 * at(0, 44).f), 100);     // heavy, direct
  assert.equal(Math.round(100 * at(37, 44).f), 50);     // heavy, halfway along its reach (15..59)
});

test("a shell on the enemy does 60, a heavy kills, and ammunition is limited", () => {
  const s = E.createRound(DAY0), foe = s.tanks[1];
  let r = E.aimPower(s, 0, 45, foe.x, "shell");
  const a = E.clone(s);
  const res = E.fire(a, 45, r.power, "shell");
  assert.ok(res.dealt > 0 && res.dealt <= 60, "a shell does at most 60");
  assert.equal(res.outcome, "hit");
  const b = E.clone(s);
  r = E.aimPower(b, 0, 45, foe.x, "heavy");
  const hv = E.fire(b, 45, r.power, "heavy");
  assert.ok(hv.dealt > 60, "a close heavy does far more than a shell");
  // two heavies, one cluster per round
  const c = E.createRound(DAY0 + 1);
  c.tanks.forEach((t) => { t.armor = 100; });
  E.fire(c, 20, 10, "heavy"); E.fire(c, 20, 10, "heavy");
  assert.equal(E.ammoLeft(c, "heavy"), 0);
  assert.equal(E.fire(c, 20, 10, "heavy").ok, false);
  E.fire(c, 20, 10, "cluster");
  assert.equal(E.ammoLeft(c, "cluster"), 0);
  assert.equal(E.fire(c, 20, 10, "cluster").ok, false);
  assert.equal(E.ammoLeft(c, "shell"), 99);
});

test("a hit on you costs 20 to 40 and the enemy's error shrinks every round", () => {
  assert.ok(E.spread(2, 1) < E.spread(1, 1) && E.spread(5, 1) < E.spread(2, 1));
  assert.ok(E.spread(20, 1) >= E.AI.floor);
  let hits = 0;
  for (let k = 0; k < 120; k++) {
    const s = E.createRound(DAY0 + k);
    const res = E.fire(s, 20, 10, "shell");   // a harmless shot, so only the return fire matters
    res.returns.forEach((q) => { if (q.hit) { hits++; assert.ok(q.dmg >= 20 && q.dmg <= 40, "damage " + q.dmg); } });
  }
  assert.ok(hits > 5, "the enemy does hit sometimes");
});

test("crater carving lowers the ground, a heavy more than a shell, and never raises it", () => {
  const s = E.createRound(DAY0), x = 500, y = s.h[x];
  const a = s.h.slice(), b = s.h.slice();
  E.carve(a, x, y, 26); E.carve(b, x, y, 44);
  assert.ok(a[x] < s.h[x] && b[x] < a[x]);
  assert.ok(a[x] <= y - 25 && b[x] <= y - 43, "the floor is about one radius down");
  for (let i = 0; i < E.W; i++) { assert.ok(a[i] <= s.h[i] && b[i] <= s.h[i]); assert.ok(a[i] >= 0); }
  const outside = s.h.slice(0, x - 27).concat(s.h.slice(x + 27)), outsideA = a.slice(0, x - 27).concat(a.slice(x + 27));
  assert.deepEqual(outsideA, outside, "nothing changes outside the radius");
  // a blast in the air changes nothing
  const c = s.h.slice(); E.carve(c, x, y + 200, 26);
  assert.deepEqual(c, s.h);
  // a shell that lands changes the real round
  const r = E.createRound(DAY0), before = r.h.slice(), foe = r.tanks[1];
  const pw = E.aimPower(r, 0, 45, foe.x, "shell").power;
  E.fire(r, 45, pw, "shell");
  assert.ok(r.h.some((v, i) => v < before[i]));
});

test("wind moves where a shot lands", () => {
  const s = E.createRound(DAY0);
  s.tanks.slice(1).forEach((t) => { t.armor = 0; });   // nothing in the way to stop the shell early
  const land = (wind) => { const t = E.clone(s); t.wind = wind; return E.probe(t, 0, 50, 70, "shell").x; };
  const calm = land(0), tail = land(5), head = land(-5);
  assert.ok(tail > calm + 15, "a tailwind carries the shell further");
  assert.ok(head < calm - 15, "a headwind holds it back");
});

// play a few turns with aimed shots and return the shot list
function playSome(idx, turns) {
  const live = E.createRound(idx), saved = [];
  for (let n = 0; n < turns && live.status === "playing"; n++) {
    const foe = live.tanks.slice(1).find((t) => t.armor > 0);
    const w = n === 2 ? "heavy" : n === 3 ? "cluster" : "shell";
    const a = 40 + n * 4, p = E.aimPower(live, 0, a, foe.x + (n - 1) * 25, w).power;
    E.fire(live, a, p, w);
    saved.push([a, p, w]);
  }
  return { live, saved };
}

test("replaying a shot list is deterministic", () => {
  for (const idx of [DAY0, DAY0 + 4, DAY0 + 6, DAY0 + 10]) {
    const { saved } = playSome(idx, 5);
    const a = E.replay(idx, undefined, saved), b = E.replay(idx, undefined, saved);
    assert.equal(a.error, false);
    assert.deepEqual(a.state, b.state);
    assert.deepEqual(a.results, b.results);
  }
});

test("save and restore: the saved shot list rebuilds the exact round", () => {
  for (const idx of [DAY0, DAY0 + 3, DAY0 + 4, DAY0 + 6]) {
    const live = E.createRound(idx), saved = [];
    for (let n = 0; n < 5 && live.status === "playing"; n++) {
      const foe = live.tanks.slice(1).find((t) => t.armor > 0);
      const w = n === 2 ? "heavy" : n === 3 ? "cluster" : "shell";
      const a = 40 + n * 4, p = E.aimPower(live, 0, a, foe.x + (n - 1) * 25, w).power;
      E.fire(live, a, p, w);
      saved.push([a, p, w]);
      // after every shot, a reload from JSON gives the same state
      const back = E.replay(idx, undefined, JSON.parse(JSON.stringify(saved)));
      assert.equal(back.error, false);
      assert.deepEqual(back.state, live);
    }
  }
});

test("the share grid has one square per shot", () => {
  const s = E.createRound(DAY0);
  E.fire(s, 20, 10, "shell");
  E.fire(s, 45, E.aimPower(s, 0, 45, s.tanks[1].x, "shell").power, "shell");
  const q = E.squares(s);
  assert.equal(Array.from(q).length, s.shots.length);
  assert.ok(/^[■▣□]+$/.test(q));
  assert.equal(s.shots[0].outcome, "miss");
  assert.equal(s.shots[1].outcome, "hit");
});

test("you lose after eight shots, or at zero armor", () => {
  const s = E.createRound(DAY0);
  for (let i = 0; i < 8; i++) { assert.equal(s.status, "playing"); E.fire(s, 20, 10, "shell"); if (s.status !== "playing") break; }
  assert.notEqual(s.status, "playing");
  assert.equal(E.fire(s, 20, 10, "shell").ok, false);
  if (s.tanks[0].armor > 0) { assert.equal(s.status, "lost"); assert.equal(s.reason, "shots"); assert.equal(s.shots.length, 8); }
});

test("a known winning shot list wins, and replays to the same win", () => {
  const idx = DAY0 + 1, start = E.createRound(idx), list = solve(start);
  assert.ok(list && list.length >= 1 && list.length <= 8, "found a solution");
  WINNER.push(...list);
  const r = E.replay(idx, undefined, list);
  assert.equal(r.error, false);
  assert.equal(r.state.status, "won");
  assert.equal(E.enemiesLeft(r.state), 0);
  assert.ok(r.state.tanks[0].armor > 0);
  assert.deepEqual(r.state.shots.length, list.length);
});

test("every one of the next 400 days has a winning shot list of at most eight shots", () => {
  const bad = [], lens = {};
  for (let k = 0; k < 400; k++) {
    const idx = DAY0 + k, list = solve(E.createRound(idx));
    if (!list) { bad.push(idx); continue; }
    const r = E.replay(idx, undefined, list);
    if (r.state.status !== "won" || list.length > 8) bad.push(idx);
    lens[list.length] = (lens[list.length] || 0) + 1;
  }
  assert.deepEqual(bad, [], "unwinnable days: " + bad.join(", "));
});

test("a random first shot almost never wins outright (under 5 percent over 400 days)", (t0) => {
  // Every aimed shot at angles 10..85 (toward the enemies), power 10..100 in steps of 5, all three weapons.
  // A shell does at most 60, so it can never finish a 100-armor tank alone; heavy and cluster are run in full when they land close enough to kill (a heavy needs a blast within about 15 of the tank's centre).
  let tried = 0, killed = 0, worstDay = 0;
  for (let k = 0; k < 400; k++) {
    const idx = DAY0 + k, s = E.createRound(idx);
    let dayTried = 0, dayKilled = 0;
    for (let a = 10; a <= 85; a += 5) {
      for (let p = 10; p <= 100; p += 5) {
        for (const w of ["shell", "heavy", "cluster"]) {
          dayTried++;
          if (w === "shell") continue;
          const b = E.probe(s, 0, a, p, w);
          if (!b || !s.tanks.slice(1).some((t) => Math.abs(t.x - b.x) < (w === "heavy" ? 20 : 45))) continue;
          const t = E.clone(s);
          E.fire(t, a, p, w);
          if (t.status === "won") dayKilled++;
        }
      }
    }
    tried += dayTried; killed += dayKilled;
    worstDay = Math.max(worstDay, dayKilled / dayTried);
  }
  const rate = killed / tried;
  t0.diagnostic("first-shot kill rate " + (100 * rate).toFixed(2) + "% over " + tried + " shots; worst day " + (100 * worstDay).toFixed(2) + "%");
  assert.ok(rate < 0.05, "first-shot kill rate " + (100 * rate).toFixed(2) + "%");
  assert.ok(worstDay < 0.15, "worst single day " + (100 * worstDay).toFixed(2) + "%");
});
