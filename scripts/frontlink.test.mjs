import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// frontlink.js is a browser script; its engine section exports itself when `module` exists.
const mod = { exports: {} };
const file = new URL("../site/games/frontlink.js", import.meta.url);
vm.runInThisContext("(function (module) {" + readFileSync(file, "utf8") + "\n})")(mod);
const E = mod.exports;

const DAYS = 400;
const unit = (id, k, t, hp = 10) => ({ id, side: id[0], k, t, hp, done: false, cap: false });
// A flat all-plains battlefield with the given units, for rule tests. `edit` may change tiles first.
function field(units, edit) {
  const S = E.newGame(1);
  S.terrain = new Array(E.N).fill("p");
  if (edit) edit(S.terrain);
  S.units = units;
  S.mine = units.filter((u) => u.side === "p").length;
  return S;
}
const at = (r, c) => r * E.W + c;
const ground = (x) => x === "p" || x === "r" || x === "f";

test("the map is the same every time for a given day, and differs between days", () => {
  const seen = new Set();
  for (let i = 0; i < DAYS; i++) {
    const a = E.buildMap(i).join(""), b = E.buildMap(i).join("");
    assert.equal(a, b);
    assert.equal(a.length, 42);
    assert.match(a, /^[prfmw]+$/);
    seen.add(a);
  }
  assert.ok(seen.size > DAYS * 0.95, "maps should rarely repeat");
  assert.deepEqual(E.newGame(5).units.map((u) => [u.id, u.k, u.t]), E.newGame(5).units.map((u) => [u.id, u.k, u.t]));
});

test("every map has a land path between the HQs for infantry and for tanks, open ground around each HQ, and is mostly mirrored", () => {
  const walk = (t, ok) => {
    const seen = new Set([E.MY_HQ]), q = [E.MY_HQ];
    for (let i = 0; i < q.length; i++) {
      const a = q[i], r = Math.floor(a / 7), c = a % 7;
      for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nr = r + dr, nc = c + dc;
        if (nr < 0 || nr > 5 || nc < 0 || nc > 6) continue;
        const b = nr * 7 + nc;
        if (!seen.has(b) && ok(t[b])) { seen.add(b); q.push(b); }
      }
    }
    return seen.has(E.FOE_HQ);
  };
  for (let i = 0; i < DAYS; i++) {
    const t = E.buildMap(i);
    assert.ok(walk(t, (x) => x !== "w"), "infantry path, day " + i);
    assert.ok(walk(t, ground), "tank path, day " + i);
    for (let k = 0; k < 42; k++) {
      const near = E.dist(k, E.MY_HQ) <= 2 || E.dist(k, E.FOE_HQ) <= 2;
      if (near) assert.ok(ground(t[k]) || t[k] === "p", "open ground near an HQ, day " + i);
    }
    let same = 0;
    for (let k = 0; k < 42; k++) if (t[k] === t[41 - k]) same++;
    assert.ok(same >= (E.dowOf(i) === 0 ? 28 : 36), "map should be near-symmetric, day " + i + " (" + same + ")");   // Siege adds forest on the enemy side only
  }
});

test("twists follow the weekday and give the documented armies", () => {
  const names = [];
  for (let i = 0; i < 7; i++) names.push(E.twistFor(i).name);
  assert.deepEqual(names, ["Siege", "Standard", "Armor rush", "Artillery duel", "Mountain pass", "Fast start", "Double front"]);
  const count = (S, side) => S.units.filter((u) => u.side === side).map((u) => u.k).sort().join("");
  assert.equal(count(E.newGame(1), "p"), "AIT"); assert.equal(count(E.newGame(1), "e"), "AIT");
  assert.equal(count(E.newGame(2), "e"), "ITT"); assert.equal(count(E.newGame(2), "p"), "AIT");
  assert.equal(count(E.newGame(3), "p"), "AAI"); assert.equal(count(E.newGame(3), "e"), "AAI");
  assert.equal(count(E.newGame(6), "p"), "AIIT"); assert.equal(E.newGame(6).units[0].hp, 6);
  assert.equal(count(E.newGame(7), "p"), "AITT"); assert.equal(count(E.newGame(7), "e"), "AIT");
  const siege = E.newGame(7), art = siege.units.find((u) => u.side === "e" && u.k === "A");
  assert.equal(siege.terrain[art.t], "f");
  const col = (i) => [0, 1, 2, 3, 4, 5].map((r) => E.buildMap(i)[r * 7 + 3]);
  assert.ok(col(4).filter((x) => x === "m").length >= 2, "Mountain pass has a ridge");
  assert.ok(col(6).filter((x) => x === "w").length >= 2, "Double front has a river");
  for (let i = 0; i < DAYS; i++) {
    const S = E.newGame(i);
    S.units.forEach((u) => assert.ok(E.COST[u.k][S.terrain[u.t]], "units start on land they can stand on, day " + i));
    assert.equal(new Set(S.units.map((u) => u.t)).size, S.units.length);
  }
});

