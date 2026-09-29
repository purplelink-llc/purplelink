// /sheets/live/setup/ — turn a live-sheet Checkout session into feed formulas.
// GET live-sheet?session_id= tells us the product and any saved settings;
// POST saves settings and returns the feed links. Nothing is stored in the
// browser: the session id in the URL (from the email) is the whole login.
(function () {
  var FN = "/.netlify/functions/live-sheet";
  var $ = function (id) { return document.getElementById(id); };
  var sessionId = new URLSearchParams(window.location.search).get("session_id") || "";
  var status = $("setup-status");
  var product = "";

  function say(el, text, isError) {
    el.textContent = text;
    el.classList.toggle("sheet-error", !!isError);
  }

  function call(method, body) {
    var opts = { method: method, headers: { "Content-Type": "application/json" } };
    var url = FN;
    if (method === "GET") url += "?session_id=" + encodeURIComponent(sessionId);
    else opts.body = JSON.stringify(body);
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (b) { return { ok: r.ok, body: b }; });
    });
  }

  function feedRow(container, label, value) {
    var row = document.createElement("div");
    row.className = "sheet-feed";
    var name = document.createElement("span");
    name.className = "sheet-feed-name";
    name.textContent = label;
    var code = document.createElement("code");
    code.textContent = value;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn sheet-copy";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var done = function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value).then(done, function () {});
      else {
        var range = document.createRange();
        range.selectNodeContents(code);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
    });
    row.appendChild(name);
    row.appendChild(code);
    row.appendChild(btn);
    container.appendChild(row);
  }

  function showFeeds(feeds, config) {
    var sheets = $("feeds-sheets"), excel = $("feeds-excel");
    sheets.textContent = "";
    excel.textContent = "";
    feeds.forEach(function (f) {
      feedRow(sheets, f.label, '=IMPORTDATA("' + f.url + '")');
      feedRow(excel, f.label, f.url);
    });
    var who = $("feeds-who");
    if (product === "live-scholar") {
      who.textContent = "Tracking " + (config.name ? config.name + " (" + config.author + ")" : config.author) + ".";
    } else {
      who.textContent = "Tracking: " + config.keywords.join(", ") +
        (config.agencies && config.agencies.length ? " · agencies: " + config.agencies.join(", ") : " · all agencies") + ".";
    }
    $("feeds-section").hidden = false;
  }

  function fill(config) {
    if (!config) return;
    if (product === "live-scholar") $("author").value = config.author || "";
    else {
      $("keywords").value = (config.keywords || []).join("\n");
      var ticked = config.agencies || [];
      document.querySelectorAll('input[name="agency"]').forEach(function (b) { b.checked = ticked.indexOf(b.value) !== -1; });
    }
  }

  function save(form, config) {
    var msg = $("save-status");
    var btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    say(msg, "Saving…");
    call("POST", { session_id: sessionId, config: config }).then(function (r) {
      btn.disabled = false;
      if (!r.ok) { say(msg, (r.body && r.body.detail) || "That didn't save. Check the entry and try again.", true); return; }
      say(msg, "Saved. Your formulas are below.");
      showFeeds(r.body.feeds, r.body.config);
      $("feeds-section").scrollIntoView({ behavior: "smooth", block: "start" });
    }).catch(function () {
      btn.disabled = false;
      say(msg, "Something went wrong. Try again, or email ben@purplelink.llc.", true);
    });
  }

  $("form-scholar").addEventListener("submit", function (e) {
    e.preventDefault();
    save(this, { author: $("author").value.trim() });
  });
  $("form-funding").addEventListener("submit", function (e) {
    e.preventDefault();
    var agencies = [];
    document.querySelectorAll('input[name="agency"]:checked').forEach(function (b) { agencies.push(b.value); });
    save(this, { keywords: $("keywords").value, agencies: agencies });
  });
  $("manage-btn").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    say($("manage-status"), "Opening Stripe…");
    call("POST", { session_id: sessionId, action: "portal" }).then(function (r) {
      if (r.ok && r.body.url) { window.location.assign(r.body.url); return; }
      btn.disabled = false;
      say($("manage-status"), (r.body && r.body.detail) || "Could not open the billing page. Email ben@purplelink.llc.", true);
    }).catch(function () {
      btn.disabled = false;
      say($("manage-status"), "Could not open the billing page. Email ben@purplelink.llc.", true);
    });
  });

  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    say(status, "Open this page from the link in your subscription email. Lost it? Use Find a purchase at purplelink.llc/recover/.", true);
    return;
  }
  call("GET").then(function (r) {
    if (!r.ok) { say(status, (r.body && r.body.detail) || "We could not find this subscription.", true); return; }
    product = r.body.product;
    var scholar = product === "live-scholar";
    $("setup-title").textContent = scholar ? "Set up your Live Citation Dashboard" : "Set up your Live Funding Feed";
    say(status, r.body.status === "trialing" ? "Your free trial is active." : "Your subscription is active.");
    $(scholar ? "form-scholar" : "form-funding").hidden = false;
    $("manage-section").hidden = false;
    fill(r.body.config);
    if (r.body.configured) showFeeds(r.body.feeds, r.body.config);
  }).catch(function () {
    say(status, "Something went wrong loading your subscription. Reload the page, or email ben@purplelink.llc.", true);
  });
})();
