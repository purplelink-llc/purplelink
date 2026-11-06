// Pick-your-own bundles on /suite/: any 2 parts for 25% off their combined price, any 3 for 40% off, whichever parts
// are chosen. The server prices the order from the chosen parts and the tier (netlify/lib/bundles.mjs); these tables
// are only for showing the price, and a test keeps them equal to the server's. Four or more parts are sent to the
// whole Suite, said plainly: a few cheap apps can cost less on their own than the Suite does.
(function () {
  var BUNDLE_PERCENT = {"2":25,"3":40};
  var SUITE_CENTS = 5999;
  // What each part costs on its own today (Vitae Plus is its first year, as in the Suite's own price stack).
  var PART_PRICE = {"moderntex":1999,"outbound-veil":2999,"legroom":999,"keyfeel":999,"tapefolio":2999,"panely":999,"summonly":999,"nee":1499,"lenses":499,"vitae-plus":2399};
  var PART_NAME = {"moderntex":"ModernTex","outbound-veil":"Outbound Veil","legroom":"Legroom","keyfeel":"Keyfeel","tapefolio":"Tapefolio","panely":"Panely","summonly":"Summonly","nee":"Née","lenses":"Lenses","vitae-plus":"Vitae Plus"};

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
  function bundleCents(sum, n) {
    return Math.round(sum * (100 - BUNDLE_PERCENT[String(n)]) / 100);
  }
  // The piece of the summary with the separate total struck through: [text, {s: "$49.98"}, text, ...].
  function priceLine(n, separate, price) {
    var pct = BUNDLE_PERCENT[String(n)];
    return [n + " apps: ", { s: money(separate) }, " " + money(price) + ", " + pct + "% off, you save " + money(separate - price) + "."];
  }
  function nextTierNudge(chosen, separate) {
    var cheapest = null;
    Object.keys(PART_PRICE).forEach(function (slug) {
      if (chosen.indexOf(slug) === -1 && (cheapest === null || PART_PRICE[slug] < PART_PRICE[cheapest])) cheapest = slug;
    });
    var now = separate - bundleCents(separate, 2);
    var then = (separate + PART_PRICE[cheapest]) - bundleCents(separate + PART_PRICE[cheapest], 3);
    return " Add a third app for " + BUNDLE_PERCENT["3"] + "% off all three. With " + PART_NAME[cheapest] + " (" + money(PART_PRICE[cheapest]) + ") your saving goes up by " + money(then - now) + ".";
  }
  function state() {
    var chosen = picks();
    var n = chosen.length;
    var separate = chosen.reduce(function (sum, slug) { return sum + (PART_PRICE[slug] || 0); }, 0);
    if (n === 0) return { parts: ["Choose two or three parts."], product: null, label: "Choose your parts" };
    if (n === 1) return { parts: ["Choose one more for " + BUNDLE_PERCENT["2"] + "% off both. Two apps get " + BUNDLE_PERCENT["2"] + "% off, three get " + BUNDLE_PERCENT["3"] + "% off."], product: null, label: "Choose one more" };
    if (n >= 4) {
      var tail = separate < SUITE_CENTS
        ? ", or buy these on their own for " + money(separate) + "."
        : ". Bought on their own, these would cost " + money(separate) + ".";
      return { parts: ["For four or more, the Suite has all ten for " + money(SUITE_CENTS) + tail],
               product: "app-suite", label: "Buy the Suite, " + money(SUITE_CENTS) };
    }
    var price = bundleCents(separate, n);
    var parts = priceLine(n, separate, price);
    if (n === 2) parts.push(nextTierNudge(chosen, separate));
    return { parts: parts, product: "bundle-" + n, label: "Buy these " + n + ", " + money(price), apps: chosen };
  }
  function refresh() {
    var s = state();
    summary.textContent = "";
    s.parts.forEach(function (piece) {
      if (typeof piece === "string") {
        summary.appendChild(document.createTextNode(piece));
      } else {
        var el = document.createElement("s");
        el.textContent = piece.s;
        summary.appendChild(el);
      }
    });
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
