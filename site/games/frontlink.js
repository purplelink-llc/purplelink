/* Frontlink: a short turn-based tactics game on a 7 by 6 map, the same battlefield for everyone each day.
   Part 1 is the pure engine (map, movement, damage, enemy turn, replay). It also loads under Node for tests.
   Part 2 is the page: a grid of buttons, an action bar and a log. Nothing here reads the clock except the day number. */
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
  var st = { S: null, moves: [], mode: "idle", sel: null, to: null, reach: null, targets: [], cursor: 0, recent: [], tiles: [], units: [] };

  function sound(n) { if (FX) FX.play(n); }
  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.S.idx, moves: st.moves, done: !!(s.today && s.today.idx === st.S.idx && s.today.done) };
    G.setGame(NAME, s);
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
        var u = document.createElement("span"); u.className = "fl-unit"; u.setAttribute("aria-hidden", "true");
        var hp = document.createElement("span"); hp.className = "fl-hp"; hp.setAttribute("aria-hidden", "true");
        var fl = document.createElement("span"); fl.className = "fl-flag"; fl.setAttribute("aria-hidden", "true");
        b.appendChild(u); b.appendChild(hp); b.appendChild(fl);
        b.addEventListener("click", onTile.bind(null, t));
        row.appendChild(b);
        st.tiles.push({ b: b, u: u, hp: hp, fl: fl });
      }
      box.appendChild(row);
    }
    box.addEventListener("keydown", onKey);
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
    var S = st.S, occ = {};
    S.units.forEach(function (u) { occ[u.t] = u; });
    for (var t = 0; t < N; t++) {
      var T = st.tiles[t], u = occ[t], b = T.b;
      b.setAttribute("data-terrain", S.terrain[t]);
      b.setAttribute("data-hq", t === MY_HQ ? "p" : t === FOE_HQ ? "e" : "");
      T.u.textContent = u ? u.k : "";
      T.u.setAttribute("data-side", u ? u.side : "");
      T.u.setAttribute("data-done", u && u.side === "p" && u.done && !S.over ? "1" : "");
      T.hp.textContent = u ? String(u.hp) : "";
      var flag = "", mark = "";
      if (st.sel && u && u.id === st.sel) mark = "sel";
      if (st.mode === "move" && st.reach && st.reach[t] !== undefined) { mark = mark || "reach"; flag = "•"; }
      if (st.mode === "act" && t === st.to) { mark = "dest"; flag = "•"; }
      if (st.mode === "act" && u && st.targets.indexOf(u.id) >= 0) { mark = "target"; flag = "×"; }
      b.setAttribute("data-mark", mark);
      b.setAttribute("data-recent", st.recent.indexOf(t) >= 0 ? "1" : "");
      T.fl.textContent = flag;
      b.setAttribute("aria-label", tileLabel(t, u));
      b.tabIndex = t === st.cursor ? 0 : -1;
    }
    var mine = S.units.filter(function (u) { return u.side === "p"; }), foe = S.units.filter(function (u) { return u.side === "e"; });
    $("fl-turn").textContent = S.over ? "Round over." : "Day " + S.day + " of " + MAXDAY + ". Your move.";
    $("fl-roster").textContent = "";
    [["Your units", mine], ["Enemy units", foe]].forEach(function (g) {
      var p = document.createElement("p"), b = document.createElement("b");
      b.textContent = g[0] + ": ";
      p.appendChild(b);
      p.appendChild(document.createTextNode(g[1].length ? g[1].map(function (u) { return KINDS[u.k].name + " " + u.hp + " HP" + (g[0] === "Your units" && u.done && !S.over ? " (acted)" : ""); }).join(", ") : "none left"));
      $("fl-roster").appendChild(p);
    });
    $("fl-end").disabled = S.over;
  }

  function focusCursor() { st.tiles[st.cursor].b.focus({ preventScroll: false }); }
  function tell(text) { $("fl-readout").textContent = text; }
  function idleHint() { return "Select one of your units with Enter or a tap. Arrow keys move around the board."; }

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
    var mv = [u.id, to, tid];
    var res = act(S, u.id, to, tid);
    if (!res.ok) { tell(res.error); return; }
    st.moves.push(mv);
    afterAction(res.events, to, tid ? "hit" : "move", lost0, kills0);
  }

  function afterAction(evs, focusTile, kind, lost0, units0) {
    var S = st.S;
    logEvents(evs);
    st.recent = [];
    evs.forEach(function (e) { e.tiles.forEach(function (t) { if (st.recent.indexOf(t) < 0) st.recent.push(t); }); });
    deselect(); st.cursor = focusTile;
    sound(S.over ? (S.won ? "win" : "lose") : S.lost > lost0 ? "bad" : S.units.length < units0 ? "capture" : kind === "hit" ? "place" : "tap");
    persist();
    var last = evs.filter(function (e) { return e.side !== "sys"; }).slice(-1)[0];
    tell(S.over ? evs[evs.length - 1].text : idleHint());
    paint();
    if (S.over) { showResult(true); return; }
    focusCursor();
    if (FX && FX.kick && kind === "hit" && last) FX.kick(st.tiles[focusTile].b, "fx-pop", 300);
  }

  function onTile(t) {
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
    n = r * W + c;
    st.cursor = n; paint(); focusCursor();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || !st.S || st.S.over || st.mode === "idle" || $("fl-game").hidden) return;
    e.preventDefault(); stepBack();
  });

  $("fl-end").addEventListener("click", function () {
    var S = st.S;
    if (S.over) return;
    var lost0 = S.lost, units0 = S.units.length;
    deselect();
    st.moves.push(["end"]);
    afterAction(endDay(S), st.cursor, "move", lost0, units0);
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
    build();
    logEvents([{ side: "sys", text: "Day 1 of " + MAXDAY + ". Your move.", tiles: [] }]);
    if (rp) logEvents(rp.events);
    window.PLShareText = function () { return shareText(st.S); };   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tick, 30000);
    $("fl-loading").hidden = true;
    $("fl-game").hidden = false;
    paint(); tell(idleHint());
    if (st.S.over) showResult(!(saved.today && saved.today.idx === idx && saved.today.done));
  }

  G.ready.then(start);
})();
