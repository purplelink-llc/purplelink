// /suite/success/ — turn a paid Mac Suite (or custom bundle) session into its things; the Suite is six: the ModernTex download,
// the Outbound Veil download, the Legroom download, the Keyfeel download, the Tapefolio download, and a lifetime Vitae Plus key. Each is its own request, so one
// slow or failed part never hides the others. Everything is built with textContent or an
// escaped attribute; nothing from a response is parsed as HTML.
(function () {
  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";
  var boxes = {
    mtx: document.getElementById("dl-moderntex"),
    ov: document.getElementById("dl-ov"),
    lg: document.getElementById("dl-lg"),
    kf: document.getElementById("dl-kf"),
    tf: document.getElementById("dl-tf"),
    key: document.getElementById("license"),
  };
  if (!boxes.mtx || !boxes.ov || !boxes.lg || !boxes.kf || !boxes.tf || !boxes.key) return;

  var FALLBACK = "We could not prepare this part. Email the address on your receipt and we will send it directly.";

  function clear(box) { while (box.firstChild) box.removeChild(box.firstChild); }
  function note(box, text) {
    clear(box);
    var p = document.createElement("p");
    p.className = "tool-status";
    p.textContent = text;
    box.appendChild(p);
  }
  function retry(box, fn) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-ghost";
    b.textContent = "Try again";
    b.addEventListener("click", fn);
    box.appendChild(b);
  }

  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    var msg = "If you just completed a purchase, use the link in your receipt email. If this looks wrong, email the address on your receipt and we will help.";
    note(boxes.mtx, msg); note(boxes.ov, msg); note(boxes.lg, msg); note(boxes.kf, msg); note(boxes.tf, msg); note(boxes.key, msg);
    return;
  }

  function files(box, fn, appName) {
    function go() {
      note(box, "Preparing your download…");
      fetch("/.netlify/functions/" + fn + "?session_id=" + encodeURIComponent(sessionId))
        .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
        .then(function (r) {
          if (!r.ok || !r.body || !r.body.files || !r.body.files.length) {
            note(box, (r.body && r.body.detail) || FALLBACK);
            retry(box, go);
            return;
          }
          clear(box);
          r.body.files.forEach(function (f) {
            var a = document.createElement("a");
            a.className = "btn btn-primary kit-dl-btn";
            a.href = f.url;
            a.setAttribute("download", "");
            a.textContent = "Download: " + f.label;
            box.appendChild(a);
          });
          if (r.body.license) {
            var holder = document.createElement("div");
            holder.className = "license-holder";
            var lead = document.createElement("p");
            lead.className = "kit-buy-meta kit-center";
            lead.textContent = "Your " + appName + " license key:";
            box.appendChild(lead);
            box.appendChild(holder);
            showKey(holder, r.body.license, "Your " + appName + " license key");
          }
        })
        .catch(function () { note(box, FALLBACK); retry(box, go); });
    }
    go();
  }

  var MAX_PENDING = 6, tries = 0;
  function loadKey() {
    var box = boxes.key;
    note(box, "Preparing your key…");
    fetch("/.netlify/functions/vitae-license?session_id=" + encodeURIComponent(sessionId))
      .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
      .then(function (r) {
        if (r.status === 402 && tries < MAX_PENDING) { tries++; setTimeout(loadKey, 5000); return; }
        if (r.status !== 200 || !r.body || !r.body.key) {
          note(box, (r.body && r.body.detail) || FALLBACK);
          retry(box, function () { tries = 0; loadKey(); });
          return;
        }
        showKey(box, r.body.key);
      })
      .catch(function () { note(box, FALLBACK); retry(box, function () { tries = 0; loadKey(); }); });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      try {
        var t = document.createElement("textarea");
        t.value = text;
        document.body.appendChild(t);
        t.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(t);
        ok ? resolve() : reject();
      } catch (e) { reject(e); }
    });
  }

  function showKey(box, key, label) {
    clear(box);
    var code = document.createElement("code");
    code.className = "license-key";
    code.tabIndex = 0;
    code.setAttribute("aria-label", label || "Your Vitae Plus key");
    code.textContent = key;
    box.appendChild(code);
    var row = document.createElement("div");
    row.className = "license-actions";
    var copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn btn-primary";
    copy.textContent = "Copy key";
    var said = document.createElement("span");
    said.className = "license-note";
    said.setAttribute("role", "status");
    copy.addEventListener("click", function () {
      copyText(key).then(
        function () { said.textContent = "Copied."; },
        function () {
          var r = document.createRange();
          r.selectNodeContents(code);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(r);
          said.textContent = "Selected. Press Command-C to copy.";
        }
      );
    });
    row.appendChild(copy);
    row.appendChild(said);
    box.appendChild(row);
  }

  // A custom bundle holds only the parts that were chosen. purchase-license reads them from Stripe's own record
  // and returns `parts` for a bundle; the whole Suite (and any failure to ask) shows all six.
  function start(parts) {
    var keep = function (slug) { return !parts || parts.indexOf(slug) !== -1; };
    ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio", "vitae-plus"].forEach(function (slug) {
      var section = document.getElementById("part-" + slug);
      if (section && !keep(slug)) section.hidden = true;
    });
    var keys = document.getElementById("part-keys");
    if (keys && !(keep("moderntex") || keep("outbound-veil") || keep("legroom"))) keys.hidden = true;
    if (parts) {
      var title = document.getElementById("hero-title");
      var lead = document.getElementById("hero-lead");
      if (title) title.textContent = "Your bundle is yours";
      if (lead) lead.textContent = "Everything you chose is below: the downloads and license keys for your parts. We have also emailed this page to the address on your receipt.";
    }
    if (keep("moderntex")) files(boxes.mtx, "moderntex-download");
    if (keep("outbound-veil")) files(boxes.ov, "outbound-veil-download");
    if (keep("legroom")) files(boxes.lg, "legroom-download");
    if (keep("keyfeel")) files(boxes.kf, "keyfeel-download", "Keyfeel");
    if (keep("tapefolio")) files(boxes.tf, "tapefolio-download", "Tapefolio");
    if (keep("vitae-plus")) loadKey();
  }
  fetch("/.netlify/functions/purchase-license?session_id=" + encodeURIComponent(sessionId))
    .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
    .then(function (r) { start(r.ok && r.body && Array.isArray(r.body.parts) ? r.body.parts : null); })
    .catch(function () { start(null); });
})();
