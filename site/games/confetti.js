/* A short burst of confetti for a win. Does nothing when the visitor prefers reduced motion. Load on pages that call it. */
(function () {
  "use strict";
  function reduced() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return true; } }
  function burst(n) {
    if (reduced()) return;
    var box = document.createElement("div");
    box.className = "pl-confetti";
    box.setAttribute("aria-hidden", "true");
    for (var i = 0; i < n; i++) box.appendChild(document.createElement("i"));
    document.body.appendChild(box);
    window.setTimeout(function () { if (box.parentNode) box.parentNode.removeChild(box); }, 1800);
  }
  window.PLConfetti = { small: function () { burst(10); }, big: function () { burst(28); } };
})();
