/* Motion module for the home page and product pages. Deferred, no
   dependencies, one shared IntersectionObserver for every reveal.

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
  // Armed = hidden, waiting. Shown = a one-off animation that ends on the
  // element's own styles, so hover and focus transitions are never delayed.
  const show = (el) => {
    reveal.unobserve(el);
    armed.delete(el);
    el.removeAttribute('data-motion-armed');
    el.setAttribute('data-motion-in', '');
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
    // site.js already reveals some elements; one system per element.
    if (el.closest('.will-reveal')) return;
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

  /* YouTube embed: a poster and a plain link until the box is near the
     screen, then the privacy-enhanced player, muted, so autoplay is allowed
     and no YouTube script loads for visitors who never scroll this far. */
  const youtube = (box) => {
    const id = box.dataset.youtubeId;
    if (!id) return;
    const conn = navigator.connection || {};
    if (conn.saveData) return;
    let done = false;
    const mount = () => {
      if (done) return;
      done = true;
      const f = doc.createElement('iframe');
      const q = 'autoplay=1&mute=1&loop=1&playlist=' + id + '&playsinline=1&rel=0&modestbranding=1';
      f.src = 'https://www.youtube-nocookie.com/embed/' + id + '?' + q;
      f.title = box.dataset.youtubeTitle || 'Video';
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.setAttribute('allowfullscreen', '');
      f.loading = 'lazy';
      f.referrerPolicy = 'strict-origin-when-cross-origin';
      box.appendChild(f);
      box.classList.add('is-loaded');
    };
    const near = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { mount(); near.disconnect(); }
    }, { rootMargin: '400px 0px' });
    near.observe(box);
    cleanups.push(() => near.disconnect());
  };

  doc.querySelectorAll('[data-motion]').forEach((box) => {
    const kind = box.dataset.motion;
    if (kind === 'reveal') arm(box);
    else if (kind === 'stagger') [...box.children].forEach(arm);
    else if (kind === 'rows') box.querySelectorAll('tbody > tr').forEach(arm);
    else if (kind === 'video') video(box);
    else if (kind === 'fix') fix(box);
    else if (kind === 'youtube') youtube(box);
  });

  /* Pages with no markup of their own (tools, blog, learn, legal) still get
     the same quiet reveal: the main content's own sections, figures, tables
     and code blocks below the fold. Anything taller than most of a screen is
     skipped, since it could never reach the reveal threshold. */
  if (!doc.querySelector('[data-motion]')) {
    const main = doc.querySelector('main');
    if (main) {
      const sel = 'section, figure, details, table, pre, .card, ul[class], ol[class], ' +
        'main > h2, main > div, article > h2, article > div';
      const fits = [...main.querySelectorAll(sel)].filter((el) =>
        !el.closest('form, [hidden], nav, aside') &&
        el.getBoundingClientRect().height < window.innerHeight * 0.7);
      const set = new Set(fits);
      fits.filter((el) => { // outermost only
        for (let p = el.parentElement; p && p !== main; p = p.parentElement) if (set.has(p)) return false;
        return true;
      }).forEach(arm);
    }
  }

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
