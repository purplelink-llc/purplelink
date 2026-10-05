/* /games/account/: stats, achievements and the optional email-link sign-in. */
(function () {
  "use strict";
  var G = window.PLGames, A = window.PLAch;
  if (!G || !A) return;
  var $ = function (id) { return document.getElementById(id); };
  var GAMES = [["linkle", "Linkle"], ["quadlink", "Quadlink"], ["daily-five", "Daily Five"], ["daily-photo", "Daily Photo"], ["daily-chess", "Daily Chess"], ["sudoku", "Sudoku"], ["landlink", "Landlink"], ["atomlink", "Atomlink"], ["prizelink", "Prizelink"], ["citylink", "Citylink"], ["peaklink", "Peaklink"], ["codelink", "Codelink"], ["thinkerlink", "Thinkerlink"], ["riverlink", "Riverlink"], ["wildlink", "Wildlink"], ["lockerlink", "Lockerlink"], ["gridlink", "Gridlink"], ["under-the-cap", "Under the Cap"], ["crossword", "Crossword"]];

  function msg(t) { $("ac-msg").textContent = t || ""; }
  function fmt(sec) { var m = Math.floor(sec / 60), s = sec % 60; return m + ":" + (s < 10 ? "0" : "") + s; }

  function renderStats() {
    var all = G.all(), box = $("ac-stats");
    box.textContent = "";
    var head = document.createElement("div");
    head.className = "ac-row ac-head";
    var signed = !!G.session.get();
    if (signed) box.setAttribute("data-ranked", ""); else box.removeAttribute("data-ranked");
    ["Game", "Finished", "Streak", "Best streak", "Avg. percentile"].concat(signed ? ["All-time rank"] : []).forEach(function (h) { var c = document.createElement("span"); c.textContent = h; head.appendChild(c); });
    box.appendChild(head);
    GAMES.forEach(function (g) {
      var rec = all[g[0]] || {}, s = rec.stats || {}, p = rec.pct;
      var row = document.createElement("div");
      row.className = "ac-row";
      var cells = [g[1], String(s.played || 0), String(s.streak || 0), String(s.max || 0), p && p.count ? Math.round(p.sum / p.count) + "%" : "none yet"];
      cells.forEach(function (t, i) { var c = document.createElement("span"); c.textContent = t; if (i === 0) c.className = "ac-name"; row.appendChild(c); });
      if (signed) { var rc = document.createElement("span"); rc.setAttribute("data-rank", g[0]); rc.textContent = s.played ? "..." : "none yet"; row.appendChild(rc); }
      box.appendChild(row);
    });
    if (signed) fillRanks();
  }

  // The server's all-time rank by wins for each game played, e.g. "#4 of 52". Other measures are on the leaderboards page.
  function fillRanks() {
    var s = G.session.get();
    G.sync().then(function () { return G.api({ action: "rank" }, s.session); }).then(function (res) {
      var games = res.status === 200 && res.body && res.body.games ? res.body.games : {};
      Array.prototype.forEach.call(document.querySelectorAll("[data-rank]"), function (c) {
        var r = games[c.getAttribute("data-rank")], w = r && r.w;
        if (w) { c.textContent = "#" + w.rank + " of " + w.total; c.setAttribute("title", "By wins. Ahead of " + w.pct + "% of players."); }
        else if (c.textContent === "...") c.textContent = "not counted yet";
      });
    }, function () { Array.prototype.forEach.call(document.querySelectorAll("[data-rank]"), function (c) { if (c.textContent === "...") c.textContent = ""; }); });
  }

  function renderAch() {
    var have = A.unlocked(), list = $("ac-ach"), n = 0;
    list.textContent = "";
    A.defs.forEach(function (d) {
      var li = document.createElement("li");
      var got = have[d.id] !== undefined;
      if (got) n++;
      li.className = "ac-ach-item";
      li.setAttribute("data-got", got ? "1" : "0");
      var h = document.createElement("strong");
      h.textContent = d.name;
      var p = document.createElement("span");
      p.textContent = d.desc;
      var st = document.createElement("em");
      st.textContent = got ? "Unlocked on puzzle " + (have[d.id] + 1) : "Locked";
      li.appendChild(h); li.appendChild(p); li.appendChild(st);
      list.appendChild(li);
    });
    $("ac-ach-count").textContent = n + " of " + A.defs.length;
  }

  function renderAccount() {
    var s = G.session.get();
    $("ac-signin").hidden = !!s;
    $("ac-profile").hidden = !s;
    $("ac-who").textContent = s ? (s.name || s.email) : "";
    if (s) { $("ac-email-shown").textContent = s.email; $("ac-name").value = s.name || ""; $("ac-remind").checked = !!s.remind; }
    renderStats(); renderAch();
    if (s && window.PLRating && G.api) {
      G.api({ action: "ratings" }, s.session).then(function (res) {
        if (res.status !== 200) return;
        $("ac-public").checked = !!res.body.public;
        var bits = [];
        if (res.body.chess) bits.push("Chess Puzzles " + res.body.chess.r + " (" + res.body.chess.n + " played)");
        if (res.body.sudoku) bits.push("Sudoku Unlimited " + res.body.sudoku.r + " (" + res.body.sudoku.n + " played)");
        $("ac-ratings").textContent = bits.length ? "Your ratings: " + bits.join(", ") + "." : "You have no puzzle ratings yet. Try Chess Puzzles or Sudoku Unlimited.";
      }, function () {});
    }
  }

  function verify(token) {
    msg("Signing you in.");
    return G.api({ action: "login_verify", token: token }).then(function (res) {
      if (res.status !== 200) { msg("That sign-in link has expired or was already used. Request a new one below."); return; }
      G.session.set({ session: res.body.session, email: res.body.email, name: res.body.name || "" });
      if (res.body.isNew && window.plTrack) window.plTrack("games_signup", window.plFirstTouch ? window.plFirstTouch() : "direct");
      return G.sync().then(function () { msg("Signed in. You stay signed in on this browser, and your progress is saved to your account. If you also play in another browser or app, ask for a link there once too."); });
    }).catch(function () { msg("Could not reach the server. Try again in a moment."); });
  }

  function wire() {
    $("ac-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var email = $("ac-email").value.trim();
      $("ac-send").disabled = true;
      G.api({ action: "login_request", email: email }).then(function (res) {
        if (res.status === 200) { if (G.markKnown) G.markKnown(true); msg("Check your email for a sign-in link. It works once and expires in 15 minutes."); }
        else if (res.status === 429) msg("Too many requests for that address today. Try again tomorrow.");
        else if (res.status === 400) msg("That does not look like an email address.");
        else msg("The email could not be sent. Try again in a moment.");
      }).catch(function () { msg("Could not reach the server. Try again in a moment."); })
        .then(function () { $("ac-send").disabled = false; });
    });
    $("ac-name-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var s = G.session.get();
      if (!s) return;
      G.api({ action: "set_name", name: $("ac-name").value }, s.session).then(function (res) {
        if (res.status === 200) { s.name = res.body.name; G.session.set(s); msg("Name saved."); renderAccount(); }
        else msg("Use 2 to 24 letters, numbers, spaces, dots, dashes or underscores.");
      });
    });
    $("ac-public").addEventListener("change", function () {
      var s = G.session.get(), on = $("ac-public").checked;
      if (!s) return;
      G.api({ action: "set_public", on: on }, s.session).then(function (res) {
        if (res.status === 200) msg(on ? "You are on the leaderboards." : "You are off the leaderboards and your rows are removed.");
        else { $("ac-public").checked = !on; msg(res.body && res.body.error === "name_needed" ? "Save a display name first. Names with blocked words cannot be shown." : "Could not change that right now."); }
      });
    });
    $("ac-remind").addEventListener("change", function () {
      var s = G.session.get(), on = $("ac-remind").checked;
      if (!s) return;
      G.api({ action: "set_reminder", on: on }, s.session).then(function (res) {
        if (res.status === 200) { s.remind = on; G.session.set(s); msg(on ? "Streak reminders are on. You will get at most one email a day, only when a streak is about to end." : "Streak reminders are off."); }
        else { $("ac-remind").checked = !on; msg("Could not change that right now."); }
      });
    });
    $("ac-sync").addEventListener("click", function () {
      msg("Syncing.");
      G.sync().then(function (res) { msg(res && res.status === 200 ? "Synced." : "Could not sync right now."); renderAccount(); });
    });
    $("ac-logout").addEventListener("click", function () {
      var s = G.session.get();
      (s ? G.api({ action: "logout" }, s.session) : Promise.resolve()).catch(function () {}).then(function () {
        G.session.set(null); if (G.markKnown) G.markKnown(false); msg("Signed out. Progress stays in this browser."); renderAccount();
      });
    });
    var armed = false;
    $("ac-delete").addEventListener("click", function () {
      var s = G.session.get();
      if (!s) return;
      if (!armed) { armed = true; $("ac-delete-note").hidden = false; $("ac-delete").textContent = "Confirm: delete my account"; return; }
      G.api({ action: "delete_account" }, s.session).then(function (res) {
        armed = false; $("ac-delete-note").hidden = true; $("ac-delete").textContent = "Delete my account";
        if (res.status === 200 || res.status === 401) { G.session.set(null); msg("Your account and its saved progress were deleted."); renderAccount(); }
        else msg("Could not delete right now. Try again, or email ben@purplelink.llc.");
      });
    });
  }

  wire();
  var off = (location.search.match(/[?&]off=([a-f0-9]{64})\.([a-f0-9]{32})/) || []);
  var token = (location.search.match(/[?&]t=([a-f0-9]{48})/) || [])[1];
  if (off[1]) {
    history.replaceState(null, "", location.pathname);
    G.api({ action: "remind_off", acct: off[1], token: off[2] }).then(function (res) {
      msg(res.status === 200 ? "Streak reminder emails are turned off." : "That link is not valid any more. Sign in to change the setting.");
      var s = G.session.get(); if (s) { s.remind = false; G.session.set(s); }
      renderAccount();
    });
    G.ready.then(renderAccount);
  } else if (token) {
    history.replaceState(null, "", location.pathname);
    verify(token).then(function () { renderAccount(); });
  } else {
    G.ready.then(renderAccount);
  }
  renderAccount();
})();
