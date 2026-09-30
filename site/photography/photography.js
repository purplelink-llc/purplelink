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
      setTimeout(() => {
        place.textContent = slides[index].dataset.caption;
        place.classList.remove('is-swapping');
      }, 220);
      thumbs[index].scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduced.matches ? 'auto' : 'smooth' });
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

    // Swipe on touch, without hijacking vertical scrolling.
    let startX = null;
    let startY = null;
    frame.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse') return;
      startX = e.clientX;
      startY = e.clientY;
    });
    frame.addEventListener('pointerup', (e) => {
      if (startX === null) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      startX = startY = null;
      if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.4) go(index + (dx < 0 ? 1 : -1), true);
    });
    frame.addEventListener('pointercancel', () => { startX = startY = null; });

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
      el.style.transitionDelay = `${Math.min((i % 3) * 0.08, 0.24)}s`;
      io.observe(el);
    });
    const showRest = () => targets.forEach((el) => { el.classList.add('is-visible'); io.unobserve(el); });
    setTimeout(showRest, 2500);
    if (document.visibilityState === 'hidden') showRest();
  }
})();
