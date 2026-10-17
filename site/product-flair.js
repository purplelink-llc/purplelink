/* Scroll scenes for product pages (linked next to motion.js, deferred, no
   dependencies). Markup API, all optional:

     data-flair="steps"   a pinned scene. Inside it, [data-flair-track] is the
                          tall scroll track and each [data-step] is one step.
                          While the visitor scrolls through the track the
                          stage stays on screen and the section's
                          data-active attribute names the current step
                          (1, 2, 3...), which the stylesheet uses to move
                          the spotlight and swap the caption.

   Without this script, with reduced motion, or without IntersectionObserver
   the scene is an ordinary section: the screenshot and every step are shown
   at once. Scrolling is never intercepted; the page scrolls at its own speed
   and the stage simply stays put for a while. */
(() => {
  'use strict';
  if (!('IntersectionObserver' in window)) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scenes = [];

  document.querySelectorAll('[data-flair="steps"]').forEach((box) => {
    const track = box.querySelector('[data-flair-track]');
    const steps = [...box.querySelectorAll('[data-step]')];
    if (!track || steps.length < 2) return;

    // One invisible marker per step, stacked down the scroll distance. The
    // marker crossing the middle of the screen is the current step.
    const rail = document.createElement('div');
    rail.className = 'flair-marks';
    rail.setAttribute('aria-hidden', 'true');
    const marks = steps.map((_, i) => {
      const m = document.createElement('span');
      m.dataset.i = String(i);
      rail.appendChild(m);
      return m;
    });

    let io = null;
    const set = (i) => {
      box.dataset.active = String(i + 1);
      steps.forEach((s, j) => s.toggleAttribute('data-current', j === i));
    };
    const on = () => {
      if (io) return;
      track.appendChild(rail);
      box.classList.add('is-pinned');
      set(0);
      io = new IntersectionObserver((entries) => {
        entries.forEach((e) => { if (e.isIntersecting) set(Number(e.target.dataset.i)); });
      }, { rootMargin: '-50% 0px -50% 0px' });
      marks.forEach((m) => io.observe(m));
    };
    const off = () => {
      if (io) { io.disconnect(); io = null; }
      rail.remove();
      box.classList.remove('is-pinned');
      delete box.dataset.active;
      steps.forEach((s) => s.removeAttribute('data-current'));
    };
    scenes.push({ on, off });
  });

  if (!scenes.length) return;
  const apply = () => scenes.forEach((s) => (reduce.matches ? s.off() : s.on()));
  apply();
  reduce.addEventListener('change', apply);
  // A printout shows every step, not whichever one was on screen.
  window.addEventListener('beforeprint', () => scenes.forEach((s) => s.off()));
  window.addEventListener('afterprint', apply);
})();
