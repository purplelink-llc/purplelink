// /vitae/plus/success/ — turn a paid Stripe session into a Vitae Plus license key.
// Calls vitae-license, then shows the key with a Copy button. Everything is built
// with textContent; nothing from the response is parsed as HTML.
(function () {
  var box = document.getElementById("license");
  if (!box) return;

  var MAX_PENDING_RETRIES = 6;
  var RETRY_MS = 5000;
  var pendingTries = 0;

  function clear() {
    while (box.firstChild) box.removeChild(box.firstChild);
  }

  function status(text, withSpinner) {
    clear();
    var p = document.createElement("p");
    p.className = "tool-status";
    if (withSpinner) {
      var s = document.createElement("span");
      s.className = "tool-spinner";
      s.setAttribute("aria-hidden", "true");
      p.appendChild(s);
    }
    p.appendChild(document.createTextNode(text));
    box.appendChild(p);
    return p;
  }

  function retryButton() {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-ghost";
    b.textContent = "Try again";
    b.addEventListener("click", function () {
      pendingTries = 0;
      load();
    });
    var row = document.createElement("div");
    row.className = "license-actions";
    row.appendChild(b);
    box.appendChild(row);
  }

  function showKey(key, email) {
    clear();
    var code = document.createElement("code");
    code.className = "license-key";
    code.id = "license-key";
    code.tabIndex = 0;
    code.setAttribute("aria-label", "Your Vitae Plus license key");
    code.textContent = key;
    box.appendChild(code);

    var row = document.createElement("div");
    row.className = "license-actions";
    var copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn btn-primary";
    copy.textContent = "Copy key";
    var copied = document.createElement("span");
    copied.className = "license-note";
    copied.setAttribute("role", "status");
    copy.addEventListener("click", function () {
      copyText(key).then(
        function () { copied.textContent = "Copied."; },
        function () {
          selectKey(code);
          copied.textContent = "Selected. Press Command-C to copy.";
        }
      );
    });
    row.appendChild(copy);
    row.appendChild(copied);
    box.appendChild(row);

    if (email) {
      var note = document.createElement("p");
      note.className = "license-note";
      note.textContent = "Stripe sends your receipt, with the order number, to " + email + ".";
      box.appendChild(note);
    }
  }

  function selectKey(el) {
    try {
      var range = document.createRange();
      range.selectNodeContents(el);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    } catch (e) { /* selection is a fallback only */ }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return Promise.reject(new Error("no clipboard"));
  }

  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    status("This link is missing its order reference. If you just paid, email ben@purplelink.llc with the order number from your Stripe receipt and you will get your key.");
    return;
  }

  function load() {
    status("Preparing your key…", true);
    fetch("/.netlify/functions/vitae-license?session_id=" + encodeURIComponent(sessionId), { cache: "no-store" })
      .then(function (resp) {
        return resp.json().then(
          function (b) { return { code: resp.status, body: b || {} }; },
          function () { return { code: resp.status, body: {} }; }
        );
      })
      .then(function (r) {
        if (r.code === 200 && typeof r.body.key === "string" && r.body.key.indexOf("VP1-") === 0) {
          showKey(r.body.key, typeof r.body.email === "string" ? r.body.email : "");
          return;
        }
        if (r.code === 402) {
          if (pendingTries < MAX_PENDING_RETRIES) {
            pendingTries += 1;
            status("Your payment is still processing. This page will try again in a moment.", true);
            setTimeout(load, RETRY_MS);
          } else {
            status("Your payment is still processing. Try again in a minute; if it does not clear, email ben@purplelink.llc with the order number from your Stripe receipt.");
            retryButton();
          }
          return;
        }
        if (r.code === 404 || r.code === 400) {
          status("We could not find a Vitae Plus order for this link. If you were charged, email ben@purplelink.llc with the order number from your Stripe receipt.");
          return;
        }
        if (r.code === 429) {
          status("Too many requests from this address today. Try again tomorrow, or email ben@purplelink.llc with the order number from your Stripe receipt.");
          return;
        }
        status("Something went wrong preparing your key. Try again in a moment, or email ben@purplelink.llc with the order number from your Stripe receipt.");
        retryButton();
      })
      .catch(function () {
        status("Could not reach the server. Check your connection and try again.");
        retryButton();
      });
  }

  load();
})();
