// /tools/ index. site.js already filters the rows (input[data-list-filter]) and fills "Recently used"; this
// file adds what only this page has: the group rail's counts and its "in view" mark, arrow keys between rows,
// and the right shortcut label in the search field. Without JavaScript the page is a complete, linked list.
(() => {
  const page = document.querySelector(".tools-index");
  if (!page) return;
  const input = page.querySelector("[data-list-filter]");
  const railLinks = [...page.querySelectorAll(".tix-rail a[href^='#']")];
  const sections = railLinks.map((a) => {
    const heading = document.getElementById(a.getAttribute("href").slice(1));
    return heading && heading.closest("section");
  });
  const rows = () => [...page.querySelectorAll(".tix-main a.tool-card, .tix-main a.tool-card-lg")].filter((a) => !a.hidden);

  // The search and the anchors sit under the sticky topbar; its height changes with the wordmark and font load.
  const topbar = document.querySelector(".topbar");
  const setTopbar = () => { if (topbar) page.style.setProperty("--tix-topbar", topbar.offsetHeight + "px"); };
  setTopbar();
  window.addEventListener("resize", setTopbar, { passive: true });

  // Cmd K on a Mac, Ctrl K elsewhere (the shortcut itself lives in site.js).
  const key = page.querySelector("[data-filter-key]");
  if (key) {
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    key.textContent = mac ? "⌘ K" : "Ctrl K";
    key.hidden = false;
  }

  // Rail counts follow the filter, so the rail doubles as a summary of where the matches are.
  const recount = () => {
    railLinks.forEach((a, i) => {
      const sec = sections[i];
      if (!sec) return;
      const n = sec.querySelectorAll("a.tool-card:not([hidden]), a.tool-card-lg:not([hidden])").length;
      a.querySelector(".tix-count").textContent = n;
      a.toggleAttribute("data-empty", n === 0);
    });
  };
  if (input) {
    // site.js registered its listeners first, so the rows are already shown or hidden when these run.
    input.addEventListener("input", recount);
    input.addEventListener("keydown", (e) => { if (e.key === "Escape") recount(); });
  }

  // Mark the group in view. A thin band a third of the way down the viewport decides, so one group wins.
  if ("IntersectionObserver" in window) {
    const visible = new Set();
    const mark = () => {
      const i = sections.findIndex((s) => s && visible.has(s));
      if (i === -1) return;
      railLinks.forEach((a, j) => { if (j === i) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) visible.add(en.target); else visible.delete(en.target); });
      mark();
    }, { rootMargin: "-30% 0px -65% 0px" });
    sections.forEach((s) => s && io.observe(s));
  }

  // Arrow keys: Down from the search box goes to the first match, then Up and Down walk the visible rows.
  // Tab order is unchanged; this is a shortcut on top of it.
  page.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const list = rows();
    if (!list.length) return;
    if (e.target === input) {
      if (e.key !== "ArrowDown") return;
      e.preventDefault();
      list[0].focus();
      return;
    }
    const i = list.indexOf(e.target);
    if (i === -1) return;
    e.preventDefault();
    if (e.key === "ArrowDown") { if (i < list.length - 1) list[i + 1].focus(); }
    else if (i > 0) list[i - 1].focus();
    else if (input) input.focus();
  });
})();
