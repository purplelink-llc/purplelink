/* Frontlink: a short turn-based tactics game on a 7 by 6 map, the same battlefield for everyone each day.
   Part 1 is the pure engine (map, movement, damage, enemy turn, replay). It also loads under Node for tests.
   Part 2 is the page: a grid of buttons, an action bar and a log. Nothing here reads the clock except the day number.

   Art: tiles, units and effects are vector drawings (inline SVG built with createElementNS, colours in frontlink.css).
   Sprite slots let generated art replace any of them with no code change. Drop WebP files into /assets/games/frontlink/
   and list the names that exist in /assets/games/frontlink/pack.json ({"sprites": ["tile-plains", ...]}); only listed
   names are requested, and a file that fails to load leaves the vector drawing in place, silently. The manifest is SPRITES
   below. Every sprite is a 128 x 128 px WebP (a 128 px frame = one tile); anchors are pixels inside a frame.
     tile-plains, tile-forest, tile-mountain, tile-water, tile-road, tile-hq-player, tile-hq-enemy
         128x128, opaque (fills the whole tile), anchor 0,0. Light comes from the top left. No grid lines or borders.
         tile-road is one image for every road tile (no neighbour joins). The HQ tiles include their own ground.
     unit-infantry|tank|artillery-player|enemy
         128x128, transparent background, anchor 64,108 (the point the unit stands on) lands at 50%, 84% of the tile.
         Draw the figure only: the game adds the team base, ground shadow, HP bar and acted marker. Player units face
         right, enemy units face left (the enemy sprites are NOT mirrored by the game). Keep the figure inside about
         100 x 90 px so it clears the HP bar at the bottom.
     fx-hit, fx-explosion
         384x128 strip of 3 frames side by side, each 128x128, transparent, anchor 64,64 (frame centre) lands on the
         tile centre. Played over about 0.3 s (hit) and 0.45 s (explosion).
     fx-flag
         128x128, transparent, anchor 30,118 (the foot of the pole) lands at 24%, 90% of the tile; the capture marker.
   See docs/games-sprites.md. */
