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
    // Read the code before the button goes in, or its label is copied too.
    const text = pre.innerText;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-copy";
    btn.textContent = "Copy";
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(text).then(() => {
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
      status.textContent = "Sending…";
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
    say("Saving…");
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

// A slim bar with the page's main action, shown once the hero's buttons have
// scrolled away and hidden again while any of its data-hide-when targets is
// on screen. Driven by IntersectionObserver only, and dismissible for the
// rest of the visit.
(() => {
  const bar = document.querySelector("[data-sticky-cta]");
  if (!bar || !("IntersectionObserver" in window)) return;
  const targets = [...document.querySelectorAll(bar.dataset.hideWhen || "")];
  if (!targets.length) return;
  let dismissed = false;
  try { dismissed = sessionStorage.getItem("sticky-cta-off") === "1"; } catch (e) { /* storage blocked */ }
  if (dismissed) return;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "sticky-cta-close";
  close.setAttribute("aria-label", "Dismiss");
  close.textContent = "\u00d7";
  bar.appendChild(close);
  const onScreen = new Set();
  let pastFirst = false;
  const update = () => {
    const show = !dismissed && pastFirst && onScreen.size === 0;
    bar.hidden = !show;
    document.body.classList.toggle("has-sticky-cta", show);
  };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) onScreen.add(e.target); else onScreen.delete(e.target);
      if (e.target === targets[0]) pastFirst = !e.isIntersecting && e.boundingClientRect.bottom < 0;
    });
    update();
  });
  targets.forEach((t) => io.observe(t));
  close.addEventListener("click", () => {
    dismissed = true;
    try { sessionStorage.setItem("sticky-cta-off", "1"); } catch (e) { /* storage blocked */ }
    io.disconnect();
    update();
  });
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

// Signature: every post-style page (blog, guides, templates, digest issues)
// ends with the Purplelink mark, the studio name and the author, so a page that
// is shared or printed on its own still says who made it. Added here rather
// than in each page so the cron-written digest issues get it without a commit.
(() => {
  const add = () => {
    const body = document.querySelector("article.post-body");
    if (!body || document.querySelector(".post-signature")) return;
    const sig = document.createElement("aside");
    sig.className = "post-signature";
    sig.setAttribute("aria-label", "About the author");
    sig.innerHTML =
      '<a class="post-signature-mark" href="/" aria-label="Purplelink LLC home">' +
      '<img src="/assets/purplelink-mark.svg" alt="" width="48" height="48" loading="lazy"></a>' +
      '<div class="post-signature-text">' +
      '<p class="post-signature-name"><a href="/">Purplelink LLC</a></p>' +
      '<p class="post-signature-line">Written by <a href="/about/" rel="author">Benjamin Ampel</a>. ' +
      'Mac apps and manuscript tools for researchers. <a href="/">purplelink.llc</a></p>' +
      "</div>";
    body.insertAdjacentElement("afterend", sig);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add);
  else add();
})();

