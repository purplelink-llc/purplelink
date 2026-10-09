// /tapefolio/success/: turn a paid Stripe session into download links and the license key.
// Calls tapefolio-download in list mode, then renders one button per entitled file.
(function () {
  var box = document.getElementById("downloads");
  var status = document.getElementById("dl-status");
  if (!box) return;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function message(html) { box.innerHTML = '<p class="tool-status">' + html + "</p>"; }

  function showLicense(key) {
    var holder = document.getElementById("license");
    if (!holder) return;
    holder.innerHTML = "";
    var code = document.createElement("code");
    code.className = "license-key";
    code.tabIndex = 0;
    code.setAttribute("aria-label", "Your Tapefolio license key");
    code.textContent = key;
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
      var done = function () { said.textContent = "Copied."; };
      var select = function () {
        var rg = document.createRange(); rg.selectNodeContents(code);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rg);
        said.textContent = "Selected. Press Command-C to copy.";
      };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(key).then(done, select); else select();
    });
    row.appendChild(copy); row.appendChild(said);
    holder.appendChild(code); holder.appendChild(row);
  }

  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    message("If you just completed a purchase, use the download link in your receipt email. If this looks wrong, email the address on your receipt and we will help.");
    return;
  }

  fetch("/.netlify/functions/tapefolio-download?session_id=" + encodeURIComponent(sessionId))
    .then(function (resp) { return resp.json().then(function (b) { return { ok: resp.ok, body: b }; }); })
    .then(function (r) {
      if (!r.ok || !r.body || !r.body.files || !r.body.files.length) {
        message(esc((r.body && r.body.detail) || "We could not prepare your download. Email the address on your receipt and we will send the files directly."));
        return;
      }
      var html = "";
      r.body.files.forEach(function (f) {
        html += '<a class="btn btn-primary kit-dl-btn" href="' + esc(f.url) + '" download>Download: ' + esc(f.label) + "</a>";
      });
      box.innerHTML = html;
      if (r.body.license) showLicense(r.body.license);
    })
    .catch(function () {
      message("Something went wrong preparing your download. Email the address on your receipt and we will send the files directly.");
    });
})();
