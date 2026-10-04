/* Shared engine for the /games/ pages. No dependencies; also loads under Node for tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PLGames = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var STORE_KEY = "pl-games-v1";

  // Whole days from the epoch (YYYY-MM-DD) to the given local date. Built from the local
  // year, month and day so a daylight saving change never shifts the puzzle number.
  function dayIndex(date, epoch) {
    var p = epoch.split("-").map(Number);
    var a = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
    var b = Date.UTC(p[0], p[1] - 1, p[2]);
    return Math.round((a - b) / 86400000);
  }

  function pick(list, idx) {
    var n = list.length;
    return list[((idx % n) + n) % n];
  }

  function decode(s) {
    var raw = typeof atob === "function" ? atob(s) : Buffer.from(s, "base64").toString("binary");
    return raw.split("").reverse().join("");
  }

  // UTF-8 base64 (quiz answers can contain accents or symbols).
  function decodeText(s) {
    var raw = typeof atob === "function" ? atob(s) : Buffer.from(s, "base64").toString("binary");
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return new TextDecoder("utf-8").decode(bytes);
  }

  // Standard two-pass scoring: exact matches first, then "present" only while the answer
  // still has an unmatched copy of that letter. Returns "c" (correct), "p" (present), "a" (absent).
  function score(guess, answer) {
    var n = answer.length, res = [], left = {}, i;
    for (i = 0; i < n; i++) res.push("a");
    for (i = 0; i < n; i++) {
      if (guess[i] === answer[i]) res[i] = "c";
      else left[answer[i]] = (left[answer[i]] || 0) + 1;
    }
    for (i = 0; i < n; i++) {
      if (res[i] === "c") continue;
      if (left[guess[i]] > 0) { res[i] = "p"; left[guess[i]]--; }
    }
    return res;
  }

  // Best state seen for each letter: correct beats present beats absent.
  var RANK = { a: 1, p: 2, c: 3 };
  function mergeKeys(keys, guess, states) {
    for (var i = 0; i < guess.length; i++) {
      var k = guess[i];
      if (!keys[k] || RANK[states[i]] > RANK[keys[k]]) keys[k] = states[i];
    }
    return keys;
  }

  // Plain geometric shapes (no emoji): filled square, square with dot, empty square.
  var SHARE = { c: "■", p: "▣", a: "□" };
  function shareRow(states) {
    return states.map(function (s) { return SHARE[s]; }).join("");
  }

  function emptyStats() { return { played: 0, won: 0, streak: 0, max: 0, last: -1, dist: {}, wins: [] }; }

  // Update the stats once per puzzle, when it ends. `idx` is the puzzle's day index.
  function recordResult(stats, idx, won, tries) {
    var s = JSON.parse(JSON.stringify(stats || emptyStats()));
    s.played += 1;
    if (won) {
      s.won += 1;
      s.streak = s.last === idx - 1 ? s.streak + 1 : 1;
      s.last = idx;
      s.dist[tries] = (s.dist[tries] || 0) + 1;
      s.wins = (s.wins || []).filter(function (x) { return x !== idx; }).concat([idx]);
      if (s.streak > s.max) s.max = s.streak;
    } else {
      s.streak = 0;
      s.last = idx;
    }
    return s;
  }

  // ---- ranks and the weekly tracker (Linkle) ----
  var RANKS = [[0, "Newcomer"], [5, "Reader"], [15, "Scribe"], [30, "Wordsmith"], [60, "Lexicographer"], [100, "Sage"]];
  function rankFor(wins) {
    var i = 0;
    for (var k = 0; k < RANKS.length; k++) if (wins >= RANKS[k][0]) i = k;
    var next = RANKS[i + 1] || null;
    return { name: RANKS[i][1], next: next ? next[1] : null, toNext: next ? next[0] - wins : 0 };
  }

  // Weeks run Monday to Sunday. `epochDow` is the weekday (Sunday = 0) of puzzle day 0.
  function weekNo(idx, epochDow) { return Math.floor((idx + ((epochDow + 6) % 7)) / 7); }

  // Which days of the current week are won, and how many full weeks were ever completed.
  function weekProgress(wins, idx, epochDow) {
    wins = wins || [];
    var w = weekNo(idx, epochDow), days = [], i, startOffset = (((epochDow + idx) % 7) + 6) % 7;
    for (i = 0; i < 7; i++) days.push(wins.indexOf(idx - startOffset + i) >= 0);
    var perWeek = {};
    wins.forEach(function (d) { var k = weekNo(d, epochDow); perWeek[k] = (perWeek[k] || 0) + 1; });
    var full = 0;
    for (var k in perWeek) if (perWeek[k] >= 7) full++;
    return { week: w, days: days, count: days.filter(Boolean).length, today: startOffset, fullWeeks: full };
  }

  // Hard mode: every hint from earlier guesses must be used. history = [{guess, score}].
  function hardModeError(guess, history) {
    var ord = ["first", "second", "third", "fourth", "fifth"];
    for (var h = 0; h < history.length; h++) {
      var g = history[h].guess, sc = history[h].score, need = {}, i;
      for (i = 0; i < g.length; i++) {
        if (sc[i] === "c" && guess[i] !== g[i]) return "The " + ord[i] + " letter must be " + g[i].toUpperCase() + ".";
        if (sc[i] !== "a") need[g[i]] = (need[g[i]] || 0) + 1;
      }
      for (var ch in need) {
        var have = 0;
        for (i = 0; i < guess.length; i++) if (guess[i] === ch) have++;
        if (have < need[ch]) return "The guess must contain " + ch.toUpperCase() + ".";
      }
    }
    return null;
  }

  // Progress lives in localStorage only. Any access can throw (private windows, blocked
  // storage), so every call is guarded and the games work without it.
  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
  }
  function save(all) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(all)); } catch (e) { /* ignore */ }
  }
  function getGame(name) { return load()[name] || {}; }
  function setGame(name, value) { var all = load(); all[name] = value; save(all); }

  function track(type, meta) {
    try { if (typeof window !== "undefined" && window.plTrack) window.plTrack(type, meta || ""); } catch (e) { /* ignore */ }
  }

  function copyText(text) {
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return false; });
    }
    return Promise.resolve(false);
  }

  return {
    dayIndex: dayIndex, pick: pick, decode: decode, decodeText: decodeText, score: score, mergeKeys: mergeKeys,
    shareRow: shareRow, emptyStats: emptyStats, recordResult: recordResult,
    rankFor: rankFor, weekNo: weekNo, weekProgress: weekProgress, hardModeError: hardModeError,
    getGame: getGame, setGame: setGame, track: track, copyText: copyText,
  };
});
