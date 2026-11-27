// The /products/ storefront: a Buy button on every product sold here, and an "Add to bundle" tray for the Mac apps.
// Checkout takes one product per Stripe session, so there is no mixed cart. Each Buy link points at the product's own
// page and works without JavaScript; with it, the click goes straight to Stripe Checkout. The tray builds the same
// pick-your-own bundle as /suite/ (2 apps 25% off, 3 apps 40% off, 4 or more go to the Suite). The server prices every
// order (netlify/lib/bundles.mjs); the tables below are only for showing the price, and a test keeps them equal to the
// server's and to site/suite/bundle.js.
(function () {
  var BUNDLE_PERCENT = {"2":25,"3":40};
  var SUITE_CENTS = 9999;
  // What each part costs on its own today (Vitae Plus is its first year, as in the Suite's own price stack).
  var PART_PRICE = {"moderntex":1999,"outbound-veil":2999,"legroom":999,"keyfeel":999,"tapefolio":2999,"panely":999,"summonly":999,"nee":1499,"lenses":499,"modernpaper":4900,"vitae-plus":2399};
  var PART_NAME = {"moderntex":"ModernTex","outbound-veil":"Outbound Veil","legroom":"Legroom","keyfeel":"Keyfeel","tapefolio":"Tapefolio","panely":"Panely","summonly":"Summonly","nee":"Née","lenses":"Lenses","modernpaper":"ModernPaper","vitae-plus":"Vitae Plus"};

  var CHECKOUT_URL = "/.netlify/functions/checkout";
  var referralCode = new URLSearchParams(window.location.search).get("ref") || "";

  function money(cents) {
    return "$" + (cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // POST one checkout request; resolves with the Stripe URL or rejects with {detail}.
  function startCheckout(payload) {
    return fetch(CHECKOUT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json().then(
            function (p) { throw p; },
            function () { throw { detail: "Could not start checkout." }; }
          );
        }
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.url) throw { detail: "Checkout did not return a redirect URL." };
        return data.url;
      });
  }

  // ---- Single-product Buy buttons -------------------------------------------------------------------------------
  function statusFor(btn) {
    var box = btn.closest("[data-shop-row]");
    return box ? box.querySelector(".shop-status") : null;
  }
  function setBusy(btn, busy) {
    if (busy) {
      if (!btn.dataset.label) btn.dataset.label = btn.textContent;
      btn.textContent = "Opening checkout…";
      btn.setAttribute("aria-disabled", "true");
      btn.classList.add("is-busy");
    } else {
      if (btn.dataset.label) btn.textContent = btn.dataset.label;
      btn.removeAttribute("aria-disabled");
      btn.classList.remove("is-busy");
    }
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("a[data-buy]");
    if (!btn) return;
    // A modified click (new tab, new window) keeps the plain link to the product page.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (btn.classList.contains("is-busy")) return;
    var status = statusFor(btn);
    if (status) { status.textContent = ""; status.classList.remove("shop-error"); }
    setBusy(btn, true);
    startCheckout({ product: btn.getAttribute("data-buy"), ref: referralCode, src: "store" })
      .then(function (url) { window.location.assign(url); })
      .catch(function (err) {
        setBusy(btn, false);
        if (status) {
          status.textContent = (err && err.detail) || "Could not start checkout.";
          status.classList.add("shop-error");
        }
      });
  });

  // ---- Bundle tray -----------------------------------------------------------------------------------------------
  var tray = document.getElementById("shop-tray");
  var addButtons = Array.prototype.slice.call(document.querySelectorAll("button[data-bundle]"));
  var chosen = [];

  function bundleCents(sum, n) {
    return Math.round(sum * (100 - BUNDLE_PERCENT[String(n)]) / 100);
  }
  // The piece of the summary with the separate total struck through: [text, {s: "$49.98"}, text, ...].
  function priceLine(n, separate, price) {
    var pct = BUNDLE_PERCENT[String(n)];
    return [n + " apps: ", { s: money(separate) }, " " + money(price) + ", " + pct + "% off, you save " + money(separate - price) + "."];
  }
  function nextTierNudge(picked, separate) {
    var cheapest = null;
    Object.keys(PART_PRICE).forEach(function (slug) {
      if (picked.indexOf(slug) === -1 && (cheapest === null || PART_PRICE[slug] < PART_PRICE[cheapest])) cheapest = slug;
    });
    var now = separate - bundleCents(separate, 2);
    var then = (separate + PART_PRICE[cheapest]) - bundleCents(separate + PART_PRICE[cheapest], 3);
    return " Add a third app for " + BUNDLE_PERCENT["3"] + "% off all three. With " + PART_NAME[cheapest] + " (" + money(PART_PRICE[cheapest]) + ") your saving goes up by " + money(then - now) + ".";
  }
  function state() {
    var n = chosen.length;
    var separate = chosen.reduce(function (sum, slug) { return sum + (PART_PRICE[slug] || 0); }, 0);
    if (n === 0) return { parts: ["Choose two or three apps."], product: null, label: "Choose your apps" };
    if (n === 1) return { parts: ["Choose one more for " + BUNDLE_PERCENT["2"] + "% off both. Two apps get " + BUNDLE_PERCENT["2"] + "% off, three get " + BUNDLE_PERCENT["3"] + "% off."], product: null, label: "Choose one more" };
    if (n >= 4) {
      var tail = separate < SUITE_CENTS
        ? ", or buy these on their own for " + money(separate) + "."
        : ". Bought on their own, these would cost " + money(separate) + ".";
      return { parts: ["For four or more, the Suite has all eleven for " + money(SUITE_CENTS) + tail],
               product: "app-suite", label: "Buy the Suite, " + money(SUITE_CENTS) };
    }
    var price = bundleCents(separate, n);
    var parts = priceLine(n, separate, price);
    if (n === 2) parts.push(nextTierNudge(chosen, separate));
    return { parts: parts, product: "bundle-" + n, label: "Buy these " + n + ", " + money(price), apps: chosen.slice() };
  }

  if (tray && addButtons.length) {
    var chipList = tray.querySelector(".shop-tray-chips");
    var summary = tray.querySelector(".shop-tray-summary");
    var trayBuy = tray.querySelector(".shop-tray-buy");
    var clearBtn = tray.querySelector(".shop-tray-clear");
    var trayStatus = tray.querySelector(".shop-tray-status");
    var countEl = tray.querySelector(".shop-tray-count");

    // Keep the chat launcher above the tray while the tray is open.
    var syncHeight = function () {
      document.documentElement.style.setProperty("--shop-tray-h", tray.offsetHeight + "px");
    };
    if ("ResizeObserver" in window) new ResizeObserver(syncHeight).observe(tray);

    var renderTray = function () {
      var s = state();
      var open = chosen.length > 0;
      tray.classList.toggle("is-open", open);
      tray.setAttribute("aria-hidden", open ? "false" : "true");
      tray.inert = !open;
      document.body.classList.toggle("shop-tray-open", open);
      if (countEl) countEl.textContent = chosen.length === 1 ? "1 app" : chosen.length + " apps";

      chipList.textContent = "";
      chosen.forEach(function (slug) {
        var li = document.createElement("li");
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "shop-chip";
        chip.setAttribute("data-remove", slug);
        chip.setAttribute("aria-label", "Remove " + PART_NAME[slug] + " from the bundle");
        chip.textContent = PART_NAME[slug];
        li.appendChild(chip);
        chipList.appendChild(li);
      });

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
      trayBuy.textContent = s.label;
      trayBuy.disabled = !s.product;

      addButtons.forEach(function (b) {
        var on = chosen.indexOf(b.getAttribute("data-bundle")) !== -1;
        b.setAttribute("aria-pressed", on ? "true" : "false");
        b.textContent = on ? "In your bundle" : "Add to bundle";
      });
      syncHeight();
    };

    var toggle = function (slug) {
      if (!PART_PRICE[slug]) return;
      var i = chosen.indexOf(slug);
      if (i === -1) chosen.push(slug); else chosen.splice(i, 1);
      trayStatus.textContent = "";
      trayStatus.classList.remove("shop-error");
      renderTray();
    };

    addButtons.forEach(function (b) {
      b.addEventListener("click", function () { toggle(b.getAttribute("data-bundle")); });
    });
    chipList.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-remove]");
      if (!chip) return;
      var slug = chip.getAttribute("data-remove");
      toggle(slug);
      // Removing a chip destroys the focused button; move focus somewhere that still exists.
      var next = chipList.querySelector(".shop-chip") || trayBuy;
      if (!chosen.length) {
        var origin = document.querySelector('button[data-bundle="' + slug + '"]');
        if (origin) origin.focus();
      } else if (next) {
        next.focus();
      }
    });
    clearBtn.addEventListener("click", function () {
      var first = chosen[0];
      chosen = [];
      trayStatus.textContent = "";
      renderTray();
      var origin = first && document.querySelector('button[data-bundle="' + first + '"]');
      if (origin) origin.focus();
    });
    trayBuy.addEventListener("click", function () {
      var s = state();
      if (!s.product) return;
      trayBuy.disabled = true;
      trayStatus.classList.remove("shop-error");
      trayStatus.textContent = "Opening checkout…";
      var payload = { product: s.product, ref: referralCode, src: "store" };
      if (s.apps) payload.apps = s.apps;
      startCheckout(payload)
        .then(function (url) { window.location.assign(url); })
        .catch(function (err) {
          trayStatus.textContent = (err && err.detail) || "Could not start checkout.";
          trayStatus.classList.add("shop-error");
          renderTray();
        });
    });

    renderTray();
  }

  // Coming back from Stripe with the Back button restores the page from the cache, busy labels and all.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll("a[data-buy].is-busy"), function (b) { setBusy(b, false); });
    if (tray) {
      var b = tray.querySelector(".shop-tray-buy");
      var st = tray.querySelector(".shop-tray-status");
      if (st) st.textContent = "";
      if (b) b.disabled = chosen.length < 2;
    }
  });
})();
