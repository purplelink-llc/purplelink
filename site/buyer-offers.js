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
    const a = document.createElement("a");
    a.className = "btn btn-ghost";
    a.href = `/products/?code=${encodeURIComponent(o.code)}`;
    a.textContent = "See the products";
    section.append(h, p, a);
    const slot = document.querySelector("[data-buyer-offer]");
    if (slot) slot.append(section); else main.append(section);
  };

  const ask = (n) => {
    fetch(`/.netlify/functions/buyer-offers?session_id=${encodeURIComponent(sessionId)}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((o) => {
        if (o && o.code) show(o);
        else if (o && o.pending && n < waits.length) setTimeout(() => ask(n + 1), waits[n]);
      })
      .catch(() => { /* the purchase email carries the code */ });
  };
  ask(0);
})();
