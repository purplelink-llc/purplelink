// Reddit Ads conversion pixel for ModernTex (owner decision, 2026-10-29).
// Loads Reddit's pixel only for a visitor whose first arrival was a Reddit ad click (an rdt_cid on this URL, or the
// first-touch channel "paid:reddit" from analytics.js), and never under Do Not Track. Everyone else gets nothing:
// no Reddit script, no Reddit cookie. Events: PageVisit on load, Lead on the trial download, AddToCart on a Buy
// click, Purchase on /moderntex/success/ (the Stripe session id is the conversion id, so a reload counts once).
// On the success page it also starts when the order itself was marked as from a Reddit ad (window.plRedditPurchase).
// Load it after /analytics.js, which defines window.plChannel.
(function () {
  var PIXEL_ID = "a2_jx9tsee4sm5h"; // Reddit Ads > Events Manager > Pixel ID (a2_... or t2_...). Empty: the script does nothing.
  if (!PIXEL_ID) return;
  var dnt = navigator.doNotTrack || window.doNotTrack || navigator.msDoNotTrack;
  if (dnt === "1" || dnt === "yes") return;

  var q = new URLSearchParams(location.search);
  var fromAd = !!q.get("rdt_cid");
  try { fromAd = fromAd || (typeof window.plChannel === "function" && window.plChannel() === "paid:reddit"); } catch (e) {}
  var onSuccess = location.pathname.indexOf("/moderntex/success") === 0;
  var started = false;

  function start() {
    if (started) return;
    started = true;
    // Reddit's standard loader: queue calls until pixel.js arrives.
    var rdt = window.rdt = window.rdt || function () {
      rdt.sendEvent ? rdt.sendEvent.apply(rdt, arguments) : rdt.callQueue.push(arguments);
    };
    rdt.callQueue = rdt.callQueue || [];
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.redditstatic.com/ads/pixel.js";
    document.head.appendChild(s);

    rdt("init", PIXEL_ID);
    rdt("track", "PageVisit");

    if (onSuccess) {
      var sid = q.get("session_id") || "";
      var purchase = { currency: "USD", value: 19.99, itemCount: 1 };
      if (sid) purchase.conversionId = sid.slice(0, 120);
      rdt("track", "Purchase", purchase);
    }

    document.addEventListener("click", function (ev) {
      var el = ev.target && ev.target.closest ? ev.target.closest("a, button") : null;
      if (!el) return;
      var href = el.getAttribute("href") || "";
      if (href.indexOf("moderntex-download?trial=1") !== -1) rdt("track", "Lead");
      else if (el.getAttribute("data-product") === "moderntex") rdt("track", "AddToCart", { currency: "USD", value: 19.99, itemCount: 1 });
    }, true);
  }

  if (fromAd) { start(); return; }
  // A buyer whose browser forgot the ad click (the first-party pl_attr cookie is HttpOnly, so the page cannot read it):
  // the success page learns reddit_ad from the order itself and calls window.plRedditPurchase(). Either order works.
  if (onSuccess) {
    window.plRedditPurchase = start;
    if (window.plRedditAd === true) start();
  }
})();