test("movement costs, terrain limits and blocking", () => {
  const S = field([unit("p0", "I", at(4, 1)), unit("p1", "T", at(5, 1)), unit("e0", "I", at(0, 6))], (t) => {
    t[at(4, 2)] = "f"; t[at(4, 3)] = "m"; t[at(4, 4)] = "w"; t[at(3, 1)] = "m";
  });
  const inf = S.units[0], tank = S.units[1];
  let R = E.reach(S, inf);
  assert.equal(R[at(4, 1)], 0, "may stay");
  assert.equal(R[at(4, 2)], 2, "forest costs 2");
  assert.equal(R[at(3, 1)], 3, "a mountain costs infantry 3");
  assert.equal(R[at(4, 4)], undefined, "water is blocked");
  assert.equal(R[at(4, 3)], undefined, "mountain after forest is too far (2 + 3)");
  assert.equal(R[at(5, 1)], undefined, "cannot stop on a friend");
  assert.equal(R[at(5, 2)], 2);
  R = E.reach(S, tank);
  assert.equal(R[at(3, 1)], undefined, "tanks cannot enter mountains");
  assert.equal(R[at(4, 2)], 3, "forest costs a tank 2 on top of one step");
  assert.equal(E.reach(S, tank)[at(5, 5)], 4, "tank moves 4 on plains");
  assert.equal(E.reach(S, tank)[at(5, 6)], undefined);
  // artillery moves 2, never onto mountains
  const A = unit("p2", "A", at(2, 3)); S.units.push(A); S.terrain[at(2, 4)] = "m"; S.terrain[at(2, 2)] = "f";
  R = E.reach(S, A);
  assert.equal(R[at(2, 4)], undefined); assert.equal(R[at(2, 2)], 2); assert.equal(R[at(2, 1)], undefined);
  // an enemy blocks the way and the tile; a friend can be passed
  const E1 = unit("e1", "T", at(5, 2)); S.units.push(E1);
  R = E.reach(S, tank);
  assert.equal(R[at(5, 2)], undefined, "cannot enter an enemy tile");
  assert.equal(R[at(5, 3)], undefined, "the way round is blocked by the mountain and forest");
  const T2 = unit("p3", "T", at(5, 0)); S.units.push(T2);
  assert.equal(E.reach(S, T2)[at(5, 1)], undefined, "friend's tile is not a stopping place");
  assert.ok(E.reach(S, T2)[at(4, 1)] === undefined, "occupied by your infantry");
  assert.equal(E.reach(S, T2)[at(3, 0)], 2);
  // fast start gives +1 on day 1 only
  const F = E.newGame(5); const tk = F.units.find((u) => u.side === "p" && u.k === "T");
  const day1 = Object.keys(E.reach(F, tk)).length; F.day = 2;
  assert.ok(Object.keys(E.reach(F, tk)).length < day1, "fast start reaches further on day 1 only");
});

