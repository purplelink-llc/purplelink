/* Scroll scenes for product pages (linked next to motion.js, deferred, no
   dependencies). Markup API, all optional:

     data-flair="steps"   a pinned scene. Inside it, [data-flair-track] is the
                          tall scroll track and each [data-step] is one step.
                          While the visitor scrolls through the track the
                          stage stays on screen and the step crossing the
                          middle of the screen gets data-current.

     data-spot="t r b l"  on a step, in a scene with one screenshot
                          (.flair-shot and .flair-spot): the spotlight's
                          insets, in percent of the screenshot, while that
                          step is current.

     .flair-scene--swap   a scene whose steps each carry a screenshot; the
                          current step's text and screenshot show together.

     data-flair-media     a media query the screen must match for the scene
                          to pin. Swap scenes default to screens at least
                          900px wide and 720px tall, since their captions
                          are long; other scenes to at least 560px tall.
                          Elsewhere the scene stays an ordinary section.

   The script also adds the row of progress ticks and tells the stylesheet
   how many steps there are (--flair-steps), so the scroll distance fits.

   Without this script, with reduced motion, or without IntersectionObserver
   the scene is an ordinary section: every screenshot and every step are
   shown at once. Scrolling is never intercepted; the page scrolls at its own
   speed and the stage simply stays put for a while. */
(() => {
  'use strict';
  if (!('IntersectionObserver' in window)) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scenes = [];
  const SPOT = ['--spot-t', '--spot-r', '--spot-b', '--spot-l'];

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

    const ticks = document.createElement('div');
    ticks.className = 'flair-progress';
    ticks.setAttribute('aria-hidden', 'true');
    const tickEls = steps.map(() => ticks.appendChild(document.createElement('span')));
    const list = box.querySelector('.flair-steps');

    let io = null;
    const set = (i) => {
      box.dataset.active = String(i + 1);
      steps.forEach((s, j) => s.toggleAttribute('data-current', j === i));
      tickEls.forEach((t, j) => t.toggleAttribute('data-on', j <= i));
      const spot = (steps[i].dataset.spot || '').trim().split(/\s+/);
      if (spot.length === 4) SPOT.forEach((v, k) => box.style.setProperty(v, spot[k] + '%'));
    };
    const on = () => {
      if (io) return;
      track.appendChild(rail);
      if (list) list.before(ticks);
      box.style.setProperty('--flair-steps', String(steps.length));
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
      ticks.remove();
      box.classList.remove('is-pinned');
      delete box.dataset.active;
      steps.forEach((s) => s.removeAttribute('data-current'));
    };
    const fits = window.matchMedia(box.dataset.flairMedia ||
      (box.classList.contains('flair-scene--swap')
        ? '(min-width: 900px) and (min-height: 720px)'
        : '(min-height: 560px)'));
    scenes.push({ on, off, fits });
  });

  if (!scenes.length) return;
  const apply = () => scenes.forEach((s) => (reduce.matches || !s.fits.matches ? s.off() : s.on()));
  apply();
  reduce.addEventListener('change', apply);
  scenes.forEach((s) => s.fits.addEventListener('change', apply));
  // A printout shows every step, not whichever one was on screen.
  window.addEventListener('beforeprint', () => scenes.forEach((s) => s.off()));
  window.addEventListener('afterprint', apply);
})();
