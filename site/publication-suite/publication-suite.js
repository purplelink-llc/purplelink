// Publication suite hub: the station stills have dark and -light renders; show the one
// that matches the current theme (site/theme.js sets data-theme on <html>).
(function () {
  var imgs = document.querySelectorAll('img[data-ps-themed]');
  if (!imgs.length) return;
  function apply() {
    var light = document.documentElement.getAttribute('data-theme') === 'light';
    imgs.forEach(function (img) {
      var src = img.getAttribute('src') || '';
      var want = light ? src.replace(/(-light)?\.webp$/, '-light.webp') : src.replace(/-light\.webp$/, '.webp');
      if (want !== src) img.setAttribute('src', want);
    });
  }
  apply();
  new MutationObserver(apply).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
})();
