// Photography page: the slideshow and the scroll reveals. Without this script
// the first photograph and every link still work; nothing here gates content.
(() => {
  const SLIDE_MS = 7000;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  const stage = document.querySelector('[data-stage]');
  if (stage) {
    const frame = stage.querySelector('.stage-frame');
    const slides = [...stage.querySelectorAll('.stage-slide')];
    const thumbs = [...stage.querySelectorAll('.stage-thumb')];
    const place = stage.querySelector('[data-place]');
    const count = stage.querySelector('[data-count]');
    const caption = stage.querySelector('.stage-caption');
    const toggle = stage.querySelector('[data-toggle]');
    const total = slides.length;

    let index = 0;
    let timer = null;
    let captionTimer = 0;
    const strip = thumbs.length ? thumbs[0].closest('.stage-thumbs') : null;
    let userPaused = reduced.matches;   // motion-sensitive visitors start paused
    let hovering = false;

    // Focal point per photograph: keeps the subject in frame when the stage
    // crops to a different shape than the photograph.
    slides.forEach((slide) => {
      const img = slide.querySelector('img');
      const [x, y] = (img.dataset.focus || '50 50').split(' ');
      img.style.objectPosition = `${x}% ${y}%`;
      img.style.transformOrigin = `${x}% ${y}%`;
    });

    const load = (i) => {
      const img = slides[(i + total) % total].querySelector('img');
      if (img.dataset.src) {
        img.src = img.dataset.src;
        delete img.dataset.src;
      }
    };

    const playing = () => !userPaused && !hovering && document.visibilityState === 'visible';

    const schedule = () => {
      clearTimeout(timer);
      stage.dataset.playing = playing() ? 'true' : 'false';
      if (playing()) timer = setTimeout(() => go(index + 1), SLIDE_MS);
    };

    const go = (to, manual = false) => {
      const next = (to + total) % total;
      if (next === index && slides[index].classList.contains('is-active')) {
        schedule();
        return;
      }
      load(next);
      load(next + 1);
      slides[index].classList.remove('is-active');
      thumbs[index].classList.remove('is-active');
      thumbs[index].removeAttribute('aria-current');
      index = next;
      slides[index].classList.add('is-active');
      thumbs[index].classList.add('is-active');
      thumbs[index].setAttribute('aria-current', 'true');
      count.textContent = `${index + 1} / ${total}`;
      place.classList.add('is-swapping');
      // One pending caption swap at a time, so quick next/prev clicks do not flicker through old names.
      clearTimeout(captionTimer);
      captionTimer = setTimeout(() => {
        place.textContent = slides[index].dataset.caption;
        place.classList.remove('is-swapping');
      }, 220);
      // Bring the active thumbnail into view by scrolling the strip only. scrollIntoView could also scroll the
      // page, which auto-advance did every seven seconds to someone reading further down.
      if (strip) {
        const t = thumbs[index];
        const left = t.offsetLeft - (strip.clientWidth - t.offsetWidth) / 2;
        strip.scrollTo({ left: Math.max(0, left), behavior: manual && !reduced.matches ? 'smooth' : 'auto' });
      }
      schedule();
    };

    const setPaused = (paused) => {
      userPaused = paused;
      toggle.setAttribute('aria-pressed', String(paused));
      toggle.setAttribute('aria-label', paused ? 'Play slideshow' : 'Pause slideshow');
      // Announce slide changes only when the visitor is driving them.
      caption.setAttribute('aria-live', paused ? 'polite' : 'off');
      schedule();
    };

    stage.querySelector('[data-next]').addEventListener('click', () => go(index + 1, true));
    stage.querySelector('[data-prev]').addEventListener('click', () => go(index - 1, true));
    toggle.addEventListener('click', () => setPaused(!userPaused));
    thumbs.forEach((t) => t.addEventListener('click', () => go(Number(t.dataset.index), true)));

    frame.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { e.preventDefault(); go(index + 1, true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); go(index - 1, true); }
      else if (e.key === 'Home') { e.preventDefault(); go(0, true); }
      else if (e.key === 'End') { e.preventDefault(); go(total - 1, true); }
    });

    // Swipe on touch. The photograph follows the finger (at half the distance, so it reads as a pull, not a
    // carousel), the direction is decided after 10px so vertical scrolling is never hijacked, and release
    // commits on a fast flick or a long enough drag, in the direction the finger was last moving.
    let drag = null;
    frame.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse') return;
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY, dx: 0, axis: null, hist: [[e.timeStamp, e.clientX]] };
    });
    frame.addEventListener('pointermove', (e) => {
      if (!drag || e.pointerId !== drag.id) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      if (!drag.axis) {
        if (Math.hypot(dx, dy) < 10) return;
        drag.axis = Math.abs(dx) > Math.abs(dy) * 1.2 ? 'x' : 'y';
        if (drag.axis === 'y') { drag = null; return; }
        try { frame.setPointerCapture(e.pointerId); } catch (err) { /* pointer already gone */ }
        slides[index].classList.add('is-dragging');
      }
      drag.dx = dx;
      drag.hist.push([e.timeStamp, e.clientX]);
      if (drag.hist.length > 5) drag.hist.shift();
      if (!reduced.matches) slides[index].style.translate = `${dx * 0.5}px 0`;
    });
    const endDrag = (cancelled) => {
      if (!drag) return;
      const d = drag;
      drag = null;
      slides[index].classList.remove('is-dragging');
      slides[index].style.translate = '';
      if (cancelled || d.axis !== 'x') return;
      const [t0, x0] = d.hist[0];
      const [t1, x1] = d.hist[d.hist.length - 1];
      const v = t1 > t0 ? (x1 - x0) / (t1 - t0) : 0;   // px per ms
      const flick = Math.abs(v) > 0.35;
      if (flick || Math.abs(d.dx) > 60) go(index + ((flick ? v : d.dx) < 0 ? 1 : -1), true);
    };
    frame.addEventListener('pointerup', () => endDrag(false));
    frame.addEventListener('pointercancel', () => endDrag(true));

    // Hold still while someone is looking at a photograph or using a control.
    ['mouseenter', 'focusin'].forEach((ev) => stage.addEventListener(ev, () => { hovering = true; schedule(); }));
    ['mouseleave', 'focusout'].forEach((ev) => stage.addEventListener(ev, (e) => {
      if (ev === 'focusout' && stage.contains(e.relatedTarget)) return;
      hovering = false;
      schedule();
    }));
    document.addEventListener('visibilitychange', schedule);
    reduced.addEventListener('change', () => setPaused(reduced.matches));

    load(1);
    setPaused(userPaused);
  }

  // Scroll reveals for the sections below the stage, with the same fail-safe
  // the rest of the site uses: anything still hidden after a moment is shown.
  if (!reduced.matches && 'IntersectionObserver' in window) {
    const targets = [...document.querySelectorAll('[data-reveal]')].filter(
      (el) => el.getBoundingClientRect().top > window.innerHeight * 0.85
    );
    const io = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }),
      { threshold: 0.08, rootMargin: '0px 0px -28px 0px' }
    );
    targets.forEach((el, i) => {
      el.classList.add('will-reveal');
      el.style.transitionDelay = `${Math.min((i % 3) * 0.04, 0.12)}s`;
      io.observe(el);
    });
    const showRest = () => targets.forEach((el) => { el.classList.add('is-visible'); io.unobserve(el); });
    setTimeout(showRest, 2500);
    if (document.visibilityState === 'hidden') showRest();
  }
})();
