/* Shared engine for the sports games (Teamlink, Gridlink, Unbeaten). One data file per sport lists famous players and
   the franchises they played for, season by season. A "stint" is [franchise, firstSeason, endSeason) so a player was on
   a team in every season s with first <= s < end. Two players are teammates when they have a franchise and a season in
   common. Also loads under Node for tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(null);
  else root.PLSports = factory(root.PLGames);
})(typeof self !== "undefined" ? self : this, function (G) {
  "use strict";

  var EPOCH = "2026-10-04";
  var cache = {};

  function fold(s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim(); }

  // Build the lookup tables for a data file once.
  function prepare(raw) {
    var d = { sport: raw.sport, name: raw.name, fr: raw.fr, fs: raw.fs || {}, cfg: raw.cfg, tl: raw.tl || [], gr: raw.gr || [], players: [], byName: {} };
    raw.p.forEach(function (r, i) {
      var p = { i: i, n: r[0], pos: r[1], tier: r[2], ovr: r[3], st: r[4], hon: r[5] || [0, 0, 0, 0], key: fold(r[0]) };
      p.g = (d.cfg.groupOf || {})[p.pos] || p.pos;
      p.first = Math.min.apply(null, p.st.map(function (s) { return s[1]; }));
      p.last = Math.max.apply(null, p.st.map(function (s) { return s[2]; })) - 1;
      p.teams = unique(p.st.map(function (s) { return s[0]; }));
      p.seasons = p.st.reduce(function (a, s) { return a + (s[2] - s[1]); }, 0);
      p.span = span(d, p.first, p.last);
      d.players.push(p); d.byName[p.n] = p;
    });
    return d;
  }
  function unique(a) { var o = [], seen = {}; a.forEach(function (x) { if (!seen[x]) { seen[x] = 1; o.push(x); } }); return o; }

  function load(sport) {
    if (cache[sport]) return cache[sport];
    cache[sport] = fetch("/games/data/sports-" + sport + ".json").then(function (r) { if (!r.ok) throw new Error("load"); return r.json(); }).then(function (raw) {
      raw.cfg.groupOf = raw.cfg.groupOf || groupMap(sport);
      return prepare(raw);
    });
    return cache[sport];
  }
  function index() {
    if (cache._index) return cache._index;
    cache._index = fetch("/games/data/sports-index.json").then(function (r) { return r.json(); }).catch(function () { return { rotation: ["nba"] }; });
    return cache._index;
  }

  // Position codes that count as one slot type, per sport (kept in step with scripts/gen_sports.py).
  var GROUPS = {
    nba: { PG: "G", SG: "G", SF: "F", PF: "F", C: "C" },
    nfl: { QB: "QB", RB: "RB", WR: "WR", TE: "TE", OL: "OL", DL: "DL", LB: "LB", DB: "DB" },
    mlb: { C: "C", "1B": "1B", "2B": "2B", "3B": "3B", SS: "SS", LF: "OF", CF: "OF", RF: "OF", SP: "SP", RP: "RP" },
    nhl: { C: "C", LW: "W", RW: "W", D: "D", G: "G" }
  };
  function groupMap(sport) { return GROUPS[sport] || {}; }

  // ---------- teammates ----------
  function shared(a, b) {
    var best = null;
    a.st.forEach(function (x) {
      b.st.forEach(function (y) {
        if (x[0] !== y[0]) return;
        var from = Math.max(x[1], y[1]), to = Math.min(x[2], y[2]);
        if (from < to && (!best || to - from > best.to - best.from)) best = { f: x[0], from: from, to: to - 1 };
      });
    });
    return best;
  }
  // Players are grouped by franchise and season; anyone in the same group is a teammate. This keeps the search fast even
  // with tens of thousands of players, because a player only looks at the groups he belonged to.
  function buckets(d) {
    if (d.bk) return d.bk;
    var bk = {};
    d.players.forEach(function (p) { addToBuckets(bk, p); });
    d.bk = bk;
    return bk;
  }
  function addToBuckets(bk, p) {
    p.st.forEach(function (x) { for (var y = x[1]; y < x[2]; y++) { var k = x[0] + "|" + y; (bk[k] = bk[k] || []).push(p); } });
  }
  function neighbors(d, p) {
    var bk = buckets(d), seen = {}, out = [];
    p.st.forEach(function (x) {
      for (var y = x[1]; y < x[2]; y++) (bk[x[0] + "|" + y] || []).forEach(function (q) { if (q !== p && !seen[q.i]) { seen[q.i] = 1; out.push(q); } });
    });
    return out;
  }
  function areTeammates(d, a, b) { return a !== b && shared(a, b) !== null; }

  // Shortest chain from a to b (inclusive), or null.
  function path(d, a, b) {
    var prev = {}, q = [a], k = 0;
    prev[a.i] = null;
    while (k < q.length) {
      var u = q[k++];
      if (u === b) break;
      neighbors(d, u).forEach(function (v) { if (!(v.i in prev)) { prev[v.i] = u; q.push(v); } });
    }
    if (!(b.i in prev)) return null;
    var out = [], u2 = b;
    while (u2) { out.push(u2); u2 = prev[u2.i]; }
    return out.reverse();
  }
  function distances(d, a) {
    var dist = {}, q = [a], k = 0;
    dist[a.i] = 0;
    while (k < q.length) { var u = q[k++]; neighbors(d, u).forEach(function (v) { if (!(v.i in dist)) { dist[v.i] = dist[u.i] + 1; q.push(v); } }); }
    return dist;
  }

  // Add the wider database (everyone who ever played, not just the famous pool). Rows: [name, position, born, stints].
  function extend(d, rows) {
    if (d.extended) return d;
    var bk = d.bk;
    rows.forEach(function (r) {
      var p = { i: d.players.length, n: r[0], pos: r[1] || "", tier: 0, ovr: 0, st: r[3], born: r[2] || 0, extra: true, key: fold(r[0]) };
      p.g = (d.cfg.groupOf || {})[p.pos] || p.pos;
      p.first = Math.min.apply(null, p.st.map(function (s) { return s[1]; }));
      p.last = Math.max.apply(null, p.st.map(function (s) { return s[2]; })) - 1;
      p.teams = unique(p.st.map(function (s) { return s[0]; }));
      p.seasons = p.st.reduce(function (a, s) { return a + (s[2] - s[1]); }, 0);
      p.span = span(d, p.first, p.last);
      d.players.push(p); d.byName[p.n] = p;
      if (bk) addToBuckets(bk, p);
    });
    d.extended = true;
    return d;
  }
  function loadAll(sport) {
    var key = sport + ":all";
    if (cache[key]) return cache[key];
    cache[key] = load(sport).then(function (d) {
      return fetch("/games/data/sports-" + sport + "-all.json").then(function (r) { if (!r.ok) throw new Error("none"); return r.json(); }).then(function (raw) { return extend(d, raw.p); }, function () { return d; });
    });
    return cache[key];
  }

  // ---------- grid criteria ----------
  function decadeOf(code) { return Number(code.split(":")[1]); }
  function crit(d, code) {
    var k = code.split(":")[0], v = code.split(":")[1];
    if (k === "t") return { code: code, label: d.fr[v] || v, short: fname(d, v), test: function (p) { return p.teams.indexOf(v) >= 0; } };
    if (k === "p") return { code: code, label: (d.cfg.gname || {})[v] || v, short: (d.cfg.gname || {})[v] || v, test: function (p) { return p.g === v; } };
    if (k === "d") { var y = Number(v); return { code: code, label: "Played in the " + y + "s", short: y + "s", test: function (p) { return p.st.some(function (s) { return s[1] < y + 10 && s[2] > y; }); } }; }
    if (k === "n") return { code: code, label: "Played for " + v + "+ teams", short: v + "+ teams", test: function (p) { return p.teams.length >= Number(v); } };
    if (k === "y") return { code: code, label: "Played " + v + "+ seasons", short: v + "+ seasons", test: function (p) { return p.seasons >= Number(v); } };
    if (k === "a") {
      var sel = d.cfg.selname || "All-Star";
      var A = { mvp: ["MVP winner", "MVP", function (p) { return p.hon[1] >= 1; }], title: ["Won a championship", "Champion", function (p) { return p.hon[2] >= 1; }],
                sel5: ["5+ " + sel + " selections", "5+ " + sel, function (p) { return p.hon[0] >= 5; }], hof: ["Hall of Famer", "Hall of Fame", function (p) { return p.hon[3] >= 1; }] }[v];
      return { code: code, label: A[0], short: A[1], test: A[2] };
    }
    if (k === "m") {
      var star = d.byName[v], last = v.split(" ").slice(-1)[0];
      return { code: code, label: "Played with " + v, short: "With " + last, test: function (p) { return p !== star && !!star && shared(p, star) !== null; } };
    }
    if (k === "o") return { code: code, label: "One-team career", short: "One team", test: function (p) { return p.teams.length === 1; } };
    return { code: code, label: code, short: code, test: function () { return false; } };
  }
  var TWO_WORD = ["Trail Blazers", "Red Sox", "White Sox", "Blue Jays", "Maple Leafs", "Golden Knights", "Blue Jackets", "Red Wings", "Golden State"];
  function shortName(name) {
    for (var i = 0; i < TWO_WORD.length; i++) if (name.slice(-TWO_WORD[i].length) === TWO_WORD[i]) return TWO_WORD[i];
    if (/^(Utah Hockey Club|Washington Football Team)$/.test(name)) return name.split(" ").slice(-1)[0];
    var w = name.split(" ");
    return w.length > 1 ? w[w.length - 1] : name;
  }
  // "12x All-Star, 4x MVP, 3x champion, Hall of Fame" for the picker; empty for players with nothing on record.
  function honorsText(d, p) {
    var h = p.hon || [0, 0, 0, 0], out = [];
    if (h[0]) out.push(h[0] + "x " + (d.cfg.selname || "All-Star"));
    if (h[1]) out.push(h[1] + "x MVP");
    if (h[2]) out.push(h[2] + "x champion");
    if (h[3]) out.push("Hall of Fame");
    return out.join(", ");
  }
  function fname(d, f) { return d.fs[f] || shortName(d.fr[f] || f); }
  function cellAnswers(d, r, c) {
    return d.players.filter(function (p) { return r.test(p) && c.test(p); });
  }

  // ---------- random numbers and days ----------
  function hash(str) { var h = 2166136261; for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) {
    var a = typeof seed === "number" ? seed >>> 0 : hash(String(seed));
    return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; var t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function dayIdx() { return G ? G.dayIndex(new Date(), EPOCH) : 0; }
  function dailySport(rotation, idx) { return rotation[((idx % rotation.length) + rotation.length) % rotation.length]; }
  function dailySlot(rotation, idx) { return Math.floor(idx / rotation.length); }

  // ---------- text ----------
  // Seasons are stored as the year a season began. Split-year leagues (NBA, NHL) read 1978-79; single-year leagues read 2005.
  function two(n) { return ("0" + (n % 100)).slice(-2); }
  function span(d, f, t) {
    if (d.cfg.split) return f === t ? f + "-" + two(f + 1) : f + "-" + two(t + 1);
    return f === t ? String(f) : f + "-" + two(t);
  }
  function stintText(d, p) {
    return p.st.map(function (s) { return fname(d, s[0]) + " " + span(d, s[1], s[2] - 1); }).join(", ");
  }
  function teamsLine(d, p) {
    return p.teams.map(function (f) { return fname(d, f); }).join(", ");
  }
  function career(p) { return p.span; }

  // ---------- local state (kept apart from the synced progress) ----------
  function loadState(key) { try { return JSON.parse(localStorage.getItem("pl-sports-" + key)) || null; } catch (e) { return null; } }
  function saveState(key, v) { try { if (v === null) localStorage.removeItem("pl-sports-" + key); else localStorage.setItem("pl-sports-" + key, JSON.stringify(v)); } catch (e) { /* ignore */ } }

  // ---------- name picker (combobox) ----------
  // opts: { input, list, items: function() -> players, exclude: function(p) -> bool, onPick: function(p), label: function(p) -> html-safe string }
  function combo(opts) {
    var input = opts.input, list = opts.list, matches = [], active = 0;
    function find(q) {
      var toks = fold(q).split(" ").filter(Boolean);
      if (!toks.length) return [];
      var out = [];
      opts.items().forEach(function (p) {
        if (opts.exclude && opts.exclude(p)) return;
        var words = p.key.split(" "), score = 0, ok = toks.every(function (t) { return words.some(function (w) { return w.indexOf(t) === 0; }) || p.key.indexOf(" " + t) >= 0 || p.key.indexOf(t) === 0; });
        if (!ok) return;
        if (p.key.indexOf(toks.join(" ")) === 0) score = 2; else if (words[words.length - 1].indexOf(toks[toks.length - 1]) === 0) score = 1;
        out.push({ p: p, s: score });
      });
      out.sort(function (a, b) { return b.s - a.s || b.p.tier - a.p.tier || (a.p.n < b.p.n ? -1 : 1); });
      return out.slice(0, 8).map(function (x) { return x.p; });
    }
    function paint() {
      list.innerHTML = "";
      matches.forEach(function (p, i) {
        var li = document.createElement("li");
        li.setAttribute("role", "option"); li.id = list.id + "-" + i; li.setAttribute("aria-selected", i === active ? "true" : "false");
        var name = document.createElement("span"); name.className = "sp-opt-name"; name.textContent = p.n;
        var meta = document.createElement("span"); meta.className = "sp-opt-meta"; meta.textContent = (p.pos ? p.pos + ", " : "") + career(p) + (p.born ? ", b. " + p.born : "");
        li.appendChild(name); li.appendChild(meta);
        li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(p); });
        list.appendChild(li);
      });
      list.hidden = !matches.length;
      input.setAttribute("aria-expanded", matches.length ? "true" : "false");
      if (matches.length) input.setAttribute("aria-activedescendant", list.id + "-" + active); else input.removeAttribute("aria-activedescendant");
    }
    function choose(p) { input.value = ""; matches = []; paint(); opts.onPick(p); }
    function onInput() { matches = find(input.value); active = 0; paint(); }
    input.addEventListener("input", onInput);
    input.addEventListener("focus", onInput);
    input.addEventListener("blur", function () { window.setTimeout(function () { list.hidden = true; input.setAttribute("aria-expanded", "false"); }, 120); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (matches.length) { active = (active + 1) % matches.length; paint(); } }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (matches.length) { active = (active + matches.length - 1) % matches.length; paint(); } }
      else if (e.key === "Escape") { list.hidden = true; }
      else if (e.key === "Enter") { e.preventDefault(); if (matches.length) choose(matches[active]); else if (opts.onNone) opts.onNone(input.value); }
    });
    return { top: function () { if (matches.length) choose(matches[active]); else if (opts.onNone) opts.onNone(input.value); }, choose: choose, clear: function () { input.value = ""; matches = []; paint(); } };
  }

  return {
    EPOCH: EPOCH, fold: fold, prepare: prepare, load: load, index: index, GROUPS: GROUPS,
    shared: shared, neighbors: neighbors, extend: extend, loadAll: loadAll, areTeammates: areTeammates, path: path, distances: distances,
    crit: crit, cellAnswers: cellAnswers, shortName: shortName, fname: fname, honorsText: honorsText, hash: hash, rng: rng,
    dayIdx: dayIdx, dailySport: dailySport, dailySlot: dailySlot,
    span: span, stintText: stintText, teamsLine: teamsLine, career: career,
    loadState: loadState, saveState: saveState, combo: combo
  };
});
