(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const SELECTORS = [
    '.service-item',
    '.product-item-link',
    '.feature-item',
    '.fact',
    '.blog-post-item',
    '.changelog-entry',
    '.oss-copy',
    '.section-top',
    '.app-hero-copy',
    '.waitlist-section h2',
    '.waitlist-section p',
    '.waitlist-section .waitlist-form',
    '.screenshots-section h2',
    '.screenshot-grid',
    '.post-hero',
  ];

  const io = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      });
    },
    { threshold: 0.07, rootMargin: '0px 0px -28px 0px' }
  );

  const viewH = window.innerHeight;

  SELECTORS.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
      const rect = el.getBoundingClientRect();
      // skip elements already fully in viewport on load
      if (rect.bottom < viewH * 0.85) return;

      el.classList.add('will-reveal');

      // stagger siblings within the same parent
      const siblings = el.parentElement
        ? [...el.parentElement.querySelectorAll(sel)]
        : [];
      const idx = siblings.indexOf(el);
      if (idx > 0) {
        el.style.transitionDelay = `${Math.min(idx * 0.075, 0.3)}s`;
      }

      io.observe(el);
    });
  });
})();
