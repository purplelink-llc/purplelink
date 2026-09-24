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

// ModernTex: someone who pressed "Buy" inside the trial app (?from=trial), or
// who downloaded the trial from this browser in the last 14 days, already has
// it, so lead with the buy button instead of offering the trial again.
(() => {
  let recent = false;
  try {
    const at = Number(localStorage.getItem("pl_mtx_trial") || 0);
    recent = at > 0 && Date.now() - at < 14 * 86400000;
  } catch (e) { /* storage blocked */ }
  const fromApp = new URLSearchParams(location.search).get("from") === "trial";
  if (!fromApp && !recent) return;
  const buy = document.getElementById("checkout-btn");
  const trial = document.getElementById("trial-download");
  if (!buy || !trial) return;
  buy.classList.replace("btn-ghost", "btn-primary");
  trial.classList.replace("btn-primary", "btn-ghost");
  trial.parentNode.insertBefore(buy, trial);
  if (!fromApp) trial.textContent = "Download the trial again";
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

  // A link marked data-set-pref="key=value" records that choice when clicked,
  // so the field pages preselect their profile on the Paper Review upload page.
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("[data-set-pref]");
    if (!a) return;
    const [k, v] = a.dataset.setPref.split("=");
    if (k && v) { prefs[k] = v; save(); }
  });
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

// Copy button on code blocks in guides and templates (four or more lines).
(() => {
  if (!navigator.clipboard) return;
  document.querySelectorAll(".post-body pre").forEach((pre) => {
    if ((pre.textContent.match(/\n/g) || []).length < 3) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-copy";
    btn.textContent = "Copy";
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(pre.innerText).then(() => {
        btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = "Copy"; }, 1600);
      }, () => { btn.textContent = "Select and copy"; });
    });
    pre.classList.add("has-copy");
    pre.appendChild(btn);
  });
})();

// "Clear what this browser remembers" on /privacy/: removes every key the
// site writes (saved choices, recent tools, checklist ticks, unsent drafts).
(() => {
  const btn = document.querySelector("[data-clear-prefs]");
  if (!btn) return;
  const status = document.querySelector("[data-clear-prefs-status]");
  btn.addEventListener("click", () => {
    let n = 0;
    try {
      Object.keys(localStorage).forEach((k) => {
        if (k.startsWith("pl_") || k.startsWith("purplelink-")) { localStorage.removeItem(k); n++; }
      });
      if (status) status.textContent = n ? "Cleared. Nothing from this site is stored in this browser now." : "There was nothing stored.";
    } catch (e) {
      if (status) status.textContent = "This browser blocks site storage, so nothing was stored.";
    }
  });
})();

// In-page filter for the tools and guides indexes. The input names the items
// it filters (data-list-filter="<selector>"); sections left with no match are
// hidden too. "/" focuses the box, Escape clears it.
(() => {
  const input = document.querySelector("[data-list-filter]");
  if (!input) return;
  const items = [...document.querySelectorAll(input.dataset.listFilter)];
  const status = input.parentElement.querySelector(".list-filter-status");
  const sections = [...new Set(items.map((el) => el.closest("section")).filter(Boolean))];
  const norm = (t) => t.toLowerCase().replace(/\s+/g, " ");
  // Price words make "free" and "paid" work as filters: a card's price label
  // decides, and cards without one take data-list-default (free, on /tools/).
  const priceWord = (el) => {
    const price = el.querySelector("[class$='-price']");
    if (!price) return input.dataset.listDefault || "";
    return /free/i.test(price.textContent) ? "free" : "paid";
  };
  const text = new Map(items.map((el) => [el, norm(el.textContent + " " + priceWord(el) + " " + (el.getAttribute("href") || el.querySelector("a")?.getAttribute("href") || ""))]));
  // Words people type that the cards phrase differently.
  const SYNONYMS = { reference: ["cit", "bib"], references: ["cit", "bib"], word: ["docx"], cv: ["resume", "vitae"], doi: ["bib", "cit"], editor: ["moderntex"] };
  const matches = (hay, t) => hay.includes(t) || (SYNONYMS[t] || []).some((alt) => hay.includes(alt));
  const apply = () => {
    const terms = norm(input.value).trim().split(" ").filter(Boolean);
    let shown = 0;
    items.forEach((el) => {
      const hit = terms.every((t) => matches(text.get(el), t));
      el.hidden = !hit;
      if (hit) shown++;
    });
    sections.forEach((sec) => { sec.hidden = !items.some((el) => !el.hidden && sec.contains(el)); });
    if (status) {
      status.textContent = !terms.length ? "" : shown ? `${shown} ${shown === 1 ? "match" : "matches"}` : "Nothing matches. Try another word, or email ben@purplelink.llc and say what you were looking for.";
    }
  };
  input.addEventListener("input", apply);
  input.addEventListener("keydown", (e) => { if (e.key === "Escape") { input.value = ""; apply(); } });
  // On a phone the keyboard covers the results; lift the box to the top.
  input.addEventListener("focus", () => {
    if (window.innerWidth > 700) return;
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(() => input.scrollIntoView({ block: "start", behavior: smooth ? "smooth" : "auto" }), 250);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t.closest && t.closest("input, textarea, select, [contenteditable]")) return;
    e.preventDefault();
    input.focus();
  });
})();

