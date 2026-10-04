/* The season model behind Unbeaten. Pure functions, no page access, so it can be tested under Node.
   A roster is { starters: [player per slot], bench: [players] }. Strength is the starters' ratings, a smaller share from
   the bench, and a bonus for players who really did play together. Ratings are our own estimates of each player at his
   best; they are not official statistics and eras are not adjusted. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(typeof PLSports !== "undefined" ? PLSports : require("./sports.js"));
  else root.PLSeason = factory(root.PLSports);
})(typeof self !== "undefined" ? self : this, function (S) {
  "use strict";

  var COST = { 1: 1, 2: 2, 3: 3, 4: 5, 5: 7 };
  function cost(p) { return COST[p.tier]; }

  // Rules for each weekday of the daily challenge. cfg.era is the debut year that splits the old and new eras.
  function constraint(d, dow) {
    var era = d.cfg.era || 1990;
    return [
      { name: "Dream team", text: "Four extra points of budget.", cap: 4, ok: function () { return true; } },
      { name: "Open draft", text: "Any player from any era.", cap: 0, ok: function () { return true; } },
      { name: "Throwback", text: "Only players whose careers began before " + era + ".", cap: 0, ok: function (p) { return p.first < era; } },
      { name: "Modern", text: "Only players whose careers began in " + (era + 10) + " or later.", cap: 0, ok: function (p) { return p.first >= era + 10; } },
      { name: "Underdogs", text: "No all-time icons. Top-tier players are locked.", cap: 0, ok: function (p) { return p.tier < 5; } },
      { name: "Cap squeeze", text: "Four points less budget.", cap: -4, ok: function () { return true; } },
      { name: "Stars only", text: "Only well-known stars, no role players.", cap: 0, ok: function (p) { return p.tier >= 3; } }
    ][((dow % 7) + 7) % 7];
  }

  function everyone(roster) { return roster.starters.concat(roster.bench).filter(Boolean); }

  function chemistry(d, roster) {
    var all = everyone(roster), pairs = 0, i, j;
    for (i = 0; i < all.length; i++) for (j = i + 1; j < all.length; j++) if (S.areTeammates(d, all[i], all[j])) pairs++;
    return { pairs: pairs, bonus: Math.min(4, pairs * 0.4) };
  }

  function mean(a) { return a.length ? a.reduce(function (x, p) { return x + p.ovr; }, 0) / a.length : 0; }
  function strength(d, roster) {
    var st = roster.starters.filter(Boolean), bn = roster.bench.filter(Boolean);
    var w = d.cfg.slots.length > 8 ? 0.82 : 0.72;
    var base = bn.length ? w * mean(st) + (1 - w) * mean(bn) : mean(st);
    var chem = chemistry(d, roster);
    return { rating: base + chem.bonus, base: base, chem: chem };
  }

  function winProb(rating, opp, scale) { return 1 / (1 + Math.exp(-(rating - opp) / scale)); }

  // The rest of the league: other teams, strongest first, the same for everyone on a given seed.
  function league(d, seed) {
    var r = S.rng("league-" + seed), n = d.cfg.teams - 1, out = [], i;
    for (i = 0; i < n; i++) {
      var z = 0; for (var k = 0; k < 6; k++) z += r(); z = (z - 3) / 0.7071;       // roughly normal
      out.push(d.cfg.base - 4 + 4.5 * z);
    }
    return out.sort(function (a, b) { return b - a; });
  }

  function seriesWin(r, p, games) {
    var need = Math.ceil((games + 0.5) / 2), a = 0, b = 0;
    while (a < need && b < need) { if (r() < p) a++; else b++; }
    return { won: a === need, a: a, b: b };
  }

  // Run one season. Returns the record, streaks, the chance of going unbeaten, and the playoffs.
  function simulate(d, roster, seed) {
    var cfg = d.cfg, r = S.rng("season-" + seed), str = strength(d, roster), L = league(d, seed);
    var order = L.slice(); for (var i = order.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)); var t = order[i]; order[i] = order[j]; order[j] = t; }
    var wins = 0, losses = 0, run = 0, best = 0, pAll = 1, sumP = 0, g, losing = [];
    for (g = 0; g < cfg.games; g++) {
      var opp = order[g % order.length], p = winProb(str.rating, opp, cfg.scale);
      pAll *= p; sumP += p;
      if (r() < p) { wins++; run++; if (run > best) best = run; } else { losses++; run = 0; losing.push(g + 1); }
    }
    var res = { rating: str.rating, base: str.base, chem: str.chem, wins: wins, losses: losses, streak: best, perfect: pAll, avgP: sumP / cfg.games, playoffs: [], champion: false, made: wins / cfg.games >= 0.5, firstLoss: losing[0] || 0 };
    if (!res.made) return res;
    var rounds = cfg.rounds, field = L.slice(0, Math.min(L.length, 8)), pi = 0;
    for (var k = 0; k < rounds.length; k++) {
      var oppR = field[Math.min(field.length - 1, field.length - 1 - Math.floor((k / rounds.length) * (field.length - 1)))];
      var pg = winProb(str.rating, oppR, cfg.scale), s = seriesWin(r, pg, rounds[k]);
      res.playoffs.push({ round: k + 1, games: rounds[k], won: s.won, a: s.a, b: s.b });
      if (!s.won) return res;
    }
    res.champion = true;
    return res;
  }

  // How good a roster the budget allows: used by tests and to keep the cap honest.
  function bestUnderCap(d, cap, ok) {
    var slots = d.cfg.slots, used = {}, total = 0, st = [], P = d.players.filter(ok || function () { return true; });
    slots.forEach(function (sl) {
      var c = P.filter(function (p) { return p.g === sl && !used[p.n]; }).sort(function (a, b) { return b.ovr - a.ovr; })[0];
      if (c) { used[c.n] = 1; st.push(c); total += cost(c); }
    });
    return { starters: st, cost: total };
  }

  return { COST: COST, cost: cost, constraint: constraint, chemistry: chemistry, strength: strength, winProb: winProb, league: league, simulate: simulate, everyone: everyone, bestUnderCap: bestUnderCap };
});
