// /photography/license/ and /photography/calendars/: buy buttons and the
// photograph picker. A click on .pl-buy posts {product, photo} to the checkout
// function (analytics.js adds channel attribution to that request) and sends
// the browser to Stripe. The picker reads /photography/hub-data.json, the same
// file the hub pages are generated from, so the choice here is always one of
// the photographs that is actually on the site.
(function () {
  "use strict";
  var CHECKOUT = "/.netlify/functions/checkout";

  function statusFor(btn) {
    var p = btn.parentNode;
    while (p && p !== document.body) {
      var s = p.querySelector("[data-buy-status]");
      if (s) return s;
      p = p.parentNode;
    }
    return null;
  }

  function buy(btn) {
    var product = btn.getAttribute("data-product") || "";
    var photo = btn.getAttribute("data-photo") || document.body.getAttribute("data-photo") || "";
    var status = statusFor(btn);
    var all = document.querySelectorAll(".pl-buy");
    for (var i = 0; i < all.length; i++) all[i].disabled = true;
    if (status) status.textContent = "Opening secure checkout…";
    var body = { product: product };
    if (photo) body.photo = photo;
    fetch(CHECKOUT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (r) {
        if (r.ok && r.j && r.j.url) { window.location.href = r.j.url; return; }
        throw new Error((r.j && r.j.detail) || "Checkout could not start.");
      })
      .catch(function (e) {
        for (var i = 0; i < all.length; i++) all[i].disabled = false;
        if (status) status.textContent = String(e.message || e) + " If it keeps failing, email ben@purplelink.llc.";
      });
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest && ev.target.closest(".pl-buy");
    if (!btn || btn.disabled) return;
    ev.preventDefault();
    buy(btn);
  });

  // ---- photograph picker (license page only) ----
  var picker = document.getElementById("lic-picker");
  if (!picker) return;
  var chosen = document.getElementById("lic-chosen");
  var filters = document.getElementById("lic-filter");
  var grid = document.getElementById("lic-grid");
  var images = [], byStem = {};

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function choose(stem, push) {
    var img = byStem[stem];
    if (!img) return;
    document.body.setAttribute("data-photo", stem);
    chosen.hidden = false;
    chosen.querySelector("img").src = img.src;
    chosen.querySelector("img").alt = img.caption;
    chosen.querySelector("[data-title]").textContent = img.title;
    chosen.querySelector("[data-caption]").textContent = img.caption;
    chosen.querySelector("[data-meta]").textContent = img.place + ", " + img.country + ". File " + stem + ".jpeg, delivered clean at full resolution.";
    var links = chosen.querySelectorAll("[data-place-link]");
    for (var i = 0; i < links.length; i++) { links[i].href = img.url; links[i].textContent = img.place; }
    var btns = document.querySelectorAll(".pl-buy[data-tier]");
    for (var j = 0; j < btns.length; j++) btns[j].disabled = false;
    if (push) {
      try { history.replaceState(null, "", "?photo=" + encodeURIComponent(stem)); } catch (e) { /* ignore */ }
      chosen.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function render(country) {
    var html = "";
    for (var i = 0; i < images.length; i++) {
      var im = images[i];
      if (country && im.country !== country) continue;
      html += '<button type="button" class="lic-cell" data-stem="' + esc(im.stem) + '" aria-label="Choose ' + esc(im.title) + '">' +
        '<img src="' + esc(im.thumb) + '" alt="" width="' + im.tw + '" height="' + im.th + '" loading="lazy" decoding="async">' +
        '<span>' + esc(im.title) + "</span></button>";
    }
    grid.innerHTML = html || "<p>No photographs in this set yet.</p>";
  }

  fetch("/photography/hub-data.json")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var countries = [];
      d.countries.forEach(function (c) {
        countries.push(c.name);
        var groups = c.places.map(function (p) { return { name: p.name, url: p.url, images: p.images }; });
        groups.push({ name: c.name, url: c.url, images: c.extra || [] });
        groups.forEach(function (g) {
          g.images.forEach(function (im) {
            if (im.people || byStem[im.stem]) return;
            var rec = Object.assign({}, im, { country: c.name, place: g.name, url: g.url });
            images.push(rec); byStem[im.stem] = rec;
          });
        });
      });
      var fh = '<li><button type="button" aria-pressed="true" data-country="">All</button></li>';
      countries.forEach(function (n) { fh += '<li><button type="button" aria-pressed="false" data-country="' + esc(n) + '">' + esc(n) + "</button></li>"; });
      filters.innerHTML = fh;
      render("");
      var want = new URLSearchParams(location.search).get("photo") || "";
      if (want && byStem[want]) choose(want, false);
      else if (want) {
        var s = document.querySelector("[data-buy-status]");
        if (s) s.textContent = "That photograph is not available for a direct license; pick one below or email ben@purplelink.llc.";
      }
    })
    .catch(function () { grid.innerHTML = "<p>The picker could not load. Open any place page under /photography/ and use its License links instead.</p>"; });

  filters.addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-country]");
    if (!b) return;
    var all = filters.querySelectorAll("button");
    for (var i = 0; i < all.length; i++) all[i].setAttribute("aria-pressed", all[i] === b ? "true" : "false");
    render(b.getAttribute("data-country"));
  });
  grid.addEventListener("click", function (ev) {
    var b = ev.target.closest(".lic-cell");
    if (b) choose(b.getAttribute("data-stem"), true);
  });
})();
