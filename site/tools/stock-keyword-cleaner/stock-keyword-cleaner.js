/* Stock Photo Keyword Cleaner page. Keywords are cleaned by StockKeywords (stock-keyword-cleaner-core.js) in the
   page. Nothing you paste is sent anywhere; the only request this page makes is the optional notify-me form, which
   sends just the fields in that form. Pasted text is untrusted, so it is only ever written with textContent or a
   textarea value. */
(function () {
  "use strict";
  var SK = window.StockKeywords;
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  var SAMPLE = "Hyde Park, London, England, travel, Serpentine lake, autumn, Hyde Park, rowing boats, tourism, " +
    "Café terrace, nature, outdoors, Kensington Gardens, Westminster, UK, uk, people walking, fallen leaves, " +
    "Royal Park, lifestyle, landmark, city park, Speakers’ Corner, golden hour";

  var input = $("sk-input"), dropGeneric = $("sk-generic"), status = $("sk-status");
  var summary = $("sk-summary"), cleaned = $("sk-cleaned"), cards = $("sk-cards"), results = $("sk-results");
  var used = false, timer = 0;

  function copyButton(getText, label) {
    var b = el("button", "btn btn-ghost sk-small", label || "Copy");
    b.type = "button";
    b.addEventListener("click", function () {
      var text = getText();
      var done = function () { b.textContent = "Copied"; setTimeout(function () { b.textContent = label || "Copy"; }, 1500); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
    });
    return b;
  }

  function note(parent, text) { parent.appendChild(el("p", "sk-note", text)); }

  function card(res) {
    var a = res.agency;
    var c = el("section", "sk-card");
    c.setAttribute("aria-label", a.name);
    var head = el("div", "sk-card-head");
    head.appendChild(el("h3", null, a.name));
    var limit = a.max ? res.keywords.length + " of " + a.max : res.keywords.length + " keywords";
    var count = el("span", "sk-count" + (res.cut.length || res.under ? " is-warn" : ""), limit);
    head.appendChild(count);
    c.appendChild(head);

    var list = el("ol", "sk-kw");
    res.keywords.forEach(function (k, i) {
      var li = el("li", a.first && i < a.first ? "is-first" : null, k);
      list.appendChild(li);
    });
    c.appendChild(list);
    if (a.first && res.keywords.length) note(c, "The first " + Math.min(a.first, res.keywords.length) + " (marked) " + a.firstLabel + ". Put the main subject first.");
    if (res.cut.length) note(c, "Cut to " + a.max + ": " + plural(res.cut.length, "keyword", "keywords") + " left out from the end (" + res.cut.join(", ") + ").");
    if (res.under) note(c, a.name + " needs at least " + a.min + " keywords. Add " + res.under + " more.");
    if (res.changed.length) note(c, "Changed to letters, digits and spaces: " + res.changed.map(function (x) { return x.from + " → " + (x.to || "(removed)"); }).join("; ") + ".");
    if (res.merged.length) note(c, "Became duplicates after that change and were merged: " + res.merged.join(", ") + ".");
    if (a.caption) note(c, "Dreamstime's rule is about editorial captions, not keywords. Build the caption below.");
    var row = el("div", "sk-actions");
    row.appendChild(copyButton(function () { return res.keywords.join(", "); }, "Copy for " + a.name));
    c.appendChild(row);
    return c;
  }

  function render() {
    var text = input.value;
    var r = SK.clean(text, { dropGeneric: dropGeneric.checked });
    cards.textContent = "";
    cleaned.textContent = "";
    if (!r.input) {
      results.hidden = true;
      status.textContent = "";
      return;
    }
    results.hidden = false;
    var parts = [plural(r.input, "keyword", "keywords") + " in", plural(r.keywords.length, "keyword", "keywords") + " out"];
    if (r.duplicates.length) parts.push(plural(r.duplicates.length, "duplicate", "duplicates") + " removed");
    if (r.generic.length) parts.push(plural(r.generic.length, "generic word", "generic words") + " removed");
    status.textContent = parts.join(", ") + ".";
    summary.textContent = "";
    if (r.duplicates.length) note(summary, "Duplicates (after lowercasing): " + r.duplicates.join(", ") + ".");
    if (r.generic.length) note(summary, "Generic words removed: " + r.generic.join(", ") + ".");
    cleaned.value = r.keywords.join(", ");
    SK.AGENCIES.forEach(function (a) { cards.appendChild(card(SK.forAgency(r.keywords, a.id))); });
    if (!used) {
      used = true;
      if (window.plTrack) window.plTrack("tool_use", "stock-keyword-cleaner");
    }
  }

  function schedule() { clearTimeout(timer); timer = setTimeout(render, 200); }
  input.addEventListener("input", schedule);
  dropGeneric.addEventListener("change", render);
  $("sk-sample").addEventListener("click", function () { input.value = SAMPLE; render(); input.focus(); });
  $("sk-clear").addEventListener("click", function () { input.value = ""; render(); input.focus(); });
  $("sk-copy-clean").appendChild(copyButton(function () { return cleaned.value; }, "Copy cleaned keywords"));

  // Editorial caption for Dreamstime.
  var month = $("sk-month"), year = $("sk-year");
  SK.MONTHS.forEach(function (m, i) {
    var o = el("option", null, m);
    o.value = String(i + 1);
    month.appendChild(o);
  });
  var now = new Date();
  month.value = String(now.getMonth() + 1);
  year.value = String(now.getFullYear());
  var capOut = $("sk-cap-out");
  function caption() {
    var prefix = SK.captionPrefix({ city: $("sk-city").value, country: $("sk-country").value, day: $("sk-day").value, month: month.value, year: year.value });
    var text = SK.editorialCaption(prefix, $("sk-cap").value);
    capOut.value = prefix ? text : "";
    $("sk-cap-note").textContent = prefix ? "" : "Fill in the place and a four-digit year to build the prefix.";
  }
  ["sk-city", "sk-country", "sk-day", "sk-month", "sk-year", "sk-cap"].forEach(function (id) { $(id).addEventListener("input", caption); });
  $("sk-cap-copy").appendChild(copyButton(function () { return capOut.value; }, "Copy caption"));
  caption();

  // Notify me: post to Netlify Forms without leaving the page. Without JavaScript the form posts normally.
  var form = $("sk-notify");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var msg = $("sk-notify-status");
    if (window.plTrack) window.plTrack("notify_click", "stockroom");
    var body = new URLSearchParams(new FormData(form)).toString();
    msg.textContent = "Sending";
    fetch("/", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body })
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        form.reset();
        msg.textContent = "Thanks. You will get one email when the Mac app ships, and nothing else.";
      })
      .catch(function () { msg.textContent = "That did not go through. Try again, or email ben@purplelink.llc."; });
  });
})();