test("damage formula and the base table", () => {
  const d = E.damage;
  assert.equal(d("T", 10, "I", 10, 0), 7);
  assert.equal(d("T", 10, "I", 10, 1), 6);      // 7 * 0.9 = 6.3
  assert.equal(d("T", 10, "I", 10, 2), 6);      // 7 * 0.8 = 5.6
  assert.equal(d("T", 5, "I", 10, 0), 4);       // 3.5 rounds up
  assert.equal(d("T", 10, "I", 5, 2), 6);       // cover counts for less when the defender is hurt: 7 * 0.9
  assert.equal(d("I", 10, "T", 10, 0), 1);
  assert.equal(d("T", 10, "T", 10, 0), 5);
  assert.equal(d("T", 10, "A", 10, 0), 7);
  assert.equal(d("I", 10, "A", 10, 0), 6);
  assert.equal(d("I", 10, "I", 10, 0), 5);
  assert.equal(d("A", 10, "I", 10, 0), 5);
  assert.equal(d("A", 10, "T", 10, 0), 6);
  assert.equal(d("A", 10, "A", 10, 0), 5);
  assert.equal(d("A", 3, "I", 10, 0), 2);       // 1.5 rounds up
});

test("counterattacks: only from inside the defender's own range, with the HP it has left", () => {
  // tank hits adjacent infantry: 7 dealt, 3 left, 3 * 1/10 rounds to no counter damage
  let S = field([unit("p0", "T", at(3, 3)), unit("e0", "I", at(3, 4)), unit("e1", "T", at(0, 6))]);
  let pv = E.preview(S, S.units[0], at(3, 3), S.units[1]);
  assert.deepEqual([pv.dealt, pv.left, pv.counter], [7, 3, 0]);
  // infantry on infantry: 5 dealt, the survivor answers with 5 HP for round(2.5) = 3
  S = field([unit("p0", "I", at(3, 3)), unit("e0", "I", at(3, 4)), unit("e1", "T", at(0, 6))]);
  pv = E.preview(S, S.units[0], at(3, 3), S.units[1]);
  assert.deepEqual([pv.dealt, pv.left, pv.counter], [5, 5, 3]);
  // cover helps the defender and the attacker's own tile counts when it is countered
  S = field([unit("p0", "I", at(3, 3)), unit("e0", "I", at(3, 4)), unit("e1", "T", at(0, 6))], (t) => { t[at(3, 4)] = "m"; t[at(3, 3)] = "f"; });
  pv = E.preview(S, S.units[0], at(3, 3), S.units[1]);
  assert.equal(pv.dealt, 4);                    // 5 * 0.8 = 4
  assert.equal(pv.left, 6);
  assert.equal(pv.counter, 3);                  // 5 * 0.6 * 0.9 -> 2.7 -> 3
  // artillery never answers an adjacent attacker, even when it survives
  S = field([unit("p0", "T", at(3, 3)), unit("e0", "A", at(3, 4)), unit("e1", "T", at(0, 6))]);
  pv = E.preview(S, S.units[0], at(3, 3), S.units[1]);
  assert.deepEqual([pv.dealt, pv.left, pv.counter], [7, 3, 0]);
  // artillery does answer other artillery at range 2 to 3, and a tank cannot answer artillery at all
  S = field([unit("p0", "A", at(3, 1)), unit("e0", "A", at(3, 3)), unit("e1", "T", at(3, 4))]);
  pv = E.preview(S, S.units[0], at(3, 1), S.units[1]);
  assert.deepEqual([pv.dealt, pv.left, pv.counter], [5, 5, 3]);
  pv = E.preview(S, S.units[0], at(3, 1), S.units[2]);
  assert.deepEqual([pv.dealt, pv.counter], [6, 0]);
  // a kill gets no answer
  S = field([unit("p0", "T", at(3, 3)), unit("e0", "I", at(3, 4), 6), unit("e1", "T", at(0, 6))]);
  pv = E.preview(S, S.units[0], at(3, 3), S.units[1]);
  assert.ok(pv.kills && pv.counter === 0 && pv.dealt === 6, "damage is capped at the defender's HP");
});