// ModernTex trial: after someone clicks a trial download, offer (never
// require) a setup email and a reminder before the trial ends. The form
// nearest the clicked link is revealed; the backend sends at most three
// emails and answers the same way for any address.
(() => {
  const forms = [...document.querySelectorAll("[data-trial-signup]")];
  if (!forms.length) return;
  const API = "https://ben-ampel--purplelink-latextools-web.modal.run/lifecycle/trial";
  // iPadOS Safari reports itself as a Mac; touch points tell them apart.
  const ua = navigator.userAgent;
  const onMac = /Macintosh/.test(ua) && !/iPhone|iPad|iPod/.test(ua) && !(navigator.maxTouchPoints > 1);
  document.querySelectorAll('a[href*="moderntex-download?trial=1"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const scope = a.closest("section, .app-hero-copy") || document;
      const form = scope.querySelector("[data-trial-signup]") || forms[0];
      form.hidden = false;
      if (onMac || a.dataset.anyway) {
        try { localStorage.setItem("pl_mtx_trial", String(Date.now())); } catch (err) { /* ignore */ }
        return;
      }
      // A disk image is no use on a phone or a PC: offer to send the link
      // to open on the Mac instead, with the download still one tap away.
      e.preventDefault();
      const head = form.querySelector(".trial-remind-head");
      head.textContent = "ModernTex runs on a Mac. Enter your email and we will send the download link, with a setup guide, to open there.";
      const note = form.querySelector("[data-trial-status]");
      if (!form.querySelector("[data-trial-anyway]")) {
        const p = document.createElement("p");
        p.className = "trial-remind-note";
        p.dataset.trialAnyway = "";
        const link = document.createElement("a");
        link.href = a.href;
        link.dataset.anyway = "1";
        link.textContent = "Download it here anyway";
        p.append(link, " (15 MB disk image).");
        note.after(p);
      }
      form.email.focus();
      if (window.plTrack) window.plTrack("trial_email_offer", /iPhone|iPad|Android/.test(ua) || navigator.maxTouchPoints > 1 ? "mobile" : "other");
    });
  });
  forms.forEach((form) => {
    const status = form.querySelector("[data-trial-status]");
    const btn = form.querySelector("button[type=submit]");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = form.email.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        status.textContent = "That address doesn't look complete.";
        form.email.focus();
        return;
      }
      btn.disabled = true;
      status.textContent = "Sending...";
      try {
        const r = await fetch(API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, website: form.website.value }),
        });
        if (r.status === 429) throw new Error("rate");
        if (!r.ok) throw new Error("http");
        status.textContent = "Thanks. If " + email + " is new to the list, the setup email is on its way.";
        form.email.disabled = true;
      } catch (err) {
        btn.disabled = false;
        status.textContent = "That didn't go through. Try again in a minute, or email ben@purplelink.llc.";
      }
    });
  });
})();

// Submission checklist: an optional single email a week before a deadline.
// The date must be 2 to 366 days out (the backend checks the same range).
(() => {
  const form = document.querySelector("[data-deadline-signup]");
  if (!form) return;
  const API = "https://ben-ampel--purplelink-latextools-web.modal.run/lifecycle/deadline";
  const status = form.querySelector("[data-deadline-status]");
  const btn = form.querySelector("button[type=submit]");
  const iso = (d) => d.toISOString().slice(0, 10);
  const day = 86400000;
  form.deadline.min = iso(new Date(Date.now() + 2 * day));
  form.deadline.max = iso(new Date(Date.now() + 366 * day));
  const say = (text, field) => {
    status.textContent = text;
    if (field) field.focus();
  };
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const deadline = form.deadline.value;
    const email = form.email.value.trim();
    if (!deadline || deadline < form.deadline.min || deadline > form.deadline.max) {
      say("Pick a deadline between two days and a year from now.", form.deadline);
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      say("That address doesn't look complete.", form.email);
      return;
    }
    btn.disabled = true;
    say("Saving...");
    try {
      const r = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, deadline, venue: form.venue.value.trim(), kind: form.dataset.deadlineKind || "submission", website: form.website.value }),
      });
      if (r.status === 429) throw new Error("rate");
      if (!r.ok) throw new Error("http");
      const when = new Date(Date.parse(deadline + "T00:00:00Z") - 7 * day);
      const sendOn = when.getTime() < Date.now() ? "within a day" : "on " + when.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
      say("Done. The reminder goes to " + email + " " + sendOn + ", with an unsubscribe link.");
      form.querySelectorAll("input").forEach((i) => { i.disabled = true; });
      if (window.plTrack) window.plTrack("deadline_signup", "");
    } catch (err) {
      btn.disabled = false;
      say("That didn't go through. Try again in a minute, or email ben@purplelink.llc.");
    }
  });
})();

