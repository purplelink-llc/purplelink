// Paid-tool purchase buttons — greyed out while we wait for Stripe
// activation. Every button that would initiate a Stripe Checkout (any
// `.pr-checkout-btn` plus the legacy `#checkout-btn` on the Paper Review
// landing) gets disabled and re-labelled to "Coming soon · $X". Removes
// the click handler at the source rather than letting users get a
// confusing 500 from an unconfigured Stripe endpoint.
//
// To re-enable purchases later, just delete this IIFE.
(() => {
  const COMING_SOON_FLAG = "data-coming-soon";

  const apply = () => {
    // Match by class first (most paid buttons), then by id (Paper Review
    // tier picker), then by data-product (auxiliary tool landings).
    const buttons = new Set([
      ...document.querySelectorAll(".pr-checkout-btn"),
      ...document.querySelectorAll('button[data-product]'),
    ]);
    const legacy = document.getElementById("checkout-btn");
    if (legacy) buttons.add(legacy);

    buttons.forEach((btn) => {
      if (btn.hasAttribute(COMING_SOON_FLAG)) return;
      btn.setAttribute(COMING_SOON_FLAG, "1");
      btn.disabled = true;
      btn.setAttribute("aria-disabled", "true");
      btn.classList.add("btn-coming-soon");
      // Preserve any "— $X" suffix in the original label so the price is
      // still legible to the user.
      const original = btn.textContent.trim();
      const priceMatch = original.match(/(\$\d+(?:\.\d{2})?)/);
      btn.textContent = priceMatch
        ? "Coming soon · " + priceMatch[1]
        : "Coming soon";
      btn.setAttribute("title", "Checkout opens once Stripe is activated.");
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }
})();

// Under-construction banner — site-wide notice that the paid manuscript
// tools (Paper Review, Cover Letter, Anonymity Check, Citation Gap,
// Revision Review, Response Review, Volume Packs) are still in active
// development. The free LaTeX/citation tools remain fully functional.
// Dismissible per browser via localStorage; revisits remember the dismissal.
(() => {
  try {
    if (localStorage.getItem('uc-banner-dismissed-2026-05-31') === '1') return;
  } catch (_) { /* localStorage may be blocked — show banner anyway */ }

  const banner = document.createElement('div');
  banner.className = 'uc-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.innerHTML =
    '<div class="uc-banner-inner">' +
      '<span class="uc-banner-text">' +
        '<strong>Under construction.</strong> ' +
        'The paid manuscript tools (Paper Review, Cover Letter, Anonymity Check, ' +
        'Citation Gap, Revision Review, Response Review, Volume Packs) are in ' +
        'active development — checkout is not yet live, please don’t try to ' +
        'pay. The free LaTeX and citation tools work as normal.' +
      '</span>' +
      '<button type="button" class="uc-banner-close" aria-label="Dismiss notice">×</button>' +
    '</div>';

  const insert = () => {
    if (!document.body) return false;
    document.body.insertBefore(banner, document.body.firstChild);
    document.body.classList.add('has-uc-banner');
    banner.querySelector('.uc-banner-close').addEventListener('click', () => {
      banner.remove();
      document.body.classList.remove('has-uc-banner');
      try { localStorage.setItem('uc-banner-dismissed-2026-05-31', '1'); } catch (_) {}
    });
    return true;
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', insert, { once: true });
  } else {
    insert();
  }
})();

// Accessibility — WAI-ARIA APG keyboard support for [role="tablist"].
// Runs regardless of reduced-motion. Wires arrow / Home / End navigation,
// maintains roving tabindex, and triggers click on the target tab so each
// page's own tab-switch handler still runs.
(() => {
  const init = (tablist) => {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    if (!tabs.length) return;

    const setActive = (idx, focus = true) => {
      tabs.forEach((t, i) => {
        t.tabIndex = i === idx ? 0 : -1;
      });
      if (focus) tabs[idx].focus();
      tabs[idx].click();
    };

    // Initial roving-tabindex state: 0 on the currently-selected tab, -1 elsewhere.
    let initial = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
    if (initial < 0) initial = 0;
    tabs.forEach((t, i) => { t.tabIndex = i === initial ? 0 : -1; });

    tablist.addEventListener('keydown', (e) => {
      const i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      let target = null;
      switch (e.key) {
        case 'ArrowLeft':  target = (i - 1 + tabs.length) % tabs.length; break;
        case 'ArrowRight': target = (i + 1) % tabs.length; break;
        case 'Home':       target = 0; break;
        case 'End':        target = tabs.length - 1; break;
      }
      if (target === null) return;
      e.preventDefault();
      setActive(target);
    });
  };

  document.querySelectorAll('[role="tablist"]').forEach(init);
})();

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

// Digest subscribe form — posts to /.netlify/functions/subscribe
(() => {
  const form = document.getElementById("subscribe-form");
  if (!form) return;

  const status = document.getElementById("subscribe-status");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    const btn = form.querySelector("button[type=submit]");

    btn.disabled = true;
    status.textContent = "";
    status.className = "subscribe-status";

    try {
      const res = await fetch("/.netlify/functions/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (res.ok) {
        status.textContent = "Subscribed. You'll get the next issue in your inbox.";
        status.classList.add("subscribe-status--ok");
        form.reset();
      } else {
        const data = await res.json().catch(() => ({}));
        status.textContent = data.error || "Something went wrong. Please try again.";
        status.classList.add("subscribe-status--err");
      }
    } catch {
      status.textContent = "Network error. Please try again.";
      status.classList.add("subscribe-status--err");
    } finally {
      btn.disabled = false;
    }
  });
})();
