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
    try {
      var q = new URLSearchParams(location.search);
      // ?from= tags internal referrals such as the ModernTex trial's Buy button.
      // ?ref=vitae / vitae-card tag visits from the Vitae app's sidebar card
      // (the privacy page says these are counted). Other ?ref= values are
      // personal referral codes and are deliberately not recorded.
      var ref = q.get("ref");
      var appRef = (ref === "vitae" || ref === "vitae-card") ? "ref:" + ref : "";
      return q.get("utm_source") || (q.get("from") ? "from:" + q.get("from") : "") || appRef;
    }
    catch (e) { return ""; }
  }
  // Where visits come from, remembered so a later purchase can say which
  // channel led to it: the first arrival and the most recent one that was not
  // direct (a referring site, a campaign tag, or a Google ad click, as a yes/no
  // flag only, never the click id). Kept in local storage for 90 days and sent
  // only with a checkout request, where it is attached to the Stripe order.
  // Direct visits, Stripe's return trip and hops within the site never
  // overwrite it. The privacy page's clear button removes it (pl_ prefix).
  var ATTR_KEY = "pl_attr";
  var ATTR_DAYS = 90;
  function clip(v, n) { return String(v || "").replace(/[^\w.\-:\/ ]/g, "").slice(0, n); }
  function arrival() {
    try {
      var q = new URLSearchParams(location.search);
      var r = refHost();
      if (/(^|\.)(stripe\.com|purplelink\.llc)$/.test(r)) r = "";
      var t = {
        s: clip(utmSource(), 60), m: clip(q.get("utm_medium"), 40), c: clip(q.get("utm_campaign"), 80),
        r: clip(r, 80), g: (q.get("gclid") || q.get("gbraid") || q.get("wbraid")) ? 1 : 0,
        l: clip(location.pathname, 120), d: new Date().toISOString().slice(0, 10)
      };
      return (t.s || t.r || t.g) ? t : null;
    } catch (e) { return null; }
  }
  var attr = (function () {
    var a = {};
    try { a = JSON.parse(localStorage.getItem(ATTR_KEY) || "{}") || {}; } catch (e) { a = {}; }
    var cutoff = new Date(Date.now() - ATTR_DAYS * 864e5).toISOString().slice(0, 10);
    if (a.first && !(a.first.d >= cutoff)) a.first = null;
    if (a.last && !(a.last.d >= cutoff)) a.last = null;
    var now = arrival();
    if (now) { if (!a.first) a.first = now; a.last = now; }
    try {
      if (a.first || a.last) localStorage.setItem(ATTR_KEY, JSON.stringify({ first: a.first || null, last: a.last || null }));
      else localStorage.removeItem(ATTR_KEY);
    } catch (e) { /* storage blocked: the sale just shows as direct */ }
    return a;
  })();

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
          } else if (url.indexOf("/.netlify/functions/purchases-recover") !== -1) {
            window.plTrack("recover_request", "");
          } else if (url.indexOf(CHECKOUT_FN) !== -1) {
            // Someone pressed a buy button. Fires on intent, before Stripe is
            // reached, which is the number that was missing: 24 people landed
            // on /kits/clip-pipeline/ in a month and Stripe recorded no session
            // at all, and there was no way to tell whether they never clicked
            // or clicked and something failed.
            var product = "";
            try {
              var body = init && init.body;
              if (typeof body === "string") {
                var parsed = JSON.parse(body) || {};
                product = parsed.product || "";
                if ((attr.first || attr.last) && !parsed.attr) {
                  parsed.attr = { first: attr.first || null, last: attr.last || null };
                  init = Object.assign({}, init, { body: JSON.stringify(parsed) });
                }
              }
            } catch (e) { /* meta is optional; never break checkout for it */ }
            window.plTrack("checkout_click", product);
          }
        } catch (e) { /* ignore */ }
        return _fetch.call(this, input, init);
      };
    }
  } catch (e) { /* leave fetch untouched on any error */ }

  // The ModernTex trial is a plain download link, not a fetch, so the wrapper
  // above never sees it. Count the click: trial downloads against later
  // checkout_click/sales is the whole funnel the trial exists to measure.
  document.addEventListener("click", function (ev) {
    try {
      var a = ev.target && ev.target.closest && ev.target.closest("a[href]");
      if (a && a.getAttribute("href").indexOf("moderntex-download?trial=1") !== -1) {
        window.plTrack("trial_download", "moderntex");
      }
      if (a && a.getAttribute("href").indexOf("outbound-veil-download?trial=1") !== -1) {
        window.plTrack("ov_trial_download", "outbound-veil");
      }
      // Anything else marked data-track="<event>" (optional data-track-meta):
      // template downloads, the phone sticky bar.
      var t = ev.target && ev.target.closest && ev.target.closest("[data-track]");
      if (t) window.plTrack(t.getAttribute("data-track"), t.getAttribute("data-track-meta") || "");
    } catch (e) { /* never interfere with the download */ }
  }, true);
})();
