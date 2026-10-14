// /moderntex/not-now/ - the page the app's expired-trial screen opens when someone picks a reason for not buying
// yet (?why=<code>&td=<days>). Sends the answer once to the count-only function (netlify/functions/signal.mjs):
// the code, and the trial day if it is a whole number 0 to 30 or "unknown". Nothing else is sent. A reload in the
// same tab does not count again. Without scripts, or with an unknown code, nothing is recorded.
(function () {
  var WHY = ["price", "feature", "other-tool", "deciding", "other"];
  var statusEl = document.getElementById("signal-status");
  var q;
  try { q = new URLSearchParams(window.location.search); } catch (e) { return; }
  var why = q.get("why");
  if (WHY.indexOf(why) === -1) return;
  var td = q.get("td");
  var payload = { kind: "whynot", value: why };
  if (td !== null && /^(?:[0-9]|[12][0-9]|30|unknown)$/.test(td)) payload.td = td === "unknown" ? td : Number(td);

  var KEY = "pl_whynot_sent";
  try { if (sessionStorage.getItem(KEY) === why) { say("Your answer is already counted."); return; } } catch (e) { /* send anyway */ }

  function say(msg) { if (statusEl) statusEl.textContent = msg; }
  function done() {
    try { sessionStorage.setItem(KEY, why); } catch (e) { /* ignore */ }
    say("Your answer is counted.");
  }
  var body = JSON.stringify(payload), url = "/.netlify/functions/signal";
  try {
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true })
      .then(function (r) { if (r.ok) done(); })
      .catch(function () { /* nothing to show; the page is still a thank-you */ });
  } catch (e) {
    try { if (navigator.sendBeacon && navigator.sendBeacon(url, new Blob([body], { type: "application/json" }))) done(); } catch (e2) { /* ignore */ }
  }
})();