test("artillery: range 2 to 3, and it cannot move and fire in the same turn", () => {
  const S = field([unit("p0", "A", at(3, 3)), unit("e0", "I", at(3, 4)), unit("e1", "I", at(3, 5)), unit("e2", "T", at(3, 6)), unit("e3", "T", at(0, 0))]);
  const A = S.units[0];
  assert.deepEqual(E.targets(S, A, at(3, 3)).map((u) => u.id), ["e1", "e2"], "distance 1 is too close, 2 and 3 are in range");
  assert.equal(E.targets(S, A, at(3, 2)).length, 0, "after moving, nothing can be targeted");
  let r = E.act(S, "p0", at(3, 2), "e1");
  assert.equal(r.ok, false);
  r = E.act(S, "p0", at(3, 3), "e0");
  assert.equal(r.ok, false, "adjacent target is out of range");
  assert.equal(E.preview(S, A, at(3, 3), S.units[2]).dealt, 5);
  r = E.act(S, "p0", at(3, 3), "e1");
  assert.equal(r.ok, true);
});

test("actions are validated", () => {
  const S = E.newGame(1), p0 = S.units[0];
  assert.equal(E.act(S, "e0", p0.t, null).ok, false, "not your unit");
  assert.equal(E.act(S, "p0", at(0, 0), null).ok, false, "out of reach");
  assert.equal(E.act(S, "p0", p0.t, "e0").ok, false, "target out of range");
  assert.equal(E.act(S, "p0", p0.t, null).ok, true);
  assert.equal(E.act(S, "p0", p0.t, null).ok, false, "a unit acts once a day");
});

test("capture: an Infantry that ends on the enemy HQ and survives the enemy turn wins", () => {
  const S = field([unit("p0", "I", at(1, 6)), unit("e0", "A", at(5, 6))]);
  assert.equal(E.act(S, "p0", E.FOE_HQ, null).ok, true);
  assert.equal(S.over, true); assert.equal(S.won, true); assert.equal(S.reason, "captured"); assert.equal(S.days, 1);
  // killed during the enemy turn: no capture
  const T = field([unit("p0", "I", at(1, 6)), unit("p1", "T", at(5, 0)), unit("e0", "T", at(0, 5)), unit("e1", "T", at(1, 5))]);
  E.act(T, "p0", E.FOE_HQ, null);
  assert.equal(T.over, false, "the day is not over until every unit has acted");
  E.endDay(T);
  assert.equal(T.units.some((u) => u.id === "p0"), false);
  assert.equal(T.over, false); assert.equal(T.day, 2);
  // only Tanks and Artillery cannot capture
  const U = field([unit("p0", "T", at(1, 6)), unit("e0", "A", at(5, 6))]);
  E.act(U, "p0", E.FOE_HQ, null);
  assert.equal(U.over, false);
});

test("capture: the enemy Infantry takes your HQ the same way", () => {
  const S = field([unit("p0", "T", at(0, 0)), unit("e0", "I", at(4, 0))]);
  E.endDay(S);
  const e = S.units.find((u) => u.id === "e0");
  assert.equal(e.t, E.MY_HQ); assert.equal(e.cap, true); assert.equal(S.over, false);
  assert.equal(S.day, 2);
  E.endDay(S);                        // you did not dislodge it
  assert.equal(S.over, true); assert.equal(S.won, false); assert.equal(S.reason, "captured"); assert.equal(S.days, 2);
});

test("win and lose by destruction, and by running out of days", () => {
  const S = field([unit("p0", "T", at(3, 3)), unit("e0", "I", at(3, 4), 5)]);
  E.act(S, "p0", at(3, 3), "e0");
  assert.equal(S.won, true); assert.equal(S.reason, "destroyed");
  const L = field([unit("p0", "I", at(0, 0), 1), unit("e0", "T", at(0, 1))]);
  E.endDay(L);
  assert.equal(L.won, false); assert.equal(L.reason, "wiped"); assert.equal(L.lost, 1);
  const D = field([unit("p0", "T", at(0, 0)), unit("e0", "A", at(5, 6))], (t) => { t[at(4, 6)] = "w"; t[at(5, 5)] = "w"; });
  for (let i = 0; i < 5; i++) { E.endDay(D); assert.equal(D.over, false); }
  E.endDay(D);
  assert.equal(D.over, true); assert.equal(D.won, false); assert.equal(D.days, 6); assert.equal(D.reason, "days");
});

