/* /games/account/: stats, achievements and the optional email-link sign-in. */
(function () {
  "use strict";
  var G = window.PLGames, A = window.PLAch;
  if (!G || !A) return;
  var $ = function (id) { return document.getElementById(id); };
  var GAMES = [["linkle", "Linkle"], ["quadlink", "Quadlink"], ["daily-five", "Daily Five"], ["crossword", "Crossword"]];

  function msg(t) { $("ac-msg").textContent = t || ""; }
  function fmt(sec) { var m = Math.floor(sec / 60), s = sec % 60; return m + ":" + (s < 10 ? "0" : "") + s; }

  function renderStats() {
    var all = G.all(), box = $("ac-stats");
    box.textContent = "";
    var head = document.createElement("div");
    head.className = "ac-row ac-head";
    ["Game", "Finished", "Streak", "Best streak", "Avg. percentile"].forEach(function (h) { var c = document.createElement("span"); c.textContent = h; head.appendChild(c); });
    box.appendChild(head);
    GAMES.forEach(function (g) {
      var rec = all[g[0]] || {}, s = rec.stats || {}, p = rec.pct;
      var row = document.createElement("div");
      row.className = "ac-row";
      var cells = [g[1], String(s.played || 0), String(s.streak || 0), String(s.max || 0), p && p.count ? Math.round(p.sum / p.count) + "%" : "none yet"];
      cells.forEach(function (t, i) { var c = document.createElement("span"); c.textContent = t; if (i === 0) c.className = "ac-name"; row.appendChild(c); });
      box.appendChild(row);
    });
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
    if (s) { $("ac-email-shown").textContent = s.email; $("ac-name").value = s.name || ""; }
    renderStats(); renderAch();
  }

  function verify(token) {
    msg("Signing you in.");
    return G.api({ action: "login_verify", token: token }).then(function (res) {
      if (res.status !== 200) { msg("That sign-in link has expired or was already used. Request a new one below."); return; }
      G.session.set({ session: res.body.session, email: res.body.email, name: res.body.name || "" });
      return G.sync().then(function () { msg("Signed in. Your progress is now saved to your account."); });
    }).catch(function () { msg("Could not reach the server. Try again in a moment."); });
  }

  function wire() {
    $("ac-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var email = $("ac-email").value.trim();
      $("ac-send").disabled = true;
      G.api({ action: "login_request", email: email }).then(function (res) {
        if (res.status === 200) msg("Check your email for a sign-in link. It works once and expires in 15 minutes.");
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
    $("ac-sync").addEventListener("click", function () {
      msg("Syncing.");
      G.sync().then(function (res) { msg(res && res.status === 200 ? "Synced." : "Could not sync right now."); renderAccount(); });
    });
    $("ac-logout").addEventListener("click", function () {
      var s = G.session.get();
      (s ? G.api({ action: "logout" }, s.session) : Promise.resolve()).catch(function () {}).then(function () {
        G.session.set(null); msg("Signed out. Progress stays in this browser."); renderAccount();
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
  var token = (location.search.match(/[?&]t=([a-f0-9]{48})/) || [])[1];
  if (token) {
    history.replaceState(null, "", location.pathname);
    verify(token).then(function () { renderAccount(); });
  } else {
    G.ready.then(renderAccount);
  }
  renderAccount();
})();
