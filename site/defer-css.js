/* Loads the stylesheets marked data-defer-css once the page has loaded.
   They are below the first screen, so first paint does not wait for them.
   Without JavaScript a <noscript> link loads them normally. */
(function () {
  function go() {
    document.querySelectorAll('link[data-defer-css]').forEach(function (l) { l.media = 'all'; });
  }
  if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
})();
