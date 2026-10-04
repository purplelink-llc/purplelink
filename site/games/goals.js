/* The game center's progress layer: the list of games, the daily run (2, 4 and all 8 puzzles), three daily
   quests, the day's spotlight game and the weekly stamps. Everything is derived from saved progress plus a small
   `goals` record (so it follows a signed-in player between devices). Load after core.js and achievements.js. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var EPOCH = "2026-10-04", EPOCH_DOW = 0;

  // Display order. `min` is a rough playing time; `kind` groups games for quests.
  var GAMES = [
    { id: "linkle", name: "Linkle", path: "/games/linkle/", min: 3, kind: "word" },
    { id: "quadlink", name: "Quadlink", path: "/games/quadlink/", min: 5, kind: "word" },
    { id: "daily-five", name: "Daily Five", path: "/games/daily-five/", min: 2, kind: "trivia" },
    { id: "daily-photo", name: "Daily Photo", path: "/games/daily-photo/", min: 2, kind: "trivia" },
    { id: "daily-chess", name: "Daily Chess", path: "/games/daily-chess/", min: 3, kind: "logic" },
    { id: "sudoku", name: "Sudoku", path: "/games/sudoku/", min: 12, kind: "logic" },
    { id: "crossword", name: "Daily Crossword", path: "/games/crossword/", min: 10, kind: "word" },
    { id: "daily-stars", name: "Daily Stars", path: "/games/daily-stars/", min: 1, kind: "stars" }
  ];
  // More daily puzzles: they keep streaks, XP and achievements but are not part of the eight-puzzle daily run.
  var MORE = [
    { id: "landlink", name: "Landlink", path: "/games/landlink/", min: 3, kind: "guess" },
    { id: "atomlink", name: "Atomlink", path: "/games/atomlink/", min: 3, kind: "guess" },
    { id: "prizelink", name: "Prizelink", path: "/games/prizelink/", min: 3, kind: "guess" },
    { id: "citylink", name: "Citylink", path: "/games/citylink/", min: 3, kind: "guess" },
    { id: "peaklink", name: "Peaklink", path: "/games/peaklink/", min: 3, kind: "guess" },
    { id: "codelink", name: "Codelink", path: "/games/codelink/", min: 3, kind: "guess" },
    { id: "thinkerlink", name: "Thinkerlink", path: "/games/thinkerlink/", min: 3, kind: "guess" },
    { id: "riverlink", name: "Riverlink", path: "/games/riverlink/", min: 3, kind: "guess" },
    { id: "wildlink", name: "Wildlink", path: "/games/wildlink/", min: 3, kind: "guess" }
  ];
  var BY = {}; GAMES.concat(MORE).forEach(function (g) { BY[g.id] = g; });
  var QUICK_FIRST = ["daily-stars", "daily-photo", "daily-five", "daily-chess", "linkle", "quadlink", "crossword", "sudoku"];
  var TIERS = [
    { n: 2, name: "Warm-up", xp: 20 },
    { n: 4, name: "Steady", xp: 20 },     // 40 in total
    { n: 8, name: "Full run", xp: 60 }    // 100 in total
  ];

  function todayIdx() { return G.dayIndex(new Date(), EPOCH); }

  function isDone(all, id, idx) {
    var s = all[id] || {};
    if (id === "daily-stars") return (s.viewed || []).indexOf(idx) >= 0;
    return !!(s.today && s.today.idx === idx && s.today.done);
  }

  function stateOf(all, idx) {
    var S = { done: {}, count: 0, played: {} };
    GAMES.forEach(function (g) {
      S.done[g.id] = isDone(all, g.id, idx);
      if (S.done[g.id]) S.count++;
      S.played[g.id] = ((all[g.id] || {}).stats || {}).played || 0;
    });
    return S;
  }
  function anyOf(S, ids) { return ids.some(function (id) { return S.done[id]; }); }
  function countOf(S, ids) { return ids.filter(function (id) { return S.done[id]; }).length; }
  function kindIds(kind) { return GAMES.filter(function (g) { return g.kind === kind; }).map(function (g) { return g.id; }); }

  // Quest pool. f(S) -> [have, need]. "count" quests are limited to one per day.
  var QUESTS = {
    three: { text: "Finish any three games", count: true, f: function (S) { return [S.count, 3]; } },
    five: { text: "Finish any five games", count: true, f: function (S) { return [S.count, 5]; } },
    mix: { text: "Finish one word game and one logic game", f: function (S) { return [(anyOf(S, kindIds("word")) ? 1 : 0) + (anyOf(S, kindIds("logic")) ? 1 : 0), 2]; } },
    quick: { text: "Finish two quick ones: Daily Five, Daily Photo or Daily Stars", f: function (S) { return [countOf(S, ["daily-five", "daily-photo", "daily-stars"]), 2]; } },
    pair: { text: "Finish Linkle and Quadlink", f: function (S) { return [countOf(S, ["linkle", "quadlink"]), 2]; } },
    board: { text: "Finish Sudoku and Daily Chess", f: function (S) { return [countOf(S, ["sudoku", "daily-chess"]), 2]; } },
    long: { text: "Finish a long one: Sudoku or the crossword", f: function (S) { return [anyOf(S, ["sudoku", "crossword"]) ? 1 : 0, 1]; } },
    fresh: { text: "Finish a game you have played fewer than five times", f: function (S) {
      return [GAMES.some(function (g) { return S.done[g.id] && S.played[g.id] < 5 && g.id !== "daily-stars"; }) ? 1 : 0, 1]; } },
    trivia: { text: "Finish Daily Five and Daily Photo", f: function (S) { return [countOf(S, ["daily-five", "daily-photo"]), 2]; } },
    stars: { text: "Read your stars, then finish one other game", f: function (S) { return [(S.done["daily-stars"] ? 1 : 0) + (S.count - (S.done["daily-stars"] ? 1 : 0) > 0 ? 1 : 0), 2]; } }
  };
  var QUEST_IDS = Object.keys(QUESTS);

  function rng(seed) {   // mulberry32
    var a = (seed * 2654435761 + 12345) >>> 0;
    return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function questsFor(idx) {
    var r = rng(idx + 7), pool = QUEST_IDS.slice(), i, j, t;
    for (i = pool.length - 1; i > 0; i--) { j = Math.floor(r() * (i + 1)); t = pool[i]; pool[i] = pool[j]; pool[j] = t; }
    var out = [], haveCount = false;
    pool.forEach(function (id) {
      if (out.length >= 3) return;
      if (QUESTS[id].count) { if (haveCount) return; haveCount = true; }
      out.push(id);
    });
    return out;
  }
  function spotFor(idx) {
    var r = rng(idx * 31 + 3), pick = GAMES[Math.floor(r() * GAMES.length)].id;
    if (idx > 0) { var prev = GAMES[Math.floor(rng((idx - 1) * 31 + 3)() * GAMES.length)].id; if (prev === pick) pick = GAMES[(GAMES.indexOf(BY[pick]) + 3) % GAMES.length].id; }
    return pick;
  }

  function goalsRec(all) {
    var g = all.goals && typeof all.goals === "object" ? all.goals : {};
    return { d: g.d || {}, w: g.w || {}, banked: g.banked || 0 };
  }
  function tierFor(count) { return count >= 8 ? 3 : count >= 4 ? 2 : count >= 2 ? 1 : 0; }

  // Monday-to-Sunday stamps for the week containing `idx`: a day is stamped once two puzzles were finished.
  function weekStamps(g, idx) {
    var off = (((EPOCH_DOW + idx) % 7) + 6) % 7, start = idx - off, days = [], n = 0;
    for (var i = 0; i < 7; i++) {
      var d = start + i, rec = g.d[d], st = rec && rec.t >= 1;
      if (st) n++;
      days.push({ idx: d, stamped: !!st, today: d === idx, future: d > idx, tier: rec ? rec.t : 0 });
    }
    return { days: days, count: n, week: G.weekNo(idx, EPOCH_DOW) };
  }

  // Compare today's progress with what is recorded; record anything new and report it.
  function refresh() {
    var all = G.all(), idx = todayIdx(), S = stateOf(all, idx), qs = questsFor(idx), spot = spotFor(idx);
    var g = goalsRec(all), rec = g.d[idx] || { t: 0, q: 0 };
    var out = { newTier: 0, newQuests: [], spotlight: false, week: false };
    var tier = tierFor(S.count), q = rec.q;
    if (tier > rec.t) out.newTier = tier;
    qs.forEach(function (id, i) {
      var f = QUESTS[id].f(S);
      if (f[0] >= f[1] && !(q & (1 << i))) { q |= 1 << i; out.newQuests.push(QUESTS[id].text); }
    });
    if (S.done[spot] && !(q & 8)) { q |= 8; out.spotlight = true; }
    if (out.newTier || out.newQuests.length || out.spotlight) {
      g.d[idx] = { t: Math.max(rec.t, tier), q: q };
      var ws = weekStamps(g, idx);
      if (ws.count >= 5 && !g.w[ws.week]) { g.w[ws.week] = 1; out.week = true; }
      // keep the record small: fold old days into a bank of XP
      Object.keys(g.d).forEach(function (k) {
        if (Number(k) < idx - 45) { g.banked += G.TIER_XP[Math.min(3, g.d[k].t)] + G.QUEST_XP * popcount(g.d[k].q); delete g.d[k]; }
      });
      G.setGame("goals", g);
    }
    return out;
  }
  function popcount(n) { var c = 0; while (n) { c += n & 1; n >>= 1; } return c; }

  function nextFor(all, idx, exclude) {
    var S = stateOf(all, idx), spot = spotFor(idx);
    var order = [spot].concat(QUICK_FIRST.filter(function (id) { return id !== spot; }));
    // a long game is not the first suggestion when a short one is open
    var open = order.filter(function (id) { return !S.done[id] && id !== exclude; });
    var short = open.filter(function (id) { return BY[id].min <= 5; });
    var id = (short.length ? short : open)[0];
    return id ? BY[id] : null;
  }

  function streaks(all, idx) {
    var out = [];
    GAMES.concat(MORE).forEach(function (g) {
      var s = (all[g.id] || {}).stats;
      if (!s || !s.streak) return;
      var alive = s.last === idx || s.last === idx - 1;
      if (!alive) return;
      out.push({ id: g.id, name: g.name, streak: s.streak, atRisk: s.last !== idx && !isDone(all, g.id, idx) });
    });
    return out.sort(function (a, b) { return b.streak - a.streak; });
  }

  // Everything the hub and the dock draw from.
  function summary() {
    var all = G.all(), idx = todayIdx(), S = stateOf(all, idx), g = goalsRec(all), rec = g.d[idx] || { t: 0, q: 0 };
    var spot = spotFor(idx);
    var qs = questsFor(idx).map(function (id, i) {
      var f = QUESTS[id].f(S);
      return { id: id, text: QUESTS[id].text, have: Math.min(f[0], f[1]), need: f[1], done: f[0] >= f[1] || !!(rec.q & (1 << i)), xp: G.QUEST_XP };
    });
    var tier = Math.max(rec.t, tierFor(S.count));
    var nextTier = TIERS[tier] || null;
    var done = Object.assign({}, S.done);
    MORE.forEach(function (g) { done[g.id] = isDone(all, g.id, idx); });
    return {
      idx: idx, games: GAMES, more: MORE, done: done, count: S.count, total: GAMES.length, tier: tier, tiers: TIERS,
      toNextTier: nextTier ? { name: nextTier.name, need: nextTier.n - S.count, xp: nextTier.xp } : null,
      quests: qs, spotlight: { id: spot, done: S.done[spot], xp: G.QUEST_XP },
      week: weekStamps(g, idx), weekXp: G.WEEK_XP, level: G.xpOf(all), streaks: streaks(all, idx),
      next: nextFor(all, idx, null)
    };
  }

  // ---- XP bookkeeping, so a finished game can say "+22 XP" ----
  var LAST = "pl-games-lastxp";
  function readLast() { try { return JSON.parse(localStorage.getItem(LAST)); } catch (e) { return null; } }
  function writeLast(x) { try { localStorage.setItem(LAST, JSON.stringify({ xp: x.xp, level: x.level })); } catch (e) { /* ignore */ } }
  G.ready.then(function () { if (!readLast()) writeLast(G.xpOf(G.all())); });

  var seen = {};
  // Called by the achievements module whenever a game ends. Safe to call twice per game.
  function afterResult(ctx) {
    if (!ctx || !ctx.game || ctx.idx === undefined || ctx.rated) return;   // rated practice has its own rating
    if (ctx.fresh === false) { refresh(); return; }   // re-reading the horoscope: nothing new to celebrate
    var key = ctx.game + ":" + ctx.idx;
    if (seen[key]) return;
    seen[key] = true;
    var FX = window.PLFX, ok = ctx.won !== undefined ? !!ctx.won : (ctx.score === undefined ? true : ctx.score >= 3);
    var before = readLast(), r = refresh(), all = G.all(), after = G.xpOf(all);
    writeLast(after);
    var gain = before ? Math.max(0, after.xp - before.xp) : 0;
    var leveled = !!before && after.level > before.level;
    var info = {
      game: ctx.game, ok: ok, gain: gain, level: after, levelUp: leveled, titleUp: leveled ? after.title : "",
      before: before, newTier: r.newTier ? TIERS[r.newTier - 1] : null, newQuests: r.newQuests, spotlight: r.spotlight, week: r.week,
      next: nextFor(all, ctx.idx, ctx.game), summary: summary()
    };
    if (FX) {
      var big = ok && (ctx.score === 5 || ctx.clean || (ctx.tries !== undefined && ctx.tries <= 2));
      if (ctx.game === "daily-stars") FX.play("good"); else FX.play(ok ? (big ? "big" : "win") : "lose");
      var t = 900;
      if (r.newQuests.length || r.newTier || r.spotlight) { window.setTimeout(function () { FX.play("quest"); }, t); t += 700; }
      if (leveled || r.week) window.setTimeout(function () { FX.play("level"); }, t);
      if (!ok) FX.vibrate(60); else FX.vibrate([20, 40, 20]);
    }
    document.dispatchEvent(new CustomEvent("pl-reward", { detail: info }));
  }

  window.PLGoals = { GAMES: GAMES, MORE: MORE, BY: BY, TIERS: TIERS, QUESTS: QUESTS, todayIdx: todayIdx, refresh: refresh, summary: summary, afterResult: afterResult, nextFor: nextFor, spotFor: spotFor, isDone: isDone, questsFor: questsFor };
})();
