/* Optional sign-in: keeps a player's saved progress in step with their account.
   Without a session this does nothing and the games stay device-only. Load after core.js. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var API = "/.netlify/functions/games-api", SKEY = "pl-games-session";

  function getSession() { try { return JSON.parse(localStorage.getItem(SKEY)); } catch (e) { return null; } }
  function setSession(s) {
    try { if (s) localStorage.setItem(SKEY, JSON.stringify(s)); else localStorage.removeItem(SKEY); } catch (e) { /* ignore */ }
  }
  function api(body, session) {
    var headers = { "Content-Type": "application/json" };
    if (session) headers.Authorization = "Bearer " + session;
    return fetch(API, { method: "POST", headers: headers, body: JSON.stringify(body) }).then(function (r) {
      return r.json().then(function (j) { return { status: r.status, body: j }; }, function () { return { status: r.status, body: {} }; });
    });
  }
  G.api = api;
  G.session = { get: getSession, set: setSession };

  // Send what this device has, adopt the merged result. If the player moved on while the request was in
  // flight, keep their newer local copy and let the next push carry it.
  // One sync at a time in this tab. Two overlapping requests for the same account could each read the old copy and
  // both count a result in the all-time ranks.
  var chain = Promise.resolve();
  function sync() {
    var run = function () { return syncNow(); };
    chain = chain.then(run, run);
    return chain;
  }
  function syncNow() {
    var s = getSession();
    if (!s) return Promise.resolve(null);
    var snapshot = JSON.stringify(G.all());
    return api({ action: "sync", data: G.all() }, s.session).then(function (res) {
      if (res.status === 401) { setSession(null); return null; }
      if (res.status === 200) {
        if (JSON.stringify(G.all()) === snapshot) G.replaceAll(res.body.data);
        if (res.body.name !== s.name || !!res.body.remind !== !!s.remind) { s.name = res.body.name; s.remind = !!res.body.remind; setSession(s); }
      }
      return res;
    }).catch(function () { return null; });
  }
  G.sync = sync;

  // The signed-in player's all-time rank in one game: { w, s, p } each { v, rank, total, pct }, or null.
  G.rankFor = function (game) {
    var s = getSession();
    if (!s) return Promise.resolve(null);
    return api({ action: "rank", game: game }, s.session).then(function (res) {
      return res.status === 200 && res.body && res.body.games ? res.body.games[game] || null : null;
    }, function () { return null; });
  };

  // Pages wait (briefly) for the first sync so they start from the merged copy.
  G.ready = getSession()
    ? Promise.race([sync(), new Promise(function (r) { window.setTimeout(r, 2500); })]).then(function () {})
    : Promise.resolve();

  var timer = 0, plain = G.setGame;
  G.setGame = function (name, value) {
    plain(name, value);
    if (!getSession()) return;
    window.clearTimeout(timer);
    timer = window.setTimeout(sync, 2500);
  };
})();
