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

  function emptyStats() { return { played: 0, won: 0, streak: 0, max: 0, last: -1, dist: {} }; }

  // Update the stats once per puzzle, when it ends. `idx` is the puzzle's day index.
  function recordResult(stats, idx, won, tries) {
    var s = JSON.parse(JSON.stringify(stats || emptyStats()));
    s.played += 1;
    if (won) {
      s.won += 1;
      s.streak = s.last === idx - 1 ? s.streak + 1 : 1;
      s.last = idx;
      s.dist[tries] = (s.dist[tries] || 0) + 1;
      if (s.streak > s.max) s.max = s.streak;
    } else {
      s.streak = 0;
      s.last = idx;
    }
    return s;
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
    dayIndex: dayIndex, pick: pick, decode: decode, score: score, mergeKeys: mergeKeys,
    shareRow: shareRow, emptyStats: emptyStats, recordResult: recordResult,
    getGame: getGame, setGame: setGame, track: track, copyText: copyText,
  };
});
