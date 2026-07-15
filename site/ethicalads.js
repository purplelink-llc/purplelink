/* EthicalAds loader for purplelink.llc — a privacy-respecting, no-tracking ad
 * network for technical audiences (an alternative/supplement to AdSense).
 *
 * ACTIVATE: apply at https://www.ethicalads.io/publishers/ , and once approved
 * set PUBLISHER below to your publisher id, then deploy. Until it is set this
 * file is a no-op and loads nothing external — so it is safe to ship now.
 *
 * On activation it loads EthicalAds' client and fills the first element with
 * id="ethicalads-slot" (or, if none exists, appends one at the end of <main>).
 * EthicalAds origins are already allowed in netlify.toml's CSP.
 */
(function () {
  "use strict";
  var PUBLISHER = ""; // <-- your EthicalAds publisher id to go live

  if (!PUBLISHER) return;

  function activate() {
    var slot = document.getElementById("ethicalads-slot");
    if (!slot) {
      var host = document.querySelector("main") || document.body;
      slot = document.createElement("div");
      slot.id = "ethicalads-slot";
      host.appendChild(slot);
    }
    slot.setAttribute("data-ea-publisher", PUBLISHER);
    slot.setAttribute("data-ea-type", "image");
    slot.classList.add("bordered");

    var s = document.createElement("script");
    s.async = true;
    s.src = "https://media.ethicalads.io/media/client/ethicalads.min.js";
    document.head.appendChild(s);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", activate);
  } else {
    activate();
  }
})();