const sig = (S) => JSON.stringify([S.day, S.over, S.won, S.days, S.lost, S.units.map((u) => [u.id, u.t, u.hp, u.done, u.cap]), S.dayStats]);

// A simple scripted player: the first listed attack, else the first reachable tile nearest the enemy HQ.
function scripted(S, moves) {
  for (let guard = 0; guard < 80 && !S.over; guard++) {
    const u = S.units.find((x) => x.side === "p" && !x.done);
    if (!u) break;
    const R = E.reach(S, u);
    let best = null;
    for (const k of Object.keys(R)) {
      const to = +k, tg = E.targets(S, u, to)[0];
      const score = (tg ? 100 : 0) - E.dist(to, E.FOE_HQ);
      if (!best || score > best.score) best = { to, tg, score };
    }
    const m = [u.id, best.to, best.tg ? best.tg.id : null];
    assert.ok(E.act(S, m[0], m[1], m[2]).ok);
    moves.push(m);
  }
}

test("the enemy turn is deterministic, and a saved move list replays to the same state", () => {
  for (let i = 0; i < 80; i++) {
    const A = E.newGame(i), B = E.newGame(i), ma = [], mb = [];
    scripted(A, ma); scripted(B, mb);
    assert.equal(sig(A), sig(B), "same moves, same result, day " + i);
    assert.deepEqual(ma, mb);
    const rp = E.replay(i, JSON.parse(JSON.stringify(ma)));
    assert.equal(rp.error, undefined);
    assert.equal(sig(rp.S), sig(A), "replay matches, day " + i);
    // stopping part way and replaying gives the same intermediate state
    const part = ma.slice(0, 4), X = E.newGame(i);
    const rp2 = E.replay(i, part);
    for (const m of part) E.act(X, m[0], m[1], m[2]);
    assert.equal(sig(rp2.S), sig(X));
  }
  assert.equal(E.replay(1, [["p0", 9999, null]]).error, "That tile is out of reach.");
  assert.ok(E.replay(1, [["nope", 1, null]]).error);
});

test("each enemy unit acts once per turn, in a fixed order, one log line each", () => {
  const S = E.newGame(1);
  const ev = E.endDay(S);
  const lines = ev.filter((e) => e.side === "e");
  assert.equal(lines.length, 3);
  assert.deepEqual(lines.map((e) => e.text.split(" ")[1]), ["Infantry", "Tank", "Artillery"]);
  assert.equal(S.day, 2);
  // an enemy Infantry that cannot be stopped heads for your HQ
  const R = field([unit("p0", "T", at(0, 0)), unit("e0", "I", at(2, 4))]);
  E.endDay(R);
  assert.ok(E.dist(R.units[1].t, E.MY_HQ) < E.dist(at(2, 4), E.MY_HQ));
});

test("share text has the documented shape", () => {
  const S = E.newGame(2);
  S.over = true; S.won = true; S.days = 4; S.lost = 1;
  S.dayStats = [{ kills: 0, hit: false }, { kills: 0, hit: true }, { kills: 1, hit: true }, { kills: 2, hit: true }];
  assert.equal(E.shareText(S), "Frontlink 3 4/6\n\n□▣■■\nUnits lost 1 of 3\n\nhttps://purplelink.llc/games/frontlink/");
  S.won = false; S.days = 6; S.mine = 3; S.lost = 3;
  S.dayStats = [{ kills: 0, hit: false }, { kills: 0, hit: false }, { kills: 0, hit: true }, { kills: 0, hit: false }, { kills: 0, hit: false }, { kills: 1, hit: true }];
  assert.equal(E.shareText(S), "Frontlink 3 X/6\n\n□□▣□□■\nUnits lost 3 of 3\n\nhttps://purplelink.llc/games/frontlink/");
});

