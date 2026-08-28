// First-party, cookieless analytics beacon (purplelink).
// Sends a pageview on load, exposes window.plTrack(type, meta), and wraps fetch
// so every call to the LaTeX-tools Modal backend is recorded as a "tool_use"
// event (tagged by the tool page). This is what Cloudflare Web Analytics can't
// tell you: which tools are actually run. No cookies, no fingerprinting. Honors
// Do Not Track. Same-origin only (no CSP change, no third-party load).
(function () {
  var dnt = navigator.doNotTrack || window.doNotTrack || navigator.msDoNotTrack;
  if (dnt === "1" || dnt === "yes") return;

  var ENDPOINT = "/.netlify/functions/track";
  var TOOL_API_HOST = "purplelink-latextools-web.modal.run";
  var CHECKOUT_FN = "/.netlify/functions/checkout";

  function refHost() {
    try {
      if (!document.referrer) return "";
      var u = new URL(document.referrer);
      if (u.host === location.host) return "";
      return u.host;
    } catch (e) { return ""; }
  }
  function utmSource() {
    try { return new URLSearchParams(location.search).get("utm_source") || ""; }
    catch (e) { return ""; }
  }
  function send(payload) {
    try {
      var body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
      } else {
        fetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true });
      }
    } catch (e) { /* analytics must never break the page */ }
  }

  window.plTrack = function (type, meta) {
    send({ t: type || "event", p: location.pathname, h: location.hostname, r: refHost(), u: utmSource(), m: meta || "" });
  };

  // Pageview on load (covers article reads and tool-page visits).
  window.plTrack("pageview");

  // Wrap fetch: any call to the tools' Modal backend is a real tool run.
  try {
    var _fetch = window.fetch;
    if (typeof _fetch === "function") {
      window.fetch = function (input, init) {
        try {
          var url = typeof input === "string" ? input : (input && input.url) || "";
          if (url.indexOf(TOOL_API_HOST) !== -1) {
            var path = "";
            try { path = new URL(url).pathname; } catch (e) { path = url.split("modal.run")[1] || ""; }
            window.plTrack("tool_use", (path || "").split("?")[0]);
          } else if (url.indexOf(CHECKOUT_FN) !== -1) {
            // Someone pressed a buy button. Fires on intent, before Stripe is
            // reached, which is the number that was missing: 24 people landed
            // on /kits/clip-pipeline/ in a month and Stripe recorded no session
            // at all, and there was no way to tell whether they never clicked
            // or clicked and something failed.
            var product = "";
            try {
              var body = init && init.body;
              if (typeof body === "string") { product = (JSON.parse(body) || {}).product || ""; }
            } catch (e) { /* meta is optional; never break checkout for it */ }
            window.plTrack("checkout_click", product);
          }
        } catch (e) { /* ignore */ }
        return _fetch.apply(this, arguments);
      };
    }
  } catch (e) { /* leave fetch untouched on any error */ }
})();
