// Shows the license keys a paid purchase is entitled to, on the success pages.
// <div data-license-keys> is filled from /.netlify/functions/purchase-license?session_id=… (the same key the
// purchase email carried: keys are derived from the session id). Built with textContent only.
(function () {
  var boxes = document.querySelectorAll("[data-license-keys]");
  if (!boxes.length) return;
  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";

  function clear(box) { while (box.firstChild) box.removeChild(box.firstChild); }
  function note(box, text) {
    clear(box);
    var p = document.createElement("p");
    p.className = "tool-status";
    p.textContent = text;
    box.appendChild(p);
  }

  function row(k) {
    var wrap = document.createElement("div");
    wrap.className = "key-row";
    var label = document.createElement("span");
    label.className = "key-row-label";
    label.textContent = k.label;
    var code = document.createElement("code");
    code.className = "key-row-value";
    code.textContent = k.key;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-ghost key-row-copy";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy the " + k.label + " license key");
    btn.addEventListener("click", function () {
      var done = function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(k.key).then(done, function () {});
      else {
        var range = document.createRange(); range.selectNodeContents(code);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
      }
    });
    wrap.appendChild(label); wrap.appendChild(code); wrap.appendChild(btn);
    return wrap;
  }

  Array.prototype.forEach.call(boxes, function (box) {
    if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
      note(box, "Your key is in your receipt email. Find a purchase on this site sends it again.");
      return;
    }
    var only = (box.getAttribute("data-license-product") || "").split(",").filter(Boolean);
    fetch("/.netlify/functions/purchase-license?session_id=" + encodeURIComponent(sessionId))
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (r) {
        var keys = (r.ok && r.body && r.body.keys) || [];
        if (only.length) keys = keys.filter(function (k) { return only.indexOf(k.product) !== -1; });
        if (!keys.length) {
          note(box, "Your key is in your receipt email. If it is not there, Find a purchase on this site sends it again.");
          return;
        }
        clear(box);
        keys.forEach(function (k) { box.appendChild(row(k)); });
      })
      .catch(function () { note(box, "We could not load your key just now. It is also in your receipt email."); });
  });
})();
