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

/* Mark the scene whose link was clicked, so its render can travel to the next
   page (see vt.css). Harmless where view transitions are not supported. */
(function () {
  function clear() {
    document.querySelectorAll('[data-vt-active]').forEach(function (n) { n.removeAttribute('data-vt-active'); });
  }
  window.addEventListener('pageshow', clear);
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.show a[href^="/"]');
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    var art = a.closest('.show').querySelector('.show-logo, .show-suite-art');
    clear();
    if (art) art.setAttribute('data-vt-active', '');
    // Exit first, then change page: the words fade away while the next page
    // downloads, so the browser's morph starts from a clean stage.
    var ok = art && window.CSS && CSS.supports('selector(:has(*))') && !matchMedia('(prefers-reduced-motion: reduce)').matches &&
      document.startViewTransition && !a.target && a.origin === location.origin;
    if (!ok) return;
    e.preventDefault();
    var href = a.href;
    document.documentElement.classList.add('vt-leaving');
    try { fetch(href, { credentials: 'same-origin' }).catch(function () {}); } catch (x) { /* warm-up only */ }
    setTimeout(function () { location.assign(href); }, 320);
  });
  window.addEventListener('pageshow', function () { document.documentElement.classList.remove('vt-leaving'); });
})();

/* Load the next page before it is clicked, so the page change is one smooth
   motion with no wait. Hover (or touch) starts it for any scene; the scene on
   screen is prepared ahead of time. Chromium only; elsewhere this does nothing.
   The page-view count waits for the visitor to arrive (see analytics.js). */
(function () {
  if (!(window.HTMLScriptElement && HTMLScriptElement.supports && HTMLScriptElement.supports('speculationrules'))) return;
  var conn = navigator.connection;
  if (conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || ''))) return;
  var links = [].slice.call(document.querySelectorAll('.show-copy a[href^="/"]'));
  if (!links.length) return;
  var all = links.map(function (a) { return a.getAttribute('href'); });
  var current = null, tag = null;
  function apply() {
    if (tag) tag.remove();
    var rules = [{ source: 'list', urls: all, eagerness: 'moderate' }];
    if (current) rules.unshift({ source: 'list', urls: [current], eagerness: 'immediate' });
    tag = document.createElement('script');
    tag.type = 'speculationrules';
    tag.textContent = JSON.stringify({ prerender: rules });
    document.head.appendChild(tag);
  }
  apply();
  if (!('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var href = en.target.getAttribute('href');
      if (href !== current) { current = href; apply(); }
    });
  }, { rootMargin: '-35% 0px -35% 0px', threshold: 0 });
  links.forEach(function (a) { io.observe(a); });
})();
