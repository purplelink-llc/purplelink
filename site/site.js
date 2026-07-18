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
    '.flagship-head',
    '.flagship-shot',
    '.flagship-point',
    '.scholar-inner',
    '.tools-inner',
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
  const refCode = new URLSearchParams(window.location.search).get("ref") || "";

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
        body: JSON.stringify({ email, ref: refCode }),
      });

      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        status.textContent = "Subscribed. You'll get the next issue in your inbox.";
        status.classList.add("subscribe-status--ok");
        form.reset();
        if (data.referralCode) {
          showReferralLink(data.referralCode);
        }
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

  function showReferralLink(code) {
    const existing = document.getElementById("referral-box");
    if (existing) existing.remove();

    const url = `${window.location.origin}/blog/digest/?ref=${encodeURIComponent(code)}`;
    const box = document.createElement("div");
    box.id = "referral-box";
    box.className = "referral-box";

    const p = document.createElement("p");
    p.textContent = "Know someone who'd like this? Share your link:";
    box.appendChild(p);

    const row = document.createElement("div");
    row.className = "referral-row";

    const input = document.createElement("input");
    input.type = "text";
    input.readOnly = true;
    input.value = url;
    input.className = "referral-input";
    input.setAttribute("aria-label", "Your referral link");
    row.appendChild(input);

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", () => {
      navigator.clipboard?.writeText(url).then(() => {
        copyBtn.textContent = "Copied!";
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
      });
    });
    row.appendChild(copyBtn);

    box.appendChild(row);
    status.insertAdjacentElement("afterend", box);
  }
})();
