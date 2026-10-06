/* Tanklink: a daily artillery duel. Everyone gets the same map each day: seeded terrain, wind and gravity, one to three
   enemy tanks. Set an angle, a power and a weapon, then fire. Every enemy still standing fires back once. Eight shots,
   100 armor. The first half of this file is the pure simulation (no DOM, no clock, no Math.random), so a saved shot list
   replays to exactly the same round. The second half is the page. */
(function () {
  "use strict";

  // ================================================================ engine
  var E = (function () {
    var W = 800, H = 400;           // logical field size; y counts up from the bottom edge
    var MAX_SHOTS = 8, VERSION = 1;
    var TANK_R = 15, TANK_UP = 7;   // a tank's hit circle: radius 15, centred 7 above the ground column it sits on
    var MUZZLE = 16, PIVOT = 9;     // the barrel tip is 16 from the pivot, which is 9 above the ground
    var NEAR = 90;                  // "close" for the share grid: about three tank widths (a tank is 30 wide)
    var SPEED = 0.1;                // launch speed per point of power, in field units per tick
    var GRAV = 0.1;                 // downward acceleration per tick squared
    var WIND_K = 0.0025;            // sideways acceleration per point of wind
    var DT = 0.5;                   // fixed time step: two steps per tick
    var MAX_STEPS = 6000;
    var SPREAD = 0.5;               // cluster bomblets leave the apex with this much sideways speed apart
    var EPOCH_DOW = 0;              // the daily epoch (2026-10-04) is a Sunday

    // base is the damage of a direct hit on an enemy tank; r is the crater radius; ammo 0 means unlimited
    var WEAPONS = {
      shell: { id: "shell", name: "Shell", r: 26, base: 60, ammo: 0 },
      heavy: { id: "heavy", name: "Heavy", r: 44, base: 100, ammo: 2 },
      cluster: { id: "cluster", name: "Cluster", r: 20, base: 40, ammo: 1 }   // r and base are per bomblet; three bomblets
    };
    var WEAPON_IDS = ["shell", "heavy", "cluster"];

    // Weekday twists, by Date.getDay() (Sunday = 0).
    var TWISTS = {
      0: { name: "Mountain", text: "A tall ridge stands in the middle of the field. Lob your shells over it.", enemies: 1, ridge: true },
      1: { name: "Standard", text: "One enemy. Wind and gravity are as shown.", enemies: 1 },
      2: { name: "Strong wind", text: "The wind is twice as strong today.", enemies: 1, windMul: 2 },
      3: { name: "Moon gravity", text: "Gravity is 0.6 of normal, so shells fly higher and farther.", enemies: 1, grav: 0.6 },
      4: { name: "Two enemies", text: "Two enemy tanks, and both fire back after each of your shots.", enemies: 2 },
      5: { name: "Tailwind day", text: "The wind always blows toward the enemy.", enemies: 1, tail: true },
      6: { name: "Three enemies", text: "Three enemy tanks, and all of them fire back after each of your shots.", enemies: 3 }
    };

    // ---- numbers that must match on every device ----
    // Math.sin can differ in the last digit between browsers, so the map uses this series (only + - * /).
    var PI = 3.141592653589793, TWO_PI = 6.283185307179586, HALF_PI = 1.5707963267948966;
    function sinRad(x) {
      x = x - TWO_PI * Math.floor(x / TWO_PI);
      if (x > PI) x -= TWO_PI;
      if (x > HALF_PI) x = PI - x; else if (x < -HALF_PI) x = -PI - x;
      var q = x * x;
      return x * (1 + q * (-1 / 6 + q * (1 / 120 + q * (-1 / 5040 + q * (1 / 362880 + q * (-1 / 39916800 + q * (1 / 6227020800 + q * (-1 / 1307674368000 + q * (1 / 355687428096000)))))))));
    }
    function sinDeg(d) { return sinRad(d * (PI / 180)); }
    function cosDeg(d) { return sinRad((90 - d) * (PI / 180)); }

    function mulberry32(a) {
      return function () {
        a = (a + 0x6D2B79F5) | 0;
        var t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }
    function hashDay(idx) { return (Math.imul((idx | 0) + 7919, 2654435761) ^ 0x5a17c3d1) >>> 0; }
    function mixSeed(seed, k) { return (Math.imul(seed ^ Math.imul(k + 1, 0x9E3779B1), 0x85ebca6b) ^ (seed >>> 7)) >>> 0; }

    function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
    function dowOf(idx) { return (((EPOCH_DOW + idx) % 7) + 7) % 7; }

    // ---- terrain ----
    function smooth(t) { return t * t * (3 - 2 * t); }

    // Gentle hills from four sine layers; a flat pad under every tank so nobody starts on a cliff; a ridge on Sundays.
    function makeTerrain(rnd, xs, tw) {
      var base = 120 + Math.floor(rnd() * 50), amp = [34, 20, 10, 5], len = [520, 300, 170, 90], ph = [], i, x;
      for (i = 0; i < 4; i++) {
        amp[i] = amp[i] * (0.7 + rnd() * 0.6);
        len[i] = len[i] * (0.8 + rnd() * 0.4);
        ph.push(rnd() * TWO_PI);
      }
      var ridgeAt = 380 + Math.floor(rnd() * 41), ridgeH = 100 + rnd() * 30, ridgeHalf = 95;
      var h = [];
      for (x = 0; x < W; x++) {
        var v = base;
        for (i = 0; i < 4; i++) v += amp[i] * sinRad(TWO_PI * x / len[i] + ph[i]);
        if (tw.ridge) {
          var t = 1 - Math.abs(x - ridgeAt) / ridgeHalf;
          if (t > 0) v += ridgeH * smooth(t);
        }
        h.push(clamp(v, 30, 330));
      }
      // the enemies share one level plateau; you get your own
      var foeLevel = 0, i2;
      for (i2 = 1; i2 < xs.length; i2++) foeLevel += h[xs[i2]] / (xs.length - 1);
      var out = h.slice();
      xs.forEach(function (tx, k) {
        var pad = k === 0 ? h[tx] : foeLevel;
        for (x = Math.max(0, tx - 48); x <= Math.min(W - 1, tx + 48); x++) {
          var dx = Math.abs(x - tx), w = dx <= 20 ? 1 : 1 - smooth((dx - 20) / 28);
          out[x] = pad * w + out[x] * (1 - w);
        }
      });
      return out.map(function (v) { return Math.round(v); });
    }

    function groundAt(h, x) {
      if (x <= 0) return h[0];
      if (x >= W - 1) return h[W - 1];
      var i = Math.floor(x), f = x - i;
      return h[i] + (h[i + 1] - h[i]) * f;
    }

    // Remove a circle from the ground. Columns cut through by the circle drop to its floor; columns above it cave in by the
    // circle's height there. Heights stay whole numbers.
    function carve(h, cx, cy, r) {
      var x0 = Math.max(0, Math.ceil(cx - r)), x1 = Math.min(W - 1, Math.floor(cx + r)), x;
      for (x = x0; x <= x1; x++) {
        var dx = x - cx, d2 = r * r - dx * dx;
        if (d2 < 0) continue;
        var d = Math.sqrt(d2), bottom = cy - d, top = cy + d;
        if (h[x] >= top) h[x] = Math.max(0, Math.round(h[x] - 2 * d));
        else if (h[x] > bottom) h[x] = Math.max(0, Math.round(bottom));
      }
    }

    function tankCenter(h, t) { return { x: t.x, y: h[t.x] + TANK_UP }; }

    // ---- a round ----
    function createRound(idx, dow) {
      if (dow === undefined) dow = dowOf(idx);
      var tw = TWISTS[dow], seed = hashDay(idx), rnd = mulberry32(seed), i;
      var u = rnd(), sg = rnd(), wind;
      if (tw.tail) wind = 1 + Math.floor(u * 5);
      else if (tw.windMul) wind = (sg < 0.5 ? -1 : 1) * (2 + Math.floor(u * 4)) * tw.windMul;
      else wind = Math.floor(u * 11) - 5;
      var px = 60 + Math.floor(rnd() * 181);
      // Enemies stand together on the right: the first anywhere in the range, the rest 40 to 65 units further on.
      var n = tw.enemies, lo = tw.ridge ? 560 : 330, hi = 750, gaps = [0], xs = [px], gx = 0;
      for (i = 1; i < n; i++) { gx += 40 + Math.floor(rnd() * 26); gaps.push(gx); }
      var ex = Math.floor(lo + rnd() * (hi - gx - lo));
      for (i = 0; i < n; i++) xs.push(ex + gaps[i]);
      var h = makeTerrain(rnd, xs, tw);
      var tanks = xs.map(function (x, k) { return { x: x, armor: 100, aim: k === 0 ? 45 : 135 }; });
      return {
        v: VERSION, idx: idx, dow: dow, seed: seed, twist: tw.name, wind: wind, grav: GRAV * (tw.grav || 1),
        h: h, tanks: tanks, shots: [], status: "playing", reason: ""
      };
    }

    function clone(state) { return JSON.parse(JSON.stringify(state)); }
    function alive(t) { return t.armor > 0; }
    function enemiesLeft(state) { return state.tanks.slice(1).filter(alive).length; }
    function used(state, weapon) { return state.shots.filter(function (s) { return s.weapon === weapon; }).length; }
    function ammoLeft(state, weapon) { var w = WEAPONS[weapon]; return w.ammo ? w.ammo - used(state, weapon) : 99; }

    // ---- one projectile, from launch to its end ----
    // Ends in a boom {x, y}, in a split (cluster apex) or out of the field. rec = keep the path (one point per tick).
    function flight(h, targets, grav, wind, x, y, vx, vy, split, rec) {
      var ax = wind * WIND_K, path = rec ? [[x, y]] : null, i, k;
      for (i = 1; i <= MAX_STEPS; i++) {
        vx += ax * DT; vy -= grav * DT;
        x += vx * DT; y += vy * DT;
        if (rec && (i & 1) === 0) path.push([x, y]);
        if (x < 0 || x > W - 1) { if (rec) path.push([x, y]); return { path: path, out: true }; }
        for (k = 0; k < targets.length; k++) {
          var c = tankCenter(h, targets[k]), dx = x - c.x, dy = y - c.y;
          if (dx * dx + dy * dy <= TANK_R * TANK_R) { if (rec) path.push([x, y]); return { path: path, boom: { x: x, y: y } }; }
        }
        var g = groundAt(h, x);
        if (y <= g) { y = g; if (rec) path.push([x, y]); return { path: path, boom: { x: x, y: y } }; }
        if (split && vy <= 0) { if (rec) path.push([x, y]); return { path: path, split: { x: x, y: y, vx: vx, vy: vy } }; }
      }
      return { path: path, out: true };
    }

    function launch(state, by, angle, power) {
      var t = state.tanks[by], g = state.h[t.x], v = power * SPEED;
      return { x: t.x + MUZZLE * cosDeg(angle), y: g + PIVOT + MUZZLE * sinDeg(angle), vx: v * cosDeg(angle), vy: v * sinDeg(angle) };
    }
    function targetsFor(state, by) { return by === 0 ? state.tanks.slice(1).filter(alive) : [state.tanks[0]].filter(alive); }

    // Where a shot would explode, without changing anything: {x, y} or null when it leaves the field.
    // A cluster reports where its middle bomblet lands.
    function probe(state, by, angle, power, weapon) {
      var s = launch(state, by, angle, power), tg = targetsFor(state, by);
      var r = flight(state.h, tg, state.grav, state.wind, s.x, s.y, s.vx, s.vy, weapon === "cluster", false);
      if (r.split) r = flight(state.h, tg, state.grav, state.wind, r.split.x, r.split.y, r.split.vx, r.split.vy, false, false);
      return r.boom || null;
    }

    // The power (10..100) whose shot lands closest to targetX at this angle, and how far off it lands.
    function aimPower(state, by, angle, targetX, weapon) {
      weapon = weapon || "shell";
      var best = { power: 10, err: 1e9 }, p;
      function tryP(q) {
        var b = probe(state, by, angle, q, weapon), e = b ? Math.abs(b.x - targetX) : 1e9;
        if (e < best.err) best = { power: q, err: e };
      }
      for (p = 10; p <= 100; p += 3) tryP(p);
      var c = best.power;
      for (p = Math.max(10, c - 3); p <= Math.min(100, c + 3); p++) tryP(p);
      return best;
    }

    // A short stub of the opening path (no terrain), for the dotted aim hint: n points, four ticks apart.
    function previewPoints(state, angle, power, n) {
      var s = launch(state, 0, angle, power), ax = state.wind * WIND_K, pts = [], i, k;
      var x = s.x, y = s.y, vx = s.vx, vy = s.vy;
      for (i = 0; i < n; i++) {
        for (k = 0; k < 8; k++) { vx += ax * DT; vy -= state.grav * DT; x += vx * DT; y += vy * DT; }
        pts.push([x, y]);
      }
      return pts;
    }

    // ---- damage ----
    // One formula. d is the distance from the blast to the tank's centre and reach = crater radius + tank radius.
    // Inside the tank (d <= 15) the blast counts in full; at reach it counts for nothing; in between it falls off in a straight line.
    //   f = 1                                 when d <= 15
    //   f = (reach - d) / (reach - 15)        when 15 < d < reach
    //   f = 0                                 when d >= reach
    // Against an enemy: damage = round(base * f), where base is 60 (Shell), 100 (Heavy) or 40 (each Cluster bomblet).
    // Against you: damage = 20 + round(20 * f), so a hit costs 20 to 40.
    function blastFactor(boom, r, tank, h) {
      var c = tankCenter(h, tank), dx = c.x - boom.x, dy = c.y - boom.y, d = Math.sqrt(dx * dx + dy * dy), reach = r + TANK_R;
      if (d >= reach) return { f: 0, d: d, hit: false };
      return { f: d <= TANK_R ? 1 : (reach - d) / (reach - TANK_R), d: d, hit: true };
    }

    function explode(state, phase, by, boom, w) {
      var rec = { x: boom.x, y: boom.y, r: w.r, hits: [], near: [] };
      targetsFor(state, by).forEach(function (t) {
        var b = blastFactor(boom, w.r, t, state.h);
        rec.near.push({ t: state.tanks.indexOf(t), d: b.d, dx: boom.x - t.x });   // measured before the ground changes
        if (!b.hit) return;
        var dmg = by === 0 ? Math.round(w.base * b.f) : 20 + Math.round(20 * b.f);
        dmg = Math.min(dmg, t.armor);
        if (dmg > 0) { t.armor -= dmg; rec.hits.push({ t: state.tanks.indexOf(t), dmg: dmg }); }
      });
      carve(state.h, boom.x, boom.y, w.r);
      phase.booms.push(rec);
      return rec;
    }

    // One tank fires: flights are the paths for animation (a cluster has two groups: the shell, then its bomblets).
    function runPhase(state, by, angle, power, weapon) {
      var w = WEAPONS[weapon], s = launch(state, by, angle, power), phase = { by: by, angle: angle, power: power, weapon: weapon, groups: [], booms: [], armor: null };
      state.tanks[by].aim = angle;
      var first = flight(state.h, targetsFor(state, by), state.grav, state.wind, s.x, s.y, s.vx, s.vy, weapon === "cluster", true);
      if (first.split) {
        phase.groups.push([{ path: first.path, boom: null }]);
        var group = [];
        [-1, 0, 1].forEach(function (k) {
          var f = flight(state.h, targetsFor(state, by), state.grav, state.wind, first.split.x, first.split.y, first.split.vx + k * SPREAD, first.split.vy, false, true);
          if (f.boom) { f.boomInfo = explode(state, phase, by, f.boom, w); }
          group.push({ path: f.path, boom: f.boom || null });
        });
        phase.groups.push(group);
      } else {
        if (first.boom) explode(state, phase, by, first.boom, w);
        phase.groups.push([{ path: first.path, boom: first.boom || null }]);
      }
      phase.armor = state.tanks.map(function (t) { return t.armor; });
      return phase;
    }

    // ---- the enemy ----
    // Each enemy works out the exact shot that would land on your tank (it simulates the real wind and gravity), then aims
    // off by a seeded distance. The most it can be off by is 160 units in round 1 and shrinks by 15% every round, never below 20.
    var AI = { e0: 160, decay: 0.85, floor: 20, crowd: 0.5 };
    function spread(n, foes) { var s = AI.e0 * (1 + AI.crowd * (foes - 1)), i; for (i = 1; i < n; i++) s *= AI.decay; return Math.max(AI.floor, s); }

    function aiShot(state, ei, n) {
      var me = state.tanks[ei], you = state.tanks[0], rng = mulberry32(mixSeed(state.seed, n * 8 + ei));
      rng();
      var e0 = 38 + Math.floor(rng() * 25), off = (rng() * 2 - 1) * spread(n, state.tanks.length - 1), an = rng() * 2 - 1;
      var dir = you.x >= me.x ? 1 : -1, best = null, elevs = [e0, 62, 74, 83], aimX = clamp(you.x + off, 5, W - 6), i;
      for (i = 0; i < elevs.length; i++) {
        var a = dir > 0 ? elevs[i] : 180 - elevs[i], aim = aimPower(state, ei, a, aimX, "shell");
        if (!best || aim.err < best.err) best = { angle: a, power: aim.power, err: aim.err };
        if (best.err <= 6) break;
      }
      return { angle: clamp(best.angle + Math.round(an * 2), 0, 180), power: best.power };
    }

    // ---- a turn ----
    // Fire one shot for the player, then every living enemy fires back. Changes `state` and returns what happened.
    function fire(state, angle, power, weapon) {
      if (state.status !== "playing") return { ok: false, error: "over" };
      if (!WEAPONS[weapon]) return { ok: false, error: "weapon" };
      angle = clamp(Math.round(angle), 0, 180); power = clamp(Math.round(power), 10, 100);
      if (ammoLeft(state, weapon) <= 0) return { ok: false, error: "empty" };
      var n = state.shots.length + 1, living = state.tanks.map(function (t, i) { return i > 0 && alive(t) ? i : -1; }).filter(function (i) { return i > 0; });
      var res = { ok: true, n: n, shot: { angle: angle, power: power, weapon: weapon }, phases: [], returns: [] };
      var armorBefore = state.tanks.map(function (t) { return t.armor; });

      var ph = runPhase(state, 0, angle, power, weapon);
      res.phases.push(ph);
      var dealt = 0, kills = [], hitBy = {};
      ph.booms.forEach(function (b) { b.hits.forEach(function (x) { dealt += x.dmg; hitBy[x.t] = (hitBy[x.t] || 0) + x.dmg; }); });
      living.forEach(function (i) { if (!alive(state.tanks[i])) kills.push(i); });
      // the blast that came closest to an enemy that was standing when you fired
      var nearest = null;
      ph.booms.forEach(function (b) {
        b.near.forEach(function (q) {
          if (!nearest || q.d < nearest.dist) nearest = { enemy: q.t, dist: q.d, dx: q.dx };
        });
      });
      if (nearest) {
        var dirTo = state.tanks[nearest.enemy].x >= state.tanks[0].x ? 1 : -1;
        nearest.short = nearest.dx * dirTo < 0;   // the blast fell on your side of the enemy
        nearest.dx = Math.round(Math.abs(nearest.dx)); nearest.dist = Math.round(nearest.dist);
      }
      res.dealt = dealt; res.hitBy = hitBy; res.kills = kills; res.nearest = nearest;
      res.outcome = dealt > 0 ? "hit" : (nearest && nearest.dist <= NEAR ? "near" : "miss");

      if (enemiesLeft(state) === 0) { state.status = "won"; }
      else {
        for (var i = 1; i < state.tanks.length; i++) {
          if (!alive(state.tanks[i])) continue;
          var ai = aiShot(state, i, n), before = state.tanks[0].armor;
          var p2 = runPhase(state, i, ai.angle, ai.power, "shell");
          res.phases.push(p2);
          var dmg = before - state.tanks[0].armor, nb = p2.booms[0] || null;
          res.returns.push({ by: i, hit: dmg > 0, dmg: dmg, dx: nb ? Math.round(nb.x - state.tanks[0].x) : null });
          if (!alive(state.tanks[0])) break;
        }
        if (!alive(state.tanks[0])) { state.status = "lost"; state.reason = "armor"; }
        else if (n >= MAX_SHOTS) { state.status = "lost"; state.reason = "shots"; }
      }
      state.shots.push({
        angle: angle, power: power, weapon: weapon, outcome: res.outcome, dealt: dealt,
        land: ph.booms.map(function (b) { return [Math.round(b.x), Math.round(b.y)]; })
      });
      res.status = state.status; res.reason = state.reason;
      res.armorBefore = armorBefore;
      return res;
    }

    // Rebuild a round from a saved shot list: [[angle, power, weapon], ...]. Returns every turn's result too.
    function replay(idx, dow, shots) {
      var state = createRound(idx, dow), results = [], i;
      for (i = 0; i < shots.length; i++) {
        var s = shots[i], r = fire(state, s[0], s[1], s[2]);
        if (!r.ok) return { state: state, results: results, error: true, at: i };
        results.push(r);
      }
      return { state: state, results: results, error: false };
    }

    function squares(state) {
      var G = { hit: "■", near: "▣", miss: "□" };
      return state.shots.map(function (s) { return G[s.outcome]; }).join("");
    }

    return {
      W: W, H: H, MAX_SHOTS: MAX_SHOTS, VERSION: VERSION, TANK_R: TANK_R, TANK_UP: TANK_UP, NEAR: NEAR, WEAPONS: WEAPONS, WEAPON_IDS: WEAPON_IDS, TWISTS: TWISTS,
      mulberry32: mulberry32, hashDay: hashDay, dowOf: dowOf, sinDeg: sinDeg, cosDeg: cosDeg,
      createRound: createRound, clone: clone, fire: fire, replay: replay, squares: squares, ammoLeft: ammoLeft, enemiesLeft: enemiesLeft,
      carve: carve, groundAt: groundAt, tankCenter: tankCenter, probe: probe, aimPower: aimPower, previewPoints: previewPoints,
      blastFactor: blastFactor, spread: spread, AI: AI, aiShot: aiShot, launch: launch
    };
  })();

  var host = typeof window !== "undefined" ? window : null;
  if (host) host.PLTanklinkEngine = E;
  if (typeof module !== "undefined" && module.exports) module.exports = E;
  if (!host || !host.PLGames || typeof document === "undefined") return;

  // ================================================================ page
  var G = host.PLGames, NAME = "tanklink", URL_ = "https://purplelink.llc/games/tanklink/", EPOCH = "2026-10-04";
  var $ = function (id) { return document.getElementById(id); };
  var canvas = $("tk-canvas");
  if (!canvas) return;
  var ctx2d = canvas.getContext("2d");
  var W = E.W, H = E.H, MAX = E.MAX_SHOTS;
  var FX = host.PLFX;

  var rs = null;                       // the engine state
  var idx = 0, twist = null;
  var aim = { angle: 45, power: 60, weapon: "shell" };
  var busy = false, skip = false, raf = 0;
  var view = { h: [], armor: [], aim: [], proj: [], trails: [], marks: [], scars: [], ty: [], tv: [] };
  var allBooms = [];                   // every blast of this round that has finished: {x, y, r}. Drives the scorch on the terrain.
  var lastText = "";

  var mql = null;
  try { mql = host.matchMedia("(prefers-reduced-motion: reduce)"); } catch (e) { mql = null; }
  function reduced() { return mql ? mql.matches : true; }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function wname(id) { return E.WEAPONS[id].name; }
  function angleText(a) { return a === 90 ? "90 up" : (a < 90 ? a : 180 - a) + (a < 90 ? " right" : " left"); }
  function windText(w) { return w === 0 ? "Calm" : Math.abs(w) + (w > 0 ? " toward the enemy" : " toward you"); }

  // ================================================================ drawing
  // Everything below only paints. Nothing here changes the round, and nothing here may call Math.random: scenery comes from
  // the day's seed (so the backdrop is the same for everyone), and the particles use their own fixed-seed generator.
  //
  // Sprite slots. Every piece of art has a vector drawing; if /assets/games/tanklink/<url> loads, the sprite replaces that
  // piece, and if it is missing or fails the vector drawing stays. Drop WebP files in the folder and nothing else changes.
  // Sizes are in source pixels at PPU = 3 pixels per field unit (a tank is about 30 units wide); the real file may be any
  // whole multiple of w by h. anchor is the point in the file that sits on the placed position. Full list and the
  // cutout rules: docs/games-sprites.md.
  //   tank-player, tank-enemy  whole tank without the barrel, facing right (the enemy is mirrored), anchor on the ground.
  //   barrel                   pointing right, anchor on the pivot; drawn under the tank so the turret can cover its base.
  //   shell-normal / -heavy / -cluster  pointing right, anchor at the centre; the cluster art is also the bomblet (drawn small).
  //   explosion                6 frames side by side; the frame is centred on the blast and drawn 2.6 crater radii wide.
  //   bg-far, bg-near          (dark theme; bg-far-day and bg-near-day are the light-theme pair) the whole field plus a 12 unit margin (824 by 424 units, 2 px per unit), far opaque, near
  //                            transparent above its hills.
  //   terrain-tile             seamless, tiled at 128 by 128 units, opaque; lighting and craters are still painted over it.
  //   grass-strip              seamless along x, 64 units long; the surface line sits at anchor y.
  var SPRITE_BASE = "/assets/games/tanklink/", PPU = 3;
  var SPRITES = {
    "tank-player":   { url: "tank-player.webp",   w: 108,  h: 72,  anchor: [54, 69],   frames: 1 },
    "tank-enemy":    { url: "tank-enemy.webp",    w: 108,  h: 72,  anchor: [54, 69],   frames: 1 },
    "barrel":        { url: "barrel.webp",        w: 72,   h: 24,  anchor: [12, 12],   frames: 1 },
    "shell-normal":  { url: "shell-normal.webp",  w: 36,   h: 18,  anchor: [18, 9],    frames: 1 },
    "shell-heavy":   { url: "shell-heavy.webp",   w: 54,   h: 27,  anchor: [27, 13.5], frames: 1 },
    "shell-cluster": { url: "shell-cluster.webp", w: 45,   h: 30,  anchor: [22.5, 15], frames: 1 },
    "explosion":     { url: "explosion.webp",     w: 1536, h: 256, anchor: [128, 128], frames: 6 },
    "bg-far":        { url: "bg-far.webp",        w: 1648, h: 848, anchor: [0, 0],     frames: 1 },
    "bg-near":       { url: "bg-near.webp",       w: 1648, h: 848, anchor: [0, 0],     frames: 1 },
    "bg-far-day":    { url: "bg-far-day.webp",    w: 1648, h: 848, anchor: [0, 0],     frames: 1 },
    "bg-near-day":   { url: "bg-near-day.webp",   w: 1648, h: 848, anchor: [0, 0],     frames: 1 },
    "terrain-tile":  { url: "terrain-tile.webp",  w: 384,  h: 384, anchor: [0, 0],     frames: 1 },
    "grass-strip":   { url: "grass-strip.webp",   w: 192,  h: 36,  anchor: [0, 12],    frames: 1 }
  };
  var spr = {}, sprStarted = false;
  function loadSprites() {
    if (sprStarted) return;
    sprStarted = true;
    var miss = {};
    try { miss = JSON.parse(host.sessionStorage.getItem("tk-sprite-miss") || "{}") || {}; } catch (e) { miss = {}; }
    // pack.json lists the sprites that exist, so nothing else is requested (same as Frontlink)
    if (typeof host.fetch !== "function") return;
    host.fetch(SPRITE_BASE + "pack.json").then(function (r) { return r.ok ? r.json() : { sprites: [] }; }).catch(function () { return { sprites: [] }; }).then(function (pack) {
    var have = {}; ((pack && pack.sprites) || []).forEach(function (n) { have[n] = 1; });
    Object.keys(SPRITES).forEach(function (name) {
      if (miss[name] || !have[name]) return;
      var img = new Image(), s = { img: img, ok: false };
      spr[name] = s;
      img.decoding = "async";
      img.onload = function () { if (img.naturalWidth > 0 && img.naturalHeight > 0) { s.ok = true; terrainDirty = true; backDirty = true; texCv = null; redraw(); } };
      img.onerror = function () {
        s.ok = false; miss[name] = 1;
        try { host.sessionStorage.setItem("tk-sprite-miss", JSON.stringify(miss)); } catch (e) { /* optional */ }
      };
      img.src = SPRITE_BASE + SPRITES[name].url;
    });
    });
  }
  function sprite(name) { var s = spr[name]; return s && s.ok ? s : null; }
  // Draw one frame with its anchor on (x, y), turned by rot (canvas radians), mirrored when flip, scaled by k.
  function drawSprite(c, name, x, y, rot, flip, frame, k) {
    var s = sprite(name);
    if (!s) return false;
    var m = SPRITES[name], img = s.img, fw = img.naturalWidth / m.frames, fh = img.naturalHeight;
    c.save();
    c.translate(x, y);
    if (rot) c.rotate(rot);
    if (flip) c.scale(-1, 1);
    if (k && k !== 1) c.scale(k, k);
    c.drawImage(img, (frame || 0) * fw, 0, fw, fh, -m.anchor[0] / PPU, -m.anchor[1] / PPU, m.w / PPU / m.frames, m.h / PPU);
    c.restore();
    return true;
  }

  // ---- canvas and palette ----
  var SCALE = Math.min(2, Math.max(1, Math.ceil(host.devicePixelRatio || 1)));
  canvas.width = W * SCALE; canvas.height = H * SCALE;
  var OV = 12;                          // margin kept around the field so a shake never shows an edge
  var FALLBACK = {
    "--tk-sky": "#201830", "--tk-sky-hi": "#1a1530", "--tk-sky-lo": "#3a2650", "--tk-glow": "#9a7ac0", "--tk-sun": "#f2ecf8",
    "--tk-far": "#3a2c58", "--tk-near": "#2c2448", "--tk-ground": "#4a3a2a", "--tk-ground-hi": "#6a5436", "--tk-ground-lo": "#2c2218",
    "--tk-grass": "#6a8a3a", "--tk-grass-hi": "#9ab85a", "--tk-edge": "#b08850", "--tk-you": "#c9a6ff", "--tk-foe": "#ff9d9d",
    "--tk-ink": "#f4eefa", "--tk-trail": "#d8c8f0", "--tk-mark": "#f4eefa", "--tk-cloud": "#d8c8f0", "--tk-pill": "#1a1428",
    "--tk-night": "1", "--tk-star-a": "0.85", "--tk-cloud-a": "0.2"
  };
  var pal = null, tints = {}, terrainDirty = true, terr = null, sc = null;
  function palette() {
    if (pal) return pal;
    var cs = host.getComputedStyle(canvas), k;
    pal = {};
    for (k in FALLBACK) pal[k] = cs.getPropertyValue(k).trim() || FALLBACK[k];
    pal.font = cs.fontFamily || "sans-serif";
    pal.night = parseFloat(pal["--tk-night"]) > 0.5;
    pal.starA = parseFloat(pal["--tk-star-a"]) || 0;
    pal.cloudA = parseFloat(pal["--tk-cloud-a"]) || 0;
    return pal;
  }
  function repaint() { pal = null; tints = {}; tankParts = {}; terrainDirty = true; backDirty = true; }
  function fy(y) { return H - y; }
  function rr(c, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    c.beginPath(); c.moveTo(x + r, y); c.lineTo(x + w - r, y); c.arc(x + w - r, y + r, r, -Math.PI / 2, 0);
    c.lineTo(x + w, y + h - r); c.arc(x + w - r, y + h - r, r, 0, Math.PI / 2); c.lineTo(x + r, y + h);
    c.arc(x + r, y + h - r, r, Math.PI / 2, Math.PI); c.lineTo(x, y + r); c.arc(x + r, y + r, r, Math.PI, Math.PI * 1.5); c.closePath();
  }
  // A soft round blob in one colour, made once and stamped many times (cheaper than a gradient per particle).
  function softBlob(color) {
    var cv = document.createElement("canvas"), g, gr;
    cv.width = cv.height = 96; g = cv.getContext("2d");
    gr = g.createRadialGradient(48, 48, 0, 48, 48, 48);
    gr.addColorStop(0, "#fff"); gr.addColorStop(0.45, "rgba(255,255,255,0.55)"); gr.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 96, 96);
    g.globalCompositeOperation = "source-in"; g.fillStyle = color; g.fillRect(0, 0, 96, 96);
    return cv;
  }
  function blob(key, color) { return tints[key] || (tints[key] = softBlob(color)); }
  var DUST = "rgb(196,164,122)", SMOKE = "rgb(80,74,90)", SMOKE_N = "rgb(138,130,152)", FIRE = "rgb(255,168,58)";

  // ---- scenery from the day's seed: the same backdrop for everyone ----
  function buildScenery() {
    var r = E.mulberry32((rs.seed ^ 0x2f6b9a37) >>> 0), i;
    function layer(base, amps, lens) {
      var o = { base: base, a: [], l: [], p: [], fill: null, line: null };
      for (i = 0; i < amps.length; i++) { o.a.push(amps[i] * (0.75 + r() * 0.5)); o.l.push(lens[i] * (0.8 + r() * 0.4)); o.p.push(r() * 6.2832); }
      return o;
    }
    function hillY(o, x) { var v = o.base, k; for (k = 0; k < o.a.length; k++) v += o.a[k] * Math.sin(6.2832 * x / o.l[k] + o.p[k]); return v; }
    function paths(o) {
      var x, f = new Path2D(), l = new Path2D();
      f.moveTo(-OV - 6, H + OV); l.moveTo(-OV - 6, fy(hillY(o, -OV - 6)));
      f.lineTo(-OV - 6, fy(hillY(o, -OV - 6)));
      for (x = -OV; x <= W + OV + 6; x += 6) { f.lineTo(x, fy(hillY(o, x))); l.lineTo(x, fy(hillY(o, x))); }
      f.lineTo(W + OV + 6, H + OV); f.closePath();
      o.fill = f; o.line = l;
    }
    sc = { far: layer(236, [20, 11, 5], [430, 240, 120]), near: layer(190, [26, 13, 6], [340, 190, 90]), stars: [], clouds: [], strata: [], speck: [], rocks: [], tufts: [] };
    paths(sc.far); paths(sc.near);
    sc.mood = r();
    sc.sunX = 90 + r() * 620; sc.sunY = 238 + r() * 56; sc.sunR = 16 + r() * 8;
    for (i = 0; i < 70; i++) sc.stars.push({ x: r() * W, y: r() * 190, s: 0.7 + r() * 1.2, a: 0.35 + r() * 0.65, ph: r() * 6.28 });
    for (i = 0; i < 5; i++) sc.clouds.push({ x: r() * (W + 300), y: 34 + r() * 120, s: 0.7 + r() * 0.9, v: 1.5 + r() * 2.5 });
    for (i = 0; i < 9; i++) sc.strata.push({ y: 96 + i * 36 + r() * 16, amp: 2 + r() * 4, len: 70 + r() * 140, ph: r() * 6.28, w: 3 + r() * 5, light: r() < 0.4 });
    for (i = 0; i < 320; i++) sc.speck.push({ x: r() * W, y: 60 + r() * 340, s: 0.7 + r() * 1.6, a: 0.1 + r() * 0.2, light: r() < 0.5 });
    for (i = 0; i < 42; i++) sc.rocks.push({ x: r() * W, y: 90 + r() * 310, rx: 2 + r() * 3.4, ry: 1.3 + r() * 2.1, a: 0.14 + r() * 0.16 });
    for (i = 0; i < 230; i++) sc.tufts.push({ x: 1 + r() * (W - 2), t: 2 + r() * 3.4, lean: (r() - 0.5) * 2.4, k: r() < 0.5 });
    terrainDirty = true; backDirty = true; texCv = null;
  }

  // strata, speckle and stones: painted once per map (they do not change when a crater is cut) and laid over the ground fill
  var texCv = null;
  function renderTex() {
    texCv = layerOf(texCv);
    var c = texCv.getContext("2d");
    // strata: wavy bands at fixed heights, so a crater cuts through them
    c.lineJoin = "round";
    sc.strata.forEach(function (s) {
      var x;
      c.beginPath();
      for (x = -OV; x <= W + OV; x += 8) { var y = s.y + Math.sin(6.2832 * x / s.len + s.ph) * s.amp; if (x === -OV) c.moveTo(x, y); else c.lineTo(x, y); }
      c.strokeStyle = s.light ? "rgba(255,240,210,0.07)" : "rgba(0,0,0,0.14)"; c.lineWidth = s.w; c.stroke();
    });
    sc.speck.forEach(function (s) { c.fillStyle = s.light ? "rgba(255,240,210," + s.a + ")" : "rgba(0,0,0," + s.a + ")"; c.fillRect(s.x, s.y, s.s, s.s); });
    sc.rocks.forEach(function (s) { c.fillStyle = "rgba(20,12,8," + s.a + ")"; c.beginPath(); c.ellipse(s.x, s.y, s.rx, s.ry, 0, 0, 6.2832); c.fill(); c.fillStyle = "rgba(255,240,210," + (s.a * 0.5) + ")"; c.beginPath(); c.ellipse(s.x - 0.6, s.y - 0.6, s.rx * 0.6, s.ry * 0.5, 0, 0, 6.2832); c.fill(); });
  }

  // ---- terrain: lit gradient, strata, speckle, a soft shadow and a grass line under the surface, a scorched rim round craters ----
  function renderTerrain(h, p) {
    if (!terr) { terr = document.createElement("canvas"); terr.width = (W + 2 * OV) * SCALE; terr.height = (H + 2 * OV) * SCALE; }
    var c = terr.getContext("2d"), i, k, maxH = 0, body = new Path2D(), line = new Path2D(), sTile = sprite("terrain-tile"), sGrass = sprite("grass-strip");
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, terr.width, terr.height);
    c.setTransform(SCALE, 0, 0, SCALE, OV * SCALE, OV * SCALE);
    for (i = 0; i < W; i++) if (h[i] > maxH) maxH = h[i];
    body.moveTo(-OV, H + OV); body.lineTo(-OV, fy(h[0])); line.moveTo(-OV, fy(h[0]));
    for (i = 0; i < W; i++) { body.lineTo(i, fy(h[i])); line.lineTo(i, fy(h[i])); }
    body.lineTo(W + OV, fy(h[W - 1])); line.lineTo(W + OV, fy(h[W - 1]));
    body.lineTo(W + OV, H + OV); body.closePath();
    var g = c.createLinearGradient(0, fy(maxH) - 4, 0, H + OV);
    g.addColorStop(0, p["--tk-ground-hi"]); g.addColorStop(0.3, p["--tk-ground"]); g.addColorStop(1, p["--tk-ground-lo"]);
    c.save(); c.clip(body);
    if (sTile) {
      try {
        var pat = c.createPattern(sTile.img, "repeat");
        pat.setTransform(new DOMMatrix().scale(128 / sTile.img.naturalWidth, 128 / sTile.img.naturalHeight));
        c.fillStyle = pat; c.fillRect(-OV, -OV, W + 2 * OV, H + 2 * OV);
        c.globalAlpha = 0.45; c.fillStyle = g; c.fillRect(-OV, -OV, W + 2 * OV, H + 2 * OV); c.globalAlpha = 1;
      } catch (e) { c.fillStyle = g; c.fillRect(-OV, -OV, W + 2 * OV, H + 2 * OV); }
    } else { c.fillStyle = g; c.fillRect(-OV, -OV, W + 2 * OV, H + 2 * OV); }
    if (!texCv) renderTex();
    c.drawImage(texCv, -OV, -OV, W + 2 * OV, H + 2 * OV);
    // soft shadow just under the surface line
    c.save(); c.translate(0, 2);
    c.strokeStyle = "rgba(10,6,4,0.10)"; c.lineWidth = 20; c.stroke(line);
    c.strokeStyle = "rgba(10,6,4,0.12)"; c.lineWidth = 12; c.stroke(line);
    c.strokeStyle = "rgba(10,6,4,0.16)"; c.lineWidth = 6; c.stroke(line);
    c.restore();
    // the surface itself
    if (sGrass) {
      var m = SPRITES["grass-strip"], sw = m.w / PPU, sh = m.h / PPU, nw = sGrass.img.naturalWidth, nh = sGrass.img.naturalHeight, x0;
      for (x0 = -OV; x0 < W + OV; x0 += 4) {
        var hx = Math.max(0, Math.min(W - 1, Math.round(x0 + 2))), sx = ((x0 % sw) + sw) % sw;
        c.drawImage(sGrass.img, sx / sw * nw, 0, 4 / sw * nw, nh, x0, fy(h[hx]) - m.anchor[1] / PPU, 4.4, sh);
      }
    } else {
      c.lineCap = "round";
      c.strokeStyle = p["--tk-grass"]; c.lineWidth = 6; c.stroke(line);
      c.save(); c.translate(0, -1.4); c.strokeStyle = p["--tk-grass-hi"]; c.lineWidth = 1.8; c.globalAlpha = 0.9; c.stroke(line); c.restore();
    }
    // scorch around craters
    view.scars.forEach(function (s) {
      var R = s.r * 1.7, cg = c.createRadialGradient(s.x, fy(s.y), 0, s.x, fy(s.y), R);
      cg.addColorStop(0, "rgba(6,3,4,0.78)"); cg.addColorStop(0.55, "rgba(6,3,4,0.7)"); cg.addColorStop(1, "rgba(6,3,4,0)");
      c.fillStyle = cg; c.fillRect(s.x - R, fy(s.y) - R, 2 * R, 2 * R);
    });
    c.restore();
    // blades of grass stand up from the surface, but not on steep or scorched ground
    if (!sGrass) {
      sc.tufts.forEach(function (t) {
        var xi = Math.round(t.x), y = fy(h[xi]), a, burnt = false;
        if (Math.abs(h[Math.min(W - 1, xi + 3)] - h[Math.max(0, xi - 3)]) > 7) return;
        for (k = 0; k < view.scars.length; k++) { a = view.scars[k]; if ((xi - a.x) * (xi - a.x) + (h[xi] - a.y) * (h[xi] - a.y) < a.r * a.r * 2.4) { burnt = true; break; } }
        if (burnt) return;
        c.fillStyle = t.k ? p["--tk-grass"] : p["--tk-grass-hi"];
        c.beginPath(); c.moveTo(xi - 1.2, y + 0.5); c.lineTo(xi + t.lean, y - t.t); c.lineTo(xi + 1.2, y + 0.5); c.closePath(); c.fill();
      });
    }
    terrainDirty = false;
  }

  // ---- sky and the two hill layers ----
  // Painted once into their own canvases (sky, sun or moon, stars, clouds and the far hills in one; the near hills in
  // another) and joined with the terrain into one finished picture, so an ordinary frame is a single image copy. While the
  // screen shakes the layers are copied separately, each moving by a different amount: that is the parallax.
  var layA = null, layB = null, scene = null, backDirty = true, sceneDirty = true;
  function layerOf(cv) {
    if (!cv) { cv = document.createElement("canvas"); cv.width = (W + 2 * OV) * SCALE; cv.height = (H + 2 * OV) * SCALE; }
    var c = cv.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height);
    c.setTransform(SCALE, 0, 0, SCALE, OV * SCALE, OV * SCALE);
    return cv;
  }
  function renderBack(p) {
    layA = layerOf(layA); layB = layerOf(layB);
    var c = layA.getContext("2d"), far = sprite(p.night ? "bg-far" : "bg-far-day"), near = sprite(p.night ? "bg-near" : "bg-near-day"), i;
    if (far) c.drawImage(far.img, -OV, -OV, W + 2 * OV, H + 2 * OV);
    else {
      var g = c.createLinearGradient(0, -OV, 0, H + OV);
      g.addColorStop(0, p["--tk-sky-hi"]); g.addColorStop(1, p["--tk-sky-lo"]);
      c.fillStyle = g; c.fillRect(-OV, -OV, W + 2 * OV, H + 2 * OV);
      // sun or moon on a seeded spot, with a horizon glow that is stronger on some days
      var sx = sc.sunX, sy = fy(sc.sunY);
      c.globalAlpha = 0.35 + 0.5 * sc.mood; var gl = blob("glow", p["--tk-glow"]); c.drawImage(gl, sx - 230, sy - 230, 460, 460);
      c.globalAlpha = 0.55; c.drawImage(gl, sx - 70, sy - 70, 140, 140);
      c.globalAlpha = 1; c.fillStyle = p["--tk-sun"]; c.beginPath(); c.arc(sx, sy, sc.sunR, 0, 6.2832); c.fill();
      if (p.night) {
        c.fillStyle = "rgba(60,50,90,0.16)";
        c.beginPath(); c.arc(sx - sc.sunR * 0.3, sy - sc.sunR * 0.2, sc.sunR * 0.28, 0, 6.2832); c.fill();
        c.beginPath(); c.arc(sx + sc.sunR * 0.35, sy + sc.sunR * 0.3, sc.sunR * 0.2, 0, 6.2832); c.fill();
      }
      if (p.starA > 0.02) {
        c.fillStyle = p["--tk-sun"];
        for (i = 0; i < sc.stars.length; i++) { var st = sc.stars[i]; c.globalAlpha = p.starA * st.a; c.fillRect(st.x, st.y, st.s, st.s); }
      }
      c.globalAlpha = p.cloudA;
      var cb = blob("cloud", p["--tk-cloud"]);
      for (i = 0; i < sc.clouds.length; i++) {
        var cl = sc.clouds[i], cx = cl.x % (W + 100) - 50, cy = cl.y, k = cl.s;
        c.drawImage(cb, cx - 50 * k, cy - 22 * k, 100 * k, 44 * k);
        c.drawImage(cb, cx - 16 * k, cy - 32 * k, 76 * k, 48 * k);
        c.drawImage(cb, cx - 76 * k, cy - 10 * k, 70 * k, 34 * k);
      }
      c.globalAlpha = 1;
      var hg = c.createLinearGradient(0, fy(sc.far.base + 40), 0, H + OV);
      hg.addColorStop(0, p["--tk-far"]); hg.addColorStop(1, p["--tk-sky-lo"]);
      c.fillStyle = hg; c.fill(sc.far.fill);
      c.globalAlpha = 0.35; c.strokeStyle = p["--tk-glow"]; c.lineWidth = 1.2; c.stroke(sc.far.line); c.globalAlpha = 1;
    }
    c = layB.getContext("2d");
    if (near) c.drawImage(near.img, -OV, -OV, W + 2 * OV, H + 2 * OV);
    else {
      var ng = c.createLinearGradient(0, fy(sc.near.base + 40), 0, H + OV);
      ng.addColorStop(0, p["--tk-near"]); ng.addColorStop(1, p["--tk-ground-lo"]);
      c.fillStyle = ng; c.fill(sc.near.fill);
      c.globalAlpha = 0.28; c.strokeStyle = p["--tk-glow"]; c.lineWidth = 1.2; c.stroke(sc.near.line); c.globalAlpha = 1;
    }
    backDirty = false; sceneDirty = true;
  }
  function renderScene() {
    scene = layerOf(scene);
    var c = scene.getContext("2d"), w = W + 2 * OV, h = H + 2 * OV;
    c.drawImage(layA, -OV, -OV, w, h); c.drawImage(layB, -OV, -OV, w, h); c.drawImage(terr, -OV, -OV, w, h);
    sceneDirty = false;
  }
  // a few stars near the top of the sky twinkle over the finished picture (kept above any hill)
  function drawTwinkle(c, p, T) {
    if (!T || p.starA < 0.02 || sprite("bg-far") || sprite("bg-far-day")) return;
    var i, st;
    c.fillStyle = p["--tk-sun"];
    for (i = 0; i < sc.stars.length; i++) {
      st = sc.stars[i];
      if (st.y > 62 || i % 3) continue;
      c.globalAlpha = p.starA * st.a * (0.25 + 0.75 * (0.5 + 0.5 * Math.sin(T * 0.0021 + st.ph)));
      c.fillRect(st.x - 0.4, st.y - 0.4, st.s + 0.8, st.s + 0.8);
    }
    c.globalAlpha = 1;
  }

  // ---- tanks ----
  // On a narrow screen the whole field shrinks, so tanks, labels and marks are drawn a little larger to stay readable.
  var ts = 1, cssScale = 1;
  function tpx(base, minCss) { return Math.max(base * ts, minCss / cssScale); }   // text size in field units: never under minCss pixels on screen
  var STEEL = "#8f8aa0", STEEL_HI = "#cfcade", STEEL_LO = "#474158", RUBBER = "#262031";
  function hullPath(c) { c.beginPath(); c.moveTo(-14, -7); c.lineTo(14, -7); c.lineTo(15.5, -8.6); c.lineTo(10.5, -11.8); c.lineTo(-11, -11.8); c.lineTo(-14.5, -9.4); c.closePath(); }
  function domePath(c) { c.beginPath(); c.moveTo(-8.6, -10.2); c.ellipse(0, -10.2, 8.6, 6.8, 0, Math.PI, 0); c.closePath(); }
  function flame(c, x, y, h, w, ph, T) {
    var fl = 0.82 + 0.18 * Math.sin(T * 0.017 + ph) + 0.1 * Math.sin(T * 0.031 + ph * 2.3), hh = h * fl, ww = w * (1.05 - 0.1 * Math.sin(T * 0.02 + ph)), sway = Math.sin(T * 0.012 + ph) * ww * 0.4;
    c.fillStyle = "rgba(235,92,28,0.92)";
    c.beginPath(); c.moveTo(x - ww, y); c.quadraticCurveTo(x - ww * 0.9, y - hh * 0.55, x + sway, y - hh); c.quadraticCurveTo(x + ww * 0.9, y - hh * 0.55, x + ww, y); c.closePath(); c.fill();
    c.fillStyle = "rgba(255,206,92,0.95)"; hh *= 0.62; ww *= 0.55;
    c.beginPath(); c.moveTo(x - ww, y); c.quadraticCurveTo(x - ww * 0.9, y - hh * 0.55, x + sway * 0.6, y - hh); c.quadraticCurveTo(x + ww * 0.9, y - hh * 0.55, x + ww, y); c.closePath(); c.fill();
  }

  // The tank's lower half (tracks, hull, marking) and its dome are painted once per team and palette, then stamped each frame.
  var TP_W = 40, TP_H = 24, TP_X = 20, TP_Y = 20, tankParts = {};
  function tankPart(p, mine, part) {
    var key = (mine ? "y" : "f") + part;
    if (tankParts[key]) return tankParts[key];
    var S = SCALE * 1.5, cv = document.createElement("canvas"), c = cv.getContext("2d"), col = mine ? p["--tk-you"] : p["--tk-foe"];
    cv.width = Math.ceil(TP_W * S); cv.height = Math.ceil(TP_H * S);
    c.setTransform(S, 0, 0, S, TP_X * S, TP_Y * S); c.lineJoin = "round"; c.lineCap = "round";
    if (part === 0) {
      rr(c, -15.5, -7.4, 31, 7.4, 3.7); c.fillStyle = RUBBER; c.fill();
      c.strokeStyle = "rgba(255,255,255,0.16)"; c.lineWidth = 1; c.setLineDash([1.4, 1.6]); c.beginPath(); c.moveTo(-13.5, -0.9); c.lineTo(13.5, -0.9); c.stroke(); c.setLineDash([]);
      for (var w = 0; w < 5; w++) {
        var wx = -11 + w * 5.5;
        c.fillStyle = "#4b4458"; c.beginPath(); c.arc(wx, -3.7, 2.35, 0, 6.2832); c.fill();
        c.fillStyle = "#9a93ab"; c.beginPath(); c.arc(wx, -3.7, 0.85, 0, 6.2832); c.fill();
      }
      c.strokeStyle = "rgba(10,6,18,0.85)"; c.lineWidth = 1; rr(c, -15.5, -7.4, 31, 7.4, 3.7); c.stroke();
      hullPath(c); c.fillStyle = col; c.fill();
      var hg = c.createLinearGradient(0, -12, 0, -7); hg.addColorStop(0, "rgba(255,255,255,0.32)"); hg.addColorStop(1, "rgba(0,0,0,0.3)");
      hullPath(c); c.fillStyle = hg; c.fill();
      c.strokeStyle = "rgba(10,6,18,0.85)"; c.lineWidth = 1.1; hullPath(c); c.stroke();
      c.strokeStyle = "rgba(0,0,0,0.28)"; c.lineWidth = 0.8; c.beginPath(); c.moveTo(-13, -8.5); c.lineTo(13, -8.5); c.stroke();
      // the marking: a diamond for you, a triangle for the enemy, so the sides differ in shape as well as colour
      c.fillStyle = "#f7f1ff"; c.strokeStyle = "rgba(10,6,18,0.9)"; c.lineWidth = 0.8; c.beginPath();
      if (mine) { c.moveTo(-7, -11.2); c.lineTo(-4.6, -9.6); c.lineTo(-7, -8); c.lineTo(-9.4, -9.6); } else { c.moveTo(-7, -11.2); c.lineTo(-4.6, -8); c.lineTo(-9.4, -8); }
      c.closePath(); c.fill(); c.stroke();
    } else {
      domePath(c); c.fillStyle = col; c.fill();
      var dg = c.createLinearGradient(-5, -18, 5, -8); dg.addColorStop(0, "rgba(255,255,255,0.4)"); dg.addColorStop(0.55, "rgba(255,255,255,0)"); dg.addColorStop(1, "rgba(0,0,0,0.3)");
      domePath(c); c.fillStyle = dg; c.fill();
      c.strokeStyle = "rgba(10,6,18,0.85)"; c.lineWidth = 1.1; domePath(c); c.stroke();
      c.fillStyle = "rgba(10,6,18,0.55)"; c.beginPath(); c.ellipse(3, -15.4, 2.2, 0.95, 0, 0, 6.2832); c.fill();
    }
    tankParts[key] = cv;
    return cv;
  }

  function drawTank(c, p, k, x, gy, armor, barrelDeg, mine, T, slope) {
    var col = mine ? p["--tk-you"] : p["--tk-foe"], dead = armor <= 0, f = mine ? 1 : -1, tv = view.tv[k] || { recoil: 0, flash: 0, hit: 0 };
    var rad = barrelDeg * Math.PI / 180, bodyS = sprite(mine ? "tank-player" : "tank-enemy"), barS = sprite("barrel");
    c.save();
    c.translate(x, fy(gy)); c.rotate(-slope); c.scale(ts, ts);
    c.lineJoin = "round"; c.lineCap = "round";
    // ground shadow
    c.fillStyle = "rgba(0,0,0,0.3)"; c.beginPath(); c.ellipse(0, 0.6, 18.5, 3.4, 0, 0, 6.2832); c.fill();
    if (dead) { drawWreck(c, p, col, f, T); c.restore(); return; }
    var back = 3.2 * tv.recoil, a = -rad + slope, pivotY = -9.2;
    if (bodyS) {
      // sprite tank: barrel under, body on top
      c.save(); c.translate(0, pivotY); c.rotate(a);
      if (!drawSprite(c, "barrel", -back, 0, 0, false, 0, 1)) { barrelShape(c, col, back); }
      muzzleFlash(c, tv, back);
      c.restore();
      drawSprite(c, mine ? "tank-player" : "tank-enemy", 0, 0, 0, f < 0, 0, 1);
    } else {
      var low = tankPart(p, mine, 0), dome = tankPart(p, mine, 1);
      c.save(); c.scale(f, 1); c.drawImage(low, -TP_X, -TP_Y, TP_W, TP_H); c.restore();
      // barrel (not mirrored: it turns by the world angle)
      c.save(); c.translate(0, pivotY); c.rotate(a);
      barrelShape(c, col, back);
      muzzleFlash(c, tv, back);
      c.restore();
      // dome turret
      c.save(); c.scale(f, 1); c.drawImage(dome, -TP_X, -TP_Y, TP_W, TP_H); c.restore();
      // a flash of white when a blast lands on it
      if (tv.hit > 0.02) {
        c.save(); c.scale(f, 1); c.globalAlpha = Math.min(0.7, tv.hit * 0.7); c.fillStyle = "#fff"; hullPath(c); c.fill(); domePath(c); c.fill(); c.restore();
      }
    }
    // antenna and a pennant that streams with the wind
    var ax = -9 * f, ay = -15, tx = ax - 2 * f, ty = -27.5, wd = rs.wind, dir = wd >= 0 ? 1 : -1, len = wd === 0 ? 3.6 : 5 + Math.abs(wd) * 0.9;
    var wave = T ? Math.sin(T * 0.012 + k * 1.7) * (0.8 + Math.abs(wd) * 0.12) : 0;
    c.strokeStyle = "rgba(10,6,18,0.85)"; c.lineWidth = 0.9; c.beginPath(); c.moveTo(ax, ay); c.lineTo(tx, ty); c.stroke();
    c.beginPath(); c.moveTo(tx, ty);
    if (wd === 0) { c.lineTo(tx + 1.8, ty + 1.2); c.lineTo(tx + 0.2, ty + 4.4); c.lineTo(tx - 0.8, ty + 3.6); }
    else { c.lineTo(tx + dir * len * 0.55, ty + 0.8 + wave * 0.5); c.lineTo(tx + dir * len, ty + 2 + wave); c.lineTo(tx + dir * len * 0.55, ty + 3.2 + wave * 0.4); c.lineTo(tx, ty + 4); }
    c.closePath(); c.fillStyle = col; c.fill(); c.lineWidth = 0.7; c.stroke();
    // smoke when armor is low (moving smoke is made by the particle system; reduced motion gets a still puff)
    if (armor <= 35 && !T) {
      c.fillStyle = "rgba(70,66,78,0.32)"; c.beginPath(); c.ellipse(-2, -22, 5, 3.6, 0, 0, 6.2832); c.fill();
      c.fillStyle = "rgba(70,66,78,0.22)"; c.beginPath(); c.ellipse(1, -29, 6.5, 4.4, 0, 0, 6.2832); c.fill();
    }
    c.restore();
  }
  function barrelShape(c, col, back) {
    var bg = c.createLinearGradient(0, -2, 0, 2); bg.addColorStop(0, STEEL_HI); bg.addColorStop(0.5, STEEL); bg.addColorStop(1, STEEL_LO);
    c.fillStyle = bg; c.fillRect(2 - back, -1.8, 12.8, 3.6);
    c.strokeStyle = "rgba(10,6,18,0.85)"; c.lineWidth = 1; c.strokeRect(2 - back, -1.8, 12.8, 3.6);
    c.fillStyle = col; c.fillRect(4 - back, -2.4, 1.8, 4.8);                       // team band
    c.fillStyle = STEEL_LO; c.fillRect(14.2 - back, -2.8, 4, 5.6);                 // muzzle brake
    c.strokeStyle = "rgba(10,6,18,0.9)"; c.strokeRect(14.2 - back, -2.8, 4, 5.6);
    c.beginPath(); c.moveTo(15.7 - back, -2.8); c.lineTo(15.7 - back, 2.8); c.moveTo(17.1 - back, -2.8); c.lineTo(17.1 - back, 2.8); c.stroke();
  }
  function muzzleFlash(c, tv, back) {
    if (!(tv.flash > 0.02)) return;
    var s = tv.flash, tipX = 19 - back, i, a, r;
    var gl = blob("fire", FIRE); c.globalAlpha = Math.min(1, s * 1.2); c.drawImage(gl, tipX - 14 * s, -14 * s, 28 * s, 28 * s);
    c.globalAlpha = Math.min(1, s * 1.5); c.fillStyle = "rgba(255,230,150,0.96)"; c.beginPath();
    for (i = 0; i < 12; i++) { a = i * Math.PI / 6; r = (i % 2 ? 4 : 12) * s; c.lineTo(tipX + Math.cos(a) * r * (a > 1.6 && a < 4.7 ? 0.5 : 1), Math.sin(a) * r * 0.9); }
    c.closePath(); c.fill();
    c.fillStyle = "#fff"; c.beginPath(); c.arc(tipX, 0, 3.4 * s, 0, 6.2832); c.fill();
    c.globalAlpha = 1;
  }
  // a charred hull with the turret blown off, the barrel drooping and a fire; the side accent stays so you can tell whose it was
  function drawWreck(c, p, col, f, T) {
    c.save(); c.scale(f, 1);
    rr(c, -15.5, -6.4, 31, 6.4, 3.2); c.fillStyle = "#17131d"; c.fill();
    c.strokeStyle = "rgba(255,255,255,0.1)"; c.lineWidth = 1; c.beginPath(); c.moveTo(-13, -5.8); c.lineTo(13, -5.8); c.stroke();
    c.fillStyle = "#322c3b"; c.beginPath(); c.arc(-11, -3.2, 2.2, 0, 6.2832); c.arc(-5.5, -3.2, 2.2, 0, 6.2832); c.arc(5.5, -3.2, 2.2, 0, 6.2832); c.fill();
    c.save(); c.translate(0, 1.2); c.rotate(0.03); hullPath(c); c.fillStyle = "#26212e"; c.fill();
    var sg = c.createLinearGradient(0, -12, 0, -6); sg.addColorStop(0, "rgba(255,255,255,0.1)"); sg.addColorStop(1, "rgba(0,0,0,0.45)"); c.fillStyle = sg; hullPath(c); c.fill();
    c.strokeStyle = col; c.lineWidth = 1.6; hullPath(c); c.stroke(); c.restore();
    c.strokeStyle = "rgba(0,0,0,0.6)"; c.lineWidth = 0.9; c.beginPath(); c.moveTo(-4, -10.5); c.lineTo(-1, -8.5); c.lineTo(-3, -7); c.moveTo(6, -10); c.lineTo(8, -8); c.stroke();
    c.fillStyle = col; c.beginPath(); c.moveTo(-7, -10.4); c.lineTo(-4.8, -8.9); c.lineTo(-7, -7.4); c.lineTo(-9.2, -8.9); c.closePath(); c.fill();
    // the blown-off turret, on its side beside the hull
    c.save(); c.translate(17, -3); c.rotate(0.55); domePath(c); c.fillStyle = "#1d1924"; c.fill(); c.strokeStyle = col; c.lineWidth = 1.3; c.stroke(); c.restore();
    // the barrel, bent down over the front
    c.strokeStyle = "#3a3446"; c.lineWidth = 3.4; c.beginPath(); c.moveTo(3, -9); c.lineTo(11, -5.5); c.stroke();
    c.strokeStyle = "rgba(10,6,18,0.8)"; c.lineWidth = 1; c.beginPath(); c.moveTo(3, -10.7); c.lineTo(11, -7.2); c.stroke();
    c.restore();
    var t = T || 0;
    flame(c, -5 * f, -10, 11, 3.6, 0.4, t); flame(c, 3 * f, -11, 15, 4.4, 2.1, t); flame(c, 9 * f, -8, 8, 3, 4.6, t);
    if (!T) { c.fillStyle = "rgba(70,66,78,0.4)"; c.beginPath(); c.ellipse(0, -24, 6, 4, 0, 0, 6.2832); c.fill(); c.fillStyle = "rgba(70,66,78,0.26)"; c.beginPath(); c.ellipse(2, -32, 7.5, 5, 0, 0, 6.2832); c.fill(); }
  }
  // Names and armor sit above each tank. When tanks stand close together the labels would overlap, so they stack in rows,
  // each tied to its tank by a thin line.
  function labelText(armor, label) { return label + " " + (armor > 0 ? armor : "down"); }
  function layoutLabels(c, p, items) {
    var fs = tpx(11, 9.5), rows = [];
    c.font = "700 " + fs + "px " + p.font;
    items.forEach(function (it) { it.w = c.measureText(it.txt).width + 10 * ts; it.lx = Math.max(it.w / 2, Math.min(W - it.w / 2, it.x)); });
    var rowH = fs + 12 * ts;
    items.slice().sort(function (a, b) { return a.x - b.x; }).forEach(function (it) {
      var r = 0, clash = function (o) { return Math.abs(o.lx - it.lx) < (o.w + it.w) / 2 && Math.abs((o.gy + o.row * rowH) - (it.gy + r * rowH)) < rowH - 2; };
      while (r < 4 && rows.some(function (o) { return clash(o); })) r++;
      it.row = r; rows.push(it);
    });
    return fs;
  }
  function drawLabel(c, p, it, fs) {
    var col = it.mine ? p["--tk-you"] : p["--tk-foe"], frac = Math.max(0, it.armor) / 100, off = it.row * (fs + 12 * ts), ty = -(38 + 3.5) * ts - off;
    c.save(); c.translate(it.lx, fy(it.gy));
    if (it.row > 0) { c.strokeStyle = p["--tk-ink"]; c.globalAlpha = 0.55; c.lineWidth = 1; c.beginPath(); c.moveTo(it.x - it.lx, -30.4 * ts - off); c.lineTo(it.x - it.lx, -29 * ts); c.stroke(); c.globalAlpha = 1; }
    c.save(); c.scale(ts, ts); c.translate(0, -off / ts);
    c.fillStyle = "rgba(10,8,16,0.78)"; rr(c, -17.5, -38, 35, 7.6, 3.8); c.fill();
    if (frac > 0) { c.fillStyle = col; rr(c, -16.5, -37, Math.max(2, 33 * frac), 5.6, 2.8); c.fill(); }
    c.strokeStyle = "rgba(10,8,16,0.8)"; c.lineWidth = 1; c.beginPath(); [0.25, 0.5, 0.75].forEach(function (q) { c.moveTo(-16.5 + 33 * q, -37); c.lineTo(-16.5 + 33 * q, -31.4); }); c.stroke();
    c.strokeStyle = p["--tk-ink"]; c.lineWidth = 1.2; c.globalAlpha = 0.9; rr(c, -17.5, -38, 35, 7.6, 3.8); c.stroke(); c.globalAlpha = 1;
    c.restore();
    c.font = "700 " + fs + "px " + p.font; c.textAlign = "center"; c.lineJoin = "round";
    c.lineWidth = Math.max(3, fs * 0.3); c.strokeStyle = p["--tk-pill"]; c.strokeText(it.txt, 0, ty);
    c.fillStyle = p["--tk-ink"]; c.fillText(it.txt, 0, ty);
    c.restore();
  }

  // ---- effects: particles, fireballs, shock rings, shake, wind streaks ----
  var CAP = 150;
  var fx = { P: [], balls: [], rings: [], shake: 0, mag: 0, streaks: [], acc: [] };
  var crand = E.mulberry32(0x7a11c0de);    // cosmetic only
  function addP(o) { if (fx.P.length >= CAP) fx.P.splice(0, fx.P.length - CAP + 1); fx.P.push(o); }
  function spawnBoom(b, kill) {
    var R = b.r, n, i, ang, sp;
    fx.balls.push({ x: b.x, y: b.y, r: R, age: 0, max: kill ? 0.7 : 0.5 });
    fx.rings.push({ x: b.x, y: b.y, r: R, age: 0, max: 0.5 });
    n = R >= 40 ? 14 : R >= 26 ? 10 : 6;
    for (i = 0; i < n; i++) {
      ang = (0.12 + crand() * 0.76) * Math.PI; sp = (70 + crand() * 150) * (0.7 + R / 60);
      addP({ k: "deb", x: b.x, y: b.y, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, age: 0, max: 0.7 + crand() * 0.6, s: 1.6 + crand() * 2.4, rot: crand() * 6, vr: (crand() - 0.5) * 14, hi: crand() < 0.5 });
    }
    for (i = 0; i < 6; i++) { ang = crand() * 6.2832; sp = 90 + crand() * 160; addP({ k: "spark", x: b.x, y: b.y, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp + 40, age: 0, max: 0.25 + crand() * 0.25 }); }
    n = R >= 40 ? 8 : 5;
    for (i = 0; i < n; i++) addP({ k: "dust", x: b.x + (crand() - 0.5) * R * 1.4, y: b.y + crand() * 4, vx: (crand() - 0.5) * 36, vy: 10 + crand() * 26, age: 0, max: 0.9 + crand() * 0.6, s: R * (0.5 + crand() * 0.35), a: 0.55 });
    n = R >= 40 ? 5 : 3;
    for (i = 0; i < n; i++) addP({ k: "smoke", x: b.x + (crand() - 0.5) * R * 0.8, y: b.y + R * 0.2, vx: (crand() - 0.5) * 20, vy: 22 + crand() * 22, age: 0, max: 1.3 + crand() * 0.8, s: R * (0.35 + crand() * 0.25), a: 0.5 });
  }
  function spawnPop(pt) {
    var i, ang, sp;
    fx.rings.push({ x: pt[0], y: pt[1], r: 15, age: 0, max: 0.3 });
    for (i = 0; i < 5; i++) { ang = crand() * 6.2832; sp = 50 + crand() * 90; addP({ k: "spark", x: pt[0], y: pt[1], vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, age: 0, max: 0.3 }); }
  }
  function killBoom(k) {
    var t = rs.tanks[k], c = E.tankCenter(view.h, t);
    spawnBoom({ x: c.x, y: c.y, r: 30 }, true);
    startShake(5.5);
  }
  function startShake(mag) { if (reduced()) return; fx.mag = Math.max(fx.mag * (fx.shake > 0 ? 1 : 0), mag); fx.shake = 0.38; }
  function fireFx(by, angle) {
    var tv = view.tv[by], c = E.tankCenter(view.h, rs.tanks[by]), rad = angle * Math.PI / 180, i;
    if (!tv) return;
    tv.recoil = 1; tv.flash = 1;
    for (i = 0; i < 3; i++) {
      addP({ k: "smoke", x: c.x + Math.cos(rad) * 18 * ts, y: c.y + 2 + Math.sin(rad) * 18 * ts, vx: Math.cos(rad) * (14 + crand() * 22) + (crand() - 0.5) * 10, vy: Math.sin(rad) * (14 + crand() * 22) + 8, age: 0, max: 0.6 + crand() * 0.4, s: 5 + crand() * 3, a: 0.4 });
    }
  }
  function buildStreaks() {
    var n = rs.wind === 0 ? 0 : 6 + Math.abs(rs.wind) * 2, r = E.mulberry32((rs.seed ^ 0x1b873593) >>> 0), i;
    fx.streaks = [];
    for (i = 0; i < n; i++) fx.streaks.push({ x: r() * W, y: 26 + r() * 200, l: 0.7 + r() * 0.6, ph: r() * 6.28 });
  }
  function stepFx(dt) {
    var i, q, wd = rs ? rs.wind : 0, keep = [];
    for (i = 0; i < fx.P.length; i++) {
      q = fx.P[i]; q.age += dt;
      if (q.age >= q.max) continue;
      q.x += q.vx * dt; q.y += q.vy * dt;
      if (q.k === "deb") { q.vy -= 360 * dt; q.rot += q.vr * dt; }
      else if (q.k === "spark") q.vy -= 260 * dt;
      else { q.vx += wd * 3 * dt; q.vx *= Math.pow(0.35, dt); q.vy *= Math.pow(0.55, dt); }
      keep.push(q);
    }
    fx.P = keep;
    fx.balls = fx.balls.filter(function (b) { b.age += dt; return b.age < b.max; });
    fx.rings = fx.rings.filter(function (b) { b.age += dt; return b.age < b.max; });
    if (fx.shake > 0) fx.shake = Math.max(0, fx.shake - dt);
    view.tv.forEach(function (tv) { tv.recoil = Math.max(0, tv.recoil - dt / 0.2); tv.flash = Math.max(0, tv.flash - dt / 0.1); tv.hit = Math.max(0, tv.hit - dt / 0.3); });
    // wind streaks drift with the wind and wrap round the field
    var sp = (14 + Math.abs(wd) * 9) * (wd >= 0 ? 1 : -1);
    fx.streaks.forEach(function (s) { s.x += sp * dt * s.l; if (s.x > W + 40) s.x = -40; else if (s.x < -40) s.x = W + 40; });
    // smoke rises from a tank that is badly hurt; a wreck smokes harder
    if (rs && !reduced()) {
      view.armor.forEach(function (a, k) {
        if (a > 35 || fx.P.length > 110) return;
        var rate = a <= 0 ? 7 : a <= 15 ? 4.5 : 2.2, t = rs.tanks[k], c = E.tankCenter(view.h, t);
        fx.acc[k] = (fx.acc[k] || 0) + rate * dt;
        while (fx.acc[k] >= 1) {
          fx.acc[k] -= 1;
          addP({ k: "smoke", x: c.x + (crand() - 0.5) * 8, y: c.y + 8 + crand() * 4, vx: (crand() - 0.5) * 8, vy: 24 + crand() * 14, age: 0, max: 1.4 + crand() * 0.9, s: 5 + crand() * 3.4, a: a <= 0 ? 0.62 : 0.42 });
        }
      });
    }
    // tanks settle into a new crater instead of jumping
    for (i = 0; i < view.ty.length; i++) {
      var tg = view.h[rs.tanks[i].x];
      if (view.ty[i] === undefined || reduced()) view.ty[i] = tg;
      else { view.ty[i] += (tg - view.ty[i]) * Math.min(1, dt / 0.09); if (Math.abs(tg - view.ty[i]) < 0.05) view.ty[i] = tg; }
    }
  }
  function fxBusy() {
    var i;
    if (fx.P.length || fx.balls.length || fx.rings.length || fx.shake > 0) return true;
    for (i = 0; i < view.tv.length; i++) if (view.tv[i].recoil > 0 || view.tv[i].flash > 0 || view.tv[i].hit > 0) return true;
    for (i = 0; i < view.ty.length; i++) if (rs && view.ty[i] !== view.h[rs.tanks[i].x]) return true;
    return false;
  }

  function pathPoint(path, t) {
    var i = Math.min(path.length - 1, Math.floor(t)), j = Math.min(path.length - 1, i + 1), f = t - Math.floor(t), a = path[i], b = path[j];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  }
  // A shell: a tapered tail that fades behind it, then the head. Heavy and cluster shells and the bomblets each look different.
  function drawProj(c, p, q) {
    var kind = q.kind, head = pathPoint(q.path, q.t), pts = [head], cum = [0], i = Math.floor(q.t), acc = 0, prev = head, d, pt, s;
    var big = kind === "heavy", tiny = kind === "bomblet", tailLen = big ? 66 : tiny ? 26 : 48, wmax = big ? 5.4 : tiny ? 2.2 : kind === "cluster" ? 3.6 : 3.2;
    var warm = p.night ? "#ffb04a" : "#e0661e", tailCol = !q.mine ? p["--tk-foe"] : (kind === "shell" ? p["--tk-trail"] : warm);
    while (i >= 0 && acc < tailLen) {
      pt = q.path[i]; d = Math.hypot(pt[0] - prev[0], pt[1] - prev[1]);
      if (d > 0.05) { acc += d; pts.push(pt); cum.push(acc); prev = pt; }
      i--;
    }
    c.lineCap = "round";
    for (s = 1; s < pts.length; s++) {
      var u = Math.min(1, cum[s] / tailLen), w = wmax * Math.pow(1 - u, 0.9) + 0.4, al = Math.pow(1 - u, 1.3);
      if (big || kind === "cluster") { c.globalAlpha = al * 0.28; c.strokeStyle = warm; c.lineWidth = w * 2.4; c.beginPath(); c.moveTo(pts[s - 1][0], fy(pts[s - 1][1])); c.lineTo(pts[s][0], fy(pts[s][1])); c.stroke(); }
      c.globalAlpha = al * 0.95; c.strokeStyle = tailCol; c.lineWidth = w;
      c.beginPath(); c.moveTo(pts[s - 1][0], fy(pts[s - 1][1])); c.lineTo(pts[s][0], fy(pts[s][1])); c.stroke();
    }
    c.globalAlpha = 1;
    var ang = pts.length > 1 ? Math.atan2(fy(head[1]) - fy(pts[1][1]), head[0] - pts[1][0]) : 0, hx = head[0], hy = fy(head[1]);
    if (big || kind === "cluster") { var gl = blob("fire", FIRE); c.globalAlpha = 0.55; c.drawImage(gl, hx - 12, hy - 12, 24, 24); c.globalAlpha = 1; }
    var name = big ? "shell-heavy" : kind === "cluster" || tiny ? "shell-cluster" : "shell-normal";
    if (drawSprite(c, name, hx, hy, ang, false, 0, tiny ? 0.6 : 1)) return;
    c.save(); c.translate(hx, hy); c.rotate(ang); c.strokeStyle = "rgba(10,6,18,0.7)"; c.lineWidth = 1;
    if (big) {
      rr(c, -6.5, -2.7, 13, 5.4, 2.7); c.fillStyle = "#2f2a3a"; c.fill(); c.stroke();
      c.fillStyle = warm; c.fillRect(1, -2.7, 2.4, 5.4);
      c.fillStyle = p["--tk-ink"]; c.beginPath(); c.moveTo(6.5, -2.2); c.lineTo(9.5, 0); c.lineTo(6.5, 2.2); c.closePath(); c.fill();
    } else if (kind === "cluster") {
      c.fillStyle = p["--tk-ink"]; c.beginPath(); c.arc(0, 0, 3.8, 0, 6.2832); c.fill(); c.stroke();
      c.strokeStyle = warm; c.lineWidth = 1.4; c.beginPath(); c.moveTo(-1.2, -3.5); c.lineTo(-1.2, 3.5); c.stroke();
    } else if (tiny) {
      c.fillStyle = p["--tk-ink"]; c.beginPath(); c.arc(0, 0, 2.1, 0, 6.2832); c.fill(); c.stroke();
    } else {
      rr(c, -4, -1.7, 8, 3.4, 1.7); c.fillStyle = p["--tk-ink"]; c.fill(); c.stroke();
    }
    c.restore();
  }

  function drawFireballs(c, p) {
    var ex = sprite("explosion");
    fx.balls.forEach(function (b) {
      var u = b.age / b.max, e = 1 - (1 - u) * (1 - u), R = b.r * (0.5 + 0.75 * e), x = b.x, y = fy(b.y);
      if (ex) {
        var m = SPRITES.explosion, fw = ex.img.naturalWidth / m.frames, fh = ex.img.naturalHeight, fr = Math.min(m.frames - 1, Math.floor(u * m.frames)), D = 2.6 * b.r;
        c.drawImage(ex.img, fr * fw, 0, fw, fh, x - D / 2, y - D / 2, D, D);
        return;
      }
      var a = 1 - u, g = c.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, "rgba(255,250,222," + a + ")"); g.addColorStop(0.35, "rgba(255,196,80," + (0.95 * a) + ")");
      g.addColorStop(0.72, "rgba(235,90,30," + (0.7 * a) + ")"); g.addColorStop(1, "rgba(120,30,20,0)");
      c.fillStyle = g; c.beginPath(); c.arc(x, y, R, 0, 6.2832); c.fill();
      if (u < 0.2) { c.globalAlpha = (1 - u / 0.2) * 0.85; c.fillStyle = "#fff"; c.beginPath(); c.arc(x, y, b.r * 0.85, 0, 6.2832); c.fill(); c.globalAlpha = 1; }
    });
    fx.rings.forEach(function (b) {
      var u = b.age / b.max, e = 1 - (1 - u) * (1 - u);
      c.globalAlpha = 0.6 * (1 - u); c.strokeStyle = p["--tk-ink"]; c.lineWidth = 3.2 * (1 - u) + 0.6;
      c.beginPath(); c.arc(b.x, fy(b.y), b.r * (0.7 + 1.25 * e), 0, 6.2832); c.stroke();
    });
    c.globalAlpha = 1;
  }
  function drawParticles(c, p, front) {
    var i, q, u, s, bl;
    for (i = 0; i < fx.P.length; i++) {
      q = fx.P[i];
      if ((q.k === "deb" || q.k === "spark") !== front) continue;
      u = q.age / q.max;
      if (q.k === "dust" || q.k === "smoke") {
        s = q.s * (1 + 1.4 * u); bl = q.k === "dust" ? blob("dust", DUST) : blob(p.night ? "smoke-n" : "smoke", p.night ? SMOKE_N : SMOKE);
        c.globalAlpha = q.a * Math.pow(1 - u, 1.2); c.drawImage(bl, q.x - s, fy(q.y) - s, 2 * s, 2 * s);
      } else if (q.k === "deb") {
        c.globalAlpha = 1 - u * u * u; c.fillStyle = q.hi ? p["--tk-ground-hi"] : p["--tk-ground-lo"];
        c.save(); c.translate(q.x, fy(q.y)); c.rotate(q.rot); c.fillRect(-q.s / 2, -q.s / 2, q.s, q.s * 0.7); c.restore();
      } else {
        c.globalAlpha = 1 - u; c.strokeStyle = "#ffd98a"; c.lineWidth = 1.4;
        c.beginPath(); c.moveTo(q.x, fy(q.y)); c.lineTo(q.x - q.vx * 0.035, fy(q.y - q.vy * 0.035)); c.stroke();
      }
    }
    c.globalAlpha = 1;
  }
  function drawStreaks(c, p, T) {
    if (!fx.streaks.length) return;
    var dir = rs.wind > 0 ? 1 : -1, L = 12 + Math.abs(rs.wind) * 3.2;
    c.strokeStyle = p["--tk-ink"]; c.lineWidth = 1.2; c.lineCap = "round";
    fx.streaks.forEach(function (s) {
      var wob = T ? Math.sin(T * 0.002 + s.ph) * 3 : 0, l = L * s.l;
      c.globalAlpha = 0.16 + 0.12 * s.l; c.beginPath(); c.moveTo(s.x - dir * l, s.y + wob); c.lineTo(s.x, s.y + wob); c.stroke();
    });
    c.globalAlpha = 1;
  }
  function drawWindHud(c, p) {
    var wd = rs.wind, ax = W / 2, fs = Math.round(tpx(13, 10.5)), txt = "Wind " + Math.abs(wd), len = 14 + Math.abs(wd) * 5, ph = fs + 9 + (wd !== 0 ? 11 : 0), pw, wy;
    c.font = "700 " + fs + "px " + p.font; c.textAlign = "center";
    pw = Math.max(c.measureText(txt).width + 22, len + 30);
    c.globalAlpha = 0.74; c.fillStyle = p["--tk-pill"]; rr(c, ax - pw / 2, 5, pw, ph, 9); c.fill(); c.globalAlpha = 1;
    c.fillStyle = p["--tk-ink"]; c.fillText(txt, ax, 5 + fs + 1);
    if (wd !== 0) {
      var s = wd > 0 ? 1 : -1; wy = 5 + fs + 9;
      c.strokeStyle = p["--tk-ink"]; c.lineWidth = 2; c.lineCap = "round"; c.lineJoin = "round";
      c.beginPath(); c.moveTo(ax - s * len / 2, wy); c.lineTo(ax + s * len / 2, wy);
      c.moveTo(ax + s * len / 2, wy); c.lineTo(ax + s * (len / 2 - 6), wy - 4.5); c.moveTo(ax + s * len / 2, wy); c.lineTo(ax + s * (len / 2 - 6), wy + 4.5); c.stroke();
    }
  }

  var lastTs = 0;
  function redraw() { draw(lastTs); }
  function draw(now) {
    var p = palette(), c = ctx2d, i, T = reduced() ? 0 : (now || 0);
    if (!rs) return;
    var h = view.h.length ? view.h : rs.h;
    if (!h.length) return;
    lastTs = now || 0;
    if (!sc) buildScenery();
    ts = Math.min(1.45, Math.max(1, 520 / Math.max(1, canvas.clientWidth))); cssScale = Math.max(0.2, canvas.clientWidth / W);
    if (backDirty) renderBack(p);
    if (terrainDirty) { renderTerrain(h, p); sceneDirty = true; }
    if (sceneDirty) renderScene();
    var sx = 0, sy = 0;
    if (fx.shake > 0 && !reduced()) { var m = fx.mag * (fx.shake / 0.38); sx = Math.sin(T * 0.11) * m; sy = Math.cos(T * 0.17 + 1) * m * 0.7; }
    c.setTransform(SCALE, 0, 0, SCALE, 0, 0);
    c.clearRect(0, 0, W, H);
    if (sx || sy) {
      c.drawImage(layA, -OV + sx * 0.2, -OV + sy * 0.2, W + 2 * OV, H + 2 * OV);
      c.drawImage(layB, -OV + sx * 0.55, -OV + sy * 0.55, W + 2 * OV, H + 2 * OV);
      c.drawImage(terr, -OV + sx, -OV + sy, W + 2 * OV, H + 2 * OV);
    } else c.drawImage(scene, -OV, -OV, W + 2 * OV, H + 2 * OV);
    drawTwinkle(c, p, T);
    c.save(); c.translate(sx, sy);
    drawStreaks(c, p, T);
    // earlier landings
    c.font = "700 " + Math.round(tpx(11, 9.5)) + "px " + p.font; c.textAlign = "left"; c.lineJoin = "round";
    view.marks.forEach(function (mk) {
      var x = mk[0], y = fy(mk[1]);
      c.strokeStyle = p["--tk-pill"]; c.lineWidth = 4.2; c.beginPath(); c.moveTo(x - 4 * ts, y - 8 * ts); c.lineTo(x + 4 * ts, y); c.moveTo(x + 4 * ts, y - 8 * ts); c.lineTo(x - 4 * ts, y); c.stroke();
      c.lineWidth = 3.2; c.strokeText(String(mk[2]), x + 7 * ts, y - 2);
      c.strokeStyle = p["--tk-mark"]; c.lineWidth = 2; c.beginPath(); c.moveTo(x - 4 * ts, y - 8 * ts); c.lineTo(x + 4 * ts, y); c.moveTo(x + 4 * ts, y - 8 * ts); c.lineTo(x - 4 * ts, y); c.stroke();
      c.fillStyle = p["--tk-mark"]; c.fillText(String(mk[2]), x + 7 * ts, y - 2);
    });
    // where earlier shells went: a dotted path
    view.trails.forEach(function (t) {
      c.strokeStyle = t.mine ? p["--tk-trail"] : p["--tk-foe"]; c.globalAlpha = t.mine ? 0.6 : 0.4; c.lineWidth = 1.8; c.setLineDash([2, 6]); c.lineCap = "round";
      c.beginPath();
      t.path.forEach(function (q, k) { if (k === 0) c.moveTo(q[0], fy(q[1])); else c.lineTo(q[0], fy(q[1])); });
      c.stroke();
    });
    c.setLineDash([]); c.globalAlpha = 1;
    drawParticles(c, p, false);
    // tanks
    rs.tanks.forEach(function (t, k) {
      var gy = view.ty[k] === undefined || reduced() ? h[t.x] : view.ty[k], barrel = k === 0 ? (busy ? view.aim[0] : aim.angle) : view.aim[k];
      var slope = Math.max(-0.45, Math.min(0.45, Math.atan2(h[Math.min(W - 1, t.x + 13)] - h[Math.max(0, t.x - 13)], 26)));
      drawTank(c, p, k, t.x, gy, view.armor[k], barrel === undefined ? t.aim : barrel, k === 0, T, slope);
    });
    // aim stub: a few dots at the start of the path, so the barrel's angle is easy to read
    if (!busy && rs.status === "playing") {
      c.fillStyle = p["--tk-trail"]; c.strokeStyle = "rgba(0,0,0,0.35)"; c.lineWidth = 1;
      E.previewPoints(rs, aim.angle, aim.power, 4).forEach(function (q) { c.beginPath(); c.arc(q[0], fy(q[1]), 2.4, 0, 6.2832); c.fill(); c.stroke(); });
    }
    view.proj.forEach(function (q) { drawProj(c, p, q); });
    drawFireballs(c, p);
    drawParticles(c, p, true);
    var items = rs.tanks.map(function (t, k) {
      return { x: t.x, gy: view.ty[k] === undefined || reduced() ? h[t.x] : view.ty[k], armor: view.armor[k], mine: k === 0, txt: labelText(view.armor[k], k === 0 ? "You" : (rs.tanks.length > 2 ? "Enemy " + k : "Enemy")) };
    });
    var lfs = layoutLabels(c, p, items);
    items.forEach(function (it) { drawLabel(c, p, it, lfs); });
    c.restore();
    drawWindHud(c, p);
  }

  // ---- text ----
  function describeField() {
    var me = rs.tanks[0], parts = ["Artillery field. Your tank is at the left with " + me.armor + " armor."];
    rs.tanks.slice(1).forEach(function (t, k) {
      parts.push((rs.tanks.length > 2 ? "Enemy " + (k + 1) : "The enemy") + (t.armor > 0 ? " has " + t.armor + " armor and stands about " + Math.abs(t.x - me.x) + " units to your right." : " is destroyed."));
    });
    parts.push("Wind: " + windText(rs.wind) + ".");
    if (rs.grav !== 0.1) parts.push("Gravity is 0.6 of normal.");
    parts.push("Shot " + Math.min(rs.shots.length + 1, MAX) + " of " + MAX + ".");
    return parts.join(" ");
  }

  function paintHud() {
    var me = rs.tanks[0];
    $("tk-shotn").textContent = "Shot " + Math.min(rs.shots.length + (rs.status === "playing" ? 1 : 0), MAX) + " of " + MAX;
    $("tk-armor").textContent = "Your armor " + me.armor;
    $("tk-foes").textContent = rs.tanks.slice(1).map(function (t, k) { return (rs.tanks.length > 2 ? "Enemy " + (k + 1) + " " : "Enemy ") + (t.armor > 0 ? t.armor : "down"); }).join(", ");
    $("tk-wind").textContent = "Wind " + windText(rs.wind);
    $("tk-wind-arrow").textContent = rs.wind === 0 ? "" : (rs.wind > 0 ? "→" : "←");
    var chip = $("tk-wind").parentNode, pips = $("tk-wind-pips");
    if (!pips) { chip.classList.add("tk-chip-wind"); pips = document.createElement("span"); pips.id = "tk-wind-pips"; pips.className = "tk-pips"; pips.setAttribute("aria-hidden", "true"); chip.appendChild(pips); for (var q = 0; q < 5; q++) { var pp = document.createElement("span"); pp.className = "tk-pip"; pips.appendChild(pp); } }
    Array.prototype.forEach.call(pips.children, function (pp, q) { pp.classList.toggle("on", q < Math.ceil(Math.abs(rs.wind) / 2)); });
    var g = $("tk-grav"); g.hidden = rs.grav === 0.1;
    canvas.setAttribute("aria-label", describeField());
  }

  function paintControls() {
    var play = rs.status === "playing";
    $("tk-controls").hidden = !play;
    $("tk-angle").value = String(180 - aim.angle);
    $("tk-power").value = String(aim.power);
    $("tk-angle-out").textContent = angleText(aim.angle);
    $("tk-power-out").textContent = String(aim.power);
    $("tk-angle").setAttribute("aria-valuetext", angleText(aim.angle));
    E.WEAPON_IDS.forEach(function (id) {
      var b = $("tk-w-" + id), left = E.ammoLeft(rs, id);
      b.setAttribute("aria-pressed", aim.weapon === id ? "true" : "false");
      b.disabled = left <= 0 || busy;
      var n = b.querySelector(".tk-w-n");
      n.textContent = left > 50 ? "unlimited" : left + " left";
    });
    $("tk-fire").disabled = busy || !play;
  }

  function say(t) { lastText = t; $("tk-status").textContent = t; }

  function shotMessage(res) {
    var w = wname(res.shot.weapon), single = rs.tanks.length === 2, who = single ? "the enemy" : "the nearest enemy", out = [];
    if (res.dealt > 0) {
      var ids = Object.keys(res.hitBy).map(Number).sort();
      var bits = ids.map(function (i) {
        var t = rs.tanks[i], nm = single ? "Enemy" : "Enemy " + i;
        return t.armor > 0 ? nm + " armor " + t.armor : nm + " destroyed";
      });
      out.push("Hit. " + bits.join(", ") + ".");
    } else if (!res.nearest) out.push(w + " left the field.");
    else if (res.nearest.dx < 5) out.push(w + " landed beside " + who + " and did no damage.");
    else out.push(w + " landed " + res.nearest.dx + (res.nearest.short ? " short of " : " beyond ") + who + ".");
    if (res.returns.length) {
      var hits = res.returns.filter(function (r) { return r.hit; }), dmg = hits.reduce(function (a, r) { return a + r.dmg; }, 0);
      if (!hits.length) out.push("Return fire missed.");
      else out.push("Return fire hit you for " + dmg + ". Your armor is " + rs.tanks[0].armor + ".");
    }
    if (res.status === "won") out.push("All enemy tanks are destroyed.");
    else if (res.status === "lost") out.push(res.reason === "armor" ? "Your tank is destroyed." : "You are out of shots.");
    return out.join(" ");
  }

  // ---- view state ----
  function syncView() {
    view.h = rs.h.slice();
    view.armor = rs.tanks.map(function (t) { return t.armor; });
    view.aim = rs.tanks.map(function (t, k) { return k === 0 ? aim.angle : t.aim; });
    view.proj = [];
    view.scars = allBooms.slice();
    view.ty = rs.tanks.map(function (t) { return view.h[t.x]; });
    while (view.tv.length < rs.tanks.length) view.tv.push({ recoil: 0, flash: 0, hit: 0 });
    terrainDirty = true;
  }
  function marks() {
    var m = [];
    rs.shots.forEach(function (s, k) { s.land.forEach(function (l) { m.push([l[0], l[1], k + 1]); }); });
    return m;
  }
  function trailsOf(res) {
    var t = [];
    res.phases.forEach(function (ph) { ph.groups.forEach(function (g) { g.forEach(function (f) { t.push({ mine: ph.by === 0, path: f.path }); }); }); });
    return t;
  }
  function commitBooms(res) {
    res.phases.forEach(function (ph) { ph.booms.forEach(function (b) { allBooms.push({ x: b.x, y: b.y, r: b.r }); }); });
  }

  // ---- the loop ----
  // One requestAnimationFrame loop drives the shot animation and the idle life of the field (flags, streaks, clouds, smoke).
  // It runs at full rate while a shot is in the air, about 30 a second otherwise, and not at all when the tab is hidden,
  // the canvas is off screen or the visitor prefers reduced motion (then the field is drawn only when something changes).
  var anim = null, lastStep = 0, inView = true;
  function needsLoop() { return busy || (!reduced() && inView && !(document.hidden)); }
  function loop(ts) {
    raf = 0;
    if (!needsLoop()) { lastStep = 0; return; }
    var el = lastStep ? ts - lastStep : 16.7;
    if (!busy && el < 30) { raf = host.requestAnimationFrame(loop); return; }
    lastStep = ts;
    var dt = Math.min(50, el);
    if (busy) animStep(dt);
    stepFx(dt / 1000);
    draw(ts);
    if (needsLoop()) raf = host.requestAnimationFrame(loop); else lastStep = 0;
  }
  function kick() { if (!raf && rs && needsLoop()) raf = host.requestAnimationFrame(loop); }

  // ---- animation ----
  // Frame counts below are at 60 frames a second; they are scaled by the real time between frames.
  function startGroup() {
    var a = anim, ph = a.phases[a.pi];
    a.group = ph.groups[a.gi]; a.tick = 0; a.waiting = 0; a.applied = false; a.ended = a.group.map(function () { return false; });
    if (a.gi === 0) { view.aim[ph.by] = ph.angle; fireFx(ph.by, ph.angle); }
    a.mark = view.trails.length;
    a.group.forEach(function () { view.trails.push({ mine: ph.by === 0, path: [] }); });
  }
  function animate(res, pre, done) {
    anim = { res: res, done: done, phases: res.phases, pi: 0, gi: 0, tick: 0, waiting: 0, group: null, ended: [], mark: 0, slow: res.kills.length > 0 || (res.status === "lost" && res.reason === "armor") };
    view.h = pre.h.slice(); view.armor = pre.armor.slice(); view.aim = pre.aim.slice(); view.proj = []; view.trails = [];
    view.marks = marks().filter(function (m) { return m[2] < res.n; });
    view.scars = pre.scars.slice(); view.ty = rs.tanks.map(function (t) { return view.h[t.x]; });
    terrainDirty = true;
    fx.P = []; fx.balls = []; fx.rings = [];
    startGroup();
    kick();
  }
  function landed(ph, b) {
    E.carve(view.h, b.x, b.y, b.r);
    view.scars.push({ x: b.x, y: b.y, r: b.r }); terrainDirty = true;
    spawnBoom(b, false);
    var close = b.hits.length > 0, i;
    for (i = 0; i < b.near.length; i++) if (b.near[i].d <= b.r + 30) close = true;
    if (close) startShake((b.hits.length ? 6 : 3.5) * (0.7 + b.r / 60));
    b.hits.forEach(function (hh) { if (view.tv[hh.t]) view.tv[hh.t].hit = 1; });
    if (FX) FX.play(b.hits.length ? "capture" : "place");
  }
  function kindOf(ph, gi) { return ph.weapon === "cluster" ? (gi === 0 ? "cluster" : "bomblet") : ph.weapon; }
  function endAnim() {
    var a = anim;
    anim = null;
    fx.P = []; fx.balls = []; fx.rings = []; fx.shake = 0;
    commitBooms(a.res);
    syncView(); view.trails = trailsOf(a.res); view.marks = marks();
    draw(lastTs); a.done();
  }
  function animStep(dt) {
    var a = anim;
    if (!a) return;
    if (skip) { endAnim(); return; }
    var fe = dt / 16.667, ph = a.phases[a.pi], speed = ph.by === 0 ? 3 : 5, all = true, lastGroup = a.gi === ph.groups.length - 1, lastPhase = a.pi === a.phases.length - 1;
    a.tick += speed * fe;
    view.proj = [];
    a.group.forEach(function (f, k) {
      var last = f.path.length - 1, at = Math.min(a.tick, last), tr = view.trails[a.mark + k];
      if (tr) tr.path = f.path.slice(0, Math.floor(at) + 1);
      if (!a.ended[k] && at >= last) {
        a.ended[k] = true;
        if (f.boom) {
          var b = ph.booms.filter(function (bb) { return Math.abs(bb.x - f.boom.x) < 0.001 && Math.abs(bb.y - f.boom.y) < 0.001; })[0];
          if (b) landed(ph, b);
        } else if (ph.weapon === "cluster" && a.gi === 0) spawnPop(f.path[last]);
      }
      if (!a.ended[k]) { view.proj.push({ path: f.path, t: at, kind: kindOf(ph, a.gi), mine: ph.by === 0 }); all = false; }
    });
    if (all) {
      a.waiting += fe;
      if (a.waiting >= 14 && lastGroup && !a.applied) {
        // this group has landed: show its armor result
        a.applied = true;
        ph.armor.forEach(function (ar, k) {
          if (ar < view.armor[k]) { if (view.tv[k]) view.tv[k].hit = 1; if (ar <= 0 && view.armor[k] > 0) killBoom(k); }
        });
        view.armor = ph.armor.slice();
      }
      var need = !lastGroup && ph.weapon === "cluster" ? 5 : (lastGroup && lastPhase && a.slow ? 38 : 14);
      if (a.waiting >= need) {
        if (!lastGroup) a.gi += 1;
        else if (!lastPhase) { a.pi += 1; a.gi = 0; }
        else { endAnim(); return; }
        startGroup();
      }
    }
  }

  // ---- saving ----
  function persist(done) {
    var s = G.getGame(NAME);
    s.today = { v: E.VERSION, idx: idx, shots: rs.shots.map(function (x) { return [x.angle, x.power, x.weapon]; }), done: !!done };
    G.setGame(NAME, s);
  }

  // ---- play ----
  function fire() {
    if (busy || rs.status !== "playing") return;
    if (rs.shots.length === 0) G.track("game_start", NAME);
    var pre = { h: rs.h.slice(), armor: rs.tanks.map(function (t) { return t.armor; }), aim: rs.tanks.map(function (t, k) { return k === 0 ? aim.angle : t.aim; }), scars: allBooms };
    var res = E.fire(rs, aim.angle, aim.power, aim.weapon);
    if (!res.ok) { say("That weapon has no ammunition left."); return; }
    persist(false);
    busy = true; skip = false;
    paintControls();
    function after() {
      busy = false; skip = false;
      paintHud(); paintControls();
      say(shotMessage(res));
      if (FX && res.returns.some(function (r) { return r.hit; })) { FX.play("bad"); FX.vibrate(30); }
      else if (FX && res.dealt > 0) FX.play("good");
      if (rs.status !== "playing") { finish(true); return; }
      if (E.ammoLeft(rs, aim.weapon) <= 0) setWeapon("shell");
      $("tk-fire").focus({ preventScroll: true });
    }
    if (reduced()) {
      commitBooms(res); syncView(); view.trails = trailsOf(res); view.marks = marks(); redraw(); after();
    } else animate(res, pre, after);
  }

  function setAngle(a) { aim.angle = Math.max(0, Math.min(180, Math.round(a))); paintControls(); if (!busy) redraw(); }
  function setPower(p) { aim.power = Math.max(10, Math.min(100, Math.round(p))); paintControls(); if (!busy) redraw(); }
  function setWeapon(w) {
    if (busy || rs.status !== "playing" || E.ammoLeft(rs, w) <= 0) return;
    aim.weapon = w; paintControls();
  }

  // ---- result ----
  function shotLine(s, k) {
    var o = s.outcome === "hit" ? "Hit, " + s.dealt + " damage." : s.outcome === "near" ? "Close." : "Missed.";
    return "Shot " + (k + 1) + ": " + wname(s.weapon) + ", angle " + angleText(s.angle) + ", power " + s.power + ". " + o;
  }

  function shareText() {
    var won = rs.status === "won", n = rs.shots.length;
    return "Tanklink " + (idx + 1) + " " + (won ? n : "X") + "/" + MAX + "\n\n" + E.squares(rs) + "\nArmor " + rs.tanks[0].armor + "%\n\n" + URL_;
  }

  function finish(fresh) {
    var won = rs.status === "won", n = rs.shots.length, armor = rs.tanks[0].armor;
    var saved = G.getGame(NAME);
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, idx, won, n);
      saved.today = { v: E.VERSION, idx: idx, shots: rs.shots.map(function (x) { return [x.angle, x.power, x.weapon]; }), done: true };
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (won ? n : "loss"));
      var c = { game: NAME, idx: idx, won: won, shots: n, clean: won && armor === 100 };
      if (host.PLAch) host.PLAch.check(c);
      if (won && host.PLConfetti) { if (c.clean) host.PLConfetti.big(); else host.PLConfetti.small(); }
      G.submitScore(NAME, idx, won ? n : 99).then(function (r) {
        $("tk-pct").textContent = G.describePercentile(r);
        if (r && host.PLAch) host.PLAch.check({ game: NAME, idx: idx, won: won, shots: n, clean: c.clean, pct: r.percentile, total: r.total });
      });
    } else {
      var sp = G.savedPercentile(NAME, idx);
      if (sp) $("tk-pct").textContent = G.describePercentile(sp);
    }
    var s = saved.stats || G.emptyStats();
    G.paintNote($("tk-saver"), s, idx, true, NAME);
    $("tk-controls").hidden = true;
    $("tk-result").hidden = false;
    $("tk-result-head").textContent = won ? "Won in " + plural(n, "shot", "shots") : (armor <= 0 ? "Your tank was destroyed" : "Out of shots");
    var left = rs.tanks.slice(1).filter(function (t) { return t.armor > 0; });
    $("tk-reveal").textContent = won ? "Every enemy tank is down, and you finished with " + armor + "% armor." :
      plural(left.length, "enemy tank is", "enemy tanks are") + " still standing" + (left.length === 1 ? " with " + left[0].armor + " armor." : ".");
    $("tk-played").textContent = s.played;
    $("tk-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("tk-streak").textContent = s.streak;
    $("tk-max").textContent = s.max;
    var tot = 0, cnt = 0, k;
    for (k in s.dist) { tot += Number(k) * s.dist[k]; cnt += s.dist[k]; }
    $("tk-avg").textContent = cnt ? "Average shots in a win: " + (tot / cnt).toFixed(1) + "." : "";
    $("tk-squares").textContent = E.squares(rs);
    $("tk-squares").setAttribute("aria-label", "Your shots: " + rs.shots.map(function (x) { return x.outcome === "hit" ? "hit" : x.outcome === "near" ? "close" : "miss"; }).join(", "));
    var list = $("tk-review"); list.textContent = "";
    rs.shots.forEach(function (x, i) { var li = document.createElement("li"); li.textContent = shotLine(x, i); list.appendChild(li); });
    tick();
    if (fresh) $("tk-result").scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
  }

  function tick() {
    var el = $("tk-next-in");
    if (!el || $("tk-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now;
    el.textContent = Math.floor(ms / 3600000) + " h " + ("0" + Math.floor((ms % 3600000) / 60000)).slice(-2) + " min";
  }

  // ---- input ----
  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target, tag = t && t.tagName, k = e.key, step = e.shiftKey ? 5 : 1;
    if (tag === "TEXTAREA" || tag === "A" || tag === "SUMMARY") return;
    if (k === "Escape") { if (busy) { skip = true; e.preventDefault(); } return; }
    if (rs.status !== "playing") return;
    if (busy) { if (k === " " || k === "Enter") { skip = true; e.preventDefault(); } return; }
    if (k === "ArrowLeft") setAngle(aim.angle + step);
    else if (k === "ArrowRight") setAngle(aim.angle - step);
    else if (k === "ArrowUp") setPower(aim.power + step);
    else if (k === "ArrowDown") setPower(aim.power - step);
    else if (k === "1") setWeapon("shell");
    else if (k === "2") setWeapon("heavy");
    else if (k === "3") setWeapon("cluster");
    else if ((k === " " || k === "Enter") && tag !== "BUTTON") fire();
    else return;
    e.preventDefault();
  }

  // Dragging from your tank with a mouse or pen also sets angle and power. Touch uses the sliders so the page can still scroll.
  var dragging = false;
  function dragAim(e) {
    var r = canvas.getBoundingClientRect(), c = E.tankCenter(rs.h, rs.tanks[0]);
    var x = (e.clientX - r.left) * W / r.width - c.x, y = H - (e.clientY - r.top) * H / r.height - c.y;
    var a = Math.atan2(y, x) * 180 / Math.PI;
    if (y < 0) a = x >= 0 ? 0 : 180;
    setAngle(a);
    setPower(Math.sqrt(x * x + y * y) / 2.6);
  }

  function wire() {
    $("tk-angle").addEventListener("input", function () { setAngle(180 - Number(this.value)); });
    $("tk-power").addEventListener("input", function () { setPower(Number(this.value)); });
    E.WEAPON_IDS.forEach(function (id) { $("tk-w-" + id).addEventListener("click", function () { setWeapon(id); }); });
    $("tk-fire").addEventListener("click", fire);
    $("tk-play").addEventListener("keydown", onKey);
    canvas.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "touch" || busy || rs.status !== "playing") return;
      dragging = true; canvas.setPointerCapture(e.pointerId); dragAim(e); canvas.focus({ preventScroll: true });
    });
    canvas.addEventListener("pointermove", function (e) { if (dragging) dragAim(e); });
    canvas.addEventListener("pointerup", function () { dragging = false; });
    canvas.addEventListener("pointercancel", function () { dragging = false; });
    // the footer's theme toggle changes the palette; repaint when it does
    try { new MutationObserver(function () { repaint(); if (!busy) redraw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] }); } catch (e) { /* optional */ }
    // motion preference, tab visibility and scrolling the canvas out of view all start or stop the idle animation
    try { if (mql) mql.addEventListener("change", function () { if (!busy) redraw(); kick(); }); } catch (e) { /* optional */ }
    document.addEventListener("visibilitychange", kick);
    try { new IntersectionObserver(function (es) { inView = es[es.length - 1].isIntersecting; kick(); }).observe(canvas); } catch (e) { /* optional */ }
    host.PLShareText = shareText;   // the share row (share.js) reads this when the player taps a button
    host.setInterval(tick, 30000);
  }

  function start() {
    idx = G.dayIndex(new Date(), EPOCH);
    var dow = new Date().getDay();
    twist = E.TWISTS[dow];
    $("tk-number").textContent = "Map " + (idx + 1);
    var tw = $("tk-twist");
    if (tw) { $("tk-twist-name").textContent = twist.name + "."; $("tk-twist-text").textContent = twist.text; tw.hidden = false; }
    var saved = G.getGame(NAME), today = saved.today, rep = null;
    if (today && today.idx === idx && today.v === E.VERSION && Array.isArray(today.shots)) {
      rep = E.replay(idx, dow, today.shots);
      if (rep.error) rep = null;
    }
    if (rep) {
      rs = rep.state;
      var last = rep.results[rep.results.length - 1];
      rep.results.forEach(commitBooms);
      wire(); syncView(); view.marks = marks();
      if (last) view.trails = trailsOf(last);
    } else {
      rs = E.createRound(idx, dow);
      wire(); syncView();
    }
    buildScenery(); buildStreaks();
    $("tk-loading").hidden = true;
    $("tk-game").hidden = false;
    paintHud(); paintControls(); draw(0);
    kick();
    host.setTimeout(loadSprites, 400);
    if (rep && rep.results.length) say("Restored: " + rs.shots.length + " of " + MAX + " shots fired. " + shotMessage(rep.results[rep.results.length - 1]));
    if (rs.status !== "playing") finish(!(today && today.done));
  }

  G.ready.then(start);
})();
