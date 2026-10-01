// /photography/license/success/ and /photography/calendars/success/: turn a
// paid Stripe session into download links (same shape as /kits/success.js,
// against photo-download.mjs).
(function () {
  var box = document.getElementById("downloads");
  if (!box) return;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function message(html) { box.innerHTML = '<p class="tool-status">' + html + "</p>"; }

  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    message("If you just completed a purchase, use the download link in your receipt email. If this looks wrong, email ben@purplelink.llc with your order id.");
    return;
  }

  fetch("/.netlify/functions/photo-download?session_id=" + encodeURIComponent(sessionId))
    .then(function (resp) { return resp.json().then(function (b) { return { ok: resp.ok, body: b }; }); })
    .then(function (r) {
      if (!r.ok || !r.body || !r.body.files || !r.body.files.length) {
        message(esc((r.body && r.body.detail) || "We could not prepare your download. Email ben@purplelink.llc with your order id and the files will be sent directly."));
        return;
      }
      var html = "";
      r.body.files.forEach(function (f) {
        html += '<a class="btn btn-primary kit-dl-btn" href="' + esc(f.url) + '" download>Download: ' + esc(f.label) + "</a>";
      });
      box.innerHTML = html;
    })
    .catch(function () {
      message("Something went wrong preparing your download. Email ben@purplelink.llc with your order id and the files will be sent directly.");
    });
})();
