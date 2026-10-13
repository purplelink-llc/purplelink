// /moderntex/buy/ - the page the in-app Buy button opens. Starts the Stripe Checkout
// session for ModernTex without a second click, but only when the link carries
// ?from=trial (so a crawler or a stray visit does not create sessions). Anyone else gets
// the button. Attribution (from:trial and the optional d=<0-7> trial day) is recorded by
// analytics.js, which adds it to the checkout request.
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

  function start() {
    if (started) return;
    started = true;
    btn.disabled = true;
    say("Opening checkout...", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: "moderntex" }),
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

  btn.addEventListener("click", start);
  try {
    if (new URLSearchParams(window.location.search).get("from") === "trial") start();
  } catch (e) { /* the button still works */ }
})();
