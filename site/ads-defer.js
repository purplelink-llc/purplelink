/* Loads the AdSense script after the page has settled: on the first scroll,
   key or pointer press, or 4 seconds after load, whichever comes first.
   Same script, same client id, same CSP; it just no longer competes with the
   first screen for bandwidth. */
(function () {
  var done = false;
  var SRC = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6407975157274256';
  function load() {
    if (done) return;
    done = true;
    ['scroll', 'keydown', 'pointerdown', 'touchstart'].forEach(function (t) { window.removeEventListener(t, load); });
    var s = document.createElement('script');
    s.async = true;
    s.src = SRC;
    s.crossOrigin = 'anonymous';
    document.head.appendChild(s);
  }
  ['scroll', 'keydown', 'pointerdown', 'touchstart'].forEach(function (t) { window.addEventListener(t, load, { once: true, passive: true }); });
  function arm() { setTimeout(load, 4000); }
  if (document.readyState === 'complete') arm(); else window.addEventListener('load', arm);
})();