(function () {
  "use strict";

  // ===================== Part 1: engine =====================
  var W = 7, H = 6, N = W * H, MAXDAY = 6, EPOCH = "2026-10-04";
  var MY_HQ = (H - 1) * W, FOE_HQ = W - 1;      // bottom left and top right
  var KINDS = {
    I: { name: "Infantry", move: 3, min: 1, max: 1 },
    T: { name: "Tank", move: 4, min: 1, max: 1 },
    A: { name: "Artillery", move: 2, min: 2, max: 3 }
  };
  var TERRAIN = {
    p: { name: "plains", stars: 0 }, r: { name: "road", stars: 0 }, f: { name: "forest", stars: 1 },
    m: { name: "mountain", stars: 2 }, w: { name: "water", stars: 0 }
  };
  // Movement cost to enter a tile. A kind with no entry for a terrain cannot enter it.
  var COST = { I: { p: 1, r: 1, f: 2, m: 3 }, T: { p: 1, r: 1, f: 2 }, A: { p: 1, r: 1, f: 2 } };
  // Base damage, attacker kind then defender kind, before HP and cover.
  var BASE = { I: { I: 5, T: 1, A: 6 }, T: { I: 7, T: 5, A: 7 }, A: { I: 5, T: 6, A: 5 } };
  var VALUE = { I: 1, T: 2.5, A: 2 };            // how much the enemy cares about each kind
  // Weekday twists, keyed by day of week (Sunday = 0). Day 0 of the puzzle count is a Sunday.
  var TWISTS = {
    1: { name: "Standard", text: "Each side has one Infantry, one Tank and one Artillery.", me: "ITA", foe: "ITA" },
    2: { name: "Armor rush", text: "The enemy has two Tanks and one Infantry. You have one of each kind.", me: "ITA", foe: "TTI" },
    3: { name: "Artillery duel", text: "Each side has two Artillery and one Infantry.", me: "IAA", foe: "IAA" },
    4: { name: "Mountain pass", text: "A mountain ridge splits the map. Each side has two Infantry and one Tank.", me: "IIT", foe: "IIT", ridge: "m" },
    5: { name: "Fast start", text: "Every unit moves one tile further on day 1.", me: "ITA", foe: "ITA", fast: true },
    6: { name: "Double front", text: "A river with two crossings. Each side has four weaker units of 6 HP.", me: "IITA", foe: "IITA", hp: 6, ridge: "w" },
    0: { name: "Siege", text: "The enemy Artillery sits behind forest. You have an extra Tank.", me: "ITTA", foe: "ITA", siege: true }
  };
  var MY_SLOTS = [4 * W + 1, 5 * W + 1, 4 * W, 3 * W, 5 * W + 2];
  var FOE_SLOTS = MY_SLOTS.map(function (t) { return N - 1 - t; });

  var NB = [];
  (function () {
    for (var t = 0; t < N; t++) {
      var r = Math.floor(t / W), c = t % W, a = [];
      if (r > 0) a.push(t - W);
      if (c > 0) a.push(t - 1);
      if (c < W - 1) a.push(t + 1);
      if (r < H - 1) a.push(t + W);
      NB.push(a);
    }
  })();

  function rowOf(t) { return Math.floor(t / W); }
  function colOf(t) { return t % W; }
  function dist(a, b) { return Math.abs(rowOf(a) - rowOf(b)) + Math.abs(colOf(a) - colOf(b)); }
  function where(t) { return "row " + (rowOf(t) + 1) + ", column " + (colOf(t) + 1); }
  function dowOf(idx) { return ((idx % 7) + 7) % 7; }
  function twistFor(idx) { return TWISTS[dowOf(idx)]; }

  function mulberry32(a) {
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function rollTerrain(x) { return x < 0.52 ? "p" : x < 0.66 ? "r" : x < 0.84 ? "f" : x < 0.92 ? "m" : "w"; }

  // The HQ to HQ path that crosses the fewest tiles failing `ok` (a path of only good tiles when one exists).
  function route(t, ok) {
    var cost = [], prev = [], seen = [], i, c;
    for (i = 0; i < N; i++) { cost.push(99); prev.push(-1); seen.push(false); }
    cost[MY_HQ] = 0;
    for (c = 0; c < N; c++) {
      var a = -1;
      for (i = 0; i < N; i++) if (!seen[i] && (a < 0 || cost[i] < cost[a])) a = i;
      seen[a] = true;
      for (var k = 0; k < NB[a].length; k++) {
        var b = NB[a][k], w = cost[a] + (ok(t[b]) ? 0 : 1);
        if (w < cost[b]) { cost[b] = w; prev[b] = a; }
      }
    }
    var path = [], x = FOE_HQ;
    while (x !== -1) { path.push(x); x = prev[x]; }
    return path;
  }

  var GROUND = function (x) { return x === "p" || x === "r" || x === "f"; };

  // The map is point-symmetric (the enemy half is the player half turned around), then two tiles are nudged so
  // it is only mirror-ish. HQ surroundings are always open ground. A draw is kept only when a tank can drive
  // from HQ to HQ without any carving, so a crossing on a ridge or river is open to both sides; the next
  // draw is tried otherwise (the carve at the end is a last resort that is not reached in practice).
  function buildMap(idx) {
    var t, salt;
    for (salt = 0; salt < 64; salt++) {
      t = drawMap(idx, salt);
      if (route(t, GROUND).every(function (x) { return GROUND(t[x]); })) return t;
    }
    route(t, GROUND).forEach(function (x) { if (!GROUND(t[x])) t[x] = "r"; });
    return t;
  }

  function drawMap(idx, salt) {
    var tw = twistFor(idx), rng = mulberry32((Math.imul(idx + 7, 0x9E3779B1) ^ 0x5F356495 ^ Math.imul(salt, 0x85EBCA6B)) >>> 0), t = [], i, r;
    for (i = 0; i < 4; i++) rng();
    for (i = 0; i < N; i++) t.push("p");
    for (i = 0; i < N / 2; i++) { t[i] = rollTerrain(rng()); t[N - 1 - i] = t[i]; }
    var lane = Math.floor(rng() * 3), keep = {};
    if (tw.ridge) {
      for (r = 0; r < H / 2; r++) {
        var a = r * W + 3;
        t[a] = t[N - 1 - a] = r === lane ? "r" : tw.ridge;
        keep[a] = keep[N - 1 - a] = true;
      }
    }
    var zone = {};
    for (i = 0; i < N; i++) if (dist(i, MY_HQ) <= 2 || dist(i, FOE_HQ) <= 2) zone[i] = true;
    for (i = 0; i < N; i++) if (zone[i] && (t[i] === "w" || t[i] === "m")) t[i] = "p";
    t[MY_HQ] = t[FOE_HQ] = "p";
    for (r = 0; r < 2; r++) {
      var j = Math.floor(rng() * N);
      if (!zone[j] && !keep[j] && "pfr".indexOf(t[j]) >= 0) t[j] = t[j] === "p" ? "f" : "p";
    }
    if (tw.siege) [5, 4, 12, 11].forEach(function (x) { t[x] = "f"; });   // forest in front of the enemy Artillery
    return t;
  }

  function mkUnit(side, n, k, tile, hp) { return { id: side + n, side: side, k: k, t: tile, hp: hp, done: false, cap: false }; }

  function newGame(idx) {
    var tw = twistFor(idx), hp = tw.hp || 10, units = [], i;
    for (i = 0; i < tw.me.length; i++) units.push(mkUnit("p", i, tw.me[i], MY_SLOTS[i], hp));
    var fs = FOE_SLOTS.slice(0, tw.foe.length);
    if (tw.siege) fs = [13, 12, 5];   // Infantry and Tank forward, Artillery in the corner
    for (i = 0; i < tw.foe.length; i++) units.push(mkUnit("e", i, tw.foe[i], fs[i], hp));
    return {
      idx: idx, twist: tw, terrain: buildMap(idx), units: units, day: 1, over: false, won: false, days: 0, reason: "",
      lost: 0, mine: tw.me.length, dayStats: [{ kills: 0, hit: false }]
    };
  }

  function clone(S) {
    var c = {};
    for (var k in S) c[k] = S[k];
    c.units = S.units.map(function (u) { return { id: u.id, side: u.side, k: u.k, t: u.t, hp: u.hp, done: u.done, cap: u.cap }; });
    c.dayStats = S.dayStats.map(function (d) { return { kills: d.kills, hit: d.hit }; });
    return c;
  }

  function unitById(S, id) { for (var i = 0; i < S.units.length; i++) if (S.units[i].id === id) return S.units[i]; return null; }
  function unitAt(S, t) { for (var i = 0; i < S.units.length; i++) if (S.units[i].t === t) return S.units[i]; return null; }
  function stars(S, t) { return TERRAIN[S.terrain[t]].stars; }
  function moveOf(S, u) { return KINDS[u.k].move + (S.twist.fast && S.day === 1 ? 1 : 0); }

  // Tiles the unit may stop on (own tile included) mapped to their movement cost. Units may pass through friends, never foes.
  function reach(S, u) {
    var allow = moveOf(S, u), best = [], occ = [], i, c;
    for (i = 0; i < N; i++) { best.push(99); occ.push(null); }
    S.units.forEach(function (v) { occ[v.t] = v; });
    var buckets = [];
    for (c = 0; c <= allow; c++) buckets.push([]);
    best[u.t] = 0; buckets[0].push(u.t);
    for (c = 0; c <= allow; c++) {
      for (i = 0; i < buckets[c].length; i++) {
        var a = buckets[c][i];
        if (best[a] !== c) continue;
        for (var k = 0; k < NB[a].length; k++) {
          var b = NB[a][k], cost = COST[u.k][S.terrain[b]];
          if (!cost || (occ[b] && occ[b].side !== u.side)) continue;
          if (c + cost <= allow && c + cost < best[b]) { best[b] = c + cost; buckets[c + cost].push(b); }
        }
      }
    }
    var out = {};
    for (i = 0; i < N; i++) if (best[i] <= allow && (!occ[i] || occ[i] === u)) out[i] = best[i];
    return out;
  }

  // Enemy units this unit could hit from the tile `from`. Artillery cannot move and fire in one turn.
  function targets(S, u, from) {
    if (u.k === "A" && from !== u.t) return [];
    var K = KINDS[u.k];
    return S.units.filter(function (v) { var d = dist(from, v.t); return v.side !== u.side && d >= K.min && d <= K.max; });
  }
  function inRange(k, a, b) { var d = dist(a, b); return d >= KINDS[k].min && d <= KINDS[k].max; }

  function damage(attKind, attHp, defKind, defHp, cover) {
    return Math.round(BASE[attKind][defKind] * attHp / 10 * (1 - 0.1 * cover * defHp / 10));
  }

  // What an attack from the tile `from` would do. The defender hits back with its remaining HP, but only
  // from inside its own range, so Artillery (range 2 to 3) never answers an adjacent attacker.
  function preview(S, u, from, v) {
    var dealt = Math.min(v.hp, damage(u.k, u.hp, v.k, v.hp, stars(S, v.t))), left = v.hp - dealt, counter = 0;
    if (left > 0 && inRange(v.k, v.t, from)) counter = Math.min(u.hp, damage(v.k, left, u.k, u.hp, stars(S, from)));
    return { dealt: dealt, left: left, counter: counter, own: u.hp - counter, kills: left <= 0, dies: u.hp - counter <= 0 };
  }

  function nm(u, lower) { return (u.side === "p" ? (lower ? "your " : "Your ") : (lower ? "the enemy " : "Enemy ")) + KINDS[u.k].name; }
  function say(ev, side, text, tiles) { ev.push({ side: side, text: text, tiles: tiles || [] }); }

  function remove(S, u) {
    S.units = S.units.filter(function (x) { return x !== u; });
    if (u.side === "p") S.lost++;
  }
  function finish(S, won, reason, ev, text) {
    if (S.over) return;
    S.over = true; S.won = won; S.days = S.day; S.reason = reason;
    say(ev, "sys", text);
  }
  function checkEnd(S, ev) {
    if (S.over) return;
    if (!S.units.some(function (u) { return u.side === "e"; })) finish(S, true, "destroyed", ev, "Every enemy unit is destroyed. You win on day " + S.day + ".");
    else if (!S.units.some(function (u) { return u.side === "p"; })) finish(S, false, "wiped", ev, "All your units are destroyed.");
  }

  // One unit's whole action: move, then optionally attack. Shared by both sides.
  function doAction(S, u, to, tgt, ev) {
    var from = u.t, ds = S.dayStats[S.day - 1], tiles = [from, to];
    var text = to !== from ? nm(u) + " moves to " + where(to) : nm(u) + " at " + where(from) + " holds position";
    u.t = to; u.done = true;
    u.cap = u.k === "I" && to === (u.side === "p" ? FOE_HQ : MY_HQ);
    if (tgt) {
      var pv = preview(S, u, to, tgt);
      tiles.push(tgt.t);
      tgt.hp -= pv.dealt;
      u.hp -= pv.counter;
      text += " and attacks " + nm(tgt, true) + ": " + pv.dealt + " damage";
      text += pv.kills ? ", destroyed." : ", " + tgt.hp + " HP left.";
      if (pv.counter) text += " It hits back for " + pv.counter + (pv.dies ? ", and " + nm(u, true) + " is destroyed." : ", leaving " + u.hp + " HP.");
      if (u.side === "p") { if (pv.dealt > 0) ds.hit = true; if (pv.kills) ds.kills++; }
      else { if (pv.counter > 0) ds.hit = true; if (pv.dies) ds.kills++; }
      if (pv.kills) remove(S, tgt);
      if (pv.dies) remove(S, u);
    } else text += ".";
    say(ev, u.side, text, tiles);
    checkEnd(S, ev);
  }

  // Cost to walk from each tile to `goal` for this kind of unit, ignoring other units.
  function field(S, kind, goal) {
    var d = [], i, c;
    for (i = 0; i < N; i++) d.push(99);
    d[goal] = 0;
    var buckets = [[goal]];
    for (c = 0; c < 60; c++) {
      var cur = buckets[c] || [];
      for (i = 0; i < cur.length; i++) {
        var a = cur[i];
        if (d[a] !== c) continue;
        var enter = COST[kind][S.terrain[a]] || 1;
        for (var k = 0; k < NB[a].length; k++) {
          var b = NB[a][k];
          if (!COST[kind][S.terrain[b]]) continue;
          if (c + enter < d[b]) { d[b] = c + enter; (buckets[c + enter] = buckets[c + enter] || []).push(b); }
        }
      }
    }
    return d;
  }

  // The enemy's turn for one unit. Fixed rules, no randomness: take the attack that does the most
  // (kills count double, a costly counter counts against it); with none worth taking, advance
  // (Infantry on your HQ, everything else on the nearest of your units), preferring cover on ties.
  function enemyAct(S, u, ev) {
    var R = reach(S, u), tiles = Object.keys(R).map(Number), bestScore = 0, best = null;
    var rush = u.k === "I" && R[MY_HQ] !== undefined;
    tiles.forEach(function (d) {
      if (rush && d !== MY_HQ) return;
      targets(S, u, d).forEach(function (v) {
        var pv = preview(S, u, d, v);
        var score = pv.dealt * VALUE[v.k] * (pv.kills ? 2 : 1) - 0.5 * pv.counter * VALUE[u.k] + 0.01 * stars(S, d);
        if (pv.dealt > 0 && score > bestScore) { bestScore = score; best = { d: d, v: v }; }
      });
    });
    if (best) { doAction(S, u, best.d, best.v, ev); return; }
    var foes = S.units.filter(function (v) { return v.side === "p"; }), f, pick = u.t, pickKey = null;
    if (u.k === "I") f = field(S, "I", MY_HQ);
    else {
      f = [];
      for (var i = 0; i < N; i++) f.push(99);
      foes.forEach(function (v) { var g = field(S, u.k, v.t); for (var j = 0; j < N; j++) if (g[j] < f[j]) f[j] = g[j]; });
    }
    tiles.forEach(function (d) {
      var key = f[d];
      if (u.k === "A" && foes.some(function (v) { return inRange("A", d, v.t); })) key = -1;
      var cover = stars(S, d), stay = d === u.t ? 1 : 0;
      if (pickKey === null || key < pickKey[0] || (key === pickKey[0] && (cover > pickKey[1] || (cover === pickKey[1] && stay > pickKey[2])))) { pickKey = [key, cover, stay]; pick = d; }
    });
    doAction(S, u, pick, null, ev);
  }

  // Ends your day: the enemy takes its turn, then captures are settled and the next day begins.
  function endDay(S) {
    var ev = [];
    if (S.over) return ev;
    say(ev, "sys", "Enemy turn, day " + S.day + ".");
    if (S.units.some(function (u) { return u.side === "e" && u.cap; })) {
      finish(S, false, "captured", ev, "The enemy has held your headquarters for a full turn. It is captured.");
      return ev;
    }
    S.units.filter(function (u) { return u.side === "e"; }).forEach(function (u) {
      if (!S.over && S.units.indexOf(u) >= 0) enemyAct(S, u, ev);
    });
    if (S.over) return ev;
    if (S.units.some(function (u) { return u.side === "p" && u.cap; })) {
      finish(S, true, "captured", ev, "Your Infantry held the enemy headquarters through the enemy turn. It is captured. You win on day " + S.day + ".");
      return ev;
    }
    if (S.day >= MAXDAY) { finish(S, false, "days", ev, "Day " + MAXDAY + " is over and the enemy still stands. You are out of days."); return ev; }
    S.day++;
    S.units.forEach(function (u) { u.done = false; });
    S.dayStats.push({ kills: 0, hit: false });
    say(ev, "sys", "Day " + S.day + " of " + MAXDAY + ". Your move.");
    return ev;
  }

  // Applies one of your actions: unit id, destination tile and an optional target id. When the last unit has
  // acted the day ends by itself. Returns { ok, events } or { ok: false, error }.
  function act(S, uid, to, tid) {
    var bad = function (e) { return { ok: false, error: e }; };
    if (S.over) return bad("The round is over.");
    var u = unitById(S, uid);
    if (!u || u.side !== "p") return bad("No such unit.");
    if (u.done) return bad("That unit has already acted.");
    if (reach(S, u)[to] === undefined) return bad("That tile is out of reach.");
    var tgt = null;
    if (tid) {
      tgt = unitById(S, tid);
      if (!tgt || targets(S, u, to).indexOf(tgt) < 0) return bad("That target is out of range.");
    }
    var ev = [];
    doAction(S, u, to, tgt, ev);
    if (!S.over && !S.units.some(function (x) { return x.side === "p" && !x.done; })) ev = ev.concat(endDay(S));
    return { ok: true, events: ev };
  }

  // Rebuilds a game from its saved move list. A move is [unitId, tile, targetId or null], or ["end"].
  function replay(idx, moves) {
    var S = newGame(idx), events = [];
    for (var i = 0; i < moves.length; i++) {
      var m = moves[i], res;
      if (S.over) return { S: S, events: events, error: "moves after the end" };
      if (m && m[0] === "end") res = { ok: true, events: endDay(S) };
      else res = m && act(S, m[0], m[1], m[2] || null);
      if (!res || !res.ok) return { S: S, events: events, error: res && res.error || "bad move" };
      events = events.concat(res.events);
    }
    return { S: S, events: events };
  }

  // The result text: headline, one square per day played, units lost, link.
  var SHARE_URL = "https://purplelink.llc/games/frontlink/";
  function shareText(S) {
    var days = S.over ? S.days : S.day, row = "";
    for (var i = 0; i < days; i++) { var d = S.dayStats[i] || { kills: 0, hit: false }; row += d.kills > 0 ? "■" : d.hit ? "▣" : "□"; }
    var score = S.over && S.won ? S.days : "X";
    return "Frontlink " + (S.idx + 1) + " " + score + "/" + MAXDAY + "\n\n" + row + "\nUnits lost " + S.lost + " of " + S.mine + "\n\n" + SHARE_URL;
  }

  var Engine = {
    W: W, H: H, N: N, MAXDAY: MAXDAY, EPOCH: EPOCH, MY_HQ: MY_HQ, FOE_HQ: FOE_HQ, KINDS: KINDS, TERRAIN: TERRAIN, COST: COST, BASE: BASE, TWISTS: TWISTS,
    twistFor: twistFor, dowOf: dowOf, buildMap: buildMap, newGame: newGame, clone: clone, unitById: unitById, unitAt: unitAt,
    reach: reach, targets: targets, damage: damage, preview: preview, act: act, endDay: endDay, replay: replay, shareText: shareText,
    where: where, rowOf: rowOf, colOf: colOf, dist: dist, stars: stars, mulberry32: mulberry32
  };
  if (typeof window !== "undefined") window.PLFrontlinkEngine = Engine;
  if (typeof module !== "undefined" && module.exports) module.exports = Engine;

  // ===================== Part 2: the page =====================
  if (typeof window === "undefined" || typeof document === "undefined" || !window.PLGames) return;
  var G = window.PLGames, NAME = "frontlink", FX = window.PLFX;
  var $ = function (id) { return document.getElementById(id); };
  if (!$("fl-board")) return;
  var st = { S: null, moves: [], mode: "idle", sel: null, to: null, reach: null, targets: [], cursor: 0, recent: [], tiles: [], sprites: {}, anim: null };

  function sound(n) { if (FX) FX.play(n); }
  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.S.idx, moves: st.moves, done: !!(s.today && s.today.idx === st.S.idx && s.today.done) };
    G.setGame(NAME, s);
  }

  // ---- sprite layer: optional WebP art that replaces the vector drawing, see the header comment ----
  var SPRITE_DIR = "/assets/games/frontlink/";
  var PLACE = { unit: [50, 84], fx: [50, 50], flag: [24, 90] };   // where a sprite's anchor lands inside the tile, in percent
  var SPRITES = {};
  [["tile-plains", 128, 128, 0, 0, 1], ["tile-forest", 128, 128, 0, 0, 1], ["tile-mountain", 128, 128, 0, 0, 1], ["tile-water", 128, 128, 0, 0, 1],
    ["tile-road", 128, 128, 0, 0, 1], ["tile-hq-player", 128, 128, 0, 0, 1], ["tile-hq-enemy", 128, 128, 0, 0, 1],
    ["unit-infantry-player", 128, 128, 64, 108, 1], ["unit-infantry-enemy", 128, 128, 64, 108, 1],
    ["unit-tank-player", 128, 128, 64, 108, 1], ["unit-tank-enemy", 128, 128, 64, 108, 1],
    ["unit-artillery-player", 128, 128, 64, 108, 1], ["unit-artillery-enemy", 128, 128, 64, 108, 1],
    ["fx-hit", 128, 128, 64, 64, 3], ["fx-explosion", 128, 128, 64, 64, 3], ["fx-flag", 128, 128, 30, 118, 1]
  ].forEach(function (a) {
    SPRITES[a[0]] = { name: a[0], url: SPRITE_DIR + a[0] + ".webp", w: a[1], h: a[2], anchor: [a[3], a[4]], frames: a[5], img: null, asked: false, waiters: [] };
  });
  var pack = { ready: false, names: {} };
  // pack.json lists the sprite names that exist, so a missing file never causes a failed request.
  function askSprite(name) {
    var e = SPRITES[name];
    if (!pack.ready || !pack.names[name] || e.asked || !e.waiters.length) return;
    e.asked = true;
    var im = new Image();
    im.onload = function () { e.img = im; var w = e.waiters; e.waiters = []; w.forEach(function (f) { try { f(im); } catch (x) { /* keep the vector art */ } }); };
    im.onerror = function () { e.waiters = []; };
    im.src = e.url;
  }
  function useSprite(name, cb) {
    var e = SPRITES[name];
    if (!e) return;
    if (e.img) { cb(e.img); return; }
    e.waiters.push(cb);
    askSprite(name);
  }
  try {
    window.fetch(SPRITE_DIR + "pack.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      ((j && j.sprites) || []).forEach(function (nm) { pack.names[nm] = true; });
    }).catch(function () { /* no pack: vector art only */ }).then(function () {
      pack.ready = true;
      Object.keys(SPRITES).forEach(askSprite);
    });
  } catch (e) { /* no fetch: vector art only */ }

  // ---- vector art, built with createElementNS; every colour comes from the stylesheet ----
  var NS = "http://www.w3.org/2000/svg";
  function n1(x) { return Math.round(x * 10) / 10; }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function svgBox(cls) { return el("svg", { viewBox: "0 0 100 100", "class": cls, "aria-hidden": "true", focusable: "false" }); }
  function rect(p, x, y, w, h, c, rx) { return el("rect", { x: n1(x), y: n1(y), width: n1(w), height: n1(h), rx: rx || 0, "class": c }, p); }
  function circ(p, x, y, r, c) { return el("circle", { cx: n1(x), cy: n1(y), r: n1(r), "class": c }, p); }
  function ell(p, x, y, rx, ry, c) { return el("ellipse", { cx: n1(x), cy: n1(y), rx: n1(rx), ry: n1(ry), "class": c }, p); }
  function poly(p, pts, c) { return el("polygon", { points: pts.map(function (q) { return n1(q[0]) + "," + n1(q[1]); }).join(" "), "class": c }, p); }
  function pth(p, d, c) { return el("path", { d: d, "class": c }, p); }
  function seg(p, x1, y1, x2, y2, c, w) { return el("line", { x1: n1(x1), y1: n1(y1), x2: n1(x2), y2: n1(y2), "stroke-width": w || 1, "stroke-linecap": "round", "class": c }, p); }
  function between(rng, a, b) { return a + rng() * (b - a); }

  function tuft(g, x, y, s) {
    var m = "M" + n1(x) + " " + n1(y);
    pth(g, m + "l" + n1(-3.5 * s) + " " + n1(-8 * s) + m + "l0 " + n1(-10 * s) + m + "l" + n1(3.5 * s) + " " + n1(-8 * s), "fl-tuft");
  }
  function ground(g, rng, alt, cls) {
    rect(g, 0, 0, 100, 100, cls + (alt ? "-b" : "-a"));
    for (var i = 0; i < 2; i++) ell(g, between(rng, 14, 86), between(rng, 14, 86), between(rng, 14, 26), between(rng, 8, 14), cls === "fl-pl" ? "fl-pl-patch" : "fl-fo-patch");
  }

  function drawPlains(g, rng, alt) {
    ground(g, rng, alt, "fl-pl");
    var i, n = 4 + Math.floor(rng() * 3);
    for (i = 0; i < n; i++) tuft(g, between(rng, 10, 90), between(rng, 22, 90), 0.8 + rng() * 0.7);
    if (rng() < 0.4) { var fx = between(rng, 14, 86), fy = between(rng, 18, 86); circ(g, fx, fy, 2.4, "fl-flower"); circ(g, fx, fy, 1, "fl-flower-c"); }
  }

  var ARMS = [["n", 0, -1], ["e", 1, 0], ["s", 0, 1], ["w", -1, 0]];
  function drawRoad(g, rng, alt, nb) {
    ground(g, rng, alt, "fl-pl");
    var any = nb.n || nb.e || nb.s || nb.w, has = any ? nb : { e: true, w: true, n: false, s: false };
    tuft(g, between(rng, 8, 22), between(rng, 84, 94), 0.8); tuft(g, between(rng, 78, 92), between(rng, 18, 30), 0.8);
    circ(g, 50, 50, 24, "fl-rd-edge");
    ARMS.forEach(function (a) { if (has[a[0]]) pth(g, "M50 50L" + (50 + a[1] * 54) + " " + (50 + a[2] * 54), "fl-rd-edge fl-rd-arm fl-rd-wide"); });
    circ(g, 50, 50, 21, "fl-rd-bed");
    ARMS.forEach(function (a) { if (has[a[0]]) pth(g, "M50 50L" + (50 + a[1] * 54) + " " + (50 + a[2] * 54), "fl-rd-bed fl-rd-arm"); });
    ARMS.forEach(function (a) {
      if (!has[a[0]]) return;
      [-7, 7].forEach(function (o) {
        var jx = between(rng, -1, 1);
        if (a[1]) seg(g, 50, 50 + o + jx, 50 + a[1] * 52, 50 + o + jx, "fl-rd-rut", 2.2);
        else seg(g, 50 + o + jx, 50, 50 + o + jx, 50 + a[2] * 52, "fl-rd-rut", 2.2);
      });
      for (var d = 27 + rng() * 6; d < 98; d += between(rng, 10, 15)) {
        [-1, 1].forEach(function (sd) {
          if (rng() < 0.12) return;
          var lat = sd * (24 + between(rng, -1, 1.2)), r = between(rng, 1.7, 2.9);
          if (a[1]) { circ(g, 50 + a[1] * d, 50 + lat, r, "fl-stone"); } else { circ(g, 50 + lat, 50 + a[2] * d, r, "fl-stone"); }
        });
      }
    });
    ARMS.forEach(function (a) {
      if (has[a[0]]) return;
      [-9, 0, 9].forEach(function (lat) {
        var r = between(rng, 1.8, 2.8);
        if (a[1]) circ(g, 50 + a[1] * 24, 50 + lat, r, "fl-stone"); else circ(g, 50 + lat, 50 + a[2] * 24, r, "fl-stone");
      });
    });
  }

  function drawForest(g, rng, alt) {
    ground(g, rng, alt, "fl-fo");
    var slots = [[26, 34], [72, 30], [50, 52], [24, 72], [76, 70]], i, j, use = [];
    for (i = slots.length - 1; i > 0; i--) { j = Math.floor(rng() * (i + 1)); var tmp = slots[i]; slots[i] = slots[j]; slots[j] = tmp; }
    var count = 3 + Math.floor(rng() * 3);
    for (i = 0; i < count; i++) use.push({ x: slots[i][0] + between(rng, -5, 5), y: slots[i][1] + between(rng, -4, 4), r: between(rng, 13, 18) });
    use.sort(function (a, b) { return a.y - b.y; });
    use.forEach(function (tr) {
      ell(g, tr.x + tr.r * 0.28, tr.y + tr.r * 0.95, tr.r * 0.95, tr.r * 0.36, "fl-shadow");
      rect(g, tr.x - 2.2, tr.y + tr.r * 0.5, 4.4, tr.r * 0.62, "fl-trunk");
      circ(g, tr.x, tr.y, tr.r, "fl-tr-d");
      circ(g, tr.x - tr.r * 0.14, tr.y - tr.r * 0.14, tr.r * 0.8, "fl-tr-m");
      circ(g, tr.x - tr.r * 0.36, tr.y - tr.r * 0.38, tr.r * 0.34, "fl-tr-l");
    });
  }

  function drawMountain(g, rng, alt) {
    rect(g, 0, 0, 100, 100, "fl-mt-ground" + (alt ? "-b" : "-a"));
    ell(g, 50, 86, 44, 9, "fl-shadow");
    function peak(ax, ay, w, by, foot) {
      var m = ax + foot, f = 0.36, ly = ay + (by - ay) * f, lx = ax - w * f, rx = ax + w * f;
      poly(g, [[ax, ay], [ax - w, by], [m, by]], "fl-mt-l");
      poly(g, [[ax, ay], [m, by], [ax + w, by]], "fl-mt-d");
      var zc = [ax - w * f * 0.1, ly + 4];
      poly(g, [[ax, ay], [lx, ly], [ax - w * f * 0.5, ly - 5], zc], "fl-snow");
      poly(g, [[ax, ay], zc, [ax + w * f * 0.4, ly - 5], [rx, ly]], "fl-snow-d");
    }
    peak(between(rng, 24, 34), between(rng, 24, 32), between(rng, 22, 27), 68, between(rng, -4, 4));
    peak(between(rng, 70, 78), between(rng, 30, 38), between(rng, 20, 25), 70, between(rng, -4, 4));
    peak(between(rng, 48, 56), between(rng, 12, 20), between(rng, 30, 36), 88, between(rng, -5, 5));
    for (var i = 0; i < 4; i++) { var rx = between(rng, 8, 92), ry = between(rng, 82, 94); ell(g, rx, ry, between(rng, 2, 4), between(rng, 1.4, 2.4), "fl-rock"); }
  }

  function drawWater(g, rng, alt) {
    rect(g, 0, 0, 100, 100, alt ? "fl-wa-b" : "fl-wa-a");
    [26, 52, 78].forEach(function (y, i) {
      var holder = el("g", { transform: "translate(" + n1(-rng() * 20) + " " + n1(between(rng, -5, 5)) + ")" }, g);
      pth(holder, "M-24 " + y + "q10 -7 20 0t20 0t20 0t20 0t20 0t20 0t20 0", "fl-wave fl-wv" + (i + 1));
    });
    for (var i = 0; i < 3; i++) circ(g, between(rng, 10, 90), between(rng, 10, 90), 1.5, "fl-glint fl-gl" + (i + 1));
  }

  function drawFort(g, rng, alt) {
    ground(g, rng, alt, "fl-pl");
    tuft(g, between(rng, 6, 16), between(rng, 88, 94), 0.8); tuft(g, between(rng, 84, 94), between(rng, 88, 94), 0.8);
    ell(g, 52, 84, 38, 7, "fl-shadow");
    rect(g, 14, 56, 72, 26, "fl-fort-w");
    rect(g, 14, 56, 72, 5, "fl-fort-top");
    var x;
    for (x = 14; x < 80; x += 14) rect(g, x, 50, 8, 7, "fl-fort-w");
    rect(g, 34, 28, 32, 54, "fl-fort-k");
    rect(g, 34, 28, 11, 54, "fl-fort-lit");
    for (x = 34; x < 62; x += 11) rect(g, x, 22, 7, 7, "fl-fort-k");
    for (x = 20; x < 80; x += 8) { if (x < 30 || x > 66) seg(g, x, 66, x + 5, 66, "fl-fort-joint", 0.9); }
    pth(g, "M44 82V68a6 6 0 0 1 12 0V82z", "fl-fort-gate");
    rect(g, 40, 38, 5, 9, "fl-fort-slit", 2); rect(g, 55, 38, 5, 9, "fl-fort-slit", 2);
    seg(g, 50, 22, 50, 4, "fl-pole", 2);
    pth(g, "M50 5q8 -4 16 0t0 10q-8 4 -16 0z", "fl-tc fl-cloth");
  }

  function drawTerrain(svg, terr, rng, alt, nb, hq) {
    var g = el("g", { "class": "fl-vec" }, svg);
    if (hq) drawFort(g, rng, alt);
    else if (terr === "r") drawRoad(g, rng, alt, nb);
    else if (terr === "f") drawForest(g, rng, alt);
    else if (terr === "m") drawMountain(g, rng, alt);
    else if (terr === "w") drawWater(g, rng, alt);
    else drawPlains(g, rng, alt);
  }
  function tileSpriteName(terr, hq) {
    if (hq) return hq === "p" ? "tile-hq-player" : "tile-hq-enemy";
    return { p: "tile-plains", r: "tile-road", f: "tile-forest", m: "tile-mountain", w: "tile-water" }[terr];
  }
  function sizeOf(e) { return { w: n1(e.w * 100 / 128), h: n1(e.h * 100 / 128) }; }
  function spriteImage(e, place, frame) {
    var k = 100 / 128, x = n1(place[0] - e.anchor[0] * k), y = n1(place[1] - e.anchor[1] * k), s = sizeOf(e);
    if (e.frames === 1) return el("image", { href: e.url, x: x, y: y, width: s.w, height: s.h, preserveAspectRatio: "none" });
    var box = el("svg", { x: x, y: y, width: s.w, height: s.h, viewBox: "0 0 " + e.w + " " + e.h, overflow: "hidden" });
    el("image", { href: e.url, x: -frame * e.w, y: 0, width: e.w * e.frames, height: e.h, preserveAspectRatio: "none" }, box);
    return box;
  }
  function artFor(S, t) {
    var terr = S.terrain[t], hq = t === MY_HQ ? "p" : t === FOE_HQ ? "e" : "", r = rowOf(t), c = colOf(t);
    var rng = mulberry32(((S.idx + 3) * 7919 + t * 104729 + 1337) >>> 0);
    var nb = { n: r > 0 && S.terrain[t - W] === "r", s: r < H - 1 && S.terrain[t + W] === "r", w: c > 0 && S.terrain[t - 1] === "r", e: c < W - 1 && S.terrain[t + 1] === "r" };
    var svg = svgBox("fl-art");
    drawTerrain(svg, terr, rng, (r + c) & 1, nb, hq);
    useSprite(tileSpriteName(terr, hq), function (img) {
      var e = SPRITES[tileSpriteName(terr, hq)];
      svg.appendChild(spriteImage(e, [0, 0], 0));
      svg.setAttribute("class", "fl-art fl-has-img");
    });
    return svg;
  }

  // ---- units ----
  function drawInfantry(g) {
    rect(g, 40, 62, 7, 17, "fl-td", 2); rect(g, 52, 62, 7, 17, "fl-td", 2);
    rect(g, 38.5, 77, 10, 5, "fl-boot", 2); rect(g, 51, 77, 10, 5, "fl-boot", 2);
    rect(g, 31, 46, 9, 17, "fl-pack", 3);
    rect(g, 38, 43, 24, 25, "fl-tc", 6);
    rect(g, 38, 60, 24, 3.5, "fl-boot");
    rect(g, 44, 44, 5, 22, "fl-tl", 2);
    seg(g, 56, 52, 64, 55, "fl-tc fl-arm", 6);
    seg(g, 40, 60, 82, 46, "fl-gun-o", 5);
    seg(g, 40, 60, 82, 46, "fl-gun", 3);
    rect(g, 36, 56, 9, 6, "fl-wood", 2);
    circ(g, 65, 54.5, 3.3, "fl-skin");
    circ(g, 50, 33, 8, "fl-skin");
    pth(g, "M41 34a9 9 0 0 1 18 0z", "fl-td");
    rect(g, 40, 33, 21, 3.2, "fl-td", 1.5);
  }
  function drawTank(g) {
    rect(g, 18, 62, 64, 20, "fl-track", 10);
    [28, 39, 50, 61, 72].forEach(function (x) { circ(g, x, 72, 4, "fl-wheel"); circ(g, x, 72, 1.5, "fl-hub"); });
    pth(g, "M23 64L31 49H69L79 64z", "fl-tc");
    pth(g, "M31 49H69L71.5 53H28.5z", "fl-tl");
    rect(g, 66, 39, 20, 5.5, "fl-steel", 2);
    rect(g, 84, 37.5, 5, 8.5, "fl-steel-d", 1.5);
    rect(g, 36, 36, 30, 15, "fl-tc", 7);
    rect(g, 40, 37.5, 14, 4, "fl-tl", 2);
    ell(g, 50, 36, 6, 2.4, "fl-td");
    rect(g, 44, 56, 12, 3.5, "fl-td", 1.5);
  }
  function drawArtillery(g) {
    seg(g, 44, 70, 12, 85, "fl-steel-d fl-leg", 5);
    seg(g, 47, 72, 24, 88, "fl-steel-d fl-leg", 4);
    seg(g, 42, 60, 80, 39, "fl-gun-o", 9);
    seg(g, 42, 60, 80, 39, "fl-steel", 6);
    seg(g, 73, 43, 84, 37, "fl-steel-d", 8.5);
    pth(g, "M36 50L53 44L56 72L36 74z", "fl-tc");
    pth(g, "M36 50L53 44L53.5 49L36 55z", "fl-tl");
    circ(g, 46, 72, 10, "fl-track");
    circ(g, 46, 72, 6.4, "fl-wheel");
    circ(g, 46, 72, 2.4, "fl-tc");
    rect(g, 52, 58, 8, 6, "fl-wood", 1.5);
  }
  var DRAW = { I: drawInfantry, T: drawTank, A: drawArtillery };
  var KNAME = { I: "infantry", T: "tank", A: "artillery" };

  function maxHp() { return (st.S && st.S.twist.hp) || 10; }

  // One unit: a team base (round for you, diamond for the enemy), a ground shadow, the figure, an HP bar and an acted marker.
  function makeUnit(side, k, hp) {
    var d = document.createElement("div"), svg = svgBox("fl-fig"), base = el("g", { "class": "fl-baseg" }, svg);
    d.className = "fl-sprite"; d.setAttribute("data-side", side); d.setAttribute("data-k", k);
    ell(base, 50, 84, 33, 9.5, "fl-shadow");
    if (side === "p") ell(base, 50, 82.5, 29, 9, "fl-base");
    else poly(base, [[17, 82.5], [50, 72], [83, 82.5], [50, 93]], "fl-base");
    var body = el("g", { "class": "fl-body" }, svg), flip = el("g", side === "e" ? { "class": "fl-flip", transform: "translate(100 0) scale(-1 1)" } : { "class": "fl-flip" }, body);
    var vec = el("g", { "class": "fl-vec" }, flip);
    DRAW[k](vec);
    var img = el("g", { "class": "fl-imgslot" }, flip);
    var bar = el("g", { "class": "fl-hp" }, svg);
    rect(bar, 6, 89, 58, 9, "fl-hpbg", 3);
    var fill = rect(bar, 7.5, 90.5, 55, 6, "fl-hpf", 2);
    var i, n = hp || 10;
    for (i = 1; i < n; i++) rect(bar, 7.5 + 55 * i / n - 0.5, 90.5, 1, 6, "fl-hpt");
    var dn = el("g", { "class": "fl-dn" }, svg);
    circ(dn, 17, 17, 11, "fl-dn-bg"); rect(dn, 12.5, 11.5, 3.6, 11, "fl-dn-bar", 1); rect(dn, 18.9, 11.5, 3.6, 11, "fl-dn-bar", 1);
    d.appendChild(svg);
    var num = document.createElement("span"); num.className = "fl-hpn"; d.appendChild(num);
    useSprite("unit-" + KNAME[k] + "-" + (side === "p" ? "player" : "enemy"), function () {
      var e = SPRITES["unit-" + KNAME[k] + "-" + (side === "p" ? "player" : "enemy")];
      img.appendChild(spriteImage(e, PLACE.unit, 0));
      svg.setAttribute("class", "fl-fig fl-has-img");
    });
    return { el: d, num: num, fill: fill };
  }

  function dressUnit(sp, u, S) {
    var mx = (S.twist.hp || 10);
    sp.num.textContent = String(u.hp);
    var frac = Math.max(0, Math.min(1, u.hp / mx));
    sp.fill.setAttribute("width", n1(55 * frac));
    sp.fill.setAttribute("data-lvl", frac > 0.6 ? "hi" : frac > 0.3 ? "mid" : "lo");
    sp.el.setAttribute("data-done", u.side === "p" && u.done && !S.over ? "1" : "");
    sp.el.setAttribute("data-sel", st.sel && u.id === st.sel ? "1" : "");
  }
  function placeUnit(sp, t) {
    sp.el.style.setProperty("--r", String(rowOf(t))); sp.el.style.setProperty("--c", String(colOf(t)));
    sp.el.style.setProperty("--z", String(rowOf(t) + 1)); sp.t = t;
  }
  function spriteFor(u, S) {
    var sp = st.sprites[u.id];
    if (!sp) {
      sp = makeUnit(u.side, u.k, S.twist.hp || 10); sp.id = u.id;
      st.sprites[u.id] = sp; $("fl-units").appendChild(sp.el);
    }
    return sp;
  }
  function dropUnit(id) { var sp = st.sprites[id]; if (sp && sp.el.parentNode) sp.el.parentNode.removeChild(sp.el); delete st.sprites[id]; }
  // Puts every unit sprite where the given state says it is.
  function syncSprites(V) {
    var seen = {};
    V.units.forEach(function (u) { var sp = spriteFor(u, V); placeUnit(sp, u.t); dressUnit(sp, u, V); seen[u.id] = true; });
    Object.keys(st.sprites).forEach(function (id) { if (!seen[id]) dropUnit(id); });
  }

  function makeMark() {
    var s = svgBox("fl-mk"), d = el("g", { "class": "fl-mk-dot" }, s), r = el("g", { "class": "fl-mk-ret" }, s), x = el("g", { "class": "fl-mk-dest" }, s);
    circ(d, 50, 50, 5, "fl-mk-fill");
    [[8, 8, 1, 1], [92, 8, -1, 1], [8, 92, 1, -1], [92, 92, -1, -1]].forEach(function (c) {
      pth(r, "M" + c[0] + " " + (c[1] + c[3] * 20) + "V" + c[1] + "H" + (c[0] + c[2] * 20), "fl-mk-br");
    });
    [[50, 6, 50, 22], [50, 78, 50, 94], [6, 50, 22, 50], [78, 50, 94, 50]].forEach(function (l) { seg(r, l[0], l[1], l[2], l[3], "fl-mk-tick", 3.4); });
    pth(x, "M30 40L50 62L70 40", "fl-mk-chev");
    return s;
  }
  function makeCap() {
    var s = svgBox("fl-cap");
    circ(s, 50, 50, 43, "fl-capring");
    var g = el("g", { "class": "fl-vec" }, s);
    seg(g, 14, 38, 14, 10, "fl-pole", 2.4);
    pth(g, "M14 10L33 16L14 23z", "fl-capcloth");
    useSprite("fx-flag", function () { s.appendChild(spriteImage(SPRITES["fx-flag"], PLACE.flag, 0)); s.setAttribute("class", "fl-cap fl-has-img"); });
    return s;
  }

  // ---- the board: 42 buttons built once and updated in place, so keyboard focus is never lost ----
  function build() {
    var box = $("fl-board");
    box.textContent = "";
    for (var r = 0; r < H; r++) {
      var row = document.createElement("div");
      row.className = "fl-row"; row.setAttribute("role", "row");
      for (var c = 0; c < W; c++) {
        var t = r * W + c, b = document.createElement("button");
        b.type = "button"; b.className = "fl-tile"; b.setAttribute("role", "gridcell"); b.setAttribute("data-t", t);
        b.appendChild(artFor(st.S, t));
        var mk = makeMark(), cap = makeCap();
        b.appendChild(mk); b.appendChild(cap);
        b.addEventListener("click", onTile.bind(null, t));
        row.appendChild(b);
        st.tiles.push({ b: b, mk: mk, cap: cap });
      }
      box.appendChild(row);
    }
    box.addEventListener("keydown", onKey);
    paintLegend();
  }

  // The legend keys use the same drawings as the board.
  function paintLegend() {
    Array.prototype.forEach.call(document.querySelectorAll(".fl-key[data-terrain]"), function (k) {
      var terr = k.getAttribute("data-terrain"), svg = svgBox("fl-art");
      drawTerrain(svg, terr, mulberry32(11 + terr.charCodeAt(0)), 0, { n: false, s: false, e: false, w: false }, "");
      k.textContent = ""; k.setAttribute("aria-hidden", "true"); k.appendChild(svg);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".fl-key[data-kind]"), function (k) {
      var u = makeUnit(k.getAttribute("data-side") || "p", k.getAttribute("data-kind"), 10);
      k.textContent = ""; k.setAttribute("aria-hidden", "true"); k.appendChild(u.el);
    });
  }

  function tileLabel(t, u) {
    var S = st.S, ter = TERRAIN[S.terrain[t]].name, s = "Row " + (rowOf(t) + 1) + ", column " + (colOf(t) + 1) + ": " + ter;
    if (t === MY_HQ) s += ", your headquarters";
    if (t === FOE_HQ) s += ", enemy headquarters";
    if (u) {
      s += ", " + (u.side === "p" ? "your " : "enemy ") + KINDS[u.k].name + ", " + u.hp + " HP";
      if (u.side === "p" && !S.over) s += u.done ? ", has acted" : ", ready";
      if (u.cap) s += ", holding the headquarters";
    }
    if (st.sel && u && u.id === st.sel) s += ", selected";
    if (st.mode === "move" && st.reach && st.reach[t] !== undefined) s += t === unitOfId(st.sel).t ? ", stay here" : ", can move here";
    if (st.mode === "act" && t === st.to) s += ", destination";
    if (st.mode === "act" && u && st.targets.indexOf(u.id) >= 0) s += ", can be attacked";
    return s;
  }
  function unitOfId(id) { return unitById(st.S, id); }

  function paint() {
    var S = st.S, occ = {}, sel = st.sel ? unitOfId(st.sel) : null;
    S.units.forEach(function (u) { occ[u.t] = u; });
    for (var t = 0; t < N; t++) {
      var T = st.tiles[t], u = occ[t], b = T.b;
      b.setAttribute("data-terrain", S.terrain[t]);
      b.setAttribute("data-hq", t === MY_HQ ? "p" : t === FOE_HQ ? "e" : "");
      b.setAttribute("data-cap", (t === MY_HQ || t === FOE_HQ) && u && u.cap ? u.side : "");
      var mark = "", range = "";
      if (st.sel && u && u.id === st.sel) mark = "sel";
      if (st.mode === "move" && st.reach && st.reach[t] !== undefined) mark = mark || "reach";
      if (st.mode === "act" && t === st.to) mark = "dest";
      if (st.mode === "act" && u && st.targets.indexOf(u.id) >= 0) mark = "target";
      if (st.mode === "act" && sel && t !== st.to && (sel.k !== "A" || st.to === sel.t) && inRange(sel.k, st.to, t)) range = "1";
      b.setAttribute("data-mark", mark);
      b.setAttribute("data-range", range);
      b.setAttribute("data-recent", st.recent.indexOf(t) >= 0 ? "1" : "");
      b.setAttribute("aria-label", tileLabel(t, u));
      b.tabIndex = t === st.cursor ? 0 : -1;
    }
    var cur = $("fl-cursor");
    cur.style.setProperty("--r", String(rowOf(st.cursor))); cur.style.setProperty("--c", String(colOf(st.cursor)));
    var mine = S.units.filter(function (u) { return u.side === "p"; }), foe = S.units.filter(function (u) { return u.side === "e"; });
    $("fl-turn").textContent = S.over ? "Round over." : "Day " + S.day + " of " + MAXDAY + ". Your move.";
    Array.prototype.forEach.call($("fl-days").children, function (li, i) {
      li.setAttribute("data-s", i + 1 < S.day ? "past" : i + 1 === S.day ? (S.over ? "end" : "now") : "next");
    });
    $("fl-roster").textContent = "";
    [["Your units", mine, "p"], ["Enemy units", foe, "e"]].forEach(function (g) {
      var p = document.createElement("p"), b = document.createElement("b"), sw = document.createElement("span");
      sw.className = "fl-sw"; sw.setAttribute("data-side", g[2]); sw.setAttribute("aria-hidden", "true");
      b.textContent = g[0] + ": ";
      p.appendChild(sw); p.appendChild(b);
      p.appendChild(document.createTextNode(g[1].length ? g[1].map(function (u) { return KINDS[u.k].name + " " + u.hp + " HP" + (g[0] === "Your units" && u.done && !S.over ? " (acted)" : ""); }).join(", ") : "none left"));
      $("fl-roster").appendChild(p);
    });
    $("fl-end").disabled = S.over;
    if (!st.anim) syncSprites(S);
  }

  function focusCursor() { st.tiles[st.cursor].b.focus({ preventScroll: false }); }
  function tell(text) { $("fl-readout").textContent = text; }
  function idleHint() { return "Select one of your units with Enter or a tap. Arrow keys move around the board."; }

  // ---- motion: slides, lunges, shells, hits and explosions. All cosmetic; any input skips to the final board ----
  var RM = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function calm() { return !RM || RM.matches || typeof Element.prototype.animate !== "function"; }
  function later(ms, fn) { var A = st.anim; if (!A) return; A.timers.push(window.setTimeout(function () { if (st.anim === A) fn(); }, ms)); }
  function run(node, kf, opts) { var a = node.animate(kf, opts); if (st.anim) st.anim.anims.push(a); return a; }
  function endAnim() {
    var A = st.anim;
    if (!A) return;
    st.anim = null;
    A.timers.forEach(function (id) { window.clearTimeout(id); });
    A.anims.forEach(function (a) { try { a.cancel(); } catch (e) { /* already finished */ } });
    $("fl-fx").textContent = "";
    $("fl-banner").removeAttribute("data-show");
    $("fl-stage").removeAttribute("data-phase");
    syncSprites(st.S);
    var f = A.after; if (f) f();
  }

  function fxAt(t, cls, parent) {
    var d = document.createElement("div");
    d.className = cls; d.style.setProperty("--r", String(rowOf(t))); d.style.setProperty("--c", String(colOf(t)));
    (parent || $("fl-fx")).appendChild(d);
    later(1700, function () { if (d.parentNode) d.parentNode.removeChild(d); });
    return d;
  }
  function frames(host, name, ms) {      // plays a sprite strip when the art is loaded; false when it is not
    var e = SPRITES[name];
    if (!e || !e.img) return false;
    var box = svgBox("fl-fxs"), i;
    host.appendChild(box);
    for (i = 0; i < e.frames; i++) (function (f) {
      later(f * ms / e.frames, function () { box.textContent = ""; box.appendChild(spriteImage(e, PLACE.fx, f)); });
    })(i);
    return true;
  }
  function banner(text, side) {
    var b = $("fl-banner");
    b.setAttribute("data-side", side); b.firstChild.textContent = text;
    b.removeAttribute("data-show"); void b.offsetWidth; b.setAttribute("data-show", "1");
  }
  function spark(t, strong) {
    var d = fxAt(t, "fl-spark");
    if (frames(d, "fx-hit", 280)) return;
    var s = svgBox("fl-sparksvg");
    poly(s, [[50, 8], [58, 36], [88, 26], [66, 48], [92, 70], [60, 62], [54, 92], [44, 62], [10, 76], [34, 48], [12, 24], [42, 36]], "fl-sp1");
    circ(s, 50, 50, strong ? 15 : 11, "fl-sp2");
    d.appendChild(s);
  }
  function floatNum(t, text, kind) {
    var d = fxAt(t, "fl-dmg"), s = document.createElement("span");
    d.setAttribute("data-k", kind); s.textContent = text; d.appendChild(s);
  }
  function flash(sp) {
    if (!sp) return;
    run(sp.el, [{ filter: "brightness(1)", transform: "translateX(0)" }, { filter: "brightness(2.6) saturate(0.4)", transform: "translateX(-3px)", offset: 0.25 },
      { filter: "brightness(1.6)", transform: "translateX(3px)", offset: 0.55 }, { filter: "brightness(1)", transform: "translateX(0)" }], { duration: 320 });
  }
  function smoke(t) {
    var d = fxAt(t, "fl-smokes"), i;
    for (i = 1; i <= 3; i++) { var p = document.createElement("i"); p.className = "fl-smoke fl-sm" + i; d.appendChild(p); }
  }
  function boom(t, id) {
    var d = fxAt(t, "fl-boom");
    if (!frames(d, "fx-explosion", 460)) {
      var s = svgBox("fl-boomsvg");
      poly(s, [[50, 2], [60, 28], [90, 14], [74, 40], [98, 56], [70, 62], [80, 92], [52, 74], [40, 98], [36, 68], [6, 78], [28, 54], [4, 36], [34, 36], [30, 8], [46, 28]], "fl-bm1");
      poly(s, [[50, 20], [57, 38], [76, 32], [64, 48], [78, 62], [58, 58], [50, 78], [43, 58], [24, 64], [36, 48], [24, 34], [43, 38]], "fl-bm2");
      circ(s, 50, 50, 9, "fl-bm3");
      d.appendChild(s);
      for (var i = 1; i <= 6; i++) { var sh = document.createElement("i"); sh.className = "fl-shard fl-sh" + i; d.appendChild(sh); }
    }
    later(90, function () { if (id) dropUnit(id); });
    smoke(t);
  }

  function pxOf(t, G0) { return { x: colOf(t) * G0.pitch, y: rowOf(t) * G0.pitch }; }
  function slide(sp, from, to, ms, G0) {
    var fr = rowOf(from), fc = colOf(from), tr = rowOf(to), tc = colOf(to), pts = [[fc, fr]];
    if (fc !== tc) pts.push([tc, fr]);
    if (fr !== tr) pts.push([tc, tr]);
    var total = 0, i, cum = [0];
    for (i = 1; i < pts.length; i++) { total += Math.abs(pts[i][0] - pts[i - 1][0]) + Math.abs(pts[i][1] - pts[i - 1][1]); cum.push(total); }
    var kf = pts.map(function (p, j) {
      return { transform: "translate(" + n1((p[0] - tc) * G0.pitch) + "px," + n1((p[1] - tr) * G0.pitch) + "px)", offset: total ? cum[j] / total : j };
    });
    sp.el.style.setProperty("--z", "40");
    run(sp.el, kf, { duration: ms, easing: "ease-in-out" });
    later(ms, function () { sp.el.style.setProperty("--z", String(tr + 1)); });
  }
  function lunge(sp, from, to, G0) {
    var dx = colOf(to) - colOf(from), dy = rowOf(to) - rowOf(from), m = G0.pitch * 0.34;
    sp.el.style.setProperty("--z", "40");
    run(sp.el, [{ transform: "translate(0,0)" }, { transform: "translate(" + n1(dx * m) + "px," + n1(dy * m) + "px)", offset: 0.45 }, { transform: "translate(0,0)" }], { duration: 270, easing: "ease-out" });
  }
  function recoil(sp, from, to, G0) {
    var dx = colOf(to) - colOf(from), dy = rowOf(to) - rowOf(from), l = Math.max(1, Math.abs(dx) + Math.abs(dy)), m = G0.pitch * 0.12;
    run(sp.el, [{ transform: "translate(0,0)" }, { transform: "translate(" + n1(-dx / l * m) + "px," + n1(-dy / l * m) + "px)", offset: 0.2 }, { transform: "translate(0,0)" }], { duration: 380, easing: "ease-out" });
  }
  function shell(from, to, G0) {
    var a = pxOf(from, G0), b = pxOf(to, G0), dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy);
    var ms = Math.round(330 + len / G0.pitch * 70), arc = Math.max(G0.pitch * 0.7, len * 0.4), kf = [], i;
    for (i = 0; i <= 14; i++) {
      var k = i / 14, h = 4 * k * (1 - k);
      kf.push({ transform: "translate(" + n1(dx * k) + "px," + n1(dy * k - arc * h) + "px) scale(" + n1(0.8 + h * 0.7) + ")" });
    }
    [0, 1, 2].forEach(function (n) {
      var d = fxAt(from, "fl-shell" + (n ? " fl-shell-t" : ""));
      run(d, kf, { duration: ms, delay: n * 45, easing: "linear", fill: "both" });
      later(n * 45 + ms, function () { if (d.parentNode) d.parentNode.removeChild(d); });
    });
    return ms;
  }

  // Replays the actions of one move on a copy of the old board, so each step knows who moved, who was hit and for how much.
  function buildSteps(before, evs) {
    var V = clone(before), steps = [];
    evs.forEach(function (e) {
      if (e.side === "sys") { steps.push({ sys: e.text }); return; }
      var u = null, tgt = null;
      V.units.forEach(function (x) { if (x.t === e.tiles[0] && x.side === e.side) u = x; });
      if (!u) return;
      if (e.tiles.length > 2) tgt = unitAt(V, e.tiles[2]);
      var t0 = tgt ? tgt.hp : 0, u0 = u.hp, from = u.t;
      doAction(V, u, e.tiles[1], tgt, []);
      steps.push({
        side: e.side, id: u.id, k: u.k, from: from, to: e.tiles[1], tid: tgt ? tgt.id : null, tt: tgt ? tgt.t : -1,
        dealt: tgt ? t0 - tgt.hp : 0, counter: u0 - u.hp, thp: tgt ? tgt.hp : 0, uhp: u.hp, killed: !!tgt && V.units.indexOf(tgt) < 0, died: V.units.indexOf(u) < 0
      });
    });
    return steps;
  }

  function geometry() {
    var a = st.tiles[0].b.getBoundingClientRect(), b = st.tiles[1].b.getBoundingClientRect();
    return a.width > 0 ? { tile: a.width, pitch: b.left - a.left } : null;
  }

  // Starts the motion for one move. `before` is the board as it was, `after` runs when the motion ends or is skipped.
  function animate(before, evs, after) {
    var G0 = calm() ? null : geometry();
    if (!G0) return false;
    st.anim = { timers: [], anims: [], after: after };
    syncSprites(before);
    var steps = buildSteps(before, evs), t = 0;
    steps.forEach(function (s) {
      if (s.sys) {
        if (/^Enemy turn/.test(s.sys)) { later(t, function () { $("fl-stage").setAttribute("data-phase", "e"); banner("Enemy turn", "e"); }); t += 750; }
        else if (/^Day \d/.test(s.sys)) { later(t, function () { $("fl-stage").removeAttribute("data-phase"); banner(s.sys.replace(/ of \d+\. Your move\.$/, "") + ". Your move", "p"); }); t += 450; }
        return;
      }
      var sp = st.sprites[s.id], tsp = s.tid ? st.sprites[s.tid] : null;
      if (!sp) return;
      var dist = Math.abs(rowOf(s.from) - rowOf(s.to)) + Math.abs(colOf(s.from) - colOf(s.to)), at = t, imp;
      if (dist) {
        var dm = Math.min(520, 120 + dist * 95);
        later(at, function () { placeUnit(sp, s.to); slide(sp, s.from, s.to, dm, G0); });
        at += dm + 50;
      }
      if (s.tid) {
        if (s.k === "A") {
          later(at, function () { shell(s.to, s.tt, G0); recoil(sp, s.to, s.tt, G0); smoke(s.to); });
          imp = at + Math.round(330 + (Math.abs(rowOf(s.to) - rowOf(s.tt)) + Math.abs(colOf(s.to) - colOf(s.tt))) * 70);
        } else {
          later(at, function () { lunge(sp, s.to, s.tt, G0); });
          imp = at + 120;
        }
        later(imp, function () {
          flash(tsp); spark(s.tt, s.killed); floatNum(s.tt, "-" + s.dealt, "hit");
          if (tsp && !s.killed) { tsp.num.textContent = String(s.thp); dressHp(tsp, s.thp); }
        });
        if (s.killed) later(imp + 140, function () { boom(s.tt, s.tid); });
        var end = imp + (s.killed ? 600 : 300);
        if (s.counter > 0) {
          later(imp + 300, function () {
            flash(sp); spark(s.to, s.died); floatNum(s.to, "-" + s.counter, "counter");
            if (!s.died) { sp.num.textContent = String(s.uhp); dressHp(sp, s.uhp); }
          });
          if (s.died) later(imp + 440, function () { boom(s.to, s.id); });
          end = Math.max(end, imp + (s.died ? 740 : 560));
        }
        at = end;
      }
      later(at, function () { if (s.side === "p" && st.sprites[s.id]) st.sprites[s.id].el.setAttribute("data-done", "1"); });
      t = at + 120;
    });
    later(t + 250, endAnim);
    return true;
  }
  function dressHp(sp, hp) {
    var frac = Math.max(0, Math.min(1, hp / maxHp()));
    sp.fill.setAttribute("width", n1(55 * frac));
    sp.fill.setAttribute("data-lvl", frac > 0.6 ? "hi" : frac > 0.3 ? "mid" : "lo");
  }

  // ---- the log ----
  function logEvents(evs) {
    var ol = $("fl-log");
    evs.forEach(function (e) {
      var li = document.createElement("li");
      li.className = "fl-log-" + e.side; li.textContent = e.text;
      ol.appendChild(li);
    });
    while (ol.children.length > 90) ol.removeChild(ol.firstChild);
    ol.scrollTop = ol.scrollHeight;
  }

  // ---- choosing: select a unit, pick a tile, then Attack / Wait / Cancel ----
  function clearBar() { var bar = $("fl-actions"); bar.hidden = true; bar.textContent = ""; }
  function deselect() { st.mode = "idle"; st.sel = null; st.to = null; st.reach = null; st.targets = []; clearBar(); }

  function select(u) {
    st.mode = "move"; st.sel = u.id; st.to = null; st.targets = []; st.reach = reach(st.S, u); st.recent = [];
    clearBar(); sound("tap");
    tell(KINDS[u.k].name + " selected. Choose a marked tile to move to, or its own tile to stay. Escape deselects.");
  }
  function stepBack() {
    if (st.mode === "act") {
      var u = unitOfId(st.sel); st.mode = "move"; st.to = null; st.targets = []; clearBar(); st.cursor = u.t;
      tell("Choose another tile for the " + KINDS[u.k].name + ", or press Escape to deselect.");
    } else if (st.mode === "move") { var ut = unitOfId(st.sel).t; deselect(); st.cursor = ut; tell(idleHint()); }
    paint(); focusCursor();
  }

  function attackText(u, to, v) {
    var pv = preview(st.S, u, to, v), s = "Attack " + nmLower(v) + " at " + where(v.t) + ": about " + pv.dealt + " damage";
    s += pv.kills ? ", which destroys it." : ", leaving it " + pv.left + " HP.";
    if (!pv.kills) s += pv.counter ? " It hits back for " + pv.counter + ", leaving your " + KINDS[u.k].name + " " + pv.own + " HP." : " It cannot hit back.";
    return { pv: pv, text: s };
  }
  function nmLower(v) { return (v.side === "p" ? "your " : "enemy ") + KINDS[v.k].name; }

  function showBar() {
    var u = unitOfId(st.sel), bar = $("fl-actions"), first = null;
    bar.textContent = ""; bar.hidden = false;
    st.targets = targets(st.S, u, st.to).map(function (v) { return v.id; });
    st.targets.forEach(function (id) {
      var v = unitOfId(id), a = attackText(u, st.to, v), b = document.createElement("button"), l1 = document.createElement("span"), l2 = document.createElement("span");
      b.type = "button"; b.className = "btn btn-primary fl-act"; b.title = a.text;
      l1.textContent = "Attack " + KINDS[v.k].name + " at " + where(v.t);
      b.setAttribute("aria-label", a.text);
      l2.className = "fl-pv";
      l2.textContent = a.pv.kills ? "Deals " + a.pv.dealt + ", destroys it" : "Deals " + a.pv.dealt + ", takes " + a.pv.counter;
      b.appendChild(l1); b.appendChild(l2);
      b.addEventListener("click", function () { commit(id); });
      b.addEventListener("focus", function () { tell(a.text); });
      bar.appendChild(b);
      if (!first) first = b;
    });
    var w = document.createElement("button"); w.type = "button"; w.className = "btn btn-ghost fl-act"; w.textContent = "Wait";
    w.addEventListener("click", function () { commit(null); });
    var c = document.createElement("button"); c.type = "button"; c.className = "btn btn-ghost fl-act"; c.textContent = "Cancel";
    c.addEventListener("click", stepBack);
    bar.appendChild(w); bar.appendChild(c);
    var K = KINDS[u.k].name, dest = st.to === u.t ? "stays at " + where(st.to) : "moves to " + where(st.to);
    tell("The " + K + " " + dest + ". " + (st.targets.length ? "Choose a target, or Wait." : u.k === "A" && st.to !== u.t ? "Artillery cannot move and fire in the same turn." : "Nothing is in range. Choose Wait.") + " Escape goes back.");
    (first || w).focus();
  }

  function commit(tid) {
    var S = st.S, u = unitOfId(st.sel), to = st.to, kills0 = S.units.length, lost0 = S.lost;
    var mv = [u.id, to, tid], before = clone(S);
    var res = act(S, u.id, to, tid);
    if (!res.ok) { tell(res.error); return; }
    st.moves.push(mv);
    afterAction(res.events, to, tid ? "hit" : "move", lost0, kills0, before);
  }

  function afterAction(evs, focusTile, kind, lost0, units0, before) {
    var S = st.S, moving = false, tail = null;
    logEvents(evs);
    st.recent = [];
    evs.forEach(function (e) { e.tiles.forEach(function (t) { if (st.recent.indexOf(t) < 0) st.recent.push(t); }); });
    deselect(); st.cursor = focusTile;
    sound(S.over ? (S.won ? "win" : "lose") : S.lost > lost0 ? "bad" : S.units.length < units0 ? "capture" : kind === "hit" ? "place" : "tap");
    persist();
    var last = evs.filter(function (e) { return e.side !== "sys"; }).slice(-1)[0];
    tell(S.over ? evs[evs.length - 1].text : idleHint());
    if (S.over) tail = function () { showResult(true); };
    moving = before && animate(before, evs, tail);
    paint();
    if (S.over) { if (!moving) tail(); return; }
    focusCursor();
    if (FX && FX.kick && kind === "hit" && last && !moving) FX.kick(st.tiles[focusTile].b, "fx-pop", 300);
  }

  function onTile(t) {
    endAnim();
    var S = st.S, u = unitAt(S, t);
    st.cursor = t;
    if (S.over) { tell(u ? tileLabel(t, u) : ""); paint(); return; }
    if (st.mode === "idle") {
      if (u && u.side === "p" && !u.done) select(u);
      else if (u && u.side === "p") tell("That " + KINDS[u.k].name + " has already acted today.");
      else if (u) tell("Enemy " + KINDS[u.k].name + ", " + u.hp + " HP, on " + TERRAIN[S.terrain[t]].name + ".");
      else tell(idleHint());
    } else if (st.mode === "move") {
      if (st.reach[t] !== undefined) { st.to = t; st.mode = "act"; showBar(); paint(); return; }
      if (u && u.side === "p" && !u.done) select(u);
      else tell("That tile is out of reach. Choose a marked tile, or press Escape to deselect.");
    } else if (st.mode === "act") {
      if (u && st.targets.indexOf(u.id) >= 0) { commit(u.id); return; }
      if (t === st.to) { showBar(); paint(); return; }
      if (st.reach[t] !== undefined) { st.to = t; showBar(); paint(); return; }
      if (u && u.side === "p" && !u.done) select(u);
      else tell("Choose an action from the bar, or press Escape to go back.");
    }
    paint();
  }

  function onKey(e) {
    var t = st.cursor, r = rowOf(t), c = colOf(t), n = t;
    if (e.key === "ArrowUp") r = Math.max(0, r - 1);
    else if (e.key === "ArrowDown") r = Math.min(H - 1, r + 1);
    else if (e.key === "ArrowLeft") c = Math.max(0, c - 1);
    else if (e.key === "ArrowRight") c = Math.min(W - 1, c + 1);
    else if (e.key === "Home") c = 0;
    else if (e.key === "End") c = W - 1;
    else return;
    e.preventDefault();
    endAnim();
    n = r * W + c;
    st.cursor = n; paint(); focusCursor();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || !st.S || st.S.over || st.mode === "idle" || $("fl-game").hidden) return;
    e.preventDefault(); stepBack();
  });

  $("fl-end").addEventListener("click", function () {
    endAnim();
    var S = st.S;
    if (S.over) return;
    var lost0 = S.lost, units0 = S.units.length, before = clone(S);
    deselect();
    st.moves.push(["end"]);
    afterAction(endDay(S), st.cursor, "move", lost0, units0, before);
  });

  // ---- the result ----
  function tick() {
    var el = $("fl-next-in");
    if (!el || $("fl-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
  }

  function showResult(fresh) {
    var S = st.S, saved = G.getGame(NAME), clean = S.won && S.lost === 0;
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, S.idx, S.won, S.days);
      saved.today = { idx: S.idx, moves: st.moves, done: true, won: S.won, days: S.days };
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (S.won ? "win" + S.days : "loss"));
      if (window.PLAch) window.PLAch.check({ game: NAME, idx: S.idx, won: S.won, days: S.days, clean: clean });
      if (S.won && window.PLConfetti) { if (clean) window.PLConfetti.big(); else window.PLConfetti.small(); }
      G.submitScore(NAME, S.idx, S.won ? S.days : 99).then(function (res) {
        $("fl-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: S.idx, won: S.won, days: S.days, clean: clean, pct: res.percentile, total: res.total });
      });
    }
    var s = saved.stats || G.emptyStats();
    G.paintNote($("fl-saver"), s, S.idx, true, NAME);
    clearBar();
    $("fl-result").hidden = false;
    $("fl-result-head").textContent = S.won ? "Won on day " + S.days + " of " + MAXDAY : "Defeated";
    var why = { destroyed: "Every enemy unit was destroyed.", captured: S.won ? "Your Infantry held the enemy headquarters." : "The enemy held your headquarters.", wiped: "All your units were destroyed.", days: "Six days passed without a win." }[S.reason] || "";
    $("fl-reveal").textContent = why + " You lost " + S.lost + " of " + S.mine + " units.";
    $("fl-played").textContent = s.played;
    $("fl-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("fl-streak").textContent = s.streak;
    $("fl-max").textContent = s.max;
    $("fl-turn").textContent = "Round over.";
    tell(why);
    tick();
    if (fresh && $("fl-result").scrollIntoView) $("fl-result").scrollIntoView({ block: "nearest", behavior: FX && FX.reduced && FX.reduced() ? "auto" : "smooth" });
  }

  function start() {
    var idx = G.dayIndex(new Date(), EPOCH), tw = twistFor(idx), saved = G.getGame(NAME);
    $("fl-number").textContent = "Battle " + (idx + 1);
    $("fl-twist-name").textContent = tw.name + "."; $("fl-twist-text").textContent = tw.text; $("fl-twist").hidden = false;
    var rp = saved.today && saved.today.idx === idx && saved.today.moves ? replay(idx, saved.today.moves) : null;
    if (rp && rp.error) rp = null;          // a save that no longer replays is dropped
    st.S = rp ? rp.S : newGame(idx);
    st.moves = rp ? saved.today.moves : [];
    st.cursor = st.S.units.filter(function (u) { return u.side === "p"; })[0].t;
    $("fl-loading").hidden = true;
    $("fl-game").hidden = false;           // shown before build so the tiles can be measured
    build();
    logEvents([{ side: "sys", text: "Day 1 of " + MAXDAY + ". Your move.", tiles: [] }]);
    if (rp) logEvents(rp.events);
    window.PLShareText = function () { return shareText(st.S); };   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tick, 30000);
    paint(); tell(idleHint());
    if (st.S.over) showResult(!(saved.today && saved.today.idx === idx && saved.today.done));
  }

  G.ready.then(start);
})();