// Free tools: a one-line next step under the result, revealed once a result
// is on screen and not when the run ended in an error.
(() => {
  document.querySelectorAll("[data-tool-next]").forEach((line) => {
    const target = document.querySelector(line.dataset.toolNext);
    if (!target || !("MutationObserver" in window)) return;
    const check = () => {
      const failed = target.querySelector(".tool-error, [role=alert]");
      const shown = !target.hidden && target.textContent.trim().length > 0 && !failed;
      if (shown) line.hidden = false;
    };
    new MutationObserver(check).observe(target, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["hidden"] });
  });
})();

// Back from a closed Stripe checkout (?checkout=canceled): say that nothing
// was charged and where to ask, once, then drop the flag from the address.
(() => {
  const q = new URLSearchParams(location.search);
  if (q.get("checkout") !== "canceled") return;
  q.delete("checkout");
  history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : "") + location.hash);
  const main = document.querySelector("main");
  if (!main) return;
  const note = document.createElement("div");
  note.className = "checkout-canceled";
  note.setAttribute("role", "status");
  const p = document.createElement("p");
  p.append("Checkout closed, and nothing was charged. If a question stopped you, email ");
  const mail = document.createElement("a");
  mail.href = "mailto:ben@purplelink.llc?subject=Question%20before%20buying";
  mail.textContent = "ben@purplelink.llc";
  p.append(mail, "; every price is also on the ");
  const pricing = document.createElement("a");
  pricing.href = "/pricing/";
  pricing.textContent = "pricing page";
  p.append(pricing, ".");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "checkout-canceled-close";
  close.setAttribute("aria-label", "Dismiss");
  close.textContent = "\u00d7";
  close.addEventListener("click", () => note.remove());
  note.append(p, close);
  main.prepend(note);
  if (window.plTrack) window.plTrack("checkout_canceled", location.pathname);
})();

// Mac-only downloads (data-mac-download="App name"): on a phone, tablet or
// PC, show where the app runs and offer to email the page to yourself (a
// plain mailto, nothing sent to Purplelink), with the download one tap away.
(() => {
  const ua = navigator.userAgent;
  const onMac = /Macintosh/.test(ua) && !/iPhone|iPad|iPod/.test(ua) && !(navigator.maxTouchPoints > 1);
  if (onMac) return;
  document.querySelectorAll("a[data-mac-download]").forEach((a) => {
    a.addEventListener("click", (e) => {
      if (a.dataset.anyway) return;
      e.preventDefault();
      const box = a.closest("div");
      let note = box.parentNode.querySelector(".mac-only-note");
      if (!note) {
        const app = a.dataset.macDownload;
        note = document.createElement("p");
        note.className = "mac-only-note";
        note.setAttribute("role", "status");
        note.append(app + " runs on a Mac with " + (a.dataset.macReq || "a recent macOS") + ". ");
        const mail = document.createElement("a");
        mail.href = "mailto:?subject=" + encodeURIComponent(app + " for Mac") + "&body=" + encodeURIComponent("Download " + app + " on your Mac: " + location.origin + location.pathname);
        mail.textContent = "Email yourself the link";
        const again = document.createElement("a");
        again.href = a.href;
        again.dataset.anyway = "1";
        again.textContent = "download it here anyway";
        note.append(mail, " to open it there, or ", again, ".");
        box.insertAdjacentElement("afterend", note);
        if (window.plTrack) window.plTrack("mac_only_note", app);
      }
      note.querySelector("a").focus();
    });
  });
})();

// Phones only (CSS hides it elsewhere): a slim bar with the page's main
// action, shown once the hero's buttons have scrolled away and hidden again
// while any of its data-hide-when targets is on screen.
(() => {
  const bar = document.querySelector("[data-sticky-cta]");
  if (!bar || !("IntersectionObserver" in window)) return;
  const targets = [...document.querySelectorAll(bar.dataset.hideWhen || "")];
  if (!targets.length) return;
  const onScreen = new Set();
  const update = () => {
    const pastFirst = targets[0].getBoundingClientRect().bottom < 0;
    const show = pastFirst && onScreen.size === 0;
    bar.hidden = !show;
    document.body.classList.toggle("has-sticky-cta", show);
  };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => (e.isIntersecting ? onScreen.add(e.target) : onScreen.delete(e.target)));
    update();
  });
  targets.forEach((t) => io.observe(t));
  window.addEventListener("scroll", update, { passive: true });
})();

// /tools/paper-review/packs/?pack=20 opens with that pack selected.
(() => {
  const want = new URLSearchParams(location.search).get("pack");
  if (!want || !/^\d{1,3}$/.test(want)) return;
  const pick = () => {
    const r = document.querySelector(`input[type="radio"][name="pack"][value$="-${want}"]`);
    if (r && !r.checked) { r.checked = true; r.dispatchEvent(new Event("change", { bubbles: true })); }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pick);
  else pick();
})();
