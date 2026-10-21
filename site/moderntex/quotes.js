/*
 * Customer quotes scroller on /moderntex/ (section [data-quote-scroller]).
 *
 * Reveals the previous/next buttons and the "2 of 5" count, and keeps them in step with the row as the reader
 * scrolls it any way they like. It never scrolls on its own. With reduced motion the buttons jump instead of
 * gliding. Without this script the row still scrolls and snaps; only the buttons stay hidden.
 */
(function () {
  "use strict";
  var root = document.querySelector("[data-quote-scroller]");
  if (!root) return;
  var track = root.querySelector("[data-quote-track]");
  var nav = root.querySelector("[data-quote-nav]");
  var prev = root.querySelector("[data-quote-prev]");
  var next = root.querySelector("[data-quote-next]");
  var count = root.querySelector("[data-quote-count]");
  if (!track || !nav || !prev || !next || !count) return;
  var items = Array.prototype.slice.call(track.children);
  if (items.length < 2) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function current() {
    var left = track.scrollLeft, best = 0, bestGap = Infinity;
    items.forEach(function (el, i) {
      var gap = Math.abs(el.offsetLeft - track.offsetLeft - left);
      if (gap < bestGap) { bestGap = gap; best = i; }
    });
    return best;
  }
  function update() {
    // The count names the quotes fully in view: "2 of 5" on a phone, "1–3 of 5" on a wide screen.
    var left = track.scrollLeft, right = left + track.clientWidth, shown = [];
    items.forEach(function (el, i) {
      var a = el.offsetLeft - track.offsetLeft, b = a + el.offsetWidth;
      if (a >= left - 2 && b <= right + 2) shown.push(i + 1);
    });
    if (!shown.length) shown = [current() + 1];
    var first = shown[0], last = shown[shown.length - 1];
    var atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
    count.textContent = (first === last ? first : first + "\u2013" + last) + " of " + items.length;
    prev.disabled = track.scrollLeft <= 2;
    next.disabled = atEnd;
    nav.hidden = track.scrollWidth <= track.clientWidth + 2;
  }
  function go(step) {
    var i = Math.max(0, Math.min(items.length - 1, current() + step));
    track.scrollTo({ left: items[i].offsetLeft - track.offsetLeft, behavior: reduce ? "auto" : "smooth" });
  }
  prev.addEventListener("click", function () { go(-1); });
  next.addEventListener("click", function () { go(1); });
  var pending = false;
  track.addEventListener("scroll", function () {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(function () { pending = false; update(); });
  }, { passive: true });
  window.addEventListener("resize", update);
  update();
})();
