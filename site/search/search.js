// Site search over /search-index.json (built at deploy by
// scripts/gen_search_index.py). Every word typed must appear somewhere in a
// page's title, description, headings or section; titles weigh most.
(() => {
  const input = document.getElementById("q");
  const list = document.getElementById("results");
  const status = document.getElementById("search-status");
  if (!input || !list) return;

  // Words people type that the pages phrase differently.
  const SYNONYMS = { reference: ["citation", "bib"], references: ["citation", "bib"], cv: ["resume", "vitae"], word: ["docx", "word"], editor: ["moderntex", "editor"], price: ["pricing", "$"], cost: ["pricing", "$"], refund: ["refund", "terms"], reviewer: ["review", "reviewer"] };
  let index = [];
  const norm = (t) => (t || "").toLowerCase();

  const score = (e, terms) => {
    const t = norm(e.t), d = norm(e.d), h = norm((e.h || []).join(" ")), s = norm(e.s), u = norm(e.u);
    let total = 0;
    for (const term of terms) {
      const alts = [term].concat(SYNONYMS[term] || []);
      let best = 0;
      for (const a of alts) {
        if (t.includes(a)) best = Math.max(best, t.startsWith(a) ? 7 : 5);
        else if (h.includes(a)) best = Math.max(best, 2.5);
        else if (d.includes(a) || u.includes(a)) best = Math.max(best, 1.5);
        else if (s.includes(a)) best = Math.max(best, 1);
      }
      if (!best) return 0;
      total += best;
    }
    return total;
  };

  const render = () => {
    const terms = norm(input.value).split(/\s+/).filter((w) => w.length > 1);
    list.textContent = "";
    if (!terms.length) { status.textContent = ""; return; }
    const hits = index.map((e) => [score(e, terms), e]).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]).slice(0, 30);
    status.textContent = hits.length
      ? hits.length + (hits.length === 1 ? " page" : " pages")
      : "Nothing matches. Try fewer or shorter words, or email ben@purplelink.llc and say what you were looking for.";
    for (const [, e] of hits) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = e.u;
      a.className = "search-hit";
      const tag = document.createElement("span");
      tag.className = "search-tag";
      tag.textContent = e.s;
      const title = document.createElement("strong");
      title.textContent = e.t;
      const desc = document.createElement("span");
      desc.className = "search-desc";
      desc.textContent = e.d;
      a.append(tag, title, desc);
      li.append(a);
      list.append(li);
    }
  };

  let timer = 0;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      render();
      const url = input.value.trim() ? "?q=" + encodeURIComponent(input.value.trim()) : location.pathname;
      history.replaceState(null, "", url);
    }, 120);
  });
  document.getElementById("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const first = list.querySelector("a");
    if (first) location.href = first.href;
  });

  // The words searched for are counted when a result is opened.
  list.addEventListener("click", (e) => {
    if (e.target.closest("a") && window.plTrack) window.plTrack("search", norm(input.value).trim().slice(0, 60));
  });

  fetch("/search-index.json")
    .then((r) => r.json())
    .then((data) => {
      index = data;
      const q = new URLSearchParams(location.search).get("q");
      if (q) input.value = q;
      render();
    })
    .catch(() => { status.textContent = "Search could not load. Every page is listed on the tools and guides pages."; });
})();
