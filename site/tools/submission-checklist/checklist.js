// Submission checklist: ticks persist in localStorage (this browser only),
// with a progress count and a reset for the next paper. The page works as a
// plain list without JavaScript or storage.
(() => {
  const KEY = "pl_submission_checklist";
  const boxes = [...document.querySelectorAll("input[data-check]")];
  const count = document.querySelector("[data-checklist-count]");
  const total = document.querySelector("[data-checklist-total]");
  const bar = document.querySelector("[data-checklist-bar]");
  const reset = document.querySelector("[data-checklist-reset]");
  if (!boxes.length) return;

  let state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { state = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignore */ } };

  const render = () => {
    const done = boxes.filter((b) => b.checked).length;
    if (count) count.textContent = String(done);
    if (total) total.textContent = String(boxes.length);
    if (bar) bar.style.width = Math.round((done / boxes.length) * 100) + "%";
    boxes.forEach((b) => b.closest("li").classList.toggle("is-done", b.checked));
  };

  boxes.forEach((b) => {
    b.checked = !!state[b.dataset.check];
    b.addEventListener("change", () => {
      state[b.dataset.check] = b.checked;
      save();
      render();
      if (b.checked && window.plTrack) window.plTrack("checklist_tick", b.dataset.check);
    });
  });

  if (reset) {
    reset.addEventListener("click", () => {
      state = {};
      save();
      boxes.forEach((b) => { b.checked = false; });
      render();
    });
  }

  render();
})();
