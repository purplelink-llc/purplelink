/* Showcase: a small pointer tilt on each device. Fine pointers only, and
   never when the visitor asked for reduced motion. The page works without it. */
(function () {
  var rm = window.matchMedia('(prefers-reduced-motion: reduce)');
  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  if (rm.matches || !fine.matches) return;
  document.querySelectorAll('[data-tilt]').forEach(function (stage) {
    var dev = stage.querySelector('.dev');
    if (!dev) return;
    stage.addEventListener('pointermove', function (e) {
      var r = stage.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      stage.style.setProperty('--tx', (x * 6).toFixed(2));
      stage.style.setProperty('--ty', (y * 5).toFixed(2));
    });
    stage.addEventListener('pointerleave', function () {
      stage.style.setProperty('--tx', 0);
      stage.style.setProperty('--ty', 0);
    });
  });
})();
