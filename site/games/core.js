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

  function emptyStats() { return { played: 0, won: 0, streak: 0, max: 0, last: -1, dist: {}, wins: [], freezes: [] }; }

  // Update the stats once per puzzle, when it ends. `idx` is the puzzle's day index.
  function recordResult(stats, idx, won, tries) {
    var s = JSON.parse(JSON.stringify(stats || emptyStats()));
    s.played += 1;
    if (won) {
      s.won += 1;
      if (s.last === idx - 1) s.streak += 1;
      else if (s.last === idx - 2 && s.streak > 0 && !(s.freezes || []).some(function (f) { return f > idx - 8; })) {
        // The streak saver: one missed day per week is forgiven, so a streak survives a busy day.
        s.freezes = (s.freezes || []).concat([idx - 1]);
        s.streak += 2;
      } else s.streak = 1;
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

  // XP and level are derived from saved progress, so they never drift and need no storage of their own.
  var XP_GAMES = ["linkle", "quadlink", "daily-five", "daily-photo", "daily-chess", "sudoku", "crossword", "landlink", "atomlink", "prizelink", "citylink", "peaklink", "codelink", "thinkerlink", "riverlink", "wildlink", "lockerlink", "gridlink", "under-the-cap", "tanklink"];
  // Daily run bonuses: finishing 2, 4 and all 8 puzzles; each quest and the day's spotlight game add 15; a week with
  // five stamped days adds 50. Stored in all.goals = { d: { day: { t: tier, q: bitmask } }, w: { week: 1 }, banked: xp of pruned days }.
  var TIER_XP = [0, 20, 40, 100], QUEST_XP = 15, WEEK_XP = 50;
  function bits(n) { var c = 0; while (n) { c += n & 1; n >>= 1; } return c; }
  function goalXp(all) {
    var g = all && all.goals; if (!g) return 0;
    var xp = g.banked || 0, k;
    for (k in (g.d || {})) xp += TIER_XP[Math.min(3, g.d[k].t || 0)] + QUEST_XP * bits(g.d[k].q || 0);
    for (k in (g.w || {})) xp += WEEK_XP;
    return xp;
  }
  var TITLES = ["Newcomer", "Regular", "Solver", "Puzzler", "Tactician", "Wordsmith", "Strategist", "Adept", "Virtuoso", "Sage"];
  function titleFor(level) { return TITLES[Math.min(TITLES.length - 1, Math.max(0, level - 1))]; }
  function xpOf(all) {
    var xp = 0;
    XP_GAMES.forEach(function (g) {
      var s = (all[g] && all[g].stats) || {};
      xp += 10 * (s.played || 0) + 5 * (s.won || 0) + 3 * (s.max || 0);
    });
    xp += 25 * Object.keys(all.ach || {}).length;
    xp += goalXp(all);
    var level = 1;
    while (30 * (level + 1) * level <= xp) level++;
    var floor = 30 * level * (level - 1), ceil = 30 * (level + 1) * level;
    return { xp: xp, level: level, into: xp - floor, need: ceil - floor, title: titleFor(level) };
  }

  function saverNote(stats, idx) {
    return stats && (stats.freezes || []).indexOf(idx - 1) >= 0 ? "Your streak saver covered yesterday, so your streak is still alive. You get one a week." : "";
  }

  // After a game ends, a signed-out player is offered a way to keep their score and streak. The line is
  // the streak-saver message when there is one. Signing in uses the same email link as the account page;
  // a session lasts 90 days, renews while it is used, and each device signs in on its own, so signing in
  // on a phone never signs anyone out of a laptop. "Not now" silences the offer for a week.
  var OFFER_KEY = "pl-games-offer-v1", OFFER_QUIET_MS = 7 * 86400000;
  function offerText(stats) {
    var t = "Save your score and streak? Sign in with an email link and your progress follows you to other devices. You stay signed in on this one.";
    if (stats && stats.played === 1) t += " Right now your streak is kept in this browser only, so anything played in another browser or app is not included.";
    return t;
  }
  // Once this browser has been signed in, or the player has asked for a link, we know their email: leave them alone from then on.
  var KNOWN_KEY = "pl-games-known";
  function markKnown(on) {
    try { if (on === false) localStorage.removeItem(KNOWN_KEY); else localStorage.setItem(KNOWN_KEY, "1"); } catch (e) { /* ignore */ }
  }
  function offerQuiet() {
    try {
      if (localStorage.getItem(KNOWN_KEY)) return true;
      var t = Number(localStorage.getItem(OFFER_KEY)); return !!t && Date.now() - t < OFFER_QUIET_MS;
    } catch (e) { return false; }
  }
  function offerSignedIn() {
    try { return !!(window.PLGames && window.PLGames.session && window.PLGames.session.get()); } catch (e) { return false; }
  }
  function buildOffer(stats) {
    var box = document.createElement("div"), p = document.createElement("p"), form = document.createElement("form"),
      label = document.createElement("label"), input = document.createElement("input"), send = document.createElement("button"),
      later = document.createElement("button"), status = document.createElement("p");
    box.className = "game-offer"; box.setAttribute("role", "group"); box.setAttribute("aria-label", "Save your progress");
    p.className = "game-offer-text"; p.textContent = offerText(stats);
    form.className = "ac-form game-offer-form";
    input.id = "game-offer-email"; input.type = "email"; input.name = "email"; input.required = true; input.maxLength = 254; input.autocomplete = "email";
    label.htmlFor = input.id; label.textContent = "Email address";
    send.type = "submit"; send.className = "btn btn-primary"; send.textContent = "Email me a link";
    later.type = "button"; later.className = "btn btn-ghost"; later.textContent = "Not now";
    status.className = "game-offer-status"; status.setAttribute("role", "status");
    form.appendChild(label); form.appendChild(input); form.appendChild(send); form.appendChild(later);
    box.appendChild(p); box.appendChild(form); box.appendChild(status);
    later.addEventListener("click", function () {
      try { localStorage.setItem(OFFER_KEY, String(Date.now())); } catch (e) { /* ignore */ }
      box.remove();
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var api = window.PLGames && window.PLGames.api;
      if (!api) { status.textContent = "Sign-in is not available right now. Try the Account page."; return; }
      send.disabled = true; status.textContent = "Sending.";
      api({ action: "login_request", email: input.value.trim() }).then(function (res) {
        if (res.status === 200) { markKnown(true); status.textContent = "Check your email and open the link on this device. You will stay signed in here, and you can sign in on any other device the same way."; form.hidden = true; }
        else if (res.status === 429) status.textContent = "Too many requests for that address today. Try again tomorrow.";
        else if (res.status === 400) status.textContent = "That does not look like an email address.";
        else status.textContent = "The email could not be sent. Try again in a moment.";
      }).catch(function () { status.textContent = "Could not reach the server. Try again in a moment."; })
        .then(function () { send.disabled = false; });
    });
    return box;
  }
  function ordinalLine(label, r) { return label + " #" + r.rank + " of " + r.total + (r.total > 1 ? " (ahead of " + r.pct + "%)" : ""); }
  // "All-time: wins #4 of 52 (ahead of 94%), best streak #2 of 52". Needs the account's latest results on the server,
  // so it syncs first. Quietly absent when the player is signed out, offline or the server has nothing yet.
  function paintRank(box, game) {
    var gg = window.PLGames;
    if (!gg || !gg.sync || !gg.rankFor) return;
    gg.sync().then(function () { return gg.rankFor(game); }).then(function (r) {
      if (!r || !box.parentNode) return;
      var bits = [];
      if (r.w) bits.push(ordinalLine("wins", r.w));
      if (r.s && r.s.v > 1) bits.push(ordinalLine("best streak", r.s));
      if (r.p) bits.push(ordinalLine("average percentile", r.p));
      if (bits.length) box.textContent = "All-time: " + bits.join(", ") + ". ";
      var a = document.createElement("a");
      a.href = "/games/leaderboard/?g=daily:" + game + "&b=day";
      a.textContent = "See who did best today";
      box.appendChild(a);
    }).catch(function () { /* the rank line is optional */ });
  }
  function paintNote(el, stats, idx, on, game) {
    if (!el || typeof document === "undefined") return;
    el.textContent = "";
    var sib = el.nextElementSibling;
    while (sib && (sib.classList.contains("game-offer") || sib.classList.contains("game-rank"))) { var nx = sib.nextElementSibling; sib.remove(); sib = nx; }
    if (on === false) return;
    el.textContent = saverNote(stats, idx);
    if (!el.parentNode) return;
    if (offerSignedIn()) {
      if (game) { var line = document.createElement("p"); line.className = "game-rank"; line.setAttribute("role", "status"); el.parentNode.insertBefore(line, el.nextSibling); paintRank(line, game); }
      return;
    }
    if (offerQuiet()) return;
    el.parentNode.insertBefore(buildOffer(stats), el.nextSibling);
  }

  // Progress lives in localStorage only. Any access can throw (private windows, blocked
  // storage), so every call is guarded and the games work without it.
  function load() {
    var all;
    try { all = JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
    // Lockerlink was launched as Teamlink; carry the saved progress over to the new name
    var moved = false; [["teamlink", "lockerlink"], ["unbeaten", "under-the-cap"]].forEach(function (m) { if (all[m[0]] && !all[m[1]]) { all[m[1]] = all[m[0]]; delete all[m[0]]; moved = true; } });
    if (moved) { try { localStorage.setItem(STORE_KEY, JSON.stringify(all)); } catch (e) { /* ignore */ } }
    return all;
  }
  function save(all) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(all)); } catch (e) { /* ignore */ }
  }
  function getGame(name) { return load()[name] || {}; }
  function replaceAll(all) { save(all && typeof all === "object" ? all : {}); }
  function setGame(name, value) { var all = load(); all[name] = value; save(all); }

  function track(type, meta) {
    try { if (typeof window !== "undefined" && window.plTrack) window.plTrack(type, meta || ""); } catch (e) { /* ignore */ }
  }

  // ---- per-day history ----
  // Mirror of the helpers in netlify/lib/games-logic.mjs (a test keeps them in step): { s: first day, c: "..." } with
  // two base-36 characters per day, the score (lower is better, 99 = lost) or "zz" for a day not played. 730 days kept.
  var HIST_DAYS = 730, HIST_NONE = "zz";
  function histEnc(n) { var t = Math.min(1295, Math.max(0, Math.trunc(n))).toString(36); return t.length < 2 ? "0" + t : t; }
  function histSet(h, idx, score) {
    if (typeof idx !== "number" || idx < 0 || idx !== Math.trunc(idx) || typeof score !== "number" || !isFinite(score)) return h || null;
    var cell = histEnc(score), i;
    if (!h) return { s: idx, c: cell };
    var st = h.s, c = h.c, pad = "";
    if (idx < st) { for (i = 0; i < st - idx; i++) pad += HIST_NONE; c = pad + c; st = idx; }
    var at = (idx - st) * 2;
    if (at >= c.length) { for (i = 0; i < (at - c.length) / 2; i++) pad += HIST_NONE; c = c + pad + cell; }
    else if (c.slice(at, at + 2) === HIST_NONE) c = c.slice(0, at) + cell + c.slice(at + 2);
    if (c.length > 2 * HIST_DAYS) { var drop = (c.length - 2 * HIST_DAYS) / 2; c = c.slice(drop * 2); st += drop; }
    return { s: st, c: c };
  }
  function histGet(h, idx) {
    if (!h) return null;
    var at = (idx - h.s) * 2;
    if (at < 0 || at + 2 > h.c.length) return null;
    var t = h.c.slice(at, at + 2);
    return t === HIST_NONE ? null : parseInt(t, 36);
  }
  // Called for every finished puzzle, before the percentile request, so the history is kept even offline.
  function noteScore(game, idx, score) {
    var g = getGame(game), h = histSet(g.hist, idx, score);
    if (h && (!g.hist || h.c !== g.hist.c || h.s !== g.hist.s)) { g.hist = h; setGame(game, g); }
  }

  // A random id for this browser, used only so people who share a connection each count once in a day's percentile.
  var VID_KEY = "pl-games-vid";
  function vid() {
    try {
      var v = localStorage.getItem(VID_KEY);
      if (v && /^[a-f0-9]{32}$/.test(v)) return v;
      var out = "", i;
      if (typeof crypto !== "undefined" && crypto.getRandomValues) { var a = new Uint8Array(16); crypto.getRandomValues(a); for (i = 0; i < 16; i++) out += (a[i] < 16 ? "0" : "") + a[i].toString(16); }
      else for (i = 0; i < 32; i++) out += Math.floor(Math.random() * 16).toString(16);
      localStorage.setItem(VID_KEY, out);
      return out;
    } catch (e) { return ""; }
  }

  // Anonymous score for the day's percentile. Lower is better (guesses, misses, 20-second blocks); 99 = lost.
  // Sent once per puzzle; nothing identifying goes with it.
  function submitScore(game, idx, score) {
    noteScore(game, idx, score);
    var g = getGame(game);
    if (g.scored && g.scored[idx]) return Promise.resolve(null);
    if (typeof fetch !== "function") return Promise.resolve(null);
    var headers = { "Content-Type": "application/json" }, sess = null;
    try { sess = window.PLGames && window.PLGames.session && window.PLGames.session.get(); } catch (e) { /* ignore */ }
    if (sess && sess.session) headers.Authorization = "Bearer " + sess.session;
    return fetch("/.netlify/functions/games-api", {
      method: "POST", headers: headers,
      body: JSON.stringify({ action: "score", game: game, idx: idx, score: score, vid: vid() }),
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
      if (!res || typeof res.percentile !== "number") return null;
      var g2 = getGame(game);
      g2.scored = g2.scored || {};
      g2.scored[idx] = true;
      g2.last = { idx: idx, percentile: res.percentile, total: res.total };
      var keys = Object.keys(g2.scored);
      if (keys.length > 60) delete g2.scored[keys[0]];
      // a lone early player's 50% says nothing, so the running average only counts days with a real crowd
      if (res.total >= 10) {
        var p = g2.pct || { sum: 0, count: 0, best: 0, last: 0 };
        g2.pct = { sum: p.sum + res.percentile, count: p.count + 1, best: Math.max(p.best, res.percentile), last: res.percentile };
      }
      setGame(game, g2);
      return res;
    }).catch(function () { return null; });
  }

  // One line for the result screen, or "" when there is nothing useful to say yet.
  function describePercentile(res) {
    if (!res) return "";
    if (res.total < 10) return res.total <= 1 ? "You are the first player today." : "You are one of " + res.total + " players so far today.";
    return "You did better than " + res.percentile + "% of the " + res.total + " players who have finished today's puzzle.";
  }

  // The percentile saved when this puzzle was finished, so it still shows after a reload.
  function savedPercentile(game, idx) {
    var l = getGame(game).last;
    return l && l.idx === idx ? { percentile: l.percentile, total: l.total } : null;
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
    rankFor: rankFor, xpOf: xpOf, goalXp: goalXp, titleFor: titleFor, TIER_XP: TIER_XP, QUEST_XP: QUEST_XP, WEEK_XP: WEEK_XP, saverNote: saverNote, paintNote: paintNote, offerText: offerText, histSet: histSet, histGet: histGet, noteScore: noteScore, vid: vid, markKnown: markKnown, offerQuiet: offerQuiet, weekNo: weekNo, weekProgress: weekProgress, hardModeError: hardModeError,
    getGame: getGame, setGame: setGame, all: load, replaceAll: replaceAll, ready: Promise.resolve(),
    submitScore: submitScore, describePercentile: describePercentile, savedPercentile: savedPercentile, track: track, copyText: copyText,
  };
});