// Post hero: a kicker above the title and a banner image under it, on every
// post-style page (blog, guides, templates, digest issues). The title styling
// is CSS; this adds the two bits CSS cannot. Product posts show the real app
// capture and the prints post shows one of Ben's photographs (the site's own
// watermarked copy). Pages with no fitting image, digest issues included, get
// the kicker and the styled title only. Added here, not in each page, so
// the cron-written digest issues get it without a commit.
(() => {
  const PHOTOS = [{"s":"skogafoss","a":"Skógafoss waterfall falling from a green cliff, with a rainbow in the spray at its base","c":"Skógafoss, Iceland","f":[62,40],"w":1400,"h":934}];
  const SHOTS = {"mt":{"src":"/assets/moderntex-screens/01-editor-clean-1440.webp","w":1440,"h":792},"tikz":{"src":"/assets/moderntex-screens/07-tikz-editor-1440.webp","w":1440,"h":919},"pr":{"src":"/assets/tool-shots/paper-review-sample.webp","w":1440,"h":522},"vit":{"src":"/assets/vitae-screens/dashboard-1440.webp","w":1440,"h":747},"gp":{"src":"/assets/globepin-screens/03-globe-800.webp","w":800,"h":1739},"haea":{"src":"/assets/haea-screens/01-today-800.webp","w":800,"h":1739}};
  // slug -> screenshot key (product posts) or photo slug (travel posts)
  const BY_SLUG = {
    "the-latex-editor-academics-want": "mt", "best-mac-latex-editors": "mt",
    "overleaf-alternative-mac": "mt", "the-co-author-who-writes-in-word": "mt",
    "latex-track-changes": "mt", "compile-latex-project-to-pdf-online": "mt",
    "tikz-and-tables-without-the-syntax": "tikz",
    "ai-paper-review-tools-compared": "pr", "paper-review": "pr", "use-paper-review-before-submitting": "pr",
    "running-your-manuscript-through-paper-review": "pr", "get-feedback-on-a-paper-before-submitting": "pr",
    "methodology-problems-peer-reviewers-flag": "pr", "desk-reject-recovery": "pr",
    "reviewer-says-novelty-is-limited": "pr", "how-to-respond-to-reviewer-2": "pr",
    "catch-ai-hallucinated-citations": "pr", "what-stays-in-a-blinded-manuscript": "pr",
    "where-your-academic-record-actually-lives": "vit", "track-academic-cv-tenure-case": "vit",
    "globepin-vs-polarsteps": "gp", "what-globepin-does-differently": "gp",
    "why-haea-is-on-device": "haea", "best-on-device-health-apps": "haea",
    "travel-photographs-as-prints": "skogafoss"
  };
  const ALT = {
    mt: "ModernTex with a LaTeX source on the left and the compiled PDF on the right",
    tikz: "ModernTex TikZ designer showing a flowchart and the generated TikZ code",
    pr: "A Paper Review report excerpt listing critical blind spots with quoted passages",
    vit: "The Vitae dashboard showing submissions, grants and deadlines",
    gp: "GlobePin showing a 3D globe with places visited", haea: "Haea showing the Today view with sleep and activity"
  };
  const PHONE = { gp: 1, haea: 1 };

  const kind = () => {
    const p = location.pathname;
    if (p.indexOf("/blog/digest/") === 0) return "Daily Digest";
    if (p.indexOf("/guides/") === 0) return "Guide";
    if (p.indexOf("/templates/") === 0) return "Template";
    if (p.indexOf("/latex-errors/") === 0) return "LaTeX errors";
    return "Blog";
  };
  const pick = (hero) => {
    const slug = location.pathname.replace(/\/index\.html$/, "").replace(/\.html$/, "").split("/").filter(Boolean).pop() || "";
    const key = BY_SLUG[slug];
    if (key && SHOTS[key]) return { shot: key };
    const wanted = key && PHOTOS.find((p) => p.s === key);
    if (wanted) return { photo: wanted };
    return null;
  };
  const el = (tag, cls, attrs) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
    return n;
  };
  const build = () => {
    const hero = document.querySelector(".post-hero");
    if (!hero || document.querySelector(".post-kicker")) return;
    const title = hero.querySelector(".post-title");
    if (title) {
      const k = el("p", "post-kicker");
      k.innerHTML = '<img src="/assets/purplelink-mark.svg" alt="" width="18" height="18"><span></span>';
      k.lastChild.textContent = kind();
      title.insertAdjacentElement("beforebegin", k);
    }
    const choice = pick(hero);
    if (!choice) return;
    const fig = el("figure", "post-banner" + (choice.shot ? (PHONE[choice.shot] ? " post-banner-phone" : " post-banner-shot") : " post-banner-photo"));
    let img;
    if (choice.photo) {
      const p = choice.photo;
      img = el("img", "", { src: "/assets/photography/" + p.s + "-1400.webp", alt: p.a, width: p.w, height: p.h, decoding: "async", fetchpriority: "high" });
      img.style.objectPosition = p.f[0] + "% " + p.f[1] + "%";
      fig.appendChild(img);
      const cap = el("figcaption", "post-banner-caption");
      cap.textContent = p.c + ". A photograph by Benjamin Ampel.";
      fig.appendChild(cap);
    } else {
      const s = SHOTS[choice.shot];
      img = el("img", "", { src: s.src, alt: ALT[choice.shot], width: s.w, height: s.h, decoding: "async", fetchpriority: "high" });
      fig.appendChild(img);
    }
    hero.insertAdjacentElement("afterend", fig);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();

// Link to this tool: on every page whose <main> holds a .tool-app, append a
// small block after the app with a ready-made sentence and a Copy button, so
// a reader can paste the tool into a lab wiki or a course page. Skipped on
// noindex pages (the paid upload and success pages carry a .tool-app too).
// Pages that load /tools/tools.js send the file to the backend, so their
// sentence says "files are not stored" rather than "runs in your browser".
(() => {
  const build = () => {
    const main = document.querySelector("main");
    if (!main) return;
    const app = main.querySelector(".tool-app");
    if (!app || document.querySelector(".tool-link")) return;
    const robots = document.querySelector('meta[name="robots"]');
    if (robots && /noindex/i.test(robots.getAttribute("content") || "")) return;
    const canonical = document.querySelector('link[rel="canonical"]');
    const h1 = main.querySelector("h1") || document.querySelector("h1");
    if (!canonical || !h1) return;
    const url = canonical.href;
    const name = (h1.textContent || "").replace(/\s+/g, " ").trim();
    if (!url || !name) return;
    const onServer = !!document.querySelector('script[src^="/tools/tools.js"]');
    const text = name + (onServer ? ", free, no account, files are not stored: " : ", free and runs in your browser: ") + url;

    const el = (tag, cls, attrs) => {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
      return n;
    };
    const box = el("aside", "tool-link", { "aria-labelledby": "tool-link-heading" });
    const head = el("h2", "tool-link-head", { id: "tool-link-heading" });
    head.textContent = "Link to this tool";
    const row = el("div", "tool-link-row");
    const input = el("input", "tool-link-input", { type: "text", readonly: "", "aria-label": "Text to paste when linking to this tool", spellcheck: "false" });
    input.value = text;
    const btn = el("button", "btn btn-ghost tool-link-copy", { type: "button" });
    btn.textContent = "Copy";
    const status = el("p", "tool-link-status", { role: "status", "aria-live": "polite" });
    row.appendChild(input);
    row.appendChild(btn);
    box.appendChild(head);
    box.appendChild(row);
    box.appendChild(status);
    app.insertAdjacentElement("afterend", box);

    let timer = null;
    const say = (msg) => {
      status.textContent = msg;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => { status.textContent = ""; }, 4000);
    };
    const selectAll = () => {
      input.focus();
      input.select();
      try { input.setSelectionRange(0, input.value.length); } catch (_) {}
    };
    const fallback = () => {
      selectAll();
      let ok = false;
      try { ok = document.execCommand && document.execCommand("copy"); } catch (_) { ok = false; }
      say(ok ? "Copied." : "Selected. Press Command-C or Ctrl-C to copy.");
    };
    input.addEventListener("focus", () => { input.select(); });
    btn.addEventListener("click", () => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => { say("Copied."); }, fallback);
      } else {
        fallback();
      }
    });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();

// Researcher list: the submission checklist PDF by email, then a note when a
// tool changes. One block, added after the article on guides and blog posts
// (before the signature) and after "Link to this tool" on tool pages. Not on
// digest issues, waitlist, success or noindex pages, and not shown again to a
// browser that has signed up. /checklist/ carries the same form in its own
// markup; this wires it up too. The function is checklist-signup.mjs.
(() => {
  const API = "/.netlify/functions/checklist-signup";
  const PDF = "/assets/downloads/submission-checklist.pdf";
  const KEY = "pl_checklist_signup";
  const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;

  const signedUp = () => {
    try { return localStorage.getItem(KEY) === "1"; } catch (_) { return false; }
  };
  const remember = () => {
    try { localStorage.setItem(KEY, "1"); } catch (_) { /* private mode: ask again next time */ }
  };

  const markup =
    '<h2 class="list-signup-head" id="list-signup-h">The submission checklist, by email</h2>' +
    '<p class="list-signup-lede">Twelve checks reviewers run first, as a one-page PDF, plus one note when a tool changes. No daily mail.</p>' +
    '<form class="list-signup-form" novalidate>' +
    '<div class="list-signup-field">' +
    '<label for="list-signup-email">Email</label>' +
    '<input type="email" id="list-signup-email" name="email" autocomplete="email" inputmode="email" spellcheck="false" placeholder="you@university.edu" required>' +
    "</div>" +
    '<input type="text" name="website" class="visually-hidden" tabindex="-1" autocomplete="off" aria-hidden="true">' +
    '<button type="submit" class="btn btn-primary">Send me the checklist</button>' +
    "</form>" +
    '<p class="list-signup-status" data-list-signup-status role="status" aria-live="polite"></p>' +
    '<p class="list-signup-fine">Unsubscribe from any email with one click. <a href="/privacy/">Privacy</a>.</p>';

  const pdfLink = (text) => {
    const a = document.createElement("a");
    a.href = PDF;
    a.setAttribute("download", "");
    a.textContent = text;
    return a;
  };

  const wire = (box) => {
    const form = box.querySelector("form");
    const status = box.querySelector("[data-list-signup-status]");
    if (!form || !status) return;
    const input = form.querySelector('input[type="email"]');
    const btn = form.querySelector('button[type="submit"]');
    const label = btn.textContent;
    const say = (text, isError, withLink) => {
      status.textContent = text;
      status.classList.toggle("is-error", !!isError);
      if (withLink) {
        status.appendChild(document.createTextNode(" "));
        status.appendChild(pdfLink("Download the checklist (PDF)"));
        status.appendChild(document.createTextNode("."));
      }
    };
    const done = () => {
      // Hold the height so nothing below the block jumps when the form goes.
      box.style.minHeight = box.offsetHeight + "px";
      box.classList.add("is-done");
      [...box.children].forEach((child) => {
        if (child !== status && !child.matches(".list-signup-head")) child.remove();
      });
      status.classList.remove("is-error");
      status.textContent = "Sent. Check your inbox. You can also ";
      status.appendChild(pdfLink("download it now"));
      status.appendChild(document.createTextNode("."));
      status.setAttribute("tabindex", "-1");
      status.focus({ preventScroll: true });
    };
    input.addEventListener("input", () => {
      if (status.classList.contains("is-error")) say("");
      input.removeAttribute("aria-invalid");
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (btn.disabled) return;
      const email = input.value.trim();
      if (!EMAIL.test(email)) {
        say("That address doesn't look complete.", true);
        input.setAttribute("aria-invalid", "true");
        input.focus();
        return;
      }
      btn.disabled = true;
      btn.textContent = "Sending";
      say("");
      try {
        const r = await fetch(API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, page: location.pathname, website: form.website.value }),
        });
        if (!r.ok) throw new Error(String(r.status));
        remember();
        done();
        if (window.plTrack) window.plTrack("checklist_signup", "");
      } catch (err) {
        btn.disabled = false;
        btn.textContent = label;
        const why = err && err.message === "429"
          ? "Too many requests from here today, so the email was not sent."
          : "The email didn't go through. Try again in a minute.";
        say(why, true, true);
      }
    });
  };

  const build = () => {
    // A form already in the page (the /checklist/ page) is wired, never doubled.
    const present = document.querySelector("[data-list-signup]");
    if (present) { wire(present); return; }

    const path = location.pathname;
    if (/^\/checklist(\/|$)/.test(path) || /^\/blog\/digest(\/|$)/.test(path)) return;
    if (/(^|\/)(waitlist|success)(\/|\.html|$)/.test(path)) return;
    const robots = document.querySelector('meta[name="robots"]');
    if (robots && /noindex/i.test(robots.getAttribute("content") || "")) return;
    if (signedUp()) return;

    let anchor = null;
    let variant = "";
    // Most posts are <article class="post-body">; older guides use a div in <main>.
    const main = document.querySelector("main");
    const article = document.querySelector("article.post-body") || (main && main.querySelector(".post-body"));
    const app = main && main.querySelector(".tool-app");
    if (article && /^\/(guides|blog)\/./.test(path)) {
      anchor = article;
      variant = "list-signup--post";
    } else if (app) {
      anchor = document.querySelector(".tool-link") || app;
      variant = "list-signup--tool";
    }
    if (!anchor) return;

    const box = document.createElement("aside");
    box.className = "list-signup " + variant;
    box.setAttribute("data-list-signup", "");
    box.setAttribute("aria-labelledby", "list-signup-h");
    box.innerHTML = markup;
    anchor.insertAdjacentElement("afterend", box);
    wire(box);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();

// House promo: one small card for one of Purplelink's own apps, picked at random on each page load and
// placed above the footer. Skipped on checkout, receipt and account-management pages, hidden for the rest of
// the visit once dismissed, and never promotes the app a page is already about.
(() => {
  const path = location.pathname;
  if (/\/(success|recover|manage|upload|packs|setup)\//.test(path) || path.startsWith('/stats/')) return;
  try { if (sessionStorage.getItem('pl-promo-hidden') === '1') return; } catch (_) { /* storage blocked: show it */ }

  const APPS = [
    { id: 'moderntex', name: 'ModernTex', href: '/moderntex/', icon: '/assets/moderntex-icon.webp', cta: 'Try it free',
      text: 'A native LaTeX editor for Mac. Free for 7 days, then $19.99 once, with every update included.', own: ['/moderntex/', '/suite/'] },
    { id: 'outbound-veil', name: 'Outbound Veil', href: '/outbound-veil/', icon: '/assets/outbound-veil-icon.webp', cta: 'Try it free',
      text: 'Checks what you type for personal information before you send it. Free 7-day trial, then $29.99.', own: ['/outbound-veil/', '/suite/'] },
    { id: 'legroom', name: 'Legroom', href: '/legroom/', icon: '/assets/legroom-icon.webp', cta: 'Try it free',
      text: 'Shows your free disk space and cleans the folders you choose, after you approve a preview. Free 7-day trial, then $9.99.', own: ['/legroom/', '/suite/'] },
    { id: 'keyfeel', name: 'Keyfeel', href: '/keyfeel/', icon: '/assets/keyfeel-icon-128.webp', cta: 'Try it free',
      text: 'Recorded keyboard, click and scroll sounds for your Mac, with optional trackpad haptics. Free 7-day trial, then $9.99.', own: ['/keyfeel/', '/suite/'] },
    { id: 'vitae', name: 'Vitae', href: '/vitae/', icon: '/assets/vitae-icon.webp', cta: 'Get it free',
      text: 'Track submissions, grants and your CV in one place. Free for Mac, with an optional Plus subscription from $2.99 a month.', own: ['/vitae/'] },
    { id: 'paper-review', name: 'Paper Review', href: '/tools/paper-review/', icon: '/assets/purplelink-logo-64.png', cta: 'See how it works',
      text: 'AI reviewers read your manuscript the way a journal would, before you submit. From $9.', own: ['/tools/paper-review/'] },
    { id: 'scholar-utility-belt', name: 'Scholar Utility Belt', href: '/scholar-utility-belt/', icon: '/assets/scholar-utility-belt-icon.webp', cta: 'Add to Chrome',
      text: 'Journal rankings, h-index and retraction alerts inside Google Scholar. A free Chrome extension.', own: ['/scholar-utility-belt/'] },
    { id: 'mac-suite', name: 'Mac Suite', href: '/suite/', icon: '/assets/moderntex-icon.webp', cta: 'See the bundle',
      text: 'ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio and Vitae Plus together for $54.99, once.', own: ['/suite/', '/moderntex/', '/outbound-veil/', '/legroom/', '/keyfeel/', '/tapefolio/', '/vitae/plus/'] },
    { id: 'globepin', name: 'GlobePin', href: '/globepin/', icon: '/assets/globepin-icon.webp', cta: 'Get it free',
      text: 'Mark every place you have been on a map. Free for iPhone.', own: ['/globepin/'] },
  ];

  const place = () => {
    const footer = document.querySelector('footer.footer');
    if (!footer || document.querySelector('.house-promo')) return;
    const pool = APPS.filter((a) => !a.own.some((p) => path.startsWith(p)));
    if (!pool.length) return;
    const app = pool[Math.floor(Math.random() * pool.length)];

    const box = document.createElement('aside');
    box.className = 'house-promo';
    box.setAttribute('aria-label', 'About one of our apps');
    const card = document.createElement('div');
    card.className = 'house-promo-card';
    const img = document.createElement('img');
    img.src = app.icon; img.alt = ''; img.width = 48; img.height = 48; img.loading = 'lazy'; img.decoding = 'async';
    const body = document.createElement('div');
    body.className = 'house-promo-body';
    const tag = document.createElement('span');
    tag.className = 'house-promo-tag';
    tag.textContent = 'From Purplelink';
    const text = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = app.name;
    text.appendChild(strong);
    text.appendChild(document.createTextNode(' ' + app.text));
    body.appendChild(tag); body.appendChild(text);
    const link = document.createElement('a');
    link.className = 'btn btn-ghost house-promo-cta';
    link.href = app.href;
    link.textContent = app.cta;
    link.addEventListener('click', () => { try { window.plTrack && window.plTrack('promo_click', app.id); } catch (_) { /* ignore */ } });
    const hide = document.createElement('button');
    hide.type = 'button';
    hide.className = 'house-promo-hide';
    hide.setAttribute('aria-label', 'Hide this suggestion');
    hide.textContent = 'Hide';
    hide.addEventListener('click', () => {
      box.remove();
      try { sessionStorage.setItem('pl-promo-hidden', '1'); } catch (_) { /* ignore */ }
    });
    card.appendChild(img); card.appendChild(body); card.appendChild(link); card.appendChild(hide);
    box.appendChild(card);
    footer.parentNode.insertBefore(box, footer);
    window.setTimeout(() => { try { window.plTrack && window.plTrack('promo_view', app.id); } catch (_) { /* ignore */ } }, 1200);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', place); else place();
})();
