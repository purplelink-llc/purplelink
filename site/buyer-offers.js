// Success pages: the buyer's cross-sell code (netlify/lib/buyer-codes.mjs). After a paid order the webhook makes
// one code, 30% off one other Purplelink product, once, for 30 days. This shows it under the order and remembers it
// in this browser, so a product page applies it at checkout (site.js). The webhook can lag the redirect by a few
// seconds, so the page asks a few times and then stops quietly; the code is in the purchase email either way.
(() => {
  const sessionId = new URLSearchParams(location.search).get("session_id") || "";
  if (!/^cs_(live|test)_[A-Za-z0-9]{10,200}$/.test(sessionId)) return;
  const main = document.querySelector("main");
  if (!main) return;
  const waits = [1500, 3000, 6000, 12000];

  const show = (o) => {
    try {
      localStorage.setItem("pl_buyer_code", JSON.stringify({ code: o.code, expires: o.expires }));
    } catch (e) { /* storage blocked: the link below still carries the code */ }
    const section = document.createElement("section");
    section.className = "buyer-offer";
    section.setAttribute("aria-labelledby", "buyer-offer-heading");
    const h = document.createElement("h2");
    h.id = "buyer-offer-heading";
    h.className = "tools-section-heading";
    h.textContent = `${o.percent}% off one more product`;
    const p = document.createElement("p");
    p.append("Your code ");
    const code = document.createElement("strong");
    code.className = "buyer-offer-code";
    code.textContent = o.code;
    p.append(code, ` takes ${o.percent}% off one other Purplelink product, once, until ${o.expires_text}. ` +
      "It is applied at checkout from this browser or from the link in your purchase email. " +
      "It does not work on bundles or subscriptions.");
    section.append(h, p);
    // Up to two hand-picked products (netlify/lib/upsell.mjs), with the real price and the price with the code.
    const picks = Array.isArray(o.suggestions) ? o.suggestions.filter((s) =>
      s && typeof s.name === "string" && /^\/[a-z0-9\-/]+\/$/.test(s.path || "") &&
      /^\$\d+\.\d{2}$/.test(s.price || "") && /^\$\d+\.\d{2}$/.test(s.price_with_code || "")).slice(0, 2) : [];
    if (picks.length) {
      const list = document.createElement("ul");
      list.className = "buyer-offer-picks";
      for (const s of picks) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = `${s.path}?code=${encodeURIComponent(o.code)}`;
        link.textContent = s.name;
        link.addEventListener("click", () => {
          if (typeof window.plTrack === "function") window.plTrack("upsell_click", String(s.product || ""));
        });
        const price = document.createElement("span");
        price.className = "buyer-offer-price";
        price.textContent = `${s.price_with_code} with your code (normally ${s.price})`;
        li.append(link, " ", price);
        list.append(li);
      }
      section.append(list);
    }
    const a = document.createElement("a");
    a.className = "btn btn-ghost";
    a.href = `/products/?code=${encodeURIComponent(o.code)}`;
    a.textContent = picks.length ? "See all products" : "See the products";
    section.append(a);
    const slot = document.querySelector("[data-buyer-offer]");
    if (slot) slot.append(section); else main.append(section);
  };

  // The buyer's own referral link (netlify/lib/referrals.mjs). Shown once, under the code if there is one.
  let referralShown = false;
  const showReferral = (url) => {
    if (referralShown || typeof url !== "string" || !/^https:\/\/purplelink\.llc\/\?ref=[0-9a-f]{10}$/.test(url)) return;
    referralShown = true;
    const section = document.createElement("section");
    section.className = "buyer-offer";
    section.setAttribute("aria-labelledby", "buyer-referral-heading");
    const h = document.createElement("h2");
    h.id = "buyer-referral-heading";
    h.className = "tools-section-heading";
    h.textContent = "Your referral link";
    const p = document.createElement("p");
    p.textContent = "A friend who makes their first Purplelink purchase through this link gets 20% off. " +
      "Two weeks after their order you get a free Standard Paper Review by email. The same link is in your purchase email.";
    const line = document.createElement("p");
    const code = document.createElement("code");
    code.className = "buyer-offer-code";
    code.textContent = url;
    line.append(code);
    section.append(h, p, line);
    if (navigator.clipboard && window.isSecureContext) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn-ghost";
      b.textContent = "Copy link";
      b.addEventListener("click", () => {
        navigator.clipboard.writeText(url).then(() => { b.textContent = "Copied"; }).catch(() => {});
      });
      section.append(b);
    }
    const slot = document.querySelector("[data-buyer-offer]");
    if (slot) slot.append(section); else main.append(section);
  };

  const ask = (n) => {
    fetch(`/.netlify/functions/buyer-offers?session_id=${encodeURIComponent(sessionId)}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((o) => {
        if (o && o.code) show(o);
        if (o) showReferral(o.referral_link);
        if (o && o.pending && n < waits.length) setTimeout(() => ask(n + 1), waits[n]);
      })
      .catch(() => { /* the purchase email carries the code */ });
  };
  ask(0);
})();
