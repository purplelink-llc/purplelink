/* Puzzle ratings for Chess Puzzles and Sudoku Unlimited. Signed-in players are rated by the rating service (the
   browser only reports which puzzle ended how, never a rating); everyone else is rated here, on this device, with the
   same Elo formulas as netlify/lib/ratings.mjs. Kept in a key of its own so a sync never touches it. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(null);
  else root.PLRating = factory(root.PLGames);
})(typeof self !== "undefined" ? self : this, function (G) {
  "use strict";
  var KEY = "pl-games-ratings";
  var START = 1000, MIN = 400, MAX = 3200;
  var LEVEL_RATING = [0, 900, 1250, 1600, 1950, 2300], PAR = [0, 300, 480, 720, 1080, 1500];
  var TIERS = [[0, "Novice"], [800, "Learner"], [1200, "Club player"], [1500, "Strong"], [1800, "Expert"], [2100, "Master"], [2400, "Grandmaster"]];

  function expected(p, q) { return 1 / (1 + Math.pow(10, (q - p) / 400)); }
  function kFactor(n, r) { return n < 20 ? 48 : n < 60 ? 32 : r >= 2400 ? 16 : 24; }
  function nextRating(rec, puzzleRating, score) {
    var r = rec.r, nr = Math.min(MAX, Math.max(MIN, Math.round(r + kFactor(rec.n, r) * (score - expected(r, puzzleRating)))));
    return { r: nr, delta: nr - r };
  }
  function sudokuScore(result, seconds, level) {
    if (result === "skip") return 0;
    if (result === "help") return 0.35;
    var p = PAR[level];
    return seconds <= p / 2 ? 0.95 : seconds <= p ? 0.8 : seconds <= 2 * p ? 0.6 : 0.5;
  }
  var SPORTS = ["lockerlink", "gridlink", "under-the-cap"];
  var SPORT_TIERS = [[0, "Rookie"], [900, "Role player"], [1050, "Starter"], [1200, "All-Star"], [1400, "MVP"], [1650, "Hall of Famer"], [1900, "Greatest of all time"]];
  function tierFor(r, game) { var L = game && SPORTS.indexOf(game) >= 0 ? SPORT_TIERS : TIERS, t = L[0][1]; L.forEach(function (x) { if (r >= x[0]) t = x[1]; }); return t; }

  // Daily sports games: the same formulas as netlify/lib/ratings.mjs.
  function lockerlinkPuzzleRating(par) { return 900 + 150 * par; }
  function lockerlinkScore(i) { return i.won ? Math.max(0.15, 1 - 0.15 * Math.max(0, i.links - i.par) - 0.05 * Math.min(i.misses, 10) - 0.08 * Math.min(i.hints, 5)) : 0; }
  function unbeatenScore(i) { var share = Math.min(1, Math.max(0, (i.wins / i.games - 0.45) / 0.5)); return Math.min(1, 0.85 * share + (i.champion ? 0.15 : 0)); }
  function sportsRating(game, i) {
    if (game === "lockerlink") return { puzzleRating: lockerlinkPuzzleRating(i.par), score: lockerlinkScore(i), solved: !!i.won };
    if (game === "gridlink") return { puzzleRating: 1000, score: i.filled / 9, solved: i.filled >= 5 };
    return { puzzleRating: 1100, score: unbeatenScore(i), solved: !!i.champion };
  }
  function empty() { return { r: START, n: 0, w: 0, peak: START, streak: 0, best: 0 }; }

  function load() {
    var all; try { all = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
    var moved = false; [["teamlink", "lockerlink"], ["unbeaten", "under-the-cap"]].forEach(function (m) { if (all[m[0]] && !all[m[1]]) { all[m[1]] = all[m[0]]; delete all[m[0]]; moved = true; } });   // the sports games were launched as Teamlink and Unbeaten
    if (moved) { try { localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) { /* ignore */ } }
    return all;
  }
  function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* ignore */ } }
  function get(game) { var all = load(); return Object.assign(empty(), all[game] || {}); }
  function put(game, rec) { var all = load(); all[game] = rec; save(all); }

  // The puzzle in progress, so a reload cannot be used to dodge a loss.
  function current(game, value) {
    var all = load(); all.cur = all.cur || {};
    if (value === undefined) return all.cur[game] || null;
    if (value === null) delete all.cur[game]; else all.cur[game] = value;
    save(all);
    return value;
  }
  function recentIds(game, add) {
    var all = load(); all.seen = all.seen || {}; var list = all.seen[game] || [];
    if (add) { list = list.filter(function (x) { return x !== add; }).concat([add]).slice(-300); all.seen[game] = list; save(all); }
    return list;
  }

  function session() { return G && G.session ? G.session.get() : null; }

  // Server-side numbers for a signed-in player; local ones otherwise.
  function load_(game) {
    var s = session();
    if (!s || !G.api) return Promise.resolve({ rec: get(game), signedIn: false });
    return G.api({ action: "ratings" }, s.session).then(function (res) {
      if (res.status === 401) { G.session.set(null); return { rec: get(game), signedIn: false }; }
      if (res.status !== 200) return { rec: get(game), signedIn: true, offline: true };
      var rec = res.body[game];
      if (rec) put(game, Object.assign(empty(), rec));
      return { rec: rec ? Object.assign(empty(), rec) : get(game), signedIn: true, name: res.body.name, public: !!res.body.public, fresh: !rec };
    }, function () { return { rec: get(game), signedIn: true, offline: true }; });
  }

  // One finished puzzle. info: { id, puzzleRating, result, ms, level? }. Resolves to { rec, delta, signedIn }.
  // One finished daily sports puzzle. info: { idx, sport, ms, ... the fields each game reports }.
  function reportDaily(game, info) {
    var rec = get(game), s = session(), id = "d" + info.idx, r = sportsRating(game, info);
    if ((rec.ids || []).indexOf(id) >= 0) return Promise.resolve({ rec: rec, delta: 0, signedIn: !!s, repeat: true });
    function local() {
      var out = nextRating(rec, r.puzzleRating, r.score), next = Object.assign({}, rec);
      next.r = out.r; next.n += 1; next.peak = Math.max(next.peak, out.r);
      if (r.solved) { next.w += 1; next.streak += 1; next.best = Math.max(next.best, next.streak); } else next.streak = 0;
      next.ids = (rec.ids || []).concat([id]).slice(-40);
      put(game, next);
      return { rec: next, delta: out.delta, signedIn: !!s };
    }
    if (!s || !G.api) return Promise.resolve(local());
    var body = { action: "rating_report", game: game, id: id, idx: info.idx, sport: info.sport, ms: Math.max(0, Math.min(21000000, Math.round(info.ms))) };
    ["won", "links", "misses", "hints", "filled", "wins", "champion", "roster"].forEach(function (k) { if (info[k] !== undefined) body[k] = info[k]; });
    if (rec.n > 0) body.seed = { r: rec.r, n: rec.n };
    return G.api(body, s.session).then(function (res) {
      if (res.status === 200 && typeof res.body.r === "number") {
        var next = Object.assign({}, rec, { r: res.body.r, n: res.body.n, peak: res.body.peak, streak: res.body.streak, w: rec.w + (r.solved && !res.body.repeat ? 1 : 0) });
        next.best = Math.max(next.best || 0, res.body.streak); next.ids = (rec.ids || []).concat([id]).slice(-40);
        put(game, next);
        return { rec: next, delta: res.body.delta, signedIn: true, public: !!res.body.public };
      }
      if (res.status === 401) G.session.set(null);
      return local();
    }, function () { return local(); });
  }

  function report(game, info) {
    if (SPORTS.indexOf(game) >= 0) return reportDaily(game, info);
    var rec = get(game), s = session();
    var score = game === "chess" ? (info.result === "solved" ? 1 : 0) : sudokuScore(info.result, info.ms / 1000, info.level);
    var solved = game === "chess" ? info.result === "solved" : info.result !== "skip";
    function local() {
      var out = nextRating(rec, info.puzzleRating, score), next = Object.assign({}, rec);
      next.r = out.r; next.n += 1; next.peak = Math.max(next.peak, out.r);
      if (solved) { next.w += 1; next.streak += 1; next.best = Math.max(next.best, next.streak); } else next.streak = 0;
      put(game, next);
      return { rec: next, delta: out.delta, signedIn: !!s };
    }
    if (!s || !G.api) return Promise.resolve(local());
    var body = { action: "rating_report", game: game, id: info.id, result: info.result, ms: Math.round(info.ms) };
    if (rec.n > 0) body.seed = { r: rec.r, n: rec.n };
    return G.api(body, s.session).then(function (res) {
      if (res.status === 200 && typeof res.body.r === "number") {
        var next = Object.assign({}, rec, { r: res.body.r, n: res.body.n, peak: res.body.peak, streak: res.body.streak, w: rec.w + (solved ? 1 : 0) });
        next.best = Math.max(next.best || 0, res.body.streak);
        put(game, next);
        return { rec: next, delta: res.body.delta, signedIn: true, public: !!res.body.public };
      }
      if (res.status === 401) G.session.set(null);
      return local();      // not accepted (too fast, offline, signed out): still rated here so the player is not penalised twice
    }, function () { return local(); });
  }

  function setPublic(on) {
    var s = session();
    if (!s) return Promise.resolve({ status: 401, body: {} });
    return G.api({ action: "set_public", on: !!on }, s.session);
  }

  function leaderboard(game, board, idx) {
    var s = session(), body = { action: "leaderboard", game: game, board: board };
    if (idx !== undefined) body.idx = idx;
    return G.api(body, s ? s.session : null).then(function (res) { return res.status === 200 ? res.body : null; }, function () { return null; });
  }

  return {
    START: START, LEVEL_RATING: LEVEL_RATING, PAR: PAR, expected: expected, kFactor: kFactor, nextRating: nextRating, sudokuScore: sudokuScore, tierFor: tierFor,
    get: get, load: load_, report: report, SPORTS: SPORTS, sportsRating: sportsRating, current: current, recentIds: recentIds, setPublic: setPublic, leaderboard: leaderboard
  };
});
