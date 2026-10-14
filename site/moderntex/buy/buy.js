// /moderntex/buy/ - the page the in-app Buy button opens. Starts the Stripe Checkout
// session for ModernTex without a second click, but only when the link carries
// ?from=trial (so a crawler or a stray visit does not create sessions). Anyone else gets
// the button. Since the app's expired-trial screen the link is
// ?utm_source=moderntex-app&utm_medium=trial-screen&utm_campaign=expired&td=<0-30|unknown>, which starts
// checkout the same way. First-touch attribution (the utm tags, or from:trial and d=<0-7>) is recorded by
// analytics.js, which adds it to the checkout request; this file adds the trial day (td) and utm_source (src)
// to the request, and checkout.mjs validates both and stores them as Stripe metadata (trial_day, app_source).
(function () {
  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;
  var started = false;

  function say(msg, isError) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = isError ? "tool-status bib-err" : "tool-status";
  }

  function params() { try { return new URLSearchParams(window.location.search); } catch (e) { return null; } }
  // td: a whole number 0 to 30 or the word "unknown"; anything else is dropped (the server checks again).
  function trialDay(q) {
    var v = q && q.get("td");
    return v !== null && v !== undefined && /^(?:[0-9]|[12][0-9]|30|unknown)$/.test(v) ? v : "";
  }
  function appSource(q) {
    var v = q && q.get("utm_source");
    return v && /^[a-z0-9_-]{1,40}$/.test(v) ? v : "";
  }

  function start() {
    if (started) return;
    started = true;
    btn.disabled = true;
    say("Opening checkout...", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.url) throw { detail: "Checkout did not return a redirect URL." };
        window.location.assign(data.url);
      })
      .catch(function (err) {
        started = false;
        btn.disabled = false;
        say((err && err.detail) || "Could not start checkout. Try the button again.", true);
      });
  }

  function payload() {
    var q = params(), p = { product: "moderntex" };
    var td = trialDay(q), src = appSource(q);
    if (td) p.td = td;
    if (src) p.src = src;
    return p;
  }

  btn.addEventListener("click", start);
  try {
    var q = params();
    if (q && (q.get("from") === "trial" || q.get("utm_source") === "moderntex-app")) start();
  } catch (e) { /* the button still works */ }
})();
