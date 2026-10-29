// First-party analytics beacon (purplelink).
// Sends a pageview on load, exposes window.plTrack(type, meta), and wraps fetch
// so every call to the LaTeX-tools Modal backend is recorded as a "tool_use"
// event (tagged by the tool page). This is what Cloudflare Web Analytics can't
// tell you: which tools are actually run (tool_use, plus tool_outcome and offer_view/offer_click for the per-tool counts in track.mjs), and which affiliate links are clicked (affiliate_click: program and page, never the destination). No fingerprinting. The one cookie is pl_attr,
// set by the server (not this script) when an ad or campaign visitor downloads the ModernTex trial; see the trial
// link code at the bottom. Honors Do Not Track. Same-origin only (no CSP change, no third-party load).
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
      // Some mail clients leave quoted-printable "=3D" in a link, so utm_source=email
      // arrives as "3Demail". Strip that prefix so those visits count as email.
      var src = (q.get("utm_source") || "").replace(/^3D(?=[a-z])/i, "");
      return src || (q.get("from") ? "from:" + q.get("from") : "") || appRef;
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
  // The in-app Buy link may carry the trial day as ?from=trial&d=<0-7>. Only a single digit 0 to 7 counts,
  // and only with from=trial; anything else is ignored. It is recorded as the campaign field "trial-day-N"
  // so the first-touch source stays "from:trial" and existing reports keep matching.
  function trialDay(q) {
    if (q.get("from") !== "trial") return "";
    var d = q.get("d");
    return d !== null && /^[0-7]$/.test(d) ? "trial-day-" + d : "";
  }
  function arrival() {
    try {
      var q = new URLSearchParams(location.search);
      var r = refHost();
      if (/(^|\.)(stripe\.com|purplelink\.llc)$/.test(r)) r = "";
      var t = {
        s: clip(utmSource(), 60), m: clip(q.get("utm_medium"), 40), c: clip(q.get("utm_campaign") || trialDay(q), 80),
        t: clip(q.get("utm_content"), 60),
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
    // A first visit with no campaign tag, outside referrer or ad click is recorded too, as a placeholder (x: 1) holding
    // only the landing page and date, so an order from a direct visitor shows where they landed instead of nothing
    // (2026-10-28: 6 of 13 site orders since 09-28 had no record). A later tagged arrival still replaces it, so the
    // first-touch channel means what it meant before; checkout.mjs keeps l and d and drops the marker.
    if (now) { if (!a.first || a.first.x) a.first = now; a.last = now; }
    else if (!a.first) a.first = { x: 1, l: clip(location.pathname, 120), d: new Date().toISOString().slice(0, 10) };
    try {
      if (a.first || a.last) localStorage.setItem(ATTR_KEY, JSON.stringify({ first: a.first || null, last: a.last || null }));
      else localStorage.removeItem(ATTR_KEY);
    } catch (e) { /* storage blocked: the sale just shows as direct */ }
    return a;
  })();

  // Reddit ad click id (?rdt_cid=), kept like the first arrival (90 days, first one wins, "pl_" prefix so the privacy
  // page's clear button removes it) and sent only with a ModernTex checkout, so the server can report that sale to
  // Reddit. Never recorded under Do Not Track (this whole file stops above in that case).
  var RDT_KEY = "pl_rdt";
  var rdtClick = (function () {
    var r = null;
    try { r = JSON.parse(localStorage.getItem(RDT_KEY) || "null"); } catch (e) { r = null; }
    var cutoff = new Date(Date.now() - ATTR_DAYS * 864e5).toISOString().slice(0, 10);
    if (r && !(r.d >= cutoff)) r = null;
    try {
      var c = new URLSearchParams(location.search).get("rdt_cid");
      c = c ? String(c).replace(/[^\w.\-:=]/g, "").slice(0, 128) : "";
      if (c && !r) r = { c: c, d: new Date().toISOString().slice(0, 10) };
    } catch (e) { /* ignore */ }
    try { if (r) localStorage.setItem(RDT_KEY, JSON.stringify(r)); else localStorage.removeItem(RDT_KEY); } catch (e) { /* storage blocked */ }
    return r ? r.c : "";
  })();

  // LinkedIn reaches us under several names: www.linkedin.com and other linkedin.com hosts, the lnkd.in short
  // link, the Android app (android-app://com.linkedin.android, or com.linkedin.android as a bare host) and
  // utm_source=linkedin in any case. They are one channel, "linkedin". Only the host is looked at, so a page
  // that merely mentions linkedin in its path or query string does not count. The same rule is applied to
  // old stored records in netlify/functions/stats.mjs (keep the two in step).
  function isLinkedin(v) {
    var h = String(v || "").toLowerCase().replace(/^[a-z][a-z0-9+.\-]*:\/\//, "").split(/[\/?#]/)[0].replace(/:\d+$/, "");
    return h === "linkedin" || h === "lnkd.in" || /(^|\.)linkedin\.com$/.test(h) || /^com\.linkedin\.android(\.[a-z]+)?$/.test(h);
  }

  // The free tool pages carry one offer card whose link is tagged utm_source=tool-<slug>. That is channel "tool", with
  // the slug as the detail: the label reads "tool:<slug>". Only the campaign source is read, never the referrer, so a
  // referring site that merely has "tool" in its name is unaffected. A paid click (below) still reads "paid:..." first.
  // Mirrored in netlify/functions/stats.mjs (toolChannel), which folds the same names in stored records.
  function toolChannel(src) {
    var m = /^tool-([a-z0-9][a-z0-9-]{0,39})$/i.exec(String(src || ""));
    return m ? "tool:" + m[1].toLowerCase() : "";
  }

  // A short label for how this visitor first arrived ("google", "chatgpt.com", a campaign tag, or "direct"), for counting
  // sign-ups by channel. Nothing is stored with an account; the label goes out once, as an event in our own statistics.
  window.plFirstTouch = function () {
    var f = attr.first || attr.last;
    var label = (f && (f.s || f.r)) || (f && f.g ? "google ads" : "direct");
    return (f && toolChannel(f.s)) || (isLinkedin(label) ? "linkedin" : label);
  };

  // The first-touch channel as a short label for the funnel events below only (product-page views, trial
  // downloads, buy clicks), so cost per trial and per sale can be worked out per channel. Paid clicks
  // (a Google, Microsoft or other ad click id, or utm_medium=cpc/ppc/paid) read "paid:<source>"; otherwise the
  // campaign source, the referring site, or "direct". Same stored arrival as above; no id leaves the browser.
  function channel() {
    var f = attr.first || attr.last;
    if (!f) return "direct";
    var med = String(f.m || "").toLowerCase();
    if (f.g || med === "cpc" || med === "ppc" || med === "paid" || med === "paidsocial") return clip("paid:" + (f.s || "google"), 40);
    var tool = toolChannel(f.s);
    if (tool) return clip(tool, 40);
    var label = f.s || f.r || "direct";
    return isLinkedin(label) ? "linkedin" : clip(label, 40);
  }
  // reddit-pixel.js reads this to load Reddit's pixel only for visitors who first came from a Reddit ad.
  window.plChannel = channel;
  // The tag naming the one link that brought the first arrival (utm_content, for example a single directory listing
  // or one email batch), so a placement can be counted on its own rather than shared with its whole channel. Sent with
  // the same funnel events as the channel label, never alone. Empty when the link carried none.
  function contentTag() {
    var f = attr.first || attr.last;
    return f && f.t ? clip(f.t, 60) : "";
  }
  var FUNNEL = /^(checkout_click|trial_download|ov_trial_download|lg_trial_download|kf_trial_download|tf_trial_download|pn_trial_download|sm_trial_download|guide_mtx_trial)$/;

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
    var ev = { t: type || "event", p: location.pathname, h: location.hostname, r: refHost(), u: utmSource(), m: meta || "" };
    if (type === "pageview" || FUNNEL.test(type || "")) { ev.ft = channel(); var fc = contentTag(); if (fc) ev.fc = fc; }
    send(ev);
  };

  // Pageview on load (covers article reads and tool-page visits).
  window.plTrack("pageview");

  // Wrap fetch: any call to the tools' Modal backend is a real tool run.
  try {
    var _fetch = window.fetch;
    if (typeof _fetch === "function") {
      window.fetch = function (input, init) {
        var toolCall = false;
        try {
          var url = typeof input === "string" ? input : (input && input.url) || "";
          if (url.indexOf(TOOL_API_HOST) !== -1) {
            var path = "";
            try { path = new URL(url).pathname; } catch (e) { path = url.split("modal.run")[1] || ""; }
            window.plTrack("tool_use", (path || "").split("?")[0]);
            toolCall = true;
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
                if (!parsed.rdt && (rdtClick || channel() === "paid:reddit")) {
                  parsed.rdt = rdtClick ? { c: rdtClick } : {};
                  init = Object.assign({}, init, { body: JSON.stringify(parsed) });
                }
                if ((attr.first || attr.last) && !parsed.attr) {
                  parsed.attr = { first: attr.first || null, last: attr.last || null };
                  init = Object.assign({}, init, { body: JSON.stringify(parsed) });
                }
              }
            } catch (e) { /* meta is optional; never break checkout for it */ }
            window.plTrack("checkout_click", product);
          }
        } catch (e) { /* ignore */ }
        var pending = _fetch.call(this, input, init);
        // How the run ended, for the per-tool counts: ok, error, or limit (the tool refused because of its size,
        // time or daily limit). Counts only; the response body is never kept, and a read for the timeout flag
        // happens on a clone so the tool's own code still gets the untouched response.
        if (toolCall) {
          pending.then(function (resp) {
            try {
              var st = resp.status, kind = "error";
              if (resp.ok) kind = "ok";
              else if (st === 408 || st === 413 || st === 429 || st === 504) kind = "limit";
              if (kind !== "error" || !/json/.test(resp.headers.get("content-type") || "")) { window.plTrack("tool_outcome", kind); return; }
              resp.clone().json().then(function (j) {
                window.plTrack("tool_outcome", j && j.error === "timeout" ? "limit" : "error");
              }, function () { window.plTrack("tool_outcome", "error"); });
            } catch (e) { /* ignore */ }
          }, function () { window.plTrack("tool_outcome", "error"); });
        }
        return pending;
      };
    }
  } catch (e) { /* leave fetch untouched on any error */ }

  // Tool pages show one offer card (<aside data-offer="<app>">). Count it once per page view, when at least half of it
  // is on screen. The counts are per tool and per day on the server, with nothing that identifies the visitor.
  try {
    var offer = document.querySelector("[data-offer]");
    if (offer && "IntersectionObserver" in window) {
      var seen = new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            seen.disconnect();
            window.plTrack("offer_view", offer.getAttribute("data-offer") || "");
            return;
          }
        }
      }, { threshold: 0.5 });
      seen.observe(offer);
    }
  } catch (e) { /* the page works the same without it */ }

  // Affiliate links (rel="sponsored", stamped data-aff="<program>" by scripts/affiliates.py): which program, from
  // which page. Counted like any other event; the destination URL is never sent.
  // Links that already carry data-track (the /desk/ book cards send affiliate_click with an ISBN) are counted by the
  // data-track handler instead.
  function countAffiliate(ev) {
    var s = ev.target && ev.target.closest && ev.target.closest('a[rel~="sponsored"]');
    if (!s || s.hasAttribute("data-track")) return;
    var prog = s.getAttribute("data-aff") || "";
    if (!prog) { try { prog = new URL(s.href).hostname.replace(/^www\./, ""); } catch (e) { prog = "unknown"; } }
    var slug = location.pathname.replace(/\/+$/, "").split("/").pop() || "home";
    window.plTrack("affiliate_click", (prog + " " + slug).slice(0, 110));
  }
  // A middle click opens the link in a new tab and fires auxclick, never click. Count it for paid links only; the
  // data-track book cards on /desk/ are counted the same way so both kinds of paid link agree.
  document.addEventListener("auxclick", function (ev) {
    try {
      if (ev.button !== 1) return;
      countAffiliate(ev);
      var t = ev.target && ev.target.closest && ev.target.closest('a[rel~="sponsored"][data-track]');
      if (t) window.plTrack(t.getAttribute("data-track"), t.getAttribute("data-track-meta") || "");
    } catch (e) { /* never interfere with the link */ }
  }, true);

  // At the moment of the click, add the first-touch channel label (ach), the Reddit click id (arc), the first link's
  // tag (atg, its utm_content, which names one ad) and the day first seen (ad) to the ModernTex trial link. The server turns them into the first-party pl_attr cookie so a purchase after
  // the 7-day trial can still be credited (Safari drops script-written storage after 7 days). Nothing is added for a
  // direct visitor with no ad click, and this file does nothing at all under Do Not Track.
  function tagTrialLink(a) {
    try {
      var ch = channel().replace(/[^\w.\-:]/g, "").slice(0, 40);
      var rc = rdtClick ? String(rdtClick).replace(/[^\w.\-:=]/g, "").slice(0, 128) : "";
      if (!rc && (!ch || ch === "direct")) return;
      var f = attr.first || attr.last;
      var u = new URL(a.href, location.href);
      if (u.origin !== location.origin) return;
      var tg = contentTag().replace(/[^\w.\-]/g, "");
      u.searchParams.delete("ach"); u.searchParams.delete("arc"); u.searchParams.delete("atg"); u.searchParams.delete("ad");
      if (ch) u.searchParams.set("ach", ch);
      if (rc) u.searchParams.set("arc", rc);
      if (tg) u.searchParams.set("atg", tg);
      if (f && f.d) u.searchParams.set("ad", String(f.d).slice(0, 10));
      a.setAttribute("href", u.pathname + u.search);
    } catch (e) { /* never interfere with the download */ }
  }

  // The ModernTex trial is a plain download link, not a fetch, so the wrapper
  // above never sees it. Count the click: trial downloads against later
  // checkout_click/sales is the whole funnel the trial exists to measure.
  document.addEventListener("click", function (ev) {
    try {
      var a = ev.target && ev.target.closest && ev.target.closest("a[href]");
      if (a && a.getAttribute("href").indexOf("moderntex-download?trial=1") !== -1) {
        window.plTrack("trial_download", "moderntex");
        tagTrialLink(a);
      }
      if (a && a.getAttribute("href").indexOf("outbound-veil-download?trial=1") !== -1) {
        window.plTrack("ov_trial_download", "outbound-veil");
      }
      if (a && a.getAttribute("href").indexOf("legroom-download?trial=1") !== -1) {
        window.plTrack("lg_trial_download", "legroom");
      }
      // Keyfeel's page links ?download=1 (since 1.1.0 there is one download); ?trial=1 is the old link, kept so cached pages still count.
      if (a && /keyfeel-download\?(download|trial)=1/.test(a.getAttribute("href"))) {
        window.plTrack("kf_trial_download", "keyfeel");
      }
      if (a && /tapefolio-download\?(download|trial)=1/.test(a.getAttribute("href"))) {
        window.plTrack("tf_trial_download", "tapefolio");
      }
      if (a && /panely-download\?(download|trial)=1/.test(a.getAttribute("href"))) {
        window.plTrack("pn_trial_download", "panely");
      }
      if (a && /summonly-download\?(download|trial)=1/.test(a.getAttribute("href"))) {
        window.plTrack("sm_trial_download", "summonly");
      }
      countAffiliate(ev);
      // Anything else marked data-track="<event>" (optional data-track-meta):
      // template downloads, the phone sticky bar.
      var t = ev.target && ev.target.closest && ev.target.closest("[data-track]");
      if (t) window.plTrack(t.getAttribute("data-track"), t.getAttribute("data-track-meta") || "");
    } catch (e) { /* never interfere with the download */ }
  }, true);
})();