test("a player who never moves and only ends the day loses on each of the next " + DAYS + " days", () => {
  const reasons = {};
  for (let i = 0; i < DAYS; i++) {
    const S = E.newGame(i);
    for (let n = 0; n < 8 && !S.over; n++) E.endDay(S);
    assert.equal(S.over, true); assert.equal(S.won, false, "naive plan lost, day " + i);
    reasons[S.reason] = true;
  }
  assert.ok(Object.keys(reasons).length >= 2);
});

// ---- a bounded search, to show every day can be won inside six days ----
const VAL = { I: 1, T: 2.5, A: 2 };
function rate(S) {
  if (S.over) return S.won ? 1e6 - S.days * 1000 : -1e6;
  const foes = S.units.filter((u) => u.side === "e"), mine = S.units.filter((u) => u.side === "p");
  let v = 0;
  for (const u of mine) v += u.hp * VAL[u.k];
  for (const u of foes) { v -= u.hp * VAL[u.k] * 1.4; if (u.cap) v -= 80; if (u.k === "I") v += 0.5 * E.dist(u.t, E.MY_HQ); }
  for (const u of mine) {
    let d = 99;
    for (const f of foes) d = Math.min(d, E.dist(u.t, f.t));
    v -= 0.3 * d;
    if (u.k === "I") v -= 0.2 * E.dist(u.t, E.FOE_HQ);
    if (u.cap) v += 20;
  }
  return v;
}
function options(S, u, K) {
  const R = E.reach(S, u), out = [];
  for (const k of Object.keys(R)) {
    const to = +k;
    out.push([u.id, to, null]);
    for (const v of E.targets(S, u, to)) out.push([u.id, to, v.id]);
  }
  const scored = out.map((m) => { const C = E.clone(S); E.act(C, m[0], m[1], m[2]); return { m, C, s: rate(C) }; });
  scored.sort((a, b) => b.s - a.s);
  return scored.slice(0, K);
}
function search(idx, B, K) {
  let layer = [{ S: E.newGame(idx), moves: [] }];
  for (let day = 1; day <= E.MAXDAY; day++) {
    let frontier = layer; const next = [], seen = new Set();
    for (let step = 0; step < 6 && frontier.length; step++) {
      const cand = [];
      for (const node of frontier) {
        const todo = node.S.units.filter((u) => u.side === "p" && !u.done);
        for (const u of todo) for (const o of options(node.S, u, K)) {
          const key = o.C.day + "|" + o.C.units.map((x) => x.id + x.t + ":" + x.hp + (x.done ? "d" : "") + (x.cap ? "c" : "")).join(",");
          if (seen.has(key)) continue;
          seen.add(key);
          const moves = node.moves.concat([o.m]);
          if (o.C.over && o.C.won) return moves;
          cand.push({ S: o.C, moves, s: rate(o.C) });
        }
        if (todo.length && step > 0) {
          const C = E.clone(node.S); E.endDay(C);
          const moves = node.moves.concat([["end"]]);
          if (C.over && C.won) return moves;
          next.push({ S: C, moves, s: rate(C) });
        }
      }
      cand.sort((a, b) => b.s - a.s);
      const stay = [];
      for (const c of cand) (c.S.over || c.S.day !== day ? next : stay).push(c);
      frontier = stay.slice(0, B * 2);
    }
    next.sort((a, b) => b.s - a.s);
    layer = next.filter((n) => !n.S.over).slice(0, B);
    if (!layer.length) return null;
  }
  return null;
}

test("a winning plan of at most six days exists on each of the next " + DAYS + " days", { timeout: 600000 }, () => {
  const hist = {};
  for (let i = 0; i < DAYS; i++) {
    const moves = search(i, 8, 6) || search(i, 40, 10) || search(i, 300, 16);
    assert.ok(moves, "no winning plan found for day " + i + " (" + E.twistFor(i).name + ")");
    const rp = E.replay(i, moves);
    assert.equal(rp.error, undefined, "plan replays, day " + i);
    assert.equal(rp.S.won, true); assert.ok(rp.S.days >= 1 && rp.S.days <= 6);
    hist[rp.S.days] = (hist[rp.S.days] || 0) + 1;
  }
  assert.ok(Object.keys(hist).every((d) => d >= 2), "no day is won in a single turn");
});
