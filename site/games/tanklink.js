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
  var view = { h: [], armor: [], aim: [], proj: [], booms: [], trails: [], marks: [] };
  var lastText = "";

  function reduced() { try { return host.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return true; } }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function wname(id) { return E.WEAPONS[id].name; }
  function angleText(a) { return a === 90 ? "90 up" : (a < 90 ? a : 180 - a) + (a < 90 ? " right" : " left"); }
  function windText(w) { return w === 0 ? "Calm" : Math.abs(w) + (w > 0 ? " toward the enemy" : " toward you"); }

  // ---- canvas ----
  var SCALE = Math.min(2, Math.max(1, Math.ceil(host.devicePixelRatio || 1)));
  canvas.width = W * SCALE; canvas.height = H * SCALE;
  var FALLBACK = { "--tk-sky": "#201830", "--tk-ground": "#4a3a2a", "--tk-edge": "#b08850", "--tk-you": "#c9a6ff", "--tk-foe": "#ff9d9d", "--tk-ink": "#f4eefa", "--tk-trail": "#d8c8f0", "--tk-mark": "#f4eefa" };
  function palette() {
    var cs = host.getComputedStyle(canvas), p = {}, k;
    for (k in FALLBACK) p[k] = cs.getPropertyValue(k).trim() || FALLBACK[k];
    p.font = cs.fontFamily || "sans-serif";
    return p;
  }
  function fy(y) { return H - y; }

  // On a narrow screen the whole field shrinks, so tanks, labels and marks are drawn a little larger to stay readable.
  var ts = 1;
  function drawTank(c, p, x, gy, armor, barrel, mine, label) {
    var col = mine ? p["--tk-you"] : p["--tk-foe"], dead = armor <= 0;
    c.save();
    c.translate(x, fy(gy)); c.scale(ts, ts);
    c.lineJoin = "round"; c.lineCap = "round";
    if (dead) {
      c.fillStyle = p["--tk-sky"]; c.strokeStyle = col; c.lineWidth = 2;
      c.beginPath(); c.moveTo(-13, 0); c.lineTo(-9, -6); c.lineTo(7, -4); c.lineTo(13, 0); c.closePath(); c.fill(); c.stroke();
      c.restore(); return;
    }
    var rad = barrel * Math.PI / 180, bx = Math.cos(rad) * 20, by = -9 - Math.sin(rad) * 20;
    c.strokeStyle = p["--tk-ink"]; c.lineWidth = 5;
    c.beginPath(); c.moveTo(0, -9); c.lineTo(bx, by); c.stroke();
    c.strokeStyle = col; c.lineWidth = 3;
    c.beginPath(); c.moveTo(0, -9); c.lineTo(bx, by); c.stroke();
    c.fillStyle = col; c.strokeStyle = p["--tk-ink"]; c.lineWidth = 2;
    c.beginPath(); c.rect(-14, -9, 28, 9); c.fill(); c.stroke();
    c.beginPath(); c.arc(0, -9, 7, Math.PI, 0); c.fill(); c.stroke();
    c.fillStyle = p["--tk-sky"]; c.strokeStyle = p["--tk-ink"]; c.lineWidth = 1.5;
    c.beginPath(); c.rect(-16, -34, 32, 6); c.fill(); c.stroke();
    c.fillStyle = col; c.fillRect(-16, -34, 32 * Math.max(0, armor) / 100, 6);
    c.fillStyle = p["--tk-ink"]; c.font = "700 11px " + p.font; c.textAlign = "center";
    c.fillText(label, 0, -39);
    c.restore();
  }

  function draw() {
    var p = palette(), c = ctx2d, i;
    ts = Math.min(1.45, Math.max(1, 520 / Math.max(1, canvas.clientWidth)));
    c.setTransform(SCALE, 0, 0, SCALE, 0, 0);
    c.clearRect(0, 0, W, H);
    c.fillStyle = p["--tk-sky"]; c.fillRect(0, 0, W, H);
    var h = view.h.length ? view.h : (rs ? rs.h : []);
    if (!h.length) return;
    // ground
    c.beginPath(); c.moveTo(0, H);
    for (i = 0; i < W; i++) c.lineTo(i, fy(h[i]));
    c.lineTo(W - 1, H); c.closePath();
    c.fillStyle = p["--tk-ground"]; c.fill();
    c.beginPath();
    for (i = 0; i < W; i++) { if (i === 0) c.moveTo(i, fy(h[i])); else c.lineTo(i, fy(h[i])); }
    c.strokeStyle = p["--tk-edge"]; c.lineWidth = 2; c.stroke();
    // wind
    var wind = rs.wind, ax = W / 2;
    c.fillStyle = p["--tk-ink"]; c.strokeStyle = p["--tk-ink"]; c.lineWidth = 2; c.font = "700 " + Math.round(14 * ts) + "px " + p.font; c.textAlign = "center";
    c.fillText(wind === 0 ? "Wind 0" : "Wind " + Math.abs(wind), ax, 14 + 8 * ts);
    if (wind !== 0) {
      var s = wind > 0 ? 1 : -1, len = 14 + Math.abs(wind) * 5;
      var wy = 20 + 12 * ts;
      c.beginPath(); c.moveTo(ax - s * len / 2, wy); c.lineTo(ax + s * len / 2, wy);
      c.moveTo(ax + s * len / 2, wy); c.lineTo(ax + s * (len / 2 - 6), wy - 5); c.moveTo(ax + s * len / 2, wy); c.lineTo(ax + s * (len / 2 - 6), wy + 5); c.stroke();
    }
    // earlier landings
    c.font = "600 " + Math.round(11 * ts) + "px " + p.font; c.textAlign = "left";
    view.marks.forEach(function (m) {
      var x = m[0], y = fy(m[1]);
      c.strokeStyle = p["--tk-mark"]; c.lineWidth = 2;
      c.beginPath(); c.moveTo(x - 4 * ts, y - 8 * ts); c.lineTo(x + 4 * ts, y); c.moveTo(x + 4 * ts, y - 8 * ts); c.lineTo(x - 4 * ts, y); c.stroke();
      c.fillStyle = p["--tk-mark"]; c.fillText(String(m[2]), x + 7 * ts, y - 2);
    });
    // trails
    view.trails.forEach(function (t) {
      c.strokeStyle = t.mine ? p["--tk-trail"] : p["--tk-foe"]; c.globalAlpha = t.mine ? 0.9 : 0.55; c.lineWidth = 2; c.setLineDash([2, 6]); c.lineCap = "round";
      c.beginPath();
      t.path.forEach(function (q, k) { if (k === 0) c.moveTo(q[0], fy(q[1])); else c.lineTo(q[0], fy(q[1])); });
      c.stroke();
    });
    c.setLineDash([]); c.globalAlpha = 1;
    // tanks
    rs.tanks.forEach(function (t, k) {
      var barrel = k === 0 ? (busy ? view.aim[0] : aim.angle) : view.aim[k];
      drawTank(c, p, t.x, h[t.x], view.armor[k], barrel === undefined ? t.aim : barrel, k === 0, k === 0 ? "You" : (rs.tanks.length > 2 ? "Enemy " + k : "Enemy"));
    });
    // aim stub: a few dots at the start of the path, so the barrel's angle is easy to read
    if (!busy && rs.status === "playing") {
      c.fillStyle = p["--tk-trail"]; c.globalAlpha = 0.7;
      E.previewPoints(rs, aim.angle, aim.power, 4).forEach(function (q) { c.beginPath(); c.arc(q[0], fy(q[1]), 2.2, 0, Math.PI * 2); c.fill(); });
      c.globalAlpha = 1;
    }
    // projectiles and blasts
    c.fillStyle = p["--tk-ink"];
    view.proj.forEach(function (q) { c.beginPath(); c.arc(q[0], fy(q[1]), 3.5, 0, Math.PI * 2); c.fill(); });
    view.booms.forEach(function (b) {
      var k = Math.min(1, b.age / 14);
      c.globalAlpha = 1 - k * 0.8; c.fillStyle = p["--tk-edge"];
      c.beginPath(); c.arc(b.x, fy(b.y), b.r * (0.4 + 0.6 * k), 0, Math.PI * 2); c.fill();
      c.globalAlpha = 1; c.strokeStyle = p["--tk-ink"]; c.lineWidth = 2; c.stroke();
    });
    c.globalAlpha = 1;
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
    view.proj = []; view.booms = [];
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

  // ---- animation ----
  function animate(res, pre, done) {
    var phases = res.phases, pi = 0, gi = 0, tick = 0, waiting = 0, group = null, ended = [];
    view.h = pre.h.slice(); view.armor = pre.armor.slice(); view.aim = pre.aim.slice(); view.proj = []; view.booms = []; view.trails = []; view.marks = marks().filter(function (m) { return m[2] < res.n; });
    function finish() {
      host.cancelAnimationFrame(raf);
      syncView(); view.trails = trailsOf(res); view.marks = marks();
      draw(); done();
    }
    function startGroup() {
      group = phases[pi].groups[gi]; tick = 0; waiting = 0; ended = group.map(function () { return false; });
      if (gi === 0) view.aim[phases[pi].by] = phases[pi].angle;
    }
    startGroup();
    var showTrail = function (ph) { group.forEach(function (f) { view.trails.push({ mine: ph.by === 0, path: [] }); }); };
    var mark = view.trails.length; showTrail(phases[0]);
    function step() {
      if (skip) { finish(); return; }
      var ph = phases[pi], speed = ph.by === 0 ? 3 : 5, all = true;
      tick += speed;
      view.proj = [];
      group.forEach(function (f, k) {
        var at = Math.min(tick, f.path.length - 1), tr = view.trails[mark + k];
        if (tr) tr.path = f.path.slice(0, at + 1);
        if (!ended[k]) {
          view.proj.push(f.path[at]);
          if (at >= f.path.length - 1) {
            ended[k] = true;
            if (f.boom) {
              var b = ph.booms.filter(function (bb) { return Math.abs(bb.x - f.boom.x) < 0.001 && Math.abs(bb.y - f.boom.y) < 0.001; })[0];
              if (b) { E.carve(view.h, b.x, b.y, b.r); view.booms.push({ x: b.x, y: b.y, r: b.r, age: 0 }); }
              if (FX) FX.play(b && b.hits.length ? "capture" : "place");
            }
          }
        }
        if (!ended[k]) all = false;
      });
      view.booms.forEach(function (b) { b.age += 1; });
      view.booms = view.booms.filter(function (b) { return b.age < 16; });
      if (all) {
        waiting += 1;
        if (waiting === 1) { view.proj = []; }
        if (waiting >= 14) {
          // this group has landed: show its armor result, then the next group or phase
          if (gi === ph.groups.length - 1) { view.armor = ph.armor.slice(); }
          if (gi < ph.groups.length - 1) { gi += 1; }
          else if (pi < phases.length - 1) { pi += 1; gi = 0; }
          else { finish(); return; }
          startGroup(); mark = view.trails.length; showTrail(phases[pi]);
        }
      }
      draw();
      raf = host.requestAnimationFrame(step);
    }
    raf = host.requestAnimationFrame(step);
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
    var pre = { h: rs.h.slice(), armor: rs.tanks.map(function (t) { return t.armor; }), aim: rs.tanks.map(function (t, k) { return k === 0 ? aim.angle : t.aim; }) };
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
      syncView(); view.trails = trailsOf(res); view.marks = marks(); draw(); after();
    } else animate(res, pre, after);
  }

  function setAngle(a) { aim.angle = Math.max(0, Math.min(180, Math.round(a))); paintControls(); if (!busy) draw(); }
  function setPower(p) { aim.power = Math.max(10, Math.min(100, Math.round(p))); paintControls(); if (!busy) draw(); }
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
    try { new MutationObserver(function () { if (!busy) draw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] }); } catch (e) { /* optional */ }
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
      wire(); syncView(); view.marks = marks();
      if (last) view.trails = trailsOf(last);
    } else {
      rs = E.createRound(idx, dow);
      wire(); syncView();
    }
    $("tk-loading").hidden = true;
    $("tk-game").hidden = false;
    paintHud(); paintControls(); draw();
    if (rep && rep.results.length) say("Restored: " + rs.shots.length + " of " + MAX + " shots fired. " + shotMessage(rep.results[rep.results.length - 1]));
    if (rs.status !== "playing") finish(!(today && today.done));
  }

  G.ready.then(start);
})();
