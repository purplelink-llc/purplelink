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
  // No IntersectionObserver means nothing would ever un-hide these elements.
  if (!('IntersectionObserver' in window)) return;

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

  const hidden = new Set();

  const io = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        hidden.delete(entry.target);
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
      hidden.add(el);
    });
  });

  // The observer only fires for a page that is actually being drawn. A
  // background tab, a headless renderer or a screenshot service runs this
  // script, gets the elements hidden, and never gets them back — the section
  // ships blank. Reveal anything still waiting after a beat, so the animation
  // stays an enhancement rather than a precondition for seeing the content.
  const revealRest = () => {
    hidden.forEach(el => {
      el.classList.add('is-visible');
      io.unobserve(el);
    });
    hidden.clear();
  };
  setTimeout(revealRest, 2000);
  if (document.visibilityState === 'hidden') revealRest();
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

// ModernTex: someone who pressed "Buy" inside the trial app (?from=trial) already
// has the trial, so lead with the buy button instead of offering the trial again.
(() => {
  if (new URLSearchParams(location.search).get("from") !== "trial") return;
  const buy = document.getElementById("checkout-btn");
  const trial = document.getElementById("trial-download");
  if (!buy || !trial) return;
  buy.classList.replace("btn-ghost", "btn-primary");
  trial.classList.replace("btn-primary", "btn-ghost");
  trial.parentNode.insertBefore(buy, trial);
})();

// Remembered choices. A control marked data-remember="<key>" keeps its last
// value in localStorage: the LaTeX engine, the Word style, the Paper Review
// tier and field. Restored after every deferred page script has run, with a
// change event, so each page's own handlers (prices, labels) see the value.
// Storage can be missing or throw (private windows); the page works without it.
(() => {
  const KEY = "pl_prefs";
  let prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { prefs = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ } };

  const restore = () => {
    document.querySelectorAll("select[data-remember]").forEach((sel) => {
      const k = sel.dataset.remember;
      const v = prefs[k];
      if (v && sel.value !== v && [...sel.options].some((o) => o.value === v)) {
        sel.value = v;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
      sel.addEventListener("change", () => { prefs[k] = sel.value; save(); });
    });

    document.querySelectorAll('input[type="radio"][data-remember]').forEach((radio) => {
      const k = radio.dataset.remember;
      if (prefs[k] === radio.value && !radio.checked) {
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      radio.addEventListener("change", () => { if (radio.checked) { prefs[k] = radio.value; save(); } });
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", restore);
  else restore();
})();

// Recently used tools. Each visit to a tool page is remembered (last six, in
// this browser only), and pages with a [data-recent-tools] slot list them so a
// returning visitor is one click from the tool they came back for.
(() => {
  const KEY = "pl_recent_tools";
  let list = [];
  try { list = JSON.parse(localStorage.getItem(KEY) || "[]") || []; } catch (e) { list = []; }
  if (!Array.isArray(list)) list = [];

  const m = location.pathname.match(/^\/tools\/([a-z0-9-]+)\/$/);
  const h1 = document.querySelector(".tools-hero h1");
  if (m && h1) {
    const href = "/tools/" + m[1] + "/";
    const title = h1.textContent.replace(/\s+/g, " ").trim().slice(0, 60);
    list = [{ href, title }].concat(list.filter((t) => t && t.href !== href)).slice(0, 6);
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* ignore */ }
  }

  document.querySelectorAll("[data-recent-tools]").forEach((slot) => {
    const items = list.filter((t) => t && typeof t.href === "string" && /^\/tools\/[a-z0-9-]+\/$/.test(t.href) && t.href !== location.pathname);
    if (!items.length) return;
    const label = document.createElement("span");
    label.className = "recent-tools-label";
    label.textContent = "Recently used";
    slot.appendChild(label);
    items.forEach((t) => {
      const a = document.createElement("a");
      a.className = "tool-chip";
      a.href = t.href;
      a.textContent = t.title;
      slot.appendChild(a);
    });
    slot.hidden = false;
  });
})();

// Blog index topic filter. The chips stay hidden without JavaScript, so every
// post is listed; with it, one click narrows the list to a topic.
(() => {
  const bar = document.querySelector("[data-blog-filter]");
  if (!bar) return;
  const items = [...document.querySelectorAll(".blog-post-item[data-topic]")];
  const buttons = [...bar.querySelectorAll("button[data-filter]")];
  const apply = (topic) => {
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filter === topic)));
    items.forEach((it) => { it.hidden = topic !== "all" && it.dataset.topic !== topic; });
  };
  buttons.forEach((b) => b.addEventListener("click", () => apply(b.dataset.filter)));
  bar.hidden = false;
})();
