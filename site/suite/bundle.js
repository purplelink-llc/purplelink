// Pick-your-own bundles on /suite/: any 2 for one price, any 3 for one price, whichever parts are chosen. The server
// prices the order from the count alone (netlify/lib/bundles.mjs); this table is only for showing the price, and a test
// keeps it equal to the server's. Four or more parts cost more than the whole Suite, so that case offers the Suite.
(function () {
  var BUNDLE_PRICING = {"2":3499,"3":4499,"suite":5999};
  // What each part costs on its own today (Vitae Plus is its first year, as in the Suite's own price stack).
  var PART_PRICE = {"moderntex":1999,"outbound-veil":2999,"legroom":999,"keyfeel":999,"tapefolio":2999,"panely":999,"summonly":999,"vitae-plus":2399};

  var form = document.getElementById("bundle-form");
  if (!form) return;
  var summary = document.getElementById("bundle-summary");
  var buy = document.getElementById("bundle-buy");
  var statusEl = document.getElementById("bundle-status");
  var referralCode = new URLSearchParams(window.location.search).get("ref") || "";

  function money(cents) {
    return "$" + (cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function picks() {
    return Array.prototype.map.call(form.querySelectorAll('input[name="apps"]:checked'), function (i) { return i.value; });
  }
  function setStatus(msg, isError) {
    statusEl.textContent = msg;
    statusEl.classList.toggle("bundle-error", Boolean(isError));
  }
  function state() {
    var chosen = picks();
    var n = chosen.length;
    var separate = chosen.reduce(function (sum, slug) { return sum + (PART_PRICE[slug] || 0); }, 0);
    if (n === 0) return { text: "Choose two or three parts.", product: null, label: "Choose your parts" };
    if (n === 1) return { text: "Choose one more. A single app is cheaper on its own, from its own page.", product: null, label: "Choose one more" };
    if (n >= 4) {
      return { text: "Four or more cost more than the Suite, which has all eight for " + money(BUNDLE_PRICING.suite) + ". The Suite is the better buy.",
               product: "app-suite", label: "Buy the Suite, " + money(BUNDLE_PRICING.suite) };
    }
    var price = BUNDLE_PRICING[String(n)];
    if (separate <= price) {
      return { text: "Bought separately, these " + n + " cost " + money(separate) + ", which is less than the " + money(price) + " bundle. Buy them on their own, or pick different parts.",
               product: null, label: "Choose different parts" };
    }
    return { text: n + " parts for " + money(price) + ". Bought separately: " + money(separate) + ", so you save " + money(separate - price) + ".",
             product: "bundle-" + n, label: "Buy these " + n + ", " + money(price), apps: chosen };
  }
  function refresh() {
    var s = state();
    summary.textContent = s.text;
    buy.textContent = s.label;
    buy.disabled = !s.product;
  }

  form.addEventListener("change", refresh);
  buy.addEventListener("click", function () {
    var s = state();
    if (!s.product) return;
    buy.disabled = true;
    setStatus("Opening checkout…", false);
    var payload = { product: s.product, ref: referralCode };
    if (s.apps) payload.apps = s.apps;
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.url) throw { detail: "Checkout did not return a redirect URL." };
        window.location.assign(data.url);
      })
      .catch(function (err) {
        setStatus((err && err.detail) || "Could not start checkout.", true);
        refresh();
      });
  });

  refresh();
})();
