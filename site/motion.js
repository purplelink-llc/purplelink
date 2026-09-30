/* Motion module. Deferred, no dependencies, safe to include on any page.

   Markup API (all optional; content is fully visible without this script):
     data-motion="reveal"   the element eases in when scrolled to
     data-motion="stagger"  each child eases in, delayed by its place in the batch
     data-motion="rows"     table body rows ease in and take a brief highlight
     data-motion="video"    hero media: <video> plays only near and on screen
     data-motion="fix"      error-to-fix demo; plays once, [data-motion-replay] replays

   The module does nothing when the visitor asks for reduced motion or the
   browser lacks IntersectionObserver, and it switches off if that
   preference changes while the page is open. */
(() => {
  'use strict';
  const doc = document;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduce.matches || !('IntersectionObserver' in window)) return;

  const armed = new Set();
  const cleanups = [];
  const finishers = []; // demos that must show their end state if nobody scrolls

  /* Reveal ------------------------------------------------------------ */
  const show = (el) => {
    reveal.unobserve(el);
    armed.delete(el);
    el.removeAttribute('data-motion-armed');
    if (el.tagName === 'TR') el.setAttribute('data-motion-flash', '');
  };

  const reveal = new IntersectionObserver((entries) => {
    let n = 0;
    entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => (a.target.compareDocumentPosition(b.target) & 4 ? -1 : 1))
      .forEach((e) => {
        if (n > 0) e.target.dataset.motionI = String(Math.min(n, 5));
        n += 1;
        show(e.target);
      });
  }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });

  const arm = (el) => {
    // Already on screen at load: leave it alone so nothing flashes.
    if (el.getBoundingClientRect().top < window.innerHeight * 0.9) return;
    el.setAttribute('data-motion-armed', '');
    armed.add(el);
    reveal.observe(el);
  };

  /* Hero video -------------------------------------------------------- */
  const video = (box) => {
    const v = box.querySelector('video');
    const btn = box.querySelector('[data-motion-toggle]');
    const conn = navigator.connection || {};
    if (!v || conn.saveData || /(^|-)2g$/.test(conn.effectiveType || '')) return;

    let loaded = false;
    let onScreen = false;
    let userPaused = false;

    const load = () => {
      if (loaded) return;
      loaded = true;
      v.querySelectorAll('source[data-src]').forEach((s) => { s.src = s.dataset.src; });
      v.load();
    };
    const sync = () => {
      if (onScreen && !userPaused && !doc.hidden) {
        load();
        const p = v.play();
        if (p && p.catch) p.catch(() => {});
      } else if (loaded) {
        v.pause();
      }
    };

    // The files may not exist yet: the overlay only appears once frames play.
    v.addEventListener('playing', () => {
      box.classList.add('is-playing');
      if (btn) btn.hidden = false;
    });

    if (btn) {
      btn.addEventListener('click', () => {
        userPaused = !userPaused;
        btn.textContent = userPaused ? 'Play video' : 'Pause video';
        sync();
      });
    }

    const near = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { load(); near.disconnect(); }
    }, { rootMargin: '300px 0px' });
    const inView = new IntersectionObserver((es) => {
      onScreen = es[es.length - 1].isIntersecting;
      sync();
    });
    near.observe(box);
    inView.observe(box);
    doc.addEventListener('visibilitychange', sync);
    cleanups.push(() => {
      near.disconnect();
      inView.disconnect();
      doc.removeEventListener('visibilitychange', sync);
      v.pause();
      box.classList.remove('is-playing');
    });
  };

  /* Error to fix ------------------------------------------------------ */
  const fix = (box) => {
    const btn = box.querySelector('[data-motion-replay]');
    const play = () => {
      box.classList.remove('is-playing');
      void box.offsetWidth; // restart the CSS animations
      box.classList.add('is-playing');
    };
    box.classList.add('is-armed');
    if (btn) { btn.hidden = false; btn.addEventListener('click', play); }
    const once = new IntersectionObserver((es) => {
      if (!es.some((e) => e.isIntersecting)) return;
      once.disconnect();
      play();
    }, { threshold: 0.4 });
    once.observe(box);
    const stop = () => {
      once.disconnect();
      box.classList.remove('is-armed', 'is-playing');
      if (btn) btn.hidden = true;
    };
    cleanups.push(stop);
    finishers.push(stop);
  };

  doc.querySelectorAll('[data-motion]').forEach((box) => {
    const kind = box.dataset.motion;
    if (kind === 'reveal') arm(box);
    else if (kind === 'stagger') [...box.children].forEach(arm);
    else if (kind === 'rows') box.querySelectorAll('tbody > tr').forEach(arm);
    else if (kind === 'video') video(box);
    else if (kind === 'fix') fix(box);
  });

  const revealAll = () => {
    [...armed].forEach(show);
    finishers.forEach((fn) => fn());
  };
  // A hidden tab or a print pass never scrolls: show everything.
  doc.addEventListener('visibilitychange', () => { if (doc.hidden) revealAll(); });
  window.addEventListener('beforeprint', revealAll);
  if (doc.hidden) revealAll();

  reduce.addEventListener('change', () => {
    if (!reduce.matches) return;
    revealAll();
    reveal.disconnect();
    cleanups.forEach((fn) => fn());
  });
})();
